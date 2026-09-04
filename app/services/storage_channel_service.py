from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from sqlalchemy import select
from telethon.errors import RPCError
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    EditAdminRequest,
)
from telethon.tl.types import ChatAdminRights, PeerChannel

from app.config import BOT_USERNAME
from app.database import AsyncSessionLocal
from app.database.models import TelegramStorageChannel
from app.services.telegram_id_utils import (
    to_bot_api_chat_id,
    to_telethon_channel_id,
)
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
        await client.get_entity(
            PeerChannel(to_telethon_channel_id(chat_id))
        )
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
# BOT'NI STORAGE CHANNEL'GA ADMIN QILISH
# ============================================================
#
# MUHIM ARXITEKTURA QOIDASI: Auto Reply/First Message source
# xabarlari Bot API server-side `copyMessage` orqali to'g'ridan-
# to'g'ri Storage Channel'ga nusxalanadi. `copyMessage` broadcast
# kanalga yozish uchun bot O'SHA KANALDA ADMIN (kamida "xabar
# joylash" huquqi bilan) bo'lishi SHART.
#
# ROOT CAUSE (tuzatilgan xato): kanallarda (broadcast, megagroup
# EMAS) bot oddiy a'zo sifatida `InviteToChannelRequest` bilan
# QO'SHILA OLMAYDI — Telegram buni aniq rad etadi:
# `UserBotError: Bots can only be admins in channels`. To'g'ri
# mexanizm — botni TO'G'RIDAN-TO'G'RI `EditAdminRequest`
# (channels.editAdmin) orqali admin qilish: bu so'rov kanal
# egasi (bu yerda — Telethon foydalanuvchi akkaunti) tomonidan
# yuborilganda, bot ALLAQACHON a'zo bo'lishini TALAB QILMAYDI —
# Telegram uni promotsiya bilan birga avtomatik "taklif" ham
# qiladi. Alohida invite bosqichi shu sabab BUTUNLAY OLIB
# TASHLANDI (na kerak, na ishlaydi).

async def _ensure_bot_is_storage_admin(
    client,
    chat_id: int,
) -> bool:
    """
    Botni Storage Channel'da admin (faqat `post_messages`
    huquqi bilan) qilib tayinlaydi — Telethon (kanal egasi)
    tomonidan.

    MUHIM (false-success tuzatildi): bu funksiya FAQAT
    `EditAdminRequest` HAQIQATAN muvaffaqiyatli bo'lgandagina
    True qaytaradi va "SUCCESS" log yozadi. Har qanday
    bosqichdagi xatolik — aniq "FAILED" log va False bilan
    darhol to'xtaydi (hech qanday "baribir davom etamiz"
    degan yashirin fallback yo'q).
    """

    telethon_channel_id = to_telethon_channel_id(chat_id)

    try:
        channel_entity = await client.get_entity(
            PeerChannel(telethon_channel_id)
        )
    except Exception as exc:
        logger.error(
            "Storage channel bot admin FAILED [resolve_channel]: "
            "%s: %s (chat_id=%s)",
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
            "Storage channel bot admin FAILED [resolve_bot]: "
            "%s: %s (chat_id=%s, BOT_USERNAME=%s)",
            type(exc).__name__,
            exc,
            chat_id,
            BOT_USERNAME,
            exc_info=exc,
        )
        return False

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
            "Storage channel bot admin FAILED [edit_admin]: "
            "%s: %s (chat_id=%s)",
            type(exc).__name__,
            exc,
            chat_id,
            exc_info=exc,
        )
        return False

    logger.info(
        "Storage channel bot admin SUCCESS (Telethon/editAdmin): "
        "chat_id=%s, can_post_messages=True",
        chat_id,
    )

    return True


# ============================================================
# BOT API TOMONIDAN TASDIQLASH (spec 8-bo'lim)
# ============================================================
#
# MUHIM: yuqoridagi `_ensure_bot_is_storage_admin` FAQAT
# Telethon (kanal egasi) nuqtai nazaridan "men botni admin
# qildim" deydi. Lekin `copyMessage` BOT API orqali chaqiriladi
# — shu sabab botning O'ZI, Bot API orqali, xuddi shu holatni
# ko'ra olishi MUSTAQIL ravishda tasdiqlanadi. Faqat IKKALA
# tekshiruv ham o'tgandan keyingina kanal `active` deb
# belgilanadi.

async def _verify_bot_can_post_via_bot_api(
    bot: Bot,
    chat_id: int,
) -> bool:
    bot_api_chat_id = to_bot_api_chat_id(chat_id)

    try:
        member = await bot.get_chat_member(
            bot_api_chat_id,
            bot.id,
        )
    except Exception as exc:
        logger.error(
            "Storage channel bot admin FAILED [bot_api_verify]: "
            "%s: %s (chat_id=%s)",
            type(exc).__name__,
            exc,
            chat_id,
            exc_info=exc,
        )
        return False

    is_admin = member.status == ChatMemberStatus.ADMINISTRATOR
    can_post = bool(getattr(member, "can_post_messages", False))

    if not is_admin or not can_post:
        logger.error(
            "Storage channel bot admin FAILED [bot_api_verify]: "
            "bot admin emas yoki post huquqi yo'q "
            "(status=%s, can_post_messages=%s, chat_id=%s)",
            getattr(member, "status", None),
            can_post,
            chat_id,
        )
        return False

    logger.info(
        "Storage channel bot admin SUCCESS (Bot API tasdiqlandi): "
        "chat_id=%s, can_post_messages=True",
        chat_id,
    )

    return True


async def _ensure_and_verify_bot_admin(
    client,
    bot: Bot,
    chat_id: int,
) -> bool:
    """
    Botni Storage Channel'da admin qilish (Telethon) VA buni Bot
    API'ning o'zi orqali mustaqil tasdiqlash (spec 8-bo'lim) —
    ikkalasi ham muvaffaqiyatli bo'lgandagina True qaytaradi.
    """

    if not await _ensure_bot_is_storage_admin(client, chat_id):
        return False

    return await _verify_bot_can_post_via_bot_api(bot, chat_id)


# ============================================================
# MARKAZIY SERVIS: GET OR CREATE (Telethon health-check bilan)
# ============================================================

async def get_or_create_user_storage_channel(
    *,
    telegram_id: int,
    db_user_id: int,
    telegram_account_id: int,
    bot: Bot,
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

    MUHIM (spec 8-bo'lim): C va A holatlarining ikkalasida ham
    kanal faqat Telethon TOMONDAN emas, Bot API TOMONDAN ham
    (`_ensure_and_verify_bot_admin`) tasdiqlangandan keyingina
    READY/CREATED (ya'ni "ishlatsa bo'ladi") deb qaytariladi.
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
        telethon_channel_id = await _create_channel_via_telethon(
            client
        )

        if telethon_channel_id is None:
            return StorageChannelResult(ERROR, None)

        # MUHIM (spec 6/7-bo'lim, root cause tuzatildi): DB'ga
        # Telethon'ning "bare" ID'si EMAS — Bot API ishlaydigan
        # chat_id (-100xxxxxxxxxx) yoziladi.
        bot_api_chat_id = to_bot_api_chat_id(telethon_channel_id)

        logger.info(
            "Storage channel CREATE: user_id=%s, account_id=%s, "
            "telethon_channel_id=%s, bot_api_chat_id=%s",
            db_user_id,
            telegram_account_id,
            telethon_channel_id,
            bot_api_chat_id,
        )

        channel = await _save_channel(
            db_user_id=db_user_id,
            telegram_account_id=telegram_account_id,
            chat_id=bot_api_chat_id,
        )

        if channel is None:
            return StorageChannelResult(ERROR, None)

        if not await _ensure_and_verify_bot_admin(
            client, bot, bot_api_chat_id
        ):
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
        if not await _ensure_and_verify_bot_admin(
            client,
            bot,
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
