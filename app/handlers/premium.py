from aiogram import Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(lambda c: c.data == "premium")
async def premium(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "💎 <b>Premium</b>\n\n"
        "Hozircha Nano-Bot barcha foydalanuvchilar "
        "uchun bepul.\n\n"
        "💰 Keyinchalik Premium — $1/oy."
    )