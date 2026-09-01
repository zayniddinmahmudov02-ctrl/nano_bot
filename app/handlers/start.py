import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select

from app.config import BOT_USERNAME
from app.database import AsyncSessionLocal
from app.database.models import (
    AdminStatistics,
    Referral,
    Statistics,
    Subscription,
    UserSettings,
)
from app.keyboards.main import main_menu_keyboard
from app.services.user_service import get_or_create_user

logger = logging.getLogger(__name__)

router = Router()


async def initialize_user_data(
    session,
    user,
):
    """
    Foydalanuvchi uchun barcha boshlang‘ich
    ma'lumotlarni yaratadi.

    user.id — ichki PostgreSQL ID.
    user.telegram_id — Telegram ID.
    """

    # -----------------------------
    # USER SETTINGS
    # -----------------------------

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


    # -----------------------------
    # STATISTICS
    # -----------------------------

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


    # -----------------------------
    # SUBSCRIPTION
    # -----------------------------

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
            is_premium=False,
        )

        session.add(subscription)


    # -----------------------------
    # REFERRAL
    # -----------------------------

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


    # -----------------------------
    # ADMIN STATISTICS
    # -----------------------------

    result = await session.execute(
        select(AdminStatistics)
        .order_by(AdminStatistics.id.asc())
        .limit(1)
    )

    admin_statistics = result.scalar_one_or_none()

    if admin_statistics is None:
        admin_statistics = AdminStatistics(
            total_users=0,
            total_auto_replies=0,
            total_replied_people=0,
            total_payments=0,
            total_revenue=0,
        )

        session.add(admin_statistics)

    return (
        settings,
        statistics,
        subscription,
        referral,
        admin_statistics,
    )


async def process_start(
    message: Message,
) -> None:
    telegram_user = message.from_user

    if telegram_user is None:
        return

    telegram_id = int(telegram_user.id)

    async with AsyncSessionLocal() as session:

        # Telegram ID → User
        user = await get_or_create_user(
            session,
            telegram_user,
        )

        is_new_user = False

        # Foydalanuvchi bilan bog‘liq ma'lumotlarni tekshirish
        result = await session.execute(
            select(UserSettings).where(
                UserSettings.user_id == user.id
            )
        )

        if result.scalar_one_or_none() is None:
            is_new_user = True

        await initialize_user_data(
            session,
            user,
        )

        await session.commit()

    logger.info(
        "User started bot: telegram_id=%s, db_user_id=%s, new=%s",
        telegram_id,
        user.id,
        is_new_user,
    )

    if is_new_user:
        text = (
            "👋 <b>Nano-Bot'ga xush kelibsiz!</b>\n\n"
            "🤖 Telegram akkauntingizni "
            "avtomatlashtirish uchun yordamchingiz.\n\n"
            "Quyidagi imkoniyatlardan foydalanishingiz mumkin:\n\n"
            "📱 Telegram ulash\n"
            "🤖 Avto javoblar\n"
            "1️⃣ Birinchi xabar\n"
            "👥 Referallar\n"
            "📊 Statistika\n"
            "🌐 Til\n"
            "💎 Premium\n"
            "⚙️ Sozlamalar\n\n"
            "Boshlash uchun kerakli bo‘limni tanlang 👇"
        )
    else:
        text = (
            "👋 <b>Qaytganingizdan xursandmiz!</b>\n\n"
            "Nano-Bot tayyor. Kerakli bo‘limni tanlang 👇"
        )

    await message.answer(
        text,
        reply_markup=main_menu_keyboard(),
    )


@router.message(CommandStart())
async def start_command(
    message: Message,
) -> None:
    """
    /start
    /start referral_code
    """

    args = None

    if message.text:
        parts = message.text.split(maxsplit=1)

        if len(parts) > 1:
            args = parts[1].strip()

    await process_start(message)

    # Referral deep-link alohida qayta ishlanadi.
    # Referral handler o‘zining apply_referral()
    # funksiyasi orqali tekshiradi.
    if args:
        try:
            from app.handlers.referrals import apply_referral

            await apply_referral(
                telegram_id=int(message.from_user.id),
                referral_code=args,
            )

        except Exception:
            logger.exception(
                "Failed to process referral: telegram_id=%s",
                message.from_user.id,
            )


@router.message(F.text == "🏠 Bosh menyu")
async def start_home(
    message: Message,
) -> None:
    await message.answer(
        "🏠 <b>Bosh menyu</b>\n\n"
        "Kerakli bo‘limni tanlang 👇",
        reply_markup=main_menu_keyboard(),
    )


__all__ = [
    "router",
    "process_start",
    "initialize_user_data",
]