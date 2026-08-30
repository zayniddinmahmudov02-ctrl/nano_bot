from aiogram import Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(lambda c: c.data == "telegram_connect")
async def telegram_connect(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "📱 <b>Telegram ulash</b>\n\n"
        "Bu bo‘lim orqali shaxsiy Telegram akkauntingizni "
        "Nano-Botga ulaysiz.\n\n"
        "⚙️ Ulanish tizimi keyingi bosqichda sozlanadi."
    )