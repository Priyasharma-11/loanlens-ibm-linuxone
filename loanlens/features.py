"""Feature pipeline pieces. Module-level functions so pickled pipelines are importable on any host."""
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from .config import NUMERIC, DERIVED, CATEGORICAL


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["amount_per_month"] = df["credit_amount"] / df["duration_months"].clip(lower=1)
    return df


def build_preprocessor() -> ColumnTransformer:
    cats = [CATEGORICAL[c] for c in CATEGORICAL]
    return ColumnTransformer(
        [("num", StandardScaler(), NUMERIC + DERIVED),
         ("cat", OneHotEncoder(categories=cats, handle_unknown="ignore", sparse_output=False), list(CATEGORICAL))],
        remainder="drop", sparse_threshold=0.0)


def group_names(prep) -> list:
    """Map each transformed column back to its original feature name."""
    groups = []
    for n in prep.get_feature_names_out():
        kind, rest = n.split("__", 1)
        if kind == "num":
            groups.append(rest)
        else:
            groups.append(max((c for c in CATEGORICAL if rest.startswith(c + "_")), key=len))
    return groups
