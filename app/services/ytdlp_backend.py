from __future__ import annotations

import asyncio
import glob
import logging
import os
import shutil
from typing import Any, Dict, List, Optional, Tuple

from app.services.media_downloader_common import (
    DOWNLOAD_TIMEOUT_SECONDS,
    MAX_CAROUSEL_ITEMS,
    MAX_FILE_SIZE_BYTES,
    DownloadResult,
    classify_media_type,
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
        # MUHIM (real testlar bilan tasdiqlangan): oldingi
        # `best[acodec!=none][vcodec!=none]` filtri ko'plab
        # provayderlarda (masalan Instagram) codec maydonlari
        # "noma'lum" (None) bo'lgan, lekin AMALDA to'liq
        # (audio+video birlashtirilgan, ffmpeg SHART EMAS)
        # formatlarni NOTO'G'RI rad etib, keraksiz ravishda
        # ffmpeg talab qiluvchi bestvideo+bestaudio yo'liga
        # tushirib yuborar edi. Oddiy "best" — yt-dlp'ning o'z
        # ichki tanlash mantig'i — bunday formatlarni to'g'ri
        # tanlaydi; faqat HAQIQATAN alohida video/audio
        # oqimlaridan boshqa hech narsa mavjud bo'lmagan holatda
        # (masalan zamonaviy YouTube) ikkinchi variant —
        # bestvideo+bestaudio (ffmpeg orqali birlashtirish) —
        # ishga tushadi.
        "format": "best/bestvideo+bestaudio",
        "merge_output_format": "mp4",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # Carousel/multi-media postlar uchun: bitta so'rovda
        # cheksiz ko'p elementni yuklab olishning oldini oladi.
        "playlistend": MAX_CAROUSEL_ITEMS,
        "max_filesize": MAX_FILE_SIZE_BYTES,
        "logger": _SilentYtDlpLogger(),
        "socket_timeout": 30,
        "retries": 2,
        "noprogress": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=True)


def _glob_pattern_for(output_path: str) -> str:
    """
    `output_path` shablonidagi `%(autonumber)s`/`%(ext)s`
    joy-belgilarini `*` bilan almashtirib, shu YUKLAB OLISH
    urinishiga tegishli BARCHA haqiqiy fayllarni (carousel
    elementlari, .part qoldiqlari va h.k.) topish uchun glob
    naqshini quradi.
    """

    return output_path.replace(
        "%(autonumber)s", "*"
    ).replace("%(ext)s", "*")


def _cleanup_all(glob_pattern: str) -> None:
    """
    Shu yuklab olish urinishiga tegishli BARCHA vaqtinchalik
    fayllarni (muvaffaqiyatli saqlangan/tanlanmagan carousel
    elementlari, chala .part fayllar) diskdan o'chiradi — orphan
    vaqtinchalik fayl qolmasligi uchun (spec 6-bo'lim).
    """

    try:
        for path in glob.glob(glob_pattern):
            cleanup_file(path)
    except Exception:
        logger.exception(
            "Vaqtinchalik fayllarni tozalashda xatolik."
        )


def _resolve_entry_path(entry: Dict[str, Any]) -> Optional[str]:
    requested_downloads = entry.get("requested_downloads")

    if requested_downloads:
        return requested_downloads[0].get("filepath")

    return entry.get("_filename")


async def run_download(url: str) -> DownloadResult:
    """
    Berilgan havoladan media(lar)ni vaqtincha diskka yuklab oladi.

    Faqat OCHIQ (public) kontent bilan ishlaydi — maxfiy/login
    talab qiladigan kontentni chetlab o'tishga (bypass) hech
    qanday urinish yo'q; yt-dlp shunday holatlarda tabiiy
    ravishda xatolik qaytaradi va biz buni "private" sifatida
    aniq belgilaymiz.

    Carousel/multi-media post bo'lsa — imkon qadar barcha
    elementlar (MAX_CAROUSEL_ITEMS chegarasigacha) yuklab olinadi;
    natijaning birinchi elementi `file_path`/`media_type`/`title`
    orqali, qolganlari `extra_files` orqali qaytariladi.
    """

    output_template = make_temp_output_template()
    output_path = str(output_template)
    glob_pattern = _glob_pattern_for(output_path)

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
        _cleanup_all(glob_pattern)
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
        _cleanup_all(glob_pattern)

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

        if "requested format is not available" in message:
            logger.warning(
                "Yuklab olish rad etildi: mos format topilmadi "
                "(server ffmpeg'siz birlashtira olmadi bo'lishi "
                "mumkin)."
            )
            return DownloadResult(
                ok=False, error_code="unavailable"
            )

        logger.exception(
            "Yuklab olishda kutilmagan xatolik."
        )
        return DownloadResult(ok=False, error_code="failed")

    if info is None:
        _cleanup_all(glob_pattern)
        return DownloadResult(ok=False, error_code="failed")

    # Carousel (playlist) bo'lsa bir nechta entry, aks holda —
    # bitta "entry" sifatida o'zi.
    entries: List[Dict[str, Any]] = info.get("entries") or [info]

    accepted: List[Tuple[str, str, Optional[str]]] = []
    had_oversized_candidate = False
    kept_paths = set()

    for entry in entries[:MAX_CAROUSEL_ITEMS]:
        if entry is None:
            continue

        path = _resolve_entry_path(entry)

        if not path or not os.path.exists(path):
            continue

        file_size = os.path.getsize(path)

        if file_size <= 0:
            cleanup_file(path)
            continue

        if file_size > MAX_FILE_SIZE_BYTES:
            had_oversized_candidate = True
            cleanup_file(path)
            continue

        title = entry.get("title") or info.get("title")
        media_type = classify_media_type(path)

        accepted.append((path, media_type, title))
        kept_paths.add(os.path.abspath(path))

    # Ushbu urinishga tegishli, lekin YUQORIDA "qabul qilingan"
    # ro'yxatga kirmagan har qanday boshqa fayl (masalan ishlatil-
    # magan format probasi, .part qoldiq) — orphan sifatida
    # o'chiriladi.
    for path in glob.glob(glob_pattern):
        if os.path.abspath(path) not in kept_paths:
            cleanup_file(path)

    if not accepted:
        if had_oversized_candidate:
            return DownloadResult(ok=False, error_code="too_large")

        return DownloadResult(ok=False, error_code="failed")

    first_path, first_media_type, first_title = accepted[0]

    return DownloadResult(
        ok=True,
        file_path=first_path,
        title=first_title,
        media_type=first_media_type,
        extra_files=accepted[1:] or None,
    )


__all__ = [
    "run_download",
    "is_ffmpeg_available",
]
