from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Statistics, StatisticsEvent

AUTO_REPLY_EVENT = "auto_reply"
FIRST_MESSAGE_EVENT = "first_message"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class UserStatistics:
    replied_people: int
    auto_replies_total: int
    auto_replies_today: int
    auto_replies_7d: int
    auto_replies_30d: int
    first_messages_total: int
    first_messages_today: int
    first_messages_7d: int
    first_messages_30d: int


async def record_statistics_event(
    session: AsyncSession,
    user_id: int,
    event_type: str,
) -> None:
    """
    "Bugun / 7 kun / 30 kun" ko'rinishidagi vaqt oralig'i
    statistikasi uchun yengil, mazmunsiz (faqat vaqt + tur)
    yozuv qo'shadi. Chaqiruvchi keyin commit qilishi kerak.
    """

    session.add(
        StatisticsEvent(
            user_id=user_id,
            event_type=event_type,
        )
    )


async def _count_events(
    session: AsyncSession,
    user_id: int,
    event_type: str,
    since: Optional[datetime] = None,
) -> int:
    query = select(func.count(StatisticsEvent.id)).where(
        StatisticsEvent.user_id == user_id,
        StatisticsEvent.event_type == event_type,
    )

    if since is not None:
        query = query.where(StatisticsEvent.created_at >= since)

    result = await session.execute(query)

    return result.scalar_one()


async def get_user_statistics(
    session: AsyncSession,
    user_id: int,
) -> UserStatistics:
    """
    Foydalanuvchi uchun statistikani qaytaradi.

    MUHIM: "Umumiy" (jami) sonlar mavjud `Statistics`
    jadvalidagi kumulyativ hisoblagichlardan olinadi (bu
    qiymatlar StatisticsEvent joriy etilishidan oldingi
    yuborishlarni ham o'z ichiga oladi). "Bugun/7 kun/30 kun"
    esa faqat `StatisticsEvent` jadvali joriy etilgandan
    keyingi yangi yozuvlar asosida hisoblanadi.
    """

    now = _now()
    today_start = now.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    result = await session.execute(
        select(Statistics).where(Statistics.user_id == user_id)
    )

    statistics = result.scalar_one_or_none()

    replied_people = (
        statistics.replied_people if statistics else 0
    )
    auto_replies_total = (
        statistics.auto_replies if statistics else 0
    )
    first_messages_total = (
        statistics.first_messages_sent if statistics else 0
    )

    auto_replies_today = await _count_events(
        session, user_id, AUTO_REPLY_EVENT, today_start
    )
    auto_replies_7d = await _count_events(
        session,
        user_id,
        AUTO_REPLY_EVENT,
        now - timedelta(days=7),
    )
    auto_replies_30d = await _count_events(
        session,
        user_id,
        AUTO_REPLY_EVENT,
        now - timedelta(days=30),
    )

    first_messages_today = await _count_events(
        session, user_id, FIRST_MESSAGE_EVENT, today_start
    )
    first_messages_7d = await _count_events(
        session,
        user_id,
        FIRST_MESSAGE_EVENT,
        now - timedelta(days=7),
    )
    first_messages_30d = await _count_events(
        session,
        user_id,
        FIRST_MESSAGE_EVENT,
        now - timedelta(days=30),
    )

    return UserStatistics(
        replied_people=replied_people,
        auto_replies_total=auto_replies_total,
        auto_replies_today=auto_replies_today,
        auto_replies_7d=auto_replies_7d,
        auto_replies_30d=auto_replies_30d,
        first_messages_total=first_messages_total,
        first_messages_today=first_messages_today,
        first_messages_7d=first_messages_7d,
        first_messages_30d=first_messages_30d,
    )


__all__ = [
    "AUTO_REPLY_EVENT",
    "FIRST_MESSAGE_EVENT",
    "UserStatistics",
    "record_statistics_event",
    "get_user_statistics",
]
