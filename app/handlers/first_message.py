from aiogram import Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(lambda c: c.data == "first_message")
async def first_message(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "1️⃣ <b>Birinchi xabar</b>\n\n"
        "Sizga birinchi marta yozgan odamga "
        "yuboriladigan xabar shu yerda sozlanadi."
    )