import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import TelegramAccount
from app.keyboards.main import main_menu_keyboard
from app.keyboards.telegram import (
    telegram_menu_keyboard,
)
from app.services.user_service import (
    get_user_by_telegram_id,
)
from app.telegram.user_client import telegram_client_manager

logger = logging.getLogger(__name__)

router = Router()


class TelegramConnectStates(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    waiting_password = State()


@router.message(F.text == "📱 Telegram ulash")
async def telegram_connect_menu(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

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


@router.message(F.text == "🔌 Telegramni uzish")
async def telegram_disconnect(
    message: Message,
    state: FSMContext,
) -> None:
    telegram_id = int(message.from_user.id)

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


@router.message(F.text == "🔄 Holatni tekshirish")
async def telegram_status(
    message: Message,
) -> None:
    telegram_id = int(message.from_user.id)

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


@router.message(
    TelegramConnectStates.waiting_phone,
    F.text,
)
async def receive_phone(
    message: Message,
    state: FSMContext,
) -> None:
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

    result = (
        await telegram_client_manager
        .start_phone_login(
            user_id=telegram_id,
            phone=phone,
        )
    )

    status = result.get("status")

    if status == "already_authorized":
        await save_connected_account(
            telegram_id=telegram_id,
            result=result,
        )

        await state.clear()

        await message.answer(
            "✅ Telegram akkaunt allaqachon "
            "ulangan.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if status == "code_sent":
        await state.update_data(
            phone=phone
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
        return

    if status == "flood_wait":
        seconds = result.get(
            "seconds",
            0,
        )

        await message.answer(
            "⏳ Juda ko‘p urinish.\n\n"
            f"{seconds} soniyadan keyin "
            "qayta urinib ko‘ring."
        )
        return

    logger.error(
        "Telegram login error: %s",
        result,
    )

    await message.answer(
        "❌ Telegram kodini yuborishda "
        "xatolik yuz berdi.\n\n"
        "Telefon raqamingizni tekshiring "
        "va qayta urinib ko‘ring."
    )


@router.message(
    TelegramConnectStates.waiting_code,
    F.text == "❌ Bekor qilish",
)
async def cancel_code(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "❌ Telegram ulash bekor qilindi.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(
    TelegramConnectStates.waiting_code,
    F.text,
)
async def receive_code(
    message: Message,
    state: FSMContext,
) -> None:
    code = message.text.strip()

    if not code.isdigit():
        await message.answer(
            "❌ Kod faqat raqamlardan iborat "
            "bo‘lishi kerak."
        )
        return

    data = await state.get_data()
    phone = data.get("phone")

    if not phone:
        await state.clear()

        await message.answer(
            "❌ Login sessiyasi topilmadi.\n\n"
            "Ulanishni qaytadan boshlang.",
            reply_markup=main_menu_keyboard(),
        )
        return

    telegram_id = int(message.from_user.id)

    await message.answer(
        "⏳ <b>Kod tekshirilmoqda...</b>"
    )

    result = (
        await telegram_client_manager
        .sign_in_code(
            user_id=telegram_id,
            phone=phone,
            code=code,
        )
    )

    status = result.get("status")

    if status == "authorized":
        await save_connected_account(
            telegram_id=telegram_id,
            result=result,
        )

        await state.clear()

        await message.answer(
            "✅ <b>Telegram muvaffaqiyatli ulandi!</b>\n\n"
            "Endi Nano-Bot sizning shaxsiy "
            "Telegram akkauntingizdagi avtomatik "
            "javoblarni boshqarishi mumkin.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if status == "password_required":
        await state.set_state(
            TelegramConnectStates.waiting_password
        )

        await message.answer(
            "🔐 <b>2FA password kerak.</b>\n\n"
            "Telegram akkauntingizdagi "
            "2 bosqichli himoya parolini yuboring.\n\n"
            "⚠️ Password database'ga saqlanmaydi."
        )
        return

    if status == "invalid_code":
        await message.answer(
            "❌ Kod noto‘g‘ri.\n\n"
            "Telegram yuborgan kodni "
            "qaytadan kiriting."
        )
        return

    if status == "expired_code":
        await state.clear()

        await message.answer(
            "⌛ Kodning amal qilish muddati tugadi.\n\n"
            "Telegram ulashni qaytadan boshlang.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if status == "flood_wait":
        seconds = result.get(
            "seconds",
            0,
        )

        await message.answer(
            "⏳ Juda ko‘p urinish.\n\n"
            f"{seconds} soniyadan keyin "
            "qayta urinib ko‘ring."
        )
        return

    logger.error(
        "Telegram code error: %s",
        result,
    )

    await message.answer(
        "❌ Telegram akkauntni ulashda "
        "xatolik yuz berdi."
    )


@router.message(
    TelegramConnectStates.waiting_password,
    F.text == "❌ Bekor qilish",
)
async def cancel_password(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "❌ Telegram ulash bekor qilindi.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(
    TelegramConnectStates.waiting_password,
    F.text,
)
async def receive_password(
    message: Message,
    state: FSMContext,
) -> None:
    password = message.text.strip()

    if not password:
        await message.answer(
            "❌ Password bo‘sh bo‘lishi mumkin emas."
        )
        return

    telegram_id = int(message.from_user.id)

    await message.answer(
        "⏳ <b>2FA tekshirilmoqda...</b>"
    )

    result = (
        await telegram_client_manager
        .sign_in_password(
            user_id=telegram_id,
            password=password,
        )
    )

    status = result.get("status")

    if status == "authorized":
        await save_connected_account(
            telegram_id=telegram_id,
            result=result,
        )

        await state.clear()

        await message.answer(
            "✅ <b>Telegram muvaffaqiyatli ulandi!</b>\n\n"
            "2FA tekshirildi va session yaratildi.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if status == "invalid_password":
        await message.answer(
            "❌ 2FA password noto‘g‘ri.\n\n"
            "Qaytadan kiriting."
        )
        return

    logger.error(
        "Telegram password error: %s",
        result,
    )

    await message.answer(
        "❌ 2FA tekshirishda xatolik yuz berdi."
    )


async def get_connection_status(
    telegram_id: int,
) -> bool:
    """
    Telegram ID orqali User topiladi.
    Keyin User.id orqali TelegramAccount qidiriladi.
    """

    telegram_id = int(telegram_id)

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

        if not account:
            return False

        if not account.is_connected:
            return False

        db_user_id = user.id

    authorized = (
        await telegram_client_manager
        .is_authorized(telegram_id)
    )

    if authorized:
        return True

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TelegramAccount).where(
                TelegramAccount.user_id == db_user_id
            )
        )

        account = result.scalar_one_or_none()

        if account:
            account.is_connected = False
            account.status = "disconnected"

            await session.commit()

    return False


async def save_connected_account(
    telegram_id: int,
    result: dict,
) -> None:
    """
    Telegram ID orqali User topadi.
    TelegramAccount.user_id ga esa User.id yozadi.
    """

    telegram_id = int(telegram_id)

    connected_telegram_id = result.get(
        "telegram_id"
    )

    if not connected_telegram_id:
        raise RuntimeError(
            "Telegram ID olinmadi."
        )

    connected_telegram_id = int(
        connected_telegram_id
    )

    username = result.get(
        "username"
    )

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            raise RuntimeError(
                "Bot foydalanuvchisi database'dan topilmadi."
            )

        result_query = await session.execute(
            select(TelegramAccount).where(
                TelegramAccount.user_id == user.id
            )
        )

        account = result_query.scalar_one_or_none()

        if account:
            account.telegram_id = connected_telegram_id
            account.is_connected = True
            account.status = "connected"

            if not account.session_name:
                account.session_name = (
                    f"user_{telegram_id}"
                )

            if hasattr(account, "username"):
                account.username = username

        else:
            account = TelegramAccount(
                user_id=user.id,
                telegram_id=connected_telegram_id,
                phone=None,
                username=username,
                session_name=f"user_{telegram_id}",
                is_connected=True,
                status="connected",
            )

            session.add(account)

        await session.commit()

    logger.info(
        "Telegram account connected: "
        "telegram_user=%s "
        "telegram_account=%s "
        "username=%s",
        telegram_id,
        connected_telegram_id,
        username,
    )


__all__ = [
    "router",
    "TelegramConnectStates",
    "get_connection_status",
    "save_connected_account",
]