from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt

from app.database import AsyncSessionLocal
from app.services.user_service import get_or_create_user_settings

# ============================================================
# MUHIM:
#
# Bu — Nano-Bot'ning O'ZIGA kirishni himoyalovchi qo'shimcha
# parol. Telegram akkaunt paroli, OTP yoki 2FA BILAN HECH
# QANDAY ALOQASI YO'Q va ular bilan aralashtirilmaydi.
#
# Parol HECH QACHON plain text saqlanmaydi — faqat bcrypt hash.
# Parol qiymati hech qachon logga yozilmaydi.
# ============================================================

INACTIVITY_WINDOW = timedelta(hours=1)
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)

MIN_PASSWORD_LENGTH = 4
MAX_PASSWORD_LENGTH = 64


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PasswordCheckResult:
    ok: bool
    locked: bool = False
    locked_until: Optional[datetime] = None
    attempts_remaining: Optional[int] = None


# ============================================================
# HASHING (bcrypt)
# ============================================================

def hash_password(plain_password: str) -> str:
    """
    Parolni bcrypt bilan xeshlaydi. Natija DB'ga saqlanadi —
    plain qiymat hech qachon saqlanmaydi yoki logga yozilmaydi.
    """

    password_bytes = plain_password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())

    return hashed.decode("utf-8")


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def validate_password_format(
    plain_password: str,
) -> Optional[str]:
    """
    Parol formatini tekshiradi. Xato bo'lsa foydalanuvchiga
    ko'rsatiladigan xabar qaytaradi, aks holda None.
    """

    if not plain_password or not plain_password.strip():
        return "❌ Parol bo'sh bo'lishi mumkin emas."

    if len(plain_password) < MIN_PASSWORD_LENGTH:
        return (
            "❌ Parol kamida "
            f"{MIN_PASSWORD_LENGTH} ta belgidan iborat "
            "bo'lishi kerak."
        )

    if len(plain_password) > MAX_PASSWORD_LENGTH:
        return (
            "❌ Parol juda uzun "
            f"(maksimal {MAX_PASSWORD_LENGTH} belgi)."
        )

    return None


# ============================================================
# SETTINGS MUTATIONS
# ============================================================

async def set_password(
    user_id: int,
    plain_password: str,
) -> None:
    async with AsyncSessionLocal() as session:
        settings = await get_or_create_user_settings(
            session,
            user_id,
        )

        settings.password_hash = hash_password(plain_password)
        settings.password_enabled = True
        settings.failed_password_attempts = 0
        settings.password_locked_until = None
        settings.authenticated_until = (
            _now() + INACTIVITY_WINDOW
        )
        settings.last_activity_at = _now()

        await session.commit()


async def disable_password(user_id: int) -> None:
    async with AsyncSessionLocal() as session:
        settings = await get_or_create_user_settings(
            session,
            user_id,
        )

        settings.password_hash = None
        settings.password_enabled = False
        settings.failed_password_attempts = 0
        settings.password_locked_until = None
        settings.authenticated_until = None

        await session.commit()


# ============================================================
# ACTIVITY / SESSION TRACKING
# ============================================================

async def touch_activity(user_id: int) -> None:
    """
    Har bir RUXSAT BERILGAN interaction'dan keyin chaqiriladi.

    - last_activity_at har doim yangilanadi.
    - Agar parol yoqilgan bo'lsa, authenticated_until "sirg'anib
      boruvchi" (sliding) oyna sifatida uzaytiriladi — shu orqali
      foydalanuvchi faol bo'lgan davrda parol qayta so'ralmaydi.
    """

    async with AsyncSessionLocal() as session:
        settings = await get_or_create_user_settings(
            session,
            user_id,
        )

        now = _now()
        settings.last_activity_at = now

        if settings.password_enabled:
            settings.authenticated_until = (
                now + INACTIVITY_WINDOW
            )

        await session.commit()


async def needs_password_challenge(user_id: int) -> bool:
    async with AsyncSessionLocal() as session:
        settings = await get_or_create_user_settings(
            session,
            user_id,
        )

        if (
            not settings.password_enabled
            or not settings.password_hash
        ):
            return False

        if settings.authenticated_until is None:
            return True

        return _now() >= settings.authenticated_until


async def evaluate_activity(user_id: int) -> bool:
    """
    Middleware uchun bitta so'rovli qulay funksiya.

    - Agar parol talab qilinsa: True qaytaradi (hech narsa
      yangilanmaydi — chunki foydalanuvchi hali autentifikatsiya
      qilinmagan).
    - Aks holda: last_activity_at (va agar parol yoqilgan bo'lsa
      authenticated_until) yangilanadi, False qaytaradi.
    """

    async with AsyncSessionLocal() as session:
        settings = await get_or_create_user_settings(
            session,
            user_id,
        )

        now = _now()

        if settings.password_enabled and settings.password_hash:
            if (
                settings.authenticated_until is None
                or now >= settings.authenticated_until
            ):
                return True

            settings.authenticated_until = (
                now + INACTIVITY_WINDOW
            )

        settings.last_activity_at = now

        await session.commit()

        return False


async def is_password_enabled(user_id: int) -> bool:
    async with AsyncSessionLocal() as session:
        settings = await get_or_create_user_settings(
            session,
            user_id,
        )

        return bool(settings.password_enabled)


# ============================================================
# CHALLENGE / RATE LIMITING (brute-force himoya)
# ============================================================

async def check_password_attempt(
    user_id: int,
    plain_password: str,
) -> PasswordCheckResult:
    """
    Kiritilgan parolni tekshiradi. Muvaffaqiyatsiz urinishlar
    hisoblanadi va ma'lum chegaradan o'tsa, vaqtinchalik
    bloklanadi (rate limiting / brute-force himoya).
    """

    async with AsyncSessionLocal() as session:
        settings = await get_or_create_user_settings(
            session,
            user_id,
        )

        now = _now()

        if (
            settings.password_locked_until is not None
            and now < settings.password_locked_until
        ):
            return PasswordCheckResult(
                ok=False,
                locked=True,
                locked_until=settings.password_locked_until,
            )

        if not settings.password_hash:
            # Parol umuman o'rnatilmagan — challenge shart emas.
            return PasswordCheckResult(ok=True)

        is_valid = verify_password(
            plain_password,
            settings.password_hash,
        )

        if is_valid:
            settings.failed_password_attempts = 0
            settings.password_locked_until = None
            settings.authenticated_until = (
                now + INACTIVITY_WINDOW
            )
            settings.last_activity_at = now

            await session.commit()

            return PasswordCheckResult(ok=True)

        settings.failed_password_attempts += 1

        attempts_remaining = max(
            0,
            MAX_FAILED_ATTEMPTS
            - settings.failed_password_attempts,
        )

        locked = False
        locked_until = None

        if settings.failed_password_attempts >= MAX_FAILED_ATTEMPTS:
            locked_until = now + LOCKOUT_DURATION
            settings.password_locked_until = locked_until
            settings.failed_password_attempts = 0
            locked = True

        await session.commit()

        return PasswordCheckResult(
            ok=False,
            locked=locked,
            locked_until=locked_until,
            attempts_remaining=attempts_remaining,
        )


__all__ = [
    "INACTIVITY_WINDOW",
    "MAX_FAILED_ATTEMPTS",
    "LOCKOUT_DURATION",
    "PasswordCheckResult",
    "hash_password",
    "verify_password",
    "validate_password_format",
    "set_password",
    "disable_password",
    "touch_activity",
    "evaluate_activity",
    "needs_password_challenge",
    "is_password_enabled",
    "check_password_attempt",
]
