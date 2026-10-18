"""Dependency-free HTTP API (stdlib only) - chosen so it runs on LinuxONE/s390x without compiled web deps.
    python -m loanlens.server --host 127.0.0.1 --port 8000
Reviewer endpoints need header X-Reviewer-Token == $LOANLENS_REVIEWER_TOKEN (if unset: loopback clients only)."""
import argparse, json, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from . import audit as A, service as S
from .config import reviewer_token

REVIEWER_ONLY = [("GET", r"^/pending$"), ("GET", r"^/audit$"), ("GET", r"^/audit/verify$"),
                 ("POST", r"^/corrections/\d+/review$")]


class H(BaseHTTPRequestHandler):
    server_version = "LoanLens/1.0"

    def log_message(self, fmt, *a):
        pass

    def _send(self, code, obj):
        b = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _authorised(self, method, path):
        if not any(m == method and re.match(p, path) for m, p in REVIEWER_ONLY):
            return True
        tok = reviewer_token()
        if tok:
            return self.headers.get("X-Reviewer-Token") == tok
        return self.client_address[0] in ("127.0.0.1", "::1")

    def _route(self, method):
        u = urlparse(self.path)
        path, q = u.path.rstrip("/") or "/", parse_qs(u.query)
        if not self._authorised(method, path):
            return self._send(401, {"error": "reviewer token required"})
        body = {}
        if method == "POST":
            n = int(self.headers.get("Content-Length") or 0)
            if n > 100_000:
                return self._send(413, {"error": "payload too large"})
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._send(400, {"error": "invalid JSON"})
        try:
            if method == "GET":
                if path == "/health":
                    return self._send(200, {"ok": True, **{k: v for k, v in S.model_info().items() if k in ("model_version", "runtime", "dataset_source")}})
                if path == "/model": return self._send(200, S.model_info())
                if path == "/stats": return self._send(200, S.stats())
                if path == "/pending": return self._send(200, S.pending_corrections())
                if path == "/audit": return self._send(200, A.audit_tail(int(q.get("limit", ["100"])[0])))
                if path == "/audit/verify": return self._send(200, A.verify_chain())
                m = re.match(r"^/history/(\w+)$", path)
                if m: return self._send(200, S.history(m.group(1)))
                if path == "/": return self._send(200, {"service": "LoanLens", "endpoints": [
                    "GET /health /model /stats /history/<id>", "POST /assess /whatif /corrections",
                    "reviewer: GET /pending /audit /audit/verify, POST /corrections/<id>/review"]})
            else:
                if path == "/assess": return self._send(200, S.assess_application(body.get("application", body), body.get("actor", "applicant")))
                if path == "/whatif": return self._send(200, S.what_if(body["application"], body.get("overrides", {})))
                if path == "/corrections":
                    return self._send(200, S.submit_correction(body["app_id"], body["field"], body["claimed_value"], body.get("reason", "")))
                m = re.match(r"^/corrections/(\d+)/review$", path)
                if m:
                    return self._send(200, S.review_correction(int(m.group(1)), body.get("decision", ""), body.get("reviewer", "reviewer"), body.get("note", "")))
            self._send(404, {"error": "not found"})
        except KeyError as e:
            self._send(400, {"error": f"missing field {e}"})
        except Exception as e:  # never leak stack traces
            self._send(500, {"error": type(e).__name__})

    def do_GET(self): self._route("GET")
    def do_POST(self): self._route("POST")


def make_server(host="127.0.0.1", port=8000):
    S.get_bundle()
    return ThreadingHTTPServer((host, port), H)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    print(f"LoanLens API on http://{a.host}:{a.port}  (reviewer token {'set' if reviewer_token() else 'NOT set: loopback only'})")
    make_server(a.host, a.port).serve_forever()
