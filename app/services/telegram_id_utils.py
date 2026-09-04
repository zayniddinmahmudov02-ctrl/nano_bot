from __future__ import annotations

# ============================================================
# Telethon (MTProto) "bare" channel ID va Bot API "chat_id"
# formatlari orasidagi MARKAZLASHTIRILGAN, YAGONA konvertatsiya.
# ============================================================
#
# ROOT CAUSE (real production xatosi orqali tasdiqlangan):
# Telethon `channel.id` HAR DOIM musbat, "bare" raqam (masalan
# 3932438193). Bot API esa xuddi shu kanal uchun MANFIY,
# "-100" bilan boshlanadigan chat_id kutadi (masalan
# -1003932438193). Bular bitta ID'ning ikki "ko'rinishi" —
# lekin bir-birining o'rniga to'g'ridan-to'g'ri ISHLATIB
# BO'LMAYDI. Bare Telethon ID'ni `bot.copy_message(chat_id=...)`
# ga to'g'ridan-to'g'ri berish "Bad Request: chat not found"
# xatosiga olib keladi — bu xato aynan shu sabab yuz bergan edi.
#
# Formula — Telegram ekotizimida keng qo'llaniladigan standart
# konvertatsiya: bot_api_chat_id = -(10**12 + telethon_channel_id)

_CHANNEL_ID_OFFSET = 10 ** 12


def to_bot_api_chat_id(value: int) -> int:
    """
    Berilgan qiymatni Bot API `chat_id` formatiga (manfiy,
    -100xxxxxxxxxx) keltiradi.

    MUHIM (eski DB qatorlari bilan xavfsiz moslik — hech qanday
    destruktiv migratsiyasiz): agar `value` ALLAQACHON manfiy
    bo'lsa (demak u allaqachon Bot API formatida saqlangan),
    o'zgarishsiz qaytariladi. Musbat bo'lsa (eski, "bare"
    Telethon formatida saqlangan qator) — konvertatsiya qilinadi.
    Ikki format belgisi (musbat/manfiy) hech qachon bir-biriga
    aralashmaydi, shu sabab bu ANIQ va xavfsiz.
    """

    if value < 0:
        return value

    return -(_CHANNEL_ID_OFFSET + value)


def to_telethon_channel_id(value: int) -> int:
    """
    Berilgan qiymatni Telethon uchun "bare" (musbat) channel ID
    formatiga keltiradi. `to_bot_api_chat_id` bilan bir xil
    mantiqda — eski (musbat, allaqachon "bare") qatorlar bilan
    ham to'g'ri ishlaydi.
    """

    if value > 0:
        return value

    return -value - _CHANNEL_ID_OFFSET


__all__ = [
    "to_bot_api_chat_id",
    "to_telethon_channel_id",
]
