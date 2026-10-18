"""Business logic: validate -> assess -> explain -> explore -> correct (pending) -> verify -> audit.
Every function takes/returns plain dicts so it can be used in-process (Streamlit/CLI) or over HTTP."""
import json, os, platform, time, uuid
import joblib
import numpy as np
import pandas as pd

from . import audit as A
from .affordability import affordability, tenure_sweep
from .config import (ALL_FIELDS, AUDIT_ONLY, CATEGORICAL, DISCLAIMER, ENGINE_B, MODEL_INPUTS, NUMERIC,
                     artifact_dir)
from .counterfactual import band, find_scenarios
from .explain import explain, to_frame
from .validation import validate_application

_BUNDLE = None
BAND_LABEL = {"lower": "Lower estimated risk", "moderate": "Moderate estimated risk", "higher": "Higher estimated risk"}


def reset_cache():
    global _BUNDLE
    _BUNDLE = None


def get_bundle():
    global _BUNDLE
    if _BUNDLE is None:
        p = artifact_dir() / "model.joblib"
        if not p.exists():
            from .train import train
            train(os.getenv("LOANLENS_DATASET", "auto"))
        _BUNDLE = joblib.load(p)
    return _BUNDLE


def _score_many(apps):
    b = get_bundle()
    pipe = b["pipeline"]
    X = pd.concat([to_frame(a) for a in apps], ignore_index=True)
    return pipe.predict_proba(X)[:, list(pipe.classes_).index(1)]


def _evaluate(app, scenarios=False):
    v = validate_application(app)
    out = {"validation": v}
    if v["errors"]:
        out["status"] = "invalid_input"
        return out
    out["affordability"] = affordability(app)
    if v["review"]:
        out["status"] = "flagged_for_review"
        return out
    b = get_bundle()
    t0 = time.perf_counter()
    p = float(_score_many([app])[0])
    ex = explain(b, app)
    out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    bd = band(p, b["threshold"])
    out.update({"status": "assessed", "risk": {"probability": p, "band": bd, "band_label": BAND_LABEL[bd],
                                              "threshold": b["threshold"]}, "explanation": ex})
    if scenarios:
        out["scenarios"] = find_scenarios(app, _score_many, b["threshold"], p)
    return out


def _meta():
    b = get_bundle()
    return {"model_version": b["model_version"], "dataset_source": b["dataset_source"], "disclaimer": DISCLAIMER}


def _snapshot(con, app_id, version, kind, app, ev):
    cur = con.execute(
        "INSERT INTO snapshots(app_id,app_version,kind,input_json,input_hash,model_version,ts,probability,band,"
        "explanation_json,latency_ms) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (app_id, version, kind, A.canon(app), A.input_hash(app), get_bundle()["model_version"], A.now(),
         ev["risk"]["probability"], ev["risk"]["band"], A.canon(ev["explanation"]), ev["latency_ms"]))
    return cur.lastrowid


def assess_application(application: dict, actor="applicant") -> dict:
    app = {k: application.get(k) for k in ALL_FIELDS}
    ev = _evaluate(app, scenarios=True)
    res = dict(ev, **_meta())
    if ev["status"] == "invalid_input":  # data minimisation: log field names + codes, not values
        A.audit_event("VALIDATION_FAILED", {"errors": [{"field": e["field"], "code": e["code"]} for e in ev["validation"]["errors"]]}, actor)
        return res
    if ev["status"] == "flagged_for_review":
        A.audit_event("REVIEW_FLAGGED", {"codes": [e["code"] for e in ev["validation"]["review"]],
                                         "input_hash": A.input_hash(app)}, actor)
        return res
    app_id = uuid.uuid4().hex[:12]
    with A.db() as c:
        c.execute("INSERT INTO applications VALUES(?,?,?,?,?)", (app_id, 1, A.canon(app), A.now(), A.now()))
        sid = _snapshot(c, app_id, 1, "OFFICIAL", app, ev)
    A.audit_event("ASSESSED", {"snapshot_id": sid, "app_version": 1, "model_version": res["model_version"],
                               "input_hash": A.input_hash(app), "probability": round(ev["risk"]["probability"], 4),
                               "band": ev["risk"]["band"], "latency_ms": ev["latency_ms"]}, actor, app_id)
    res.update({"app_id": app_id, "app_version": 1, "snapshot_id": sid, "application": app})
    return res


def what_if(application: dict, overrides: dict, actor="applicant") -> dict:
    base = {k: application.get(k) for k in ALL_FIELDS}
    mod = dict(base, **{k: v for k, v in overrides.items() if k in ALL_FIELDS})
    o, m = _evaluate(base), _evaluate(mod)
    A.audit_event("WHATIF_RUN", {"changed": sorted(k for k in overrides if base.get(k) != mod.get(k)),
                                 "original_hash": A.input_hash(base), "modified_hash": A.input_hash(mod),
                                 "hypothetical": True}, actor)
    out = {"label": "HYPOTHETICAL - official record unchanged", "original": o, "modified": m, **_meta()}
    if "risk" in o and "risk" in m:
        out["delta_probability"] = m["risk"]["probability"] - o["risk"]["probability"]
    if "affordability" in m:
        out["tenure_sweep"] = tenure_sweep(mod) if not m["validation"]["errors"] else None
    return out


def _coerce(field, value):
    if field in CATEGORICAL:
        return value
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return value
    if isinstance(value, float) and value.is_integer() and field in NUMERIC + ["age", "tenure_months"]:
        return int(value)
    return value


def _load_app(c, app_id):
    r = c.execute("SELECT * FROM applications WHERE app_id=?", (app_id,)).fetchone()
    return (r["version"], json.loads(r["data"])) if r else (None, None)


def submit_correction(app_id: str, field: str, claimed_value, reason: str, actor="applicant") -> dict:
    if field not in ALL_FIELDS:
        return {"status": "rejected", "reason": f"unknown field {field}"}
    with A.db() as c:
        ver, app = _load_app(c, app_id)
    if app is None:
        return {"status": "rejected", "reason": "unknown application"}
    val = _coerce(field, claimed_value)
    if val == app[field]:
        return {"status": "rejected", "reason": "claimed value equals recorded value"}
    mod = dict(app, **{field: val})
    v = validate_application(mod)
    if v["errors"]:
        A.audit_event("CORRECTION_REJECTED_INVALID", {"field": field, "codes": [e["code"] for e in v["errors"]]}, actor, app_id)
        return {"status": "invalid_input", "validation": v}
    before, after = _evaluate(app), _evaluate(mod)
    hyp_id = None
    with A.db() as c:
        if after["status"] == "assessed":
            hyp_id = _snapshot(c, app_id, ver, "HYPOTHETICAL", mod, after)
        cur = c.execute("INSERT INTO corrections(app_id,base_version,field,old_value,claimed_value,reason,status,"
                        "submitted_ts,hypothetical_snapshot_id) VALUES(?,?,?,?,?,?,?,?,?)",
                        (app_id, ver, field, A.canon(app[field]), A.canon(val), reason[:500], "PENDING_VERIFICATION", A.now(), hyp_id))
        cid = cur.lastrowid
    A.audit_event("CORRECTION_SUBMITTED", {"correction_id": cid, "field": field, "base_version": ver,
                                           "hypothetical_snapshot_id": hyp_id}, actor, app_id)
    out = {"status": "pending_verification", "correction_id": cid, "field": field, "claimed_value": val,
           "label": "HYPOTHETICAL (unverified claim) - official record is unchanged until a reviewer verifies it",
           "before": before, "hypothetical_after": after, **_meta()}
    if "risk" in before and "risk" in after:
        out["delta_probability"] = after["risk"]["probability"] - before["risk"]["probability"]
    return out


def review_correction(correction_id: int, decision: str, reviewer: str, note: str = "") -> dict:
    decision = decision.upper()
    if decision not in ("VERIFIED", "REJECTED"):
        return {"status": "error", "reason": "decision must be VERIFIED or REJECTED"}
    with A.db() as c:
        r = c.execute("SELECT * FROM corrections WHERE correction_id=?", (correction_id,)).fetchone()
        if not r:
            return {"status": "error", "reason": "unknown correction"}
        if r["status"] != "PENDING_VERIFICATION":
            return {"status": "error", "reason": f"already {r['status']}"}
        ver, app = _load_app(c, r["app_id"])
        if decision == "VERIFIED" and ver != r["base_version"]:
            return {"status": "error", "reason": "stale: record changed since correction was submitted"}
        c.execute("UPDATE corrections SET status=?,reviewed_ts=?,reviewer=?,review_note=? WHERE correction_id=?",
                  (decision, A.now(), reviewer, note[:500], correction_id))
    if decision == "REJECTED":
        A.audit_event("CORRECTION_REJECTED", {"correction_id": correction_id, "note": note[:200]}, reviewer, r["app_id"])
        return {"status": "rejected", "correction_id": correction_id}
    new = dict(app, **{r["field"]: json.loads(r["claimed_value"])})
    ev = _evaluate(new)
    with A.db() as c:
        c.execute("UPDATE applications SET version=?,data=?,updated_ts=? WHERE app_id=?",
                  (ver + 1, A.canon(new), A.now(), r["app_id"]))
        sid = _snapshot(c, r["app_id"], ver + 1, "OFFICIAL", new, ev) if ev["status"] == "assessed" else None
    A.audit_event("CORRECTION_VERIFIED", {"correction_id": correction_id, "new_version": ver + 1, "snapshot_id": sid,
                                          "new_input_hash": A.input_hash(new)}, reviewer, r["app_id"])
    return dict(ev, **_meta(), correction_id=correction_id, app_id=r["app_id"], app_version=ver + 1,
                snapshot_id=sid, outcome="verified")


def pending_corrections():
    with A.db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM corrections WHERE status='PENDING_VERIFICATION' ORDER BY correction_id")]


def history(app_id: str) -> dict:
    with A.db() as c:
        ver, app = _load_app(c, app_id)
        snaps = [dict(r) for r in c.execute("SELECT snapshot_id,app_version,kind,input_hash,model_version,ts,probability,band,latency_ms "
                                            "FROM snapshots WHERE app_id=? ORDER BY snapshot_id", (app_id,))]
        cors = [dict(r) for r in c.execute("SELECT * FROM corrections WHERE app_id=? ORDER BY correction_id", (app_id,))]
    return {"app_id": app_id, "version": ver, "official_record": app, "snapshots": snaps, "corrections": cors}


def stats():
    with A.db() as c:
        lat = [r[0] for r in c.execute("SELECT latency_ms FROM snapshots WHERE latency_ms IS NOT NULL")]
        ev = {r[0]: r[1] for r in c.execute("SELECT event_type,COUNT(*) FROM audit_log GROUP BY event_type")}
    q = (lambda p: round(float(np.percentile(lat, p)), 2)) if lat else (lambda p: None)
    return {"inference_count": len(lat), "latency_ms_p50": q(50), "latency_ms_p95": q(95), "events": ev}


def model_info():
    b = get_bundle()
    mp = artifact_dir() / "metrics.json"
    return {"model_version": b["model_version"], "dataset_source": b["dataset_source"], "trained_at": b["trained_at"],
            "threshold": b["threshold"], "trained_on": b["trained_on"],
            "runtime": {"machine": platform.machine(), "system": platform.system(), "python": platform.python_version(),
                        "platform": platform.platform()},
            "metrics": json.loads(mp.read_text()) if mp.exists() else None}
