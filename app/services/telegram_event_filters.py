from __future__ import annotations

import logging

from telethon.tl.types import User as TelethonUser

logger = logging.getLogger(__name__)


def is_private_incoming_event(event) -> bool:
    """
    Telethon event obyektining o'zidan (tarmoqqa chiqmasdan)
    tekshiriladigan, ARZON/SINXRON filter.

    Guruh/superguruh/kanal xabarlari uchun `False` qaytaradi —
    shu orqali ular hatto `_handle_message` chaqirilishidan
    OLDIN, event obuna darajasida ("func=" filtri sifatida)
    chetlab o'tiladi.

    MUHIM: bu funksiya faqat "private chat"ligini tekshiradi —
    sender bot yoki haqiqiy User ekanligini emas (buning uchun
    `event.get_sender()` kerak, u tarmoqqa chiqadi va shuning
    uchun faqat async `validate_private_user_event()` ichida
    tekshiriladi).
    """

    if getattr(event, "out", False):
        return False

    is_private = getattr(event, "is_private", False)

    return bool(is_private)


async def validate_private_user_event(
    event,
    *,
    log_prefix: str,
) -> bool:
    """
    Auto Reply va First Message uchun UMUMIY, qat'iy filter.

    Quyidagilarning barchasi bajarilgandagina True qaytaradi:
    - xabar "out" (o'zimiz yuborgan) emas
    - chat aynan PRIVATE (1-to-1) — guruh/superguruh/kanal emas
    - xabar service (action) xabar emas
    - yuboruvchi (sender) haqiqiy Telegram User — bot, Chat
      yoki Channel obyekti emas

    MUHIM ARXITEKTURA QOIDASI:
    Bu funksiya har ikkala Engine'ning `_handle_message()`
    ichida — DB so'rovlaridan va keyword matchingdan OLDIN —
    chaqiriladi. Shu tufayli guruh/kanal/bot xabarlari uchun
    hech qanday keraksiz DB so'rovi yoki Auto Reply/First
    Message yuborilishi amalga oshirilmaydi.

    Bu funksiya ichki "processing" funksiyasi hisoblanadi —
    kelajakda boshqa joydan (masalan test yoki alohida
    chaqiruv orqali) `_handle_message()` chaqirilsa ham, bu
    tekshiruv har doim qayta bajariladi (faqat Telethon event
    obuna filtriga tayanilmaydi).

    Xavfsiz DEBUG log yoziladi — telefon, OTP, 2FA, session,
    token, parol yoki xabar matni HECH QACHON logga chiqarilmaydi.
    """

    if getattr(event, "out", False):
        logger.debug(
            "%s ignored: self message",
            log_prefix,
        )
        return False

    if not bool(getattr(event, "is_private", False)):
        logger.debug(
            "%s ignored: non-private chat",
            log_prefix,
        )
        return False

    message = getattr(event, "message", None)

    if message is None:
        return False

    if getattr(message, "action", None) is not None:
        logger.debug(
            "%s ignored: service message",
            log_prefix,
        )
        return False

    try:
        sender = await event.get_sender()
    except Exception:
        logger.exception(
            "%s: sender ma'lumotini olishda xatolik.",
            log_prefix,
        )
        return False

    if sender is None:
        logger.debug(
            "%s ignored: non-user sender",
            log_prefix,
        )
        return False

    if getattr(sender, "bot", False):
        logger.debug(
            "%s ignored: bot sender",
            log_prefix,
        )
        return False

    if not isinstance(sender, TelethonUser):
        logger.debug(
            "%s ignored: non-user sender",
            log_prefix,
        )
        return False

    return True


__all__ = [
    "is_private_incoming_event",
    "validate_private_user_event",
]
