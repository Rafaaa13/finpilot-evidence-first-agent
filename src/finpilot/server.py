from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from .pipeline import run_fixture
from .serialization import json_safe
from .ui import build_workbench


def serve(host='127.0.0.1', port=8765):
    if host != '127.0.0.1':
        raise ValueError('Prototype binds only to 127.0.0.1; no public deployment')
    page = build_workbench(server=True)
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body, content_type):
            raw=body if isinstance(body,bytes) else body.encode('utf-8')
            self.send_response(status); self.send_header('Content-Type',content_type+'; charset=utf-8')
            self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            path=urlparse(self.path).path
            if path in ('/','/index.html','/workbench.html'):
                self._send(200, page, 'text/html'); return
            if path=='/health': self._send(200, '{"status":"ok","mode":"fixture"}', 'application/json'); return
            self._send(404,'not found','text/plain')
        def do_POST(self):
            expected = f'127.0.0.1:{port}'
            origin = self.headers.get('Origin')
            if self.headers.get('Host') != expected or self.headers.get('X-FinPilot') != 'local' or (origin and origin != 'http://' + expected) or self.headers.get('Content-Type') != 'application/json':
                self._send(403, 'local JSON requests only', 'text/plain'); return
            if urlparse(self.path).path!='/api/run': self._send(404,'not found','text/plain'); return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 10000: raise ValueError('invalid request length')
                body=json.loads(self.rfile.read(length) or b'{}')
                if not isinstance(body,dict): raise ValueError('request must be object')
                result=run_fixture(str(body.get('ticker','DEMO')),str(body.get('as_of','2025-12-31')),output_dir=None,
                                   transaction_cost=float(body.get('transaction_cost',.001)),
                                   pd_multiplier=float(body.get('pd_multiplier',1.5)),lgd_shift=float(body.get('lgd_shift',.1)))
                self._send(200,json.dumps(json_safe(result),ensure_ascii=False,allow_nan=False),'application/json')
            except Exception as exc:
                self._send(400,json.dumps({'status':'review','error':type(exc).__name__+': request rejected'},ensure_ascii=False),'application/json')
        def log_message(self, fmt, *args): return
    server=ThreadingHTTPServer((host,port),Handler)
    print(f'FinPilot workbench: http://{host}:{port}/')
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
