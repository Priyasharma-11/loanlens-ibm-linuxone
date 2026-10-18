"""SQLite storage: applications, snapshots, corrections and a hash-chained, append-only audit log."""
import hashlib, json, sqlite3, time
from contextlib import contextmanager
from .config import db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, event_type TEXT, actor TEXT,
  subject TEXT, details TEXT, prev_hash TEXT, hash TEXT);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log
  BEGIN SELECT RAISE(ABORT,'audit_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log
  BEGIN SELECT RAISE(ABORT,'audit_log is append-only'); END;
CREATE TABLE IF NOT EXISTS applications(app_id TEXT PRIMARY KEY, version INTEGER, data TEXT, created_ts TEXT, updated_ts TEXT);
CREATE TABLE IF NOT EXISTS snapshots(snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT, app_id TEXT, app_version INTEGER,
  kind TEXT, input_json TEXT, input_hash TEXT, model_version TEXT, ts TEXT, probability REAL, band TEXT,
  explanation_json TEXT, latency_ms REAL);
CREATE TABLE IF NOT EXISTS corrections(correction_id INTEGER PRIMARY KEY AUTOINCREMENT, app_id TEXT, base_version INTEGER,
  field TEXT, old_value TEXT, claimed_value TEXT, reason TEXT, status TEXT, submitted_ts TEXT, reviewed_ts TEXT,
  reviewer TEXT, review_note TEXT, hypothetical_snapshot_id INTEGER);
"""


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def input_hash(obj):
    return hashlib.sha256(canon(obj).encode()).hexdigest()


@contextmanager
def db():
    con = sqlite3.connect(str(db_path()), timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _hash(prev, ts, et, actor, subject, details):
    return hashlib.sha256((prev + "|" + ts + "|" + et + "|" + actor + "|" + (subject or "") + "|" + details).encode()).hexdigest()


def audit_event(event_type, details, actor="system", subject=None):
    con = sqlite3.connect(str(db_path()), timeout=30, isolation_level=None)
    try:
        con.executescript(SCHEMA)
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        prev, ts, d = (row[0] if row else "GENESIS"), now(), canon(details)
        h = _hash(prev, ts, event_type, actor, subject, d)
        con.execute("INSERT INTO audit_log(ts,event_type,actor,subject,details,prev_hash,hash) VALUES(?,?,?,?,?,?,?)",
                    (ts, event_type, actor, subject, d, prev, h))
        con.execute("COMMIT")
        return h
    finally:
        con.close()


def audit_tail(limit=100):
    with db() as c:
        rows = c.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r, details=json.loads(r["details"])) for r in rows]


def verify_chain():
    with db() as c:
        rows = c.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    prev = "GENESIS"
    for r in rows:
        if r["prev_hash"] != prev or _hash(prev, r["ts"], r["event_type"], r["actor"], r["subject"], r["details"]) != r["hash"]:
            return {"valid": False, "entries": len(rows), "first_bad_id": r["id"]}
        prev = r["hash"]
    return {"valid": True, "entries": len(rows), "first_bad_id": None}
