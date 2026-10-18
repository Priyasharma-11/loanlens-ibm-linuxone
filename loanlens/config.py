"""Central configuration: schema, labels, paths. Paths are read at call time so tests can override via env."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def artifact_dir() -> Path:
    p = Path(os.getenv("LOANLENS_ARTIFACTS", ROOT / "artifacts"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return Path(os.getenv("LOANLENS_DB", artifact_dir() / "loanlens.db"))


def reviewer_token() -> str:
    return os.getenv("LOANLENS_REVIEWER_TOKEN", "")


# ---------------- Engine A: empirical risk model schema ----------------
NUMERIC = ["duration_months", "credit_amount", "installment_rate", "existing_credits"]
DERIVED = ["amount_per_month"]
CATEGORICAL = {
    "checking_status": ["lt_0", "0_to_200", "ge_200", "no_account"],
    "credit_history": ["none_or_all_paid", "all_paid_this_bank", "existing_paid_duly",
                       "past_delays", "critical_other_credits"],
    "savings_status": ["lt_100", "100_to_500", "500_to_1000", "ge_1000", "unknown_none"],
    "employment_since": ["unemployed", "lt_1y", "1_to_4y", "4_to_7y", "ge_7y"],
    "housing": ["rent", "own", "free"],
    "property": ["real_estate", "life_insurance", "car_other", "none"],
}
MODEL_INPUTS = NUMERIC + list(CATEGORICAL)
AUDIT_ONLY = ["age"]  # NOT a model feature; used for eligibility check + group-level error analysis only

# ---------------- Engine B: affordability simulator schema (INR) ----------------
ENGINE_B = ["monthly_income", "existing_emi", "loan_inr", "rate_pct", "tenure_months"]

ALL_FIELDS = MODEL_INPUTS + AUDIT_ONLY + ENGINE_B

LABELS = {
    "duration_months": "Loan duration (months)",
    "credit_amount": "Loan amount (dataset units)",
    "installment_rate": "Installment rate (1-4)",
    "existing_credits": "Existing credits",
    "amount_per_month": "Amount per month (derived)",
    "checking_status": "Checking account status",
    "credit_history": "Credit history",
    "savings_status": "Savings",
    "employment_since": "Employment duration",
    "housing": "Housing",
    "property": "Property",
    "age": "Age", "monthly_income": "Monthly income (INR)", "existing_emi": "Existing EMI (INR)",
    "loan_inr": "Requested loan (INR)", "rate_pct": "Interest rate (% p.a.)",
    "tenure_months": "Tenure (months)",
}

VALUE_LABELS = {
    "lt_0": "negative balance", "0_to_200": "balance 0-200", "ge_200": "balance 200+",
    "no_account": "no checking account",
    "none_or_all_paid": "no credits / all paid", "all_paid_this_bank": "all paid at this bank",
    "existing_paid_duly": "existing credits paid duly", "past_delays": "past payment delays",
    "critical_other_credits": "critical / credits elsewhere",
    "lt_100": "under 100", "100_to_500": "100-500", "500_to_1000": "500-1000", "ge_1000": "1000+",
    "unknown_none": "unknown / none",
    "unemployed": "unemployed", "lt_1y": "under 1 year", "1_to_4y": "1-4 years",
    "4_to_7y": "4-7 years", "ge_7y": "7+ years",
    "rent": "renting", "own": "owns home", "free": "lives free",
    "real_estate": "real estate", "life_insurance": "life insurance / savings agreement",
    "car_other": "car / other", "none": "none / unknown",
}

DISCLAIMER = ("Illustrative decision-support output from a prototype trained on public/synthetic data. "
              "It is NOT a lender's decision, NOT a credit score, and NOT financial advice. "
              "Explanations describe model behaviour, not causes of real-world repayment.")
