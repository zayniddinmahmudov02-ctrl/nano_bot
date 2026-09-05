from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from aiogram import Bot
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
from app.services.user_service import get_user_language

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None
_bot_instance: Optional[Bot] = None

EXCHANGE_RATE_REFRESH_MINUTES = 360
ACTIVITY_EXPIRY_SWEEP_MINUTES = 15
UNANSWERED_REMINDER_SWEEP_MINUTES = 30


def set_bot_instance(bot: Bot) -> None:
    """
    main.py startup vaqtida chaqiriladi — 24 soatlik "javob
    berilmagan chat" eslatmalarini yuborish uchun Bot obyektiga
    referens saqlanadi.
    """

    global _bot_instance
    _bot_instance = bot


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


async def _job_send_unanswered_reminders() -> None:
    """
    24 soatdan ortiq javobsiz turgan chatlar uchun Nano-Bot
    foydalanuvchisiga (akkaunt egasiga) BIR MARTA eslatma
    yuboradi (spec 4/9-bo'lim).

    MUHIM: bitta periodic job orqali BARCHA tegishli yozuvlar
    qayta ishlanadi — har bir chat uchun alohida scheduler job
    yaratilmaydi. Har bir yozuv uchun reminder faqat bir marta
    yuboriladi (`reminder_sent` bayrog'i orqali) — spam bo'lmaydi.
    Xabar matni/tarixi bu yerda ishlatilmaydi/saqlanmaydi —
    faqat texnik metadata (ism/username/kutish vaqti).
    """

    if _bot_instance is None:
        return

    from app.keyboards.nano import nano_unanswered_reminder_keyboard
    from app.services.unanswered_chat_service import (
        get_due_reminders,
        try_claim_reminder,
    )
    from app.texts import t

    try:
        targets = await get_due_reminders()
    except Exception:
        logger.exception(
            "Scheduler: javobsiz chat eslatmalarini olishda "
            "xatolik."
        )
        return

    for target in targets:
        try:
            # MUHIM (race condition — spec 6/8-bo'lim): `targets`
            # ro'yxati bir necha soniya OLDIN so'ralgan bo'lishi
            # mumkin — shu oraliqda foydalanuvchi javob yozib,
            # yozuv ANSWERED bo'lib ulgurgan bo'lishi mumkin.
            # Xabar yuborishdan DARHOL OLDIN yozuv ATOMIK ravishda
            # "band" qilinadi (bitta UPDATE ... WHERE); agar bu
            # False qaytarsa — USER REPLY ustunlik qilgan, reminder
            # UMUMAN yuborilmaydi.
            claimed = await try_claim_reminder(target.record_id)

            if not claimed:
                continue

            async with AsyncSessionLocal() as session:
                lang = await get_user_language(
                    session,
                    target.owner_telegram_id,
                )

            display_name = (
                target.peer_name
                or (
                    f"@{target.peer_username}"
                    if target.peer_username
                    else f"ID {target.peer_id}"
                )
            )

            text = (
                f"{t('unanswered_reminder_title', lang)}\n\n"
                f"{t('unanswered_reminder_body', lang)}\n\n"
                f"{t('unanswered_reminder_peer_line', lang, name=display_name)}"
            )

            keyboard = nano_unanswered_reminder_keyboard(
                record_id=target.record_id,
                peer_name=target.peer_name,
                peer_username=target.peer_username,
                peer_id=target.peer_id,
                lang=lang,
            )

            await _bot_instance.send_message(
                target.owner_telegram_id,
                text,
                reply_markup=keyboard,
            )

        except Exception:
            # MUHIM: reminder ENDI xabar yuborishdan OLDIN "band"
            # qilinadi — shu sabab send bosqichida xatolik (masalan
            # bot bloklangan) bo'lsa ham qayta urinilmaydi (record
            # allaqachon reminder_sent=True). Bu — race condition'ni
            # yopish uchun ongli almashinuv: qayta-urinish o'rniga
            # "javob berilgan chatga ikkinchi marta eslatma
            # yuborilmasligi" kafolati ustunlik qiladi.
            logger.exception(
                "Javobsiz chat eslatmasini yuborishda xatolik "
                "(record_id=%s).",
                target.record_id,
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

    scheduler.add_job(
        _job_send_unanswered_reminders,
        "interval",
        minutes=UNANSWERED_REMINDER_SWEEP_MINUTES,
        id="send_unanswered_reminders",
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
    "set_bot_instance",
    "start_scheduler",
    "stop_scheduler",
    "is_scheduler_running",
]
