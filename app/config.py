import os

from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

TELEGRAM_API_ID = os.getenv(
    "TELEGRAM_API_ID",
    "",
).strip()

TELEGRAM_API_HASH = os.getenv(
    "TELEGRAM_API_HASH",
    "",
).strip()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://nano_user:CHANGE_ME@localhost:5432/nano_bot",
).strip()

TRIAL_DAYS = int(
    os.getenv("TRIAL_DAYS", "7")
)

SUBSCRIPTION_PRICE_USD = float(
    os.getenv("SUBSCRIPTION_PRICE_USD", "1")
)

LOG_LEVEL = os.getenv(
    "LOG_LEVEL",
    "INFO",
).upper()

# Admin Telegram ID'lari.
# Masalan:
# ADMIN_IDS=123456789,987654321
ADMIN_IDS = {
    int(user_id.strip())
    for user_id in os.getenv(
        "ADMIN_IDS",
        "",
    ).split(",")
    if user_id.strip().isdigit()
}


def validate_bot_config() -> None:
    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN .env faylida belgilanmagan."
        )


def validate_telegram_config() -> None:
    if not TELEGRAM_API_ID:
        raise ValueError(
            "TELEGRAM_API_ID .env faylida belgilanmagan."
        )

    if not TELEGRAM_API_HASH:
        raise ValueError(
            "TELEGRAM_API_HASH .env faylida belgilanmagan."
        )


def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS