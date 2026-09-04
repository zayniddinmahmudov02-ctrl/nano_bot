from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TRIAL_DURATION_DAYS
from app.database import AsyncSessionLocal
from app.database.models import Subscription

# Status string qiymatlari — Subscription.status ustunida
# saqlanadi (asosan STATISTIKA/ADMIN PANEL o'qish uchun qulaylik
# maqsadida; ACCESS tekshiruvining o'zi har doim vaqt
# belgilaridan JONLI hisoblanadi, shu status maydonining eskirib
# qolishiga bog'liq emas).
STATUS_TRIAL = "trial"
STATUS_ACTIVE = "active"
STATUS_EXPIRED = "expired"


class AccessStatus(str, Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_or_create_subscription(
    session: AsyncSession,
    user_id: int,
) -> Subscription:
    """
    users.id bo'yicha Subscription (Faollik) qatorini topadi.

    MUHIM: agar qator hali mavjud bo'lmasa — bu YANGI
    foydalanuvchi degani, shu yerda 7 kunlik bepul TRIAL
    boshlanadi. Trial faqat BIR MARTA beriladi: qator allaqachon
    mavjud bo'lsa (trial ishlatilgan yoki yo'qligidan qat'i
    nazar), qayta trial berilmaydi — funksiya faqat mavjud
    qatorni qaytaradi.
    """

    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id
        )
    )

    subscription = result.scalar_one_or_none()

    if subscription is None:
        now = _now()

        subscription = Subscription(
            user_id=user_id,
            status=STATUS_TRIAL,
            trial_started_at=now,
            trial_expires_at=(
                now + timedelta(days=TRIAL_DURATION_DAYS)
            ),
        )

        session.add(subscription)
        await session.flush()

    return subscription


def is_trial_active(subscription: Subscription) -> bool:
    if subscription.trial_expires_at is None:
        return False

    return subscription.trial_expires_at > _now()


def is_activity_active(subscription: Subscription) -> bool:
    if subscription.activity_expires_at is None:
        return False

    return subscription.activity_expires_at > _now()


def has_access(subscription: Subscription) -> bool:
    """
    Botning pullik funksiyalariga kirish ruxsati bormi.

    Qoida (spec 13-bo'lim):
    trial active → ruxsat
    OR
    activity active → ruxsat
    """

    return is_trial_active(subscription) or is_activity_active(
        subscription
    )


def get_access_status(subscription: Subscription) -> AccessStatus:
    if is_trial_active(subscription):
        return AccessStatus.TRIAL

    if is_activity_active(subscription):
        return AccessStatus.ACTIVE

    return AccessStatus.EXPIRED


def get_activity_expiry(
    subscription: Subscription,
) -> Optional[datetime]:
    return subscription.activity_expires_at


@dataclass
class AccessCheckResult:
    allowed: bool
    status: AccessStatus
    trial_expires_at: Optional[datetime]
    activity_expires_at: Optional[datetime]


async def check_access(telegram_user_id: int) -> AccessCheckResult:
    """
    Botning pullik funksiyalariga kirishdan OLDIN chaqiriladigan
    guard funksiyasi (access middleware o'rnini bosadi).

    Ichki `users.id` emas, TELEGRAM ID qabul qiladi — chaqiruvchi
    handlerlar odatda faqat shuni bilishadi.
    """

    from app.services.user_service import get_user_by_telegram_id

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_user_id,
        )

        if user is None:
            return AccessCheckResult(
                allowed=False,
                status=AccessStatus.EXPIRED,
                trial_expires_at=None,
                activity_expires_at=None,
            )

        subscription = await get_or_create_subscription(
            session,
            user.id,
        )

        await session.commit()

        return AccessCheckResult(
            allowed=has_access(subscription),
            status=get_access_status(subscription),
            trial_expires_at=subscription.trial_expires_at,
            activity_expires_at=(
                subscription.activity_expires_at
            ),
        )


async def grant_activity(
    session: AsyncSession,
    user_id: int,
    duration_days: int,
) -> Subscription:
    """
    Foydalanuvchiga Faollik beradi (yangi to'lov tasdiqlangach
    chaqiriladi).

    Qoida (spec 10-bo'lim): agar mavjud Faollik hali tugamagan
    bo'lsa, yangi muddat MAVJUD muddat USTIGA qo'shiladi.
    Aks holda: yangi muddat = hozirgi vaqt + paket davomiyligi.
    """

    subscription = await get_or_create_subscription(
        session,
        user_id,
    )

    now = _now()

    current_expiry = subscription.activity_expires_at

    base = (
        current_expiry
        if current_expiry is not None and current_expiry > now
        else now
    )

    subscription.activity_expires_at = base + timedelta(
        days=duration_days
    )
    subscription.status = STATUS_ACTIVE

    await session.flush()

    return subscription


__all__ = [
    "STATUS_TRIAL",
    "STATUS_ACTIVE",
    "STATUS_EXPIRED",
    "AccessStatus",
    "AccessCheckResult",
    "get_or_create_subscription",
    "is_trial_active",
    "is_activity_active",
    "has_access",
    "get_access_status",
    "get_activity_expiry",
    "check_access",
    "grant_activity",
]
