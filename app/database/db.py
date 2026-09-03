import logging
import os

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL .env faylida topilmadi."
    )


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def check_database() -> bool:
    """
    PostgreSQL ulanishini tekshiradi.
    """

    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT 1")
            )

        return True

    except Exception:
        logger.exception(
            "PostgreSQL ulanishida xatolik."
        )
        return False


async def create_tables() -> None:
    """
    Barcha SQLAlchemy jadvallarini yaratadi.

    Mavjud jadvallar o'chirilmaydi.
    """

    # Model importlari Base metadata'ga ro'yxatdan o'tishi uchun
    from app.database import models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )

    logger.info(
        "Database jadvallari tayyor."
    )


async def run_manual_migrations() -> None:
    """
    Mavjud jadvallarga yangi ustunlar qo'shadi.

    MUHIM:
    - Faqat ADD COLUMN IF NOT EXISTS ishlatiladi.
    - Hech qanday DROP yoki mavjud ma'lumotni o'zgartirish yo'q.
    - Idempotent: bir necha marta ishga tushirilsa ham xato bermaydi.
    """

    statements = [
        "ALTER TABLE auto_replies "
        "ADD COLUMN IF NOT EXISTS storage_chat_id BIGINT",
        "ALTER TABLE auto_replies "
        "ADD COLUMN IF NOT EXISTS storage_message_id INTEGER",
        "ALTER TABLE first_messages "
        "ADD COLUMN IF NOT EXISTS storage_chat_id BIGINT",
        "ALTER TABLE first_messages "
        "ADD COLUMN IF NOT EXISTS storage_message_id INTEGER",
        "ALTER TABLE first_messages "
        "ADD COLUMN IF NOT EXISTS repeat_interval_seconds "
        "INTEGER NOT NULL DEFAULT 3600",
        # Bot paroli / inactivity lock (21-bo'lim).
        # MUHIM: Telegram akkaunt paroli/2FA EMAS — faqat
        # Nano-Bot'ning o'ziga kirishni himoyalovchi qo'shimcha
        # parol. Faqat bcrypt hash saqlanadi.
        "ALTER TABLE user_settings "
        "ADD COLUMN IF NOT EXISTS password_hash TEXT",
        "ALTER TABLE user_settings "
        "ADD COLUMN IF NOT EXISTS password_enabled "
        "BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE user_settings "
        "ADD COLUMN IF NOT EXISTS last_activity_at "
        "TIMESTAMPTZ",
        "ALTER TABLE user_settings "
        "ADD COLUMN IF NOT EXISTS authenticated_until "
        "TIMESTAMPTZ",
        "ALTER TABLE user_settings "
        "ADD COLUMN IF NOT EXISTS failed_password_attempts "
        "INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE user_settings "
        "ADD COLUMN IF NOT EXISTS password_locked_until "
        "TIMESTAMPTZ",
    ]

    try:
        async with engine.begin() as connection:
            for statement in statements:
                await connection.execute(text(statement))

        logger.info(
            "Manual migratsiyalar muvaffaqiyatli bajarildi."
        )

    except Exception:
        logger.exception(
            "Manual migratsiyalarni bajarishda xatolik."
        )
        raise


async def close_database() -> None:
    """
    Database connection poolni yopadi.
    """

    await engine.dispose()

    logger.info(
        "PostgreSQL connection pool yopildi."
    )