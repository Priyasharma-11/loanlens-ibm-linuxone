"""Terminal walkthrough of the full flow - good for LinuxONE screen recordings (no UI deps needed).
    python scripts/demo_cli.py"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from loanlens import audit as A, service as S

APP = dict(monthly_income=25000, existing_emi=12000, loan_inr=200000, rate_pct=12, tenure_months=36, duration_months=36,
           credit_amount=6500, installment_rate=4, existing_credits=2, checking_status="lt_0", credit_history="past_delays",
           savings_status="lt_100", employment_since="lt_1y", housing="rent", property="none", age=29)


import pathlib
from loanlens.config import artifact_dir
_dp = pathlib.Path(artifact_dir()) / "demo_profile.json"
CORR = ("savings_status", "ge_1000")
if _dp.exists():
    _d = json.loads(_dp.read_text()); APP = _d["application"]; CORR = (_d["suggested_correction"]["field"], _d["suggested_correction"]["claimed_value"])


def hdr(t): print("\n" + "=" * 8, t, "=" * 8)


hdr("1. Invalid input (negative income) -> no assessment + audit entry")
r = S.assess_application(dict(APP, monthly_income=-25000)); print(r["status"], [e["code"] for e in r["validation"]["errors"]])
hdr("2. EMI above income -> flagged for review, score withheld")
r = S.assess_application(dict(APP, existing_emi=30000)); print(r["status"], [e["code"] for e in r["validation"]["review"]])
hdr("3. Valid assessment")
r = S.assess_application(APP); aid = r["app_id"]
print(f"app={aid} model={r['model_version']} data={r['dataset_source']} risk={r['risk']['probability']:.1%} ({r['risk']['band_label']}) latency={r['latency_ms']}ms")
for line in r["explanation"]["plain_language"]: print(" -", line)
hdr("4. Constrained what-if (HYPOTHETICAL)")
for s in r["scenarios"]: print(f" [{'moves band' if s['moves_band'] else 'same band'}] amount x{s['amount_multiplier']} duration {s['duration_months']}mo -> {s['probability']:.1%} ({s['band']}) [{s['delta_probability']:+.1%}]")
hdr("5. Correction claim (pending) -> hypothetical result, official record unchanged")
c = S.submit_correction(aid, CORR[0], CORR[1], "supporting document provided")
print(c["status"], f"official {c['before']['risk']['probability']:.1%} -> hypothetical {c['hypothetical_after']['risk']['probability']:.1%}")
print(f"official {CORR[0]} still:", S.history(aid)["official_record"][CORR[0]])
hdr("6. Reviewer verifies -> official record v2 + new snapshot")
v = S.review_correction(c["correction_id"], "VERIFIED", "reviewer1", "statement checked")
print("version", v["app_version"], f"risk now {v['risk']['probability']:.1%}")
hdr("7. Audit chain")
print(A.verify_chain())
for e in reversed(A.audit_tail(6)): print(f" #{e['id']} {e['event_type']:24s} {e['subject'] or '-':14s} {e['hash'][:10]}")
