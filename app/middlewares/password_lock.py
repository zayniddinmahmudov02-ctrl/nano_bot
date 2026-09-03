from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.database import AsyncSessionLocal
from app.services.password_service import evaluate_activity
from app.services.user_service import get_user_by_telegram_id
from app.states.password_lock import PasswordLockStates

CHALLENGE_TEXT = (
    "🔐 <b>Bot himoyalangan.</b>\n\n"
    "Davom etish uchun parolni kiriting:"
)


class PasswordLockMiddleware(BaseMiddleware):
    """
    Foydalanuvchi o'zi yoqqan "Bot paroli" (21/13-bo'limlar)
    himoyasini amalga oshiradi.

    MUHIM: bu Telegram akkaunt paroli/OTP/2FA EMAS — faqat
    Nano-Botning o'ziga kirishni himoyalovchi, foydalanuvchi
    ixtiyoriy ravishda yoqadigan qo'shimcha qatlam.

    Agar `password_enabled=True` va oxirgi 1 soat ichida
    faollik bo'lmagan bo'lsa — barcha boshqa handlerlar
    (sensitive bo'lganlari ham) to'xtatiladi va faqat parol
    kiritish holati ochiq qoladi.
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

        if telegram_id is None:
            return await handler(event, data)

        state = data.get("state")

        if state is not None:
            current_state = await state.get_state()

            if (
                current_state
                == PasswordLockStates.waiting_password_challenge.state
            ):
                # Parol kiritish jarayonining o'zi — dedicated
                # handlerga o'tkaziladi.
                return await handler(event, data)

        try:
            async with AsyncSessionLocal() as session:
                db_user = await get_user_by_telegram_id(
                    session,
                    telegram_id,
                )

            if db_user is None:
                # Hali /start bosilmagan — bloklash shart emas.
                return await handler(event, data)

            challenge_needed = await evaluate_activity(
                db_user.id
            )

        except Exception:
            # Sozlamalarni o'qib bo'lmasa, botni to'liq
            # yiqitmaslik uchun oddiy ishlashda davom etamiz.
            return await handler(event, data)

        if not challenge_needed:
            return await handler(event, data)

        if state is not None:
            await state.set_state(
                PasswordLockStates.waiting_password_challenge
            )

        if isinstance(event, Message):
            await event.answer(CHALLENGE_TEXT)
        elif isinstance(event, CallbackQuery):
            await event.answer(
                "🔐 Parol talab qilinadi.",
                show_alert=True,
            )

            if event.message is not None:
                try:
                    await event.message.answer(CHALLENGE_TEXT)
                except Exception:
                    pass

        return None


__all__ = [
    "PasswordLockMiddleware",
    "CHALLENGE_TEXT",
]
