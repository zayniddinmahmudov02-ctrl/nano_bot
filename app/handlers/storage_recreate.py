from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.database import AsyncSessionLocal
from app.keyboards.storage import (
    STORAGE_RECREATE_CANCELLED_TEXT,
    STORAGE_RECREATE_FAILED_TEXT,
    STORAGE_RECREATED_TEXT,
)
from app.services.storage_channel_service import (
    recreate_user_storage_channel,
)
from app.services.user_service import (
    get_connected_telegram_account,
    get_user_by_telegram_id,
)

logger = logging.getLogger(__name__)

router = Router()


async def _safe_edit(callback: CallbackQuery, text: str) -> None:
    try:
        await callback.message.edit_text(text)
    except Exception:
        try:
            await callback.message.answer(text)
        except Exception:
            logger.exception(
                "Storage recreate xabarini yangilab bo'lmadi."
            )


# ============================================================
# "✅ Ha, yangi kanal ochish"
# ============================================================
#
# MUHIM: bu handler Auto Reply VA First Message flow'larining
# ikkalasi uchun ham UMUMIY — qaysi FSM holatiga qaytish
# kerakligi `resolve_storage_channel_or_prompt()` tomonidan
# `state`ga oldindan yozilgan `storage_return_state` orqali
# aniqlanadi (spec 13-bo'lim: "Bitta markaziy Storage Channel
# Service ishlatsin").

@router.callback_query(F.data == "storage:recreate:confirm")
async def storage_recreate_confirm(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            await callback.answer(
                "❌ Foydalanuvchi topilmadi.",
                show_alert=True,
            )
            return

        account = await get_connected_telegram_account(
            session,
            user.id,
        )

        if account is None:
            await callback.answer(
                "❌ Telegram akkaunt topilmadi.",
                show_alert=True,
            )
            return

        db_user_id = user.id
        telegram_account_id = account.id

    channel = await recreate_user_storage_channel(
        telegram_id=telegram_id,
        db_user_id=db_user_id,
        telegram_account_id=telegram_account_id,
        bot=callback.bot,
    )

    if channel is None:
        await callback.answer()
        await state.clear()
        await _safe_edit(callback, STORAGE_RECREATE_FAILED_TEXT)
        return

    data = await state.get_data()
    return_state = data.get("storage_return_state")

    if return_state:
        await state.set_state(return_state)

    logger.info(
        "Storage channel qayta ochildi: account_id=%s",
        telegram_account_id,
    )

    await callback.answer("✅")
    await _safe_edit(callback, STORAGE_RECREATED_TEXT)


# ============================================================
# "❌ Yo'q"
# ============================================================

@router.callback_query(F.data == "storage:recreate:cancel")
async def storage_recreate_cancel(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    await callback.answer("❌ Bekor qilindi.")
    await _safe_edit(callback, STORAGE_RECREATE_CANCELLED_TEXT)


__all__ = [
    "router",
]
