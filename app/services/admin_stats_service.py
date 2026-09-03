from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.database.models import (
    AutoReply,
    AutoReplyKeyword,
    FirstMessage,
    Payment,
    Referral,
    SecurityEvent,
    Statistics,
    Subscription,
    TelegramAccount,
    User,
)

# ============================================================
# PAYMENT STATUS — mavjud kodda hali Payment.status uchun aniq
# qiymatlar belgilanmagan (default "pending"). Kelajakdagi
# implementatsiyalar bilan mos ishlashi uchun eng ko'p
# tarqalgan status nomlari bilan moslashtirilgan.
# ============================================================

SUCCESS_PAYMENT_STATUSES = (
    "success",
    "successful",
    "paid",
    "completed",
)

PENDING_PAYMENT_STATUSES = ("pending",)

FAILED_PAYMENT_STATUSES = (
    "failed",
    "cancelled",
    "canceled",
    "error",
    "declined",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# 6.1 OVERVIEW STATISTICS
# ============================================================

@dataclass
class NewUsersWindow:
    today: int
    last_7_days: int
    last_30_days: int
    all_time: int


@dataclass
class OverviewStats:
    total_users: int
    active_users: int
    connected_accounts: int
    total_auto_replies: int
    active_auto_replies: int
    total_first_messages: int
    premium_users: int
    auto_replies_sent: int
    first_messages_sent: int
    referred_users: int
    total_payments: int
    total_revenue: float
    currency: str
    new_users: NewUsersWindow


async def get_overview_stats() -> OverviewStats:
    async with AsyncSessionLocal() as session:
        total_users = (
            await session.execute(
                select(func.count(User.id))
            )
        ).scalar_one()

        active_users = (
            await session.execute(
                select(func.count(User.id)).where(
                    User.active.is_(True)
                )
            )
        ).scalar_one()

        now = _now()
        today_start = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        new_users_today = (
            await session.execute(
                select(func.count(User.id)).where(
                    User.created_at >= today_start
                )
            )
        ).scalar_one()

        new_users_7d = (
            await session.execute(
                select(func.count(User.id)).where(
                    User.created_at >= now - timedelta(days=7)
                )
            )
        ).scalar_one()

        new_users_30d = (
            await session.execute(
                select(func.count(User.id)).where(
                    User.created_at >= now - timedelta(days=30)
                )
            )
        ).scalar_one()

        new_users_window = NewUsersWindow(
            today=new_users_today,
            last_7_days=new_users_7d,
            last_30_days=new_users_30d,
            all_time=total_users,
        )

        connected_accounts = (
            await session.execute(
                select(func.count(TelegramAccount.id)).where(
                    TelegramAccount.is_connected.is_(True)
                )
            )
        ).scalar_one()

        total_auto_replies = (
            await session.execute(
                select(func.count(AutoReply.id))
            )
        ).scalar_one()

        active_auto_replies = (
            await session.execute(
                select(func.count(AutoReply.id)).where(
                    AutoReply.is_active.is_(True)
                )
            )
        ).scalar_one()

        total_first_messages = (
            await session.execute(
                select(func.count(FirstMessage.id))
            )
        ).scalar_one()

        premium_users = (
            await session.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.status == "premium",
                    (
                        Subscription.premium_expires_at.is_(None)
                        | (
                            Subscription.premium_expires_at
                            > _now()
                        )
                    ),
                )
            )
        ).scalar_one()

        auto_replies_sent = (
            await session.execute(
                select(
                    func.coalesce(
                        func.sum(Statistics.auto_replies), 0
                    )
                )
            )
        ).scalar_one()

        first_messages_sent = (
            await session.execute(
                select(
                    func.coalesce(
                        func.sum(
                            Statistics.first_messages_sent
                        ),
                        0,
                    )
                )
            )
        ).scalar_one()

        referred_users = (
            await session.execute(
                select(func.count(Referral.id)).where(
                    Referral.referred_by.is_not(None)
                )
            )
        ).scalar_one()

        total_payments = (
            await session.execute(
                select(func.count(Payment.id))
            )
        ).scalar_one()

        revenue_result = await session.execute(
            select(
                func.coalesce(func.sum(Payment.amount), 0),
                Payment.currency,
            )
            .where(
                Payment.status.in_(SUCCESS_PAYMENT_STATUSES)
            )
            .group_by(Payment.currency)
            .order_by(func.sum(Payment.amount).desc())
            .limit(1)
        )

        revenue_row = revenue_result.first()

        total_revenue = float(revenue_row[0]) if revenue_row else 0.0
        currency = revenue_row[1] if revenue_row else "USD"

        return OverviewStats(
            total_users=total_users,
            active_users=active_users,
            connected_accounts=connected_accounts,
            total_auto_replies=total_auto_replies,
            active_auto_replies=active_auto_replies,
            total_first_messages=total_first_messages,
            premium_users=premium_users,
            auto_replies_sent=int(auto_replies_sent),
            first_messages_sent=int(first_messages_sent),
            referred_users=referred_users,
            total_payments=total_payments,
            total_revenue=total_revenue,
            currency=currency,
            new_users=new_users_window,
        )


# ============================================================
# 6.2 USERS
# ============================================================

@dataclass
class UserListItem:
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    active: bool
    created_at: datetime
    account_count: int
    auto_reply_count: int
    has_first_message: bool
    is_premium: bool
    referral_count: int


async def get_users_page(
    page: int = 1,
    page_size: int = 5,
):
    page = max(1, page)

    async with AsyncSessionLocal() as session:
        total = (
            await session.execute(
                select(func.count(User.id))
            )
        ).scalar_one()

        total_pages = max(1, (total + page_size - 1) // page_size)
        page = min(page, total_pages)

        result = await session.execute(
            select(User)
            .order_by(User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        users = result.scalars().all()
        user_ids = [user.id for user in users]

        account_counts = {}

        if user_ids:
            account_result = await session.execute(
                select(
                    TelegramAccount.user_id,
                    func.count(TelegramAccount.id),
                )
                .where(TelegramAccount.user_id.in_(user_ids))
                .group_by(TelegramAccount.user_id)
            )

            account_counts = dict(account_result.all())

        premium_ids = set()

        if user_ids:
            premium_result = await session.execute(
                select(Subscription.user_id).where(
                    Subscription.user_id.in_(user_ids),
                    Subscription.status == "premium",
                    (
                        Subscription.premium_expires_at.is_(None)
                        | (
                            Subscription.premium_expires_at
                            > _now()
                        )
                    ),
                )
            )

            premium_ids = set(premium_result.scalars().all())

        auto_reply_counts = {}

        if user_ids:
            auto_reply_result = await session.execute(
                select(
                    AutoReply.user_id,
                    func.count(AutoReply.id),
                )
                .where(AutoReply.user_id.in_(user_ids))
                .group_by(AutoReply.user_id)
            )

            auto_reply_counts = dict(
                auto_reply_result.all()
            )

        first_message_ids = set()

        if user_ids:
            first_message_result = await session.execute(
                select(FirstMessage.user_id).where(
                    FirstMessage.user_id.in_(user_ids)
                )
            )

            first_message_ids = set(
                first_message_result.scalars().all()
            )

        referral_counts = {}

        if user_ids:
            referral_result = await session.execute(
                select(
                    Referral.user_id,
                    Referral.referral_count,
                ).where(Referral.user_id.in_(user_ids))
            )

            referral_counts = dict(referral_result.all())

        items = [
            UserListItem(
                id=user.id,
                telegram_id=user.telegram_id,
                username=user.username,
                first_name=user.first_name,
                active=user.active,
                created_at=user.created_at,
                account_count=account_counts.get(user.id, 0),
                auto_reply_count=auto_reply_counts.get(
                    user.id, 0
                ),
                has_first_message=(
                    user.id in first_message_ids
                ),
                is_premium=user.id in premium_ids,
                referral_count=referral_counts.get(
                    user.id, 0
                ),
            )
            for user in users
        ]

        return items, total, total_pages, page


@dataclass
class UserDetail:
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    language: str
    active: bool
    created_at: datetime
    account_count: int
    connected_account_count: int
    auto_reply_count: int
    active_auto_reply_count: int
    has_first_message: bool
    first_message_active: bool
    premium_status: str
    referral_count: int
    referred_by: Optional[int]


async def get_user_detail(user_id: int) -> Optional[UserDetail]:
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)

        if user is None:
            return None

        account_count = (
            await session.execute(
                select(func.count(TelegramAccount.id)).where(
                    TelegramAccount.user_id == user_id
                )
            )
        ).scalar_one()

        connected_account_count = (
            await session.execute(
                select(func.count(TelegramAccount.id)).where(
                    TelegramAccount.user_id == user_id,
                    TelegramAccount.is_connected.is_(True),
                )
            )
        ).scalar_one()

        auto_reply_count = (
            await session.execute(
                select(func.count(AutoReply.id)).where(
                    AutoReply.user_id == user_id
                )
            )
        ).scalar_one()

        active_auto_reply_count = (
            await session.execute(
                select(func.count(AutoReply.id)).where(
                    AutoReply.user_id == user_id,
                    AutoReply.is_active.is_(True),
                )
            )
        ).scalar_one()

        first_message = (
            await session.execute(
                select(FirstMessage).where(
                    FirstMessage.user_id == user_id
                )
            )
        ).scalar_one_or_none()

        subscription = (
            await session.execute(
                select(Subscription).where(
                    Subscription.user_id == user_id
                )
            )
        ).scalar_one_or_none()

        if subscription is None:
            premium_status = "🔴 Yo'q"
        elif subscription.status == "premium" and (
            subscription.premium_expires_at is None
            or subscription.premium_expires_at > _now()
        ):
            premium_status = "🟢 Faol"
        else:
            premium_status = f"⚪️ {subscription.status}"

        referral = (
            await session.execute(
                select(Referral).where(
                    Referral.user_id == user_id
                )
            )
        ).scalar_one_or_none()

        return UserDetail(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language=user.language,
            active=user.active,
            created_at=user.created_at,
            account_count=account_count,
            connected_account_count=connected_account_count,
            auto_reply_count=auto_reply_count,
            active_auto_reply_count=active_auto_reply_count,
            has_first_message=first_message is not None,
            first_message_active=(
                bool(first_message.active)
                if first_message is not None
                else False
            ),
            premium_status=premium_status,
            referral_count=(
                referral.referral_count
                if referral is not None
                else 0
            ),
            referred_by=(
                referral.referred_by
                if referral is not None
                else None
            ),
        )


# ============================================================
# 6.3 AUTO REPLIES
# ============================================================

@dataclass
class AutoReplyStats:
    total: int
    active: int
    inactive: int
    top_keywords: List[tuple]
    messages_sent: int


async def get_auto_reply_stats(
    top_limit: int = 3,
) -> AutoReplyStats:
    async with AsyncSessionLocal() as session:
        total = (
            await session.execute(
                select(func.count(AutoReply.id))
            )
        ).scalar_one()

        active = (
            await session.execute(
                select(func.count(AutoReply.id)).where(
                    AutoReply.is_active.is_(True)
                )
            )
        ).scalar_one()

        top_keyword_rows = (
            await session.execute(
                select(
                    AutoReplyKeyword.keyword,
                    func.count(AutoReplyKeyword.id),
                )
                .group_by(AutoReplyKeyword.keyword)
                .order_by(func.count(AutoReplyKeyword.id).desc())
                .limit(top_limit)
            )
        ).all()

        messages_sent = (
            await session.execute(
                select(
                    func.coalesce(
                        func.sum(Statistics.auto_replies), 0
                    )
                )
            )
        ).scalar_one()

        return AutoReplyStats(
            total=total,
            active=active,
            inactive=total - active,
            top_keywords=[
                (row[0], row[1]) for row in top_keyword_rows
            ],
            messages_sent=int(messages_sent),
        )


# ============================================================
# 6.3b FIRST MESSAGE
# ============================================================

@dataclass
class FirstMessageStats:
    total: int
    active: int
    inactive: int
    messages_sent: int


async def get_first_message_stats() -> FirstMessageStats:
    async with AsyncSessionLocal() as session:
        total = (
            await session.execute(
                select(func.count(FirstMessage.id))
            )
        ).scalar_one()

        active = (
            await session.execute(
                select(func.count(FirstMessage.id)).where(
                    FirstMessage.active.is_(True)
                )
            )
        ).scalar_one()

        messages_sent = (
            await session.execute(
                select(
                    func.coalesce(
                        func.sum(
                            Statistics.first_messages_sent
                        ),
                        0,
                    )
                )
            )
        ).scalar_one()

        return FirstMessageStats(
            total=total,
            active=active,
            inactive=total - active,
            messages_sent=int(messages_sent),
        )


# ============================================================
# 6.4 PREMIUM
# ============================================================

@dataclass
class PremiumStats:
    total_premium: int
    active_premium: int
    expiring_soon: int
    revenue: float
    currency: str


async def get_premium_stats() -> PremiumStats:
    async with AsyncSessionLocal() as session:
        total_premium = (
            await session.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.status == "premium"
                )
            )
        ).scalar_one()

        now = _now()

        active_premium = (
            await session.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.status == "premium",
                    (
                        Subscription.premium_expires_at.is_(None)
                        | (Subscription.premium_expires_at > now)
                    ),
                )
            )
        ).scalar_one()

        soon = now + timedelta(days=7)

        expiring_soon = (
            await session.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.status == "premium",
                    Subscription.premium_expires_at.is_not(None),
                    Subscription.premium_expires_at > now,
                    Subscription.premium_expires_at <= soon,
                )
            )
        ).scalar_one()

        revenue_row = (
            await session.execute(
                select(
                    func.coalesce(
                        func.sum(Payment.amount), 0
                    ),
                    Payment.currency,
                )
                .where(
                    Payment.status.in_(
                        SUCCESS_PAYMENT_STATUSES
                    )
                )
                .group_by(Payment.currency)
                .order_by(func.sum(Payment.amount).desc())
                .limit(1)
            )
        ).first()

        return PremiumStats(
            total_premium=total_premium,
            active_premium=active_premium,
            expiring_soon=expiring_soon,
            revenue=float(revenue_row[0]) if revenue_row else 0.0,
            currency=revenue_row[1] if revenue_row else "USD",
        )


# ============================================================
# 6.5 PAYMENTS
# ============================================================

@dataclass
class PaymentStats:
    total: int
    successful: int
    pending: int
    failed: int
    revenue_by_currency: List[tuple]


async def get_payment_stats() -> PaymentStats:
    async with AsyncSessionLocal() as session:
        total = (
            await session.execute(
                select(func.count(Payment.id))
            )
        ).scalar_one()

        successful = (
            await session.execute(
                select(func.count(Payment.id)).where(
                    Payment.status.in_(
                        SUCCESS_PAYMENT_STATUSES
                    )
                )
            )
        ).scalar_one()

        pending = (
            await session.execute(
                select(func.count(Payment.id)).where(
                    Payment.status.in_(
                        PENDING_PAYMENT_STATUSES
                    )
                )
            )
        ).scalar_one()

        failed = (
            await session.execute(
                select(func.count(Payment.id)).where(
                    Payment.status.in_(
                        FAILED_PAYMENT_STATUSES
                    )
                )
            )
        ).scalar_one()

        revenue_rows = (
            await session.execute(
                select(
                    Payment.currency,
                    func.coalesce(
                        func.sum(Payment.amount), 0
                    ),
                )
                .where(
                    Payment.status.in_(
                        SUCCESS_PAYMENT_STATUSES
                    )
                )
                .group_by(Payment.currency)
            )
        ).all()

        return PaymentStats(
            total=total,
            successful=successful,
            pending=pending,
            failed=failed,
            revenue_by_currency=[
                (row[0], float(row[1])) for row in revenue_rows
            ],
        )


# ============================================================
# 6.7 SECURITY
# ============================================================

@dataclass
class SecurityStats:
    high_count: int
    critical_count: int
    recent_critical_24h: int
    recent_events: List[SecurityEvent]


async def get_security_stats(
    recent_limit: int = 5,
) -> SecurityStats:
    async with AsyncSessionLocal() as session:
        high_count = (
            await session.execute(
                select(func.count(SecurityEvent.id)).where(
                    SecurityEvent.severity == "HIGH"
                )
            )
        ).scalar_one()

        critical_count = (
            await session.execute(
                select(func.count(SecurityEvent.id)).where(
                    SecurityEvent.severity == "CRITICAL"
                )
            )
        ).scalar_one()

        since = _now() - timedelta(hours=24)

        recent_critical_24h = (
            await session.execute(
                select(func.count(SecurityEvent.id)).where(
                    SecurityEvent.severity.in_(
                        ("HIGH", "CRITICAL")
                    ),
                    SecurityEvent.created_at >= since,
                )
            )
        ).scalar_one()

        recent_events = (
            await session.execute(
                select(SecurityEvent)
                .order_by(SecurityEvent.created_at.desc())
                .limit(recent_limit)
            )
        ).scalars().all()

        return SecurityStats(
            high_count=high_count,
            critical_count=critical_count,
            recent_critical_24h=recent_critical_24h,
            recent_events=list(recent_events),
        )


__all__ = [
    "NewUsersWindow",
    "OverviewStats",
    "get_overview_stats",
    "UserListItem",
    "get_users_page",
    "UserDetail",
    "get_user_detail",
    "AutoReplyStats",
    "get_auto_reply_stats",
    "FirstMessageStats",
    "get_first_message_stats",
    "PremiumStats",
    "get_premium_stats",
    "PaymentStats",
    "get_payment_stats",
    "SecurityStats",
    "get_security_stats",
]
