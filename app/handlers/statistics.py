from aiogram import Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(lambda c: c.data == "statistics")
async def statistics(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "📊 <b>Statistika</b>\n\n"
        "👥 Javob berilgan odamlar: 0\n"
        "🤖 Avto javoblar: 0\n\n"
        "Suhbatlar mazmuni saqlanmaydi."
    )