from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.database import AsyncSessionLocal
from app.database.models import TelegramAccount, UnansweredChat, User

logger = logging.getLogger(__name__)

STATUS_UNANSWERED = "UNANSWERED"
STATUS_ANSWERED = "ANSWERED"

REMINDER_THRESHOLD = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# OUTGOING (bot yubordi) — record yaratish/yangilash
# ============================================================

async def record_outgoing_message(
    *,
    telegram_account_id: int,
    peer_id: int,
    peer_name: Optional[str],
    peer_username: Optional[str],
    sent_at: Optional[datetime] = None,
) -> None:
    """
    Auto Reply YOKI First Message Engine muvaffaqiyatli xabar
    yuborgandan KEYIN chaqiriladi.

    MUHIM (spec 7-bo'lim): bir peer uchun faqat BITTA faol
    (UNANSWERED) yozuv bo'ladi. Agar allaqachon mavjud bo'lsa —
    faqat `last_bot_message_at`/display metadata yangilanadi,
    `waiting_since` O'ZGARTIRILMAYDI (javob kutish birinchi
    xabardan boshlab hisoblanadi). Agar mavjud bo'lmasa — yangi
    "javobsizlik sikli" boshlanadi.

    Xabar matni/tarixi bu yerda HECH QACHON saqlanmaydi — faqat
    peer ID va vaqt belgilari.
    """

    sent_at = sent_at or _now()

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UnansweredChat).where(
                    UnansweredChat.telegram_account_id
                    == telegram_account_id,
                    UnansweredChat.peer_id == peer_id,
                    UnansweredChat.status == STATUS_UNANSWERED,
                )
            )

            existing = result.scalar_one_or_none()

            if existing is not None:
                existing.last_bot_message_at = sent_at

                if peer_name:
                    existing.peer_name = peer_name

                if peer_username:
                    existing.peer_username = peer_username

                await session.commit()
                return

            new_record = UnansweredChat(
                telegram_account_id=telegram_account_id,
                peer_id=peer_id,
                peer_type="user",
                peer_name=peer_name,
                peer_username=peer_username,
                first_bot_message_at=sent_at,
                waiting_since=sent_at,
                last_bot_message_at=sent_at,
                status=STATUS_UNANSWERED,
                reminder_sent=False,
            )

            session.add(new_record)

            try:
                await session.commit()
            except IntegrityError:
                # MUHIM (race condition himoyasi — spec 18-bo'lim
                # "duplicate outgoing message"): parallel chaqiruv
                # allaqachon xuddi shu (account, peer) uchun faol
                # yozuv yaratgan bo'lishi mumkin — DB darajasidagi
                # qisman unique index shuni ushlaydi. Xatolik
                # xavfsiz yutiladi, duplicate yozuv yaratilmaydi.
                await session.rollback()

    except Exception:
        logger.exception(
            "Unanswered chat record yaratish/yangilashda "
            "xatolik."
        )


# ============================================================
# INCOMING (user javob berdi) — resolve qilish
# ============================================================

async def mark_answered(
    *,
    telegram_account_id: int,
    peer_id: int,
    replied_at: Optional[datetime] = None,
) -> bool:
    """
    User shu peer'dan yangi xabar yuborganda chaqiriladi.

    Agar faol (UNANSWERED) yozuv mavjud bo'lsa — ANSWERED qilib
    belgilanadi va True qaytariladi. Aks holda (bu peer uchun
    hech qanday kutilayotgan javob yo'q edi) hech narsa
    qilinmaydi — False qaytariladi.

    Idempotent: allaqachon ANSWERED bo'lgan yozuvga qayta
    chaqirilsa ham xavfsiz (hech narsa topilmaydi, hech narsa
    o'zgarmaydi) — Telegram'ning takroriy (duplicate) update
    yuborishi xavfli emas.
    """

    replied_at = replied_at or _now()

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UnansweredChat).where(
                    UnansweredChat.telegram_account_id
                    == telegram_account_id,
                    UnansweredChat.peer_id == peer_id,
                    UnansweredChat.status == STATUS_UNANSWERED,
                )
            )

            record = result.scalar_one_or_none()

            if record is None:
                return False

            record.status = STATUS_ANSWERED
            record.user_replied_at = replied_at

            await session.commit()

            return True

    except Exception:
        logger.exception(
            "Unanswered chat'ni ANSWERED qilishda xatolik."
        )
        return False


# ============================================================
# RO'YXAT (Nano-Agent UI uchun)
# ============================================================

@dataclass
class UnansweredChatItem:
    id: int
    peer_id: int
    peer_name: Optional[str]
    peer_username: Optional[str]
    waiting_since: datetime


async def get_unanswered_page(
    telegram_account_id: int,
    page: int = 1,
    page_size: int = 10,
) -> Tuple[List[UnansweredChatItem], int, int, int]:
    page = max(1, page)

    async with AsyncSessionLocal() as session:
        total = (
            await session.execute(
                select(func.count(UnansweredChat.id)).where(
                    UnansweredChat.telegram_account_id
                    == telegram_account_id,
                    UnansweredChat.status == STATUS_UNANSWERED,
                )
            )
        ).scalar_one()

        total_pages = max(
            1, (total + page_size - 1) // page_size
        )
        page = min(page, total_pages)

        # MUHIM (spec 3-bo'lim): ENG UZOQ VAQT javobsiz qolgan
        # chat birinchi — ORDER BY waiting_since ASC.
        result = await session.execute(
            select(UnansweredChat)
            .where(
                UnansweredChat.telegram_account_id
                == telegram_account_id,
                UnansweredChat.status == STATUS_UNANSWERED,
            )
            .order_by(UnansweredChat.waiting_since.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        rows = result.scalars().all()

        items = [
            UnansweredChatItem(
                id=row.id,
                peer_id=row.peer_id,
                peer_name=row.peer_name,
                peer_username=row.peer_username,
                waiting_since=row.waiting_since,
            )
            for row in rows
        ]

        return items, total, total_pages, page


async def get_unanswered_chat_by_id(
    telegram_account_id: int,
    record_id: int,
) -> Optional[UnansweredChat]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UnansweredChat).where(
                UnansweredChat.id == record_id,
                UnansweredChat.telegram_account_id
                == telegram_account_id,
            )
        )

        return result.scalar_one_or_none()


# ============================================================
# STATISTIKA (mavjud Statistics tizimini buzmasdan, qo'shimcha)
# ============================================================

@dataclass
class UnansweredStatsSummary:
    unanswered: int
    answered: int
    overdue_24h: int


async def get_unanswered_stats(
    telegram_account_id: int,
) -> UnansweredStatsSummary:
    async with AsyncSessionLocal() as session:
        unanswered = (
            await session.execute(
                select(func.count(UnansweredChat.id)).where(
                    UnansweredChat.telegram_account_id
                    == telegram_account_id,
                    UnansweredChat.status == STATUS_UNANSWERED,
                )
            )
        ).scalar_one()

        answered = (
            await session.execute(
                select(func.count(UnansweredChat.id)).where(
                    UnansweredChat.telegram_account_id
                    == telegram_account_id,
                    UnansweredChat.status == STATUS_ANSWERED,
                )
            )
        ).scalar_one()

        threshold = _now() - REMINDER_THRESHOLD

        overdue_24h = (
            await session.execute(
                select(func.count(UnansweredChat.id)).where(
                    UnansweredChat.telegram_account_id
                    == telegram_account_id,
                    UnansweredChat.status == STATUS_UNANSWERED,
                    UnansweredChat.waiting_since <= threshold,
                )
            )
        ).scalar_one()

        return UnansweredStatsSummary(
            unanswered=unanswered,
            answered=answered,
            overdue_24h=overdue_24h,
        )


# ============================================================
# SCHEDULER — 24 soatlik reminder
# ============================================================

@dataclass
class ReminderTarget:
    record_id: int
    owner_telegram_id: int
    peer_id: int
    peer_name: Optional[str]
    peer_username: Optional[str]
    waiting_since: datetime


async def get_due_reminders(
    limit: int = 200,
) -> List[ReminderTarget]:
    """
    24 soatdan ortiq javobsiz turgan va hali reminder
    yuborilmagan yozuvlarni topadi. Har biri uchun bildirishnoma
    kimga (Nano-Bot foydalanuvchisi, ya'ni akkaunt egasi)
    yuborilishi kerakligini ham (User.telegram_id) qaytaradi.
    """

    threshold = _now() - REMINDER_THRESHOLD

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                UnansweredChat.id,
                User.telegram_id,
                UnansweredChat.peer_id,
                UnansweredChat.peer_name,
                UnansweredChat.peer_username,
                UnansweredChat.waiting_since,
            )
            .join(
                TelegramAccount,
                TelegramAccount.id
                == UnansweredChat.telegram_account_id,
            )
            .join(
                User,
                User.id == TelegramAccount.user_id,
            )
            .where(
                UnansweredChat.status == STATUS_UNANSWERED,
                UnansweredChat.reminder_sent.is_(False),
                UnansweredChat.waiting_since <= threshold,
            )
            .limit(limit)
        )

        return [
            ReminderTarget(
                record_id=row[0],
                owner_telegram_id=row[1],
                peer_id=row[2],
                peer_name=row[3],
                peer_username=row[4],
                waiting_since=row[5],
            )
            for row in result.all()
        ]


async def mark_reminder_sent(record_id: int) -> None:
    try:
        async with AsyncSessionLocal() as session:
            record = await session.get(
                UnansweredChat, record_id
            )

            if record is None:
                return

            record.reminder_sent = True
            record.reminder_sent_at = _now()

            await session.commit()

    except Exception:
        logger.exception(
            "reminder_sent belgilashda xatolik "
            "(record_id=%s).",
            record_id,
        )


__all__ = [
    "STATUS_UNANSWERED",
    "STATUS_ANSWERED",
    "REMINDER_THRESHOLD",
    "record_outgoing_message",
    "mark_answered",
    "UnansweredChatItem",
    "get_unanswered_page",
    "get_unanswered_chat_by_id",
    "UnansweredStatsSummary",
    "get_unanswered_stats",
    "ReminderTarget",
    "get_due_reminders",
    "mark_reminder_sent",
]
