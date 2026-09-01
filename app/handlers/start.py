from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.filters.command import CommandObject
from aiogram.types import Message
from sqlalchemy import select

from app.config import BOT_USERNAME
from app.database.db import AsyncSessionLocal
from app.database.models import (
    AdminStatistics,
    Referral,
    Statistics,
    Subscription,
    User,
    UserSettings,
)
from app.keyboards.main import main_menu_keyboard
from app.handlers.referrals import generate_referral_code, apply_referral


router = Router(name="start")

logger = logging.getLogger(__name__)


async def get_or_create_user(message: Message) -> tuple[User, bool]:
    """
    Foydalanuvchini topadi yoki yaratadi.

    Returns:
        (user, is_new_user)
    """

    if not message.from_user:
        raise ValueError("Telegram foydalanuvchisi aniqlanmadi.")

    telegram_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        is_new_user = user is None

        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                language="uz",
                active=True,
            )

            session.add(user)
            await session.flush()

        else:
            # Telegramdagi ism va username o'zgargan bo'lishi mumkin.
            user.username = message.from_user.username
            user.first_name = message.from_user.first_name
            user.last_name = message.from_user.last_name
            user.active = True

        # ---------------------------------------------------------
        # USER SETTINGS
        # ---------------------------------------------------------

        result = await session.execute(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        settings = result.scalar_one_or_none()

        if settings is None:
            settings = UserSettings(
                user_id=user.id,
                language=user.language or "uz",
            )
            session.add(settings)

        # ---------------------------------------------------------
        # STATISTICS
        # ---------------------------------------------------------

        result = await session.execute(
            select(Statistics).where(Statistics.user_id == user.id)
        )
        statistics = result.scalar_one_or_none()

        if statistics is None:
            statistics = Statistics(
                user_id=user.id,
                people_replied=0,
                auto_replies_sent=0,
                first_messages_sent=0,
            )
            session.add(statistics)

        # ---------------------------------------------------------
        # SUBSCRIPTION
        # ---------------------------------------------------------

        result = await session.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        subscription = result.scalar_one_or_none()

        if subscription is None:
            subscription = Subscription(
                user_id=user.id,
                status="free",
            )
            session.add(subscription)

        # ---------------------------------------------------------
        # REFERRAL
        # ---------------------------------------------------------

        result = await session.execute(
            select(Referral).where(Referral.user_id == user.id)
        )
        referral = result.scalar_one_or_none()

        if referral is None:
            referral = Referral(
                user_id=user.id,
                referral_code=generate_referral_code(user.id),
                referral_count=0,
            )
            session.add(referral)

        # ---------------------------------------------------------
        # ADMIN STATISTICS
        # ---------------------------------------------------------

        admin_stats = await session.execute(
            select(AdminStatistics).limit(1)
        )
        admin_statistics = admin_stats.scalar_one_or_none()

        if admin_statistics is None:
            admin_statistics = AdminStatistics(
                total_users=0,
                total_auto_replies=0,
                total_replied_people=0,
                total_payments=0,
                total_revenue=0,
            )
            session.add(admin_statistics)

        if is_new_user:
            admin_statistics.total_users += 1

        await session.commit()
        await session.refresh(user)

        return user, is_new_user


@router.message(CommandStart())
async def start_handler(
    message: Message,
    command: CommandObject,
):
    """
    /start komandasi.

    Qo'llab-quvvatlanadi:

        /start

    va referral:

        /start ref_123456
    """

    try:
        user, is_new_user = await get_or_create_user(message)

    except Exception:
        logger.exception("Foydalanuvchini yaratishda xatolik")

        await message.answer(
            "❌ Tizimda vaqtinchalik xatolik yuz berdi.\n"
            "Iltimos, birozdan keyin qayta urinib ko‘ring."
        )
        return

    # ---------------------------------------------------------
    # REFERRAL
    # ---------------------------------------------------------

    if is_new_user and command.args:
        referral_code = command.args.strip()

        try:
            applied = await apply_referral(
                new_user_id=user.id,
                referral_code=referral_code,
            )

            if applied:
                logger.info(
                    "Referral qo'llandi: user=%s code=%s",
                    user.id,
                    referral_code,
                )

        except Exception:
            logger.exception(
                "Referral qo'llashda xatolik: user=%s code=%s",
                user.id,
                referral_code,
            )

    # ---------------------------------------------------------
    # WELCOME MESSAGE
    # ---------------------------------------------------------

    first_name = (
        message.from_user.first_name
        if message.from_user and message.from_user.first_name
        else "Do‘st"
    )

    if is_new_user:
        text = (
            f"👋 <b>Assalomu alaykum, {first_name}!</b>\n\n"
            "🤖 <b>Nano-Bot</b>ga xush kelibsiz!\n\n"
            "Nano-Bot orqali Telegram akkauntingizni ulab, "
            "avtomatik javoblar va birinchi xabar funksiyalaridan "
            "foydalanishingiz mumkin.\n\n"
            "🚀 Boshlash uchun quyidagi menyudan kerakli bo‘limni tanlang."
        )
    else:
        text = (
            f"👋 <b>Xush kelibsiz, {first_name}!</b>\n\n"
            "Nano-Bot xizmatlaridan foydalanishni davom ettiring.\n\n"
            "👇 Kerakli bo‘limni tanlang:"
        )

    await message.answer(
        text,
        reply_markup=main_menu_keyboard(),
    )


@router.message(lambda message: message.text == "🏠 Bosh menyu")
async def back_to_main_menu(message: Message):
    """
    Bosh menyuga qaytish.
    """

    await message.answer(
        "🏠 <b>Bosh menyu</b>\n\n"
        "👇 Kerakli bo‘limni tanlang:",
        reply_markup=main_menu_keyboard(),
    )


__all__ = ["router"]