from aiogram import F, Router
from aiogram.types import CallbackQuery


router = Router()


@router.callback_query(F.data == "settings")
async def settings_handler(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    await callback.message.edit_text(
        "⚙️ <b>Sozlamalar</b>\n\n"
        "Bu bo'lim tez orada to'ldiriladi."
    )


@router.callback_query(F.data == "statistics")
async def statistics_handler(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    await callback.message.edit_text(
        "📊 <b>Statistika</b>\n\n"
        "Hozircha statistika mavjud emas."
    )


@router.callback_query(F.data == "conversations")
async def conversations_handler(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    await callback.message.edit_text(
        "💬 <b>Suhbatlar</b>\n\n"
        "Hozircha suhbatlar mavjud emas."
    )


@router.callback_query(F.data == "subscription")
async def subscription_handler(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    await callback.message.edit_text(
        "💳 <b>Nano-Bot obunasi</b>\n\n"
        "🎁 7 kun — bepul\n"
        "💵 Keyin — $1 / oy"
    )


@router.callback_query(F.data == "telegram_connect")
async def telegram_connect_handler(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    await callback.message.edit_text(
        "📱 <b>Telegram akkauntini ulash</b>\n\n"
        "Bu bo'lim orqali shaxsiy Telegram "
        "akkauntingizni Nano-Bot'ga ulaysiz.\n\n"
        "Keyingi bosqichda ulash tizimini yaratamiz."
    )


@router.callback_query(F.data == "keywords")
async def keywords_handler(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    await callback.message.edit_text(
        "🔑 <b>Kalit so'zlar</b>\n\n"
        "Bu yerda kalit so'zlar va ularga "
        "bog'langan javoblarni yaratamiz."
    )


@router.callback_query(F.data == "responses")
async def responses_handler(
    callback: CallbackQuery,
) -> None:
    await callback.answer()

    await callback.message.edit_text(
        "💬 <b>Javoblar</b>\n\n"
        "Bu yerda avtomatik javoblar va "
        "response flow'lar yaratiladi."
    )