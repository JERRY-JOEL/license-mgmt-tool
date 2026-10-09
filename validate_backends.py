import os
import sys
import importlib

ROOT = 'C:/Users/JerryJoel/OneDrive - Cloud Destinations Infotech Pvt Ltd/Documents/Projects/License Management Tool - Updated UI'

# Load DATABASE_URL from Frontend/.env so both backends can be imported
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

os.environ.setdefault(
    'DATABASE_URL',
    'postgresql+psycopg2://postgres:Cloud%40123@127.0.0.1:5432/license_management',
)

failures = []

# ---- 1) Frontend/backend (npm run backend) ----
sys.path.insert(0, os.path.join(ROOT, 'Frontend', 'backend'))
try:
    main = importlib.import_module('main')
    routes = [f"{sorted(r.methods)[0]} {r.path}" for r in main.app.routes
              if '/requests' in r.path]
    print('[Frontend/backend] import OK, request routes:')
    for r in sorted(routes):
        print('   ', r)
    if len(routes) < 4:
        failures.append(f'Frontend/backend has only {len(routes)} request routes')
except Exception as exc:
    failures.append(f'Frontend/backend import failed: {exc!r}')
finally:
    for mod in list(sys.modules):
        if mod in ('main', 'models', 'database', 'schemas', 'seed_data'):
            del sys.modules[mod]
    sys.path.pop(0)

# ---- 2) CMDB_Backend-main ----
sys.path.insert(0, os.path.join(ROOT, 'CMDB_Backend-main'))
try:
    api_v1 = importlib.import_module('routers.api_v1')
    routes = [f"{sorted(r.methods)[0]} {r.path}" for r in api_v1.router.routes
              if '/requests' in r.path]
    print('[CMDB_Backend-main] import OK, request routes:')
    for r in sorted(routes):
        print('   ', r)
    if len(routes) < 4:
        failures.append(f'CMDB has only {len(routes)} request routes')
except Exception as exc:
    failures.append(f'CMDB import failed: {exc!r}')
finally:
    for mod in list(sys.modules):
        if mod.startswith('routers') or mod in ('database', 'models'):
            del sys.modules[mod]
    sys.path.pop(0)

if failures:
    print('\nFAILURES:')
    for f in failures:
        print(' -', f)
    sys.exit(1)

print('\nAll backend imports and request routes validated.')
