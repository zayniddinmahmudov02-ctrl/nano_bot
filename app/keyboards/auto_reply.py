from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def auto_reply_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    builder.button(text="➕ Avto javob qo‘shish")
    builder.button(text="📋 Avto javoblarim")
    builder.button(text="🏠 Bosh menyu")

    builder.adjust(2, 1)

    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
    )


def auto_reply_back_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    builder.button(text="⬅️ Orqaga")
    builder.button(text="🏠 Bosh menyu")

    builder.adjust(2)

    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
    )


def auto_reply_cancel_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    builder.button(text="❌ Bekor qilish")

    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
    )


__all__ = [
    "auto_reply_keyboard",
    "auto_reply_back_keyboard",
    "auto_reply_cancel_keyboard",
]