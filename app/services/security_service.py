from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from aiogram import Bot

from app.config import ADMIN_IDS
from app.database import AsyncSessionLocal
from app.database.models import SecurityEvent
from app.utils.logger import redact_secrets

logger = logging.getLogger(__name__)


class SecuritySeverity:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


_ALERTED_SEVERITIES = {
    SecuritySeverity.HIGH,
    SecuritySeverity.CRITICAL,
}

# Bir xil hodisa adminni spam qilmasligi uchun debounce oynasi.
_ALERT_DEBOUNCE_SECONDS = 300

# (event_type, severity, user_id, telegram_account_id) -> oxirgi
# ogohlantirish yuborilgan vaqt (monotonic).
_last_alert_sent: dict = {}

_bot_instance: Optional[Bot] = None


def set_bot_instance(bot: Bot) -> None:
    """
    main.py startup vaqtida chaqiriladi — security alertlarni
    yuborish uchun Bot obyektiga referens saqlanadi.
    """

    global _bot_instance
    _bot_instance = bot


def _should_alert(key: tuple) -> bool:
    now = time.monotonic()
    last = _last_alert_sent.get(key)

    if last is not None and (now - last) < _ALERT_DEBOUNCE_SECONDS:
        return False

    _last_alert_sent[key] = now
    return True


async def _send_admin_alert(
    *,
    event_type: str,
    severity: str,
    safe_description: str,
    source: Optional[str],
) -> None:
    if _bot_instance is None:
        return

    if not ADMIN_IDS:
        return

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    text = (
        "🚨 <b>SECURITY ALERT</b>\n\n"
        "Nano-Bot xavfsizlik hodisasini aniqladi.\n\n"
        f"Daraja: <b>{severity}</b>\n"
        f"Hodisa: <b>{event_type}</b>\n"
        f"Vaqt: {timestamp}\n"
        f"Manba: {source or '—'}\n\n"
        f"{safe_description}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await _bot_instance.send_message(admin_id, text)
        except Exception:
            logger.exception(
                "Admin'ga security alert yuborib bo'lmadi."
            )


async def record_security_event(
    *,
    event_type: str,
    severity: str,
    safe_description: str,
    source: Optional[str] = None,
    user_id: Optional[int] = None,
    telegram_account_id: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> None:
    """
    Xavfsizlik hodisasini DB'ga yozadi va HIGH/CRITICAL
    darajadagi hodisalar uchun admin(lar)ga ogohlantirish
    yuboradi (debounce bilan, spam qilmasdan).

    MUHIM: safe_description va metadata hech qachon maxfiy
    qiymat (token/parol/session) o'z ichiga olmasligi kerak —
    qo'shimcha ehtiyot chorasi sifatida ular yozishdan oldin
    ham sanitize qilinadi.
    """

    safe_description = (
        redact_secrets(safe_description) or safe_description
    )

    metadata_json = None

    if metadata:
        try:
            sanitized_metadata = {
                str(key): redact_secrets(str(value))
                for key, value in metadata.items()
            }
            metadata_json = json.dumps(
                sanitized_metadata,
                ensure_ascii=False,
            )
        except Exception:
            metadata_json = None

    try:
        async with AsyncSessionLocal() as session:
            event = SecurityEvent(
                event_type=event_type,
                severity=severity,
                safe_description=safe_description,
                source=source,
                user_id=user_id,
                telegram_account_id=telegram_account_id,
                metadata_json=metadata_json,
            )

            session.add(event)
            await session.commit()

    except Exception:
        logger.exception(
            "Security event DB'ga yozilmadi: event_type=%s",
            event_type,
        )

    logger.warning(
        "SECURITY_EVENT | %s | %s | %s",
        severity,
        event_type,
        safe_description,
    )

    if severity not in _ALERTED_SEVERITIES:
        return

    debounce_key = (
        event_type,
        severity,
        user_id,
        telegram_account_id,
    )

    if not _should_alert(debounce_key):
        return

    await _send_admin_alert(
        event_type=event_type,
        severity=severity,
        safe_description=safe_description,
        source=source,
    )


__all__ = [
    "SecuritySeverity",
    "set_bot_instance",
    "record_security_event",
]
