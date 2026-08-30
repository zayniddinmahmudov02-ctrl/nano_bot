from aiogram import Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(lambda c: c.data == "auto_replies")
async def auto_replies(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🤖 <b>Avto javoblar</b>\n\n"
        "Bu yerda kalit so‘zlarga mos avtomatik "
        "javoblar yaratiladi.\n\n"
        "➕ Avto xabar qo‘shish — keyingi bosqichda."
    )