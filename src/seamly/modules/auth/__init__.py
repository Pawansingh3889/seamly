"""Auth module: login, logout, and the demo user bootstrap."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from seamly.common.types import Result
from seamly.modules.auth import repository as auth_repo
from seamly.modules.auth import service as auth_service

PERMISSIONS: dict[str, set[str]] = {
    "auth.login": {"anonymous"},
    "auth.logout": {"ops", "analyst", "cfo", "admin"},
    "auth.bootstrap_demo_user": {"admin", "anonymous"},
}

DEMO_EMAIL = "cfo@kestrel.example"
DEMO_PASSWORD = "demo-secret"


async def handle_login(session: AsyncSession, payload: dict[str, Any]) -> Result[Any]:
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not email or not password:
        return Result.err("auth.credentials_required", "Email and password are required.")
    user = await auth_repo.user_by_email(session, email)
    if user is None or not auth_service.verify_password(password, user.password_hash):
        return Result.err("auth.bad_credentials", "Email or password is incorrect.")
    token = auth_service.new_session_token()
    await auth_repo.create_session(session, auth_service.hash_token(token), user.id)
    return Result.ok({"token": token, "name": user.name, "role": user.role})


async def handle_logout(session: AsyncSession, payload: dict[str, Any]) -> Result[Any]:
    token = str(payload.get("token", ""))
    if token:
        await auth_repo.delete_session(session, auth_service.hash_token(token))
    return Result.ok({})


async def handle_bootstrap_demo_user(session: AsyncSession, payload: dict[str, Any]) -> Result[Any]:
    """Idempotent: creates the demo CFO user if missing."""

    existing = await auth_repo.user_by_email(session, DEMO_EMAIL)
    if existing is not None:
        return Result.ok({"email": existing.email, "created": False})
    user = await auth_repo.create_user(
        session,
        email=DEMO_EMAIL,
        name="Demo CFO",
        password_hash=auth_service.hash_password(DEMO_PASSWORD),
        role="cfo",
    )
    return Result.ok({"email": user.email, "created": True})
