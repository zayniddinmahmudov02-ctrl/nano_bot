from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def telegram_menu_keyboard(
    connected: bool = False,
) -> ReplyKeyboardMarkup:
    """
    Telegram ulash bo‘limi klaviaturasi.
    """

    if connected:
        return ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(
                        text="🔌 Telegramni uzish"
                    ),
                ],
                [
                    KeyboardButton(
                        text="🔄 Holatni tekshirish"
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

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Telegram ulash"
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


def telegram_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Telegram ulash jarayonini bekor qilish.
    """

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