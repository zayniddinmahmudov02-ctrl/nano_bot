from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from app.config import (
    MAX_CONCURRENT_YOUTUBE_DOWNLOADS,
    YOUTUBE_MAX_FILE_SIZE_MB,
)

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
# - Limitlar `.env` orqali sozlanadi (app/config.py:
#   YOUTUBE_MAX_FILE_SIZE_MB, MAX_CONCURRENT_YOUTUBE_DOWNLOADS) —
#   Instagram Save VA YouTube Save uchun UMUMIY (bitta semaphore,
#   serverning umumiy yukini nazorat qiladi).
# ============================================================

MAX_FILE_SIZE_BYTES = YOUTUBE_MAX_FILE_SIZE_MB * 1024 * 1024
MAX_CONCURRENT_DOWNLOADS = MAX_CONCURRENT_YOUTUBE_DOWNLOADS
DOWNLOAD_TIMEOUT_SECONDS = 180
SLOT_WAIT_TIMEOUT_SECONDS = 0.2

# Carousel/multi-media postlar uchun bitta so'rovda yuklab
# olinadigan MAKSIMAL element soni — cheksiz carousel serverni
# yuklab qo'ymasligi uchun.
MAX_CAROUSEL_ITEMS = 10

_download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)


class DownloadBusyError(Exception):
    """Barcha yuklab olish 'joylari' band bo'lganda ko'tariladi."""


# Media turini fayl kengaytmasidan aniqlash — Telegramga qaysi
# `send_*` metodi bilan yuborish kerakligini tanlash uchun
# ishlatiladi (spec 5-bo'lim).
_IMAGE_EXTENSIONS = {
    "jpg", "jpeg", "png", "webp", "bmp", "tiff", "heic",
}
_AUDIO_EXTENSIONS = {
    "mp3", "m4a", "aac", "opus", "ogg", "wav", "flac", "wma",
}
_VIDEO_EXTENSIONS = {
    "mp4", "mkv", "webm", "mov", "avi", "flv", "m4v", "3gp",
}


def classify_media_type(file_path: str) -> str:
    """
    Fayl kengaytmasi asosida Telegramga yuborish uchun media
    turini aniqlaydi: "photo" | "video" | "audio" | "document".

    Noma'lum/kutilmagan kengaytma uchun "document" qaytariladi —
    bu har doim xavfsiz fallback (spec 5-bo'lim).
    """

    extension = Path(file_path).suffix.lstrip(".").lower()

    if extension in _IMAGE_EXTENSIONS:
        return "photo"

    if extension in _AUDIO_EXTENSIONS:
        return "audio"

    if extension in _VIDEO_EXTENSIONS:
        return "video"

    return "document"


@dataclass
class DownloadResult:
    ok: bool
    file_path: Optional[str] = None
    title: Optional[str] = None
    media_type: Optional[str] = None
    # media_type: "photo" | "video" | "audio" | "document"

    # Carousel/multi-media post bo'lsa — birinchi elementdan
    # KEYINGI barcha elementlar shu yerda: (file_path, media_type,
    # title) uchligi sifatida. Oddiy (bitta media) natija uchun
    # bo'sh ro'yxat.
    extra_files: Optional[List[Tuple[str, str, Optional[str]]]] = None

    error_code: Optional[str] = None
    # error_code: one of app.services.download_errors' standard
    # codes (YT_DLP_UNAVAILABLE, INVALID_URL, BUSY, PRIVATE,
    # LOGIN_REQUIRED, AGE_RESTRICTED, VIDEO_UNAVAILABLE, NOT_FOUND,
    # GEO_RESTRICTED, RATE_LIMITED, TIMEOUT, NETWORK_ERROR,
    # FILE_TOO_LARGE, FFMPEG_ERROR, EXTRACTOR_ERROR, UNKNOWN).


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


def make_temp_output_template() -> Path:
    """
    Har bir yuklab olish uchun noyob, taxmin qilib bo'lmaydigan
    vaqtinchalik fayl nomi shabloni.

    MUHIM: haqiqiy kengaytma bu yerda QAT'IY belgilanmaydi —
    `%(ext)s` orqali yt-dlp'ning o'ziga topshiriladi, shunda
    saqlangan fayl haqiqiy kontent turiga (video/photo/audio)
    mos haqiqiy kengaytmaga ega bo'ladi (masalan Instagram photo
    posti ".mp4" deb NOTO'G'RI nomlanib qolmaydi).

    `%(autonumber)s` — carousel/multi-media post bir nechta
    elementga ega bo'lganda, har bir element o'zining ALOHIDA,
    bir-birini ustidan yozmaydigan fayliga ega bo'lishini
    kafolatlaydi.
    """

    directory = get_temp_download_dir()
    filename = f"{uuid.uuid4().hex}_%(autonumber)s.%(ext)s"

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
    "MAX_CAROUSEL_ITEMS",
    "DOWNLOAD_TIMEOUT_SECONDS",
    "DownloadBusyError",
    "DownloadResult",
    "classify_media_type",
    "download_slot",
    "get_temp_download_dir",
    "make_temp_output_template",
    "cleanup_file",
]
