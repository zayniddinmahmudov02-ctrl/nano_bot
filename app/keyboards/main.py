from aiogram.types import InlineKeyboardMarkup

from app.keyboards.nano import nano_main_menu_keyboard
from app.texts import DEFAULT_LANGUAGE


def main_menu_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    """
    Nano-Bot asosiy menyusi.

    MUHIM: bu funksiya ataylab saqlab qolindi, chunki ko'plab
    handlerlarda xavfsiz zaxira (fallback) sifatida
    `reply_markup=main_menu_keyboard()` ko'rinishida ishlatiladi.
    Endi u INLINE Bosh menyuni (nano_main_menu_keyboard) qaytaradi
    — shu orqali barcha mavjud chaqiruv joylari boshqa hech narsa
    o'zgartirmasdan avtomatik ravishda inline'ga o'tadi.

    Reply-keyboard (ReplyKeyboardMarkup/KeyboardButton) endi
    loyihaning bosh menyusi uchun umuman ishlatilmaydi.
    """

    return nano_main_menu_keyboard(lang)


__all__ = [
    "main_menu_keyboard",
]
