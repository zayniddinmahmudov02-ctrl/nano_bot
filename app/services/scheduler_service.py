from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import Subscription
from app.services.activity_service import (
    STATUS_EXPIRED,
    is_activity_active,
    is_trial_active,
)
from app.services.exchange_rate_service import refresh_exchange_rate

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None

EXCHANGE_RATE_REFRESH_MINUTES = 360
ACTIVITY_EXPIRY_SWEEP_MINUTES = 15


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _job_refresh_exchange_rate() -> None:
    try:
        await refresh_exchange_rate()
    except Exception:
        logger.exception(
            "Scheduler: exchange rate yangilashda xatolik."
        )


async def _job_sweep_expired_activity() -> None:
    """
    Muddati tugagan trial/Faollik holatlarini `status` maydonida
    "expired" deb belgilaydi (faqat statistika/admin panel
    o'qishi uchun qulaylik — ACCESS tekshiruvining o'zi bu
    maydonga bog'liq EMAS, u har doim vaqt belgilaridan JONLI
    hisoblanadi, shu sababli bu job ishlamay qolsa ham
    foydalanuvchi kirish huquqi noto'g'ri hisoblanmaydi).
    """

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Subscription).where(
                    Subscription.status != STATUS_EXPIRED
                )
            )

            subscriptions = result.scalars().all()

            changed = 0

            for subscription in subscriptions:
                if is_trial_active(
                    subscription
                ) or is_activity_active(subscription):
                    continue

                # Trial yoki Faollik hech qachon boshlanmagan
                # (ikkalasi ham NULL) — bu hali "expired" emas,
                # shunchaki hech narsa sotib olinmagan holat.
                if (
                    subscription.trial_expires_at is None
                    and subscription.activity_expires_at is None
                ):
                    continue

                subscription.status = STATUS_EXPIRED
                changed += 1

            if changed:
                await session.commit()

                logger.info(
                    "Scheduler: %s ta Faollik holati "
                    "'expired' deb belgilandi.",
                    changed,
                )

    except Exception:
        logger.exception(
            "Scheduler: Faollik muddatini tekshirishda xatolik."
        )


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        _job_refresh_exchange_rate,
        "interval",
        minutes=EXCHANGE_RATE_REFRESH_MINUTES,
        id="refresh_exchange_rate",
        next_run_time=_now(),
        replace_existing=True,
    )

    scheduler.add_job(
        _job_sweep_expired_activity,
        "interval",
        minutes=ACTIVITY_EXPIRY_SWEEP_MINUTES,
        id="sweep_expired_activity",
        next_run_time=_now(),
        replace_existing=True,
    )

    return scheduler


async def start_scheduler() -> None:
    global _scheduler

    if _scheduler is not None:
        return

    _scheduler = create_scheduler()
    _scheduler.start()

    logger.info(
        "Scheduler ishga tushdi (exchange rate + activity "
        "expiry)."
    )


async def stop_scheduler() -> None:
    global _scheduler

    if _scheduler is None:
        return

    try:
        _scheduler.shutdown(wait=False)
    except Exception:
        logger.exception("Scheduler to'xtatishda xatolik.")

    _scheduler = None


def is_scheduler_running() -> bool:
    return _scheduler is not None and _scheduler.running


__all__ = [
    "start_scheduler",
    "stop_scheduler",
    "is_scheduler_running",
]
