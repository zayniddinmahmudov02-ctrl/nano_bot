import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import User
from app.keyboards.language import language_keyboard
from app.keyboards.main import main_menu_keyboard
from app.keyboards.settings import (
    name_cancel_keyboard,
    settings_keyboard,
)

logger = logging.getLogger(__name__)

router = Router()


class SettingsStates(StatesGroup):
    waiting_name = State()


# =========================================================
# USER
# =========================================================

async def get_user(
    telegram_id: int,
) -> User | None:

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id == telegram_id
            )
        )

        return result.scalar_one_or_none()


# =========================================================
# SETTINGS MENU
# =========================================================

@router.message(F.text == "⚙️ Sozlamalar")
async def settings_menu(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    user = await get_user(
        message.from_user.id
    )

    if not user:
        await message.answer(
            "❌ Foydalanuvchi topilmadi.",
            reply_markup=main_menu_keyboard(),
        )
        return

    full_name = " ".join(
        x
        for x in [
            user.first_name,
            user.last_name,
        ]
        if x
    )

    if not full_name:
        full_name = "Belgilanmagan"

    await message.answer(
        "⚙️ <b>Sozlamalar</b>\n\n"
        f"👤 Ism: <b>{full_name}</b>\n"
        f"🌐 Til: <b>{user.language}</b>\n\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=settings_keyboard(),
    )


# =========================================================
# NAME
# =========================================================

@router.message(F.text == "👤 Ism va familiya")
async def edit_name_start(
    message: Message,
    state: FSMContext,
) -> None:

    user = await get_user(
        message.from_user.id
    )

    if not user:
        await message.answer(
            "❌ Foydalanuvchi topilmadi."
        )
        return

    current_name = " ".join(
        x
        for x in [
            user.first_name,
            user.last_name,
        ]
        if x
    )

    if not current_name:
        current_name = "Belgilanmagan"

    await state.set_state(
        SettingsStates.waiting_name
    )

    await message.answer(
        "👤 <b>Ism va familiya</b>\n\n"
        f"Joriy ism: <b>{current_name}</b>\n\n"
        "Yangi ism va familiyangizni yuboring.\n\n"
        "Masalan:\n"
        "<code>Zayniddin Makhmudov</code>",
        reply_markup=name_cancel_keyboard(),
    )


@router.message(
    SettingsStates.waiting_name,
    F.text == "❌ Bekor qilish",
)
async def cancel_name(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    await message.answer(
        "❌ O‘zgartirish bekor qilindi.",
        reply_markup=settings_keyboard(),
    )


@router.message(
    SettingsStates.waiting_name,
    F.text,
)
async def save_name(
    message: Message,
    state: FSMContext,
) -> None:

    value = message.text.strip()

    if len(value) < 2:
        await message.answer(
            "❌ Ism juda qisqa.\n\n"
            "Kamida 2 ta belgi kiriting."
        )
        return

    parts = value.split()

    first_name = parts[0]

    last_name = (
        " ".join(parts[1:])
        if len(parts) > 1
        else None
    )

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User).where(
                User.telegram_id
                == message.from_user.id
            )
        )

        user = result.scalar_one_or_none()

        if not user:
            await state.clear()

            await message.answer(
                "❌ Foydalanuvchi topilmadi.",
                reply_markup=main_menu_keyboard(),
            )
            return

        user.first_name = first_name
        user.last_name = last_name

        if user.settings:
            user.settings.display_first_name = (
                first_name
            )
            user.settings.display_last_name = (
                last_name
            )

        await session.commit()

    await state.clear()

    full_name = " ".join(
        x
        for x in [
            first_name,
            last_name,
        ]
        if x
    )

    await message.answer(
        "✅ <b>Ism va familiya saqlandi.</b>\n\n"
        f"👤 <b>{full_name}</b>",
        reply_markup=settings_keyboard(),
    )


# =========================================================
# LANGUAGE
# =========================================================

@router.message(
    F.text == "🌐 Tilni o‘zgartirish"
)
async def settings_language(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    await message.answer(
        "🌐 <b>Tilni tanlang</b>\n\n"
        "Interfeys tilini tanlang:",
        reply_markup=language_keyboard(
            uzbek=True,
            russian=True,
            english=True,
            german=True,
        ),
    )


# =========================================================
# ABOUT
# =========================================================

@router.message(
    F.text == "ℹ️ Nano-Bot haqida"
)
async def about_nano(
    message: Message,
) -> None:

    await message.answer(
        "ℹ️ <b>Nano-Bot</b>\n\n"
        "🤖 Shaxsiy Telegram avtomatlashtirish "
        "yordamchisi.\n\n"
        "Nano-Bot yordamida:\n"
        "• 📱 Telegram akkauntingizni ulash\n"
        "• 🤖 Avto javoblar yaratish\n"
        "• 1️⃣ Birinchi xabarni sozlash\n"
        "• 👥 Referral orqali limitlarni oshirish\n"
        "• 📊 Statistikani ko‘rish\n"
        "• 🌐 Interfeys tilini tanlash\n\n"
        "🔒 Suhbatlar mazmuni Nano-Bot "
        "database'ida saqlanmaydi."
    )


# =========================================================
# BACK
# =========================================================

@router.message(F.text == "⬅️ Orqaga")
async def settings_back(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    await message.answer(
        "🏠 <b>Asosiy menyu</b>",
        reply_markup=main_menu_keyboard(),
    )