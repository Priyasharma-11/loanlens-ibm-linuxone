#!/usr/bin/env bash
# curl evidence of the API running on the host. Usage: ./scripts/api_smoke.sh [base_url]
U="${1:-http://127.0.0.1:8000}"; H='Content-Type: application/json'
APP='{"monthly_income":25000,"existing_emi":12000,"loan_inr":200000,"rate_pct":12,"tenure_months":36,"duration_months":24,"credit_amount":3500,"installment_rate":3,"existing_credits":1,"checking_status":"0_to_200","credit_history":"existing_paid_duly","savings_status":"100_to_500","employment_since":"1_to_4y","housing":"rent","property":"car_other","age":29}'
echo "--- health"; curl -s $U/health; echo
echo "--- valid assessment"; curl -s -X POST -H "$H" -d "{\"application\":$APP}" $U/assess | python3 -c "import sys,json;r=json.load(sys.stdin);print(r['status'],r['risk'],r['latency_ms'],'ms')"
echo "--- invalid (negative income)"; curl -s -X POST -H "$H" -d "{\"application\":${APP/\"monthly_income\":25000/\"monthly_income\":-25000}}" $U/assess | python3 -c "import sys,json;r=json.load(sys.stdin);print(r['status'],[e['code'] for e in r['validation']['errors']])"
echo "--- audit chain"; curl -s -H "X-Reviewer-Token: ${LOANLENS_REVIEWER_TOKEN:-}" $U/audit/verify; echo
