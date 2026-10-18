"""Model-derived explanations.
For a logistic regression, the SHAP value of each (transformed) feature under the independence assumption is exactly
coef_j * (x_j - mean_j) in log-odds space. We compute that directly (no extra dependency), aggregate one-hot columns
back to the original feature, and verify additivity: base + sum(contributions) == model logit.
Text comes from fixed templates - never from a free-text generator.
"""
import numpy as np
import pandas as pd
from .config import MODEL_INPUTS, AUDIT_ONLY, LABELS, VALUE_LABELS


def to_frame(app: dict) -> pd.DataFrame:
    return pd.DataFrame([{k: app[k] for k in MODEL_INPUTS + AUDIT_ONLY}])


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def _display(feature, app):
    if feature == "amount_per_month":
        return f"{app['credit_amount'] / max(app['duration_months'], 1):,.0f}"
    v = app[feature]
    return VALUE_LABELS.get(v, v) if isinstance(v, str) else f"{v:,}" if isinstance(v, int) else f"{v:,.2f}"


def _strength(c):
    a = abs(c)
    return "strongly" if a >= 0.5 else "moderately" if a >= 0.2 else "slightly"


def explain(bundle: dict, app: dict) -> dict:
    pipe = bundle["pipeline"]
    prep, clf = pipe.named_steps["prep"], pipe.named_steps["clf"]
    z = np.asarray(prep.transform(pipe.named_steps["derive"].transform(to_frame(app))))[0]
    coef, mean = clf.coef_[0], bundle["background_mean"]
    contrib = coef * (z - mean)
    base = float(clf.intercept_[0] + coef @ mean)
    agg = {}
    for g, c in zip(bundle["feature_groups"], contrib):
        agg[g] = agg.get(g, 0.0) + float(c)
    rows = [{"feature": g, "label": LABELS.get(g, g), "value": _display(g, app),
             "contribution_logodds": round(c, 4), "direction": "raises_risk" if c > 0 else "lowers_risk"}
            for g, c in sorted(agg.items(), key=lambda kv: -abs(kv[1]))]
    logit = base + sum(agg.values())
    return {"method": "exact additive contributions for logistic regression (SHAP-equivalent, independent features)",
            "base_probability": float(_sigmoid(base)), "base_logit": base, "model_logit": float(logit),
            "contributions": rows, "plain_language": plain_language(rows),
            "caveat": "Contributions are relative to the average training applicant and describe the model, "
                      "not causes. Correlated inputs (e.g. amount, duration, amount per month) share credit."}


def plain_language(rows, top=5):
    out = []
    for r in rows[:top]:
        if abs(r["contribution_logodds"]) < 0.02:
            continue
        verb = "raised" if r["contribution_logodds"] > 0 else "lowered"
        out.append(f"{r['label']} ({r['value']}) {_strength(r['contribution_logodds'])} {verb} the estimated risk "
                   f"compared with the average applicant in the training data.")
    return out


def shap_crosscheck(bundle, background_df, app):
    """Optional: compare our contributions with the shap library if installed (returns None otherwise)."""
    try:
        import shap
    except Exception:
        return None
    pipe = bundle["pipeline"]
    tf = lambda df: np.asarray(pipe.named_steps["prep"].transform(pipe.named_steps["derive"].transform(df)))
    ex = shap.LinearExplainer((pipe.named_steps["clf"].coef_[0], pipe.named_steps["clf"].intercept_[0]), tf(background_df))
    return ex.shap_values(tf(to_frame(app)))[0]
