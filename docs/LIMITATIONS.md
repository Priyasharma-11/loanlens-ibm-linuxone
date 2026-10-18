# Limitations (disclose these in the pitch)
* Target is historical repayment risk (German Credit label) — not approval, not default probability for Indian borrowers.
* Engine A amounts are in dataset units (DM in German Credit); Engine B is INR. They are intentionally not blended.
* German Credit: 1,000 rows, old, non-Indian. Synthetic data demonstrates workflow only; its metrics mean nothing about reality.
* Age-group error rates are an audit view with small samples; not proof of fairness. Other protected attributes are not analysed.
* What-if search is a bounded grid over amount and duration; results are hypothetical and may be unrealistic for a person.
* "Verification" is a human reviewer clicking a button in the prototype; no document checks, no bureau integration.
* Audit log detects tampering by someone who edits rows, not by someone who rewrites the whole chain; anchoring the head hash externally would fix that.
* Not production security: no encryption at rest, no user authentication for applicants, no rate limiting. Not RBI-certified.
