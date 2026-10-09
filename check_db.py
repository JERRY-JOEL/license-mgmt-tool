import os
import sys

ROOT = 'C:/Users/JerryJoel/OneDrive - Cloud Destinations Infotech Pvt Ltd/Documents/Projects/License Management Tool - Updated UI'


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

try:
    import psycopg2
    url = os.environ['DATABASE_URL'].replace('postgresql+psycopg2://', 'postgresql://')
    conn = psycopg2.connect(url, connect_timeout=3)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT version()")
    print('PostgreSQL reachable:', cur.fetchone()[0][:60])
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='license_requests' ORDER BY ordinal_position"
    )
    cols = [r[0] for r in cur.fetchall()]
    print('license_requests columns:', cols)
    conn.close()
    print('DB_OK')
except Exception as exc:
    print('DB_UNREACHABLE:', repr(exc))
    sys.exit(2)
