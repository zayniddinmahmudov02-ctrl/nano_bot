from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base


# ============================================================
# USER
# ============================================================

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
        String(10),
        default="uz",
        nullable=False,
    )

    # Python: user.active
    # PostgreSQL: users.is_active
    active: Mapped[bool] = mapped_column(
        "is_active",
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================
# USER SETTINGS
# ============================================================

class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    language: Mapped[str] = mapped_column(
        String(10),
        default="uz",
        nullable=False,
    )

    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # ------------------------------------------------------
    # BOT PAROLI / INACTIVITY LOCK (21-bo'lim)
    # ------------------------------------------------------
    # MUHIM: bu — Telegram akkaunt paroli/2FA EMAS. Bu faqat
    # Nano-Bot'ning O'ZIGA kirishni himoyalovchi, foydalanuvchi
    # o'rnatgan qo'shimcha parol. Hech qachon plain text
    # saqlanmaydi — faqat bcrypt hash.

    password_hash: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    password_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    authenticated_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    failed_password_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    password_locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================
# TELEGRAM ACCOUNT
# ============================================================

class TelegramAccount(Base):
    __tablename__ = "telegram_accounts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
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

    session_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    session_data: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="disconnected",
        nullable=False,
    )

    auto_reply_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_connected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================
# AUTO REPLY
# ============================================================

class AutoReply(Base):
    __tablename__ = "auto_replies"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    telegram_account_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("telegram_accounts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    message_type: Mapped[str] = mapped_column(
        String(50),
        default="text",
        nullable=False,
    )

    message_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    file_id: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    link: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Nano-Bot Storage kanalidagi post reference.
    # Auto Reply 2.0: media Bot API file_id emas,
    # shu ustunlar orqali Storage Channel'dan olinadi.
    storage_chat_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    storage_message_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # ACTIVE | NEEDS_RESAVE
    #
    # Storage Channel o'chirilgan/topilmasa va shu Auto Reply'ning
    # source posti yangi kanalga hali qayta saqlanmagan bo'lsa
    # NEEDS_RESAVE bo'ladi — record o'chirilmaydi, faqat userga
    # "postni qayta yuboring" degan holat ko'rsatiladi. Post
    # muvaffaqiyatli qayta saqlansa (tahrirlash orqali) yana
    # ACTIVE'ga qaytadi.
    source_status: Mapped[str] = mapped_column(
        String(20),
        default="ACTIVE",
        server_default="ACTIVE",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================
# AUTO REPLY KEYWORD
# ============================================================

class AutoReplyKeyword(Base):
    __tablename__ = "auto_reply_keywords"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    auto_reply_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("auto_replies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    keyword: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# ============================================================
# FIRST MESSAGE
# ============================================================

class FirstMessage(Base):
    __tablename__ = "first_messages"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    message_type: Mapped[str] = mapped_column(
        String(50),
        default="text",
        nullable=False,
    )

    text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    file_id: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    link: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Nano-Bot Storage kanalidagi post reference.
    # First Message 2.0: media Bot API file_id emas,
    # shu ustunlar orqali Storage Channel'dan olinadi.
    storage_chat_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    storage_message_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # ACTIVE | NEEDS_RESAVE — qarang: AutoReply.source_status
    # izohi (bir xil qoida).
    source_status: Mapped[str] = mapped_column(
        String(20),
        default="ACTIVE",
        server_default="ACTIVE",
        nullable=False,
    )

    # Bir xil kontaktga First Message qayta yuborilishi
    # uchun kutiladigan interval (soniyalarda).
    # 3600 = har 1 soatdan keyin, 86400 = har 1 kundan keyin.
    repeat_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        default=3600,
        server_default="3600",
        nullable=False,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================
# FIRST MESSAGE CONTACT
# ============================================================
#
# Foydalanuvchining shaxsiy Telegram akkauntiga birinchi marta
# (yoki interval o'tgandan keyin qayta) yozgan kontaktlarni
# kuzatish uchun. Chat content saqlanmaydi — faqat texnik
# vaqt belgilari.

class FirstMessageContact(Base):
    __tablename__ = "first_message_contacts"

    __table_args__ = (
        UniqueConstraint(
            "telegram_account_id",
            "peer_id",
            name="uq_first_message_contacts_account_peer",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    telegram_account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("telegram_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    peer_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    last_incoming_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_first_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================
# TELEGRAM STORAGE CHANNEL
# ============================================================
#
# Har bir ulangan Telegram akkaunt uchun shu akkaunt nomidan
# yaratilgan shaxsiy "Nano-Bot Storage" kanali. Auto Reply va
# First Message postlari shu kanalda saqlanadi — DB'da media
# faylning o'zi saqlanmaydi, faqat message reference.

class TelegramStorageChannel(Base):
    __tablename__ = "telegram_storage_channels"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    telegram_account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("telegram_accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================
# TERMS ACCEPTANCE
# ============================================================
#
# Telegram akkaunt ulashdan oldin foydalanuvchi rozilik
# bildirgan shartnoma versiyasini qayd etadi.

class TermsAcceptance(Base):
    __tablename__ = "terms_acceptances"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "terms_version",
            name="uq_terms_acceptances_user_version",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    terms_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# ============================================================
# SECURITY EVENT
# ============================================================
#
# Xavfsizlik hodisalarining audit yozuvi. Hech qachon maxfiy
# qiymat (token/parol/session) saqlanmaydi — faqat
# "safe_description" va sanitized metadata.

class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    safe_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    telegram_account_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("telegram_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    metadata_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


# ============================================================
# BOT SETTINGS
# ============================================================
#
# Yagona (singleton, id=1) qator — Admin Panel orqali
# boshqariladigan runtime sozlamalar (masalan maintenance mode).

class BotSettings(Base):
    __tablename__ = "bot_settings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    maintenance_mode: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    maintenance_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================
# REFERRAL
# ============================================================

class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    referred_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    referral_code: Mapped[str] = mapped_column(
        String(100),
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
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# ============================================================
# STATISTICS
# ============================================================

class Statistics(Base):
    __tablename__ = "statistics"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    replied_people: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    auto_replies: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    first_messages_sent: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================
# STATISTICS EVENT
# ============================================================
#
# `Statistics` jadvali faqat KUMULYATIV hisoblagichlarni
# saqlaydi (jami son) — undan "bugun/7 kun/30 kun" kabi vaqt
# oralig'idagi sonlarni hisoblab bo'lmaydi. Shu sababli, FAQAT
# shu aniq ehtiyoj uchun, juda minimal (vaqt belgisi + tur)
# yozuv jadvali qo'shildi. Xabar mazmuni SAQLANMAYDI — faqat
# "auto_reply" yoki "first_message" yuborilgani va qachon.

class StatisticsEvent(Base):
    __tablename__ = "statistics_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


# ============================================================
# SUBSCRIPTION
# ============================================================

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="free",
        nullable=False,
    )

    trial_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    trial_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # MUHIM (Faollik/Monetizatsiya arxitekturasi): "Premium"
    # tushunchasi olib tashlandi, endi "Faollik" (Activity)
    # ishlatiladi. `premium_started_at`/`premium_expires_at`
    # ustunlari ESKI arxitekturadan qoladi (mavjud ma'lumotni
    # buzmaslik uchun o'chirilmaydi/nomlanmaydi), lekin endi
    # kodning hech bir joyida ishlatilmaydi — ular deprecated.
    # Yangi, faol maydon — `activity_expires_at`.
    premium_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    premium_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Faollik (pullik paket) qachongacha amal qilishi. NULL —
    # foydalanuvchi hech qachon Faollik sotib olmagan (faqat
    # trial bo'lishi mumkin).
    activity_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================
# PAYMENT (Faollik to'lovlari — admin qo'lda tasdiqlaydi)
# ============================================================

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Qulaylik uchun users.telegram_id'ning nusxasi — admin
    # panel/payment channel kartalarida qo'shimcha JOIN'siz
    # ko'rsatish uchun.
    telegram_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )

    # ESKI (legacy) maydonlar — mavjud yozuvlarni buzmaslik
    # uchun saqlanadi. Yangi Faollik to'lovlari uchun
    # `usd_amount`/`uzs_amount` ishlatiladi.
    amount: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="USD",
        nullable=False,
    )

    # PENDING | APPROVED | REJECTED | CANCELLED
    status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
        index=True,
    )

    # Har bir to'lov uchun unique, tashqi ko'rinadigan ID
    # (masalan UUID4 hex) — admin panel/payment channel
    # kartalarida ko'rsatiladi.
    payment_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )

    # Faollik paketi kaliti: "1m" | "3m" | "6m" | "1y".
    package: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    duration_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    usd_amount: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    uzs_amount: Mapped[Optional[float]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
    )

    # To'lov so'rovi yaratilgan paytdagi USD->UZS kursi
    # (informatsion, audit uchun saqlanadi).
    exchange_rate: Mapped[Optional[float]] = mapped_column(
        Numeric(18, 6),
        nullable=True,
    )

    # Foydalanuvchi yuborgan chek/skrinshotning Bot API file_id'si
    # (faqat botning o'z to'lovlar kanaliga qayta yuborish uchun —
    # bu yerda Telethon/Storage Channel arxitekturasi TATBIQ
    # ETILMAYDI, chunki bu shaxsiy Auto Reply/First Message media
    # emas, balki bot o'zi administratori bo'lgan to'lovlar
    # kanaliga oddiy Bot API xabar).
    receipt_file_id: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    receipt_file_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    # To'lovlar kanalidagi so'rov kartasining message_id'si —
    # tasdiqlash/rad etishda shu xabarni tahrirlash uchun.
    admin_channel_message_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    rejected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Tasdiqlagan/rad etgan adminning Telegram ID'si.
    approved_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


# ============================================================
# EXCHANGE RATE CACHE
# ============================================================
#
# USD -> UZS kursi uchun yagona (singleton, id=1) qator.
# Har bir user request'da tashqi API'ga murojaat qilinmasligi
# uchun kurs shu yerda kesh qilinadi (+ jarayon xotirasida ham).

class ExchangeRateCache(Base):
    __tablename__ = "exchange_rate_cache"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    rate: Mapped[float] = mapped_column(
        Numeric(18, 6),
        nullable=False,
    )

    source: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================
# ADMIN STATISTICS
# ============================================================

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
        Numeric(12, 2),
        default=0,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================
# UNANSWERED CHATS
# ============================================================
#
# "Javob berilmagan chatlar" monitoringi — bu CONVERSATION
# CONTENT saqlash tizimi EMAS. Faqat texnik metadata saqlanadi:
# peer ID, vaqt belgilari, holat. Xabar matni/tarixi hech qachon
# bu jadvalga (yoki boshqa hech qayerga) yozilmaydi.

class UnansweredChat(Base):
    __tablename__ = "unanswered_chats"

    __table_args__ = (
        # Bir peer uchun bir vaqtning o'zida faqat BITTA faol
        # (UNANSWERED) yozuv bo'lishi mumkin — DB darajasidagi
        # himoya (ilova darajasidagi "avval tekshir, keyin
        # yarat" logikasidan tashqari, race condition'lardan
        # ham himoya qiladi). ANSWERED holatidagi eski yozuvlar
        # bu cheklovga kirmaydi — bitta peer uchun tarixda
        # bir nechta ANSWERED sikli bo'lishi mumkin.
        Index(
            "uq_unanswered_chats_active_peer",
            "telegram_account_id",
            "peer_id",
            unique=True,
            postgresql_where=text("status = 'UNANSWERED'"),
        ),
        Index(
            "ix_unanswered_chats_account_status",
            "telegram_account_id",
            "status",
        ),
        # MUHIM: `waiting_since` uchun alohida Index(...) shart
        # emas — quyida ustun darajasida `index=True` orqali
        # aynan shu nom bilan avtomatik yaratiladi. Ikkalasini
        # ham qo'shish "relation already exists" xatosiga olib
        # keladi.
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    telegram_account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("telegram_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    peer_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    peer_type: Mapped[str] = mapped_column(
        String(20),
        default="user",
        server_default="user",
        nullable=False,
    )

    # MUHIM (Privacy): faqat ko'rsatish (display) uchun ism/
    # username — conversation content EMAS.
    peer_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    peer_username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Joriy javobsizlik "sikli" boshlangan birinchi outgoing
    # xabar vaqti.
    first_bot_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Saralash uchun ishlatiladigan maydon — joriy sikl uchun
    # doim `first_bot_message_at`ga teng (bot keyingi xabar
    # yuborsa ham qayta boshlanmaydi, spec 7-bo'lim qoidasi).
    waiting_since: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Shu peer'ga yuborilgan ENG OXIRGI outgoing xabar vaqti
    # (bot bir necha marta yozgan bo'lishi mumkin).
    last_bot_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    user_replied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # UNANSWERED | ANSWERED
    status: Mapped[str] = mapped_column(
        String(20),
        default="UNANSWERED",
        server_default="UNANSWERED",
        nullable=False,
        index=True,
    )

    reminder_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )