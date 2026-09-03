from __future__ import annotations

import asyncio
import logging
import os
import shutil
from typing import Any, Dict, Optional

from app.services.media_downloader_common import (
    DOWNLOAD_TIMEOUT_SECONDS,
    MAX_FILE_SIZE_BYTES,
    DownloadResult,
    cleanup_file,
    make_temp_output_template,
)

logger = logging.getLogger(__name__)

# ============================================================
# yt-dlp asosidagi umumiy backend.
#
# YouTube-Save va Insta-Save — ikkalasi ham shu bitta,
# provider-agnostik funksiyadan foydalanadi. Kelajakda
# provider almashtirish kerak bo'lsa, faqat shu fayl
# o'zgartiriladi — yuqori darajadagi handler/service kodi
# tegilmaydi.
#
# MUHIM: `url` (havola) hech qachon logga yozilmaydi — faqat
# umumiy, xavfsiz xabarlar yoziladi.
# ============================================================


class _SilentYtDlpLogger:
    """
    yt-dlp'ning o'z konsol chiqishini butunlay o'chiradi —
    shu orqali havola/token kabi ma'lumotlar logga tasodifan
    tushib qolmaydi.
    """

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        pass


def is_ffmpeg_available() -> bool:
    """
    Zamonaviy YouTube (va ko'plab boshqa platformalar) video
    va audio oqimlarini ALOHIDA beradi — ularni bitta faylga
    birlashtirish uchun ffmpeg SHART. ffmpeg serverda
    o'rnatilmagan bo'lsa, bu funksiya False qaytaradi va
    yuklab olish urinishi boshlanmasdan oldin foydalanuvchiga
    aniq xabar ko'rsatiladi.
    """

    return shutil.which("ffmpeg") is not None


def _blocking_download(
    url: str,
    output_path: str,
) -> Optional[Dict[str, Any]]:
    """
    MUHIM: bu funksiya BLOKLOVCHI (sync) — faqat alohida
    threadda (asyncio.to_thread) chaqirilishi kerak.
    """

    import yt_dlp

    ydl_opts = {
        # MUHIM: zamonaviy YouTube deyarli hech qachon tayyor
        # (video+audio birlashtirilgan) format bermaydi — shu
        # sababli eng yaxshi video va audio oqimlari alohida
        # olinib, ffmpeg orqali bitta mp4 faylga birlashtiriladi
        # (bu — is_ffmpeg_available() orqali oldindan
        # tekshiriladi). Agar pre-muxed format mavjud bo'lsa
        # (masalan ba'zi boshqa platformalarda), u ustunlik
        # oladi va ffmpeg umuman kerak bo'lmaydi.
        "format": (
            "best[acodec!=none][vcodec!=none]/"
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo+bestaudio/best"
        ),
        "merge_output_format": "mp4",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": MAX_FILE_SIZE_BYTES,
        "logger": _SilentYtDlpLogger(),
        "socket_timeout": 30,
        "retries": 2,
        "noprogress": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=True)


async def run_download(url: str) -> DownloadResult:
    """
    Berilgan havoladan videoni vaqtincha diskka yuklab oladi.

    Faqat OCHIQ (public) kontent bilan ishlaydi — maxfiy/login
    talab qiladigan kontentni chetlab o'tishga (bypass) hech
    qanday urinish yo'q; yt-dlp shunday holatlarda tabiiy
    ravishda xatolik qaytaradi va biz buni "private" sifatida
    aniq belgilaymiz.
    """

    output_template = make_temp_output_template("mp4")
    output_path = str(output_template)

    try:
        info = await asyncio.wait_for(
            asyncio.to_thread(
                _blocking_download,
                url,
                output_path,
            ),
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
        )

    except asyncio.TimeoutError:
        cleanup_file(output_path)
        logger.warning(
            "Yuklab olish vaqt chegarasidan oshdi (timeout)."
        )
        return DownloadResult(ok=False, error_code="timeout")

    except ImportError:
        logger.error(
            "yt-dlp kutubxonasi o'rnatilmagan."
        )
        return DownloadResult(
            ok=False, error_code="unavailable"
        )

    except Exception as error:
        cleanup_file(output_path)

        message = str(error).lower()

        if "ffmpeg" in message:
            logger.error(
                "yt-dlp: ffmpeg serverda o'rnatilmagan — "
                "video/audio birlashtirish imkonsiz."
            )
            return DownloadResult(
                ok=False, error_code="unavailable"
            )

        if any(
            keyword in message
            for keyword in (
                "private",
                "login",
                "sign in",
                "restricted",
                "rate-limit",
            )
        ):
            logger.warning(
                "Yuklab olish rad etildi: maxfiy/himoyalangan "
                "kontent."
            )
            return DownloadResult(
                ok=False, error_code="private"
            )

        if any(
            keyword in message
            for keyword in ("max-filesize", "too large", "filesize")
        ):
            logger.warning(
                "Yuklab olish rad etildi: fayl hajmi "
                "chegaradan katta."
            )
            return DownloadResult(
                ok=False, error_code="too_large"
            )

        logger.exception(
            "Yuklab olishda kutilmagan xatolik."
        )
        return DownloadResult(ok=False, error_code="failed")

    actual_path = output_path

    if info is not None:
        requested_downloads = info.get("requested_downloads")

        if requested_downloads:
            actual_path = requested_downloads[0].get(
                "filepath", output_path
            )
        elif info.get("_filename"):
            actual_path = info.get("_filename")

    if not actual_path or not os.path.exists(actual_path):
        return DownloadResult(ok=False, error_code="failed")

    file_size = os.path.getsize(actual_path)

    if file_size > MAX_FILE_SIZE_BYTES:
        cleanup_file(actual_path)
        return DownloadResult(ok=False, error_code="too_large")

    if file_size <= 0:
        cleanup_file(actual_path)
        return DownloadResult(ok=False, error_code="failed")

    title = info.get("title") if info else None

    return DownloadResult(
        ok=True,
        file_path=actual_path,
        title=title,
    )


__all__ = [
    "run_download",
    "is_ffmpeg_available",
]
