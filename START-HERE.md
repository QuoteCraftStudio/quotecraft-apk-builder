# QuoteCraft HTML-to-APK Builder

## What you have

A Windows desktop launcher and a mobile-friendly Android browser interface. Windows compiles a real, signed APK using the Android SDK and Gradle. Your phone can upload HTML or ZIP files, start builds and download APKs while your computer is running.

This package is source and launch scripts, not a precompiled Windows EXE or an Android builder APK. Android uses Chrome for the builder interface; the phone does not compile locally. The generated Android apps use a native WebView shell. No ad SDK or analytics code is added by this builder. Existing ads or tracking in your uploaded HTML remain in that HTML.

## One-time Windows setup

1. Use your existing Python installation, or install Python 3.10 or newer from https://www.python.org/downloads/windows/. Include the Python launcher and Tcl/Tk during installation.
2. Install Android Studio from https://developer.android.com/studio. Its bundled Java runtime can be used by this builder.
3. In Android Studio, open SDK Manager. Install **Android SDK Platform 35**. Under SDK Tools, enable **Show Package Details**, then install **Android SDK Build-Tools 35.0.0**. Review and accept any Android SDK licence prompts yourself.
4. Right-click **Install-Gradle.ps1** and choose **Run with PowerShell**. It downloads Gradle 8.11.1 from its official distribution site and checks the published SHA-256 before extracting it. If PowerShell is blocked, install Gradle 8.11.1 following https://gradle.org/install/ and set QUOTECRAFT_GRADLE to its gradle.bat path. You do not need to disable a security setting.

The first Android build downloads the Android build plugin and AndroidX library. Later builds reuse the downloaded dependencies. Internet access is therefore needed for initial setup and the first build. No paid API or online build service is required.

## Build on Windows

1. Extract this ZIP into a normal folder.
2. Double-click **Start-Windows.cmd**. A desktop control window opens.
3. Click **Open Builder**. The builder opens in your browser and pairs automatically.
4. Enter an app name and permanent app ID, such as **com.quotecraft.quickquote**.
5. Choose your HTML file. If it uses separate JavaScript, CSS or images, upload a ZIP with **index.html at its top level**, alongside those files.
6. Enable microphone or camera only if that app needs them.
7. Click **Build APK**, wait for completion, then **Download APK**.

If the desktop control window cannot open, double-click Start-With-Android-Phone.cmd to use the browser and console interface instead.

## Use your Android phone

1. In the Windows control window, enable **Allow my Android phone...** before opening the builder. Alternatively run **Start-With-Android-Phone.cmd**.
2. Keep the computer and phone on the same trusted Wi-Fi. The control window or console shows the computer address and pairing code.
3. Open that address in Chrome on the phone, enter the code and select your HTML or ZIP.
4. Start the build and download the completed APK on the phone.

Windows may ask whether to permit access: use your Private network. Do not expose this service to the internet or forward its port. Local phone communication uses HTTP, so use it only on trusted Wi-Fi. Closing the builder disconnects the phone. A new pairing code is generated each time the builder starts.

Install downloaded APKs through Android's normal file/install screen. Android may ask you to allow installations from the browser or file manager. These APKs are for direct installation; this builder does not publish to Google Play or produce Play Store app bundles.

## Updates and your signing keys

Keep the same app ID and increase the version number for updates. Your signing key and its password are saved at:

`%LOCALAPPDATA%\QuoteCraftAPKBuilder\signing\YOUR.APP.ID\`

Back up the entire signing folder privately. Do not upload it to GitHub. You need the same signing key to update an app already installed on a phone. APKs, generated projects and build logs remain under `%LOCALAPPDATA%\QuoteCraftAPKBuilder\jobs\`.

## Compatibility and limits

- Generated apps support Android 8.0 and newer.
- File uploads are limited to 40 MB; ZIPs may expand to 100 MB.
- Basic HTML, JavaScript and browser localStorage are supported. External network requests remain subject to WebView CORS rules and require HTTPS.
- Use relative paths for supporting assets, such as `js/app.js`, rather than website-root paths such as `/js/app.js`.
- Native file picking is included, as are optional runtime microphone/camera permissions.
- Browser speech recognition is **not guaranteed** in Android WebView. A native speech-recognition integration may be needed for your Translator.
- Printing, sharing, blob/data downloads (such as backup exports) and PDF rendering need app-specific testing or native integrations. Packaged file export is not implemented in this first version.
- The wrapper cannot clean up or repair broken HTML automatically.
- Default Android launcher icon is used in this version; custom app icons are not implemented.
- Each app gets its own private browser storage. Existing website data is not migrated.
- You can queue up to three builds. Restart after 50 jobs; saved APKs remain on disk.

## Verification

Python project generation, ZIP path protections, API pairing checks and the asynchronous build flow were tested. JavaScript syntax and generated XML were checked. An Android build and device installation could not be run in the creation environment because it lacks the Android SDK/JDK compiler and cannot download the required build dependencies. Full APK, speech and device behaviour remain unverified until a build succeeds on your Windows computer.

Pinned build tools: Android Gradle Plugin 8.10.1, Gradle 8.11.1, compile/target SDK 35, AndroidX WebKit 1.12.1. These are intentional compatible versions, not a claim that they are the newest releases.

## Optional: make a Windows EXE

Double-click **Build-Windows.cmd** on Windows to package the EXE. The included GitHub Actions workflow can also compile it on a Windows runner after the project is uploaded to a repository. These packaging routes do not run application tests.

On Windows with Python installed:

```text
py -3 -m pip install pyinstaller
py -3 -m PyInstaller --noconfirm --onefile --windowed --name QuoteCraft-APK-Builder --add-data "web;web" --add-data "templates;templates" desktop.py
```

The EXE appears in the dist folder. It still requires the Android build tools installed separately. This EXE build has not been run here.
