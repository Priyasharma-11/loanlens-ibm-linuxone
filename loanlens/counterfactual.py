"""Constrained what-if search (bounded grid, no external lib). All outputs are HYPOTHETICAL.
Constraints: loan amount may be reduced to at most 50% of the request; duration stays within [6, 72] months and
within +/-24 months of the request; categorical facts and income are never altered."""
from .config import VALUE_LABELS  # noqa: F401

AMOUNT_MULTS = [round(1 - 0.05 * i, 2) for i in range(0, 11)]
DURATION_DELTAS = [-12, -6, 0, 6, 12, 18, 24]
MIN_DUR, MAX_DUR = 6, 72


def band(p, thr):
    return "higher" if p >= thr else "moderate" if p >= 0.6 * thr else "lower"


BAND_RANK = {"higher": 2, "moderate": 1, "lower": 0}


def find_scenarios(app: dict, score_many, thr: float, p0: float, max_results=3):
    cands = []
    for m in AMOUNT_MULTS:
        for d in DURATION_DELTAS:
            dur = app["duration_months"] + d
            if not (MIN_DUR <= dur <= MAX_DUR) or (m == 1.0 and d == 0):
                continue
            c = dict(app, credit_amount=max(1, int(round(app["credit_amount"] * m))), duration_months=int(dur))
            cands.append((m, d, c))
    if not cands:
        return []
    probs = score_many([c for _, _, c in cands])
    b0 = band(p0, thr)
    res = []
    for (m, d, c), p in zip(cands, probs):
        b = band(float(p), thr)
        moves = BAND_RANK[b] < BAND_RANK[b0]
        if moves or (p0 - p) >= 0.01:
            res.append({"amount_multiplier": m, "duration_delta_months": d, "credit_amount": c["credit_amount"],
                        "duration_months": c["duration_months"], "probability": float(p), "band": b,
                        "delta_probability": float(p - p0), "moves_band": bool(moves), "cost": (1 - m) + abs(d) / 48.0,
                        "kind": "amount_only" if d == 0 else "duration_only" if m == 1.0 else "combined"})
    res.sort(key=lambda r: (BAND_RANK[r["band"]], r["cost"], r["probability"]))
    picked, kinds = [], set()
    for r in sorted(res, key=lambda r: (r["cost"], BAND_RANK[r["band"]], r["probability"])):
        if r["kind"] not in kinds:
            picked.append(r); kinds.add(r["kind"])
    picked.sort(key=lambda r: (not r["moves_band"], r["cost"]))
    for r in picked:
        r["label"] = "HYPOTHETICAL - not a guarantee and not a lender decision"
    return picked[:max_results]
