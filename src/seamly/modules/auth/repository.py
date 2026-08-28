"""Auth repository: users and server-side sessions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seamly.modules.auth.models import Session, UserAccount


async def user_by_email(session: AsyncSession, email: str) -> UserAccount | None:
    found: UserAccount | None = await session.scalar(
        select(UserAccount).where(UserAccount.email == email)
    )
    return found


async def user_by_id(session: AsyncSession, user_id: int) -> UserAccount | None:
    return await session.get(UserAccount, user_id)


async def create_user(
    session: AsyncSession, email: str, name: str, password_hash: str, role: str
) -> UserAccount:
    row = UserAccount(email=email, name=name, password_hash=password_hash, role=role)
    session.add(row)
    return row


async def create_session(session: AsyncSession, token_hash: str, user_id: int) -> Session:
    row = Session(token_hash=token_hash, user_id=user_id)
    session.add(row)
    return row


async def session_by_token_hash(session: AsyncSession, token_hash: str) -> Session | None:
    found: Session | None = await session.scalar(
        select(Session).where(Session.token_hash == token_hash)
    )
    return found


async def delete_session(session: AsyncSession, token_hash: str) -> None:
    existing = await session_by_token_hash(session, token_hash)
    if existing is not None:
        await session.delete(existing)
