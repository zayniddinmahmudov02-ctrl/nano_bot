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
#
# MUHIM:
# .env faylida ADMIN_IDS (ko'plik, vergul bilan ajratilgan)
# ishlatiladi. Eski ADMIN_ID (birlik) ham backward-compatible
# tarzda qo'llab-quvvatlanadi — agar u ham berilgan bo'lsa,
# ro'yxatga qo'shiladi.

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

ADMIN_IDS_RAW = get_env(
    "ADMIN_IDS"
)


def _parse_admin_ids(
    raw: str,
    legacy_single: int,
) -> tuple:
    ids = set()

    if legacy_single:
        ids.add(legacy_single)

    for part in raw.split(","):
        part = part.strip()

        if not part:
            continue

        try:
            ids.add(int(part))
        except ValueError:
            continue

    return tuple(sorted(ids))


ADMIN_IDS = _parse_admin_ids(
    ADMIN_IDS_RAW,
    ADMIN_ID,
)


def is_admin(telegram_id) -> bool:
    """
    Berilgan Telegram ID admin ro'yxatida bormi tekshiradi.
    """

    try:
        telegram_id = int(telegram_id)
    except (TypeError, ValueError):
        return False

    return telegram_id in ADMIN_IDS


# =========================================================
# BOT CONTROL (ixtiyoriy — faqat Linux/systemd serverida)
# =========================================================
#
# Admin panelning Stop/Restart/Start funksiyasi FAQAT shu
# bitta, aniq nano_bot xizmat nomini boshqaradi — hech qanday
# boshqa server xizmatiga tegilmaydi. Standart qiymat
# "nano_bot.service" — agar serverda bunday systemd xizmati
# mavjud bo'lmasa (masalan lokal Windows dev muhitida),
# buyruq xavfsiz tarzda xatolik bilan yakunlanadi va admin'ga
# aniq xabar beriladi, bot yiqilmaydi.
#
# Boshqa unit nomi kerak bo'lsa yoki funksiya butunlay
# o'chirilishi kerak bo'lsa, .env'da NANO_BOT_SYSTEMD_SERVICE
# ni mos ravishda o'zgartiring yoki bo'shatib qo'ying.

NANO_BOT_SYSTEMD_SERVICE = get_env(
    "NANO_BOT_SYSTEMD_SERVICE",
    "nano_bot.service",
)


# =========================================================
# FAOLLIK / MONETIZATSIYA (Premium o'rnini bosuvchi tizim)
# =========================================================
#
# MUHIM: PREMIUM_PRICE/PREMIUM_CURRENCY ESKI, endi ishlatilmaydigan
# sozlamalar edi — Faollik paketlari narxi endi
# `app/services/payment_service.py`dagi ACTIVITY_PACKAGES
# lug'atida qattiq belgilangan (spec talabiga ko'ra: 1 oy $1,
# 3 oy $2.50, 6 oy $4, 1 yil $6).

TRIAL_DURATION_DAYS = 7

# To'lov (chek/skrinshot) so'rovlari yuboriladigan Telegram
# kanali. .env orqali sozlanishi mumkin — sozlanmagan bo'lsa,
# vazifada berilgan standart kanal ID ishlatiladi. MUHIM:
# real `.env` fayli bu o'zgaruvchi bilan qayta yozilmaydi —
# faqat `.env.example`ga placeholder qo'shildi.
PAYMENT_CHANNEL_ID_RAW = get_env(
    "PAYMENT_CHANNEL_ID",
    "-1004392136813",
)

try:
    PAYMENT_CHANNEL_ID = int(PAYMENT_CHANNEL_ID_RAW)
except ValueError:
    PAYMENT_CHANNEL_ID = 0

# To'lov qabul qilinadigan karta — MUHIM: bitta joydan
# boshqariladi (config), kod ichida hech qayerda hardcode
# qilinmaydi. .env orqali sozlanishi mumkin (ixtiyoriy),
# sozlanmasa quyidagi standart qiymat ishlatiladi.
PAYMENT_CARD_NUMBER = get_env(
    "PAYMENT_CARD_NUMBER",
    "9860350144907192",
)

PAYMENT_CARD_TYPE = get_env(
    "PAYMENT_CARD_TYPE",
    "Uz-Humo",
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


# =========================================================
# NANO-YORDAMCHI / MEDIA DOWNLOAD (Instagram Save / YouTube Save)
# =========================================================
#
# MUHIM: bu limitlar Instagram Save VA YouTube Save uchun UMUMIY,
# markazlashtirilgan yuklab olish mexanizmini boshqaradi
# (app/services/media_downloader_common.py — bitta semaphore,
# ikkala platforma uchun ham serverning umumiy yukini nazorat
# qiladi). .env orqali sozlanishi mumkin; sozlanmasa xavfsiz
# standart qiymatlar ishlatiladi.

YOUTUBE_MAX_FILE_SIZE_MB_RAW = get_env(
    "YOUTUBE_MAX_FILE_SIZE_MB",
    "50",
)

try:
    YOUTUBE_MAX_FILE_SIZE_MB = int(YOUTUBE_MAX_FILE_SIZE_MB_RAW)
except ValueError:
    YOUTUBE_MAX_FILE_SIZE_MB = 50

MAX_CONCURRENT_YOUTUBE_DOWNLOADS_RAW = get_env(
    "MAX_CONCURRENT_YOUTUBE_DOWNLOADS",
    "2",
)

try:
    MAX_CONCURRENT_YOUTUBE_DOWNLOADS = int(
        MAX_CONCURRENT_YOUTUBE_DOWNLOADS_RAW
    )
except ValueError:
    MAX_CONCURRENT_YOUTUBE_DOWNLOADS = 2

# MUHIM (root cause — "serverda sozlanmagan" xatosi): ffmpeg
# ba'zan PATH orqali topilmaydi — masalan systemd xizmati
# interaktiv shell'dan FARQLI, minimal PATH muhitida ishlaydi.
# Bo'sh qoldirilsa, avtomatik aniqlash (PATH + odatiy o'rnatish
# joylari) ishlatiladi; kerak bo'lsa, aniq absolyut yo'lni shu
# yerda ko'rsating (masalan "/usr/bin/ffmpeg").
FFMPEG_PATH = get_env("FFMPEG_PATH", "")