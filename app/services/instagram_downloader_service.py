from __future__ import annotations

import re

from app.services.media_downloader_common import (
    DownloadBusyError,
    DownloadResult,
    download_slot,
)
from app.services.ytdlp_backend import run_download

_INSTAGRAM_URL_PATTERN = re.compile(
    r"^https?://(www\.)?instagram\.com/"
    r"(p|reel|reels|tv)/[A-Za-z0-9_\-]+",
    re.IGNORECASE,
)


def validate_url(url: str) -> bool:
    if not url:
        return False

    return bool(_INSTAGRAM_URL_PATTERN.match(url.strip()))


async def download(url: str) -> DownloadResult:
    """
    Insta-Save: faqat ochiq (public) Instagram post/reel
    videolarini yuklab oladi. Login/session credential talab
    qiladigan yoki maxfiy akkauntlarni chetlab o'tishga hech
    qanday urinish yo'q — bunday hollarda yt-dlp tabiiy
    ravishda xatolik qaytaradi va "private" sifatida
    belgilanadi.
    """

    if not validate_url(url):
        return DownloadResult(ok=False, error_code="invalid_url")

    try:
        async with download_slot():
            return await run_download(url)

    except DownloadBusyError:
        return DownloadResult(ok=False, error_code="busy")


__all__ = [
    "validate_url",
    "download",
]
