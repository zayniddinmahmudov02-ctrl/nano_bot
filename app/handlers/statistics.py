import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import Statistics
from app.keyboards.main import main_menu_keyboard
from app.keyboards.statistics import statistics_keyboard

logger = logging.getLogger(__name__)

router = Router()


async def get_or_create_statistics(
    user_id: int,
) -> Statistics:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Statistics).where(
                Statistics.user_id == user_id
            )
        )

        statistics = result.scalar_one_or_none()

        if statistics:
            return statistics

        statistics = Statistics(
            user_id=user_id,
            people_replied=0,
            total_auto_replies=0,
            today_replies=0,
            month_replies=0,
        )

        session.add(statistics)
        await session.commit()
        await session.refresh(statistics)

        return statistics


async def get_statistics(
    user_id: int,
) -> dict:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Statistics).where(
                Statistics.user_id == user_id
            )
        )

        statistics = result.scalar_one_or_none()

        if not statistics:
            return {
                "people_replied": 0,
                "total_auto_replies": 0,
                "today_replies": 0,
                "month_replies": 0,
            }

        return {
            "people_replied": statistics.people_replied,
            "total_auto_replies": (
                statistics.total_auto_replies
            ),
            "today_replies": statistics.today_replies,
            "month_replies": statistics.month_replies,
        }


@router.message(F.text == "📊 Statistika")
async def statistics_menu(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    data = await get_statistics(
        message.from_user.id
    )

    await message.answer(
        "📊 <b>Statistika</b>\n\n"
        f"👥 Javob berilgan odamlar: "
        f"<b>{data['people_replied']}</b>\n"
        f"🤖 Avto javoblar: "
        f"<b>{data['total_auto_replies']}</b>\n\n"
        f"📅 Bugungi javoblar: "
        f"<b>{data['today_replies']}</b>\n"
        f"🗓 Oylik javoblar: "
        f"<b>{data['month_replies']}</b>\n\n"
        "🔒 Suhbatlar mazmuni saqlanmaydi.",
        reply_markup=statistics_keyboard(),
    )


@router.message(F.text == "🔄 Yangilash")
async def refresh_statistics(
    message: Message,
) -> None:
    data = await get_statistics(
        message.from_user.id
    )

    await message.answer(
        "📊 <b>Statistika yangilandi</b>\n\n"
        f"👥 Javob berilgan odamlar: "
        f"<b>{data['people_replied']}</b>\n"
        f"🤖 Avto javoblar: "
        f"<b>{data['total_auto_replies']}</b>\n\n"
        f"📅 Bugungi javoblar: "
        f"<b>{data['today_replies']}</b>\n"
        f"🗓 Oylik javoblar: "
        f"<b>{data['month_replies']}</b>\n\n"
        "🔒 Suhbatlar mazmuni saqlanmaydi.",
        reply_markup=statistics_keyboard(),
    )


@router.message(F.text == "⬅️ Orqaga")
async def statistics_back(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "🏠 <b>Asosiy menyu</b>",
        reply_markup=main_menu_keyboard(),
    )