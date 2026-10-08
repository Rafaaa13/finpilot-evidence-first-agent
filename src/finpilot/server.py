from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .advisor import enhance, test_connection
from .integrations import LlmClient
from .pipeline import run_fixture
from .investment import analyze_investment, demo_inputs
from .serialization import json_safe
from .ui import build_workbench


def serve(host="127.0.0.1", port=8765):
    if host != "127.0.0.1":
        raise ValueError("Prototype binds only to 127.0.0.1; no public deployment")
    page = build_workbench(server=True)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body, content_type):
            raw = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(status); self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html", "/workbench.html"):
                self._send(200, page, "text/html"); return
            if path == "/health":
                self._send(200, '{"status":"ok","mode":"local_fixture"}', "application/json"); return
            self._send(404, "not found", "text/plain")

        def do_POST(self):
            expected = f"127.0.0.1:{port}"
            origin = self.headers.get("Origin")
            if self.headers.get("Host") != expected or self.headers.get("X-FinPilot") != "local" or (origin and origin != "http://" + expected) or self.headers.get("Content-Type") != "application/json":
                self._send(403, "local JSON requests only", "text/plain"); return
            path = urlparse(self.path).path
            if path not in {"/api/run", "/api/investment", "/api/construct", "/api/doctor", "/api/advisor/preview", "/api/advisor/test", "/api/advisor/enhance"}:
                self._send(404, "not found", "text/plain"); return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 2_100_000: raise ValueError("request exceeds 2MB limit")
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict): raise ValueError("request must be object")
                if path == "/api/advisor/preview":
                    from .advisor import enhancement_preview
                    research_result = body.get("research_result") or analyze_investment(**demo_inputs())
                    result = enhancement_preview(research_result, str(body.get("question", "")))
                elif path == "/api/advisor/test":
                    client = LlmClient.from_env()
                    if client is None: raise ValueError("未配置 FINPILOT_LLM_ENDPOINT")
                    result = test_connection(client)
                elif path == "/api/advisor/enhance":
                    client = LlmClient.from_env() if body.get("live_model") else None
                    research_result = body.get("research_result") or analyze_investment(**demo_inputs())
                    result = enhance(research_result, str(body.get("question", "")), client)
                elif path == "/api/doctor":
                    from .data_sources import data_doctor
                    result = data_doctor(provider=body.get("provider"))
                elif path == "/api/construct":
                    from .construction import construct
                    research_result = body.get("research_result") or analyze_investment(**demo_inputs())
                    result = construct(research_result, body.get("prices_csv", ""), selected=body.get("selected"), method=body.get("method", "equal"), cash_floor=float(body.get("cash_floor", .10)), asset_cap=float(body.get("asset_cap", .30)), sector_cap=float(body.get("sector_cap", .50)), capital=float(body.get("capital", 100000)), current=body.get("current"), fee_bps=float(body.get("fee_bps", 10)))
                elif path == "/api/investment":
                    if body.get("stocks_csv"):
                        result = analyze_investment(
                            body["stocks_csv"], body.get("prices_csv", ""), body.get("as_of", "2025-12-31"),
                            profile=body.get("profile", "balanced"), weight_cap=float(body.get("weight_cap", .30)),
                            max_names=int(body.get("max_names", 5)), method=body.get("method", "equal"), data_kind="user_import",
                        )
                    else:
                        result = analyze_investment(**demo_inputs(body.get("as_of", "2025-12-31")), profile=body.get("profile", "balanced"), method=body.get("method", "equal"), weight_cap=float(body.get("weight_cap", .30)), max_names=int(body.get("max_names", 5)))
                else:
                    result = run_fixture(str(body.get("ticker", "DEMO")), str(body.get("as_of", "2025-12-31")), output_dir=None, transaction_cost=float(body.get("transaction_cost", .001)), pd_multiplier=float(body.get("pd_multiplier", 1.5)), lgd_shift=float(body.get("lgd_shift", .1)))
                self._send(200, json.dumps(json_safe(result), ensure_ascii=False, allow_nan=False), "application/json")
            except Exception as exc:
                self._send(400, json.dumps({"status": "review", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), "application/json")

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"FinPilot workbench: http://{host}:{port}/")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
