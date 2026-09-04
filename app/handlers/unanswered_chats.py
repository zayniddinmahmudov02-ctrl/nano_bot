from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.database import AsyncSessionLocal
from app.keyboards.nano import (
    nano_agent_menu_keyboard,
    nano_unanswered_list_keyboard,
)
from app.services.access_guard import guard_callback_access
from app.services.unanswered_chat_service import get_unanswered_page
from app.services.user_service import (
    get_connected_telegram_account,
    get_user_by_telegram_id,
    get_user_language,
)
from app.texts import t

logger = logging.getLogger(__name__)

router = Router()

PAGE_SIZE = 10

# Rang-kodlangan holat chegaralari — spec 3-bo'lim namunasiga
# aniq mos: 🔴 3 kun 4 soat, 🟠 2 kun 7 soat, 🟡 5 soat.
# Demak: 🔴 >= 3 kun (72 soat), 🟠 >= 1 kun (24 soat), 🟡 < 24 soat.
_RED_THRESHOLD_HOURS = 72
_ORANGE_THRESHOLD_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _status_emoji(waiting_hours: float) -> str:
    if waiting_hours >= _RED_THRESHOLD_HOURS:
        return "🔴"

    if waiting_hours >= _ORANGE_THRESHOLD_HOURS:
        return "🟠"

    return "🟡"


def _format_duration(waiting_since: datetime, lang: str) -> str:
    delta = _now() - waiting_since

    total_hours = max(0, int(delta.total_seconds() // 3600))
    days, hours = divmod(total_hours, 24)

    if days > 0:
        return t(
            "duration_days_hours",
            lang,
            days=days,
            hours=hours,
        )

    return t("duration_hours_only", lang, hours=hours)


def _display_name(peer_name, peer_username, peer_id: int) -> str:
    if peer_name:
        return peer_name

    if peer_username:
        return f"@{peer_username}"

    return f"ID {peer_id}"


async def _render_list_text(
    telegram_account_id: int,
    page: int,
    lang: str,
):
    items, total, total_pages, page = await get_unanswered_page(
        telegram_account_id,
        page,
        PAGE_SIZE,
    )

    if not items:
        text = (
            f"{t('unanswered_list_title', lang)}\n\n"
            f"{t('unanswered_list_empty', lang)}"
        )
        return text, items, page, total_pages

    lines = [t("unanswered_list_title", lang), ""]

    for item in items:
        waiting_hours = (
            _now() - item.waiting_since
        ).total_seconds() / 3600

        lines.append(
            t(
                "unanswered_item_line",
                lang,
                emoji=_status_emoji(waiting_hours),
                duration=_format_duration(
                    item.waiting_since, lang
                ),
                name=_display_name(
                    item.peer_name,
                    item.peer_username,
                    item.peer_id,
                ),
            )
        )
        lines.append("")

    lines.append(t("unanswered_list_hint", lang))

    return "\n".join(lines), items, page, total_pages


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
                "Javob berilmagan chatlar xabarini yangilab "
                "bo'lmadi."
            )


async def _resolve_account(telegram_id: int):
    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        lang = await get_user_language(session, telegram_id)

        if user is None:
            return None, None, lang

        account = await get_connected_telegram_account(
            session,
            user.id,
        )

        return user, account, lang


# ============================================================
# LIST (page 1 — Nano-Agent ichidan kirish)
# ============================================================

@router.callback_query(F.data == "nano:agent:unanswered")
async def nano_unanswered_list(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    _user, account, lang = await _resolve_account(telegram_id)

    if not await guard_callback_access(callback, lang):
        return

    if account is None:
        await callback.answer()

        await _safe_edit(
            callback,
            t("unanswered_list_empty", lang),
            nano_agent_menu_keyboard(lang),
        )
        return

    text, items, page, total_pages = await _render_list_text(
        account.id,
        1,
        lang,
    )

    await callback.answer()

    await _safe_edit(
        callback,
        text,
        nano_unanswered_list_keyboard(
            items,
            page,
            total_pages,
            lang,
        ),
    )


@router.callback_query(
    F.data.startswith("nano:agent:unanswered:page:")
)
async def nano_unanswered_page(
    callback: CallbackQuery,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    try:
        page = int(callback.data.split(":")[-1])
    except ValueError:
        page = 1

    telegram_id = int(callback.from_user.id)

    _user, account, lang = await _resolve_account(telegram_id)

    if not await guard_callback_access(callback, lang):
        return

    if account is None:
        await callback.answer()
        return

    text, items, page, total_pages = await _render_list_text(
        account.id,
        page,
        lang,
    )

    await callback.answer()

    await _safe_edit(
        callback,
        text,
        nano_unanswered_list_keyboard(
            items,
            page,
            total_pages,
            lang,
        ),
    )


@router.callback_query(
    F.data.startswith("nano:agent:unanswered:nolink:")
)
async def nano_unanswered_nolink(
    callback: CallbackQuery,
) -> None:
    """
    MUHIM (spec 5-bo'lim): username'i yo'q peer uchun soxta URL
    yaratilmaydi — buning o'rniga aniq, halol tushuntirish
    alert ko'rinishida ko'rsatiladi.
    """

    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    await callback.answer(
        t("unanswered_nolink_alert", lang),
        show_alert=True,
    )


@router.callback_query(F.data == "nano:noop")
async def nano_noop(callback: CallbackQuery) -> None:
    await callback.answer()


__all__ = [
    "router",
]
