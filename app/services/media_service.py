from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramEntityTooLarge
from aiogram.types import Message as BotMessage
from telethon import TelegramClient
from telethon.tl.types import MessageMediaWebPage, PeerChannel

logger = logging.getLogger(__name__)

SUPPORTED_MESSAGE_TYPES = (
    "text",
    "photo",
    "video",
    "document",
    "audio",
    "voice",
    "animation",
)


# ============================================================
# DETECT INCOMING POST CONTENT (Bot API side — faqat TUR
# aniqlash va UI uchun, hech qachon fayl yuklab olish uchun
# ISHLATILMAYDI)
# ============================================================

def detect_post_content(
    message: BotMessage,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    aiogram Message'dan post TURINI va caption/textini aniqlaydi.

    MUHIM: bu funksiya faqat UI (qo'llab-quvvatlanmaydigan
    turlarni erta rad etish, "message_type" ustunini DB'ga
    yozish) uchun ishlatiladi. Qaytarilgan `file_id` ENDI
    Storage Channel'ga saqlash uchun ISHLATILMAYDI (pastdagi
    `send_post_to_storage`ga qarang) — Bot API'ning ~20MB
    yuklab olish chegarasidan butunlay qochish uchun asosiy
    saqlash yo'li endi Telethon (foydalanuvchi akkaunti,
    MTProto) orqali ishlaydi.

    Qaytaradi:
    (message_type, text_or_caption, file_id, file_name)
    """

    if message.photo:
        return (
            "photo",
            message.caption,
            message.photo[-1].file_id,
            None,
        )

    if message.video:
        return (
            "video",
            message.caption,
            message.video.file_id,
            message.video.file_name,
        )

    if message.document:
        return (
            "document",
            message.caption,
            message.document.file_id,
            message.document.file_name,
        )

    if message.audio:
        return (
            "audio",
            message.caption,
            message.audio.file_id,
            message.audio.file_name,
        )

    if message.voice:
        return (
            "voice",
            message.caption,
            message.voice.file_id,
            None,
        )

    if message.animation:
        return (
            "animation",
            message.caption,
            message.animation.file_id,
            message.animation.file_name,
        )

    if message.text:
        return (
            "text",
            message.text,
            None,
            None,
        )

    return None, None, None, None


def is_part_of_media_group(message: BotMessage) -> bool:
    """
    Xabar albom (media group)ning bir qismimi — aniqlaydi.

    MUHIM: hozirgi arxitektura Auto Reply/First Message uchun
    bitta post = bitta storage_message_id saqlaydi. Albomning
    faqat BIRINCHI kelgan elementi shu post sifatida saqlanadi
    (xavfsiz individual-media fallback) — qolgan albom
    elementlari e'tiborsiz qoldiriladi, xatolik chiqarilmaydi.
    """

    return bool(message.media_group_id)


class StoragePostTooLarge(Exception):
    """
    Fayl Telegram MTProto (Telethon) orqali ham nusxalab
    bo'lmaydigan darajada katta yoki Telegram serveri fayl
    qismlarini rad etdi.

    MUHIM: bu ENDI Bot API cheklovi emas — asosiy saqlash yo'li
    (pastga qarang) hech qachon Bot API orqali fayl yuklab
    olmaydi, shu sabab standart ~20MB Bot API chegarasi
    umuman qo'llanilmaydi. Bu faqat Telegram MTProto darajasidagi
    (juda kam uchraydigan) o'ta katta fayl xatosi uchun xavfsizlik
    to'ri sifatida saqlanadi.
    """


# ============================================================
# ASOSIY OQIM: Bot API server-side `copyMessage` orqali source
# xabarni to'g'ridan-to'g'ri Storage Channel'ga nusxalash
# ============================================================
#
# MUHIM ARXITEKTURA QOIDASI (2-marta ko'rib chiqilgan):
# Ilgari bu yerda source xabar foydalanuvchining Telethon
# sessiyasi orqali, bot bilan foydalanuvchi o'rtasidagi chatdan
# `get_messages(bot_entity, ids=source_message_id)` bilan QAYTA
# qidirilar edi. Bu YONDASHUV ISHONCHSIZ bo'lib chiqdi — amalda
# "Source xabar Telethon orqali topilmadi" xatosiga olib keldi,
# chunki Bot API orqali botga kelgan xabar har doim ham userning
# MTProto (Telethon) sessiyasi nuqtai nazaridan xuddi shu
# `message_id` bilan, xuddi shu vaqtda ko'rinadigan/qayta
# o'qiladigan bo'lib chiqavermaydi.
#
# YANGI (to'g'ri) arxitektura: source xabar botning O'ZIGA Bot
# API orqali kelgan bo'lsa, uni qayta topish/yuklab olish shart
# EMAS — bot buni Telegram serverining o'ziga "shu xabarni
# boshqa chatga (Storage Channel'ga) ham joylashtir" deb
# ko'rsatma beruvchi `Bot.copy_message()` bilan hal qiladi. Bu —
# `forwardMessage`ga o'xshash, lekin "Forwarded from" havolasisiz
# — TO'LIQ SERVER-SIDE amal: bot fayl BAYTLARINI hech qachon
# o'zi yuklab olmaydi va qayta yuklamaydi, shu sabab standart Bot
# API ~20MB yuklab olish chegarasi bu yerda UMUMAN qo'llanilmaydi.
#
# Buning uchun BITTA YANGI TALAB bor: bot Storage Channel'ga
# a'zo va admin (kamida "xabar joylash" huquqi bilan) bo'lishi
# kerak — aks holda `copyMessage` maqsad chatga yoza olmaydi
# (bu huquq `storage_channel_service.py`da channel yaratilganda/
# qayta yaratilganda avtomatik beriladi).
#
# Telethon bu funksiyada ENDI FAQAT bitta narsa uchun ishlatiladi:
# copy muvaffaqiyatli bo'lgandan KEYIN, Storage Channel'ning
# O'ZIDA (bot emas, foydalanuvchi chatida emas) xabar haqiqatan
# mavjudligini tasdiqlash — bu Telethon foydalanuvchi o'zi
# yaratgan/egalik qiladigan kanalni o'qiganidek ishonchli.

async def send_post_to_storage(
    *,
    bot: Bot,
    telethon_client: TelegramClient,
    storage_chat_id: int,
    source_chat_id: int,
    source_message_id: int,
    content_type: Optional[str] = None,
    user_id: Optional[int] = None,
    account_id: Optional[int] = None,
) -> Optional[int]:
    """
    Foydalanuvchi botga yuborgan source xabarni Bot API
    `copy_message` (server-side) orqali to'g'ridan-to'g'ri
    foydalanuvchining Storage Channel'iga nusxalaydi.

    Qaytaradi: Storage Channel'dagi YANGI xabar ID'si (HECH
    QACHON `source_message_id` emas — bular ikki butunlay boshqa
    chatdagi ikki mustaqil xabar), yoki xatolik/topilmasa None.

    MUHIM (post-copy validation): Bot API'dan qaytgan "nusxalandi"
    javobiga ko'r-ko'rona ishonilmaydi — copy Storage Channel'ga
    yuborilgandan DARHOL KEYIN Telethon orqali `get_messages()`
    bilan qayta o'qib, HAQIQATAN ham u yerda mavjudligi
    tasdiqlanadi. Agar tasdiqlanmasa — fake/soxta ID hech qachon
    qaytarilmaydi va hech qachon DB'ga yozilmaydi.

    MUHIM (diagnostika): har bir bosqich ALOHIDA try/except bilan
    o'ralgan va aniq bosqich nomi + exception TURI (xabar
    mazmuni/token/session'siz) bilan log yoziladi — "Postni
    saqlashda xatolik" degan umumiy xabar ortida endi aniq
    texnik sabab har doim serverga yoziladi.
    """

    log_ctx = (
        "user_id=%s, account_id=%s, source_chat_id=%s, "
        "source_message_id=%s, storage_chat_id=%s, content_type=%s"
    )
    log_args = (
        user_id,
        account_id,
        source_chat_id,
        source_message_id,
        storage_chat_id,
        content_type,
    )

    logger.info("storage_save SOURCE: (" + log_ctx + ")", *log_args)

    # ------------------------------------------------------
    # 1-BOSQICH: Bot API server-side `copyMessage` — source
    # xabar botning javobgarligida, fayl baytlarini bot hech
    # qachon o'zi yuklab olmaydi/qayta yuklamaydi.
    # ------------------------------------------------------
    try:
        copied = await bot.copy_message(
            chat_id=storage_chat_id,
            from_chat_id=source_chat_id,
            message_id=source_message_id,
        )
    except TelegramEntityTooLarge as exc:
        logger.error(
            "storage_save FAILED [copy_message]: fayl juda katta: "
            "%s: %s (" + log_ctx + ")",
            type(exc).__name__,
            exc,
            *log_args,
        )
        raise StoragePostTooLarge() from None
    except TelegramAPIError as exc:
        logger.error(
            "storage_save FAILED [copy_message]: Telegram Bot API "
            "xatosi: %s: %s (" + log_ctx + ")",
            type(exc).__name__,
            exc,
            *log_args,
            exc_info=exc,
        )
        return None
    except Exception as exc:
        logger.error(
            "storage_save FAILED [copy_message]: %s: %s (" + log_ctx + ")",
            type(exc).__name__,
            exc,
            *log_args,
            exc_info=exc,
        )
        return None

    storage_message_id = int(copied.message_id)

    logger.info(
        "storage_save COPY_OK: storage_message_id=%s, copy_success=True ("
        + log_ctx + ")",
        storage_message_id,
        *log_args,
    )

    # ------------------------------------------------------
    # 2-BOSQICH: Storage Channel entity'sini Telethon orqali
    # topish — FAQAT tasdiqlash (validation) uchun, source
    # xabarni qidirish uchun EMAS.
    # ------------------------------------------------------
    try:
        storage_entity = await telethon_client.get_entity(
            PeerChannel(storage_chat_id)
        )
    except Exception as exc:
        logger.error(
            "storage_save FAILED [resolve_storage_entity]: "
            "%s: %s, storage_message_id=%s (" + log_ctx + ")",
            type(exc).__name__,
            exc,
            storage_message_id,
            *log_args,
            exc_info=exc,
        )
        return None

    # ------------------------------------------------------
    # 3-BOSQICH: post-copy validation — copy muvaffaqiyatli
    # "qaytgan" bo'lsa ham, DARHOL qayta o'qib, xabar haqiqatan
    # Storage Channel'da mavjudligini tasdiqlaymiz. Tasdiqlanmasa
    # — DB'ga HECH QACHON fake ID yozilmaydi.
    # ------------------------------------------------------
    try:
        verified = await telethon_client.get_messages(
            storage_entity,
            ids=storage_message_id,
        )
    except Exception as exc:
        logger.error(
            "storage_save FAILED [verify]: %s: %s, "
            "storage_message_id=%s (" + log_ctx + ")",
            type(exc).__name__,
            exc,
            storage_message_id,
            *log_args,
            exc_info=exc,
        )
        return None

    if verified is None:
        logger.error(
            "storage_save FAILED [verify]: post-copy validation "
            "muvaffaqiyatsiz — Storage'da tasdiqlanmadi, "
            "storage_message_id=%s (" + log_ctx + ")",
            storage_message_id,
            *log_args,
        )
        return None

    logger.info(
        "storage_save OK: storage_message_id=%s, copy_success=True ("
        + log_ctx + ")",
        storage_message_id,
        *log_args,
    )

    return storage_message_id


# ============================================================
# SEND STORED POST AS A NEW MESSAGE (NOT FORWARD)
# ============================================================

@dataclass
class SendStoredPostResult:
    success: bool

    # MUHIM: aynan "topilmadi" (Storage Channel yoki undagi
    # xabar o'chirilgan/kirish yo'q) holatini boshqa (vaqtinchalik/
    # texnik) xatolardan ajratib beradi — chaqiruvchi shu orqali
    # Auto Reply/First Message record'ini "NEEDS_RESAVE" deb
    # belgilashi kerakmi yoki yo'qmi hal qiladi.
    not_found: bool = False


async def send_stored_post(
    *,
    telethon_client: TelegramClient,
    storage_chat_id: int,
    storage_message_id: int,
    target_chat_id: int,
    user_id: Optional[int] = None,
    account_id: Optional[int] = None,
) -> SendStoredPostResult:
    """
    Storage Channel'dagi postni forward qilmasdan, yangi xabar
    sifatida target chatga yuboradi.

    Agar storage message/kanal o'chirilgan bo'lsa yoki topilmasa,
    xatolik ko'tarmaydi — `not_found=True` bilan qaytaradi va
    xavfsiz log yozadi.
    """

    try:
        storage_entity = await telethon_client.get_entity(
            PeerChannel(storage_chat_id)
        )
    except Exception:
        # MUHIM: aynan shu bosqichda (entity/kanalning o'zini
        # topish) muvaffaqiyatsizlik — kanal o'chirilgan yoki
        # kirish yo'qolganini bildiradi. Bu aniq "not_found"
        # holati (NEEDS_RESAVE uchun signal) — vaqtinchalik
        # tarmoq xatosidan farqli.
        logger.warning(
            "Storage kanaliga kirib bo'lmadi (o'chirilgan "
            "bo'lishi mumkin): chat_id=%s",
            storage_chat_id,
        )
        return SendStoredPostResult(success=False, not_found=True)

    try:
        stored_message = await telethon_client.get_messages(
            storage_entity,
            ids=storage_message_id,
        )

        found = stored_message is not None

        logger.info(
            "storage_get: user_id=%s, account_id=%s, "
            "storage_chat_id=%s, storage_message_id=%s, "
            "found=%s",
            user_id,
            account_id,
            storage_chat_id,
            storage_message_id,
            found,
        )

        if not found:
            return SendStoredPostResult(
                success=False,
                not_found=True,
            )

        has_real_media = (
            stored_message.media is not None
            and not isinstance(
                stored_message.media, MessageMediaWebPage
            )
        )

        if has_real_media:
            await telethon_client.send_file(
                target_chat_id,
                stored_message.media,
                caption=stored_message.message or None,
            )
            return SendStoredPostResult(success=True)

        if stored_message.message:
            await telethon_client.send_message(
                target_chat_id,
                stored_message.message,
            )
            return SendStoredPostResult(success=True)

        logger.warning(
            "Storage post bo'sh: chat_id=%s message_id=%s",
            storage_chat_id,
            storage_message_id,
        )
        return SendStoredPostResult(success=False, not_found=True)

    except Exception:
        # MUHIM: bu bosqichda entity (kanal) allaqachon
        # muvaffaqiyatli topilgan edi — shu sabab bu yerdagi
        # xatolik ko'pincha VAQTINCHALIK/texnik muammo (masalan
        # tarmoq), doimiy "kanal o'chirilgan" holati EMAS. Shu
        # sabab `not_found=False` — Auto Reply/First Message
        # bekorga NEEDS_RESAVE deb belgilanmaydi.
        logger.exception(
            "Storage postni yuborishda xatolik: "
            "chat_id=%s message_id=%s target=%s",
            storage_chat_id,
            storage_message_id,
            target_chat_id,
        )
        return SendStoredPostResult(success=False, not_found=False)


__all__ = [
    "SUPPORTED_MESSAGE_TYPES",
    "StoragePostTooLarge",
    "SendStoredPostResult",
    "detect_post_content",
    "is_part_of_media_group",
    "send_post_to_storage",
    "send_stored_post",
]
