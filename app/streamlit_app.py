"""LoanLens UI. Works in-process, or against a remote API (inference on LinuxONE) via LOANLENS_API_URL."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import streamlit as st
from loanlens.client import get_backend
from loanlens.config import CATEGORICAL, LABELS, VALUE_LABELS, MODEL_INPUTS, ENGINE_B, DISCLAIMER
from loanlens.config import NUMERIC

st.set_page_config(page_title="LoanLens", page_icon="🔍", layout="wide")


@st.cache_resource
def backend():
    return get_backend()


B = backend()

PROFILES = {
    "1. High EMI burden (unfavourable demo)": dict(monthly_income=25000, existing_emi=12000, loan_inr=200000, rate_pct=12, tenure_months=36,
        duration_months=36, credit_amount=6500, installment_rate=4, existing_credits=2, checking_status="lt_0",
        credit_history="past_delays", savings_status="lt_100", employment_since="lt_1y", housing="rent", property="none", age=29),
    "2. Stable profile": dict(monthly_income=90000, existing_emi=8000, loan_inr=500000, rate_pct=10.5, tenure_months=48,
        duration_months=18, credit_amount=2200, installment_rate=2, existing_credits=1, checking_status="ge_200",
        credit_history="existing_paid_duly", savings_status="ge_1000", employment_since="ge_7y", housing="own", property="real_estate", age=41),
    "3. Invalid: negative loan, EMI > income": dict(monthly_income=25000, existing_emi=30000, loan_inr=-100000, rate_pct=12, tenure_months=36,
        duration_months=24, credit_amount=3000, installment_rate=3, existing_credits=1, checking_status="0_to_200",
        credit_history="existing_paid_duly", savings_status="100_to_500", employment_since="1_to_4y", housing="rent", property="car_other", age=30),
}

import json
from loanlens.config import artifact_dir
_dp = artifact_dir() / "demo_profile.json"
if _dp.exists():  # created by scripts/find_demo_profile.py for the trained model
    _d = json.loads(_dp.read_text())
    PROFILES = {_d["name"]: _d["application"], **PROFILES}

st.title("🔍 LoanLens")
st.caption("Explain the assessment · Verify the data · Explore the alternatives")
info = B.model()
if "model_version" in info:
    src = info["dataset_source"]
    (st.warning if src == "synthetic" else st.info)(
        f"Model `{info['model_version']}` · data: **{src}** · running on **{info['runtime']['machine']}** "
        f"({info['runtime']['system']}, Python {info['runtime']['python']}) · backend: {B.mode}")
st.caption(DISCLAIMER)


def field_input(f, default, key):
    if f in CATEGORICAL:
        opts = CATEGORICAL[f]
        return st.selectbox(LABELS[f], opts, index=opts.index(default), format_func=lambda v: VALUE_LABELS.get(v, v), key=key)
    if isinstance(default, float):
        return st.number_input(LABELS[f], value=float(default), step=0.5, min_value=-1e9, key=key)
    return st.number_input(LABELS[f], value=int(default), step=1, min_value=-10**9, key=key)


def show_result(r):
    st_ = r.get("status")
    for e in r.get("validation", {}).get("errors", []):
        st.error(f"**{e['field']}** — {e['message']}")
    for e in r.get("validation", {}).get("review", []):
        st.warning(f"**Flagged for review** — {e['message']}")
    for e in r.get("validation", {}).get("warnings", []):
        st.info(e["message"])
    if st_ == "invalid_input":
        st.caption("No assessment produced. A validation event was written to the audit log.")
    if "affordability" in r:
        a = r["affordability"]
        c = st.columns(4)
        c[0].metric("New EMI (INR)", f"{a['new_emi']:,.0f}")
        c[1].metric("Combined EMI / income", f"{a['combined_emi_ratio']:.1%}")
        c[2].metric("Income after EMIs", f"{a['income_after_emis']:,.0f}")
        c[3].metric("Total interest", f"{a['total_interest']:,.0f}")
        st.caption("Engine B — " + a["note"])
    if st_ == "assessed":
        rk = r["risk"]
        c = st.columns(3)
        c[0].metric("Estimated repayment risk", f"{rk['probability']:.1%}")
        c[1].metric("Band", rk["band_label"])
        c[2].metric("Inference latency", f"{r['latency_ms']} ms")
        ex = r["explanation"]
        st.subheader("Why? (model-derived contributions)")
        df = pd.DataFrame(ex["contributions"])
        st.bar_chart(df.set_index("label")["contribution_logodds"])
        for line in ex["plain_language"]:
            st.write("• " + line)
        st.caption(ex["caveat"])


tab1, tab2, tab3, tab4, tab5 = st.tabs(["1 · Assess", "2 · What-if", "3 · Correct data", "4 · Reviewer & audit", "5 · Model & evidence"])

with tab1:
    pname = st.selectbox("Sample profile (fictional)", list(PROFILES))
    p = PROFILES[pname]
    with st.form("app_form"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Engine A — risk model inputs** (dataset units, not INR)")
            vals = {f: field_input(f, p[f], f"{pname}-{f}") for f in MODEL_INPUTS}
            vals["age"] = field_input("age", p["age"], f"{pname}-age")
        with c2:
            st.markdown("**Engine B — affordability inputs** (INR)")
            for f in ENGINE_B:
                vals[f] = field_input(f, p[f], f"{pname}-{f}")
        go = st.form_submit_button("Assess", type="primary")
    if go:
        r = B.assess(vals)
        st.session_state["last"] = r
        st.session_state["app"] = vals
    r = st.session_state.get("last")
    if r:
        if r.get("app_id"):
            st.success(f"Application `{r['app_id']}` saved (version {r['app_version']}) · snapshot #{r['snapshot_id']} · model {r['model_version']}")
        show_result(r)
        if r.get("scenarios"):
            st.subheader("Constrained what-if suggestions (HYPOTHETICAL)")
            rows = [{"Change": f"amount ×{s['amount_multiplier']} ({s['credit_amount']:,}), duration {s['duration_months']} mo",
                     "New risk": f"{s['probability']:.1%}", "Band": s["band"], "Δ": f"{s['delta_probability']:+.1%}"} for s in r["scenarios"]]
            st.table(pd.DataFrame(rows))
            st.caption("Bounded search: amount ≥ 50% of request, duration 6–72 months. Not a guarantee; not a lender decision.")

with tab2:
    app = st.session_state.get("app")
    if not app:
        st.info("Run an assessment first.")
    else:
        st.markdown("Change inputs; the **actual model is re-run** and explanations recalculated. Official record is not changed.")
        ov = {}
        c = st.columns(3)
        ov["credit_amount"] = c[0].slider("Loan amount (dataset units)", 250, 18000, min(max(int(app["credit_amount"]), 250), 18000), 250)
        ov["duration_months"] = c[1].slider("Duration (months)", 6, 72, min(max(int(app["duration_months"]), 6), 72))
        ov["loan_inr"] = c[2].slider("Requested loan (INR)", 10000, 5000000, min(max(int(app["loan_inr"]), 10000), 5000000), 10000)
        c = st.columns(2)
        ov["tenure_months"] = c[0].slider("Tenure (months, Engine B)", 6, 240, min(max(int(app["tenure_months"]), 6), 240))
        ov["rate_pct"] = c[1].slider("Interest rate (% p.a.)", 5.0, 30.0, float(min(max(app["rate_pct"], 5.0), 30.0)), 0.5)
        w = B.what_if(app, ov)
        st.caption(w.get("label", ""))
        a, b = st.columns(2)
        for col, key, title in [(a, "original", "Original"), (b, "modified", "What-if")]:
            with col:
                st.markdown(f"### {title}")
                show_result(w[key])
        if "delta_probability" in w:
            st.metric("Change in estimated risk", f"{w['delta_probability']:+.1%}")
        if w.get("tenure_sweep"):
            st.dataframe(pd.DataFrame(w["tenure_sweep"]), hide_index=True)

with tab3:
    r = st.session_state.get("last")
    if not r or not r.get("app_id"):
        st.info("Assess a valid application first.")
    else:
        st.markdown("**Explain → Verify → Reassess.** Flag a value you believe is wrong. You will see a *hypothetical* reassessment; "
                    "the official record changes only after a reviewer verifies it.")
        field = st.selectbox("Field to correct", MODEL_INPUTS + ENGINE_B, format_func=lambda f: LABELS[f])
        cur = st.session_state["app"][field]
        st.write(f"Recorded value: **{VALUE_LABELS.get(cur, cur)}**")
        claimed = field_input(field, cur, f"claim-{field}")
        reason = st.text_input("Why do you believe it is incorrect? (evidence you can provide)")
        if st.button("Submit correction claim"):
            res = B.correct(r["app_id"], field, claimed, reason)
            st.session_state["corr"] = res
        res = st.session_state.get("corr")
        if res:
            if res.get("status") == "pending_verification":
                st.warning(res["label"])
                c = st.columns(2)
                if "risk" in res["before"] and "risk" in res["hypothetical_after"]:
                    c[0].metric("Official (current)", f"{res['before']['risk']['probability']:.1%}")
                    c[1].metric("Hypothetical (unverified)", f"{res['hypothetical_after']['risk']['probability']:.1%}", f"{res['delta_probability']:+.1%}")
                else:
                    st.write("Hypothetical result affects Engine B / is withheld pending review.")
                st.caption(f"Correction #{res['correction_id']} is PENDING_VERIFICATION. Open the Reviewer tab to verify or reject.")
            else:
                st.error(str(res.get("reason") or res.get("validation") or res))

with tab4:
    st.markdown("Reviewer view — restricted. " + ("" if os.getenv("LOANLENS_API_URL") else "(In-process mode: set `LOANLENS_REVIEWER_TOKEN` for token checks via the API.)"))
    token = st.text_input("Reviewer token", type="password")
    reviewer = st.text_input("Reviewer name", "reviewer1")
    pend = B.pending(token)
    if isinstance(pend, dict):
        st.error("Not authorised or backend error: " + str(pend.get("error")))
    else:
        st.subheader(f"Pending corrections ({len(pend)})")
        for c in pend:
            with st.container(border=True):
                st.write(f"#{c['correction_id']} · app `{c['app_id']}` · **{c['field']}**: {c['old_value']} → {c['claimed_value']}")
                st.caption(f"Applicant's stated reason: {c['reason'] or '—'}")
                note = st.text_input("Review note", key=f"note{c['correction_id']}")
                x, y = st.columns(2)
                if x.button("✅ Verify (updates official record)", key=f"v{c['correction_id']}"):
                    st.json(B.review(c["correction_id"], "VERIFIED", reviewer, note, token)); st.rerun()
                if y.button("❌ Reject", key=f"r{c['correction_id']}"):
                    B.review(c["correction_id"], "REJECTED", reviewer, note, token); st.rerun()
        st.subheader("Audit log (hash-chained, append-only)")
        v = B.verify(token)
        (st.success if v.get("valid") else st.error)(f"Chain valid: {v.get('valid')} · entries: {v.get('entries')}")
        rows = B.audit(token, 100)
        if isinstance(rows, list) and rows:
            st.dataframe(pd.DataFrame([{**{k: r[k] for k in ("id", "ts", "event_type", "actor", "subject")}, "details": str(r["details"]),
                                        "hash": r["hash"][:12]} for r in rows]), hide_index=True)
        if st.session_state.get("last", {}).get("app_id"):
            st.subheader("Decision snapshots for the current application")
            h = B.history(st.session_state["last"]["app_id"])
            st.dataframe(pd.DataFrame(h["snapshots"]), hide_index=True)

with tab5:
    m = info.get("metrics")
    st.subheader("Platform evidence")
    st.json({k: info[k] for k in ("model_version", "dataset_source", "trained_at", "trained_on", "runtime") if k in info})
    st.dataframe(pd.DataFrame([B.stats()]), hide_index=True)
    st.caption("Run `python scripts/linuxone_evidence.py` ON the LinuxONE instance and save the JSON + screenshots as submission evidence. "
               "Telum acceleration is NOT claimed: scikit-learn inference runs on CPU.")
    if m:
        st.subheader("Held-out test metrics")
        rows = []
        for k, v in m["models"].items():
            t = v["test"]
            rows.append({"model": k, **{x: round(t[x], 3) for x in ("roc_auc", "pr_auc", "precision", "recall", "f1", "brier")}, "threshold": t["threshold"]})
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        cm = m["models"]["logistic_regression"]["test"]["confusion_matrix"]
        st.write("Confusion matrix (deployed LR; rows = actual, cols = predicted)")
        st.table(pd.DataFrame([[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]], index=["actual good", "actual bad"], columns=["pred good", "pred bad"]))
        st.write("Calibration (5 bins)"); st.dataframe(pd.DataFrame(m["models"]["logistic_regression"]["calibration"]), hide_index=True)
        st.write("Group-level error rates by age band (audit view; age is not a model input)")
        st.dataframe(pd.DataFrame(m["fairness_age_groups"]), hide_index=True)
        st.subheader("Limitations"); [st.write("• " + x) for x in m["limitations"]]
