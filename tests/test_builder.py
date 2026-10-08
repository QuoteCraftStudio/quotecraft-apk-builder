import base64
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import core
import server

def archive(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as z:
        for name, content in files.items(): z.writestr(name, content)
    return buffer.getvalue()

class Projects(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_complete_project_and_optional_permissions(self):
        project = core.create_project(self.root/'project', 'Mike\'s "Quote" & App', 'com.quotecraft.testapp', b'<h1>hello</h1>', 'hello.html', 2, True, False)
        manifest = ET.parse(project/'app/src/main/AndroidManifest.xml').getroot()
        permissions = [i.attrib['{http://schemas.android.com/apk/res/android}name'] for i in manifest.findall('uses-permission')]
        self.assertIn('android.permission.RECORD_AUDIO', permissions)
        self.assertNotIn('android.permission.CAMERA', permissions)
        ET.parse(project/'app/src/main/res/values/strings.xml')
        java = (project/'app/src/main/java/com/quotecraft/testapp/MainActivity.java').read_text()
        self.assertNotIn('__PACKAGE__', java)
        self.assertIn('MICROPHONE = true', java)
        self.assertIn('CAMERA = false', java)
        self.assertIn("versionCode 2", (project/'app/build.gradle').read_text())
        self.assertEqual((project/'app/src/main/assets/index.html').read_bytes(), b'<h1>hello</h1>')
    def test_zip_preserves_supporting_files(self):
        core.unpack(archive({'index.html':'hello','js/app.js':'alert(1)','css/style.css':'body{}'}), 'app.zip', self.root/'assets')
        self.assertTrue((self.root/'assets/js/app.js').is_file())
    def test_zip_traversal_absolute_backslash_and_drive_rejected(self):
        for index, path in enumerate(['../escape.txt','/escape.txt','..\\escape.txt','C:/escape.txt']):
            with self.assertRaises(ValueError): core.unpack(archive({'index.html':'hello',path:'bad'}), 'app.zip', self.root/str(index))
        self.assertFalse((self.root/'escape.txt').exists())
    def test_zip_symlink_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as z:
            item=zipfile.ZipInfo('index.html');item.create_system=3;item.external_attr=0o120777<<16
            z.writestr(item,'/etc/passwd')
        with self.assertRaises(ValueError): core.unpack(buffer.getvalue(),'app.zip',self.root/'assets')
    def test_zip_missing_index_and_case_duplicate_rejected(self):
        for index, files in enumerate([{'folder/index.html':'hello'},{'index.html':'hello','INDEX.HTML':'bad'}]):
            with self.assertRaises(ValueError): core.unpack(archive(files), 'app.zip', self.root/str(index))
    def test_expansion_limit(self):
        with patch.object(core,'MAX_EXPANDED',20):
            with self.assertRaises(ValueError): core.unpack(archive({'index.html':'X'*21}), 'app.zip', self.root/'assets')
    def test_bad_package_and_version(self):
        for package in ['com.app','com.app;echo.bad','COM.test.app','com.test.some-app','com.native.app']:
            with self.assertRaises(ValueError): core.validate('name',package)
        with self.assertRaises(ValueError): core.create_project(self.root/'p','name','com.test.app',b'x','app.html',0)
    def test_missing_toolchain_stops_before_build(self):
        with patch.object(core,'toolchain',return_value={'missing':['SDK unavailable']}):
            with self.assertRaisesRegex(RuntimeError,'SDK unavailable'): core.build(self.root,'com.test.app',lambda text:None)

class API(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = patch.object(server,'DATA',Path(self.tmp.name));self.patch.start()
        self.http,self.token,_=server.start_server(port=0)
        self.port=self.http.server_address[1]
        self.url=f'http://127.0.0.1:{self.port}'
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join();self.patch.stop();self.tmp.cleanup()
    def request(self,path,body=None,token=True,extra=None):
        headers={'Authorization':'Bearer '+self.token} if token else {}
        headers.update(extra or {})
        if body is not None: headers['Content-Type']='application/json'
        req=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=5) as response:return response.status,response.read()
        except urllib.error.HTTPError as error:return error.code,error.read()
    def test_pairing_and_host_check(self):
        self.assertEqual(self.request('/api/tools',token=False)[0],401)
        self.assertEqual(self.request('/api/tools')[0],200)
        self.assertEqual(self.request('/',extra={'Host':'malicious.example'})[0],403)
        self.assertEqual(self.request('/')[0],200)
    def test_cross_origin_upload_denied(self):
        self.assertEqual(self.request('/api/jobs',{},extra={'Origin':'https://evil.example'})[0],403)
    def test_bad_upload_and_rollback(self):
        fields={'name':'Test','package':'com.test.app','version':1,'filename':'app.zip','data':base64.b64encode(archive({'nested/index.html':'bad'})).decode()}
        self.assertEqual(self.request('/api/jobs',fields)[0],400)
        self.assertEqual(list((Path(self.tmp.name)/'jobs').iterdir()),[])
    def test_build_poll_and_download_flow(self):
        def simulated_build(project,package,report):
            report('Simulated test build\n'); apk=project/'test.apk';apk.write_bytes(b'TEST-ONLY');return apk
        with patch.object(server,'build',side_effect=simulated_build):
            fields={'name':'Test','package':'com.test.app','version':1,'filename':'app.html','data':base64.b64encode(b'<h1>hello</h1>').decode()}
            code,body=self.request('/api/jobs',fields);self.assertEqual(code,202)
            identifier=json.loads(body)['id']
            for _ in range(50):
                code,body=self.request('/api/jobs/'+identifier)
                job=json.loads(body)
                if job['status']=='complete':break
                time.sleep(.01)
            self.assertEqual(job['status'],'complete')
            self.assertNotIn('project',job)
            self.assertEqual(self.request('/api/jobs/'+identifier+'/apk'),(200,b'TEST-ONLY'))
    def test_no_unpaired_apk_download(self):
        self.assertEqual(self.request('/api/jobs/missing/apk',token=False)[0],401)

if __name__ == '__main__': unittest.main()
