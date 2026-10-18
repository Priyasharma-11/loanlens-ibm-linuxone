"""Train + evaluate. Run ON the target machine (LinuxONE) so the artifact is built for that architecture:
    python -m loanlens.train --dataset auto|german|synthetic
"""
import argparse, hashlib, json, platform, time
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from .config import MODEL_INPUTS, AUDIT_ONLY, artifact_dir
from .data import load_dataset
from .features import add_derived, build_preprocessor, group_names

MIN_GROUP_N = 30


def make_pipeline(clf):
    return Pipeline([("derive", FunctionTransformer(add_derived, validate=False)),
                     ("prep", build_preprocessor()), ("clf", clf)])


def _metrics(y, p, thr):
    pred = (p >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {"threshold": round(float(thr), 3),
            "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
            "accuracy": float((tn + tp) / len(y)),
            "precision": float(precision_score(y, pred, zero_division=0)),
            "recall": float(recall_score(y, pred, zero_division=0)),
            "f1": float(f1_score(y, pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y, p)), "pr_auc": float(average_precision_score(y, p)),
            "brier": float(brier_score_loss(y, p)), "base_rate_bad": float(np.mean(y))}


def _calibration(y, p, bins=5):
    d = pd.DataFrame({"y": np.asarray(y), "p": p})
    d["bin"] = pd.qcut(d["p"], bins, duplicates="drop")
    g = d.groupby("bin", observed=True).agg(n=("y", "size"), mean_predicted=("p", "mean"), observed_rate=("y", "mean"))
    return [{"bin": str(i), "n": int(r.n), "mean_predicted": round(float(r.mean_predicted), 3),
             "observed_rate": round(float(r.observed_rate), 3)} for i, r in g.iterrows()]


def _fairness(y, p, thr, age):
    """Group error rates by age band. Age is NOT a model input; this is an audit view only."""
    out = []
    for name, mask in [("age < 25", age < 25), ("age >= 25", age >= 25)]:
        m = np.asarray(mask)
        n = int(m.sum())
        row = {"group": name, "n": n}
        if n < MIN_GROUP_N:
            row["note"] = f"n < {MIN_GROUP_N}: too small for reliable rates"
        yy, pp = np.asarray(y)[m], (p[m] >= thr).astype(int)
        neg, pos = (yy == 0).sum(), (yy == 1).sum()
        row.update({"actual_bad_rate": float(yy.mean()) if n else None,
                    "flagged_risky_rate": float(pp.mean()) if n else None,
                    "false_positive_rate": float(((pp == 1) & (yy == 0)).sum() / neg) if neg else None,
                    "false_negative_rate": float(((pp == 0) & (yy == 1)).sum() / pos) if pos else None})
        out.append(row)
    return out


def train(dataset="auto", seed=42, n_synthetic=3000, out_dir=None):
    out_dir = out_dir or artifact_dir()
    df, source = load_dataset(dataset, n_synthetic, seed)
    X, y = df[MODEL_INPUTS + AUDIT_ONLY], df["bad"].values
    # Test split is isolated BEFORE preprocessing / threshold / model selection.
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=seed)

    models = {"logistic_regression": make_pipeline(LogisticRegression(C=1.0, max_iter=2000)),
              "hist_gradient_boosting": make_pipeline(HistGradientBoostingClassifier(
                  max_iter=150, learning_rate=0.05, max_depth=3, random_state=seed))}
    cv = StratifiedKFold(5, shuffle=True, random_state=seed)
    oof = {k: cross_val_predict(m, X_tr, y_tr, cv=cv, method="predict_proba")[:, 1] for k, m in models.items()}

    # Operating threshold chosen on out-of-fold TRAIN predictions (no test leakage), maximising F1.
    grid = np.arange(0.10, 0.91, 0.01)
    thr = float(grid[int(np.argmax([f1_score(y_tr, (oof["logistic_regression"] >= t).astype(int)) for t in grid]))])

    report = {"dataset": source, "n_rows": int(len(df)), "n_train": int(len(y_tr)), "n_test": int(len(y_te)),
              "target": "bad credit risk = 1 (historical repayment-risk label, NOT a bank approval decision)",
              "features_in_model": MODEL_INPUTS, "excluded_from_model": AUDIT_ONLY,
              "cv_roc_auc_train": {k: float(roc_auc_score(y_tr, v)) for k, v in oof.items()}, "models": {}}
    for k, m in models.items():
        m.fit(X_tr, y_tr)
        p = m.predict_proba(X_te)[:, list(m.classes_).index(1)]
        report["models"][k] = {"test": _metrics(y_te, p, thr), "calibration": _calibration(y_te, p)}
        if k == "logistic_regression":
            report["fairness_age_groups"] = _fairness(y_te, p, thr, X_te["age"].values)

    # Deployed model = logistic regression (exact additive explanations). Refit on ALL data for deployment.
    deployed = make_pipeline(LogisticRegression(C=1.0, max_iter=2000)).fit(X, y)
    prep = deployed.named_steps["prep"]
    Z = prep.transform(deployed.named_steps["derive"].transform(X))
    mean = np.asarray(Z).mean(axis=0)
    version = hashlib.sha256(json.dumps([source, len(df), seed, thr], sort_keys=True).encode()
                             + deployed.named_steps["clf"].coef_.tobytes()).hexdigest()[:12]
    bundle = {"pipeline": deployed, "threshold": thr, "background_mean": mean,
              "feature_groups": group_names(prep), "model_version": f"lr-{version}",
              "dataset_source": source, "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "trained_on": {"machine": platform.machine(), "python": platform.python_version(),
                             "sklearn": sklearn.__version__, "numpy": np.__version__}}
    joblib.dump(bundle, out_dir / "model.joblib")
    report.update({"deployed_model": "logistic_regression (refit on all rows)", "threshold": thr,
                   "model_version": bundle["model_version"], "trained_at": bundle["trained_at"],
                   "trained_on": bundle["trained_on"],
                   "limitations": ["Metrics are from a held-out split of ONE dataset; not evidence of real-world performance.",
                                   "Synthetic data (if used) only demonstrates workflow behaviour." if source == "synthetic"
                                   else "German Credit is small (1000 rows), old and not representative of Indian lending.",
                                   "Age-group error rates are an audit view, not proof of fairness."]})
    (out_dir / "metrics.json").write_text(json.dumps(report, indent=2))
    return bundle, report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="auto", choices=["auto", "german", "synthetic"])
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    b, r = train(a.dataset, a.seed)
    t = r["models"]["logistic_regression"]["test"]
    print(f"dataset={r['dataset']} model={b['model_version']} thr={b['threshold']:.2f}")
    for k, v in r["models"].items():
        m = v["test"]
        print(f"  {k:24s} AUC={m['roc_auc']:.3f} PR-AUC={m['pr_auc']:.3f} P={m['precision']:.2f} "
              f"R={m['recall']:.2f} F1={m['f1']:.2f} Brier={m['brier']:.3f}")
    print("saved ->", artifact_dir())
