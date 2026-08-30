from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.keyboards.main import main_menu


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    name = message.from_user.first_name or "foydalanuvchi"

    text = (
        f"👋 <b>Salom, {name}!</b>\n\n"
        "🤖 <b>Nano-Bot</b>ga xush kelibsiz!\n\n"
        "Nano-Bot sizga Telegram'dagi personal "
        "xabarlarni avtomatik boshqarishga yordam beradi.\n\n"
        "🔑 Kalit so'zlarni belgilang\n"
        "💬 Avto-javoblarni yarating\n"
        "📎 Rasm, fayl va linklar qo'shing\n"
        "📊 Barcha suhbatlarni saqlang\n\n"
        "Boshlash uchun quyidagi menyudan foydalaning:"
    )

    await message.answer(
        text,
        reply_markup=main_menu(),
    )