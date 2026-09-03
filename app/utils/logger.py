from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional

LOG_DIR = Path("logs")
LOG_FILE_PATH = LOG_DIR / "nano_bot.log"

LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

_REDACTED = "[REDACTED]"

# ============================================================
# PATTERN BASED REDACTION
# ============================================================
#
# Aniq token/parol/session qiymati ma'lum bo'lmagan hollarda ham
# (masalan kelajakdagi kod satrlari) umumiy naqshlar orqali
# maxfiy ma'lumotlarni logdan yashiradi.

_PATTERN_RULES = (
    # Telegram bot token shakli: 123456789:ABC-defGhIjk...
    (
        re.compile(r"\b\d{6,10}:[A-Za-z0-9_-]{30,}\b"),
        "[BOT_TOKEN]",
    ),
    # key=value yoki key: value ko'rinishidagi maxfiy maydonlar.
    #
    # MUHIM: identifikator qismi "_" bilan ham yozilishi mumkin
    # (masalan BOT_TOKEN, session_string, API_HASH) — "_" so'z
    # belgisi hisoblanadi va \b uni bo'lib bermaydi. Shu sababli
    # kalit so'z identifikatorning istalgan joyida (boshida,
    # oxirida yoki o'rtasida) qidiriladi, faqat butun
    # identifikator \b bilan chegaralanadi.
    (
        re.compile(
            r"(?i)\b([a-z0-9_]*"
            r"(?:password|parol|otp|2fa|token|session|hash|"
            r"secret|authorization)"
            r"[a-z0-9_]*)"
            r"(\s*[:=]\s*)"
            r"[^\s,;\"']+"
        ),
        r"\1\2" + _REDACTED,
    ),
)


def _extract_db_password(database_url: Optional[str]) -> Optional[str]:
    if not database_url:
        return None

    match = re.search(
        r"://[^:@/]+:([^@/]+)@",
        database_url,
    )

    if not match:
        return None

    return match.group(1)


def _collect_known_secrets() -> List[str]:
    """
    Config'dagi haqiqiy maxfiy qiymatlarni yig'adi — ular
    logda uchrasa, kontekstidan qat'i nazar maskalanadi.
    """

    try:
        from app import config
    except Exception:
        return []

    candidates = [
        getattr(config, "BOT_TOKEN", None),
        getattr(config, "TELEGRAM_API_HASH", None),
        getattr(config, "TELEGRAM_API_ID", None),
        _extract_db_password(
            getattr(config, "DATABASE_URL", None)
        ),
    ]

    return [
        value
        for value in candidates
        if value and len(str(value)) >= 4
    ]


def redact_secrets(text: Optional[str]) -> Optional[str]:
    """
    Berilgan matndan ma'lum bo'lgan maxfiy qiymatlarni va
    shubhali naqshlarni (token/parol/session shakllari) yashiradi.
    """

    if not text:
        return text

    redacted = text

    for secret in _collect_known_secrets():
        secret_str = str(secret)

        if secret_str and secret_str in redacted:
            redacted = redacted.replace(
                secret_str,
                _REDACTED,
            )

    for pattern, replacement in _PATTERN_RULES:
        redacted = pattern.sub(replacement, redacted)

    return redacted


class SecretRedactingFormatter(logging.Formatter):
    """
    Standart Formatter, lekin yakuniy formatlangan qatorni
    (xabar + traceback) yuborishdan oldin maxfiy ma'lumotlardan
    tozalaydi.
    """

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return redact_secrets(formatted) or formatted


def configure_logging(level: int = logging.INFO) -> None:
    """
    Root loggerni sozlaydi:
    - stdout'ga sanitized (maxfiy ma'lumotsiz) log chiqaradi
    - logs/nano_bot.log fayliga aylanma (rotating) yozadi

    Ikkalasi ham SecretRedactingFormatter orqali ishlaydi —
    BOT_TOKEN, API_HASH, DB parol, OTP, 2FA, session kabi
    qiymatlar hech qachon logga tushmaydi.
    """

    formatter = SecretRedactingFormatter(LOG_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)

    # Takroriy chaqiruvlarda handlerlarni ikki marta qo'shmaslik.
    root.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            LOG_FILE_PATH,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    except OSError:
        # Fayl tizimiga yozib bo'lmasa ham, stdout logging
        # ishlashda davom etadi.
        root.warning(
            "Log faylini yozib bo'lmadi: %s",
            LOG_FILE_PATH,
        )


def read_recent_log_lines(max_chars: int = 3500) -> str:
    """
    Faqat Nano-Bot'ning o'z log faylidan (LOG_FILE_PATH) oxirgi
    qatorlarni o'qiydi. Boshqa loyihalarning log fayllariga
    tegilmaydi.

    Fayl yozilayotganda ham allaqachon sanitized bo'lgani uchun,
    qo'shimcha ehtiyot chorasi sifatida yana bir bor
    redact_secrets() orqali o'tkaziladi.
    """

    if not LOG_FILE_PATH.exists():
        return "ℹ️ Hozircha log fayli mavjud emas."

    try:
        with open(
            LOG_FILE_PATH,
            "r",
            encoding="utf-8",
            errors="replace",
        ) as log_file:
            content = log_file.read()

    except OSError:
        return "❌ Log faylini o'qib bo'lmadi."

    if not content:
        return "ℹ️ Log fayli bo'sh."

    if len(content) > max_chars:
        content = content[-max_chars:]
        content = "...(yuqorisi qisqartirildi)...\n" + content

    return redact_secrets(content) or content


__all__ = [
    "LOG_FILE_PATH",
    "configure_logging",
    "redact_secrets",
    "read_recent_log_lines",
    "SecretRedactingFormatter",
]
