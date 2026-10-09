"""
License request approval emails (SMTP).

★ CONFIGURATION — all in Backend/.env:
    SMTP_HOST=smtp.example.com
    SMTP_PORT=587
    SMTP_USER=you@example.com
    SMTP_PASSWORD=secret
    SMTP_FROM=License Portal <no-reply@example.com>   (optional, defaults to SMTP_USER)
    SMTP_TLS=true
    PORTAL_BASE_URL=http://localhost:3000             (base for approval links)

If SMTP is NOT configured, every email is appended to
Backend/logs/approval_emails.log instead (dev fallback) so the whole
approval flow can be exercised without a mail server.
"""

import os
import secrets
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
_LOG_FILE = _LOG_DIR / "approval_emails.log"


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


def send_email(to: list[str], subject: str, html_body: str, text_body: str) -> bool:
    """
    Send an email via SMTP. Returns True on success.
    Without SMTP config, logs to Backend/logs/approval_emails.log and
    still returns True (request flow must not break in dev).
    """
    to = [t for t in to if t]
    if not to:
        return False

    if not _smtp_configured():
        _log_fallback(to, subject, html_body, text_body)
        print(
            f"[email] SMTP not configured -> logged {subject!r} "
            f"to {_LOG_FILE} (to={to})"
        )
        return True

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT") or "587")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD") or ""
    from_addr = os.getenv("SMTP_FROM") or user
    use_tls = os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to)
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if use_tls:
                server.starttls()
            if user:
                server.login(user, password)
            server.sendmail(from_addr, to, msg.as_string())
        print(f"[email] sent {subject!r} to {to}")
        return True
    except Exception as exc:  # noqa: BLE001 — surface but never break the API
        print(f"[email] FAILED to send {subject!r} to {to}: {exc}")
        _log_fallback(to, f"[SEND FAILED] {subject}", html_body, text_body)
        return False


# ============================================================
# Templates
# ============================================================

def _fmt_dt(value) -> str:
    if not value:
        return "—"
    if isinstance(value, str):
        return value
    return f"{value:%d %b %Y %H:%M} UTC"


def _request_summary_rows(req) -> str:
    rows = [
        ("Request ID", req.request_id),
        ("Application", req.application_name),
        ("License / Product", req.license_name),
        ("License Type", req.license_type or "—"),
        ("Request Type", req.request_type),
        ("Quantity", req.quantity),
        ("Priority", req.priority),
        ("Requested For", f"{req.requested_for} ({req.requested_for_email})"),
        ("Raised By", f"{req.submitted_by or 'IT Team'} ({req.submitted_by_email or '—'})"),
        ("Justification", req.justification or "—"),
        ("Submitted At", _fmt_dt(req.created_at)),
    ]
    return "\n".join(
        f'<tr><td style="padding:8px 14px;border-bottom:1px solid #eef2f7;'
        f'font-weight:600;color:#334155;white-space:nowrap;">{label}</td>'
        f'<td style="padding:8px 14px;border-bottom:1px solid #eef2f7;color:#475569;">{value}</td></tr>'
        for label, value in rows
    )


def _request_summary_text(req) -> str:
    return "\n".join(
        [
            f"Request ID         : {req.request_id}",
            f"Application        : {req.application_name}",
            f"License / Product  : {req.license_name}",
            f"License Type       : {req.license_type or '-'}",
            f"Request Type       : {req.request_type}",
            f"Quantity           : {req.quantity}",
            f"Priority           : {req.priority}",
            f"Requested For      : {req.requested_for} ({req.requested_for_email})",
            f"Raised By          : {req.submitted_by or 'IT Team'} ({req.submitted_by_email or '-'})",
            f"Justification      : {req.justification or '-'}",
            f"Submitted At       : {_fmt_dt(req.created_at)}",
        ]
    )


def _button_html(url: str, label: str, color: str) -> str:
    return (
        f'<a href="{url}" style="display:inline-block;padding:12px 28px;margin:0 8px;'
        f'background:{color};color:#ffffff;text-decoration:none;border-radius:6px;'
        f'font-weight:700;font-size:15px;">{label}</a>'
    )


def build_approval_email(req, approver_role: str, token: str):
    """
    Build the approval email for 'Tower Head' or 'Application Owner'.
    Returns (subject, html_body, text_body).
    """
    url = approval_url(token)
    subject = (
        f"[Approval Required] {req.request_id} — {req.license_name} "
        f"for {req.requested_for}"
    )

    html = f"""\
<html><body style="font-family:Segoe UI,Arial,sans-serif;background:#f1f5f9;padding:24px;">
  <div style="max-width:640px;margin:auto;background:#ffffff;border-radius:10px;
              border:1px solid #e2e8f0;overflow:hidden;">
    <div style="background:linear-gradient(135deg,#1e3a8a,#2563eb);padding:20px 24px;">
      <h2 style="color:#ffffff;margin:0;font-size:18px;">License Request — Approval Needed</h2>
      <p style="color:#bfdbfe;margin:6px 0 0;font-size:13px;">
        You are approving as <b>{approver_role}</b>
      </p>
    </div>
    <div style="padding:20px 24px;">
      <p style="color:#334155;font-size:14px;">
        A license request has been raised on the License Management Portal and needs
        your approval as <b>{approver_role}</b>.
      </p>
      <table style="width:100%;border-collapse:collapse;font-size:13px;border:1px solid #e2e8f0;
                    border-radius:8px;overflow:hidden;">
        {_request_summary_rows(req)}
      </table>
      <div style="text-align:center;margin:26px 0 10px;">
        {_button_html(f"{url}?action=approve", "✔ Approve", "#16a34a")}
        {_button_html(f"{url}?action=reject", "✘ Decline", "#dc2626")}
      </div>
      <p style="color:#94a3b8;font-size:12px;text-align:center;margin-top:18px;">
        The buttons open a secure approval page (no portal login required).
        If the buttons don't work, copy this link:<br/>
        <span style="color:#64748b;">{url}</span>
      </p>
    </div>
    <div style="background:#f8fafc;padding:12px 24px;border-top:1px solid #e2e8f0;
                color:#94a3b8;font-size:11px;">
      License Management Portal — automated approval mail. Please do not reply.
    </div>
  </div>
</body></html>
"""

    text = f"""\
License Request — Approval Needed

You are approving as: {approver_role}

{_request_summary_text(req)}

Approve : {url}?action=approve
Decline : {url}?action=reject

(Secure approval link — no portal login required.)
"""
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


