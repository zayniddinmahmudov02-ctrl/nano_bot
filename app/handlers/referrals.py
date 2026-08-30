from aiogram import Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(lambda c: c.data == "referrals")
async def referrals(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "👥 <b>Referallar</b>\n\n"
        "Do‘stlaringizni taklif qiling va "
        "avto javoblar limitini oshiring.\n\n"
        "10 referal → 10 ta avto javob\n"
        "30 referal → 20 ta avto javob\n"
        "50 referal → ♾️ avto javob"
    )