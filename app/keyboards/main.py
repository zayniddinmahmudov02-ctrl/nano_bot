from typing import Optional

from aiogram.types import InlineKeyboardMarkup

from app.texts import DEFAULT_LANGUAGE


def main_menu_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> Optional[InlineKeyboardMarkup]:
    """
    MUHIM: Nano-Bot'da chat ichida ko'rsatiladigan doimiy
    "asosiy menyu" (5 ta bo'lim) ENDI UMUMAN MAVJUD EMAS —
    na InlineKeyboard, na ReplyKeyboard ko'rinishida. Asosiy
    navigatsiya FAQAT Telegramning o'z pastki Menu tugmasi
    (Bot Commands: /agent, /assistant, /settings, /info,
    /referrals) orqali amalga oshiriladi.

    Bu funksiya ko'plab handlerlarda xavfsiz zaxira (fallback)
    sifatida `reply_markup=main_menu_keyboard()` ko'rinishida
    ishlatilgani uchun nomi o'zgartirilmasdan saqlab qolindi —
    lekin endi u hech qanday klaviatura qaytarmaydi (`None`),
    shunda foydalanuvchi pastdagi Menu tugmasidan foydalanishga
    yo'naltiriladi.
    """

    return None


__all__ = [
    "main_menu_keyboard",
]
