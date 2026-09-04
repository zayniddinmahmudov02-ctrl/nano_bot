from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

STORAGE_DELETED_TEXT = (
    "⚠️ Sizning Xotira kanalingiz o'chirib yuborilgan.\n\n"
    "Auto Reply xabarlarini saqlash va yuborishni davom "
    "ettirish uchun yangi Xotira kanali ochamizmi?"
)

STORAGE_RECREATE_FAILED_TEXT = (
    "❌ Yangi Xotira kanalini ochib bo'lmadi.\n\n"
    "Birozdan keyin qayta urinib ko'ring yoki Telegram "
    "akkauntingizni qayta ulang."
)

STORAGE_RECREATED_TEXT = (
    "✅ Yangi Xotira kanali ochildi.\n\n"
    "Iltimos, postingizni qaytadan yuboring."
)

STORAGE_RECREATE_CANCELLED_TEXT = "❌ Bekor qilindi."


def storage_recreate_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ha, yangi kanal ochish",
                    callback_data="storage:recreate:confirm",
                ),
                InlineKeyboardButton(
                    text="❌ Yo'q",
                    callback_data="storage:recreate:cancel",
                ),
            ],
        ]
    )


__all__ = [
    "STORAGE_DELETED_TEXT",
    "STORAGE_RECREATE_FAILED_TEXT",
    "STORAGE_RECREATED_TEXT",
    "STORAGE_RECREATE_CANCELLED_TEXT",
    "storage_recreate_confirm_keyboard",
]
