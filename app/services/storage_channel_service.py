from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from telethon.errors import RPCError, UserAlreadyParticipantError
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    EditAdminRequest,
    InviteToChannelRequest,
)
from telethon.tl.types import ChatAdminRights, PeerChannel

from app.config import BOT_USERNAME
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
# STATUS
# ============================================================
#
# MUHIM: bu servis — Auto Reply/First Message uchun Storage
# Channel bilan bog'liq YAGONA, markaziy joy. Handlerlar
# o'zlaricha kanal yaratmaydi/tekshirmaydi — barchasi shu
# yerdagi `get_or_create_user_storage_channel()`ni chaqiradi.

READY = "ready"
CREATED = "created"
NEEDS_CONFIRMATION = "needs_confirmation"
ERROR = "error"


@dataclass
class StorageChannelResult:
    status: str
    channel: Optional[TelegramStorageChannel]


# ============================================================
# GET (faqat DB'dan, Telethon tekshiruvisiz)
# ============================================================

async def get_storage_channel(
    telegram_account_id: int,
) -> Optional[TelegramStorageChannel]:
    """
    Telegram akkaunt uchun DB'dagi (faol deb belgilangan) Storage
    Channel qatorini qaytaradi — Telethon orqali HAQIQATDA hali
    mavjudligini TEKSHIRMAYDI (buning uchun
    `get_or_create_user_storage_channel()`dan foydalaning).
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
# TELETHON HEALTH-CHECK
# ============================================================

async def _is_channel_accessible(
    client,
    chat_id: int,
) -> bool:
    """
    Berilgan chat_id foydalanuvchining Telethon sessiyasi orqali
    haligacha mavjud/kirish mumkinmi — tekshiradi.

    Kanal o'chirilgan, foydalanuvchi undan chiqarilgan yoki access
    hash eskirgan bo'lsa — bu funksiya False qaytaradi (istisno
    ko'tarilmaydi, chaqiruvchi buni "needs confirmation" holati
    sifatida talqin qiladi).
    """

    try:
        await client.get_entity(PeerChannel(chat_id))
        return True
    except Exception:
        logger.warning(
            "Storage channel endi kirish mumkin emas "
            "(o'chirilgan yoki access yo'qolgan): chat_id=%s",
            chat_id,
        )
        return False


async def _get_ready_client(telegram_id: int):
    client = telegram_client_manager.get_client(telegram_id)

    if client is None:
        return None

    try:
        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            return None

        return client

    except Exception:
        logger.exception(
            "Telethon clientni tayyorlashda xatolik: "
            "telegram_id=%s",
            telegram_id,
        )
        return None


# ============================================================
# CREATE (past darajadagi, DB yozmaydi)
# ============================================================

async def _create_channel_via_telethon(client) -> Optional[int]:
    try:
        result = await client(
            CreateChannelRequest(
                title=STORAGE_CHANNEL_TITLE,
                about=STORAGE_CHANNEL_ABOUT,
                broadcast=True,
                megagroup=False,
            )
        )

        new_channel = result.chats[0]

        return int(new_channel.id)

    except RPCError:
        logger.exception(
            "Storage channel yaratishda Telegram xatosi."
        )
        return None

    except Exception:
        logger.exception(
            "Storage channel yaratishda kutilmagan xatolik."
        )
        return None


# ============================================================
# BOT'NI STORAGE CHANNEL'GA A'ZO + ADMIN QILISH
# ============================================================
#
# MUHIM ARXITEKTURA QOIDASI: Auto Reply/First Message source
# xabarlari endi Bot API server-side `copyMessage` orqali
# to'g'ridan-to'g'ri Storage Channel'ga nusxalanadi (Telethon
# orqali botdan xabar "qidirish" ENDI ISHLATILMAYDI — bu
# ishonchsiz bo'lib chiqdi). `copyMessage` broadcast kanalga
# yozish uchun bot O'SHA KANALDA ADMIN (kamida "xabar joylash"
# huquqi bilan) bo'lishi SHART — shu sabab botni admin qilish bu
# arxitekturada ENDI TALAB.

async def _ensure_bot_is_storage_admin(
    client,
    chat_id: int,
) -> bool:
    """
    Bot Storage Channel'ga a'zo va admin (faqat `post_messages`
    huquqi bilan) ekanligini ta'minlaydi.

    Idempotent va xavfsiz: bot allaqachon a'zo bo'lsa
    (`UserAlreadyParticipantError`), bu jim o'tkazib yuboriladi —
    xatolik EMAS. Har chaqiruvda qayta tekshirilishi mumkin
    (masalan eski, botsiz yaratilgan kanallarni "davolash" uchun).
    """

    try:
        channel_entity = await client.get_entity(
            PeerChannel(chat_id)
        )
    except Exception as exc:
        logger.error(
            "Storage channel: botni admin qilishda channel "
            "entity topilmadi: %s: %s (chat_id=%s)",
            type(exc).__name__,
            exc,
            chat_id,
            exc_info=exc,
        )
        return False

    try:
        bot_entity = await client.get_entity(BOT_USERNAME)
    except Exception as exc:
        logger.error(
            "Storage channel: bot entity topilmadi "
            "(BOT_USERNAME=%s): %s: %s",
            BOT_USERNAME,
            type(exc).__name__,
            exc,
            exc_info=exc,
        )
        return False

    try:
        await client(
            InviteToChannelRequest(
                channel=channel_entity,
                users=[bot_entity],
            )
        )
    except UserAlreadyParticipantError:
        pass
    except Exception:
        # MUHIM: bu bosqichdagi xatolik ALOHIDA fatal EMAS — bot
        # allaqachon a'zo bo'lishi yoki kanal creator'i sifatida
        # zaruriyat bo'lmasligi mumkin. Pastdagi admin qilish
        # bosqichi haqiqiy tekshiruv hisoblanadi.
        logger.warning(
            "Storage channel: botni kanalga qo'shishda xatolik "
            "(admin qilish baribir urinib ko'riladi): chat_id=%s",
            chat_id,
            exc_info=True,
        )

    try:
        await client(
            EditAdminRequest(
                channel=channel_entity,
                user_id=bot_entity,
                admin_rights=ChatAdminRights(
                    post_messages=True,
                ),
                rank="Storage",
            )
        )
    except Exception as exc:
        logger.error(
            "Storage channel: botni admin qilishda xatolik: "
            "%s: %s (chat_id=%s)",
            type(exc).__name__,
            exc,
            chat_id,
            exc_info=exc,
        )
        return False

    logger.info(
        "Storage channel: bot admin qilib tayinlandi "
        "(post_messages huquqi bilan): chat_id=%s",
        chat_id,
    )

    return True


# ============================================================
# MARKAZIY SERVIS: GET OR CREATE (Telethon health-check bilan)
# ============================================================

async def get_or_create_user_storage_channel(
    *,
    telegram_id: int,
    db_user_id: int,
    telegram_account_id: int,
) -> StorageChannelResult:
    """
    Auto Reply/First Message uchun ISHLATILADIGAN YAGONA, markaziy
    Storage Channel funksiyasi.

    Mantiq (spec 13-bo'lim):
    A) DB'da qator yo'q       -> yangi kanal yaratiladi, saqlanadi
    B) DB'da qator bor        -> Telethon orqali tekshiriladi
    C) ... va kanal mavjud    -> shu qator qaytariladi (READY)
    D) ... lekin o'chirilgan  -> foydalanuvchidan tasdiq so'rash
                                  kerakligini bildiruvchi holat
                                  qaytariladi (NEEDS_CONFIRMATION) —
                                  bu yerda DARHOL yangi kanal
                                  YARATILMAYDI, chunki foydalanuvchi
                                  hali "Ha" demagan.
    """

    client = await _get_ready_client(telegram_id)

    if client is None:
        logger.warning(
            "Storage channel: Telegram client tayyor emas "
            "(account_id=%s)",
            telegram_account_id,
        )
        return StorageChannelResult(ERROR, None)

    existing = await get_storage_channel(telegram_account_id)

    if existing is None:
        # A) Hali umuman yaratilmagan — yangi kanal ochamiz.
        chat_id = await _create_channel_via_telethon(client)

        if chat_id is None:
            return StorageChannelResult(ERROR, None)

        channel = await _save_channel(
            db_user_id=db_user_id,
            telegram_account_id=telegram_account_id,
            chat_id=chat_id,
        )

        if channel is None:
            return StorageChannelResult(ERROR, None)

        if not await _ensure_bot_is_storage_admin(client, chat_id):
            return StorageChannelResult(ERROR, None)

        logger.info(
            "Storage channel yaratildi: account_id=%s",
            telegram_account_id,
        )

        return StorageChannelResult(CREATED, channel)

    # B) DB'da bor — Telethon orqali haqiqatan mavjudligini
    # tekshiramiz (jim ishlatib qo'yish TAQIQLANGAN — spec
    # 2-bo'lim).
    accessible = await _is_channel_accessible(
        client,
        existing.chat_id,
    )

    if accessible:
        # C) MUHIM: bot admin ekanligi HAR SAFAR qayta
        # tekshiriladi/ta'minlanadi — bu shu arxitekturaga
        # o'tishdan OLDIN yaratilgan (botsiz) eski Storage
        # Channel'larni ham xavfsiz "davolaydi", DB'da hech
        # qanday buzg'unchi/destruktiv migratsiyasiz.
        if not await _ensure_bot_is_storage_admin(
            client,
            existing.chat_id,
        ):
            return StorageChannelResult(ERROR, None)

        return StorageChannelResult(READY, existing)

    # D) O'chirilgan/invalid — foydalanuvchi tasdig'i kerak.
    return StorageChannelResult(NEEDS_CONFIRMATION, existing)


async def _save_channel(
    *,
    db_user_id: int,
    telegram_account_id: int,
    chat_id: int,
) -> Optional[TelegramStorageChannel]:
    try:
        async with AsyncSessionLocal() as session:
            # Race-safety: boshqa parallel chaqiruv allaqachon
            # yaratgan bo'lishi mumkin.
            recheck = await session.execute(
                select(TelegramStorageChannel).where(
                    TelegramStorageChannel.telegram_account_id
                    == telegram_account_id
                )
            )

            already = recheck.scalar_one_or_none()

            if already is not None:
                already.chat_id = chat_id
                already.is_active = True

                await session.commit()
                await session.refresh(already)

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

            return storage_channel

    except Exception:
        logger.exception(
            "Storage channel DB'ga saqlashda xatolik: "
            "account_id=%s",
            telegram_account_id,
        )
        return None


# ============================================================
# QAYTA YARATISH (foydalanuvchi "✅ Ha" bosgandan keyin)
# ============================================================

async def recreate_user_storage_channel(
    *,
    telegram_id: int,
    db_user_id: int,
    telegram_account_id: int,
) -> Optional[TelegramStorageChannel]:
    """
    Foydalanuvchi eski kanal o'chirilgani haqidagi tasdiqlash
    xabarida "✅ Ha, yangi kanal ochish" tugmasini bosgandan
    keyin chaqiriladi.

    MUHIM: eski DB qatori YANGI qator bilan almashtirilmaydi —
    xuddi shu qator UPDATE qilinadi (yangi chat_id bilan), shunda
    Auto Reply/First Message recordlaridagi eski
    `storage_chat_id` referenslari (agar ular hali eski qiymatni
    saqlab tursa ham) tarixiy iz sifatida qoladi, lekin YANGI
    postlar endi albatta yangi (ishlaydigan) kanalga tushadi.
    """

    client = await _get_ready_client(telegram_id)

    if client is None:
        return None

    chat_id = await _create_channel_via_telethon(client)

    if chat_id is None:
        return None

    channel = await _save_channel(
        db_user_id=db_user_id,
        telegram_account_id=telegram_account_id,
        chat_id=chat_id,
    )

    if channel is None:
        return None

    if not await _ensure_bot_is_storage_admin(client, chat_id):
        return None

    logger.info(
        "Storage channel qayta yaratildi: account_id=%s",
        telegram_account_id,
    )

    return channel


# ============================================================
# ESKI (LEGACY) — orqaga moslik uchun, endi ICHKI ravishda
# markaziy servisga uzatiladi.
# ============================================================

async def ensure_storage_channel(
    *,
    telegram_id: int,
    db_user_id: int,
    telegram_account_id: int,
) -> Optional[TelegramStorageChannel]:
    """
    MUHIM: bu funksiya endi faqat orqaga moslik uchun saqlanadi.
    Yangi kod `get_or_create_user_storage_channel()`ni to'g'ridan-
    to'g'ri ishlatishi va uning READY/CREATED/NEEDS_CONFIRMATION/
    ERROR holatlarini alohida-alohida qayta ishlashi kerak —
    chunki bu funksiya NEEDS_CONFIRMATION holatini "topilmadi"
    (None) sifatida soddalashtiradi va foydalanuvchidan tasdiq
    so'rash imkoniyatini yo'qotadi.
    """

    result = await get_or_create_user_storage_channel(
        telegram_id=telegram_id,
        db_user_id=db_user_id,
        telegram_account_id=telegram_account_id,
    )

    if result.status in (READY, CREATED):
        return result.channel

    return None


__all__ = [
    "READY",
    "CREATED",
    "NEEDS_CONFIRMATION",
    "ERROR",
    "StorageChannelResult",
    "get_storage_channel",
    "get_or_create_user_storage_channel",
    "recreate_user_storage_channel",
    "ensure_storage_channel",
]
