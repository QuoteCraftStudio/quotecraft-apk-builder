"""Project generation and local Android build engine. No third-party Python packages."""
from __future__ import annotations
import base64
import html
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'QuoteCraftAPKBuilder'
MAX_UPLOAD = 40 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024
APP_ORIGIN = 'https://appassets.androidplatform.net'

def validate(name, package):
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
        raise ValueError('Enter an app name between 1 and 60 characters.')
    if any(ord(c) < 32 for c in name):
        raise ValueError('App name cannot contain control characters.')
    if not isinstance(package, str) or not re.fullmatch(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,}', package):
        raise ValueError('App ID must look like com.quotecraft.myapp, using lowercase letters.')
    if len(package) > 150:
        raise ValueError('App ID is too long.')
    reserved = {'abstract','assert','boolean','break','byte','case','catch','char','class','const','continue','default','do','double','else','enum','extends','final','finally','float','for','goto','if','implements','import','instanceof','int','interface','long','native','new','package','private','protected','public','return','short','static','strictfp','super','switch','synchronized','this','throw','throws','transient','try','void','volatile','while','true','false','null','_'}
    if any(part in reserved for part in package.split('.')):
        raise ValueError('App ID contains a reserved Java word. Choose a different app ID.')

def unpack(payload, filename, assets):
    if not payload or len(payload) > MAX_UPLOAD:
        raise ValueError('Choose an HTML file or ZIP no larger than 40 MB.')
    assets.mkdir(parents=True)
    suffix = Path(filename).suffix.lower()
    if suffix in ('.html', '.htm'):
        payload.decode('utf-8-sig')
        (assets / 'index.html').write_bytes(payload)
        return
    if suffix != '.zip':
        raise ValueError('Only HTML and ZIP files are supported.')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = archive.infolist()
        if len(members) > 5000 or sum(i.file_size for i in members) > MAX_EXPANDED:
            raise ValueError('ZIP expands beyond 100 MB or contains too many files.')
        seen = set()
        for info in members:
            path = PurePosixPath(info.filename)
            if '\\' in info.filename or path.is_absolute() or '..' in path.parts or ':' in info.filename:
                raise ValueError('ZIP contains an unsafe path.')
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('ZIP cannot contain symbolic links.')
            target = assets.joinpath(*path.parts)
            key = str(path).casefold()
            if key in seen:
                raise ValueError('ZIP contains duplicate file paths.')
            seen.add(key)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, target.open('wb') as dest:
                    shutil.copyfileobj(src, dest)
    if not (assets / 'index.html').is_file():
        raise ValueError('ZIP must contain index.html at its top level, alongside any CSS, JavaScript or images.')

def toolchain():
    sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if not sdk and os.name == 'nt':
        sdk = str(Path(os.environ.get('LOCALAPPDATA', '')) / 'Android' / 'Sdk')
    java = os.environ.get('JAVA_HOME')
    if not java and os.name == 'nt':
        candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Android' / 'Android Studio' / 'jbr'
        if candidate.exists():
            java = str(candidate)
    gradle = os.environ.get('QUOTECRAFT_GRADLE') or shutil.which('gradle')
    installed = DATA / 'tools' / 'gradle-8.11.1' / 'bin' / ('gradle.bat' if os.name == 'nt' else 'gradle')
    if not gradle and installed.exists():
        gradle = str(installed)
    keytool = str(Path(java) / 'bin' / ('keytool.exe' if os.name == 'nt' else 'keytool')) if java else shutil.which('keytool')
    missing = []
    if not java:
        missing.append('JDK: install Android Studio or set JAVA_HOME to a JDK 17 or newer compatible with Gradle 8.11.1.')
    if not sdk or not (Path(sdk) / 'platforms' / 'android-35' / 'android.jar').exists():
        missing.append('Android SDK Platform 35: install it in Android Studio > SDK Manager.')
    if not sdk or not (Path(sdk) / 'build-tools' / '35.0.0').is_dir():
        missing.append('Android SDK Build-Tools 35.0.0: install it in SDK Manager > SDK Tools > Show Package Details.')
    if not gradle:
        missing.append('Gradle 8.11.1: run Install-Gradle.ps1 once.')
    if not keytool or not Path(keytool).exists():
        missing.append('Java keytool is missing: check the JDK installation.')
    return dict(sdk=sdk, java=java, gradle=gradle, keytool=keytool, missing=missing)

def create_project(directory, name, package, payload, filename, version, microphone=False, camera=False):
    validate(name, package)
    if not isinstance(version, int) or not 1 <= version <= 2100000000:
        raise ValueError('Version number must be a positive whole number.')
    directory.mkdir(parents=True, exist_ok=False)
    main = directory / 'app' / 'src' / 'main'
    unpack(payload, filename, main / 'assets')
    java = main / 'java' / Path(*package.split('.'))
    java.mkdir(parents=True)
    source = (ROOT / 'templates' / 'MainActivity.java').read_text().replace('__PACKAGE__', package)
    source = source.replace('__MICROPHONE__', str(bool(microphone)).lower()).replace('__CAMERA__', str(bool(camera)).lower())
    (java / 'MainActivity.java').write_text(source, encoding='utf-8')
    resources = main / 'res' / 'values'
    resources.mkdir(parents=True)
    label = html.escape(name.strip().replace('\\', '\\\\').replace('"', '\\"'))
    (resources / 'strings.xml').write_text('<resources><string name="app_name">"' + label + '"</string></resources>', encoding='utf-8')
    permissions = '<uses-permission android:name="android.permission.INTERNET"/>'
    if microphone:
        permissions += '<uses-permission android:name="android.permission.RECORD_AUDIO"/>'
    if camera:
        permissions += '<uses-permission android:name="android.permission.CAMERA"/><uses-feature android:name="android.hardware.camera" android:required="false"/>'
    (main / 'AndroidManifest.xml').write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android">''' + permissions + '''
    <application android:label="@string/app_name" android:allowBackup="false" android:usesCleartextTraffic="false" android:theme="@android:style/Theme.Material.Light.NoActionBar">
      <activity android:name=".MainActivity" android:exported="true" android:configChanges="orientation|screenSize|keyboardHidden">
        <intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter>
      </activity>
    </application></manifest>''', encoding='utf-8')
    (directory / 'settings.gradle').write_text("pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }\ndependencyResolutionManagement { repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); repositories { google(); mavenCentral() } }\nrootProject.name = 'QuoteCraftApp'\ninclude ':app'\n")
    (directory / 'build.gradle').write_text("plugins { id 'com.android.application' version '8.10.1' apply false }\n")
    (directory / 'gradle.properties').write_text('android.useAndroidX=true\norg.gradle.jvmargs=-Xmx1536m -Dfile.encoding=UTF-8\norg.gradle.workers.max=2\n')
    (directory / 'app' / 'build.gradle').write_text('''plugins { id 'com.android.application' }
android {
    namespace '__PACKAGE__'
    compileSdk 35
    buildToolsVersion '35.0.0'
    defaultConfig {
        applicationId '__PACKAGE__'
        minSdk 26
        targetSdk 35
        versionCode __VERSION__
        versionName '__VERSION__.0'
    }
    signingConfigs {
        release {
            storeFile file(System.getenv('QC_KEYSTORE'))
            storePassword System.getenv('QC_KEYPASS')
            keyAlias 'quotecraft'
            keyPassword System.getenv('QC_KEYPASS')
        }
    }
    buildTypes { release { signingConfig signingConfigs.release; minifyEnabled false } }
    compileOptions { sourceCompatibility JavaVersion.VERSION_17; targetCompatibility JavaVersion.VERSION_17 }
}
dependencies { implementation 'androidx.webkit:webkit:1.12.1' }
'''.replace('__PACKAGE__', package).replace('__VERSION__', str(version)))
    return directory

def build(project, package, report):
    tools = toolchain()
    if tools['missing']:
        raise RuntimeError('\n'.join(tools['missing']))
    env = os.environ.copy()
    env.update(JAVA_HOME=tools['java'], ANDROID_HOME=tools['sdk'])
    keys = DATA / 'signing' / package
    keys.mkdir(parents=True, exist_ok=True)
    key = keys / 'release.jks'
    secret = keys / 'password.txt'
    if key.exists() != secret.exists():
        raise RuntimeError('Signing key files are incomplete. Restore the matching key and password from your backup.')
    if not key.exists():
        password = secrets.token_urlsafe(32)
        env['QC_KEYPASS'] = password
        # Password travels through environment variables, never command arguments or logs.
        result = subprocess.run([tools['keytool'], '-genkeypair', '-keystore', str(key), '-alias', 'quotecraft', '-storepass:env', 'QC_KEYPASS', '-keypass:env', 'QC_KEYPASS', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000', '-dname', 'CN=QuoteCraft App'], env=env, capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise RuntimeError('Could not create the signing key: ' + result.stderr[-1000:])
        secret.write_text(password)
        try:
            key.chmod(0o600); secret.chmod(0o600)
        except OSError:
            pass
    env.update(QC_KEYSTORE=str(key), QC_KEYPASS=secret.read_text().strip())
    report('Building your signed APK. The first build downloads Android dependencies and can take several minutes.\n')
    # Local trusted Gradle launcher; uploaded files never become build scripts.
    command = [tools['gradle'], '--no-daemon', '--console=plain', 'assembleRelease']
    log_path = project / 'build.log'
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=project, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            process.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()
            raise RuntimeError('Build exceeded 30 minutes. Check the log in the project folder.')
    output = log_path.read_text(encoding='utf-8', errors='replace')
    report(output[-16000:])
    apk = project / 'app' / 'build' / 'outputs' / 'apk' / 'release' / 'app-release.apk'
    if process.returncode or not apk.is_file():
        raise RuntimeError('Android build failed. The build log above has the details.')
    return apk
