import os
import sys

ROOT = 'C:/Users/JerryJoel/OneDrive - Cloud Destinations Infotech Pvt Ltd/Documents/Projects/License Management Tool - Updated UI'
BACKEND = sys.argv[1]  # 'frontend' or 'cmdb'


def load_env(path):
    if not os.path.exists(path):
        return
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())


load_env(os.path.join(ROOT, 'Frontend', '.env'))
load_env(os.path.join(ROOT, 'CMDB_Backend-main', '.env'))

if BACKEND == 'frontend':
    sys.path.insert(0, os.path.join(ROOT, 'Frontend', 'backend'))
    import main
    app = main.app
else:
    sys.path.insert(0, os.path.join(ROOT, 'CMDB_Backend-main'))
    from fastapi import FastAPI
    from routers.api_v1 import router
    app = FastAPI()
    app.include_router(router)

from fastapi.testclient import TestClient
import psycopg2

client = TestClient(app)  # no lifespan -> no network sync

url = os.environ['DATABASE_URL'].replace('postgresql+psycopg2://', 'postgresql://')
conn = psycopg2.connect(url, connect_timeout=5)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT id FROM applications ORDER BY id LIMIT 1")
APP_ID = cur.fetchone()[0]
cur.execute(
    "INSERT INTO licenses (application_id, product, license_type,"
    " purchased_qty, assigned_qty, available_qty, used_qty, data_source)"
    " VALUES (%s,'E2E Test Pool','test',5,0,5,0,'e2e') RETURNING id"
    , (APP_ID,))
LIC_ID = cur.fetchone()[0]
print('test license id:', LIC_ID)

failures = []


def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + (f'  {extra}' if extra else ''))
    if not cond:
        failures.append(name)


def counters():
    cur.execute(
        "SELECT available_qty, assigned_qty, used_qty FROM licenses WHERE id=%s",
        (LIC_ID,))
    return cur.fetchone()


def make(qty=1, lic=LIC_ID):
    r = client.post('/api/v1/requests', json={
        'requested_for': 'E2E Test User', 'email': 'e2e@example.com',
        'application_id': APP_ID, 'license_id': lic,
        'quantity': qty, 'priority': 'High', 'request_type': 'New License',
    })
    assert r.status_code == 201, r.text
    return r.json()


try:
    # 1. list endpoint
    r = client.get('/api/v1/requests')
    check('GET list 200', r.status_code == 200 and isinstance(r.json(), list))

    # 2. create
    req1 = make(2)
    check('POST create pending', req1['status'] == 'pending' and req1['request_id'])

    # 3. get one
    r = client.get(f"/api/v1/requests/{req1['request_id']}")
    check('GET one 200', r.status_code == 200 and r.json()['license_id'] == LIC_ID)

    # 4. approve
    r = client.put(f"/api/v1/requests/{req1['request_id']}", json={'action': 'approve'})
    check('approve -> approved', r.status_code == 200 and r.json()['status'] == 'approved',
          r.text[:120])

    # 5. double approve rejected
    r = client.put(f"/api/v1/requests/{req1['request_id']}", json={'action': 'approve'})
    check('double approve 409', r.status_code == 409, str(r.status_code))

    # 6. allocate decrements pool
    r = client.put(f"/api/v1/requests/{req1['request_id']}", json={'action': 'allocate'})
    ok = r.status_code == 200 and r.json()['status'] == 'allocated'
    check('allocate -> allocated', ok, r.text[:160])
    check('pool counters updated', counters() == (3, 2, 2), str(counters()))

    # 7. re-allocate rejected
    r = client.put(f"/api/v1/requests/{req1['request_id']}", json={'action': 'allocate'})
    check('re-allocate 409', r.status_code == 409, str(r.status_code))

    # 8. fulfilled via status
    r = client.put(f"/api/v1/requests/{req1['request_id']}", json={'status': 'fulfilled'})
    check('status=fulfilled', r.status_code == 200 and r.json()['status'] == 'fulfilled')

    # 9. insufficient seats
    req2 = make(9999)
    client.put(f"/api/v1/requests/{req2['request_id']}", json={'action': 'approve'})
    r = client.put(f"/api/v1/requests/{req2['request_id']}", json={'action': 'allocate'})
    check('insufficient seats 409', r.status_code == 409, str(r.status_code))

    # 10. no license pool
    req3 = make(1, lic=None)
    client.put(f"/api/v1/requests/{req3['request_id']}", json={'action': 'approve'})
    r = client.put(f"/api/v1/requests/{req3['request_id']}", json={'action': 'allocate'})
    check('no pool 400', r.status_code == 400, str(r.status_code))

    # 11. decline from pending
    req4 = make(1)
    r = client.put(f"/api/v1/requests/{req4['request_id']}", json={'action': 'decline'})
    check('decline -> declined', r.status_code == 200 and r.json()['status'] == 'declined')
    r = client.put(f"/api/v1/requests/{req4['request_id']}", json={'action': 'decline'})
    check('double decline 409', r.status_code == 409, str(r.status_code))

    # 12. status filter
    r = client.get('/api/v1/requests', params={'status': 'allocated'})
    check('status filter works',
          r.status_code == 200 and all(x['status'] == 'allocated' for x in r.json()))

    # 13. bad action
    r = client.put(f"/api/v1/requests/{req1['request_id']}", json={'action': 'bogus'})
    check('bad action 400', r.status_code == 400, str(r.status_code))

finally:
    cur.execute("DELETE FROM license_requests WHERE requested_for='E2E Test User'")
    cur.execute("DELETE FROM licenses WHERE id=%s", (LIC_ID,))
    conn.close()
    print('cleanup done')

print()
if failures:
    print('FAILED:', failures)
    sys.exit(1)
print(f'ALL CHECKS PASSED ({BACKEND})')
