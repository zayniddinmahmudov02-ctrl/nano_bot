from __future__ import annotations

import re

from app.services.download_errors import BUSY, INVALID_URL
from app.services.media_downloader_common import (
    DownloadBusyError,
    DownloadResult,
    download_slot,
)
from app.services.ytdlp_backend import run_download

_YOUTUBE_URL_PATTERN = re.compile(
    r"^https?://(www\.|m\.)?"
    r"(youtube\.com/(watch\?v=|shorts/|live/)|youtu\.be/)"
    r"[A-Za-z0-9_\-?&=]+",
    re.IGNORECASE,
)


def validate_url(url: str) -> bool:
    if not url:
        return False

    return bool(_YOUTUBE_URL_PATTERN.match(url.strip()))


async def download(url: str) -> DownloadResult:
    """
    YouTube-Save: faqat ochiq (public) YouTube videolarini
    yuklab oladi. Provider almashtirish kerak bo'lsa, faqat
    shu fayl (va ytdlp_backend) o'zgartiriladi.
    """

    if not validate_url(url):
        return DownloadResult(ok=False, error_code=INVALID_URL)

    try:
        async with download_slot():
            return await run_download(url)

    except DownloadBusyError:
        return DownloadResult(ok=False, error_code=BUSY)


__all__ = [
    "validate_url",
    "download",
]
