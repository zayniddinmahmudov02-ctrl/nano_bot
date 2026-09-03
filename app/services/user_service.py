from __future__ import annotations

from typing import Optional

from aiogram.types import User as TelegramUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import TelegramAccount, User, UserSettings


async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int,
) -> Optional[User]:
    """
    Telegram ID orqali ichki User obyektini topadi.

    MUHIM:
    telegram_id — Telegram'dagi katta ID.
    User.id — PostgreSQL ichki ID.
    Ularni aralashtirmaslik kerak.
    """
    result = await session.execute(
        select(User).where(
            User.telegram_id == int(telegram_id)
        )
    )

    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    telegram_user: TelegramUser,
) -> User:
    """
    Telegram foydalanuvchisini bazadan topadi yoki yaratadi.
    """

    telegram_id = int(telegram_user.id)

    user = await get_user_by_telegram_id(
        session=session,
        telegram_id=telegram_id,
    )

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            language="uz",
            active=True,
        )

        session.add(user)
        await session.flush()

        settings = UserSettings(
            user_id=user.id,
            language="uz",
            notifications_enabled=True,
        )

        session.add(settings)

        await session.flush()

    else:
        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
        user.last_name = telegram_user.last_name
        user.active = True

        await session.flush()

    return user


async def get_user_id_by_telegram_id(
    session: AsyncSession,
    telegram_id: int,
) -> Optional[int]:
    """
    Telegram ID'dan ichki users.id ni qaytaradi.
    """

    user = await get_user_by_telegram_id(
        session=session,
        telegram_id=telegram_id,
    )

    if user is None:
        return None

    return user.id


async def ensure_user(
    session: AsyncSession,
    telegram_user: TelegramUser,
) -> User:
    """
    get_or_create_user uchun qulay wrapper.
    """

    return await get_or_create_user(
        session=session,
        telegram_user=telegram_user,
    )


async def get_connected_telegram_account(
    session: AsyncSession,
    user_id: int,
) -> Optional[TelegramAccount]:
    """
    Foydalanuvchining ulangan (is_connected=True) Telegram
    akkauntini qaytaradi.

    MUHIM:
    user_id — users.id (ichki PostgreSQL ID).
    """

    result = await session.execute(
        select(TelegramAccount)
        .where(TelegramAccount.user_id == user_id)
        .where(TelegramAccount.is_connected.is_(True))
        .order_by(TelegramAccount.id.asc())
        .limit(1)
    )

    return result.scalar_one_or_none()


__all__ = [
    "get_user_by_telegram_id",
    "get_or_create_user",
    "get_user_id_by_telegram_id",
    "ensure_user",
    "get_connected_telegram_account",
]