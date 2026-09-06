"""V1 identity: a single local user, created on first use. Real auth (JWT / OAuth) is V2 and slots in here."""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import User

LOCAL_USER_EMAIL = "local@riff"


async def get_or_create_local_user(session: AsyncSession) -> User:
    user = (await session.execute(select(User).where(User.email == LOCAL_USER_EMAIL))).scalar_one_or_none()
    if user is None:
        user = User(email=LOCAL_USER_EMAIL, display_name="You")
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def current_user(session: AsyncSession = Depends(get_db)) -> User:
    return await get_or_create_local_user(session)
