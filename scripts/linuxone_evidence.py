"""Collect execution evidence. Run ON the LinuxONE instance and keep the output + screenshots for submission.
    python scripts/linuxone_evidence.py            -> evidence/linuxone_evidence.json"""
import json, os, platform, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, sklearn
from loanlens import audit as A, service as S
from loanlens.config import ROOT


def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception as e:
        return f"unavailable: {e}"


APP = dict(monthly_income=25000, existing_emi=12000, loan_inr=200000, rate_pct=12, tenure_months=36, duration_months=36,
           credit_amount=6500, installment_rate=4, existing_credits=2, checking_status="lt_0", credit_history="past_delays",
           savings_status="lt_100", employment_since="lt_1y", housing="rent", property="none", age=29)
b = S.get_bundle()
lat = []
for _ in range(200):
    t = time.perf_counter(); S._score_many([APP]); lat.append((time.perf_counter() - t) * 1000)
cpuinfo = sh("grep -m1 -i '^features' /proc/cpuinfo") or sh("lscpu | grep -i flags")
ev = {
    "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "machine": platform.machine(), "is_s390x": platform.machine() == "s390x", "byteorder": sys.byteorder,
    "platform": platform.platform(), "python": platform.python_version(),
    "numpy": np.__version__, "sklearn": sklearn.__version__, "uname": sh("uname -a"), "lscpu": sh("lscpu | head -25"),
    "cpu_features_line": cpuinfo, "nnpa_flag_listed": "nnpa" in cpuinfo.lower(),
    "model_version": b["model_version"], "model_trained_on": b["trained_on"], "dataset": b["dataset_source"],
    "inference_latency_ms_single_row": {"n": len(lat), "p50": round(float(np.percentile(lat, 50)), 3),
                                        "p95": round(float(np.percentile(lat, 95)), 3), "max": round(max(lat), 3)},
    "audit_chain": A.verify_chain(),
    "claim_boundary": "Evidence shows inference executing on this host. scikit-learn runs on CPU; no Telum/NNPA acceleration "
                      "is claimed. Security properties are not established by running on LinuxONE alone.",
}
os.makedirs(ROOT / "evidence", exist_ok=True)
(ROOT / "evidence" / "linuxone_evidence.json").write_text(json.dumps(ev, indent=2))
print(json.dumps(ev, indent=2))
