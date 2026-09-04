from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

from app.database import check_database
from app.services.auto_reply_engine import auto_reply_engine
from app.services.first_message_engine import (
    first_message_engine,
)
from app.services.scheduler_service import is_scheduler_running
from app.telegram.user_client import telegram_client_manager

logger = logging.getLogger(__name__)

STATUS_RUNNING = "🟢 Running"
STATUS_WARNING = "🟡 Warning"
STATUS_STOPPED = "🔴 Stopped"


@dataclass
class ComponentStatus:
    name: str
    status: str
    detail: str = field(default="")


async def get_system_status() -> List[ComponentStatus]:
    """
    Nano-Bot'ning asosiy komponentlari holatini xavfsiz tarzda
    tekshiradi. Har bir tekshiruv o'z ichida try/except bilan
    o'ralgan — bitta komponent xato bersa ham, boshqalarining
    holati ko'rsatiladi va admin panel yiqilmaydi.
    """

    results: List[ComponentStatus] = []

    # ------------------------------------------------------
    # BOT
    # ------------------------------------------------------
    # Agar shu kod ishga tushgan bo'lsa, bot polling jarayoni
    # ishlab turibdi.

    results.append(
        ComponentStatus("Bot", STATUS_RUNNING)
    )

    # ------------------------------------------------------
    # POSTGRESQL
    # ------------------------------------------------------

    try:
        db_ok = await check_database()

        results.append(
            ComponentStatus(
                "PostgreSQL",
                STATUS_RUNNING if db_ok else STATUS_STOPPED,
            )
        )

    except Exception:
        logger.exception(
            "Health check: PostgreSQL tekshiruvi xato berdi."
        )
        results.append(
            ComponentStatus("PostgreSQL", STATUS_STOPPED)
        )

    # ------------------------------------------------------
    # TELEGRAM LISTENER (Telethon user clientlar)
    # ------------------------------------------------------

    try:
        active_clients = len(telegram_client_manager.clients)

        if active_clients > 0:
            results.append(
                ComponentStatus(
                    "Telegram Listener",
                    STATUS_RUNNING,
                    f"{active_clients} ta akkaunt ulangan",
                )
            )
        else:
            results.append(
                ComponentStatus(
                    "Telegram Listener",
                    STATUS_WARNING,
                    "Ulangan akkaunt yo'q",
                )
            )

    except Exception:
        logger.exception(
            "Health check: Telegram Listener tekshiruvi "
            "xato berdi."
        )
        results.append(
            ComponentStatus(
                "Telegram Listener", STATUS_STOPPED
            )
        )

    # ------------------------------------------------------
    # AUTO REPLY ENGINE
    # ------------------------------------------------------

    try:
        ar_active = auto_reply_engine.active_account_count()

        results.append(
            ComponentStatus(
                "Auto Reply Engine",
                (
                    STATUS_RUNNING
                    if ar_active > 0
                    else STATUS_WARNING
                ),
                f"{ar_active} ta listener faol",
            )
        )

    except Exception:
        logger.exception(
            "Health check: Auto Reply Engine tekshiruvi "
            "xato berdi."
        )
        results.append(
            ComponentStatus(
                "Auto Reply Engine", STATUS_STOPPED
            )
        )

    # ------------------------------------------------------
    # FIRST MESSAGE ENGINE
    # ------------------------------------------------------

    try:
        fm_active = (
            first_message_engine.active_account_count()
        )

        results.append(
            ComponentStatus(
                "First Message Engine",
                (
                    STATUS_RUNNING
                    if fm_active > 0
                    else STATUS_WARNING
                ),
                f"{fm_active} ta listener faol",
            )
        )

    except Exception:
        logger.exception(
            "Health check: First Message Engine tekshiruvi "
            "xato berdi."
        )
        results.append(
            ComponentStatus(
                "First Message Engine", STATUS_STOPPED
            )
        )

    # ------------------------------------------------------
    # SCHEDULER
    # ------------------------------------------------------
    # Exchange rate refresh + Faollik muddati sweep job'lari
    # shu scheduler orqali ishlaydi (app/services/scheduler_service.py).

    results.append(
        ComponentStatus(
            "Scheduler",
            (
                STATUS_RUNNING
                if is_scheduler_running()
                else STATUS_STOPPED
            ),
        )
    )

    return results


__all__ = [
    "STATUS_RUNNING",
    "STATUS_WARNING",
    "STATUS_STOPPED",
    "ComponentStatus",
    "get_system_status",
]
