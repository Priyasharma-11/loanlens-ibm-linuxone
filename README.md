# 🔍 LoanLens — Explain the Assessment · Verify the Data · Explore the Alternatives
IBM Z Datathon 2026 · Theme 2 (AI Secured: Innovation Without Exposure) · explainable, privacy-aware loan-assessment **decision support** prototype.

> Not a lender's decision, not a credit score, not financial advice. Uses public/synthetic data only.

## What it does (the 3 features + 2 supporting)
| | Feature | Where |
|---|---|---|
| 1 | **Explainable risk assessment** – Engine A: logistic-regression repayment-risk model; exact additive per-feature contributions (SHAP-equivalent for linear models, verified `base + Σ = logit`), fixed plain-language templates | `loanlens/explain.py` |
| 2 | **Explain → Verify → Reassess** – applicant flags a value → *hypothetical* reassessment (clearly labelled) → official record changes **only** after a reviewer verifies | `service.submit_correction / review_correction` |
| 3 | **Constrained what-if** – bounded search (amount ≥ 50% of request, duration 6–72 mo); model is re-run every time. Engine B = separate INR affordability simulator | `counterfactual.py`, `affordability.py` |
| + | **Audit trail** – hash-chained, append-only SQLite log; decision snapshots store input hash, model version, timestamp, explanation, status | `audit.py` |
| + | **Evaluation & limitations** – confusion matrix, precision/recall/F1, ROC-AUC, PR-AUC, Brier, calibration, age-group error rates (age is *not* a model input) | `train.py` → `artifacts/metrics.json` |

Design decisions that make it defensible:
* **Two engines, kept separate**: German Credit has no income/EMI fields, so Engine A (empirical model) and Engine B (INR arithmetic) are never blended.
* **Target = historical repayment risk**, never "bank approval".
* **Validation is centralised and separate from the model** (`validation.py`, `@rule`). Invalid input → no score + audit entry. EMI ≥ income → score *withheld*, flagged for review.
* **Data minimisation in logs**: validation failures log field names + codes, not values.
* **Stdlib-only API** (`server.py`) → no compiled web dependencies on s390x. Reviewer endpoints need a token (or loopback only).

## Architecture
```
Browser → custom dashboard (web/index.html)
       → loanlens/web_ui.py (HTTP server + API proxy, 127.0.0.1:8080)
       → loanlens/server.py (backend API, 127.0.0.1:8000)
       → service layer: validation, risk model and explanations, affordability,
         what-if analysis, correction workflow, SQLite records and audit log

Alternate interface: app/streamlit_app.py
CLI demonstration: scripts/demo_cli.py
```

## Quick start (any machine, 2 minutes)
```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-core.txt
python -m loanlens.train --dataset auto    # German Credit if downloadable, else clearly-labelled synthetic
python scripts/find_demo_profile.py        # picks an applicant that flips band via what-if AND correction
python -m unittest discover -s tests -t . -v
python scripts/demo_cli.py                 # full flow in the terminal
# Primary dashboard: start ./scripts/run_api.sh 127.0.0.1 8000 in one terminal, then run python loanlens/web_ui.py in another.
```
Dataset choice: `--dataset german` (needs internet once, or place `german.data` in `data/`; UCI Statlog, CC BY 4.0) · `--dataset synthetic` (fictional; workflow demo only).

**Deploying on IBM LinuxONE: see `docs/DEPLOY_LINUXONE.md`.**

## Judge live-challenge: "block negative income & audit every rejection"
Already implemented; to show a *new* rule live, add to `loanlens/validation.py`:
```python
@rule
def loan_not_more_than_60x_income(app):
    inc, loan = num(app, "monthly_income"), num(app, "loan_inr")
    if inc and loan and loan > 60 * inc:
        return [issue("error", "loan_inr", "LOAN_TOO_LARGE", "Requested loan exceeds 60x monthly income")]
    return []
```
Restart the server, `POST /assess` → `invalid_input`, then `GET /audit` → new `VALIDATION_FAILED` entry. (`tests/test_core.py` covers negative income.)

## API
`GET /health /model /stats /history/<id>` · `POST /assess /whatif /corrections` · reviewer-only: `GET /pending /audit /audit/verify`, `POST /corrections/<id>/review {"decision":"VERIFIED|REJECTED"}`. `./scripts/api_smoke.sh` shows curl examples.

## Honest status of this build
* ✅ Tested here: model training/evaluation, validation, explanations (additivity), what-if constraints, correction workflow, audit chain + tamper detection, HTTP API incl. token enforcement — 17 unit/integration tests passing (on x86_64, Python 3.12, scikit-learn 1.8).
* ✅ Verified on IBM LinuxONE (`s390x`, Python 3.12.3, scikit-learn 1.4.1.post1): API health, dashboard-to-API connection, a sample assessment, and all 17 automated tests passed. Two API tests emitted non-fatal `ResourceWarning` messages about unclosed test sockets.
* Metrics in `artifacts/metrics.json` come from whichever dataset *you* train on; synthetic-data numbers are not evidence of real-world performance.
