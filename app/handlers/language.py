import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import User
from app.keyboards.language import language_keyboard
from app.keyboards.main import main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router()


LANGUAGES = {
    "🇺🇿 O‘zbekcha": "uz",
    "🇷🇺 Русский": "ru",
    "🇬🇧 English": "en",
    "🇩🇪 Deutsch": "de",
}


LANGUAGE_NAMES = {
    "uz": "🇺🇿 O‘zbekcha",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "de": "🇩🇪 Deutsch",
}


async def set_user_language(
    user_id: int,
    language: str,
) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id == user_id
            )
        )

        user = result.scalar_one_or_none()

        if not user:
            return False

        user.language = language

        if user.settings:
            user.settings.language = language

        await session.commit()

    return True


@router.message(F.text == "🌐 Til")
async def language_menu(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "🌐 <b>Tilni tanlang</b>\n\n"
        "Nano-Bot interfeys tilini tanlang:",
        reply_markup=language_keyboard(
            uzbek=True,
            russian=True,
            english=True,
            german=True,
        ),
    )


@router.message(F.text == "🌐 Tilni o‘zgartirish")
async def change_language(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "🌐 <b>Tilni tanlang</b>",
        reply_markup=language_keyboard(
            uzbek=True,
            russian=True,
            english=True,
            german=True,
        ),
    )


@router.message(
    F.text.in_(
        [
            "🇺🇿 O‘zbekcha",
            "🇷🇺 Русский",
            "🇬🇧 English",
            "🇩🇪 Deutsch",
        ]
    )
)
async def select_language(
    message: Message,
) -> None:
    language = LANGUAGES.get(
        message.text
    )

    if not language:
        return

    success = await set_user_language(
        user_id=message.from_user.id,
        language=language,
    )

    if not success:
        await message.answer(
            "❌ Foydalanuvchi topilmadi."
        )
        return

    await message.answer(
        f"✅ Til o‘zgartirildi: "
        f"<b>{LANGUAGE_NAMES[language]}</b>",
        reply_markup=main_menu_keyboard(),
    )


@router.message(
    F.text == "⬅️ Orqaga"
)
async def language_back(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "🏠 <b>Asosiy menyu</b>",
        reply_markup=main_menu_keyboard(),
    )