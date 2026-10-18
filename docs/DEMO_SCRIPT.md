# 3-minute demo video script (record on the LinuxONE-backed UI)
Before recording: `python scripts/find_demo_profile.py` so the first sample profile flips band; have a terminal showing `uname -m` → s390x.

| Time | Do | Say |
|---|---|---|
| 0:00–0:25 | Show profile "Auto-tuned demo". | "Asha earns ₹25,000 and pays ₹12,000 EMIs. She gets 'higher risk' and no idea why, whether her data is wrong, or what she can do." |
| 0:25–0:55 | Tab 1 → Assess. Point at s390x banner, risk band, latency. | "LoanLens validates input, estimates **repayment risk** with a model running on IBM LinuxONE, not a bank decision. Engine B separately computes affordability: 48% of income already goes to EMIs." |
| 0:55–1:25 | Show contribution chart + plain-language lines. | "Contributions come from the trained model and add up exactly to its output; text is fixed templates, no free-form LLM." |
| 1:25–1:55 | Tab 3 → submit the suggested correction (savings). Show hypothetical vs official. Tab 4 → Verify. | "She flags a wrong value. Hypothetical result is labelled unverified; the record only changes after a reviewer verifies it. Version 2 and a new snapshot are created." |
| 1:55–2:20 | Tab 2 → drag amount/duration sliders; show suggestions. Then Assess the 'Invalid' profile. | "Constrained what-ifs re-run the real model. Invalid inputs never get a score; each rejection is audited." |
| 2:20–2:45 | Tab 4 audit chain 'valid' + terminal `api_smoke.sh`; Tab 5 metrics. | "Hash-chained audit log, model version on every snapshot, held-out metrics and age-group error rates, API running on s390x." |
| 2:45–3:00 | Tab 5 limitations. | "We explain our model, not a bank's. Public/synthetic data. Next: lender reason codes, validation, hardware-accelerated inference." |
