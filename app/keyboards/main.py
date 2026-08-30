from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📱 Telegram ulash",
                    callback_data="telegram_connect",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔑 Kalit so'zlar",
                    callback_data="keywords",
                ),
                InlineKeyboardButton(
                    text="💬 Javoblar",
                    callback_data="responses",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Suhbatlar",
                    callback_data="conversations",
                ),
                InlineKeyboardButton(
                    text="📈 Statistika",
                    callback_data="statistics",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Sozlamalar",
                    callback_data="settings",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Obuna",
                    callback_data="subscription",
                )
            ],
        ]
    )