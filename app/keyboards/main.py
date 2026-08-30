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
                    text="🤖 Avto javoblar",
                    callback_data="auto_replies",
                ),
                InlineKeyboardButton(
                    text="1️⃣ Birinchi xabar",
                    callback_data="first_message",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👥 Referallar",
                    callback_data="referrals",
                ),
                InlineKeyboardButton(
                    text="📊 Statistika",
                    callback_data="statistics",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🌐 Til",
                    callback_data="language",
                ),
                InlineKeyboardButton(
                    text="💎 Premium",
                    callback_data="premium",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Sozlamalar",
                    callback_data="settings",
                )
            ],
        ]
    )