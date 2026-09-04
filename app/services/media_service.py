from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

from aiogram.types import Message as BotMessage
from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl.types import MessageMediaWebPage, PeerChannel

from app.config import BOT_USERNAME

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
# ASOSIY OQIM: Telethon (MTProto) orqali source xabarni topish
# ============================================================
#
# MUHIM ARXITEKTURA QOIDASI:
# Foydalanuvchi Auto Reply/First Message uchun postni BOTGA
# (Bot API orqali) yuboradi — lekin shu XABAR aslida foydalanuvchi
# akkauntining o'zi va bot o'rtasidagi ODDIY Telegram chati (bot —
# MTProto nuqtai nazaridan oddiy "user" hisoblanadi). Shu sababli
# foydalanuvchining ALLAQACHON ULANGAN Telethon sessiyasi xuddi
# shu xabarni — xuddi shu `message_id` bilan — MTProto orqali
# to'g'ridan-to'g'ri o'qiy oladi, Bot API'ning `getFile`/
# `bot.download()` yuklab olish yo'lidan (va uning ~20MB
# chegarasidan) BUTUNLAY qochib.
#
# Telegram'ning bitta chatdagi xabar ID'lari BOT API va MTProto
# o'rtasida BIR XIL raqamlash tizimiga ega (ikkalasi ham bitta
# server ma'lumotlariga turli "ko'rinish" xolos) — shu sabab
# `message.message_id` (aiogram) === source_message.id (Telethon)
# aynan bitta chat uchun.
#
# Fayl BAYTLARINING o'zi bu jarayonda HECH QACHON qayta yuklab
# olinmaydi/qayta yuklanmaydi: `send_file(entity, existing_media)`
# faqat Telegram serverining o'ziga "shu allaqachon serverda
# turgan faylni boshqa chatga ham joylashtir" deb ko'rsatma
# beradi — shu sabab hatto juda katta fayllar uchun ham hech
# qanday amaliy hajm chegarasi yo'q.

async def _fetch_bot_chat_message(
    telethon_client: TelegramClient,
    message_id: int,
):
    """
    Foydalanuvchi va bot o'rtasidagi chatdan, xuddi shu
    `message_id`ga ega xabarni Telethon orqali oladi.
    """

    bot_entity = await telethon_client.get_entity(BOT_USERNAME)

    return await telethon_client.get_messages(
        bot_entity,
        ids=message_id,
    )


async def send_post_to_storage(
    *,
    telethon_client: TelegramClient,
    storage_chat_id: int,
    source_message_id: int,
    fallback_text: Optional[str] = None,
    user_id: Optional[int] = None,
    account_id: Optional[int] = None,
) -> Optional[int]:
    """
    Foydalanuvchi botga yuborgan postni (Bot API `message_id`si
    orqali) Telethon (MTProto) yordamida topadi va uni
    foydalanuvchining Storage Channel'iga — Bot API'dan
    BUTUNLAY mustaqil ravishda — joylaydi.

    Qaytaradi: Storage Channel'dagi YANGI xabar ID'si (HECH
    QACHON `source_message_id` emas — bular ikki butunlay boshqa
    chatdagi ikki mustaqil xabar), yoki xatolik/topilmasa None.

    MUHIM (post-save validation): Telegram'dan qaytgan "yuborildi"
    javobiga ko'r-ko'rona ishonilmaydi — xabar Storage Channel'ga
    yuborilgandan DARHOL KEYIN `get_messages()` orqali qayta
    o'qib, HAQIQATAN ham u yerda mavjudligi tasdiqlanadi. Agar
    tasdiqlanmasa — fake/soxta ID hech qachon qaytarilmaydi va
    hech qachon DB'ga yozilmaydi.

    MUHIM: `MessageMediaWebPage` (foydalanuvchi shunchaki link
    yuborganda, Telegram avtomatik qo'shadigan URL preview)
    HAQIQIY MEDIA EMAS — `send_file()`ga uzatilmaydi, aks holda
    xatolik beradi. Bunday holatda va oddiy matn xabarlarida
    postning matni oddiy text xabar sifatida yuboriladi.
    """

    try:
        storage_entity = await telethon_client.get_entity(
            PeerChannel(storage_chat_id)
        )

        source_message = await _fetch_bot_chat_message(
            telethon_client,
            source_message_id,
        )

        if source_message is None or source_message.id is None:
            logger.warning(
                "Source xabar Telethon orqali topilmadi: "
                "message_id=%s",
                source_message_id,
            )
            return None

        has_real_media = (
            source_message.media is not None
            and not isinstance(
                source_message.media, MessageMediaWebPage
            )
        )

        if has_real_media:
            media_type = type(source_message.media).__name__

            sent = await telethon_client.send_file(
                storage_entity,
                source_message.media,
                caption=source_message.message or None,
            )
        else:
            media_type = "text"

            text = source_message.message or fallback_text

            if not text:
                logger.warning(
                    "Source xabarda na media, na matn topildi: "
                    "message_id=%s",
                    source_message_id,
                )
                return None

            sent = await telethon_client.send_message(
                storage_entity,
                text,
            )

        # MUHIM (spec 6-bo'lim — post-save validation): DARHOL
        # qayta o'qib, xabar haqiqatan Storage Channel'da
        # mavjudligini tasdiqlaymiz. Tasdiqlanmasa — DB'ga
        # HECH QACHON fake ID yozilmaydi.
        verified = await telethon_client.get_messages(
            storage_entity,
            ids=sent.id,
        )

        if verified is None:
            logger.error(
                "storage_save: post-save validation "
                "muvaffaqiyatsiz — Storage'da tasdiqlanmadi: "
                "user_id=%s, account_id=%s, "
                "source_message_id=%s, storage_chat_id=%s, "
                "storage_message_id=%s",
                user_id,
                account_id,
                source_message_id,
                storage_chat_id,
                sent.id,
            )
            return None

        logger.info(
            "storage_save: user_id=%s, account_id=%s, "
            "source_message_id=%s, storage_chat_id=%s, "
            "storage_message_id=%s, media_type=%s",
            user_id,
            account_id,
            source_message_id,
            storage_chat_id,
            sent.id,
            media_type,
        )

        return int(sent.id)

    except RPCError:
        # MUHIM: Telegram serveridan qaytgan RPC xatosi (masalan
        # o'ta katta/buzilgan fayl qismlari) — foydalanuvchiga
        # tushunarli xabar berish uchun aniq turga o'giriladi.
        logger.exception(
            "Storage kanaliga post joylashda Telegram RPC "
            "xatosi: chat_id=%s",
            storage_chat_id,
        )
        raise StoragePostTooLarge() from None

    except Exception:
        logger.exception(
            "Storage kanaliga post joylashda xatolik: chat_id=%s",
            storage_chat_id,
        )
        return None


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
