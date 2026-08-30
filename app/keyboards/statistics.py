from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def statistics_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🔄 Yangilash"
                ),
            ],
            [
                KeyboardButton(
                    text="⬅️ Orqaga"
                ),
            ],
        ],
        resize_keyboard=True,
    )