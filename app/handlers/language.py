from aiogram import Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(lambda c: c.data == "language")
async def language(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🌐 <b>Tilni tanlang</b>\n\n"
        "🇺🇿 O‘zbekcha\n"
        "🇷🇺 Русский\n"
        "🇬🇧 English\n"
        "🇩🇪 Deutsch"
    )