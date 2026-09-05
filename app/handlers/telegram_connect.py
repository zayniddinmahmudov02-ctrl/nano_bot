from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
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
from app.services.auto_reply_engine import auto_reply_engine
from app.services.first_message_engine import first_message_engine
from app.services.storage_channel_service import ensure_storage_channel
from app.services.terms_service import (
    TERMS_GATE_TEXT,
    TERMS_PAGE_COUNT,
    get_terms_page,
    has_accepted_terms,
    record_terms_acceptance,
)
from app.services.user_service import (
    get_connected_telegram_account,
    get_user_by_telegram_id,
)
from app.telegram.user_client import telegram_client_manager


logger = logging.getLogger(__name__)

router = Router()


class TelegramConnectStates(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    waiting_password = State()


# ============================================================
# TELEGRAM ULASH MENYUSI
# ============================================================

@router.message(F.text == "📱 Telegram ulash")
async def telegram_connect_menu(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    if message.from_user is None:
        return

    telegram_id = int(message.from_user.id)

    connected = await get_connection_status(telegram_id)

    if connected:
        await message.answer(
            "📱 <b>Telegram akkaunt</b>\n\n"
            "✅ Telegram akkauntingiz ulangan.\n\n"
            "Ulangan akkaunt orqali Nano-Bot "
            "avtomatik javoblarni boshqarishi mumkin.",
            reply_markup=telegram_menu_keyboard(connected=True),
        )
        return

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            await message.answer(
                "❌ Foydalanuvchi topilmadi.\n\n"
                "Iltimos, /start buyrug‘ini bosing.",
                reply_markup=main_menu_keyboard(),
            )
            return

        db_user_id = user.id

    accepted = await has_accepted_terms(db_user_id)

    if accepted:
        await _start_phone_prompt(message, state)
        return

    await message.answer(
        TERMS_GATE_TEXT,
        reply_markup=_terms_gate_keyboard(),
    )


# ============================================================
# SHARTNOMA (TERMS OF USE)
# ============================================================

def _terms_gate_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📄 Shartlarni ko‘rish",
                    callback_data="terms:view",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✅ Qabul qilaman",
                    callback_data="terms:accept",
                ),
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data="terms:cancel",
                ),
            ],
        ]
    )


def _terms_page_keyboard(index: int) -> InlineKeyboardMarkup:
    nav_row = []

    if index > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="◀️ Oldingi",
                callback_data=f"terms:page:{index - 1}",
            )
        )

    if index < TERMS_PAGE_COUNT - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="Keyingi ▶️",
                callback_data=f"terms:page:{index + 1}",
            )
        )

    rows = []

    if nav_row:
        rows.append(nav_row)

    rows.append(
        [
            InlineKeyboardButton(
                text="✅ Qabul qilaman",
                callback_data="terms:accept",
            ),
            InlineKeyboardButton(
                text="❌ Bekor qilish",
                callback_data="terms:cancel",
            ),
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(
                text="◀️ Orqaga",
                callback_data="terms:back",
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _telegram_input_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    Telefon/kod/2FA parol kiritish bosqichlarida ko'rsatiladigan
    yagona inline "Bekor qilish" tugmasi — ReplyKeyboard o'rniga.
    """

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data="nano:agent:telegram:cancel",
                ),
            ],
        ]
    )


async def _start_phone_prompt(
    message,
    state: FSMContext,
) -> None:
    await message.answer(
        "📱 <b>Telegram ulash</b>\n\n"
        "Shaxsiy Telegram akkauntingizni Nano-Botga ulang.\n\n"
        "Ulash uchun telefon raqamingizni xalqaro formatda "
        "yuboring.\n\n"
        "Masalan:\n"
        "<code>+998901234567</code>",
        reply_markup=_telegram_input_cancel_keyboard(),
    )

    await state.set_state(TelegramConnectStates.waiting_phone)


@router.callback_query(F.data == "terms:view")
async def terms_view(callback: CallbackQuery) -> None:
    await callback.answer()

    try:
        await callback.message.edit_text(
            get_terms_page(0),
            reply_markup=_terms_page_keyboard(0),
        )
    except Exception:
        await callback.message.answer(
            get_terms_page(0),
            reply_markup=_terms_page_keyboard(0),
        )


@router.callback_query(F.data.startswith("terms:page:"))
async def terms_page(callback: CallbackQuery) -> None:
    await callback.answer()

    try:
        index = int(callback.data.split(":")[-1])
    except ValueError:
        index = 0

    try:
        await callback.message.edit_text(
            get_terms_page(index),
            reply_markup=_terms_page_keyboard(index),
        )
    except Exception:
        logger.exception(
            "Terms sahifasini yangilab bo'lmadi."
        )


@router.callback_query(F.data == "terms:back")
async def terms_back(callback: CallbackQuery) -> None:
    await callback.answer()

    try:
        await callback.message.edit_text(
            TERMS_GATE_TEXT,
            reply_markup=_terms_gate_keyboard(),
        )
    except Exception:
        await callback.message.answer(
            TERMS_GATE_TEXT,
            reply_markup=_terms_gate_keyboard(),
        )


@router.callback_query(F.data == "terms:cancel")
async def terms_cancel(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()
    await callback.answer("❌ Bekor qilindi.")

    try:
        await callback.message.edit_text(
            "❌ Telegram ulash bekor qilindi."
        )
    except Exception:
        pass

    await callback.message.answer(
        "🏠 <b>Bosh menyu</b>",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "terms:accept")
async def terms_accept(
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

        db_user_id = user.id

    await record_terms_acceptance(db_user_id)

    await callback.answer("✅ Qabul qilindi.")

    try:
        await callback.message.edit_text(
            "✅ <b>Shartlar qabul qilindi.</b>"
        )
    except Exception:
        pass

    await _start_phone_prompt(callback.message, state)


# ============================================================
# TELEGRAMNI UZISH
# ============================================================

@router.message(F.text == "🔌 Telegramni uzish")
async def telegram_disconnect(
    message: Message,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return

    telegram_id = int(message.from_user.id)

    try:
        await telegram_client_manager.logout(telegram_id)

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
            "Telegram akkauntingiz Nano-Botdan uzildi.",
            reply_markup=main_menu_keyboard(),
        )

    except Exception:
        logger.exception(
            "Telegram disconnect xatosi: telegram_id=%s",
            telegram_id,
        )

        await message.answer(
            "❌ Telegram akkauntini uzishda xatolik yuz berdi."
        )


# ============================================================
# HOLATNI TEKSHIRISH
# ============================================================

@router.message(F.text == "🔄 Holatni tekshirish")
async def telegram_status(message: Message) -> None:
    if message.from_user is None:
        return

    telegram_id = int(message.from_user.id)

    try:
        connected = await get_connection_status(telegram_id)

        if not connected:
            await message.answer(
                "❌ Telegram akkaunt ulanmagan.",
                reply_markup=telegram_menu_keyboard(
                    connected=False
                ),
            )
            return

        me = await telegram_client_manager.get_me(telegram_id)

        if me:
            username = (
                f"@{me.username}"
                if me.username
                else "Username yo‘q"
            )

            name = me.first_name or "Telegram"

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
            "⚠️ Session mavjud, lekin Telegram akkauntiga "
            "ulanishni tekshirib bo‘lmadi.",
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
            "❌ Telegram holatini tekshirishda xatolik yuz berdi."
        )


# ============================================================
# TELEFON RAQAMINI BEKOR QILISH
# ============================================================

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


# ============================================================
# TELEFON RAQAMINI QABUL QILISH
# ============================================================

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

    try:
        result = await telegram_client_manager.start_phone_login(
            telegram_id=telegram_id,
            phone=phone,
        )

        if not result:
            logger.error(
                "Telegram login boshlanmadi: telegram_id=%s",
                telegram_id,
            )

            await message.answer(
                "❌ Telegram login jarayonini boshlab bo‘lmadi."
            )
            return

        await state.update_data(phone=phone)

        await state.set_state(
            TelegramConnectStates.waiting_code
        )

        await message.answer(
            "📩 <b>Kod yuborildi.</b>\n\n"
            "Telegram ilovangizga kelgan login kodini "
            "<b>qo‘lda, raqamlar orasiga bo‘sh joy qo‘yib</b> yuboring.\n\n"
            "Masalan:\n"
            "<code>7 5 8 1 1</code>\n\n"
            "⚠️ <b>Kodni copy-paste qilmang.</b>\n"
            "Har bir raqamni alohida-alohida tering.",
            reply_markup=_telegram_input_cancel_keyboard(),
        )

    except FloodWaitError as error:
        await message.answer(
            "⏳ Juda ko‘p urinish.\n\n"
            f"{int(error.seconds)} soniyadan keyin "
            "qayta urinib ko‘ring."
        )

    except Exception:
        logger.exception(
            "Telegram phone login xatosi: telegram_id=%s",
            telegram_id,
        )

        await message.answer(
            "❌ Telegram kodini yuborishda xatolik yuz berdi.\n\n"
            "Telefon raqamingizni tekshiring va "
            "qayta urinib ko‘ring."
        )


# ============================================================
# KODNI BEKOR QILISH
# ============================================================

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


# ============================================================
# LOGIN KODINI QABUL QILISH
# ============================================================

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

    # Foydalanuvchi:
    # 7 5 8 1 1
    #
    # yuborsa:
    #
    # 75811
    #
    # ko‘rinishiga keltiramiz.

    raw_code = message.text.strip()

    code = "".join(raw_code.split())

    if not code.isdigit():
        await message.answer(
            "❌ <b>Kod noto‘g‘ri.</b>\n\n"
            "Kodni faqat raqamlar bilan kiriting.\n\n"
            "Masalan:\n"
            "<code>7 5 8 1 1</code>"
        )
        return

    if len(code) < 4 or len(code) > 8:
        await message.answer(
            "❌ <b>Login kodi noto‘g‘ri.</b>\n\n"
            "Telegram yuborgan kodni to‘liq kiriting.\n\n"
            "Masalan:\n"
            "<code>7 5 8 1 1</code>"
        )
        return

    telegram_id = int(message.from_user.id)

    await message.answer(
        "⏳ <b>Kod tekshirilmoqda...</b>"
    )

    try:
        success = await telegram_client_manager.sign_in_code(
            telegram_id=telegram_id,
            code=code,
        )

        if success:
            saved = await save_connected_account(
                telegram_id=telegram_id
            )

            if not saved:
                await message.answer(
                    "⚠️ Telegram akkauntiga kirish muvaffaqiyatli "
                    "bo‘ldi, lekin ma’lumotlarni saqlashda "
                    "muammo yuz berdi.\n\n"
                    "Iltimos, holatni tekshirib ko‘ring."
                )
                return

            await state.clear()

            await _post_connect_setup(telegram_id, message.bot)

            await message.answer(
                "✅ <b>Telegram akkaunt muvaffaqiyatli ulandi!</b>\n\n"
                "Endi Nano-Bot ulangan Telegram akkauntingiz "
                "bilan ishlashi mumkin.",
                reply_markup=main_menu_keyboard(),
            )
            return

    except SessionPasswordNeededError:
        await state.set_state(
            TelegramConnectStates.waiting_password
        )

        await message.answer(
            "🔐 <b>2FA parol kerak.</b>\n\n"
            "Telegram akkauntingizda ikki bosqichli himoya "
            "yoqilgan.\n\n"
            "Iltimos, 2FA parolingizni yuboring.",
            reply_markup=_telegram_input_cancel_keyboard(),
        )

        return

    except PhoneCodeInvalidError:
        await message.answer(
            "❌ <b>Kod noto‘g‘ri.</b>\n\n"
            "Telegram yuborgan kodni qayta tekshiring "
            "va yana yuboring.\n\n"
            "Kod namunasi:\n"
            "<code>7 5 8 1 1</code>"
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
            "❌ Telegram kodini tekshirishda xatolik yuz berdi."
        )


# ============================================================
# 2FA PAROLNI BEKOR QILISH
# ============================================================

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


# ============================================================
# 2FA PAROLNI QABUL QILISH
# ============================================================

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
        success = await telegram_client_manager.sign_in_password(
            telegram_id=telegram_id,
            password=password,
        )

        if success:
            saved = await save_connected_account(
                telegram_id=telegram_id
            )

            if not saved:
                await message.answer(
                    "⚠️ Telegram akkauntiga kirish muvaffaqiyatli "
                    "bo‘ldi, lekin ma’lumotlarni saqlashda "
                    "muammo yuz berdi."
                )
                return

            await state.clear()

            await _post_connect_setup(telegram_id, message.bot)

            await message.answer(
                "✅ <b>Telegram akkaunt muvaffaqiyatli ulandi!</b>\n\n"
                "2FA tekshiruvi muvaffaqiyatli yakunlandi.\n\n"
                "Nano-Bot endi ulangan Telegram akkauntingiz "
                "bilan ishlashi mumkin.",
                reply_markup=main_menu_keyboard(),
            )

            return

        await message.answer(
            "❌ Telegram akkauntini ulashning iloji bo‘lmadi."
        )

    except Exception:
        logger.exception(
            "Telegram 2FA login xatosi: telegram_id=%s",
            telegram_id,
        )

        await message.answer(
            "❌ 2FA parolini tekshirishda xatolik yuz berdi.\n\n"
            "Parolni qayta tekshirib yuboring."
        )


# ============================================================
# ULANISHDAN KEYINGI SOZLASH
# ============================================================
#
# Telegram akkaunt muvaffaqiyatli ulangandan keyin:
# - Foydalanuvchi nomidan shaxsiy Storage Channel tayyorlanadi
# - Auto Reply va First Message listenerlari ishga tushiriladi
#
# Bu funksiya xato bersa ham ulanish jarayonini yiqitmaydi —
# faqat logga yoziladi (maxfiy ma'lumotlarsiz).

async def _post_connect_setup(
    telegram_id: int,
    bot,
) -> None:
    telegram_id = int(telegram_id)

    try:
        async with AsyncSessionLocal() as session:
            user = await get_user_by_telegram_id(
                session,
                telegram_id,
            )

            if user is None:
                return

            account = await get_connected_telegram_account(
                session,
                user.id,
            )

            if account is None:
                return

            db_user_id = user.id
            telegram_account_id = account.id

        await ensure_storage_channel(
            telegram_id=telegram_id,
            db_user_id=db_user_id,
            telegram_account_id=telegram_account_id,
            bot=bot,
        )

        # MUHIM (tartib qat'iy!): Telethon bir client'ga
        # ro'yxatdan o'tgan handler'larni REGISTRATSIYA
        # TARTIBIDA, ketma-ket chaqiradi (qarang: app/main.py
        # dagi izoh) — shu sabab First Message har doim Auto
        # Reply'dan OLDIN ishga tushirilishi kerak.
        await first_message_engine.start_for_user(db_user_id)
        await auto_reply_engine.start_for_user(db_user_id)

    except Exception:
        logger.exception(
            "Post-connect setup xatosi: telegram_id=%s",
            telegram_id,
        )


# ============================================================
# ULANGAN AKKAUNTNI DATABASE'GA SAQLASH
# ============================================================

async def save_connected_account(
    telegram_id: int,
) -> bool:
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


# ============================================================
# ULANISH HOLATI
# ============================================================

async def get_connection_status(
    telegram_id: int,
) -> bool:
    telegram_id = int(telegram_id)

    try:
        authorized = await telegram_client_manager.is_authorized(
            telegram_id
        )

        if authorized:
            return True

    except Exception:
        logger.exception(
            "Telethon authorization check failed: "
            "telegram_id=%s",
            telegram_id,
        )

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


# ============================================================
# INLINE ENTRY POINT (Nano-Agent → 📱 Telegram ulash)
# ============================================================
#
# Eski reply-keyboard triggerlar ("📱 Telegram ulash" matni)
# hamon ishlaydi (mavjud funksiyani yo'qotmaslik uchun), lekin
# yangi Bosh menyu ularni ko'rsatmaydi — endi shu bo'lim Nano-
# Agent ichidagi inline tugma orqali ochiladi. Pastdagi
# handlerlar xuddi shu mavjud logikani (get_connection_status,
# has_accepted_terms, _start_phone_prompt, terms gate) qayta
# ishlatadi — dublikat qilinmaydi.

def _telegram_connected_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Holatni tekshirish",
                    callback_data="nano:agent:telegram:status",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔌 Telegramni uzish",
                    callback_data="nano:agent:telegram:disconnect",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data="nano:agent",
                ),
            ],
        ]
    )


def _telegram_disconnected_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data="nano:agent",
                ),
            ],
        ]
    )


async def _safe_edit_connect(
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
                "Telegram ulash xabarini yangilab bo'lmadi."
            )


@router.callback_query(F.data == "nano:agent:telegram")
async def agent_telegram_entry(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    connected = await get_connection_status(telegram_id)

    await callback.answer()

    if connected:
        await _safe_edit_connect(
            callback,
            "📱 <b>Telegram akkaunt</b>\n\n"
            "✅ Telegram akkauntingiz ulangan.\n\n"
            "Ulangan akkaunt orqali Nano-Bot avtomatik "
            "javoblarni boshqarishi mumkin.",
            _telegram_connected_inline_keyboard(),
        )
        return

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            await callback.message.answer(
                "❌ Foydalanuvchi topilmadi.\n\n"
                "Iltimos, /start buyrug'ini bosing."
            )
            return

        db_user_id = user.id

    accepted = await has_accepted_terms(db_user_id)

    if accepted:
        await _start_phone_prompt(callback.message, state)
        return

    await _safe_edit_connect(
        callback,
        TERMS_GATE_TEXT,
        _terms_gate_keyboard(),
    )


@router.callback_query(F.data == "nano:agent:telegram:status")
async def agent_telegram_status(
    callback: CallbackQuery,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    try:
        connected = await get_connection_status(telegram_id)

        if not connected:
            await callback.answer()

            await _safe_edit_connect(
                callback,
                "❌ Telegram akkaunt ulanmagan.",
                _telegram_disconnected_inline_keyboard(),
            )
            return

        me = await telegram_client_manager.get_me(
            telegram_id
        )

        await callback.answer()

        if me:
            username = (
                f"@{me.username}"
                if me.username
                else "Username yo'q"
            )

            name = me.first_name or "Telegram"

            await _safe_edit_connect(
                callback,
                "📱 <b>Telegram holati</b>\n\n"
                "🟢 Holat: <b>Ulangan</b>\n"
                f"👤 Ism: <b>{name}</b>\n"
                f"🔗 Username: <b>{username}</b>\n"
                f"🆔 ID: <code>{me.id}</code>",
                _telegram_connected_inline_keyboard(),
            )
            return

        await _safe_edit_connect(
            callback,
            "⚠️ Session mavjud, lekin Telegram akkauntiga "
            "ulanishni tekshirib bo'lmadi.",
            _telegram_connected_inline_keyboard(),
        )

    except Exception:
        logger.exception(
            "Telegram status xatosi (inline): telegram_id=%s",
            telegram_id,
        )

        await callback.answer(
            "❌ Xatolik yuz berdi.",
            show_alert=True,
        )


@router.callback_query(F.data == "nano:agent:telegram:disconnect")
async def agent_telegram_disconnect(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    try:
        await telegram_client_manager.logout(telegram_id)

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

        await callback.answer("🔌 Uzildi.")

        await _safe_edit_connect(
            callback,
            "🔌 <b>Telegram uzildi.</b>\n\n"
            "Telegram akkauntingiz Nano-Botdan uzildi.",
            _telegram_disconnected_inline_keyboard(),
        )

    except Exception:
        logger.exception(
            "Telegram disconnect xatosi (inline): "
            "telegram_id=%s",
            telegram_id,
        )

        await callback.answer(
            "❌ Telegram akkauntini uzishda xatolik yuz berdi.",
            show_alert=True,
        )


@router.callback_query(F.data == "nano:agent:telegram:cancel")
async def agent_telegram_cancel_input(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Telefon/kod/2FA parol kiritish bosqichlarining yagona
    inline "Bekor qilish" ishlovchisi. Qaysi bosqichda
    ekanligidan qat'i nazar, mavjud pending Telethon
    sessiyasini (agar bo'lsa) xavfsiz tozalaydi.
    """

    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    current_state = await state.get_state()

    if current_state in (
        TelegramConnectStates.waiting_code.state,
        TelegramConnectStates.waiting_password.state,
    ):
        try:
            await telegram_client_manager.logout(telegram_id)
        except Exception:
            logger.exception(
                "Pending Telegram login cleanup failed "
                "(inline cancel): telegram_id=%s",
                telegram_id,
            )

    await state.clear()

    await callback.answer("❌ Bekor qilindi.")

    await _safe_edit_connect(
        callback,
        "❌ Telegram ulash bekor qilindi.",
        _telegram_disconnected_inline_keyboard(),
    )


# ============================================================
# EXPORT
# ============================================================

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