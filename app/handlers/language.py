import logging

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import User, UserSettings
from app.keyboards.language import language_keyboard
from app.keyboards.main import main_menu_keyboard
from app.services.user_service import get_user_by_telegram_id

logger = logging.getLogger(__name__)

router = Router()


LANGUAGES = {
    "🇺🇿 O‘zbekcha": "uz",
    "🇷🇺 Русский": "ru",
    "🇬🇧 English": "en",
    "🇩🇪 Deutsch": "de",
}


async def update_user_language(
    telegram_id: int,
    language: str,
) -> bool:
    """
    Telegram ID orqali foydalanuvchini topadi
    va User hamda UserSettings tilini yangilaydi.
    """

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            return False

        user.language = language

        result = await session.execute(
            select(UserSettings).where(
                UserSettings.user_id == user.id
            )
        )

        settings = result.scalar_one_or_none()

        if settings is None:
            settings = UserSettings(
                user_id=user.id,
                language=language,
                notifications_enabled=True,
            )

            session.add(settings)
        else:
            settings.language = language

        await session.commit()

        return True


@router.message(F.text == "🌐 Til")
async def language_menu(message: Message) -> None:
    await message.answer(
        "🌐 <b>Tilni tanlang</b>\n\n"
        "Nano-Bot interfeysi uchun kerakli tilni tanlang:",
        reply_markup=language_keyboard(),
    )


@router.message(F.text.in_(LANGUAGES.keys()))
async def select_language(message: Message) -> None:
    language = LANGUAGES[message.text]

    success = await update_user_language(
        telegram_id=int(message.from_user.id),
        language=language,
    )

    if not success:
        await message.answer(
            "❌ Foydalanuvchi topilmadi.\n\n"
            "Iltimos, /start buyrug‘ini bosing.",
            reply_markup=main_menu_keyboard(),
        )
        return

    language_names = {
        "uz": "🇺🇿 O‘zbekcha",
        "ru": "🇷🇺 Русский",
        "en": "🇬🇧 English",
        "de": "🇩🇪 Deutsch",
    }

    await message.answer(
        "✅ <b>Til muvaffaqiyatli o‘zgartirildi!</b>\n\n"
        f"Tanlangan til: "
        f"<b>{language_names.get(language, language)}</b>",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == "🏠 Bosh menyu")
async def language_back(message: Message) -> None:
    await message.answer(
        "🏠 <b>Bosh menyu</b>",
        reply_markup=main_menu_keyboard(),
    )


__all__ = [
    "router",
    "update_user_language",
]