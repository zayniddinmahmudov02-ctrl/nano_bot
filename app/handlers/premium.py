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


def is_premium_active(subscription: Subscription) -> bool:
    if subscription.status != "premium":
        return False

    if subscription.premium_expires_at is None:
        return True

    return subscription.premium_expires_at > datetime.utcnow()


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

        active = is_premium_active(subscription)
        expires_at = subscription.premium_expires_at

    if active:
        expiry_text = (
            f"📅 Amal qilish muddati: "
            f"<b>{expires_at:%d.%m.%Y}</b>"
            if expires_at
            else "📅 Amal qilish muddati: <b>Cheksiz</b>"
        )

        await message.answer(
            "💎 <b>Nano-Bot Premium</b>\n\n"
            "✅ Premium obunangiz faol.\n\n"
            f"{expiry_text}\n\n"
            "Premium imkoniyatlaridan foydalanishingiz "
            "mumkin.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(
        "💎 <b>Nano-Bot Premium</b>\n\n"
        "🎉 Hozircha Premium funksiyalari "
        "<b>bepul</b> taqdim etilmoqda.\n\n"
        f"💰 Kelajakdagi narx: "
        f"<b>{PREMIUM_PRICE} {PREMIUM_CURRENCY}</b> / oy\n\n"
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
    "is_premium_active",
]