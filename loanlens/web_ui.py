
#!/usr/bin/env python3
"""Serve the LoanLens web UI and proxy API requests locally."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HOST = "127.0.0.1"
PORT = 8080
API = "http://127.0.0.1:8000"
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[LoanLens UI] {self.address_string()} - {fmt % args}")

    def send_bytes(self, status, content, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.proxy("GET")
            return

        if self.path in ("/", "/index.html"):
            path = WEB_DIR / "index.html"
        else:
            self.send_bytes(404, b"Not found", "text/plain; charset=utf-8")
            return

        try:
            content = path.read_bytes()
            self.send_bytes(200, content, "text/html; charset=utf-8")
        except OSError:
            self.send_bytes(500, b"Dashboard file not found",
                            "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path.startswith("/api/"):
            self.proxy("POST")
        else:
            self.send_bytes(404, b"Not found", "text/plain; charset=utf-8")

    def proxy(self, method):
        allowed = {
            "/api/health": "/health",
            "/api/model": "/model",
            "/api/stats": "/stats",
            "/api/assess": "/assess",
            "/api/whatif": "/whatif",
            "/api/history": "/history",
            "/api/corrections": "/corrections",
            "/api/pending": "/pending",
            "/api/audit": "/audit",
            "/api/audit/verify": "/audit/verify",
        }

        route = self.path.split("?", 1)[0]
        if route.startswith("/api/history/"):
            target = "/history/" + route[len("/api/history/"):]
        elif route in allowed:
            target = allowed[route] + (
                "?" + self.path.split("?", 1)[1] if "?" in self.path else ""
            )
        elif route.startswith("/api/corrections/") and route.endswith("/review"):
            target = route[len("/api"):]
        else:
            self.send_bytes(404, b'{"error":"route not allowed"}',
                            "application/json")
            return

        body = None
        headers = {"Accept": "application/json"}
        if method == "POST":
            length = int(self.headers.get("Content-Length", "0"))
            if length > 100_000:
                self.send_bytes(413, b'{"error":"payload too large"}',
                                "application/json")
                return
            body = self.rfile.read(length)
            headers["Content-Type"] = "application/json"

        token = self.headers.get("X-Reviewer-Token")
        if token:
            headers["X-Reviewer-Token"] = token

        req = Request(API + target, data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=30) as response:
                data = response.read()
                self.send_bytes(response.status, data,
                                response.headers.get("Content-Type",
                                                     "application/json"))
        except HTTPError as exc:
            data = exc.read()
            self.send_bytes(exc.code, data, "application/json")
        except (URLError, TimeoutError, OSError):
            self.send_bytes(502, b'{"error":"LoanLens API is unavailable"}',
                            "application/json")


if __name__ == "__main__":
    if not (WEB_DIR / "index.html").is_file():
        raise SystemExit("Missing web/index.html")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"LoanLens UI server: http://{HOST}:{PORT}")
    print(f"Dashboard directory: {WEB_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping LoanLens UI.")
    finally:
        server.server_close()
