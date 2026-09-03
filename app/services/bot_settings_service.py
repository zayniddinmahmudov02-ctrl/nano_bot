from __future__ import annotations

import time
from typing import Optional

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import BotSettings

_SETTINGS_ROW_ID = 1
_CACHE_TTL_SECONDS = 10

_cache_value: Optional[BotSettings] = None
_cache_expires_at: float = 0.0

DEFAULT_MAINTENANCE_MESSAGE = (
    "🛠 <b>Nano-Bot texnik ishlar tufayli vaqtincha mavjud "
    "emas.</b>\n\n"
    "Iltimos, birozdan keyin qayta urinib ko‘ring."
)


async def _load_settings(session) -> BotSettings:
    result = await session.execute(
        select(BotSettings).where(
            BotSettings.id == _SETTINGS_ROW_ID
        )
    )

    settings = result.scalar_one_or_none()

    if settings is None:
        settings = BotSettings(
            id=_SETTINGS_ROW_ID,
            maintenance_mode=False,
        )

        session.add(settings)
        await session.commit()
        await session.refresh(settings)

    return settings


def _store_cache(settings: BotSettings) -> None:
    global _cache_value, _cache_expires_at

    _cache_value = settings
    _cache_expires_at = time.monotonic() + _CACHE_TTL_SECONDS


async def get_bot_settings(
    force_refresh: bool = False,
) -> BotSettings:
    global _cache_value

    now = time.monotonic()

    if (
        not force_refresh
        and _cache_value is not None
        and now < _cache_expires_at
    ):
        return _cache_value

    async with AsyncSessionLocal() as session:
        settings = await _load_settings(session)
        session.expunge(settings)

    _store_cache(settings)

    return settings


async def is_maintenance_mode() -> bool:
    settings = await get_bot_settings()
    return bool(settings.maintenance_mode)


async def set_maintenance_mode(
    enabled: bool,
    message: Optional[str] = None,
) -> BotSettings:
    async with AsyncSessionLocal() as session:
        settings = await _load_settings(session)

        settings.maintenance_mode = enabled

        if message is not None:
            settings.maintenance_message = message

        await session.commit()
        await session.refresh(settings)

        session.expunge(settings)

    _store_cache(settings)

    return settings


__all__ = [
    "DEFAULT_MAINTENANCE_MESSAGE",
    "get_bot_settings",
    "is_maintenance_mode",
    "set_maintenance_mode",
]
