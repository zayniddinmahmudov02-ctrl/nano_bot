from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


# ============================================================
# USER
# ============================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
    )

    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    first_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    last_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    language: Mapped[str] = mapped_column(
        String(5),
        default="uz",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    telegram_accounts = relationship(
        "TelegramAccount",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    auto_replies = relationship(
        "AutoReply",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    first_message = relationship(
        "FirstMessage",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    referral = relationship(
        "Referral",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    statistics = relationship(
        "Statistics",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    settings = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    subscription = relationship(
        "Subscription",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


# ============================================================
# TELEGRAM ACCOUNT
# ============================================================

class TelegramAccount(Base):
    __tablename__ = "telegram_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    session_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    session_data: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="disconnected",
    )

    auto_reply_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    connected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    user = relationship(
        "User",
        back_populates="telegram_accounts",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "telegram_id",
            name="uq_user_telegram_account",
        ),
    )


# ============================================================
# AUTO REPLY
# ============================================================

class AutoReply(Base):
    __tablename__ = "auto_replies"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        index=True,
    )

    content_type: Mapped[str] = mapped_column(
        String(30),
        default="text",
    )

    text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    media_id: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    media_type: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
    )

    link: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    buttons: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
    )

    delay_seconds: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    usage_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship(
        "User",
        back_populates="auto_replies",
    )

    keywords = relationship(
        "AutoReplyKeyword",
        back_populates="auto_reply",
        cascade="all, delete-orphan",
    )


# ============================================================
# AUTO REPLY KEYWORDS
# ============================================================

class AutoReplyKeyword(Base):
    __tablename__ = "auto_reply_keywords"

    id: Mapped[int] = mapped_column(primary_key=True)

    auto_reply_id: Mapped[int] = mapped_column(
        ForeignKey(
            "auto_replies.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    keyword: Mapped[str] = mapped_column(
        String(255),
        index=True,
    )

    auto_reply = relationship(
        "AutoReply",
        back_populates="keywords",
    )

    __table_args__ = (
        UniqueConstraint(
            "auto_reply_id",
            "keyword",
            name="uq_auto_reply_keyword",
        ),
    )


# ============================================================
# FIRST MESSAGE
# ============================================================

class FirstMessage(Base):
    __tablename__ = "first_messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    content_type: Mapped[str] = mapped_column(
        String(30),
        default="text",
    )

    text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    media_id: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    media_type: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
    )

    link: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    buttons: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship(
        "User",
        back_populates="first_message",
    )


# ============================================================
# REFERRALS
# ============================================================

class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    referral_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
    )

    referred_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    referral_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    user = relationship(
        "User",
        back_populates="referral",
        foreign_keys=[user_id],
    )


# ============================================================
# STATISTICS
# ============================================================

class Statistics(Base):
    __tablename__ = "statistics"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    people_replied: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    total_auto_replies: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    today_replies: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    month_replies: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    last_reset_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    user = relationship(
        "User",
        back_populates="statistics",
    )


# ============================================================
# USER SETTINGS
# ============================================================

class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    display_first_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    display_last_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    language: Mapped[str] = mapped_column(
        String(5),
        default="uz",
    )

    user = relationship(
        "User",
        back_populates="settings",
    )


# ============================================================
# SUBSCRIPTION
# ============================================================

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="free",
        index=True,
    )

    trial_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    subscription_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    subscription_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    payment_provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    payment_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    user = relationship(
        "User",
        back_populates="subscription",
    )


# ============================================================
# PAYMENT
# ============================================================

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    amount: Mapped[int] = mapped_column(
        Integer,
        default=1,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="USD",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
    )

    provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    provider_payment_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )


# ============================================================
# ADMIN STATISTICS
# ============================================================

class AdminStatistics(Base):
    __tablename__ = "admin_statistics"

    id: Mapped[int] = mapped_column(primary_key=True)

    total_users: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    total_auto_replies: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    total_payments: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    total_revenue: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )