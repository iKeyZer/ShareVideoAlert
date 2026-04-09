import http.server
import socketserver
import subprocess
import json
import urllib.parse
import os
import sys
import re
import glob

PORT = 8765
DIR  = os.path.dirname(os.path.abspath(__file__))
req_counter = 0

def cleanup_temp_files(except_req=None):
    for f in glob.glob(os.path.join(DIR, 'temp_video_*.mp4')):
        if except_req is not None and f.endswith(f'temp_video_{except_req}.mp4'):
            continue
        try:
            os.remove(f)
        except Exception:
            pass

class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_video(self, filepath):
        file_size = os.path.getsize(filepath)
        range_header = self.headers.get('Range')
        if range_header:
            m = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if m:
                start  = int(m.group(1))
                end    = int(m.group(2)) if m.group(2) else file_size - 1
                end    = min(end, file_size - 1)
                length = end - start + 1
                self.send_response(206)
                self.send_header('Content-Type', 'video/mp4')
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Content-Length', str(length))
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                try:
                    with open(filepath, 'rb') as f:
                        f.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk = f.read(min(65536, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                except (ConnectionResetError, BrokenPipeError):
                    pass
            else:
                self.send_response(416); self.end_headers()
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'video/mp4')
            self.send_header('Content-Length', str(file_size))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            try:
                with open(filepath, 'rb') as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except (ConnectionResetError, BrokenPipeError):
                pass

    def serve_static(self, filepath):
        ext   = os.path.splitext(filepath)[1].lower()
        types = {'.html': 'text/html; charset=utf-8', '.js': 'application/javascript',
                 '.css': 'text/css', '.png': 'image/png', '.ico': 'image/x-icon'}
        ctype = types.get(ext, 'application/octet-stream')
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(os.path.getsize(filepath)))
        self.end_headers()
        with open(filepath, 'rb') as f:
            self.wfile.write(f.read())

    def do_GET(self):
        global req_counter
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path.rstrip('/')

        if path == '/video-url':
            params = urllib.parse.parse_qs(parsed.query)
            url    = params.get('url', [''])[0]
            if not url:
                self.send_json(400, {'error': 'no url'}); return

            req_counter += 1
            my_req    = req_counter
            temp_file = os.path.join(DIR, f'temp_video_{my_req}.mp4')
            cleanup_temp_files(except_req=my_req)

            print(f'[yt-dlp] #{my_req} Descargando: {url[:70]}')

            result = subprocess.run(
                [sys.executable, '-m', 'yt_dlp',
                 '--no-playlist', '--no-warnings',
                 '-f', 'best[ext=mp4][height<=720]/best[ext=mp4]/best',
                 '-o', temp_file, url],
                capture_output=True, text=True, timeout=60
            )

            if result.returncode == 0 and os.path.exists(temp_file):
                size_mb = os.path.getsize(temp_file) / 1024 / 1024
                print(f'[yt-dlp] #{my_req} OK — {size_mb:.1f} MB')
                self.send_json(200, {'url': f'http://localhost:{PORT}/temp_video_{my_req}.mp4'})
            else:
                err = result.stderr.strip().split('\n')[-1] if result.stderr else 'error'
                print(f'[yt-dlp] #{my_req} Error: {err}')
                self.send_json(500, {'error': err})

        elif re.match(r'^/temp_video_\d+\.mp4$', path):
            filepath = os.path.join(DIR, path.lstrip('/'))
            if os.path.exists(filepath):
                self.serve_video(filepath)
            else:
                self.send_response(404); self.end_headers()

        else:
            fp = os.path.join(DIR, parsed.path.lstrip('/')) if parsed.path != '/' else os.path.join(DIR, 'index.html')
            if os.path.isfile(fp):
                self.serve_static(fp)
            else:
                self.send_response(404); self.end_headers()


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


cleanup_temp_files()
print(f'Servidor corriendo en http://localhost:{PORT}')
print(f'URL para OBS: http://localhost:{PORT}/video-share-alert-v2.html')
print('No cierres esta ventana. Ctrl+C para detener.\n')
ThreadedHTTPServer(('', PORT), Handler).serve_forever()
