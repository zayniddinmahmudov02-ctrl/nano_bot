import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import (
    Referral,
    Statistics,
    Subscription,
    User,
    UserSettings,
)
from app.keyboards.main import main_menu_keyboard
from app.services.user_service import get_or_create_user

logger = logging.getLogger(__name__)

router = Router()


async def initialize_user_data(user: User) -> None:
    """
    Foydalanuvchi uchun kerakli boshlang‘ich ma’lumotlarni yaratadi.

    Quyidagilar yaratiladi:
    - UserSettings
    - Statistics
    - Subscription
    - Referral
    """

    async with AsyncSessionLocal() as session:

        # -------------------------------------------------
        # USER SETTINGS
        # -------------------------------------------------

        result = await session.execute(
            select(UserSettings).where(
                UserSettings.user_id == user.id
            )
        )

        settings = result.scalar_one_or_none()

        if settings is None:
            settings = UserSettings(
                user_id=user.id,
                language=user.language or "uz",
                notifications_enabled=True,
            )

            session.add(settings)

        # -------------------------------------------------
        # STATISTICS
        # -------------------------------------------------

        result = await session.execute(
            select(Statistics).where(
                Statistics.user_id == user.id
            )
        )

        statistics = result.scalar_one_or_none()

        if statistics is None:
            statistics = Statistics(
                user_id=user.id,
                replied_people=0,
                auto_replies=0,
                first_messages_sent=0,
            )

            session.add(statistics)

        # -------------------------------------------------
        # SUBSCRIPTION
        # -------------------------------------------------

        result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id
            )
        )

        subscription = result.scalar_one_or_none()

        if subscription is None:
            subscription = Subscription(
                user_id=user.id,
                status="free",
            )

            session.add(subscription)

        # -------------------------------------------------
        # REFERRAL
        # -------------------------------------------------

        result = await session.execute(
            select(Referral).where(
                Referral.user_id == user.id
            )
        )

        referral = result.scalar_one_or_none()

        if referral is None:
            referral = Referral(
                user_id=user.id,
                referral_code=f"nano_{user.telegram_id}",
                referral_count=0,
            )

            session.add(referral)

        # -------------------------------------------------
        # SAVE
        # -------------------------------------------------

        await session.commit()


async def process_start(message: Message) -> None:
    telegram_user = message.from_user

    if telegram_user is None:
        return

    try:
        # -------------------------------------------------
        # USER
        # -------------------------------------------------

        async with AsyncSessionLocal() as session:
            user = await get_or_create_user(
                session,
                telegram_user,
            )

        # -------------------------------------------------
        # USER DATA
        # -------------------------------------------------

        await initialize_user_data(user)

        # -------------------------------------------------
        # MAIN MENU
        # -------------------------------------------------

        await message.answer(
            "👋 <b>Nano-Bot</b>ga xush kelibsiz!\n\n"
            "🤖 Shaxsiy Telegram akkauntingiz uchun "
            "avtomatlashtirish imkoniyatlaridan foydalaning.\n\n"
            "Quyidagi menyudan kerakli bo‘limni tanlang:",
            reply_markup=main_menu_keyboard(),
        )

    except Exception:
        logger.exception(
            "Start handlerda xatolik."
        )

        await message.answer(
            "❌ Xatolik yuz berdi.\n\n"
            "Iltimos, birozdan keyin qayta urinib ko‘ring."
        )


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await process_start(message)


__all__ = [
    "router",
    "process_start",
    "initialize_user_data",
]