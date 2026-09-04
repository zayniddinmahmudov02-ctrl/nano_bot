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
        # Faollik (Activity) tizimi — Premium o'rnini bosadi.
        # `trial_started_at`/`trial_expires_at` allaqachon mavjud;
        # faqat yangi `activity_expires_at` qo'shiladi. Eski
        # `premium_*` ustunlari o'chirilmaydi (deprecated holda
        # qoladi).
        "ALTER TABLE subscriptions "
        "ADD COLUMN IF NOT EXISTS activity_expires_at "
        "TIMESTAMPTZ",
        # Faollik to'lovlari (admin qo'lda tasdiqlaydi).
        "ALTER TABLE payments "
        "ADD COLUMN IF NOT EXISTS telegram_id BIGINT",
        "ALTER TABLE payments "
        "ADD COLUMN IF NOT EXISTS package VARCHAR(20)",
        "ALTER TABLE payments "
        "ADD COLUMN IF NOT EXISTS duration_days INTEGER",
        "ALTER TABLE payments "
        "ADD COLUMN IF NOT EXISTS usd_amount NUMERIC(12, 2)",
        "ALTER TABLE payments "
        "ADD COLUMN IF NOT EXISTS uzs_amount NUMERIC(18, 2)",
        "ALTER TABLE payments "
        "ADD COLUMN IF NOT EXISTS exchange_rate "
        "NUMERIC(18, 6)",
        "ALTER TABLE payments "
        "ADD COLUMN IF NOT EXISTS receipt_file_id TEXT",
        "ALTER TABLE payments "
        "ADD COLUMN IF NOT EXISTS receipt_file_type "
        "VARCHAR(20)",
        "ALTER TABLE payments "
        "ADD COLUMN IF NOT EXISTS admin_channel_message_id "
        "BIGINT",
        "ALTER TABLE payments "
        "ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ",
        "ALTER TABLE payments "
        "ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ",
        "ALTER TABLE payments "
        "ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ",
        "ALTER TABLE payments "
        "ADD COLUMN IF NOT EXISTS approved_by BIGINT",
        # Legacy default "pending" (lowercase) — yangi kod
        # "PENDING" (uppercase) yozadi, lekin ustun darajasidagi
        # DEFAULT o'zgartirilmaydi (mavjud qatorlarga ta'sir
        # qilmasligi uchun).
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "ix_payments_payment_id_unique ON payments (payment_id) "
        "WHERE payment_id IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS ix_payments_status "
        "ON payments (status)",
        "CREATE INDEX IF NOT EXISTS ix_payments_telegram_id "
        "ON payments (telegram_id)",
        # ------------------------------------------------------
        # STATISTICS — "people_replied" NOT NULL xatosi tuzatildi
        # ------------------------------------------------------
        # MUHIM: serverdagi haqiqiy `statistics` jadvalida ORM
        # modeli bilmaydigan, eski/orphaned `people_replied`
        # ustuni mavjud (NOT NULL, DEFAULT'siz) — bu joriy kod
        # hech qachon `people_replied`ga yozmaydi (butun loyihada
        # faqat `replied_people` ishlatiladi), shu sabab har bir
        # yangi INSERT
        #   NotNullViolationError: null value in column
        #   "people_replied" of relation "statistics"
        # xatosi bilan yiqilardi.
        #
        # Yechim: agar `people_replied` ustuni mavjud bo'lsa,
        # unga xavfsiz DEFAULT 0 beriladi — shunda uni INSERT
        # ro'yxatida ko'rsatmagan har qanday so'rov ham (jumladan
        # ORM'ning o'zi) avtomatik 0 bilan to'ldiriladi.
        # MAVJUD QATORLAR VA ULARNING QIYMATLARI BUTUNLAY
        # BUZILMAYDI — faqat DEFAULT o'rnatiladi, DROP/RENAME
        # yo'q. Ustun mavjud bo'lmasa (masalan yangi/toza DB) —
        # shartli tekshiruv tufayli hech narsa qilinmaydi, xato
        # chiqmaydi.
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'statistics'
                  AND column_name = 'people_replied'
            ) THEN
                ALTER TABLE statistics
                    ALTER COLUMN people_replied SET DEFAULT 0;
            END IF;
        END $$;
        """,
        # Modelning o'zi ishlatadigan ustunlar uchun ham
        # server-side DEFAULT — Python darajasidagi
        # `default=0`ga qo'shimcha himoya qatlami (ORM'dan
        # tashqari har qanday INSERT yo'li uchun ham xavfsiz).
        "ALTER TABLE statistics "
        "ADD COLUMN IF NOT EXISTS replied_people "
        "INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE statistics "
        "ADD COLUMN IF NOT EXISTS auto_replies "
        "INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE statistics "
        "ADD COLUMN IF NOT EXISTS first_messages_sent "
        "INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE statistics "
        "ALTER COLUMN replied_people SET DEFAULT 0",
        "ALTER TABLE statistics "
        "ALTER COLUMN auto_replies SET DEFAULT 0",
        "ALTER TABLE statistics "
        "ALTER COLUMN first_messages_sent SET DEFAULT 0",
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