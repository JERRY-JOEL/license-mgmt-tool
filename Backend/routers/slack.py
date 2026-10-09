from typing import Any

from fastapi import APIRouter, HTTPException

from config.settings import get_settings

from database.database import SessionLocal
from database.models import Application, User

from services.inventory_service import (
    build_inventory_payload,
    get_optimization_recommendations,
)

from services.slack_client import SlackClient
from services.slack_license import get_license_data
from services.slack_usage import get_usage_summary
from services.slack_users import (
    get_user_mapping,
    list_slack_users,
)
from services.slack_workspace import get_workspace_info


router = APIRouter(
    prefix="/slack",
    tags=["Slack"],
)


def _build_client() -> SlackClient:

    settings = get_settings()

    return SlackClient(
        bot_token=settings.SLACK_BOT_TOKEN,
        user_token=settings.SLACK_USER_TOKEN,
        admin_token=settings.SLACK_ADMIN_TOKEN,
    )


# ============================================================
# Slack Authentication
# ============================================================

@router.get(
    "/auth",
    summary="Slack authentication status",
)
async def auth() -> dict[str, Any]:

    client = _build_client()

    auth_payload = client.auth_test()

    return {
        "ok": auth_payload.get("ok"),
        "team_id": auth_payload.get("team_id"),
        "team": auth_payload.get("team"),
        "user_id": auth_payload.get("user_id"),
        "user": auth_payload.get("user"),
    }


# ============================================================
# Slack Workspace
# ============================================================

@router.get(
    "/workspace",
    summary="Slack workspace metadata",
)
async def workspace() -> dict[str, Any]:

    client = _build_client()

    return get_workspace_info(client)


# ============================================================
# Slack Users
# ============================================================

@router.get(
    "/users",
    summary="Slack users",
)
async def users() -> dict[str, Any]:

    client = _build_client()

    return list_slack_users(client)


# ============================================================
# Slack User Mapping
# ============================================================

@router.get(
    "/users/mapping",
    summary="Slack user to employee mapping",
)
async def users_mapping() -> dict[str, Any]:

    client = _build_client()

    return get_user_mapping(client)


# ============================================================
# Slack License
# ============================================================

@router.get(
    "/license",
    summary="Slack license information",
)
async def slack_license() -> dict[str, Any]:

    client = _build_client()

    return get_license_data(client)


# ============================================================
# Slack Usage
# ============================================================

@router.get(
    "/usage",
    summary="Slack usage information",
)
async def usage() -> dict[str, Any]:

    client = _build_client()

    return get_usage_summary(client)


# ============================================================
# Combined Slack Inventory
# ============================================================

@router.get(
    "/inventory",
    summary="Combined Slack inventory",
)
async def inventory() -> dict[str, Any]:

    client = _build_client()

    workspace_info = get_workspace_info(client)

    users_payload = list_slack_users(client)

    license_payload = get_license_data(client)

    usage_payload = get_usage_summary(client)

    return build_inventory_payload(
        workspace_info,
        license_payload,
        users_payload,
        usage_payload,
    )


# ============================================================
# Slack Optimization
# ============================================================

@router.get(
    "/optimization",
    summary="Slack optimization recommendations",
)
async def optimization() -> dict[str, Any]:

    client = _build_client()

    users_payload = list_slack_users(client)

    usage_payload = get_usage_summary(client)

    license_payload = get_license_data(client)

    return get_optimization_recommendations(
        users_payload,
        usage_payload,
        license_payload,
    )


# ============================================================
# Slack Assigned Users (from database)
# ============================================================

def _slack_assigned_users(license_id: str | None = None) -> dict[str, Any]:
    """
    Return Slack users stored in the database (users table,
    scoped to the Slack application), shaped like the
    Microsoft 365 assigned-users payload expected by the
    frontend.
    """
    db = SessionLocal()
    try:
        slack_app = (
            db.query(Application)
            .filter(Application.name == "Slack")
            .first()
        )

        if slack_app is None:
            return {
                "application": "Slack",
                "license_id": license_id,
                "total_users": 0,
                "users": [],
            }

        users = (
            db.query(User)
            .filter(User.application_id == slack_app.id)
            .all()
        )

        payload_users = [
            {
                "user_id": u.id,
                "name": u.name or "Slack User",
                "display_name": u.name or "Slack User",
                "email": u.email,
                "external_user_id": u.external_user_id,
                "role": u.role or "Member",
                "status": u.status or "active",
                "department": "Engineering & Operations",
                "application_name": "Slack",
                "license_id": license_id,
                "license_name": "Slack Pro",
                "assigned_date": (
                    u.last_activity.strftime("%Y-%m-%d")
                    if u.last_activity
                    else "2024-01-25"
                ),
            }
            for u in users
        ]

        return {
            "application": "Slack",
            "license_id": license_id,
            "total_users": len(payload_users),
            "users": payload_users,
        }
    finally:
        db.close()


@router.get(
    "/assigned-users",
    summary="Slack users assigned to Slack licenses from the database",
)
async def assigned_users() -> dict[str, Any]:
    try:
        return _slack_assigned_users()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/licenses/{license_id}/assigned-users",
    summary="Slack users assigned to a specific Slack license",
)
async def assigned_users_for_license(license_id: str) -> dict[str, Any]:
    try:
        return _slack_assigned_users(license_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc