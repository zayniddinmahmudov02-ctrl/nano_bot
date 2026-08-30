from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
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

    profile = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    onboarding = relationship(
        "OnboardingAnswer",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    telegram_accounts = relationship(
        "TelegramAccount",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    keywords = relationship(
        "Keyword",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    flows = relationship(
        "ResponseFlow",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    contacts = relationship(
        "Contact",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    conversations = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    subscription = relationship(
        "Subscription",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


# ============================================================
# USER PROFILE
# ============================================================

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    age: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    profession: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    activity: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    audience: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    contact_reasons: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    important_information: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    communication_style: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    allowed_topics: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    forbidden_topics: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    user = relationship(
        "User",
        back_populates="profile",
    )


# ============================================================
# ONBOARDING
# ============================================================

class OnboardingAnswer(Base):
    __tablename__ = "onboarding_answers"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    current_question: Mapped[int] = mapped_column(
        Integer,
        default=1,
    )

    completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    user = relationship(
        "User",
        back_populates="onboarding",
    )


# ============================================================
# CONNECTED TELEGRAM ACCOUNT
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

    conversations = relationship(
        "Conversation",
        back_populates="telegram_account",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "telegram_id",
            name="uq_user_telegram_account",
        ),
    )


# ============================================================
# CONTACT
# ============================================================

class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    user = relationship(
        "User",
        back_populates="contacts",
    )

    conversations = relationship(
        "Conversation",
        back_populates="contact",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "telegram_id",
            name="uq_user_contact",
        ),
    )


# ============================================================
# CONVERSATION
# ============================================================

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    telegram_account_id: Mapped[int] = mapped_column(
        ForeignKey(
            "telegram_accounts.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    contact_id: Mapped[int] = mapped_column(
        ForeignKey(
            "contacts.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="active",
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    last_message_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        index=True,
    )

    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    user = relationship(
        "User",
        back_populates="conversations",
    )

    telegram_account = relationship(
        "TelegramAccount",
        back_populates="conversations",
    )

    contact = relationship(
        "Contact",
        back_populates="conversations",
    )

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


# ============================================================
# MESSAGE
# ============================================================

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    telegram_message_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
    )

    direction: Mapped[str] = mapped_column(
        String(20),
    )

    sender_type: Mapped[str] = mapped_column(
        String(30),
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

    matched_keyword: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    response_step_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(
            "response_steps.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    delivery_status: Mapped[str] = mapped_column(
        String(30),
        default="received",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        index=True,
    )

    conversation = relationship(
        "Conversation",
        back_populates="messages",
    )

    response_step = relationship(
        "ResponseStep",
        foreign_keys=[response_step_id],
    )


# ============================================================
# KEYWORD
# ============================================================

class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
    )

    keyword: Mapped[str] = mapped_column(
        String(255),
        index=True,
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        index=True,
    )

    matching_mode: Mapped[str] = mapped_column(
        String(30),
        default="word",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    usage_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    flow_id: Mapped[int] = mapped_column(
        ForeignKey(
            "response_flows.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    user = relationship(
        "User",
        back_populates="keywords",
    )

    flow = relationship(
        "ResponseFlow",
        back_populates="keywords",
    )

    aliases = relationship(
        "KeywordAlias",
        back_populates="keyword",
        cascade="all, delete-orphan",
    )


# ============================================================
# KEYWORD ALIAS
# ============================================================

class KeywordAlias(Base):
    __tablename__ = "keyword_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)

    keyword_id: Mapped[int] = mapped_column(
        ForeignKey(
            "keywords.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    value: Mapped[str] = mapped_column(
        String(255),
        index=True,
    )

    keyword = relationship(
        "Keyword",
        back_populates="aliases",
    )


# ============================================================
# RESPONSE FLOW
# ============================================================

class ResponseFlow(Base):
    __tablename__ = "response_flows"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    user = relationship(
        "User",
        back_populates="flows",
    )

    keywords = relationship(
        "Keyword",
        back_populates="flow",
    )

    steps = relationship(
        "ResponseStep",
        back_populates="flow",
        cascade="all, delete-orphan",
        order_by="ResponseStep.order",
    )


# ============================================================
# RESPONSE STEP
# ============================================================

class ResponseStep(Base):
    __tablename__ = "response_steps"

    id: Mapped[int] = mapped_column(primary_key=True)

    flow_id: Mapped[int] = mapped_column(
        ForeignKey(
            "response_flows.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    order: Mapped[int] = mapped_column(
        Integer,
    )

    type: Mapped[str] = mapped_column(
        String(30),
    )

    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    media_id: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    delay_seconds: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    flow = relationship(
        "ResponseFlow",
        back_populates="steps",
    )

    buttons = relationship(
        "ResponseButton",
        back_populates="step",
        cascade="all, delete-orphan",
    )


# ============================================================
# RESPONSE BUTTON
# ============================================================

class ResponseButton(Base):
    __tablename__ = "response_buttons"

    id: Mapped[int] = mapped_column(primary_key=True)

    step_id: Mapped[int] = mapped_column(
        ForeignKey(
            "response_steps.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    text: Mapped[str] = mapped_column(
        String(255),
    )

    action_type: Mapped[str] = mapped_column(
        String(30),
    )

    action_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    row: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    step = relationship(
        "ResponseStep",
        back_populates="buttons",
    )


# ============================================================
# MEDIA
# ============================================================

class MediaFile(Base):
    __tablename__ = "media_files"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    file_id: Mapped[str] = mapped_column(
        String(500),
    )

    file_type: Mapped[str] = mapped_column(
        String(30),
    )

    file_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    mime_type: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    file_size: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
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
        default="trial",
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
        back_populates="subscription",
    )


# ============================================================
# AUDIT LOG
# ============================================================

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
    )

    details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        index=True,
    )