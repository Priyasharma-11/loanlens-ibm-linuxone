# Judge Q&A (short answers; full reasoning in the problem-statement analysis)
1. **What's new?** Not prediction or SHAP — the workflow: explain → flag discrepancy → *labelled hypothetical* reassessment → verified correction → reproducible snapshot, on LinuxONE.
2. **How can you explain a bank's rejection?** We can't, and we don't claim to. We explain *our* repayment-risk model; with lender reason codes this could be integrated.
3. **Are explanations correct?** Contributions are exact for our linear model and verified to sum to its logit (`tests/test_core.py::test_assess_and_explanation_additive`). They describe the model, not causes; correlated features (amount, duration, amount/month) share credit.
4. **Why LinuxONE?** Inference + audit run inside the enterprise platform; we record latency/arch evidence. We don't claim acceleration or that LinuxONE alone makes it secure.
5. **Fairness/old data?** Held-out metrics + age-group error rates only as an audit view; age is not a model input; no "bias-free" claim; proxies can still exist.
6. **Live change?** `validation.py` `@rule` (see README) → restart → `/assess` → `/audit`.
7. **Why logistic regression deployed?** Exact explanations; HistGradientBoosting is evaluated as a comparison but not deployed because it would need approximate attributions and gives no meaningful gain here.
8. **Security you actually built:** loopback-by-default API, reviewer token, payload limit, no stack traces, data-minimised logs, append-only triggers + hash chain. **Not built:** encryption at rest, authN for applicants, rate limiting, RBI compliance.
