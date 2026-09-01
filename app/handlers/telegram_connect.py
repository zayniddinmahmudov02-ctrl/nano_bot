from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select

from telethon.errors import (
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)

from app.database import AsyncSessionLocal
from app.database.models import TelegramAccount
from app.keyboards.main import main_menu_keyboard
from app.keyboards.telegram import telegram_menu_keyboard
from app.services.user_service import get_user_by_telegram_id
from app.telegram.user_client import telegram_client_manager


logger = logging.getLogger(__name__)

router = Router()


# =========================================================
# STATES
# =========================================================

class TelegramConnectStates(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    waiting_password = State()


# =========================================================
# TELEGRAM CONNECT MENU
# =========================================================

@router.message(F.text == "📱 Telegram ulash")
async def telegram_connect_menu(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    if message.from_user is None:
        return

    telegram_id = int(message.from_user.id)

    connected = await get_connection_status(
        telegram_id
    )

    if connected:
        await message.answer(
            "📱 <b>Telegram akkaunt</b>\n\n"
            "✅ Telegram akkauntingiz ulangan.\n\n"
            "Ulangan akkaunt orqali Nano-Bot "
            "avtomatik javoblarni boshqarishi mumkin.",
            reply_markup=telegram_menu_keyboard(
                connected=True
            ),
        )
        return

    await message.answer(
        "📱 <b>Telegram ulash</b>\n\n"
        "Shaxsiy Telegram akkauntingizni "
        "Nano-Botga ulang.\n\n"
        "Ulash uchun telefon raqamingizni "
        "xalqaro formatda yuboring.\n\n"
        "Masalan:\n"
        "<code>+998901234567</code>",
        reply_markup=telegram_menu_keyboard(
            connected=False
        ),
    )

    await state.set_state(
        TelegramConnectStates.waiting_phone
    )


# =========================================================
# DISCONNECT
# =========================================================

@router.message(F.text == "🔌 Telegramni uzish")
async def telegram_disconnect(
    message: Message,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return

    telegram_id = int(message.from_user.id)

    try:
        await telegram_client_manager.logout(
            telegram_id
        )

        async with AsyncSessionLocal() as session:
            user = await get_user_by_telegram_id(
                session,
                telegram_id,
            )

            if user:
                result = await session.execute(
                    select(TelegramAccount).where(
                        TelegramAccount.user_id == user.id
                    )
                )

                account = result.scalar_one_or_none()

                if account:
                    account.is_connected = False
                    account.status = "disconnected"

                    await session.commit()

        await state.clear()

        await message.answer(
            "🔌 <b>Telegram uzildi.</b>\n\n"
            "Telegram akkauntingiz Nano-Botdan "
            "uzildi.",
            reply_markup=main_menu_keyboard(),
        )

    except Exception:
        logger.exception(
            "Telegram disconnect xatosi: telegram_id=%s",
            telegram_id,
        )

        await message.answer(
            "❌ Telegram akkauntini uzishda "
            "xatolik yuz berdi."
        )


# =========================================================
# STATUS
# =========================================================

@router.message(F.text == "🔄 Holatni tekshirish")
async def telegram_status(
    message: Message,
) -> None:
    if message.from_user is None:
        return

    telegram_id = int(message.from_user.id)

    try:
        connected = await get_connection_status(
            telegram_id
        )

        if not connected:
            await message.answer(
                "❌ Telegram akkaunt ulanmagan.",
                reply_markup=telegram_menu_keyboard(
                    connected=False
                ),
            )
            return

        me = await telegram_client_manager.get_me(
            telegram_id
        )

        if me:
            username = (
                f"@{me.username}"
                if me.username
                else "Username yo‘q"
            )

            name = (
                me.first_name
                or "Telegram"
            )

            await message.answer(
                "📱 <b>Telegram holati</b>\n\n"
                "🟢 Holat: <b>Ulangan</b>\n"
                f"👤 Ism: <b>{name}</b>\n"
                f"🔗 Username: <b>{username}</b>\n"
                f"🆔 ID: <code>{me.id}</code>",
                reply_markup=telegram_menu_keyboard(
                    connected=True
                ),
            )
            return

        await message.answer(
            "⚠️ Session mavjud, lekin Telegram "
            "akkauntiga ulanishni tekshirib bo‘lmadi.",
            reply_markup=telegram_menu_keyboard(
                connected=False
            ),
        )

    except Exception:
        logger.exception(
            "Telegram status xatosi: telegram_id=%s",
            telegram_id,
        )

        await message.answer(
            "❌ Telegram holatini tekshirishda "
            "xatolik yuz berdi."
        )


# =========================================================
# CANCEL PHONE
# =========================================================

@router.message(
    TelegramConnectStates.waiting_phone,
    F.text == "❌ Bekor qilish",
)
async def cancel_phone(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "❌ Telegram ulash bekor qilindi.",
        reply_markup=main_menu_keyboard(),
    )


# =========================================================
# RECEIVE PHONE
# =========================================================

@router.message(
    TelegramConnectStates.waiting_phone,
    F.text,
)
async def receive_phone(
    message: Message,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return

    phone = message.text.strip()

    # -----------------------------------------------------
    # VALIDATE PHONE
    # -----------------------------------------------------

    if not phone.startswith("+"):
        await message.answer(
            "❌ Telefon raqami <code>+</code> bilan "
            "boshlanishi kerak.\n\n"
            "Masalan:\n"
            "<code>+998901234567</code>"
        )
        return

    if not phone[1:].isdigit():
        await message.answer(
            "❌ Telefon raqami noto‘g‘ri.\n\n"
            "Faqat raqam kiriting."
        )
        return

    if len(phone) < 8:
        await message.answer(
            "❌ Telefon raqami juda qisqa."
        )
        return

    telegram_id = int(message.from_user.id)

    await message.answer(
        "⏳ <b>Telegram kodi yuborilmoqda...</b>"
    )

    # -----------------------------------------------------
    # START TELEGRAM LOGIN
    # -----------------------------------------------------

    try:
        result = (
            await telegram_client_manager
            .start_phone_login(
                telegram_id=telegram_id,
                phone=phone,
            )
        )

        if not result:
            logger.error(
                "Telegram login boshlanmadi: telegram_id=%s",
                telegram_id,
            )

            await message.answer(
                "❌ Telegram login jarayonini "
                "boshlab bo‘lmadi."
            )
            return

        # -------------------------------------------------
        # SAVE FSM DATA
        # -------------------------------------------------

        await state.update_data(
            phone=phone,
        )

        await state.set_state(
            TelegramConnectStates.waiting_code
        )

        await message.answer(
            "📩 <b>Kod yuborildi.</b>\n\n"
            "Telegram ilovangizga kelgan "
            "login kodini yuboring.\n\n"
            "Masalan:\n"
            "<code>12345</code>\n\n"
            "⚠️ Kodni hech kimga yubormang."
        )

    except FloodWaitError as error:
        seconds = int(error.seconds)

        await message.answer(
            "⏳ Juda ko‘p urinish.\n\n"
            f"{seconds} soniyadan keyin "
            "qayta urinib ko‘ring."
        )

    except Exception:
        logger.exception(
            "Telegram phone login xatosi: telegram_id=%s",
            telegram_id,
        )

        await message.answer(
            "❌ Telegram kodini yuborishda "
            "xatolik yuz berdi.\n\n"
            "Telefon raqamingizni tekshiring "
            "va qayta urinib ko‘ring."
        )


# =========================================================
# CANCEL CODE
# =========================================================

@router.message(
    TelegramConnectStates.waiting_code,
    F.text == "❌ Bekor qilish",
)
async def cancel_code(
    message: Message,
    state: FSMContext,
) -> None:
    if message.from_user is not None:
        telegram_id = int(message.from_user.id)

        try:
            await telegram_client_manager.logout(
                telegram_id
            )
        except Exception:
            logger.exception(
                "Pending Telegram login cleanup failed"
            )

    await state.clear()

    await message.answer(
        "❌ Telegram ulash bekor qilindi.",
        reply_markup=main_menu_keyboard(),
    )


# =========================================================
# RECEIVE CODE
# =========================================================

@router.message(
    TelegramConnectStates.waiting_code,
    F.text,
)
async def receive_code(
    message: Message,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return

    code = message.text.strip()

    # -----------------------------------------------------
    # VALIDATE CODE
    # -----------------------------------------------------

    if not code.isdigit():
        await message.answer(
            "❌ Kod faqat raqamlardan iborat bo‘lishi kerak."
        )
        return

    if len(code) < 4 or len(code) > 8:
        await message.answer(
            "❌ Login kodi noto‘g‘ri.\n\n"
            "Telegram yuborgan kodni to‘liq kiriting."
        )
        return

    telegram_id = int(message.from_user.id)

    await message.answer(
        "⏳ <b>Kod tekshirilmoqda...</b>"
    )

    # -----------------------------------------------------
    # SIGN IN
    # -----------------------------------------------------

    try:
        success = (
            await telegram_client_manager
            .sign_in_code(
                telegram_id=telegram_id,
                code=code,
            )
        )

        if success:
            await save_connected_account(
                telegram_id=telegram_id,
            )

            await state.clear()

            await message.answer(
                "✅ <b>Telegram akkaunt muvaffaqiyatli ulandi!</b>\n\n"
                "Endi Nano-Bot ulangan Telegram "
                "akkauntingiz bilan ishlashi mumkin.",
                reply_markup=main_menu_keyboard(),
            )
            return

    except SessionPasswordNeededError:
        await state.set_state(
            TelegramConnectStates.waiting_password
        )

        await message.answer(
            "🔐 <b>2FA parol kerak.</b>\n\n"
            "Telegram akkauntingizda "
            "ikki bosqichli himoya yoqilgan.\n\n"
            "Iltimos, 2FA parolingizni yuboring."
        )
        return

    except PhoneCodeInvalidError:
        await message.answer(
            "❌ <b>Kod noto‘g‘ri.</b>\n\n"
            "Telegram yuborgan kodni qayta tekshiring "
            "va yana yuboring."
        )
        return

    except PhoneCodeExpiredError:
        await state.clear()

        await message.answer(
            "⌛ <b>Kodning amal qilish muddati tugagan.</b>\n\n"
            "Iltimos, Telegram ulash jarayonini "
            "qaytadan boshlang.",
            reply_markup=main_menu_keyboard(),
        )
        return

    except Exception:
        logger.exception(
            "Telegram code login xatosi: telegram_id=%s",
            telegram_id,
        )

        await message.answer(
            "❌ Telegram kodini tekshirishda "
            "xatolik yuz berdi."
        )


# =========================================================
# CANCEL PASSWORD
# =========================================================

@router.message(
    TelegramConnectStates.waiting_password,
    F.text == "❌ Bekor qilish",
)
async def cancel_password(
    message: Message,
    state: FSMContext,
) -> None:
    if message.from_user is not None:
        telegram_id = int(message.from_user.id)

        try:
            await telegram_client_manager.logout(
                telegram_id
            )
        except Exception:
            logger.exception(
                "2FA login cleanup failed"
            )

    await state.clear()

    await message.answer(
        "❌ Telegram ulash bekor qilindi.",
        reply_markup=main_menu_keyboard(),
    )


# =========================================================
# RECEIVE 2FA PASSWORD
# =========================================================

@router.message(
    TelegramConnectStates.waiting_password,
    F.text,
)
async def receive_password(
    message: Message,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return

    password = message.text.strip()

    if not password:
        await message.answer(
            "❌ Parol bo‘sh bo‘lishi mumkin emas."
        )
        return

    telegram_id = int(message.from_user.id)

    await message.answer(
        "⏳ <b>2FA parol tekshirilmoqda...</b>"
    )

    try:
        success = (
            await telegram_client_manager
            .sign_in_password(
                telegram_id=telegram_id,
                password=password,
            )
        )

        if success:
            await save_connected_account(
                telegram_id=telegram_id,
            )

            await state.clear()

            await message.answer(
                "✅ <b>Telegram akkaunt muvaffaqiyatli ulandi!</b>\n\n"
                "2FA tekshiruvi muvaffaqiyatli yakunlandi.\n\n"
                "Nano-Bot endi ulangan Telegram "
                "akkauntingiz bilan ishlashi mumkin.",
                reply_markup=main_menu_keyboard(),
            )
            return

        await message.answer(
            "❌ Telegram akkauntini ulashning "
            "iloji bo‘lmadi."
        )

    except Exception:
        logger.exception(
            "Telegram 2FA login xatosi: telegram_id=%s",
            telegram_id,
        )

        await message.answer(
            "❌ 2FA parolini tekshirishda "
            "xatolik yuz berdi.\n\n"
            "Parolni qayta tekshirib yuboring."
        )


# =========================================================
# SAVE CONNECTED ACCOUNT
# =========================================================

async def save_connected_account(
    telegram_id: int,
) -> bool:
    """
    Ulangan Telegram akkauntini PostgreSQL bazaga saqlaydi.

    Muhim:
    telegram_id -> users.telegram_id
    TelegramAccount.user_id -> users.id
    """

    telegram_id = int(telegram_id)

    try:
        me = await telegram_client_manager.get_me(
            telegram_id
        )

        if me is None:
            logger.error(
                "Connected Telegram user topilmadi: telegram_id=%s",
                telegram_id,
            )
            return False

        async with AsyncSessionLocal() as session:

            # -------------------------------------------------
            # INTERNAL USER
            # -------------------------------------------------

            user = await get_user_by_telegram_id(
                session,
                telegram_id,
            )

            if user is None:
                logger.error(
                    "Internal User topilmadi: telegram_id=%s",
                    telegram_id,
                )
                return False

            # -------------------------------------------------
            # TELEGRAM ACCOUNT
            # -------------------------------------------------

            result = await session.execute(
                select(TelegramAccount).where(
                    TelegramAccount.user_id == user.id
                )
            )

            account = result.scalar_one_or_none()

            username = (
                me.username
                if me.username
                else None
            )

            if account is None:
                account = TelegramAccount(
                    user_id=user.id,
                    telegram_id=int(me.id),
                    phone=None,
                    username=username,
                    session_name=f"{telegram_id}",
                    status="connected",
                    auto_reply_enabled=True,
                    is_connected=True,
                )

                session.add(account)

            else:
                account.telegram_id = int(me.id)
                account.username = username
                account.status = "connected"
                account.is_connected = True

                if not account.session_name:
                    account.session_name = f"{telegram_id}"

            await session.commit()

            logger.info(
                "Telegram account saved: user_id=%s telegram_id=%s",
                user.id,
                me.id,
            )

            return True

    except Exception:
        logger.exception(
            "Failed to save connected Telegram account: "
            "telegram_id=%s",
            telegram_id,
        )
        return False


# =========================================================
# CONNECTION STATUS
# =========================================================

async def get_connection_status(
    telegram_id: int,
) -> bool:
    """
    Telegram akkauntining ulanish holatini tekshiradi.

    Avval active Telethon session tekshiriladi,
    keyin database holati tekshiriladi.
    """

    telegram_id = int(telegram_id)

    # ---------------------------------------------------------
    # TELETHON SESSION
    # ---------------------------------------------------------

    try:
        authorized = (
            await telegram_client_manager
            .is_authorized(
                telegram_id
            )
        )

        if authorized:
            return True

    except Exception:
        logger.exception(
            "Telethon authorization check failed: "
            "telegram_id=%s",
            telegram_id,
        )

    # ---------------------------------------------------------
    # DATABASE
    # ---------------------------------------------------------

    try:
        async with AsyncSessionLocal() as session:

            user = await get_user_by_telegram_id(
                session,
                telegram_id,
            )

            if user is None:
                return False

            result = await session.execute(
                select(TelegramAccount).where(
                    TelegramAccount.user_id == user.id
                )
            )

            account = result.scalar_one_or_none()

            if account is None:
                return False

            return bool(
                account.is_connected
                and account.status == "connected"
            )

    except Exception:
        logger.exception(
            "Database connection status check failed: "
            "telegram_id=%s",
            telegram_id,
        )

        return False


# =========================================================
# EXPORTS
# =========================================================

__all__ = [
    "router",
    "TelegramConnectStates",
    "telegram_connect_menu",
    "telegram_disconnect",
    "telegram_status",
    "receive_phone",
    "receive_code",
    "receive_password",
    "save_connected_account",
    "get_connection_status",
]