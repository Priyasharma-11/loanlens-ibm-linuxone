import os, tempfile, unittest

SAMPLE = dict(monthly_income=25000, existing_emi=12000, loan_inr=200000, rate_pct=12, tenure_months=36,
              duration_months=36, credit_amount=6500, installment_rate=4, existing_credits=2,
              checking_status="lt_0", credit_history="past_delays", savings_status="lt_100",
              employment_since="lt_1y", housing="rent", property="none", age=29)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["LOANLENS_ARTIFACTS"] = cls.tmp.name
        os.environ["LOANLENS_DATASET"] = "synthetic"
        os.environ.pop("LOANLENS_REVIEWER_TOKEN", None)
        from loanlens import service
        service.reset_cache()
        service.get_bundle()  # trains on synthetic data into the temp dir
        cls.S = service

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
