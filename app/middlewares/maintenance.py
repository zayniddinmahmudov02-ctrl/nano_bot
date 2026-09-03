from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import is_admin
from app.services.bot_settings_service import (
    DEFAULT_MAINTENANCE_MESSAGE,
    get_bot_settings,
)


class MaintenanceMiddleware(BaseMiddleware):
    """
    Maintenance mode yoqilganda, admin bo'lmagan foydalanuvchilar
    uchun barcha xabar/callback handlerlarni bloklaydi va texnik
    ishlar haqida xabar beradi.

    Admin uchun har doim o'tkazib yuboriladi — aks holda admin
    maintenance mode'ni panel orqali o'chira olmay qoladi.
    """

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, Dict[str, Any]],
            Awaitable[Any],
        ],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")

        telegram_id = user.id if user is not None else None

        if telegram_id is not None and is_admin(telegram_id):
            return await handler(event, data)

        try:
            settings = await get_bot_settings()
        except Exception:
            # Sozlamalarni o'qib bo'lmasa, botni to'liq
            # yiqitmaslik uchun oddiy ishlashda davom etamiz.
            return await handler(event, data)

        if not settings.maintenance_mode:
            return await handler(event, data)

        text = (
            settings.maintenance_message
            or DEFAULT_MAINTENANCE_MESSAGE
        )

        if isinstance(event, Message):
            await event.answer(text)
        elif isinstance(event, CallbackQuery):
            await event.answer(
                "🛠 Texnik ishlar tufayli vaqtincha mavjud emas.",
                show_alert=True,
            )

        return None


__all__ = [
    "MaintenanceMiddleware",
]
