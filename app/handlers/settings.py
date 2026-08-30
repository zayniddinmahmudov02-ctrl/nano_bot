from aiogram import Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(lambda c: c.data == "settings")
async def settings(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "⚙️ <b>Sozlamalar</b>\n\n"
        "👤 Ism va familiyani tahrirlash\n"
        "🌐 Til\n"
        "ℹ️ Nano-Bot haqida"
    )