"""Application web locale (la version hébergée est statique via GitHub Pages)."""
from __future__ import annotations
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
import json
import os
import re
import threading
import time
import webbrowser
from monitor import check_all, load_json, save_json, DATA, CONFIG, SHOPS, RUN_LOCK
from notifications import configured_channels, notify

ROOT = Path(__file__).resolve().parent
INTERVAL_MINUTES = max(15, int(os.environ.get('CHECK_INTERVAL_MINUTES', '30')))
CHECK_THREAD = None


def start_scan():
    global CHECK_THREAD
    if RUN_LOCK.locked() or (CHECK_THREAD and CHECK_THREAD.is_alive()):
        return False
    CHECK_THREAD = threading.Thread(target=check_all, daemon=True)
    CHECK_THREAD.start()
    return True


def monitor_loop():
    start_scan()
    while True:
        time.sleep(INTERVAL_MINUTES * 60)
        start_scan()


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, contents, content_type='application/json; charset=utf-8'):
        data = contents if isinstance(contents, bytes) else contents.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def json(self, status, value):
        self._send(status, json.dumps(value, ensure_ascii=False))

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/index.html'):
            self._send(200, (ROOT / 'static/index.html').read_bytes(), 'text/html; charset=utf-8')
        elif path == '/api/status':
            data = load_json(DATA, {'product': 'Physiolac Bio 1er âge 800 g', 'ean': '3518646124167', 'shops': load_json(SHOPS, []), 'history': [], 'last_check': None})
            data['scanning'] = RUN_LOCK.locked()
            data['interval_minutes'] = INTERVAL_MINUTES
            data['notification_channels'] = configured_channels(load_json(CONFIG, {}))
            self.json(200, data)
        elif path == '/api/settings':
            cfg = load_json(CONFIG, {})
            self.json(200, {'ntfy_topic': cfg.get('ntfy_topic', ''), 'notification_channels': configured_channels(cfg)})
        elif path == '/health':
            self.json(200, {'ok': True})
        else:
            self.json(404, {'error': 'Introuvable'})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            size = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return self.json(400, {'error': 'Taille de requête invalide'})
        if size > 2048:
            return self.json(413, {'error': 'Données trop volumineuses'})
        if path == '/api/check':
            started = start_scan()
            return self.json(200, {'started': started, 'message': 'Vérification lancée' if started else 'Une vérification est déjà en cours'})
        if path == '/api/settings':
            try:
                payload = json.loads(self.rfile.read(size) or b'{}')
            except ValueError:
                return self.json(400, {'error': 'JSON invalide'})
            topic = payload.get('ntfy_topic', '')
            if not isinstance(topic, str) or (topic and not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', topic)):
                return self.json(400, {'error': 'Canal invalide : 8 à 64 lettres, chiffres, _ ou -'})
            cfg = load_json(CONFIG, {})
            cfg['ntfy_topic'] = topic.strip()
            save_json(CONFIG, cfg)
            return self.json(200, {'ok': True})
        if path == '/api/test-notifications':
            report = notify(test=True, settings=load_json(CONFIG, {}))
            return self.json(200 if report['sent'] else 400, report)
        self.json(404, {'error': 'Introuvable'})

    def log_message(self, fmt, *args):
        if not self.path.startswith('/api/status'):
            print('[HTTP]', fmt % args)


def main():
    host, port = '127.0.0.1', int(os.environ.get('PORT', '8765'))
    threading.Thread(target=monitor_loop, daemon=True).start()
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f'http://{host}:{port}'
    print('\n🍼 Physiolac Stock Alert démarré : ' + url)
    print(f'Vérification programmée toutes les {INTERVAL_MINUTES} minutes (tant que ce programme reste ouvert).')
    threading.Timer(1.3, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('Arrêt du programme.')
    finally:
        httpd.server_close()


if __name__ == '__main__':
    main()
