import logging

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import AutoReply, Statistics
from app.keyboards.main import main_menu_keyboard
from app.keyboards.statistics import statistics_keyboard
from app.services.user_service import get_user_by_telegram_id

logger = logging.getLogger(__name__)

router = Router()


async def get_or_create_statistics(
    session,
    user_id: int,
) -> Statistics:
    """
    user_id bu Telegram ID emas.
    Bu users.id — ichki PostgreSQL ID.
    """

    result = await session.execute(
        select(Statistics).where(
            Statistics.user_id == user_id
        )
    )

    statistics = result.scalar_one_or_none()

    if statistics is None:
        statistics = Statistics(
            user_id=user_id,
            replied_people=0,
            auto_replies=0,
            first_messages_sent=0,
        )

        session.add(statistics)

        await session.flush()

    return statistics


@router.message(F.text == "📊 Statistika")
async def statistics_menu(
    message: Message,
) -> None:
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

        statistics = await get_or_create_statistics(
            session,
            user.id,
        )

        # Bazadagi real auto-reply sonini hisoblaymiz.
        result = await session.execute(
            select(AutoReply).where(
                AutoReply.user_id == user.id
            )
        )

        auto_replies = result.scalars().all()

        active_auto_replies = sum(
            1
            for item in auto_replies
            if item.is_active
        )

        total_auto_replies = len(auto_replies)

        await session.commit()

        replied_people = (
            statistics.replied_people
        )

        first_messages_sent = (
            statistics.first_messages_sent
        )

    await message.answer(
        "📊 <b>Sizning statistikangiz</b>\n\n"
        f"👥 Javob berilgan odamlar: "
        f"<b>{replied_people}</b>\n"
        f"🤖 Jami avto javoblar: "
        f"<b>{total_auto_replies}</b>\n"
        f"🟢 Faol avto javoblar: "
        f"<b>{active_auto_replies}</b>\n"
        f"1️⃣ Yuborilgan birinchi xabarlar: "
        f"<b>{first_messages_sent}</b>\n\n"
        "Ma’lumotlar faqat statistik hisoblagich "
        "sifatida saqlanadi.",
        reply_markup=statistics_keyboard(),
    )


@router.message(F.text == "🔄 Statistikani yangilash")
async def refresh_statistics(
    message: Message,
) -> None:
    await statistics_menu(message)


@router.message(F.text == "🏠 Bosh menyu")
async def statistics_back(
    message: Message,
) -> None:
    await message.answer(
        "🏠 <b>Bosh menyu</b>",
        reply_markup=main_menu_keyboard(),
    )


__all__ = [
    "router",
    "get_or_create_statistics",
]