from __future__ import annotations

import logging

from aiogram.types import CallbackQuery, Message

from app.keyboards.nano import nano_access_denied_keyboard
from app.services.activity_service import check_access
from app.texts import t

logger = logging.getLogger(__name__)


async def guard_message_access(
    message: Message,
    lang: str,
) -> bool:
    """
    Botning pullik (Faollik talab qiladigan) funksiyalari uchun
    kirish nuqtasi guard'i (13-bo'lim).

    Qoida: trial active YOKI activity active bo'lsa — ruxsat.
    Aks holda — "Faollik muddati tugagan" ekrani ko'rsatiladi va
    False qaytariladi (chaqiruvchi handler shu yerda to'xtashi
    kerak).
    """

    if message.from_user is None:
        return False

    result = await check_access(int(message.from_user.id))

    if result.allowed:
        return True

    await message.answer(
        t("access_denied_title", lang),
        reply_markup=nano_access_denied_keyboard(lang),
    )

    return False


async def guard_callback_access(
    callback: CallbackQuery,
    lang: str,
) -> bool:
    if callback.from_user is None:
        await callback.answer()
        return False

    result = await check_access(int(callback.from_user.id))

    if result.allowed:
        return True

    await callback.answer()

    try:
        await callback.message.edit_text(
            t("access_denied_title", lang),
            reply_markup=nano_access_denied_keyboard(lang),
        )
    except Exception:
        try:
            await callback.message.answer(
                t("access_denied_title", lang),
                reply_markup=nano_access_denied_keyboard(lang),
            )
        except Exception:
            logger.exception(
                "Access-denied xabarini ko'rsatib bo'lmadi."
            )

    return False


__all__ = [
    "guard_message_access",
    "guard_callback_access",
]
