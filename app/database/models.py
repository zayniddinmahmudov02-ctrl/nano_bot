from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )

    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    first_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    last_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    language: Mapped[str] = mapped_column(
        String(5),
        default="uz",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    settings: Mapped["UserSettings | None"] = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    telegram_accounts: Mapped[list["TelegramAccount"]] = relationship(
        "TelegramAccount",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    auto_replies: Mapped[list["AutoReply"]] = relationship(
        "AutoReply",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    first_message: Mapped["FirstMessage | None"] = relationship(
        "FirstMessage",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    referral: Mapped["Referral | None"] = relationship(
        "Referral",
        foreign_keys="Referral.user_id",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    statistics: Mapped["Statistics | None"] = relationship(
        "Statistics",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    subscription: Mapped["Subscription | None"] = relationship(
        "Subscription",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    display_first_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    display_last_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    language: Mapped[str] = mapped_column(
        String(5),
        default="uz",
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="settings",
    )


class TelegramAccount(Base):
    __tablename__ = "telegram_accounts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    session_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_connected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="telegram_accounts",
    )

    auto_replies: Mapped[list["AutoReply"]] = relationship(
        "AutoReply",
        back_populates="telegram_account",
    )


class AutoReply(Base):
    __tablename__ = "auto_replies"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    telegram_account_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "telegram_accounts.id",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    message_type: Mapped[str] = mapped_column(
        String(30),
        default="text",
        nullable=False,
    )

    message_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    file_id: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    link: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="auto_replies",
    )

    telegram_account: Mapped[
        "TelegramAccount | None"
    ] = relationship(
        "TelegramAccount",
        back_populates="auto_replies",
    )

    keywords: Mapped[list["AutoReplyKeyword"]] = relationship(
        "AutoReplyKeyword",
        back_populates="auto_reply",
        cascade="all, delete-orphan",
    )


class AutoReplyKeyword(Base):
    __tablename__ = "auto_reply_keywords"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    auto_reply_id: Mapped[int] = mapped_column(
        ForeignKey(
            "auto_replies.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    keyword: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    auto_reply: Mapped["AutoReply"] = relationship(
        "AutoReply",
        back_populates="keywords",
    )


class FirstMessage(Base):
    __tablename__ = "first_messages"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    message_type: Mapped[str] = mapped_column(
        String(30),
        default="text",
        nullable=False,
    )

    message_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    file_id: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    link: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="first_message",
    )


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    referred_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    referral_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    referral_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="referral",
    )

    referrer: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[referred_by],
    )


class Statistics(Base):
    __tablename__ = "statistics"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    people_replied: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_auto_replies: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    today_replies: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    month_replies: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="statistics",
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="trial",
        nullable=False,
    )

    trial_started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    premium_started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    premium_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="subscription",
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="USD",
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
    )

    provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    transaction_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="payments",
    )


class AdminStatistics(Base):
    __tablename__ = "admin_statistics"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    total_users: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_auto_replies: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_replied_people: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_payments: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    total_revenue: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )