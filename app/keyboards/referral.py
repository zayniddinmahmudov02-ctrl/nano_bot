from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def referral_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    builder.button(text="🔗 Referal havolam")
    builder.button(text="📊 Referal statistikasi")
    builder.button(text="🏆 Darajam")
    builder.button(text="🏠 Bosh menyu")

    builder.adjust(2, 1, 1)

    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
    )


def referral_link_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    builder.button(text="📊 Referal statistikasi")
    builder.button(text="🏆 Darajam")
    builder.button(text="🏠 Bosh menyu")

    builder.adjust(2, 1)

    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
    )


def referral_level_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    builder.button(text="🔗 Referal havolam")
    builder.button(text="📊 Referal statistikasi")
    builder.button(text="🏠 Bosh menyu")

    builder.adjust(2, 1)

    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
    )


def referral_back_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    builder.button(text="🏠 Bosh menyu")

    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
    )


__all__ = [
    "referral_keyboard",
    "referral_link_keyboard",
    "referral_level_keyboard",
    "referral_back_keyboard",
]