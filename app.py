import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import sys
import os
import re
import glob
import json
import http.server
import socketserver
import urllib.parse
from datetime import datetime

PORT = 8765

# Directorios segun si corre como exe o como script
if getattr(sys, 'frozen', False):
    BASE_DIR   = os.path.dirname(sys.executable)   # donde esta el .exe
    STATIC_DIR = sys._MEIPASS                       # archivos bundleados
else:
    BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
    STATIC_DIR = BASE_DIR

CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
req_counter = 0
app_instance = None


def cleanup_temp(except_req=None):
    for f in glob.glob(os.path.join(BASE_DIR, 'temp_video_*.mp4')):
        if except_req and f.endswith(f'temp_video_{except_req}.mp4'):
            continue
        try:
            os.remove(f)
        except Exception:
            pass


class YTDLLogger:
    def debug(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg):
        if app_instance:
            app_instance.log('yt-dlp: ' + msg[:80])


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

    def serve_file(self, filepath, ctype):
        with open(filepath, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        global req_counter, app_instance
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path.rstrip('/')

        if path == '/video-url':
            params = urllib.parse.parse_qs(parsed.query)
            url    = params.get('url', [''])[0]
            if not url:
                self.send_json(400, {'error': 'no url'}); return

            req_counter += 1
            my_req    = req_counter
            temp_file = os.path.join(BASE_DIR, f'temp_video_{my_req}.mp4')
            cleanup_temp(except_req=my_req)

            if app_instance:
                app_instance.log(f'Descargando video de: {url[:50]}...')

            try:
                import yt_dlp
                ydl_opts = {
                    'format':       'best[ext=mp4][height<=720]/best[ext=mp4]/best',
                    'outtmpl':      temp_file,
                    'quiet':        True,
                    'no_warnings':  True,
                    'logger':       YTDLLogger(),
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                if os.path.exists(temp_file):
                    size_mb = os.path.getsize(temp_file) / 1024 / 1024
                    if app_instance:
                        app_instance.log(f'Video listo ({size_mb:.1f} MB)')
                    self.send_json(200, {'url': f'http://localhost:{PORT}/temp_video_{my_req}.mp4'})
                else:
                    self.send_json(500, {'error': 'archivo no generado'})

            except Exception as e:
                if app_instance:
                    app_instance.log(f'Error descarga: {str(e)[:60]}')
                self.send_json(500, {'error': str(e)[:200]})

        elif path in ('', '/', '/video-share-alert-v2.html'):
            html_path = os.path.join(STATIC_DIR, 'video-share-alert-v2.html')
            if os.path.exists(html_path):
                self.serve_file(html_path, 'text/html; charset=utf-8')
            else:
                self.send_response(404); self.end_headers()

        elif re.match(r'^/temp_video_\d+\.mp4$', path):
            filepath = os.path.join(BASE_DIR, path.lstrip('/'))
            if os.path.exists(filepath):
                self.serve_video(filepath)
            else:
                self.send_response(404); self.end_headers()
        else:
            self.send_response(404); self.end_headers()


class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


# ─────────────────────────── GUI ───────────────────────────

class App:
    def __init__(self):
        global app_instance
        app_instance = self

        self.root = tk.Tk()
        self.root.title('Video Share Alert')
        self.root.geometry('520x740')
        self.root.resizable(False, False)
        self.root.configure(bg='#1e1e2e')

        # Icono de la ventana
        icon_path = os.path.join(STATIC_DIR, '19-1.png')
        if os.path.exists(icon_path):
            try:
                icon = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, icon)
            except Exception:
                pass

        self.channel_var  = tk.StringVar(value='tu_canal')
        self.duration_var = tk.StringVar(value='10')

        self.build_ui()
        self.load_config()
        self.root.after(400, self.start_server)

    # ── UI ──────────────────────────────────────────────────
    def build_ui(self):
        # Header morado
        header = tk.Frame(self.root, bg='#9147ff', height=65)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text='Video Share Alert',
                 font=('Segoe UI', 17, 'bold'), bg='#9147ff', fg='white').pack(pady=(12, 0))
        tk.Label(header, text='Licenciado por KeyZer',
                 font=('Segoe UI', 8), bg='#9147ff', fg='#d4baff').pack()

        # Cuerpo
        body = tk.Frame(self.root, bg='#1e1e2e', padx=22, pady=14)
        body.pack(fill='both', expand=True)

        # — Configuración —
        self._section(body, 'CONFIGURACIÓN')

        self._row(body, 'Canal de Twitch:', self.channel_var, width=22)
        self._row(body, 'Duración (segundos):', self.duration_var, width=6)

        tk.Button(body, text='Guardar', command=self.save_config,
                  bg='#9147ff', fg='white', font=('Segoe UI', 9, 'bold'),
                  relief='flat', cursor='hand2', padx=14, pady=4).pack(anchor='e', pady=(2, 10))

        # — Estado —
        self._section(body, 'ESTADO DEL SERVIDOR')

        status_row = tk.Frame(body, bg='#1e1e2e')
        status_row.pack(fill='x', pady=(2, 6))
        self.dot = tk.Label(status_row, text='●', font=('Segoe UI', 13),
                            bg='#1e1e2e', fg='#f38ba8')
        self.dot.pack(side='left')
        self.status_lbl = tk.Label(status_row, text='Iniciando...',
                                   font=('Segoe UI', 10), bg='#1e1e2e', fg='#cdd6f4')
        self.status_lbl.pack(side='left', padx=8)

        tk.Label(body, text='URL para OBS:', font=('Segoe UI', 9),
                 bg='#1e1e2e', fg='#6c7086').pack(anchor='w')

        url_box = tk.Frame(body, bg='#313244', padx=10, pady=7)
        url_box.pack(fill='x', pady=(2, 4))
        self.url_lbl = tk.Label(url_box, text='Esperando...',
                                font=('Consolas', 9), bg='#313244', fg='#a6e3a1',
                                anchor='w', wraplength=430, justify='left')
        self.url_lbl.pack(fill='x')

        btn_row = tk.Frame(body, bg='#1e1e2e')
        btn_row.pack(fill='x', pady=(0, 4))
        tk.Button(btn_row, text='Copiar URL', command=self.copy_url,
                  bg='#313244', fg='#cdd6f4', font=('Segoe UI', 9),
                  relief='flat', cursor='hand2', padx=10, pady=3).pack(side='right')
        tk.Label(btn_row, text='Tamaño en OBS: 600 × 820 px',
                 font=('Segoe UI', 9, 'italic'), bg='#1e1e2e', fg='#6c7086').pack(side='left')

        # — Guía OBS —
        self._section(body, 'COMO CONFIGURAR EN OBS')

        pasos = (
            '1.  Abre OBS Studio\n'
            '2.  En "Fuentes" → haz clic en  +  → "Fuente de navegador"\n'
            '3.  Escribe cualquier nombre y haz clic en "Aceptar"\n'
            '4.  Pega la URL de arriba en el campo  URL\n'
            '5.  Cambia el Ancho a 600  y el Alto a 820\n'
            '6.  Haz clic en "Aceptar"\n'
            '7.  Mueve y posiciona la fuente donde quieras en tu escena\n'
            '8.  Los links del chat se mostraran automaticamente'
        )
        tk.Label(body, text=pasos, font=('Segoe UI', 9),
                 bg='#1e1e2e', fg='#cdd6f4', justify='left', anchor='w').pack(anchor='w', pady=(2, 10))

        # — Actividad —
        self._section(body, 'ACTIVIDAD')

        self.log_box = scrolledtext.ScrolledText(
            body, height=7, font=('Consolas', 8),
            bg='#11111b', fg='#a6e3a1', relief='flat',
            state='disabled', wrap='word'
        )
        self.log_box.pack(fill='x')

    def _section(self, parent, title):
        f = tk.Frame(parent, bg='#1e1e2e')
        f.pack(fill='x', pady=(8, 3))
        tk.Label(f, text=title, font=('Segoe UI', 8, 'bold'),
                 bg='#1e1e2e', fg='#9147ff').pack(side='left')
        tk.Frame(f, bg='#313244', height=1).pack(side='left', fill='x', expand=True, padx=(8, 0))

    def _row(self, parent, label, var, width=20):
        f = tk.Frame(parent, bg='#1e1e2e')
        f.pack(fill='x', pady=(0, 5))
        tk.Label(f, text=label, font=('Segoe UI', 10),
                 bg='#1e1e2e', fg='#cdd6f4', width=21, anchor='w').pack(side='left')
        tk.Entry(f, textvariable=var, font=('Segoe UI', 10), width=width,
                 bg='#313244', fg='white', insertbackground='white',
                 relief='flat', bd=5).pack(side='left')

    # ── Lógica ──────────────────────────────────────────────
    def log(self, msg):
        ts   = datetime.now().strftime('%H:%M:%S')
        line = f'[{ts}] {msg}\n'
        self.root.after(0, self._write_log, line)

    def _write_log(self, line):
        self.log_box.configure(state='normal')
        self.log_box.insert('end', line)
        self.log_box.see('end')
        self.log_box.configure(state='disabled')

    def get_url(self):
        ch  = self.channel_var.get().strip()
        dur = self.duration_var.get().strip()
        return f'http://localhost:{PORT}/video-share-alert-v2.html?channel={ch}&duration={dur}'

    def copy_url(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.get_url())
        self.log('URL copiada al portapapeles')

    def save_config(self):
        cfg = {'channel': self.channel_var.get().strip(),
               'duration': self.duration_var.get().strip()}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f)
        self.url_lbl.config(text=self.get_url())
        self.log('Configuracion guardada')

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    cfg = json.load(f)
                self.channel_var.set(cfg.get('channel', 'tu_canal'))
                self.duration_var.set(cfg.get('duration', '10'))
            except Exception:
                pass

    def start_server(self):
        self.log('Verificando yt-dlp...')

        def run():
            try:
                import yt_dlp  # noqa
                self.log('yt-dlp OK')
            except ImportError:
                self.log('Instalando yt-dlp (primera vez, espera un momento)...')
                import subprocess
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'yt-dlp', '-q'])
                self.log('yt-dlp instalado')

            cleanup_temp()

            try:
                server = ThreadedServer(('', PORT), Handler)
                self.root.after(0, self._on_server_up)
                server.serve_forever()
            except OSError as e:
                self.root.after(0, self._on_server_err, str(e))

        threading.Thread(target=run, daemon=True).start()

    def _on_server_up(self):
        self.dot.config(fg='#a6e3a1')
        self.status_lbl.config(text=f'Corriendo en puerto {PORT}')
        self.url_lbl.config(text=self.get_url())
        self.log(f'Servidor iniciado en puerto {PORT}')

    def _on_server_err(self, err):
        self.dot.config(fg='#f38ba8')
        self.status_lbl.config(text=f'Error: {err}')
        self.log(f'Error al iniciar servidor: {err}')

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    App().run()
