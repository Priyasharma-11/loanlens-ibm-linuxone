"""Backend facade: in-process (default) or remote API via LOANLENS_API_URL (stdlib urllib only).
Lets the Streamlit UI run on a laptop while inference runs on LinuxONE."""
import json, os, urllib.request, urllib.error
from . import audit as A, service as S


class Local:
    mode = "in-process"
    def assess(self, app): return S.assess_application(app)
    def what_if(self, app, ov): return S.what_if(app, ov)
    def correct(self, app_id, field, val, reason): return S.submit_correction(app_id, field, val, reason)
    def review(self, cid, decision, reviewer, note, token=""): return S.review_correction(cid, decision, reviewer, note)
    def pending(self, token=""): return S.pending_corrections()
    def history(self, app_id): return S.history(app_id)
    def audit(self, token="", limit=100): return A.audit_tail(limit)
    def verify(self, token=""): return A.verify_chain()
    def model(self): return S.model_info()
    def stats(self): return S.stats()


class Remote:
    def __init__(self, url):
        self.url, self.mode = url.rstrip("/"), f"remote API {url}"

    def _call(self, method, path, body=None, token=""):
        req = urllib.request.Request(self.url + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", "X-Reviewer-Token": token})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return {"status": "error", "http": e.code, "error": json.loads(e.read() or b"{}").get("error", "")}

    def assess(self, app): return self._call("POST", "/assess", {"application": app})
    def what_if(self, app, ov): return self._call("POST", "/whatif", {"application": app, "overrides": ov})
    def correct(self, app_id, field, val, reason): return self._call("POST", "/corrections", {"app_id": app_id, "field": field, "claimed_value": val, "reason": reason})
    def review(self, cid, decision, reviewer, note, token=""): return self._call("POST", f"/corrections/{cid}/review", {"decision": decision, "reviewer": reviewer, "note": note}, token)
    def pending(self, token=""): return self._call("GET", "/pending", token=token)
    def history(self, app_id): return self._call("GET", f"/history/{app_id}")
    def audit(self, token="", limit=100): return self._call("GET", f"/audit?limit={limit}", token=token)
    def verify(self, token=""): return self._call("GET", "/audit/verify", token=token)
    def model(self): return self._call("GET", "/model")
    def stats(self): return self._call("GET", "/stats")


def get_backend():
    url = os.getenv("LOANLENS_API_URL")
    return Remote(url) if url else Local()
