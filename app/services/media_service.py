from __future__ import annotations

import io
import logging
from typing import Optional, Tuple

from aiogram import Bot
from aiogram.types import Message as BotMessage
from telethon import TelegramClient
from telethon.tl.types import PeerChannel

logger = logging.getLogger(__name__)

SUPPORTED_MESSAGE_TYPES = (
    "text",
    "photo",
    "video",
    "document",
)


# ============================================================
# DETECT INCOMING POST CONTENT (Bot API side)
# ============================================================

def detect_post_content(
    message: BotMessage,
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    aiogram Message'dan post turini aniqlaydi.

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

    if message.text:
        return (
            "text",
            message.text,
            None,
            None,
        )

    return None, None, None, None


# ============================================================
# DOWNLOAD FROM BOT API
# ============================================================

async def _download_bot_file(
    bot: Bot,
    file_id: str,
    file_name: Optional[str],
) -> Optional[io.BytesIO]:
    """
    Bot API file_id orqali faylni xotiraga yuklab oladi.

    Diskka yozilmaydi — faqat Telethon'ga qayta yuborish uchun
    vaqtinchalik xotirada ushlab turiladi.
    """

    try:
        buffer = io.BytesIO()

        await bot.download(
            file_id,
            destination=buffer,
        )

        buffer.seek(0)
        buffer.name = file_name or "file"

        return buffer

    except Exception:
        logger.exception(
            "Bot API fayl yuklab olinmadi."
        )
        return None


# ============================================================
# SAVE POST TO STORAGE CHANNEL
# ============================================================

async def send_post_to_storage(
    *,
    bot: Bot,
    telethon_client: TelegramClient,
    storage_chat_id: int,
    message_type: str,
    text: Optional[str],
    file_id: Optional[str],
    file_name: Optional[str] = None,
) -> Optional[int]:
    """
    Postni foydalanuvchining Storage Channel'iga Telethon orqali
    joylaydi va yuborilgan xabar id'sini qaytaradi.
    """

    try:
        entity = await telethon_client.get_entity(
            PeerChannel(storage_chat_id)
        )

        if message_type == "text":
            if not text:
                return None

            sent = await telethon_client.send_message(
                entity,
                text,
            )

            return int(sent.id)

        if message_type not in SUPPORTED_MESSAGE_TYPES:
            logger.warning(
                "Noma'lum post turi: %s",
                message_type,
            )
            return None

        if not file_id:
            return None

        buffer = await _download_bot_file(
            bot,
            file_id,
            file_name,
        )

        if buffer is None:
            return None

        sent = await telethon_client.send_file(
            entity,
            buffer,
            caption=text or None,
        )

        return int(sent.id)

    except Exception:
        logger.exception(
            "Storage kanaliga post joylashda xatolik: chat_id=%s",
            storage_chat_id,
        )
        return None


# ============================================================
# SEND STORED POST AS A NEW MESSAGE (NOT FORWARD)
# ============================================================

async def send_stored_post(
    *,
    telethon_client: TelegramClient,
    storage_chat_id: int,
    storage_message_id: int,
    target_chat_id: int,
) -> bool:
    """
    Storage Channel'dagi postni forward qilmasdan, yangi xabar
    sifatida target chatga yuboradi.

    Agar storage message o'chirilgan bo'lsa yoki topilmasa,
    xatolik ko'tarmaydi — False qaytaradi va admin logga yozadi.
    """

    try:
        storage_entity = await telethon_client.get_entity(
            PeerChannel(storage_chat_id)
        )

        stored_message = await telethon_client.get_messages(
            storage_entity,
            ids=storage_message_id,
        )

        if stored_message is None:
            logger.warning(
                "Storage post topilmadi (o'chirilgan bo'lishi mumkin): "
                "chat_id=%s message_id=%s",
                storage_chat_id,
                storage_message_id,
            )
            return False

        if stored_message.media:
            await telethon_client.send_file(
                target_chat_id,
                stored_message.media,
                caption=stored_message.message or None,
            )
            return True

        if stored_message.message:
            await telethon_client.send_message(
                target_chat_id,
                stored_message.message,
            )
            return True

        logger.warning(
            "Storage post bo'sh: chat_id=%s message_id=%s",
            storage_chat_id,
            storage_message_id,
        )
        return False

    except Exception:
        logger.exception(
            "Storage postni yuborishda xatolik: "
            "chat_id=%s message_id=%s target=%s",
            storage_chat_id,
            storage_message_id,
            target_chat_id,
        )
        return False


__all__ = [
    "SUPPORTED_MESSAGE_TYPES",
    "detect_post_content",
    "send_post_to_storage",
    "send_stored_post",
]
