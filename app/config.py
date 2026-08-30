import os

from dotenv import load_dotenv

load_dotenv()


def get_env(
    name: str,
    default: str = "",
) -> str:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip()


# =========================================================
# NANO-BOT
# =========================================================

BOT_TOKEN = get_env("BOT_TOKEN")

BOT_USERNAME = get_env(
    "BOT_USERNAME",
    "nano_go_bot",
).lstrip("@")


# =========================================================
# POSTGRESQL
# =========================================================

DATABASE_URL = get_env(
    "DATABASE_URL"
)


# =========================================================
# TELEGRAM / TELETHON
# =========================================================

TELEGRAM_API_ID = get_env(
    "TELEGRAM_API_ID"
)

TELEGRAM_API_HASH = get_env(
    "TELEGRAM_API_HASH"
)

TELEGRAM_SESSION_DIR = get_env(
    "TELEGRAM_SESSION_DIR",
    "/opt/nano_bot/sessions",
)


# =========================================================
# ADMIN
# =========================================================

ADMIN_ID_RAW = get_env(
    "ADMIN_ID"
)

try:
    ADMIN_ID = (
        int(ADMIN_ID_RAW)
        if ADMIN_ID_RAW
        else 0
    )
except ValueError:
    ADMIN_ID = 0


# =========================================================
# PREMIUM
# =========================================================

PREMIUM_PRICE = get_env(
    "PREMIUM_PRICE",
    "1",
)

PREMIUM_CURRENCY = get_env(
    "PREMIUM_CURRENCY",
    "USD",
)


# =========================================================
# APPLICATION
# =========================================================

APP_ENV = get_env(
    "APP_ENV",
    "production",
)

LOG_LEVEL = get_env(
    "LOG_LEVEL",
    "INFO",
).upper()