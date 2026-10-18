import json, os, threading, unittest, urllib.request
from tests._base import Base, SAMPLE


class TestAPI(Base):
    def setUp(self):
        from loanlens.server import make_server
        self.srv = make_server("127.0.0.1", 0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def tearDown(self):
        self.srv.shutdown(); os.environ.pop("LOANLENS_REVIEWER_TOKEN", None)

    def call(self, method, path, body=None, headers=None):
        req = urllib.request.Request(self.url + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers=headers or {})
        try:
            with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e: return e.code, json.loads(e.read())

    def test_flow(self):
        self.assertEqual(self.call("GET", "/health")[0], 200)
        st, r = self.call("POST", "/assess", {"application": SAMPLE}); self.assertEqual(r["status"], "assessed")
        st, r = self.call("POST", "/assess", {"application": dict(SAMPLE, monthly_income=-1)}); self.assertEqual(r["status"], "invalid_input")
        self.assertEqual(self.call("POST", "/assess", None)[0], 200)  # empty body -> invalid_input, not 500
        self.assertEqual(self.call("GET", "/audit/verify")[1]["valid"], True)

    def test_reviewer_token_enforced(self):
        os.environ["LOANLENS_REVIEWER_TOKEN"] = "s3cret"
        self.assertEqual(self.call("GET", "/audit")[0], 401)
        self.assertEqual(self.call("GET", "/audit", headers={"X-Reviewer-Token": "s3cret"})[0], 200)


if __name__ == "__main__":
    unittest.main()
