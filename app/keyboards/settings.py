from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def settings_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="👤 Ism va familiya"
                ),
            ],
            [
                KeyboardButton(
                    text="🌐 Tilni o‘zgartirish"
                ),
            ],
            [
                KeyboardButton(
                    text="ℹ️ Nano-Bot haqida"
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


def name_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="❌ Bekor qilish"
                ),
            ],
        ],
        resize_keyboard=True,
    )


def settings_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="❌ Bekor qilish"
                ),
            ],
        ],
        resize_keyboard=True,
    )


def settings_back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🏠 Bosh menyu"
                ),
            ],
        ],
        resize_keyboard=True,
    )