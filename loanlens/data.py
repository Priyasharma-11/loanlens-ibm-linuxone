"""Datasets: UCI Statlog German Credit (CC BY 4.0) or a clearly-labelled synthetic generator (same schema)."""
import urllib.request
import numpy as np
import pandas as pd
from .config import ROOT, CATEGORICAL

GERMAN_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/statlog/german/german.data"
GERMAN_PATH = ROOT / "data" / "german.data"
_COLS = ["checking_status", "duration_months", "credit_history", "purpose", "credit_amount", "savings_status",
         "employment_since", "installment_rate", "personal_status", "other_debtors", "residence_since",
         "property", "age", "other_plans", "housing", "existing_credits", "job", "dependents", "telephone",
         "foreign_worker", "cls"]
_MAP = {
    "checking_status": {"A11": "lt_0", "A12": "0_to_200", "A13": "ge_200", "A14": "no_account"},
    "credit_history": {"A30": "none_or_all_paid", "A31": "all_paid_this_bank", "A32": "existing_paid_duly",
                       "A33": "past_delays", "A34": "critical_other_credits"},
    "savings_status": {"A61": "lt_100", "A62": "100_to_500", "A63": "500_to_1000", "A64": "ge_1000",
                       "A65": "unknown_none"},
    "employment_since": {"A71": "unemployed", "A72": "lt_1y", "A73": "1_to_4y", "A74": "4_to_7y", "A75": "ge_7y"},
    "housing": {"A151": "rent", "A152": "own", "A153": "free"},
    "property": {"A121": "real_estate", "A122": "life_insurance", "A123": "car_other", "A124": "none"},
}


def download_german(timeout=20):
    GERMAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(GERMAN_URL, timeout=timeout) as r:
        GERMAN_PATH.write_bytes(r.read())


def load_german(path=GERMAN_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, sep=r"\s+", header=None, names=_COLS)
    for col, m in _MAP.items():
        df[col] = df[col].map(m)
    if df[list(_MAP)].isna().any().any():
        raise ValueError("Unexpected category codes in german.data - check the file.")
    df["bad"] = (df["cls"] == 2).astype(int)  # 1 = bad credit risk
    return df.drop(columns=["cls"])


def make_synthetic(n=3000, seed=42) -> pd.DataFrame:
    """Fictional applicants in the German-Credit-like schema. For workflow demos ONLY."""
    rng = np.random.default_rng(seed)
    probs = {
        "checking_status": [.27, .27, .06, .40], "credit_history": [.04, .05, .53, .09, .29],
        "savings_status": [.60, .10, .06, .05, .19], "employment_since": [.06, .17, .34, .17, .26],
        "housing": [.18, .71, .11], "property": [.28, .23, .33, .16],
    }
    df = pd.DataFrame({c: rng.choice(v, n, p=probs[c]) for c, v in CATEGORICAL.items()})
    df["duration_months"] = np.clip(rng.gamma(3.0, 7.0, n).round(), 4, 72).astype(int)
    df["credit_amount"] = np.clip(rng.lognormal(np.log(2800), 0.8, n).round(), 250, 18000).astype(int)
    df["installment_rate"] = rng.choice([1, 2, 3, 4], n, p=[.14, .23, .16, .47])
    df["existing_credits"] = rng.choice([1, 2, 3, 4], n, p=[.63, .33, .03, .01])
    df["age"] = np.clip(rng.normal(36, 11, n).round(), 19, 75).astype(int)
    eff = {
        "checking_status": {"lt_0": .9, "0_to_200": .4, "ge_200": -.3, "no_account": -.9},
        "credit_history": {"none_or_all_paid": .1, "all_paid_this_bank": .2, "existing_paid_duly": -.4,
                           "past_delays": .6, "critical_other_credits": .4},
        "savings_status": {"lt_100": .4, "100_to_500": .2, "500_to_1000": 0, "ge_1000": -.4, "unknown_none": -.5},
        "employment_since": {"unemployed": .5, "lt_1y": .4, "1_to_4y": .1, "4_to_7y": -.3, "ge_7y": -.2},
        "housing": {"rent": .2, "own": -.2, "free": .1},
        "property": {"real_estate": -.3, "life_insurance": -.1, "car_other": .1, "none": .4},
    }
    logit = (-1.4 + 0.035 * (df["duration_months"] - 20) + 0.00012 * (df["credit_amount"] - 3000)
             + 0.25 * (df["installment_rate"] - 2.5) + 0.1 * (df["existing_credits"] - 1))
    for c, m in eff.items():
        logit = logit + df[c].map(m)
    df["bad"] = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return df


def load_dataset(name="auto", n_synthetic=3000, seed=42):
    """Returns (df, source_label). 'auto' = German if present/downloadable, else synthetic."""
    if name == "synthetic":
        return make_synthetic(n_synthetic, seed), "synthetic"
    if name in ("german", "auto"):
        if not GERMAN_PATH.exists():
            try:
                download_german()
            except Exception as e:  # offline etc.
                if name == "german":
                    raise RuntimeError(f"Could not download German Credit ({e}). Download it manually from "
                                       f"https://archive.ics.uci.edu/dataset/144 and save as {GERMAN_PATH}")
                return make_synthetic(n_synthetic, seed), "synthetic"
        return load_german(), "german_credit_uci"
    raise ValueError(f"unknown dataset {name}")
