from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Nano-Bot asosiy menyusi.
    """

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Telegram ulash"
                ),
            ],
            [
                KeyboardButton(
                    text="🤖 Avto javoblar"
                ),
                KeyboardButton(
                    text="1️⃣ Birinchi xabar"
                ),
            ],
            [
                KeyboardButton(
                    text="👥 Referallar"
                ),
                KeyboardButton(
                    text="📊 Statistika"
                ),
            ],
            [
                KeyboardButton(
                    text="🌐 Til"
                ),
                KeyboardButton(
                    text="💎 Premium"
                ),
            ],
            [
                KeyboardButton(
                    text="⚙️ Sozlamalar"
                ),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Menyudan tanlang...",
    )


def back_keyboard() -> ReplyKeyboardMarkup:
    """
    Orqaga qaytish tugmasi.
    """

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="⬅️ Orqaga"
                ),
            ],
        ],
        resize_keyboard=True,
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Jarayonni bekor qilish tugmasi.
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


def back_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Orqaga yoki bekor qilish.
    """

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="⬅️ Orqaga"
                ),
                KeyboardButton(
                    text="❌ Bekor qilish"
                ),
            ],
        ],
        resize_keyboard=True,
    )