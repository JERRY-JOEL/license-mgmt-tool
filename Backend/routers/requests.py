"""
License Request approval workflow API.

Flow:
    IT Team submits (POST /requests)
      -> email approval : Tower Head      (GET/POST /approvals/{token})
      -> email approval : Application Owner (GET/POST /approvals/{token})
      -> IT Team final action in portal   (POST /requests/{id}/final-action)
      -> approved / rejected

Statuses: pending_tower_head -> pending_app_owner -> pending_it_review
          -> approved | rejected | cancelled
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database.database import SessionLocal
from database.models import LicenseRequest

from services.email_service import (
    generate_token,
    notify_approval_request,
    notify_status,
)


router = APIRouter(prefix="/requests", tags=["License Requests"])
# NOTE: API path is /api/approvals/* so it never collides with the portal
# page route /approvals/:token (Vite proxies /api to the backend).
approvals_router = APIRouter(prefix="/api/approvals", tags=["License Approvals"])


# ============================================================
# Schemas
# ============================================================

class LicenseRequestCreate(BaseModel):
    application_name: str = Field(min_length=1, max_length=255)
    license_name: str = Field(min_length=1, max_length=255)
    license_type: str | None = None
    quantity: int = Field(default=1, ge=1)
    request_type: str = "New License"
    priority: str = "Normal"
    justification: str | None = None

    requested_for: str = Field(min_length=1, max_length=255)
    requested_for_email: str = Field(min_length=3, max_length=255)

    submitted_by: str | None = None
    submitted_by_email: str | None = None

    tower_head_name: str = Field(min_length=1, max_length=255)
    tower_head_email: str = Field(min_length=3, max_length=255)
    app_owner_name: str = Field(min_length=1, max_length=255)
    app_owner_email: str = Field(min_length=3, max_length=255)


class ApprovalDecision(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    comment: str | None = None
    actor_name: str | None = None


class FinalAction(BaseModel):
    action: str = Field(pattern="^(approve|reject|cancel)$")
    comment: str | None = None


# ============================================================
# Helpers
# ============================================================

STATUS_LABELS = {
    "pending_tower_head": "Awaiting Tower Head approval",
    "pending_app_owner": "Awaiting Application Owner approval",
    "pending_it_review": "Awaiting IT Team final review",
    "approved": "Approved",
    "rejected": "Rejected",
    "cancelled": "Cancelled",
}


def _next_request_id(db) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"REQ-{today}-"
    count = (
        db.query(LicenseRequest)
        .filter(LicenseRequest.request_id.like(prefix + "%"))
        .count()
    )
    return f"{prefix}{count + 1:04d}"


def _serialize(req: LicenseRequest, include_tokens: bool = False) -> dict:
    """Portal-safe representation of a request (tokens never leak)."""
    payload = {
        "request_id": req.request_id,
        "application_name": req.application_name,
        "license_name": req.license_name,
        "license_type": req.license_type,
        "quantity": req.quantity,
        "request_type": req.request_type,
        "priority": req.priority,
        "justification": req.justification,
        "requested_for": req.requested_for,
        "requested_for_email": req.requested_for_email,
        "submitted_by": req.submitted_by,
        "submitted_by_email": req.submitted_by_email,
        "status": req.status,
        "status_label": STATUS_LABELS.get(req.status, req.status),
        "tower_head": {
            "name": req.tower_head_name,
            "email": req.tower_head_email,
            "action": req.tower_head_action,
            "comment": req.tower_head_comment,
            "action_at": req.tower_head_action_at.isoformat()
            if req.tower_head_action_at else None,
        },
        "app_owner": {
            "name": req.app_owner_name,
            "email": req.app_owner_email,
            "action": req.app_owner_action,
            "comment": req.app_owner_comment,
            "action_at": req.app_owner_action_at.isoformat()
            if req.app_owner_action_at else None,
        },
        "final_comment": req.final_comment,
        "final_action_at": req.final_action_at.isoformat()
        if req.final_action_at else None,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "updated_at": req.updated_at.isoformat() if req.updated_at else None,
        "steps": _steps(req),
    }
    if include_tokens:
        payload["tower_head_token"] = req.tower_head_token
        payload["app_owner_token"] = req.app_owner_token
    return payload


def _steps(req: LicenseRequest) -> list[dict]:
    """4-step pipeline for the portal (IT submit -> TH -> App Owner -> IT final)."""
    def state_of(status_when_active: str, action: str | None) -> str:
        # stored actions are the raw API verbs: 'approve' | 'reject'
        if action in ("approve", "approved"):
            return "approved"
        if action in ("reject", "rejected"):
            return "rejected"
        if req.status == status_when_active:
            return "pending"
        if req.status in ("rejected", "cancelled"):
            return "skipped"
        return "waiting"

    return [
        {
            "order": 1,
            "role": "IT Team",
            "actor": f"{req.submitted_by or 'IT Team'}"
                     + (f" ({req.submitted_by_email})" if req.submitted_by_email else ""),
            "state": "approved",
            "at": req.created_at.isoformat() if req.created_at else None,
            "comment": None,
            "channel": "portal",
        },
        {
            "order": 2,
            "role": "Tower Head",
            "actor": f"{req.tower_head_name or '—'}"
                     + (f" ({req.tower_head_email})" if req.tower_head_email else ""),
            "state": state_of("pending_tower_head", req.tower_head_action),
            "at": req.tower_head_action_at.isoformat()
            if req.tower_head_action_at else None,
            "comment": req.tower_head_comment,
            "channel": "email",
        },
        {
            "order": 3,
            "role": "Application Owner",
            "actor": f"{req.app_owner_name or '—'}"
                     + (f" ({req.app_owner_email})" if req.app_owner_email else ""),
            "state": state_of("pending_app_owner", req.app_owner_action),
            "at": req.app_owner_action_at.isoformat()
            if req.app_owner_action_at else None,
            "comment": req.app_owner_comment,
            "channel": "email",
        },
        {
            "order": 4,
            "role": "IT Team (final)",
            "actor": "IT Team",
            "state": (
                "approved" if req.status == "approved"
                else "rejected" if req.status == "rejected"
                else "cancelled" if req.status == "cancelled"
                else "pending" if req.status == "pending_it_review"
                else "waiting"
            ),
            "at": req.final_action_at.isoformat() if req.final_action_at else None,
            "comment": req.final_comment,
            "channel": "portal",
        },
    ]


# ============================================================
# IT Team endpoints (portal)
# ============================================================

@router.post("", status_code=201)
def create_request(payload: LicenseRequestCreate):
    """
    IT Team raises a license request on behalf of a user.
    Triggers the approval email to the Tower Head (step 1).
    """
    db = SessionLocal()
    try:
        req = LicenseRequest(
            request_id=_next_request_id(db),
            application_name=payload.application_name,
            license_name=payload.license_name,
            license_type=payload.license_type,
            quantity=payload.quantity,
            request_type=payload.request_type,
            priority=payload.priority,
            justification=payload.justification,
            requested_for=payload.requested_for,
            requested_for_email=payload.requested_for_email,
            submitted_by=payload.submitted_by or "IT Team",
            submitted_by_email=payload.submitted_by_email,
            tower_head_name=payload.tower_head_name,
            tower_head_email=payload.tower_head_email,
            app_owner_name=payload.app_owner_name,
            app_owner_email=payload.app_owner_email,
            tower_head_token=generate_token(),
            app_owner_token=generate_token(),
            status="pending_tower_head",
        )
        db.add(req)
        db.commit()
        db.refresh(req)

        # 1) approval mail to Tower Head (the actual "mail process")
        notify_approval_request(req, "Tower Head", req.tower_head_token)
        # 2) confirmation to the IT member who submitted
        notify_status(req, "pending_tower_head")

        return _serialize(req)
    finally:
        db.close()


@router.get("")
def list_requests(status: str | None = None):
    """List all requests (optionally filtered by pipeline status)."""
    db = SessionLocal()
    try:
        query = db.query(LicenseRequest).order_by(
            LicenseRequest.created_at.desc()
        )
        if status:
            query = query.filter(LicenseRequest.status == status)
        return [_serialize(r) for r in query.all()]
    finally:
        db.close()


@router.get("/{request_id}")
def get_request(request_id: str):
    """Single request incl. full 4-step approval pipeline."""
    db = SessionLocal()
    try:
        req = (
            db.query(LicenseRequest)
            .filter(LicenseRequest.request_id == request_id)
            .first()
        )
        if not req:
            raise HTTPException(404, "Request not found")
        return _serialize(req)
    finally:
        db.close()


@router.post("/{request_id}/final-action")
def final_action(request_id: str, payload: FinalAction):
    """
    IT Team final step — only valid once Tower Head AND Application Owner
    have both approved by email (status == pending_it_review).
    """
    db = SessionLocal()
    try:
        req = (
            db.query(LicenseRequest)
            .filter(LicenseRequest.request_id == request_id)
            .first()
        )
        if not req:
            raise HTTPException(404, "Request not found")
        if req.status not in ("pending_it_review", "pending_tower_head", "pending_app_owner"):
            raise HTTPException(
                409, f"Request already {req.status}; no further action possible"
            )

        if payload.action == "cancel":
            req.status = "cancelled"
            req.final_comment = payload.comment
            req.final_action_at = datetime.utcnow()
            new_status = "cancelled"
        else:
            # Only allow approve/reject to actually close the flow after
            # email approvals; earlier terminal actions fall back to cancel.
            if req.status != "pending_it_review":
                raise HTTPException(
                    409,
                    f"Cannot finalize while status is '{req.status}' — "
                    "email approvals are still pending",
                )
            req.status = "approved" if payload.action == "approve" else "rejected"
            req.final_comment = payload.comment
            req.final_action_at = datetime.utcnow()
            new_status = req.status

        db.commit()
        db.refresh(req)

        if new_status in ("approved", "rejected"):
            notify_status(req, new_status, payload.comment or "")
        elif new_status == "cancelled":
            notify_status(req, "rejected", payload.comment or "Cancelled by IT Team")

        return _serialize(req)
    finally:
        db.close()


# ============================================================
# Email approval endpoints (token-based, no login required)
# ============================================================

def _find_by_token(db, token: str):
    """Locate (request, approver_role) for an approval token."""
    if not token:
        return None, None
    req = (
        db.query(LicenseRequest)
        .filter(LicenseRequest.tower_head_token == token)
        .first()
    )
    if req:
        return req, "Tower Head"
    req = (
        db.query(LicenseRequest)
        .filter(LicenseRequest.app_owner_token == token)
        .first()
    )
    if req:
        return req, "Application Owner"
    return None, None


@approvals_router.get("/{token}")
def get_approval(token: str):
    """
    What the approver sees after clicking the link in the approval email.
    Returns request details + which role is acting + whether they already acted.
    """
    db = SessionLocal()
    try:
        req, role = _find_by_token(db, token)
        if not req:
            raise HTTPException(404, "Invalid or expired approval link")
        return {
            "request": _serialize(req),
            "your_role": role,
            "already_actioned": (
                (role == "Tower Head" and req.tower_head_action)
                or (role == "Application Owner" and req.app_owner_action)
            ),
            "your_action": (
                req.tower_head_action if role == "Tower Head"
                else req.app_owner_action
            ),
            "your_comment": (
                req.tower_head_comment if role == "Tower Head"
                else req.app_owner_comment
            ),
            "expired": req.status in ("approved", "rejected", "cancelled"),
        }
    finally:
        db.close()


@approvals_router.post("/{token}")
def decide(token: str, payload: ApprovalDecision):
    """
    Approve / reject from the email link.
      Tower Head approve   -> status becomes pending_app_owner, mail App Owner
      Tower Head reject    -> status becomes rejected, notify stakeholders
      App Owner approve    -> status becomes pending_it_review, notify IT Team
      App Owner reject     -> status becomes rejected, notify stakeholders
    """
    db = SessionLocal()
    try:
        req, role = _find_by_token(db, token)
        if not req:
            raise HTTPException(404, "Invalid or expired approval link")

        # Which status must this approver act in?
        required_status = (
            "pending_tower_head" if role == "Tower Head" else "pending_app_owner"
        )
        already = (
            req.tower_head_action if role == "Tower Head" else req.app_owner_action
        )
        if already:
            raise HTTPException(
                409, f"You already {already} this request"
            )
        if req.status != required_status:
            raise HTTPException(
                409,
                f"This request is not awaiting {role} approval "
                f"(current: {req.status})",
            )

        now = datetime.utcnow()
        comment = payload.comment
        actor = payload.actor_name

        if role == "Tower Head":
            req.tower_head_action = payload.action
            req.tower_head_comment = comment
            req.tower_head_action_at = now
            if actor:
                req.tower_head_name = actor
            if payload.action == "approve":
                req.status = "pending_app_owner"
                # hand over to Application Owner via email
                notify_approval_request(
                    req, "Application Owner", req.app_owner_token
                )
                notify_status(req, "pending_app_owner", comment or "")
            else:
                req.status = "rejected"
                notify_status(req, "rejected", comment or "Rejected by Tower Head")
        else:  # Application Owner
            req.app_owner_action = payload.action
            req.app_owner_comment = comment
            req.app_owner_action_at = now
            if actor:
                req.app_owner_name = actor
            if payload.action == "approve":
                req.status = "pending_it_review"
                notify_status(req, "pending_it_review", comment or "")
            else:
                req.status = "rejected"
                notify_status(
                    req, "rejected", comment or "Rejected by Application Owner"
                )

        db.commit()
        db.refresh(req)
        return {
            "request": _serialize(req),
            "your_role": role,
            "your_action": payload.action,
            "message": (
                "Approval recorded — request forwarded to the next stage"
                if payload.action == "approve"
                else "Rejection recorded — stakeholders notified"
            ),
        }
    finally:
        db.close()


