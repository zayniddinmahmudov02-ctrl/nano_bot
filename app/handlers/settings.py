import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import User, UserSettings
from app.keyboards.language import language_keyboard
from app.keyboards.main import main_menu_keyboard
from app.keyboards.settings import (
    settings_back_keyboard,
    settings_cancel_keyboard,
)
from app.services.user_service import get_user_by_telegram_id

logger = logging.getLogger(__name__)

router = Router()


class SettingsStates(StatesGroup):
    waiting_name = State()


@router.message(F.text == "⚙️ Sozlamalar")
async def settings_menu(message: Message) -> None:
    telegram_id = int(message.from_user.id)

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

        username = (
            f"@{user.username}"
            if user.username
            else "—"
        )

        first_name = user.first_name or "—"
        last_name = user.last_name or "—"
        language = user.language or "uz"

    language_names = {
        "uz": "🇺🇿 O‘zbekcha",
        "ru": "🇷🇺 Русский",
        "en": "🇬🇧 English",
        "de": "🇩🇪 Deutsch",
    }

    await message.answer(
        "⚙️ <b>Sozlamalar</b>\n\n"
        f"👤 Ism: <b>{first_name}</b>\n"
        f"📝 Familiya: <b>{last_name}</b>\n"
        f"🔗 Username: <b>{username}</b>\n"
        f"🌐 Til: <b>{language_names.get(language, language)}</b>",
        reply_markup=settings_back_keyboard(),
    )


@router.message(F.text == "✏️ Ismni o‘zgartirish")
async def change_name_start(
    message: Message,
    state: FSMContext,
) -> None:
    await state.set_state(
        SettingsStates.waiting_name
    )

    await message.answer(
        "✏️ <b>Yangi ismni kiriting:</b>\n\n"
        "Bekor qilish uchun quyidagi tugmani bosing.",
        reply_markup=settings_cancel_keyboard(),
    )


@router.message(SettingsStates.waiting_name)
async def change_name(
    message: Message,
    state: FSMContext,
) -> None:
    if not message.text:
        await message.answer(
            "❌ Iltimos, ismni matn ko‘rinishida yuboring."
        )
        return

    new_name = message.text.strip()

    if len(new_name) < 2:
        await message.answer(
            "❌ Ism kamida 2 ta belgidan iborat bo‘lishi kerak."
        )
        return

    if len(new_name) > 100:
        await message.answer(
            "❌ Ism juda uzun. "
            "100 ta belgidan oshmasin."
        )
        return

    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            await state.clear()

            await message.answer(
                "❌ Foydalanuvchi topilmadi.",
                reply_markup=main_menu_keyboard(),
            )
            return

        user.first_name = new_name

        await session.commit()

    await state.clear()

    await message.answer(
        "✅ Ismingiz muvaffaqiyatli o‘zgartirildi.\n\n"
        f"👤 Yangi ism: <b>{new_name}</b>",
        reply_markup=settings_back_keyboard(),
    )


@router.message(F.text == "🌐 Tilni o‘zgartirish")
async def change_language_start(
    message: Message,
) -> None:
    await message.answer(
        "🌐 <b>Tilni tanlang:</b>",
        reply_markup=language_keyboard(),
    )


@router.message(F.text == "ℹ️ Bot haqida")
async def about_bot(message: Message) -> None:
    await message.answer(
        "🤖 <b>Nano-Bot</b>\n\n"
        "Telegram shaxsiy akkauntingiz uchun "
        "avtomatlashtirish yordamchisi.\n\n"
        "📱 Telegram ulash\n"
        "🤖 Avto javoblar\n"
        "1️⃣ Birinchi xabar\n"
        "👥 Referal tizimi\n"
        "📊 Statistikalar\n"
        "🌐 Ko‘p tilli interfeys\n\n"
        "🚀 Nano-Bot bilan Telegram'dagi "
        "kundalik ishlaringizni avtomatlashtiring.",
        reply_markup=settings_back_keyboard(),
    )


@router.message(F.text == "❌ Bekor qilish")
async def cancel_settings_action(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "❌ Amal bekor qilindi.",
        reply_markup=settings_back_keyboard(),
    )


@router.message(F.text == "⬅️ Orqaga")
async def settings_back(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "⚙️ Sozlamalar menyusi.",
        reply_markup=settings_back_keyboard(),
    )


@router.message(F.text == "🏠 Bosh menyu")
async def settings_home(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "🏠 <b>Bosh menyu</b>",
        reply_markup=main_menu_keyboard(),
    )


__all__ = [
    "router",
    "SettingsStates",
]