"""E2E test of the license request + email approval flow (dev mode, no SMTP)."""
import json
import re
import sys

import requests

BASE = "http://127.0.0.1:8000"
LOG = "Backend/logs/approval_emails.log"
failures = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"  {extra}" if extra else ""))
    if not cond:
        failures.append(name)


def read_log():
    with open(LOG, encoding="utf-8") as fh:
        return fh.read()


# 1. create
payload = {
    "application_name": "Slack",
    "license_name": "Slack Pro",
    "license_type": "Team Collaboration",
    "quantity": 1,
    "request_type": "Additional Seats",
    "priority": "High",
    "justification": "E2E approval flow test",
    "requested_for": "E2E User",
    "requested_for_email": "e2e.user@company.com",
    "submitted_by": "E2E IT",
    "submitted_by_email": "e2e.it@company.com",
    "tower_head_name": "E2E Tower Head",
    "tower_head_email": "e2e.th@company.com",
    "app_owner_name": "E2E App Owner",
    "app_owner_email": "e2e.ao@company.com",
}
r = requests.post(f"{BASE}/requests", json=payload, timeout=15)
check("POST /requests 201", r.status_code == 201, str(r.status_code))
req = r.json()
rid = req["request_id"]
check("status pending_tower_head", req["status"] == "pending_tower_head")

# 2. approval email to Tower Head was logged with a link
log = read_log()
check("TH approval mail logged", "e2e.th@company.com" in log)
urls = re.findall(r"http://localhost:3000/approvals/([A-Za-z0-9_\-]+)", log)
check("approval url present", bool(urls))
th_token = urls[-1]  # latest mail belongs to the request created above

# 3. GET approval context
r = requests.get(f"{BASE}/api/approvals/{th_token}", timeout=10)
check("GET approval 200", r.status_code == 200, str(r.status_code))
ctx = r.json()
check("role = Tower Head", ctx["your_role"] == "Tower Head")

# 4. TH approves -> pending_app_owner + AO mail
before = len(log)
r = requests.post(
    f"{BASE}/api/approvals/{th_token}",
    json={"action": "approve", "comment": "OK from TH"},
    timeout=15,
)
check("TH approve 200", r.status_code == 200, r.text[:160])
check("status pending_app_owner",
      r.json()["request"]["status"] == "pending_app_owner")
log = read_log()
check("AO approval mail logged", "e2e.ao@company.com" in log[before:])
ao_token = re.findall(
    r"http://localhost:3000/approvals/([A-Za-z0-9_\-]+)", log[before:]
)[-1]

# 5. TH cannot approve twice
r = requests.post(
    f"{BASE}/api/approvals/{th_token}", json={"action": "approve"}, timeout=10
)
check("double TH approve 409", r.status_code == 409, str(r.status_code))

# 6. AO approves -> pending_it_review + IT mail
before = len(log)
r = requests.post(
    f"{BASE}/api/approvals/{ao_token}",
    json={"action": "approve", "comment": "OK from AO"},
    timeout=15,
)
check("AO approve 200", r.status_code == 200, r.text[:160])
check("status pending_it_review",
      r.json()["request"]["status"] == "pending_it_review")
log = read_log()
check("IT final-review mail logged",
      "e2e.it@company.com" in log[before:] and "final" in log[before:].lower())

# 7. Portal list shows the pipeline
r = requests.get(f"{BASE}/requests", timeout=10)
check("GET /requests 200", r.status_code == 200)
items = [x for x in r.json() if x["request_id"] == rid]
check("request listed", len(items) == 1)
steps = items[0]["steps"]
check("4 steps", len(steps) == 4)
check("step states",
      [s["state"] for s in steps] == ["approved", "approved", "approved", "pending"],
      str([s["state"] for s in steps]))

# 8. IT final approve
r = requests.post(
    f"{BASE}/requests/{rid}/final-action",
    json={"action": "approve", "comment": "Allocated by IT"},
    timeout=15,
)
check("final approve 200", r.status_code == 200, r.text[:160])
check("status approved", r.json()["status"] == "approved")

# 9. no further actions allowed
r = requests.post(
    f"{BASE}/requests/{rid}/final-action", json={"action": "approve"}, timeout=10
)
check("final re-approve 409", r.status_code == 409, str(r.status_code))
r = requests.post(
    f"{BASE}/api/approvals/{th_token}", json={"action": "reject"}, timeout=10
)
check("closed TH reject 409", r.status_code == 409, str(r.status_code))

# 10. rejection path: TH rejects a second request
payload2 = dict(payload, license_name="Slack Business+")
r = requests.post(f"{BASE}/requests", json=payload2, timeout=15)
rid2 = r.json()["request_id"]
log = read_log()
th_token2 = re.findall(
    r"http://localhost:3000/approvals/([A-Za-z0-9_\-]+)", log
)[-1]
r = requests.post(
    f"{BASE}/api/approvals/{th_token2}",
    json={"action": "reject", "comment": "Budget freeze"},
    timeout=15,
)
check("TH reject 200", r.status_code == 200, r.text[:160])
check("status rejected", r.json()["request"]["status"] == "rejected")

# 11. invalid token
r = requests.get(f"{BASE}/api/approvals/not-a-real-token", timeout=10)
check("invalid token 404", r.status_code == 404, str(r.status_code))

# cleanup test rows
import psycopg2  # noqa: E402
import os  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv("Backend/.env")
url = os.environ["DATABASE_URL"].replace("postgresql+psycopg2://", "postgresql://")
conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()
cur.execute("DELETE FROM license_requests WHERE requested_for='E2E User'")
print("cleanup:", cur.rowcount, "rows deleted")
conn.close()

print()
if failures:
    print("FAILED:", failures)
    sys.exit(1)
print("ALL REQUEST-FLOW CHECKS PASSED")

