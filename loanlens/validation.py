"""Centralised validation, separate from the model. Add a rule = write a function and decorate it with @rule.
Severity: 'error' blocks assessment; 'review' withholds a normal score and flags for human review; 'warning' informs.
"""
import math
from .config import CATEGORICAL, ALL_FIELDS

RULES = []


def rule(fn):
    RULES.append(fn)
    return fn


def issue(sev, field, code, msg):
    return {"severity": sev, "field": field, "code": code, "message": msg}


def num(app, f):
    v = app.get(f)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or (isinstance(v, float) and not math.isfinite(v)):
        return None
    return v


@rule
def required_and_numeric(app):
    out = []
    for f in ALL_FIELDS:
        if app.get(f) is None:
            out.append(issue("error", f, "MISSING", f"{f} is required"))
        elif f not in CATEGORICAL and num(app, f) is None:
            out.append(issue("error", f, "NOT_NUMERIC", f"{f} must be a finite number"))
    return out


@rule
def categories_valid(app):
    return [issue("error", f, "BAD_CATEGORY", f"{f} must be one of {opts}")
            for f, opts in CATEGORICAL.items() if app.get(f) is not None and app.get(f) not in opts]


def _range(f, lo, hi, code):
    def r(app):
        v = num(app, f)
        if v is not None and not (lo <= v <= hi):
            return [issue("error", f, code, f"{f} must be between {lo} and {hi} (got {v})")]
        return []
    r.__name__ = f"range_{f}"
    return r


for _f, _lo, _hi, _c in [("monthly_income", 1, 1e8, "INCOME_INVALID"), ("existing_emi", 0, 1e8, "EMI_INVALID"),
                         ("loan_inr", 1, 1e9, "LOAN_INVALID"), ("rate_pct", 0, 60, "RATE_INVALID"),
                         ("tenure_months", 1, 360, "TENURE_INVALID"), ("credit_amount", 1, 250000, "AMOUNT_INVALID"),
                         ("duration_months", 1, 72, "DURATION_INVALID"), ("installment_rate", 1, 4, "INSTALL_INVALID"),
                         ("existing_credits", 0, 10, "CREDITS_INVALID"), ("age", 18, 100, "AGE_INVALID")]:
    rule(_range(_f, _lo, _hi, _c))


@rule
def overcommitted_budget(app):
    inc, emi = num(app, "monthly_income"), num(app, "existing_emi")
    if inc and emi is not None and inc > 0 and emi >= inc:
        return [issue("review", "existing_emi", "OVERCOMMITTED_BUDGET",
                      "Existing EMIs are at or above reported income - possible data error. "
                      "A normal risk score is withheld; please verify income and EMI.")]
    return []


@rule
def high_emi_ratio(app):
    inc, emi = num(app, "monthly_income"), num(app, "existing_emi")
    if inc and emi is not None and inc > 0 and 0.5 <= emi / inc < 1:
        return [issue("warning", "existing_emi", "HIGH_EMI_RATIO",
                      f"Existing EMIs use {emi / inc:.0%} of income (illustrative 50% caution level, not a lender rule).")]
    return []


def validate_application(app: dict) -> dict:
    res = {"errors": [], "review": [], "warnings": []}
    for r in RULES:
        for i in r(app):
            res[{"error": "errors", "review": "review", "warning": "warnings"}[i["severity"]]].append(i)
    return res
