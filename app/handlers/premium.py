import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.database import AsyncSessionLocal
from app.database.models import Subscription
from app.keyboards.main import main_menu_keyboard

from sqlalchemy import select

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == "💎 Premium")
async def premium_menu(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user_id
            )
        )

        subscription = (
            result.scalar_one_or_none()
        )

    if subscription:
        status = subscription.status
    else:
        status = "free"

    await message.answer(
        "💎 <b>Nano-Bot Premium</b>\n\n"
        "Hozircha Nano-Bot barcha "
        "foydalanuvchilar uchun bepul.\n\n"
        "💰 Keyinchalik Premium:\n"
        "<b>$1 / oy</b>\n\n"
        f"📌 Joriy holat: <b>{status}</b>\n\n"
        "Premium tizimi keyingi bosqichda "
        "to‘lov tizimi bilan ulanadi.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == "⬅️ Orqaga")
async def premium_back(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    await message.answer(
        "🏠 <b>Asosiy menyu</b>",
        reply_markup=main_menu_keyboard(),
    )