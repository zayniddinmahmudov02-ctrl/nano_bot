from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import AsyncSessionLocal
from app.keyboards.main import main_menu
from app.services.user_service import get_or_create_user


router = Router()


@router.message(CommandStart())
async def start_handler(
    message: Message,
    command: CommandObject,
) -> None:

    async with AsyncSessionLocal() as db:

        user, created = await get_or_create_user(
            db=db,
            telegram_user=message.from_user,
            referral_code=command.args,
        )

    name = (
        message.from_user.first_name
        or "Foydalanuvchi"
    )

    if created:
        text = (
            f"👋 <b>Salom, {name}!</b>\n\n"
            "🤖 <b>Nano-Bot</b>ga xush kelibsiz!\n\n"
            "Nano-Bot Telegram'dagi shaxsiy "
            "xabarlaringizga kalit so'zlar orqali "
            "avtomatik javob beradi.\n\n"
            "🎁 Sizga <b>7 kunlik bepul foydalanish</b> "
            "berildi.\n\n"
            "Boshlash uchun Telegram akkauntingizni "
            "ulang:"
        )

    else:
        text = (
            f"👋 <b>Qaytganingizdan xursandmiz, "
            f"{name}!</b>\n\n"
            "Nano-Bot tayyor."
        )

    await message.answer(
        text,
        reply_markup=main_menu(),
    )