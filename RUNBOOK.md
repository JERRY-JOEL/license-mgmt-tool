# RUNBOOK — License Management Tool V2

How to run and connect the **Frontend** (React + Vite, port `3000`) and **Backend** (FastAPI, port `8000`) on a Windows dev machine.

---

## 1. Architecture

```
Browser (React SPA)
   │  http://localhost:3000
   ▼
Vite dev server  (Frontend/, port 3000)
   │  dev-proxy forwards these path prefixes → http://127.0.0.1:8000
   │    /api  /microsoft365  /slack  /licenses  /requests  /health
   ▼
FastAPI backend  (Backend/, port 8000)
   │
   ▼
PostgreSQL  (127.0.0.1:5432, database: license_management)
+ live calls: Microsoft Graph API, Slack API
```

The frontend never hard-codes `http://localhost:8000`; it calls **relative paths** (`/slack/assigned-users`, `/licenses/{id}/users`, …) and the Vite proxy (`Frontend/vite.config.js`) forwards them to the backend. This avoids CORS entirely in dev; CORS middleware is also enabled on the backend as a safety net.

---

## 2. Prerequisites

| Requirement | Version used | Check |
|---|---|---|
| Python | 3.12.x | `python --version` |
| Node.js + npm | Node 24 / npm 11 | `node -v` & `npm -v` |
| PostgreSQL | running on `127.0.0.1:5432` | `Get-NetTCPConnection -LocalPort 5432 -State Listen` |

---

## 3. One-time setup

### 3.1 Backend environment file

Create `Backend/.env` (already present in this workspace):

```env
SLACK_BOT_TOKEN=xoxb-...
SLACK_USER_TOKEN=xoxp-...
SLACK_ADMIN_TOKEN=xoxp-...
DATABASE_URL=postgresql+psycopg2://postgres:<password>@127.0.0.1:5432/license_management
MS_TENANT_ID=...
MS_CLIENT_ID=...
MS_CLIENT_SECRET=...
```

> `Backend/config/settings.py` loads **only** `Backend/.env` for Slack/Microsoft credentials, and `Backend/database/database.py` requires `DATABASE_URL` — without it the API refuses to start (`DATABASE_URL is not configured`).
>
> The `Frontend/.env` file only needs `VITE_API_BASE_URL=/api/v1` (display only; actual calls use relative paths + proxy). Backend secrets do **not** belong there.

### 3.2 Backend virtualenv + dependencies

```powershell
cd "…\License Management Tool V2\Backend"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3.3 Database tables

```powershell
cd "…\License Management Tool V2\Backend"
.\.venv\Scripts\python.exe create_tables.py
# → "Database tables created successfully!"
```

Creates `applications`, `licenses`, `users`, `license_assignments`, `license_assigned_users`, `microsoft365_*`, `slack_data`, `usage`, `contracts`, `sync_log`, `license_requests`, etc.

> **Note:** if an old `license_requests` table already exists with a legacy
> schema (e.g. from another project sharing this database), drop it first —
> `create_all` will not migrate existing tables:
> `DROP TABLE IF EXISTS license_requests;` then re-run `create_tables.py`.

---

## 3A. License Request → Email Approval flow

The **Licenses** page no longer adds licenses directly — the IT Team raises a
request on behalf of a user and approvals happen **by email**:

```
IT Team (Submit Request popup)
   │  POST /requests  → status: pending_tower_head
   ▼
Tower Head  ── approval email with ✔ Approve / ✘ Decline buttons
   │  link → http://localhost:3000/approvals/<token>  (public, no login)
   │  approve → status: pending_app_owner   (next approval email sent)
   │  reject  → status: rejected             (stakeholders notified)
   ▼
Application Owner  ── approval email (same buttons)
   │  approve → status: pending_it_review   (IT notified)
   │  reject  → status: rejected
   ▼
IT Team final action in portal  (Requests modal → Approve & Complete / Reject)
   │  POST /requests/{id}/final-action
   ▼
approved / rejected   (+ outcome emails to submitter & requested user)
```

- **Portal visibility:** Licenses page → **Requests** button → click a request
  to see the 4-step pipeline and **whose approval is pending**.
- **API:** `GET/POST /requests`, `GET /requests/{id}`,
  `POST /requests/{id}/final-action`, `GET/POST /api/approvals/{token}`
  (the approvals API is under `/api/…` so it doesn't shadow the
  `/approvals/:token` frontend page).
- **Email config (`Backend/.env`):** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
  `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TLS`, `PORTAL_BASE_URL`.
  With SMTP unset, emails are written to `Backend/logs/approval_emails.log`
  (dev mode — copy the link from there to test the flow).
- **E2E test:** `Backend/.venv/Scripts/python.exe e2e_flow_test.py`
  (backend must be running; cleans up its own rows).

### 3.4 Frontend dependencies

```powershell
cd "…\License Management Tool V2\Frontend"
npm install
```

---

## 4. Starting the stack (every session)

### Terminal 1 — Backend (port 8000)

```powershell
cd "…\License Management Tool V2\Backend"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Or from `Frontend/` (equivalent npm script):

```powershell
cd "…\License Management Tool V2\Frontend"
npm run backend    # runs: python -m uvicorn app:app --app-dir ../Backend --port 8000 --reload
```

On startup the API runs **Microsoft 365 + Slack background syncs** (may log Graph/Slack errors if credentials are invalid — the API still serves requests).

**Health check:**

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
# {"status":"healthy","service":"License Management API"}
```

Swagger UI: <http://localhost:8000/docs>

### Terminal 2 — Frontend (port 3000)

```powershell
cd "…\License Management Tool V2\Frontend"
npm run dev
```

Open <http://localhost:3000/> (login accepts any email/password — auth is currently mocked in `AuthContext.jsx`).

**End-to-end check through the proxy:**

```powershell
Invoke-RestMethod http://localhost:3000/health                      # healthy
Invoke-RestMethod http://localhost:3000/microsoft365/assigned-users # total_users=887
Invoke-RestMethod http://localhost:3000/slack/assigned-users        # total_users=12
Invoke-RestMethod http://localhost:3000/licenses/1/users            # 200
```


---

## 5. Frontend → backend endpoint map

All calls originate from `Frontend/src/api/services.js` (relative paths → Vite proxy → FastAPI):

| Frontend call | Backend route | Notes |
|---|---|---|
| `GET /health` | `app.py` | service status (Settings + sidebar) |
| `GET /microsoft365/license` | `routers/microsoft365.py` | MS Graph license inventory |
| `GET /microsoft365/inventory` | `routers/microsoft365.py` | combined inventory |
| `GET /microsoft365/users` | `routers/microsoft365.py` | MS Graph users |
| `GET /microsoft365/assigned-users` | `routers/microsoft365.py` | DB `license_assigned_users` |
| `GET /microsoft365/licenses/{id}/assigned-users` | `routers/microsoft365.py` | per-license users |
| `POST /microsoft365/sync` | `routers/microsoft365.py` | trigger sync |
| `GET /slack/license` | `routers/slack.py` | Slack billing/license |
| `GET /slack/inventory` | `routers/slack.py` | combined inventory |
| `GET /slack/users` | `routers/slack.py` | Slack workspace members |
| `GET /slack/assigned-users` | `routers/slack.py` | **added** — DB users for Slack app |
| `GET /slack/licenses/{id}/assigned-users` | `routers/slack.py` | **added** — per-license users |
| `GET /licenses/{id}/users` | `app.py` | unified (MS DB → Slack DB → empty) |

Vite proxy prefixes (`Frontend/vite.config.js`): `/api`, `/microsoft365`, `/slack`, `/licenses`, `/health` → `http://localhost:8000`.
**If you add a new top-level backend route prefix, add a matching proxy entry.**

> Note: `Frontend/src/api/client.js` (axios base `/api/v1`) is currently unused by pages; all live data flows through `services.js`. There are no `/api/v1` routes in the backend.

---

## 6. Ports & process management

| Port | Process | Log |
|---|---|---|
| 8000 | uvicorn (`python.exe`) | `Backend\uvicorn.log` / `uvicorn.err.log` when started detached |
| 3000 | vite (`node`) | `Frontend\vite.log` / `vite.err.log` when started detached |
| 5432 | postgres | Windows service |

Stop stray servers (e.g., an old instance blocking the port — error `[WinError 10048] only one usage of each socket address`):

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Get-NetTCPConnection -LocalPort 3000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Backend exits: `DATABASE_URL is not configured` | missing `Backend/.env` | create it (§3.1) |
| `[WinError 10048] bind 127.0.0.1:8000` | old uvicorn still running | kill process on port 8000 (§6) |
| 404 from `localhost:3000/...` but 200 from `localhost:8000/...` | Vite proxy missing the path prefix | add proxy entry in `vite.config.js` (§5) |
| 404 on `/slack/assigned-users` or `/slack/licenses/{id}/assigned-users` | backend running old code | restart uvicorn (routes added in `routers/slack.py`) |
| Sidebar shows “API offline” | backend down or still starting syncs | check `/health`; see `Backend/uvicorn.err.log` |
| MS 365 endpoints return 500 / `authenticated: false` | Graph credentials/scopes | verify `MS_*` vars in `Backend/.env`; check `/microsoft365/auth` |
| Slack endpoints return `missing_scope` | Slack token scopes | verify `SLACK_*` tokens/scopes (see `Backend/README.md` §4–6) |
| Empty MS assigned users | no sync data yet | `POST /microsoft365/sync`, then re-query |
| Frontend build fails | stale node_modules | delete `node_modules`, re-run `npm install` |

---

## 8. Verification checklist

```powershell
# 1. Backend health
Invoke-RestMethod http://127.0.0.1:8000/health

# 2. Direct backend data routes
Invoke-RestMethod http://127.0.0.1:8000/microsoft365/assigned-users   # 887 users
Invoke-RestMethod http://127.0.0.1:8000/slack/assigned-users          # 12 users
Invoke-RestMethod http://127.0.0.1:8000/slack/license                 # 200

# 3. Same routes through the frontend proxy
Invoke-RestMethod http://localhost:3000/health
Invoke-RestMethod http://localhost:3000/slack/assigned-users
Invoke-RestMethod http://localhost:3000/licenses/1/users

# 4. UI
Start http://localhost:3000/
```

Expected: all commands return `200`, and the UI loads the Dashboard with live license/user counts.

---

## 9. Quick command sheet

```powershell
# Backend
cd "…\License Management Tool V2\Backend"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload

# Frontend
cd "…\License Management Tool V2\Frontend"
npm run dev

# DB tables (first run / after model changes)
cd "…\License Management Tool V2\Backend"
.\.venv\Scripts\python.exe create_tables.py

# Production frontend build
cd "…\License Management Tool V2\Frontend"
npm run build        # output → Frontend/dist/
```
