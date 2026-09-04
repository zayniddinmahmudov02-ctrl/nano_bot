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
        # STATISTICS — orphaned/legacy NOT NULL ustunlar
        # ------------------------------------------------------
        # MUHIM: serverdagi haqiqiy `statistics` jadvalida ORM
        # modeli BILMAYDIGAN, eski/orphaned ustunlar mavjud
        # ekanligi amalda tasdiqlandi — avval `people_replied`
        # (endi kodda `replied_people`), keyin `total_auto_replies`
        # (endi kodda `auto_replies`). Bular avvalgi schema
        # versiyasidan qolgan, NOT NULL, DEFAULT'siz ustunlar —
        # ORM ularga hech qachon yozmagani uchun har bir yangi
        # INSERT
        #   NotNullViolationError: null value in column "..."
        # xatosi bilan yiqilardi.
        #
        # Bunday nomma-nom ustunlarni birma-bir "kashf qilib"
        # tuzatish o'rniga (keyingi xato boshqa nom bilan qayta
        # chiqmasligi uchun), quyidagi DO $$ bloki `statistics`
        # jadvalidagi BARCHA NOT NULL, DEFAULT'siz, butun sonli
        # (integer/bigint/smallint/numeric) ustunlarni DINAMIK
        # ravishda topadi va har biriga xavfsiz DEFAULT 0
        # beradi — ORM ularni INSERT ro'yxatiga qo'shmasa ham,
        # Postgres avtomatik 0 bilan to'ldiradi.
        #
        # MAVJUD QATORLAR VA ULARNING QIYMATLARI BUTUNLAY
        # BUZILMAYDI — faqat DEFAULT o'rnatiladi, hech qanday
        # DROP/RENAME/UPDATE yo'q. Bunday ustun umuman bo'lmasa
        # (masalan yangi/toza DB) — sikl shunchaki bo'sh aylanadi,
        # xato chiqmaydi.
        """
        DO $$
        DECLARE
            col RECORD;
        BEGIN
            FOR col IN
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'statistics'
                  AND is_nullable = 'NO'
                  AND column_default IS NULL
                  AND data_type IN (
                      'integer', 'bigint', 'smallint', 'numeric'
                  )
                  AND column_name <> 'id'
            LOOP
                EXECUTE format(
                    'ALTER TABLE statistics ALTER COLUMN %I '
                    'SET DEFAULT 0',
                    col.column_name
                );
            END LOOP;
        END $$;
        """,
        # `statistics.user_id` — bitta user uchun ikkita qator
        # yaratilmasligi DB darajasida kafolatlansin (ilova
        # darajasidagi "avval tekshir, keyin yarat" logikasi
        # yagona himoya bo'lib qolmasligi uchun). Modelda
        # `unique=True` bor, lekin serverdagi haqiqiy jadval shu
        # cheklovsiz yaratilgan bo'lishi mumkin.
        #
        # MUHIM: agar (bugungi kungacha noma'lum sabablarga ko'ra)
        # jadvalda ALLAQACHON duplicate `user_id` qatorlari mavjud
        # bo'lsa, oddiy `CREATE UNIQUE INDEX` xato berib, BUTUN
        # migratsiya tranzaksiyasini (bitta umumiy `engine.begin()`
        # ichida) orqaga qaytarib yuborardi — shu sabab bu aniq
        # statement o'zining EXCEPTION bloki bilan izolyatsiya
        # qilingan: muvaffaqiyatsiz bo'lsa faqat NOTICE yozadi va
        # qolgan barcha migratsiyalar baribir davom etadi.
        """
        DO $$
        BEGIN
            BEGIN
                CREATE UNIQUE INDEX IF NOT EXISTS
                    ix_statistics_user_id_unique
                    ON statistics (user_id);
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE
                    'statistics.user_id unique index skipped: %',
                    SQLERRM;
            END;
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