from aiogram import Router
from aiogram.types import CallbackQuery

from app.config import is_admin

router = Router()


@router.callback_query(lambda c: c.data == "admin")
async def admin(callback: CallbackQuery):
    if not callback.from_user:
        return

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Ruxsat yo‘q.",
            show_alert=True,
        )
        return

    await callback.answer()

    await callback.message.answer(
        "👑 <b>Admin panel</b>\n\n"
        "👥 Umumiy userlar: 0\n"
        "🤖 Umumiy avto javoblar: 0\n\n"
        "Admin statistikasi keyingi bosqichda ulanadi."
    )