"""
License request approval emails.

★ CONFIGURATION — all in Backend/.env:
    MAIL_TRANSPORT=auto            auto | graph | smtp | log
      auto  -> Microsoft Graph if MS_* credentials present, else SMTP, else log
      graph -> Microsoft Graph sendMail (uses MS_TENANT_ID / MS_CLIENT_ID /
               MS_CLIENT_SECRET + MAIL_FROM mailbox; works even when the
               tenant has SMTP AUTH disabled — aka.ms/smtp_auth_disabled)
      smtp  -> classic SMTP (SMTP_HOST/PORT/USER/PASSWORD/FROM/TLS)
      log   -> force dev mode (write to logs/approval_emails.log only)
    PORTAL_BASE_URL=http://localhost:3000   (base for approval links)

IMPORTANT: .env is re-read on EVERY send, so config edits apply without
restarting the backend.

Emails are ALWAYS appended to Backend/logs/approval_emails.log as an audit
trail (with transport + status), even when delivered for real.
"""

import os
import secrets
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests as http_requests
from dotenv import load_dotenv


def _reload_env() -> None:
    """Re-read Backend/.env so config edits apply without a restart."""
    try:
        load_dotenv(_ENV_FILE, override=True)
    except Exception:
        pass


_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_ENV_FILE, override=True)

_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
_LOG_FILE = _LOG_DIR / "approval_emails.log"

# OAuth token cache for Microsoft Graph (client-credentials flow).
_GRAPH_TOKEN_CACHE: dict = {}


def generate_token() -> str:
    """Unguessable token embedded in approval links (one per approver)."""
    return secrets.token_urlsafe(32)


def _portal_base() -> str:
    return os.getenv("PORTAL_BASE_URL", "http://localhost:3000").rstrip("/")


def approval_url(token: str) -> str:
    return f"{_portal_base()}/approvals/{token}"


def _smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER"))


def _log_fallback(to, subject, html_body, text_body):
    """Dev fallback: append the email to logs/approval_emails.log."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(_LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write("=" * 78 + "\n")
        fh.write(f"Time   : {datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC\n")
        fh.write(f"To     : {', '.join(to)}\n")
        fh.write(f"Subject: {subject}\n")
        fh.write("-" * 78 + "\n")
        fh.write(text_body + "\n")
        fh.write("=" * 78 + "\n\n")


def _transport() -> str:
    return (os.getenv("MAIL_TRANSPORT") or "auto").strip().lower()


def _graph_configured() -> bool:
    return bool(
        os.getenv("MS_TENANT_ID")
        and os.getenv("MS_CLIENT_ID")
        and os.getenv("MS_CLIENT_SECRET")
    )


def _graph_from() -> str:
    return (
        os.getenv("MAIL_FROM")
        or os.getenv("SMTP_FROM")
        or os.getenv("SMTP_USER")
        or ""
    ).strip()


def _graph_token() -> str:
    """Client-credentials token for Microsoft Graph (cached ~50 min)."""
    tenant = os.getenv("MS_TENANT_ID")
    client_id = os.getenv("MS_CLIENT_ID")
    client_secret = os.getenv("MS_CLIENT_SECRET")
    now = time.time()
    cached = _GRAPH_TOKEN_CACHE.get("token")
    if cached and now < _GRAPH_TOKEN_CACHE.get("expires_at", 0) - 120:
        return cached
    resp = http_requests.post(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    _GRAPH_TOKEN_CACHE["token"] = payload["access_token"]
    _GRAPH_TOKEN_CACHE["expires_at"] = now + int(
        payload.get("expires_in", 3600)
    )
    return _GRAPH_TOKEN_CACHE["token"]


def _graph_send(to, subject, html_body, text_body) -> tuple[bool, str]:
    """Send via Microsoft Graph app-only sendMail. Returns (ok, detail)."""
    sender = _graph_from()
    if not sender:
        return False, "MAIL_FROM / SMTP_FROM / SMTP_USER is empty"
    try:
        token = _graph_token()
    except Exception as exc:
        return False, f"Graph token failed: {exc}"
    message = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": html_body},
        "toRecipients": [{"emailAddress": {"address": addr}} for addr in to],
    }
    try:
        resp = http_requests.post(
            f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"message": message, "saveToSentItems": True},
            timeout=20,
        )
    except Exception as exc:
        return False, f"Graph sendMail error: {exc}"
    if resp.status_code in (200, 202):
        return True, f"Graph 202 via {sender}"
    detail = (resp.text or "")[:300].replace("\n", " ")
    return False, f"Graph {resp.status_code}: {detail}"


def _is_placeholder_email(addr: str) -> bool:
    """True for demo/placeholder addresses that must never be mailed.

    These come from the mock/demo login and test fixtures:
      - admin@licenseportal.onmicrosoft.com (fake SSO identity — the NDR source)
      - *@company.com / *@example.* / *@test.* (form placeholders & e2e fixtures)
    Sending to them produces Exchange NDRs (550 5.4.310 DNS domain
    does not exist), so they are skipped before any transport send.
    """
    a = (addr or "").strip().lower()
    if not a:
        return True
    domain = a.rsplit("@", 1)[-1] if "@" in a else ""
    if not domain or "." not in domain:
        return True
    if domain == "licenseportal.onmicrosoft.com":
        return True
    if domain == "company.com" or domain.startswith("example.") \
            or domain.endswith(".example") or domain.startswith("test.") \
            or domain.endswith(".test") or domain == "localhost":
        return True
    return False


def _clean_recipients(to: list[str] | str) -> tuple[list[str], list[str]]:
    """Split recipients into (valid, skipped_placeholders)."""
    if isinstance(to, str):
        to = [to]
    seen: set[str] = set()
    valid: list[str] = []
    skipped: list[str] = []
    for raw in to or []:
        addr = (raw or "").strip()
        if not addr:
            continue
        key = addr.lower()
        if key in seen:
            continue
        seen.add(key)
        if _is_placeholder_email(addr):
            skipped.append(addr)
            continue
        valid.append(addr)
    return valid, skipped


def _smtp_send(to, subject, html_body, text_body) -> tuple[bool, str]:
    """Send via classic SMTP. Returns (ok, detail)."""
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT") or "587")
    user = os.getenv("SMTP_USER")
    password = (os.getenv("SMTP_PASSWORD") or "").strip().strip("\"'")
    from_addr = os.getenv("SMTP_FROM") or user
    use_tls = os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to)
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            if use_tls:
                server.starttls()
            if user:
                server.login(user, password)
            server.sendmail(from_addr, to, msg.as_string())
        return True, f"SMTP via {host}:{port} as {user}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _audit(to, subject, html_body, text_body, transport: str, status: str):
    """Append every mail attempt to logs/approval_emails.log."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(_LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write("=" * 78 + "\n")
        fh.write(f"Time   : {datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC\n")
        fh.write(f"To     : {', '.join(to)}\n")
        fh.write(f"Subject: {subject}\n")
        fh.write(f"Via    : {transport} | {status}\n")
        fh.write("-" * 78 + "\n")
        fh.write(text_body + "\n")
        fh.write("=" * 78 + "\n\n")


def send_email(to: list[str], subject: str, html_body: str, text_body: str) -> bool:
    """Deliver an email.

    Transport order (MAIL_TRANSPORT, default auto):
      auto  -> Graph if MS_* configured, else SMTP if SMTP_* configured,
               else log-only.
      graph -> Graph only (falls back to SMTP if Graph fails AND SMTP
               is configured, else logs).
      smtp  -> SMTP only (logs on failure).
      log   -> log only.
    Every attempt is appended to logs/approval_emails.log with Via/Status.
    """
    _reload_env()
    to, _skipped = _clean_recipients(to)
    if _skipped:
        print(f"[email] skipped placeholder recipient(s): {', '.join(_skipped)}")
    if not to:
        _audit([], subject, html_body, text_body, "skipped",
               "skipped (placeholder/invalid recipients: "
               f"{', '.join(_skipped) or 'none'})")
        return False
    mode = _transport()
    graph_ok_cfg = _graph_configured()
    smtp_ok_cfg = _smtp_configured()

    if mode == "log":
        _audit(to, subject, html_body, text_body, "log", "logged (forced)")
        print(f"[email] log -> {', '.join(to)} | {subject}")
        return True

    def _try_graph():
        ok, detail = _graph_send(to, subject, html_body, text_body)
        _audit(to, subject, html_body, text_body, "graph", detail)
        print(f"[email] graph -> {', '.join(to)} | {detail}")
        return ok

    def _try_smtp():
        if not smtp_ok_cfg:
            return None
        ok, detail = _smtp_send(to, subject, html_body, text_body)
        _audit(to, subject, html_body, text_body, "smtp", detail)
        print(f"[email] smtp -> {', '.join(to)} | {detail}")
        return ok

    if mode == "graph":
        if graph_ok_cfg and _try_graph():
            return True
        result = _try_smtp()
        if result:
            return True
        if not graph_ok_cfg and not smtp_ok_cfg:
            _audit(to, subject, html_body, text_body, "log",
                   "logged (no transport configured)")
            print(f"[email] log -> {', '.join(to)} | {subject}")
        return True

    if mode == "smtp":
        result = _try_smtp()
        if result is None:
            _audit(to, subject, html_body, text_body, "log",
                   "logged (smtp not configured)")
        elif not result:
            pass  # failure already audited
        else:
            return True
        return True

    # mode == "auto"
    if graph_ok_cfg and _try_graph():
        return True
    result = _try_smtp()
    if result:
        return True
    if not graph_ok_cfg and not smtp_ok_cfg:
        _audit(to, subject, html_body, text_body, "log",
               "logged (no transport configured)")
        print(f"[email] log -> {', '.join(to)} | {subject}")
    return True


def _request_summary_rows(req) -> str:
    """HTML table rows shared by approval + status emails."""
    submitted = (
        req.created_at.strftime("%d %b %Y %H:%M UTC")
        if getattr(req, "created_at", None)
        else "-"
    )
    return f"""\
        <tr><td style="padding:6px 10px;color:#64748b;">Request ID</td>\
<td style="padding:6px 10px;font-weight:600;">{req.request_id}</td></tr>
        <tr><td style="padding:6px 10px;color:#64748b;">Application</td>\
<td style="padding:6px 10px;">{req.application_name}</td></tr>
        <tr><td style="padding:6px 10px;color:#64748b;">License / Product</td>\
<td style="padding:6px 10px;">{req.license_name}</td></tr>
        <tr><td style="padding:6px 10px;color:#64748b;">License Type</td>\
<td style="padding:6px 10px;">{req.license_type or "-"}</td></tr>
        <tr><td style="padding:6px 10px;color:#64748b;">Request Type</td>\
<td style="padding:6px 10px;">{req.request_type or "-"}</td></tr>
        <tr><td style="padding:6px 10px;color:#64748b;">Quantity</td>\
<td style="padding:6px 10px;">{req.quantity}</td></tr>
        <tr><td style="padding:6px 10px;color:#64748b;">Priority</td>\
<td style="padding:6px 10px;">{req.priority or "-"}</td></tr>
        <tr><td style="padding:6px 10px;color:#64748b;">Requested For</td>\
<td style="padding:6px 10px;">{req.requested_for} ({req.requested_for_email})</td></tr>
        <tr><td style="padding:6px 10px;color:#64748b;">Raised By</td>\
<td style="padding:6px 10px;">{req.submitted_by or "-"} \
({req.submitted_by_email or "-"})</td></tr>
        <tr><td style="padding:6px 10px;color:#64748b;">Justification</td>\
<td style="padding:6px 10px;">{req.justification or "-"}</td></tr>
        <tr><td style="padding:6px 10px;color:#64748b;">Submitted At</td>\
<td style="padding:6px 10px;">{submitted}</td></tr>"""


def _request_summary_text(req) -> str:
    submitted = (
        req.created_at.strftime("%d %b %Y %H:%M UTC")
        if getattr(req, "created_at", None)
        else "-"
    )
    return (
        f"Request ID         : {req.request_id}\n"
        f"Application        : {req.application_name}\n"
        f"License / Product  : {req.license_name}\n"
        f"License Type       : {req.license_type or '-'}\n"
        f"Request Type       : {req.request_type or '-'}\n"
        f"Quantity           : {req.quantity}\n"
        f"Priority           : {req.priority or '-'}\n"
        f"Requested For      : {req.requested_for} ({req.requested_for_email})\n"
        f"Raised By          : {req.submitted_by or '-'} "
        f"({req.submitted_by_email or '-'})\n"
        f"Justification      : {req.justification or '-'}\n"
        f"Submitted At       : {submitted}"
    )


def build_approval_email(req, approver_role: str, token: str):
    """(subject, html, text) for a Tower Head / Application Owner approval."""
    url = approval_url(token)
    subject = (
        f"[Approval Required] {req.request_id} — "
        f"{req.license_name} for {req.requested_for}"
    )
    html = f"""\
<html><body style="font-family:Segoe UI,Arial,sans-serif;background:#f1f5f9;padding:24px;">
  <div style="max-width:640px;margin:auto;background:#ffffff;border-radius:10px;
              border:1px solid #e2e8f0;overflow:hidden;">
    <div style="background:linear-gradient(135deg,#1e3a8a,#2563eb);padding:20px 24px;">
      <h2 style="color:#ffffff;margin:0;font-size:18px;">
        License Request — Approval Needed</h2>
      <p style="color:#bfdbfe;margin:6px 0 0;font-size:13px;">
        You are approving as: {approver_role}</p>
    </div>
    <div style="padding:20px 24px;">
      <table style="width:100%;border-collapse:collapse;font-size:13px;
                    border:1px solid #e2e8f0;">
        {_request_summary_rows(req)}
      </table>
      <div style="margin-top:20px;text-align:center;">
        <a href="{url}?action=approve"
           style="display:inline-block;background:#16a34a;color:#fff;text-decoration:none;
                  padding:12px 28px;border-radius:8px;font-weight:600;margin-right:12px;">
          ✔ Approve</a>
        <a href="{url}?action=reject"
           style="display:inline-block;background:#dc2626;color:#fff;text-decoration:none;
                  padding:12px 28px;border-radius:8px;font-weight:600;">
          ✘ Decline</a>
      </div>
      <p style="color:#64748b;font-size:12px;margin-top:16px;text-align:center;">
        Or open this secure link (no portal login required):<br>
        <a href="{url}">{url}</a></p>
    </div>
    <div style="background:#f8fafc;padding:12px 24px;border-top:1px solid #e2e8f0;
                color:#94a3b8;font-size:11px;">
      License Management Portal — automated mail. Please do not reply.
    </div>
  </div>
</body></html>
"""
    text = (
        f"License Request — Approval Needed\n\n"
        f"You are approving as: {approver_role}\n\n"
        f"{_request_summary_text(req)}\n\n"
        f"Approve : {url}?action=approve\n"
        f"Decline : {url}?action=reject\n\n"
        f"(Secure approval link — no portal login required.)"
    )
    return subject, html, text


def notify_approval_request(req, approver_role: str, token: str) -> bool:
    """Email the next approver (Tower Head or Application Owner)."""
    to = (
        req.tower_head_email
        if approver_role == "Tower Head"
        else req.app_owner_email
    )
    subject, html, text = build_approval_email(req, approver_role, token)
    return send_email([to], subject, html, text)


def _status_email(req, to: list[str], subject: str, headline: str, comment: str = "") -> bool:
    extra = (
        f'<p style="color:#334155;font-size:13px;margin-top:16px;">'
        f'Comment: {comment}</p>'
        if comment
        else ""
    )
    html = f"""\
<html><body style="font-family:Segoe UI,Arial,sans-serif;background:#f1f5f9;padding:24px;">
  <div style="max-width:640px;margin:auto;background:#ffffff;border-radius:10px;
              border:1px solid #e2e8f0;overflow:hidden;">
    <div style="background:linear-gradient(135deg,#1e3a8a,#2563eb);padding:20px 24px;">
      <h2 style="color:#ffffff;margin:0;font-size:18px;">{headline}</h2>
    </div>
    <div style="padding:20px 24px;">
      <table style="width:100%;border-collapse:collapse;font-size:13px;border:1px solid #e2e8f0;">
        {_request_summary_rows(req)}
      </table>
      {extra}
    </div>
    <div style="background:#f8fafc;padding:12px 24px;border-top:1px solid #e2e8f0;
                color:#94a3b8;font-size:11px;">
      License Management Portal — automated mail. Please do not reply.
    </div>
  </div>
</body></html>
"""
    text = f"{headline}\n\n{_request_summary_text(req)}\n{extra}"
    return send_email(to, subject, html, text)


def notify_status(req, new_status: str, comment: str = "") -> bool:
    """
    Notify stakeholders when the pipeline advances or ends:
      pending_tower_head -> confirmation to submitter (approval mail to TH sent separately)
      pending_app_owner  -> TH approved, confirmation to submitter
      pending_it_review  -> all email approvals done, IT final review
      approved/rejected  -> final outcome to submitter + requested user
    """
    if new_status == "pending_tower_head":
        return _status_email(
            req,
            [req.submitted_by_email],
            f"[Submitted] {req.request_id} — awaiting Tower Head approval",
            "Request Submitted 📨",
            comment,
        )

    if new_status == "pending_app_owner":
        return _status_email(
            req,
            [req.submitted_by_email],
            f"[Update] {req.request_id} — Tower Head approved",
            "Tower Head Approved ✅",
            comment,
        )

    if new_status == "pending_it_review":
        return _status_email(
            req,
            [req.submitted_by_email],
            f"[Action Needed] {req.request_id} — approvals done, IT final review",
            "Awaiting IT Team Final Review 🖥️",
            comment,
        )

    if new_status == "approved":
        return _status_email(
            req,
            [req.submitted_by_email, req.requested_for_email],
            f"[Approved] {req.request_id} — {req.license_name} for {req.requested_for}",
            "Request Approved ✅",
            comment,
        )

    if new_status == "rejected":
        return _status_email(
            req,
            [req.submitted_by_email, req.requested_for_email],
            f"[Rejected] {req.request_id} — {req.license_name} for {req.requested_for}",
            "Request Rejected ❌",
            comment,
        )

    return False


