from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from telethon.errors import RPCError
from telethon.tl.functions.channels import CreateChannelRequest

from app.database import AsyncSessionLocal
from app.database.models import TelegramStorageChannel
from app.telegram.user_client import telegram_client_manager

logger = logging.getLogger(__name__)

STORAGE_CHANNEL_TITLE = "Nano-Bot Storage"

STORAGE_CHANNEL_ABOUT = (
    "Nano-Bot Auto Reply va First Message postlari "
    "shu yerda xavfsiz saqlanadi."
)


# ============================================================
# GET
# ============================================================

async def get_storage_channel(
    telegram_account_id: int,
) -> Optional[TelegramStorageChannel]:
    """
    Telegram akkaunt uchun mavjud (faol) Storage Channel'ni qaytaradi.
    """

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TelegramStorageChannel).where(
                TelegramStorageChannel.telegram_account_id
                == telegram_account_id,
                TelegramStorageChannel.is_active.is_(True),
            )
        )

        return result.scalar_one_or_none()


# ============================================================
# ENSURE (GET OR CREATE)
# ============================================================

async def ensure_storage_channel(
    *,
    telegram_id: int,
    db_user_id: int,
    telegram_account_id: int,
) -> Optional[TelegramStorageChannel]:
    """
    Foydalanuvchining shaxsiy "Nano-Bot Storage" kanali mavjudligini
    tekshiradi, bo'lmasa Telethon orqali yaratadi.

    Idempotent:
    - DB'da allaqachon faol kanal bo'lsa, yangisi yaratilmaydi.
    - Restartdan keyin ham qayta kanal yaratilmaydi
      (chunki holat DB'da saqlanadi, xotirada emas).
    """

    existing = await get_storage_channel(telegram_account_id)

    if existing is not None:
        return existing

    client = telegram_client_manager.get_client(telegram_id)

    if client is None:
        logger.warning(
            "Storage channel: Telegram client topilmadi (account_id=%s)",
            telegram_account_id,
        )
        return None

    try:
        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            logger.warning(
                "Storage channel: akkaunt avtorizatsiyadan "
                "o'tmagan (account_id=%s)",
                telegram_account_id,
            )
            return None

        result = await client(
            CreateChannelRequest(
                title=STORAGE_CHANNEL_TITLE,
                about=STORAGE_CHANNEL_ABOUT,
                broadcast=True,
                megagroup=False,
            )
        )

        new_channel = result.chats[0]
        chat_id = int(new_channel.id)

        async with AsyncSessionLocal() as session:
            # Race-safety: boshqa parallel chaqiruv allaqachon
            # yaratgan bo'lishi mumkin.
            recheck = await session.execute(
                select(TelegramStorageChannel).where(
                    TelegramStorageChannel.telegram_account_id
                    == telegram_account_id,
                    TelegramStorageChannel.is_active.is_(True),
                )
            )

            already = recheck.scalar_one_or_none()

            if already is not None:
                return already

            storage_channel = TelegramStorageChannel(
                user_id=db_user_id,
                telegram_account_id=telegram_account_id,
                chat_id=chat_id,
                title=STORAGE_CHANNEL_TITLE,
                is_active=True,
            )

            session.add(storage_channel)

            await session.commit()
            await session.refresh(storage_channel)

        logger.info(
            "Storage channel yaratildi: account_id=%s",
            telegram_account_id,
        )

        return storage_channel

    except RPCError:
        logger.exception(
            "Storage channel yaratishda Telegram xatosi: "
            "account_id=%s",
            telegram_account_id,
        )
        return None

    except Exception:
        logger.exception(
            "Storage channel yaratishda kutilmagan xatolik: "
            "account_id=%s",
            telegram_account_id,
        )
        return None


__all__ = [
    "get_storage_channel",
    "ensure_storage_channel",
]
