"""Scan for a fictional applicant for the TRAINED model whose band improves via (a) a constrained what-if AND
(b) a single plausible data correction. Writes artifacts/demo_profile.json (auto-loaded by the UI).
    python scripts/find_demo_profile.py"""
import itertools, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from loanlens import service as S
from loanlens.config import artifact_dir

BASE = dict(monthly_income=25000, existing_emi=12000, loan_inr=200000, rate_pct=12, tenure_months=36, age=29,
            housing="rent", existing_credits=1)
best = None
thr = S.get_bundle()["threshold"]
for chk, hist, sav, emp, prop, dur, amt, ins in itertools.product(
        ["lt_0", "0_to_200"], ["past_delays", "existing_paid_duly", "critical_other_credits"], ["lt_100", "100_to_500"],
        ["lt_1y", "1_to_4y"], ["none", "car_other"], [18, 24, 30, 36], [2500, 3500, 4500, 6500], [3, 4]):
    app = dict(BASE, checking_status=chk, credit_history=hist, savings_status=sav, employment_since=emp, property=prop,
               duration_months=dur, credit_amount=amt, installment_rate=ins)
    r = S._evaluate(app, scenarios=True)
    if r["status"] != "assessed" or r["risk"]["band"] != "higher":
        continue
    flips = [s for s in r["scenarios"] if s["moves_band"]]
    for corr_field, corr_val in [("savings_status", "ge_1000"), ("checking_status", "ge_200"), ("employment_since", "4_to_7y")]:
        if app[corr_field] == corr_val:
            continue
        c = S._evaluate(dict(app, **{corr_field: corr_val}))
        if flips and c["risk"]["band"] != "higher":
            score = abs(r["risk"]["probability"] - 1.25 * thr)  # prefer moderately above threshold
            if best is None or score < best[0]:
                best = (score, app, corr_field, corr_val, r["risk"]["probability"])
if best is None:
    print("No profile found that flips band under both routes; the UI will use built-in samples (still demonstrates the flow).")
else:
    _, app, cf, cv, p = best
    out = {"name": "0. Auto-tuned demo (flips via what-if AND correction)", "application": app,
           "suggested_correction": {"field": cf, "claimed_value": cv}, "estimated_risk": p, "threshold": thr}
    (artifact_dir() / "demo_profile.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
