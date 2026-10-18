import math, sqlite3, unittest
from tests._base import Base, SAMPLE
from loanlens import audit as A
from loanlens.affordability import affordability, emi
from loanlens.validation import validate_application


class TestAffordability(unittest.TestCase):
    def test_doc_example(self):  # 12000/25000 = 48%, 13000 left
        a = affordability(dict(SAMPLE, loan_inr=1, rate_pct=0, tenure_months=1000000 // 1))
        self.assertAlmostEqual(a["existing_emi_ratio"], 0.48)

    def test_emi_formula(self):
        self.assertAlmostEqual(emi(100000, 12, 12), 8884.88, places=1)
        self.assertAlmostEqual(emi(120000, 0, 12), 10000)


class TestValidation(unittest.TestCase):
    def test_negative_income_is_error(self):
        v = validate_application(dict(SAMPLE, monthly_income=-25000))
        self.assertIn("INCOME_INVALID", [e["code"] for e in v["errors"]])

    def test_missing_and_bad_category(self):
        a = dict(SAMPLE); a.pop("age"); a["housing"] = "castle"
        codes = [e["code"] for e in validate_application(a)["errors"]]
        self.assertIn("MISSING", codes); self.assertIn("BAD_CATEGORY", codes)

    def test_emi_above_income_is_review(self):
        v = validate_application(dict(SAMPLE, existing_emi=30000))
        self.assertFalse(v["errors"]); self.assertEqual(v["review"][0]["code"], "OVERCOMMITTED_BUDGET")


class TestService(Base):
    def test_invalid_input_not_scored_and_audited(self):
        n0 = len(A.audit_tail(1000))
        r = self.S.assess_application(dict(SAMPLE, monthly_income=-25000))
        self.assertEqual(r["status"], "invalid_input"); self.assertNotIn("risk", r)
        tail = A.audit_tail(1)[0]
        self.assertEqual(tail["event_type"], "VALIDATION_FAILED"); self.assertEqual(len(A.audit_tail(1000)), n0 + 1)

    def test_overcommitted_withholds_score(self):
        r = self.S.assess_application(dict(SAMPLE, existing_emi=30000))
        self.assertEqual(r["status"], "flagged_for_review"); self.assertNotIn("risk", r)

    def test_assess_and_explanation_additive(self):
        r = self.S.assess_application(SAMPLE)
        self.assertEqual(r["status"], "assessed")
        e = r["explanation"]
        total = e["base_logit"] + sum(c["contribution_logodds"] for c in e["contributions"])
        self.assertAlmostEqual(total, e["model_logit"], places=3)
        p = 1 / (1 + math.exp(-e["model_logit"]))
        self.assertAlmostEqual(p, r["risk"]["probability"], places=3)  # explanation == model output

    def test_scenarios_respect_constraints(self):
        r = self.S.assess_application(SAMPLE)
        for s in r["scenarios"]:
            self.assertGreaterEqual(s["amount_multiplier"], 0.5)
            self.assertTrue(6 <= s["duration_months"] <= 72)
            self.assertIn("HYPOTHETICAL", s["label"])

    def test_whatif_changes_prediction_and_leaves_record(self):
        r = self.S.assess_application(SAMPLE)
        w = self.S.what_if(SAMPLE, {"credit_amount": 1500})
        self.assertLess(w["delta_probability"], 0)
        self.assertEqual(self.S.history(r["app_id"])["version"], 1)

    def test_correction_pending_then_verified(self):
        r = self.S.assess_application(SAMPLE); aid = r["app_id"]
        c = self.S.submit_correction(aid, "savings_status", "ge_1000", "bank statement shows 1500")
        self.assertEqual(c["status"], "pending_verification"); self.assertIn("HYPOTHETICAL", c["label"])
        self.assertEqual(self.S.history(aid)["official_record"]["savings_status"], "lt_100")  # unchanged
        self.assertLess(c["delta_probability"], 0)
        v = self.S.review_correction(c["correction_id"], "VERIFIED", "reviewer1", "doc checked")
        self.assertEqual(v["app_version"], 2)
        h = self.S.history(aid)
        self.assertEqual(h["official_record"]["savings_status"], "ge_1000")
        self.assertEqual([s["kind"] for s in h["snapshots"]].count("OFFICIAL"), 2)
        self.assertEqual(self.S.review_correction(c["correction_id"], "VERIFIED", "x")["status"], "error")  # no double review

    def test_correction_rejected_keeps_record(self):
        aid = self.S.assess_application(SAMPLE)["app_id"]
        c = self.S.submit_correction(aid, "housing", "own", "x")
        self.S.review_correction(c["correction_id"], "REJECTED", "reviewer1", "no proof")
        self.assertEqual(self.S.history(aid)["official_record"]["housing"], "rent")

    def test_invalid_correction_refused(self):
        aid = self.S.assess_application(SAMPLE)["app_id"]
        self.assertEqual(self.S.submit_correction(aid, "monthly_income", -5, "typo")["status"], "invalid_input")

    def test_snapshot_has_model_version_and_hash(self):
        aid = self.S.assess_application(SAMPLE)["app_id"]
        s = self.S.history(aid)["snapshots"][0]
        self.assertTrue(s["model_version"].startswith("lr-")); self.assertEqual(len(s["input_hash"]), 64)

    def test_audit_chain_valid_then_tamper_detected(self):
        self.S.assess_application(SAMPLE)
        self.assertTrue(A.verify_chain()["valid"])
        with self.assertRaises(sqlite3.DatabaseError):  # append-only trigger
            with A.db() as c: c.execute("UPDATE audit_log SET actor='evil' WHERE id=1")
        with A.db() as c:  # attacker with DB access drops trigger and edits
            c.execute("DROP TRIGGER audit_no_update"); c.execute("UPDATE audit_log SET actor='evil' WHERE id=1")
        res = A.verify_chain()
        self.assertFalse(res["valid"]); self.assertEqual(res["first_bad_id"], 1)


if __name__ == "__main__":
    unittest.main()
