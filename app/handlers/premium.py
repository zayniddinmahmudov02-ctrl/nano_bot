import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select

from app.config import PREMIUM_PRICE, PREMIUM_CURRENCY
from app.database import AsyncSessionLocal
from app.database.models import Subscription
from app.keyboards.main import main_menu_keyboard
from app.services.user_service import get_user_by_telegram_id

logger = logging.getLogger(__name__)

router = Router()


async def get_or_create_subscription(
    session,
    user_id: int,
) -> Subscription:
    """
    user_id — users.id.
    Telegram ID emas.
    """

    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id
        )
    )

    subscription = result.scalar_one_or_none()

    if subscription is None:
        subscription = Subscription(
            user_id=user_id,
            status="free",
        )

        session.add(subscription)
        await session.flush()

    return subscription


@router.message(F.text == "💎 Premium")
async def premium_menu(message: Message) -> None:
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

        subscription = await get_or_create_subscription(
            session,
            user.id,
        )

        await session.commit()

        status = subscription.status or "free"

        premium_expires_at = (
            subscription.premium_expires_at
        )

    # ---------------------------------------------------------
    # PREMIUM ACTIVE
    # ---------------------------------------------------------

    is_active = (
        status == "premium"
        and premium_expires_at is not None
        and premium_expires_at > datetime.utcnow()
    )

    if is_active:
        await message.answer(
            "💎 <b>Nano-Bot Premium</b>\n\n"
            "✅ Premium obunangiz faol.\n\n"
            f"📅 Amal qilish muddati: "
            f"<b>{premium_expires_at:%d.%m.%Y}</b>\n\n"
            "Premium imkoniyatlaridan foydalanishingiz "
            "mumkin.",
            reply_markup=main_menu_keyboard(),
        )
        return

    # ---------------------------------------------------------
    # FREE
    # ---------------------------------------------------------

    await message.answer(
        "💎 <b>Nano-Bot Premium</b>\n\n"
        "Hozircha Premium funksiyalari "
        "<b>bepul</b> taqdim etilmoqda. 🎉\n\n"
        f"💰 Kelajakdagi narx: "
        f"<b>${PREMIUM_PRICE:.2f} "
        f"{PREMIUM_CURRENCY}</b> / oy\n\n"
        "🚀 To‘lov tizimi keyingi bosqichda "
        "ishga tushiriladi.\n\n"
        "Hozircha Nano-Bot'dan bepul foydalanishingiz "
        "mumkin.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == "🏠 Bosh menyu")
async def premium_back(message: Message) -> None:
    await message.answer(
        "🏠 <b>Bosh menyu</b>",
        reply_markup=main_menu_keyboard(),
    )


__all__ = [
    "router",
    "get_or_create_subscription",
]