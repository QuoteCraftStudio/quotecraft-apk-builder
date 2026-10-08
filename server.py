from __future__ import annotations
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import socket
import threading
import time
from urllib.parse import urlsplit
import webbrowser
from core import DATA, MAX_UPLOAD, ROOT, build, create_project, toolchain, validate

class Jobs:
    def __init__(self):
        self.items = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=1)

    def submit(self, fields):
        name, package = fields.get('name', ''), fields.get('package', '')
        validate(name, package)
        if type(fields.get('version')) is not int:
            raise ValueError('Version number must be a whole number.')
        if not isinstance(fields.get('data'), str):
            raise ValueError('Select your HTML or ZIP file.')
        payload = base64.b64decode(fields['data'], validate=True)
        if not payload or len(payload) > MAX_UPLOAD:
            raise ValueError('File must be between 1 byte and 40 MB.')
        if type(fields.get('microphone', False)) is not bool or type(fields.get('camera', False)) is not bool:
            raise ValueError('Permission settings must be true or false.')
        identifier = secrets.token_hex(12)
        with self.lock:
            if sum(j['status'] in ('queued', 'building') for j in self.items.values()) >= 3:
                raise ValueError('Three builds are already queued. Wait for one to finish.')
            if len(self.items) >= 50:
                raise ValueError('Restart the builder after 50 jobs. Completed APKs remain saved on disk.')
            project = DATA / 'jobs' / identifier
            try:
                create_project(project, name, package, payload, fields.get('filename', ''), fields['version'], fields.get('microphone', False), fields.get('camera', False))
            except Exception:
                import shutil
                if project.exists(): shutil.rmtree(project)
                raise
            job = dict(id=identifier, name=name, package=package, status='queued', log='Queued for build.\n', project=str(project), apk=None)
            self.items[identifier] = job
        self.executor.submit(self.run, identifier)
        return identifier

    def run(self, identifier):
        with self.lock: self.items[identifier]['status'] = 'building'
        def report(text):
            with self.lock: self.items[identifier]['log'] = (self.items[identifier]['log'] + text)[-22000:]
        try:
            job = self.items[identifier]
            apk = build(__import__('pathlib').Path(job['project']), job['package'], report)
            with self.lock: job.update(status='complete', apk=str(apk))
            report('\nAPK is ready. Download it below.\n')
        except Exception as e:
            report('\n' + str(e) + '\n')
            with self.lock: self.items[identifier]['status'] = 'failed'

    def get(self, identifier):
        with self.lock:
            if identifier not in self.items: return None
            return dict(self.items[identifier])

def local_addresses():
    addresses = {'127.0.0.1', 'localhost'}
    try: addresses.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError: pass
    return addresses

def start_server(phone=False, port=8765):
    token = secrets.token_urlsafe(24)
    jobs = Jobs()
    hosts = local_addresses()
    failures = {}
    failure_lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(30)
        def log_message(self, *args): pass
        def send(self, code, body, mime='application/json'):
            if isinstance(body, dict): body = json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            value = self.headers.get('Host', '')
            return value in {f'{h}:{port}' for h in hosts}

        def authorized(self):
            now = time.monotonic()
            with failure_lock:
                count, until = failures.get(self.client_address[0], (0, 0))
                if now < until: return False
                ok = secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token)
                if ok: failures.pop(self.client_address[0], None)
                else:
                    count += 1
                    failures[self.client_address[0]] = (count, now + 30 if count >= 10 else 0)
                return ok

        def do_GET(self):
            if not self.valid_host(): self.send(403, {'error':'Invalid builder address.'}); return
            path = urlsplit(self.path).path
            public = {'/': ('index.html','text/html; charset=utf-8'), '/app.js':('app.js','text/javascript; charset=utf-8'), '/style.css':('style.css','text/css; charset=utf-8')}
            if path in public:
                filename, mime = public[path]
                self.send(200, (ROOT/'web'/filename).read_bytes(), mime); return
            if not self.authorized(): self.send(401, {'error':'Enter the pairing code shown on your Windows computer.'}); return
            if path == '/api/tools':
                self.send(200, {'missing':toolchain()['missing']}); return
            if path.startswith('/api/jobs/'):
                parts = path.split('/')
                job = jobs.get(parts[3])
                if not job: self.send(404, {'error':'Build not found.'}); return
                if len(parts) == 5 and parts[4] == 'apk':
                    if job['status'] != 'complete': self.send(409, {'error':'APK is not ready yet.'}); return
                    self.send(200, __import__('pathlib').Path(job['apk']).read_bytes(), 'application/vnd.android.package-archive'); return
                if len(parts) == 4:
                    self.send(200, {k:job[k] for k in ('id','name','package','status','log')}); return
            self.send(404, {'error':'Page not found.'})

        def do_POST(self):
            if not self.valid_host(): self.send(403, {'error':'Invalid builder address.'}); return
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                self.send(403, {'error':'Use the builder page on this computer.'}); return
            if not self.authorized(): self.send(401, {'error':'Pairing code is incorrect.'}); return
            if urlsplit(self.path).path != '/api/jobs': self.send(404, {'error':'Page not found.'}); return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_UPLOAD * 4 // 3 + 10000:
                    raise ValueError('Upload is too large; maximum file size is 40 MB.')
                if not self.headers.get('Content-Type','').startswith('application/json'):
                    raise ValueError('Expected JSON upload.')
                fields = json.loads(self.rfile.read(length))
                if not isinstance(fields, dict): raise ValueError('Invalid upload.')
                identifier = jobs.submit(fields)
                self.send(202, {'id':identifier})
            except (ValueError, TypeError, KeyError, UnicodeError) as e:
                self.send(400, {'error':str(e)})
            except Exception:
                self.send(400, {'error':'Could not read the upload. Check that your ZIP is valid and contains index.html.'})
    server = ThreadingHTTPServer(('0.0.0.0' if phone else '127.0.0.1', port), Handler)
    port = server.server_address[1]
    server.daemon_threads = True
    return server, token, hosts

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phone', action='store_true')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server, token, hosts = start_server(args.phone,args.port)
    print('\nQuoteCraft APK Builder\nPairing code: ' + token)
    print('On this computer: http://127.0.0.1:' + str(args.port))
    if args.phone:
        for host in sorted(hosts - {'127.0.0.1','localhost'}): print('On your Android phone: http://' + host + ':' + str(args.port))
        print('Both devices must be on the same trusted Wi-Fi. Allow Private networks if Windows asks.')
    webbrowser.open('http://127.0.0.1:' + str(args.port) + '/#' + token)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__ == '__main__': main()
