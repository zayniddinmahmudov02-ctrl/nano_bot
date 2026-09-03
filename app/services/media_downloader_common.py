from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================
# Nano-Yordamchi (YouTube-Save / Insta-Save) uchun umumiy,
# provider-agnostik cheklovlar va yordamchi funksiyalar.
#
# MUHIM:
# - Video binary hech qachon PostgreSQL'ga yozilmaydi — faqat
#   diskda vaqtincha saqlanadi va Telegramga yuborilgandan
#   keyin O'CHIRILADI.
# - Download URL/token hech qachon logga yozilmaydi.
# ============================================================

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # ~50 MB (Bot API limiti)
MAX_CONCURRENT_DOWNLOADS = 2
DOWNLOAD_TIMEOUT_SECONDS = 180
SLOT_WAIT_TIMEOUT_SECONDS = 0.2

_download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)


class DownloadBusyError(Exception):
    """Barcha yuklab olish 'joylari' band bo'lganda ko'tariladi."""


@dataclass
class DownloadResult:
    ok: bool
    file_path: Optional[str] = None
    title: Optional[str] = None
    error_code: Optional[str] = None
    # error_code: "invalid_url" | "private" | "too_large" |
    #             "timeout" | "busy" | "failed"


@contextlib.asynccontextmanager
async def download_slot():
    """
    Bir vaqtning o'zida ishlaydigan yuklab olishlar sonini
    cheklaydi (concurrency limit). Agar barcha joylar band
    bo'lsa, kutmasdan DownloadBusyError ko'taradi — foydalanuvchi
    darhol xabardor qilinadi.
    """

    try:
        await asyncio.wait_for(
            _download_semaphore.acquire(),
            timeout=SLOT_WAIT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise DownloadBusyError()

    try:
        yield
    finally:
        _download_semaphore.release()


def get_temp_download_dir() -> Path:
    base = Path(tempfile.gettempdir()) / "nano_bot_downloads"
    base.mkdir(parents=True, exist_ok=True)
    return base


def make_temp_output_template(extension: str = "mp4") -> Path:
    """
    Har bir yuklab olish uchun noyob, taxmin qilib
    bo'lmaydigan vaqtinchalik fayl nomi.
    """

    directory = get_temp_download_dir()
    filename = f"{uuid.uuid4().hex}.{extension}"

    return directory / filename


def cleanup_file(file_path: Optional[str]) -> None:
    """
    Vaqtinchalik faylni xavfsiz o'chiradi. Fayl mavjud
    bo'lmasa yoki xatolik yuz bersa ham dastur yiqilmaydi.
    """

    if not file_path:
        return

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        logger.exception(
            "Vaqtinchalik faylni o'chirishda xatolik."
        )


__all__ = [
    "MAX_FILE_SIZE_BYTES",
    "MAX_CONCURRENT_DOWNLOADS",
    "DOWNLOAD_TIMEOUT_SECONDS",
    "DownloadBusyError",
    "DownloadResult",
    "download_slot",
    "get_temp_download_dir",
    "make_temp_output_template",
    "cleanup_file",
]
