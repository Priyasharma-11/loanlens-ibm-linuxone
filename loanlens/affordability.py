"""Engine B: pure arithmetic affordability simulator (INR). Not a risk score or an eligibility rule."""


def emi(principal, annual_rate_pct, months):
    r = annual_rate_pct / 1200.0
    if r == 0:
        return principal / months
    f = (1 + r) ** months
    return principal * r * f / (f - 1)


def affordability(app: dict) -> dict:
    inc, ex = app["monthly_income"], app["existing_emi"]
    new = emi(app["loan_inr"], app["rate_pct"], app["tenure_months"])
    total = ex + new
    return {"new_emi": round(new, 2), "existing_emi": round(ex, 2),
            "total_emi": round(total, 2),
            "existing_emi_ratio": round(ex / inc, 4), "combined_emi_ratio": round(total / inc, 4),
            "income_after_emis": round(inc - total, 2),
            "total_interest": round(new * app["tenure_months"] - app["loan_inr"], 2),
            "note": "Arithmetic only - not a bank risk score or eligibility rule. Real assessment uses other factors."}


def tenure_sweep(app: dict, tenures=(12, 24, 36, 48, 60, 84, 120)):
    return [{"tenure_months": t, **{k: v for k, v in affordability({**app, "tenure_months": t}).items()
                                    if k in ("new_emi", "combined_emi_ratio", "total_interest")}} for t in tenures]
