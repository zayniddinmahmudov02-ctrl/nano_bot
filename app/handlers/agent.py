import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.database import AsyncSessionLocal
from app.handlers.auto_replies import _render_list
from app.keyboards.auto_reply import auto_reply_list_inline_keyboard
from app.keyboards.nano import nano_agent_menu_keyboard, nano_stats_keyboard
from app.services.user_service import (
    get_user_by_telegram_id,
    get_user_language,
)
from app.services.user_stats_service import get_user_statistics
from app.texts import t

logger = logging.getLogger(__name__)

router = Router()


async def _safe_edit(
    callback: CallbackQuery,
    text: str,
    reply_markup,
) -> None:
    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
        )
    except Exception:
        try:
            await callback.message.answer(
                text,
                reply_markup=reply_markup,
            )
        except Exception:
            logger.exception(
                "Nano-Agent xabarini yangilab bo'lmadi."
            )


@router.message(Command("agent"))
async def agent_command(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Telegramning pastki Menu panelidan "/agent" tanlanganda
    ishga tushadi — Nano-Agent bo'limi YANGI xabar sifatida
    ochiladi (chat ichida katta doimiy inline bosh menyu yo'q).
    """

    await state.clear()

    if message.from_user is None:
        return

    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    await message.answer(
        t("agent_menu_title", lang),
        reply_markup=nano_agent_menu_keyboard(lang),
    )


@router.callback_query(F.data == "nano:agent")
async def nano_agent_menu(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Nano-Agent'ning ICHKI (nested) sahifalaridan "⬅️ Orqaga"
    bosilganda shu Nano-Agent kartasiga qaytariladi — bu ICHKI
    inline navigatsiya, asosiy 5 bo'limlik menyu emas.
    """

    await state.clear()

    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    await callback.answer()

    await _safe_edit(
        callback,
        t("agent_menu_title", lang),
        nano_agent_menu_keyboard(lang),
    )


# ============================================================
# AVTO XABAR — mavjud (allaqachon inline) ro'yxatga kirish
# ============================================================

@router.callback_query(F.data == "nano:agent:auto")
async def nano_agent_auto(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

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

        text, indexed_ids = await _render_list(
            session,
            user.id,
        )

    await callback.answer()

    keyboard = auto_reply_list_inline_keyboard(
        indexed_ids or []
    )

    await _safe_edit(callback, text, keyboard)


# ============================================================
# STATISTIKALAR
# ============================================================

@router.callback_query(F.data == "nano:agent:stats")
async def nano_agent_stats(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        lang = await get_user_language(session, telegram_id)

        if user is None:
            await callback.answer(
                "❌ Foydalanuvchi topilmadi.",
                show_alert=True,
            )
            return

        stats = await get_user_statistics(session, user.id)

    await callback.answer()

    text = (
        f"{t('stats_title', lang)}\n\n"
        f"👥 Javob berilgan odamlar: "
        f"<b>{stats.replied_people}</b>\n"
        f"🤖 Auto Reply yuborilgan: "
        f"<b>{stats.auto_replies_total}</b>\n"
        f"1️⃣ First Message yuborilgan: "
        f"<b>{stats.first_messages_total}</b>\n\n"
        f"{t('stats_period_today', lang)}: "
        f"🤖 {stats.auto_replies_today} · "
        f"1️⃣ {stats.first_messages_today}\n"
        f"{t('stats_period_7d', lang)}: "
        f"🤖 {stats.auto_replies_7d} · "
        f"1️⃣ {stats.first_messages_7d}\n"
        f"{t('stats_period_30d', lang)}: "
        f"🤖 {stats.auto_replies_30d} · "
        f"1️⃣ {stats.first_messages_30d}\n"
        f"{t('stats_period_all', lang)}: "
        f"🤖 {stats.auto_replies_total} · "
        f"1️⃣ {stats.first_messages_total}"
    )

    await _safe_edit(
        callback,
        text,
        nano_stats_keyboard(lang),
    )


__all__ = [
    "router",
]
