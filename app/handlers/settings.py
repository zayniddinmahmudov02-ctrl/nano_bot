import logging
import re
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import Subscription, User
from app.keyboards.nano import (
    nano_language_keyboard,
    nano_password_disable_confirm_keyboard,
    nano_password_enabled_keyboard,
    nano_password_input_cancel_keyboard,
    nano_password_not_set_keyboard,
    nano_premium_keyboard,
    nano_profile_input_cancel_keyboard,
    nano_profile_keyboard,
    nano_settings_menu_keyboard,
)
from app.handlers.language import update_user_language
from app.services.password_service import (
    disable_password,
    set_password,
    validate_password_format,
)
from app.services.user_service import (
    get_or_create_user_settings,
    get_user_by_telegram_id,
    get_user_language,
)
from app.texts import LANGUAGE_LABELS, t

logger = logging.getLogger(__name__)

router = Router()

MAX_NAME_LENGTH = 100

# Boshqaruv belgilari (control characters) — ismdan tozalanadi.
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


class SettingsStates(StatesGroup):
    waiting_name = State()
    waiting_password_set = State()


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
                "Sozlamalar xabarini yangilab bo'lmadi."
            )


# ============================================================
# SETTINGS MENU
# ============================================================

@router.message(Command("settings"))
async def settings_command(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Telegramning pastki Menu panelidan "/settings" tanlanganda
    ishga tushadi.
    """

    await state.clear()

    if message.from_user is None:
        return

    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    await message.answer(
        t("settings_menu_title", lang),
        reply_markup=nano_settings_menu_keyboard(lang),
    )


@router.callback_query(F.data == "nano:settings")
async def nano_settings_menu(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
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
        t("settings_menu_title", lang),
        nano_settings_menu_keyboard(lang),
    )


# ============================================================
# LANGUAGE
# ============================================================

@router.callback_query(F.data == "nano:settings:language")
async def nano_settings_language(
    callback: CallbackQuery,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    await callback.answer()

    await _safe_edit(
        callback,
        t("language_menu_title", lang),
        nano_language_keyboard(lang),
    )


@router.callback_query(
    F.data.startswith("nano:settings:language:set:")
)
async def nano_settings_language_set(
    callback: CallbackQuery,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    new_lang = callback.data.split(":")[-1]

    if new_lang not in LANGUAGE_LABELS:
        await callback.answer(
            "❌ Noto'g'ri tanlov.",
            show_alert=True,
        )
        return

    telegram_id = int(callback.from_user.id)

    success = await update_user_language(
        telegram_id=telegram_id,
        language=new_lang,
    )

    if not success:
        await callback.answer(
            "❌ Foydalanuvchi topilmadi.",
            show_alert=True,
        )
        return

    await callback.answer("✅")

    await _safe_edit(
        callback,
        f"{t('language_updated', new_lang)}\n\n"
        f"{t('settings_menu_title', new_lang)}",
        nano_settings_menu_keyboard(new_lang),
    )


# ============================================================
# PREMIUM
# ============================================================

@router.callback_query(F.data == "nano:settings:premium")
async def nano_settings_premium(
    callback: CallbackQuery,
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

        lang = await get_user_language(session, telegram_id)

        if user is None:
            await callback.answer(
                "❌ Foydalanuvchi topilmadi.",
                show_alert=True,
            )
            return

        result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id
            )
        )

        subscription = result.scalar_one_or_none()

        is_active_premium = bool(
            subscription
            and subscription.status == "premium"
            and (
                subscription.premium_expires_at is None
                or subscription.premium_expires_at
                > datetime.now(timezone.utc)
            )
        )

    await callback.answer()

    status_text = (
        t("premium_status_active", lang)
        if is_active_premium
        else t("premium_status_free", lang)
    )

    await _safe_edit(
        callback,
        f"{t('premium_title', lang)}\n\n{status_text}",
        nano_premium_keyboard(lang),
    )


# ============================================================
# PERSONAL DATA
# ============================================================

def _clean_name(raw_name: str) -> str:
    cleaned = _CONTROL_CHAR_PATTERN.sub("", raw_name)
    return cleaned.strip()


async def _render_profile_text(user: User, lang: str) -> str:
    registered = user.created_at.strftime("%d.%m.%Y")

    return (
        f"{t('profile_title', lang)}\n\n"
        f"Ism:\n{user.first_name or '—'}\n\n"
        f"Telegram ID:\n<code>{user.telegram_id}</code>\n\n"
        f"Ro'yxatdan o'tgan:\n{registered}"
    )


@router.callback_query(F.data == "nano:settings:profile")
async def nano_settings_profile(
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

        text = await _render_profile_text(user, lang)

    await callback.answer()

    await _safe_edit(
        callback,
        text,
        nano_profile_keyboard(lang),
    )


@router.callback_query(
    F.data == "nano:settings:profile:edit_name"
)
async def nano_edit_name_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    await state.set_state(SettingsStates.waiting_name)

    await callback.answer()

    await _safe_edit(
        callback,
        t("edit_name_prompt", lang),
        nano_profile_input_cancel_keyboard(lang),
    )


@router.message(SettingsStates.waiting_name)
async def receive_new_name(
    message: Message,
    state: FSMContext,
) -> None:
    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    if not message.text:
        await message.answer(t("edit_name_empty", lang))
        return

    new_name = _clean_name(message.text)

    if not new_name:
        await message.answer(t("edit_name_empty", lang))
        return

    if len(new_name) > MAX_NAME_LENGTH:
        await message.answer(t("edit_name_too_long", lang))
        return

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            await state.clear()

            await message.answer(t("user_not_found", lang))
            return

        user.first_name = new_name

        await session.commit()

        profile_text = await _render_profile_text(user, lang)

    await state.clear()

    await message.answer(t("edit_name_success", lang))

    await message.answer(
        profile_text,
        reply_markup=nano_profile_keyboard(lang),
    )


# ============================================================
# BOT PASSWORD (21/13-bo'limlar)
# ============================================================
#
# MUHIM: bu Telegram akkaunt paroli/OTP/2FA EMAS — faqat
# Nano-Botning o'ziga kirishni himoyalovchi qo'shimcha, foyda-
# lanuvchi ixtiyoriy ravishda yoqadigan parol. Plain text hech
# qachon saqlanmaydi (faqat bcrypt hash) va hech qachon
# logga yozilmaydi.

@router.callback_query(F.data == "nano:settings:password")
async def nano_settings_password(
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

        settings = await get_or_create_user_settings(
            session,
            user.id,
        )

        enabled = bool(settings.password_enabled)

        await session.commit()

    await callback.answer()

    if enabled:
        await _safe_edit(
            callback,
            f"{t('password_title', lang)}\n\n"
            f"{t('password_enabled_status', lang)}",
            nano_password_enabled_keyboard(lang),
        )
        return

    await _safe_edit(
        callback,
        f"{t('password_title', lang)}\n\n"
        f"{t('password_not_set_description', lang)}",
        nano_password_not_set_keyboard(lang),
    )


@router.callback_query(F.data == "nano:settings:password:set")
async def nano_password_set_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    await state.set_state(SettingsStates.waiting_password_set)

    await callback.answer()

    await _safe_edit(
        callback,
        t("password_set_prompt", lang),
        nano_password_input_cancel_keyboard(lang),
    )


@router.message(SettingsStates.waiting_password_set)
async def receive_new_password(
    message: Message,
    state: FSMContext,
) -> None:
    telegram_id = int(message.from_user.id)

    # Foydalanuvchi yuborgan parol matnini chatdan darhol
    # tozalashga harakat qilamiz (maxfiylik uchun).
    try:
        await message.delete()
    except Exception:
        pass

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    if not message.text:
        await message.answer(
            "❌ Parolni matn ko'rinishida kiriting."
        )
        return

    plain_password = message.text.strip()

    format_error = validate_password_format(plain_password)

    if format_error:
        await message.answer(format_error)
        return

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            await state.clear()

            await message.answer(t("user_not_found", lang))
            return

        db_user_id = user.id

    # MUHIM: parol hech qachon logga yozilmaydi.
    await set_password(db_user_id, plain_password)

    await state.clear()

    await message.answer(
        t("password_set_success", lang),
        reply_markup=nano_password_enabled_keyboard(lang),
    )

    logger.info(
        "Bot password set: telegram_id=%s",
        telegram_id,
    )


@router.callback_query(
    F.data == "nano:settings:password:disable:ask"
)
async def nano_password_disable_ask(
    callback: CallbackQuery,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    await callback.answer()

    await _safe_edit(
        callback,
        "⚠️ Bot paroli himoyasini o'chirishni xohlaysizmi?",
        nano_password_disable_confirm_keyboard(lang),
    )


@router.callback_query(
    F.data == "nano:settings:password:disable:no"
)
async def nano_password_disable_no(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await callback.answer("❌ Bekor qilindi.")

    await nano_settings_password(callback, state)


@router.callback_query(
    F.data == "nano:settings:password:disable:yes"
)
async def nano_password_disable_yes(
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

        db_user_id = user.id

    await disable_password(db_user_id)

    logger.info(
        "Bot password disabled: telegram_id=%s",
        telegram_id,
    )

    await callback.answer("✅")

    await _safe_edit(
        callback,
        f"{t('password_title', lang)}\n\n"
        f"{t('password_disabled_success', lang)}",
        nano_password_not_set_keyboard(lang),
    )


__all__ = [
    "router",
    "SettingsStates",
]
