"""User repository for MySQL backed persistence."""

from __future__ import annotations

from typing import Optional
from datetime import datetime
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models.user import DBUser, User


class UserRepository:
    """Data access layer for `users` table (MySQL domain)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: str) -> Optional[DBUser]:
        result = await self._session.execute(select(User).where(User.id == user_id))
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return DBUser.model_validate(record)

    async def get_by_username(self, username: str) -> Optional[DBUser]:
        result = await self._session.execute(select(User).where(User.username == username))
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return DBUser.model_validate(record)

    async def get_by_phone(self, phone: str) -> Optional[DBUser]:
        result = await self._session.execute(select(User).where(User.phone == phone))
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return DBUser.model_validate(record)

    async def get_by_identifier(self, identifier: str) -> Optional[DBUser]:
        statement = select(User).where(
            or_(
                User.username == identifier,
                User.phone == identifier,
            )
        )
        result = await self._session.execute(statement)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return DBUser.model_validate(record)

    async def create_user(
        self,
        username: str,
        phone: str,
        password_hash: str,
        phone_verified_at=None,
        user_id: Optional[str] = None,
    ) -> Optional[DBUser]:
        user = User(
            id=user_id or str(uuid4()),
            username=username,
            phone=phone,
            password_hash=password_hash,
            phone_verified_at=phone_verified_at,
        )
        self._session.add(user)

        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            return None

        await self._session.refresh(user)
        return DBUser.model_validate(user)

    async def update_password(self, user_id: str, new_password_hash: str) -> bool:
        statement = (
            update(User)
            .where(User.id == user_id)
            .values(password_hash=new_password_hash)
            .execution_options(synchronize_session="fetch")
        )
        result = await self._session.execute(statement)
        await self._session.commit()
        return result.rowcount > 0

    async def set_active(self, user_id: str, is_active: bool) -> bool:
        statement = (
            update(User)
            .where(User.id == user_id)
            .values(is_active=is_active)
            .execution_options(synchronize_session="fetch")
        )
        result = await self._session.execute(statement)
        await self._session.commit()
        return result.rowcount > 0

    async def reactivate_user(
        self,
        user_id: str,
        username: str,
        password_hash: str,
        phone_verified_at: datetime,
    ) -> Optional[DBUser]:
        """
        Reactivate a previously deactivated user with a new username/password.
        Returns the updated user or None if uniqueness constraints fail.
        """
        statement = (
            update(User)
            .where(User.id == user_id)
            .values(
                username=username,
                password_hash=password_hash,
                is_active=True,
                phone_verified_at=phone_verified_at,
            )
            .execution_options(synchronize_session="fetch")
        )
        try:
            await self._session.execute(statement)
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            return None

        result = await self._session.execute(select(User).where(User.id == user_id))
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return DBUser.model_validate(record)
