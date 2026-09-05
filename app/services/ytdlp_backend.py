from __future__ import annotations

import asyncio
import glob
import logging
import os
import shutil
from typing import Any, Dict, List, Optional, Tuple

from app.config import FFMPEG_PATH
from app.services.download_errors import (
    FILE_TOO_LARGE,
    TIMEOUT,
    UNKNOWN,
    classify_download_exception,
)
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


def is_yt_dlp_available() -> bool:
    """
    yt-dlp kutubxonasi (Python paketi sifatida) o'rnatilgan va
    import qilinishi mumkinmi — tekshiradi.

    MUHIM (root cause tuzatildi): "⚠️ Bu funksiya hozircha
    serverda sozlanmagan" xabari ILGARI `is_ffmpeg_available()`
    ga bog'liq edi — bu NOTO'G'RI edi, chunki ffmpeg yo'qligi
    "funksiya butunlay sozlanmagan" degani EMAS (ko'p Instagram
    va hatto ba'zi YouTube formatlari ffmpeg'siz ham ishlaydi).
    Bu xabar ENDI faqat yt-dlp'ning O'ZI mavjud bo'lmaganda
    ko'rsatiladi — ffmpeg yo'qligi alohida, download vaqtidagi
    ("unavailable") xatolik sifatida, faqat HAQIQATAN merge talab
    qiladigan videolar uchungina yuzaga keladi.
    """

    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        return False


_COMMON_FFMPEG_PATHS = (
    "/usr/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/snap/bin/ffmpeg",
)


def resolve_ffmpeg_location() -> Optional[str]:
    """
    ffmpeg'ning haqiqiy joylashuvini aniqlaydi.

    MUHIM: faqat `shutil.which("ffmpeg")` (joriy protsessning
    PATH muhitiga bog'liq) ga tayanish YETARLI EMAS — systemd
    xizmati ko'pincha interaktiv shelldan FARQLI, minimal PATH
    muhitida ishga tushadi, shu sabab ffmpeg serverda HAQIQATAN
    o'rnatilgan bo'lsa ham topilmasligi mumkin. Shu sabab:
    1) avval aniq `.env` sozlamasi (FFMPEG_PATH) tekshiriladi;
    2) keyin joriy PATH (`shutil.which`);
    3) keyin eng ko'p tarqalgan o'rnatish joylari.
    Topilgan yo'l `yt-dlp`ga `ffmpeg_location` orqali TO'G'RIDAN-
    TO'G'RI beriladi — shu orqali yt-dlp o'zi PATH orqali qayta
    "taxmin qilishi" shart bo'lmaydi (bir xil muammoni takrorlash
    xavfisiz).
    """

    if FFMPEG_PATH and os.path.isfile(FFMPEG_PATH):
        return FFMPEG_PATH

    found = shutil.which("ffmpeg")

    if found:
        return found

    for candidate in _COMMON_FFMPEG_PATHS:
        if os.path.isfile(candidate):
            return candidate

    return None


def is_ffmpeg_available() -> bool:
    """
    Zamonaviy YouTube (va ko'plab boshqa platformalar) video
    va audio oqimlarini ALOHIDA beradi — ularni bitta faylga
    birlashtirish uchun ffmpeg SHART bo'lishi mumkin.

    MUHIM: bu funksiya ENDI YouTube Save/Insta Save'ga KIRISHNI
    bloklash uchun ISHLATILMAYDI (buning uchun
    `is_yt_dlp_available()`ga qarang) — faqat merge kerak bo'lgan
    ANIQ bir yuklab olish urinishida ffmpeg mavjudligini bilish
    uchun ishlatiladi.
    """

    return resolve_ffmpeg_location() is not None


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
        # MUHIM (real testlar bilan 2 marta tasdiqlangan/tuzatilgan):
        #
        # 1) `best[acodec!=none][vcodec!=none]` (qattiq filtr) ko'plab
        #    provayderlarda (masalan Instagram) codec maydonlari
        #    "noma'lum" (None, string "none" EMAS) bo'lgan, lekin
        #    AMALDA to'liq formatlarni NOTO'G'RI rad etardi — `?`
        #    ("none-inclusive") operatori shu muammoni SUFFIKS
        #    sifatida to'g'ri hal qiladi: `!=?none` — agar qiymat
        #    NOMA'LUM bo'lsa OK (o'tkazib yuboradi), agar ANIQ "none"
        #    ga teng bo'lsa (haqiqatan audio/video yo'q) — rad etadi.
        #
        # 2) Oddiy filtrsiz "best" (birinchi versiyada ishlatilgan)
        #    ba'zan haqiqatan AUDIOSIZ (video-only) oqimni "eng
        #    sifatli" deb tanlab qo'yishi mumkin edi (agar u eng
        #    yuqori bitrate/resolution'ga ega bo'lsa) — natijada
        #    ovozsiz video yuborilib qolardi. `[acodec!=?none]
        #    [vcodec!=?none]` filtri buni oldini oladi: audio/video
        #    ANIQ yo'q (literal "none") formatlar birinchi
        #    variantdan chiqarib tashlanadi.
        #
        # 3) `filesize`/`filesize_approx` chegarasi — Telegram limitiga
        #    (MAX_FILE_SIZE_BYTES) SIG'ADIGAN formatga USTUNLIK
        #    beradi (bor bo'lsa) — shu orqali server avval katta
        #    formatni yuklab, keyin uni rad etish o'rniga, iloji
        #    boricha to'g'ri hajmni OLDINDAN tanlaydi.
        #
        # Yakuniy fallback (`bestvideo+bestaudio`) — faqat HAQIQATAN
        # audio+video birlashtirilgan formatning o'zi mavjud
        # bo'lmagan holatlarda (masalan zamonaviy YouTube) ishga
        # tushadi — bu holatda ffmpeg SHART.
        # MUHIM (real production sinovi bilan tuzatilgan): oldingi
        # variantda `bestvideo+bestaudio` yakuniy fallback HECH
        # QANDAY hajm cheklovisiz edi — to'liq (audio+video)
        # format umuman mavjud bo'lmagan videolar uchun (masalan
        # uzun YouTube video) bu eng YUQORI sifatli (masalan 4K,
        # 240MB+) alohida oqimlarni tanlardi, keyin `max_filesize`
        # o'rtada yuklab olishni to'xtatardi — natijada chala
        # (.part) fayllar qolib, xatolik hech qanday aniq log
        # yozilmasdan "failed" bo'lib qolar edi. Endi
        # `bestvideo+bestaudio` ham AVVAL hajm chegarasiga mos
        # variant bilan sinaladi.
        "format": (
            f"best[filesize<{MAX_FILE_SIZE_BYTES}]"
            f"[acodec!=?none][vcodec!=?none]/"
            f"best[filesize_approx<{MAX_FILE_SIZE_BYTES}]"
            f"[acodec!=?none][vcodec!=?none]/"
            f"best[acodec!=?none][vcodec!=?none]/"
            f"bestvideo[filesize<{MAX_FILE_SIZE_BYTES}]"
            f"+bestaudio[filesize<{MAX_FILE_SIZE_BYTES}]/"
            f"bestvideo[filesize_approx<{MAX_FILE_SIZE_BYTES}]"
            f"+bestaudio[filesize_approx<{MAX_FILE_SIZE_BYTES}]/"
            f"bestvideo+bestaudio/best"
        ),
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

    # MUHIM (root cause tuzatildi): ffmpeg joylashuvi bu yerda
    # ANIQ ko'rsatiladi — yt-dlp'ning ICHKI PATH-asosli avtomatik
    # aniqlashiga tayanilmaydi (u ham xuddi shu PATH muammosiga
    # duch kelishi mumkin, masalan systemd xizmatining minimal
    # PATH muhitida).
    ffmpeg_location = resolve_ffmpeg_location()

    if ffmpeg_location:
        ydl_opts["ffmpeg_location"] = ffmpeg_location

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
    """
    MUHIM (real production sinovi bilan topilgan va tuzatilgan
    xato): `requested_downloads` ikkita (video + audio) elementga
    ega bo'lsa — bu ular ffmpeg orqali BIRLASHTIRILGANI (merge)
    degani. Bunday holatda `requested_downloads[0]["filepath"]`
    faqat ORALIQ (pre-merge) faylga ishora qiladi — muvaffaqiyatli
    merge'dan KEYIN ffmpeg uni O'CHIRIB YUBORADI. Yakuniy,
    HAQIQIY birlashtirilgan fayl nomi ENTRY darajasidagi
    `_filename`da saqlanadi. Faqat BITTA (allaqachon to'liq,
    merge SHART emas) oqim bo'lgandagina
    `requested_downloads[0]["filepath"]` to'g'ridan-to'g'ri
    ishonchli.
    """

    requested_downloads = entry.get("requested_downloads") or []

    if len(requested_downloads) == 1:
        return requested_downloads[0].get("filepath")

    return (
        entry.get("_filename")
        or entry.get("filename")
        or (
            requested_downloads[0].get("filepath")
            if requested_downloads
            else None
        )
    )


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
        return DownloadResult(ok=False, error_code=TIMEOUT)

    except Exception as error:
        _cleanup_all(glob_pattern)

        # MUHIM (markazlashtirilgan tasnif): xatolik matni bu
        # yerda hech qachon foydalanuvchiga ko'rsatilmaydi va
        # o'zi holida logga yozilmaydi — faqat standart kod
        # (masalan "AGE_RESTRICTED") va exception TURI. `exc_info`
        # faqat haqiqatan kutilmagan (UNKNOWN) holatlar uchun
        # to'liq traceback bilan yoziladi.
        code = classify_download_exception(error)

        if code == UNKNOWN:
            logger.exception(
                "Yuklab olishda kutilmagan xatolik: %s",
                type(error).__name__,
            )
        else:
            logger.warning(
                "Yuklab olish rad etildi: %s (%s)",
                code,
                type(error).__name__,
            )

        return DownloadResult(ok=False, error_code=code)

    if info is None:
        _cleanup_all(glob_pattern)
        logger.warning(
            "Yuklab olish muvaffaqiyatsiz: yt-dlp hech qanday "
            "xatolik ko'tarmadi, lekin ma'lumot (info) ham "
            "qaytarmadi."
        )
        return DownloadResult(ok=False, error_code=UNKNOWN)

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
            logger.warning(
                "Yuklab olish rad etildi: barcha nomzod "
                "fayl(lar) hajm chegarasidan katta edi."
            )
            return DownloadResult(ok=False, error_code=FILE_TOO_LARGE)

        logger.warning(
            "Yuklab olish muvaffaqiyatsiz: yt-dlp ma'lumot "
            "qaytardi, lekin diskda haqiqiy, ishlatsa bo'ladigan "
            "fayl topilmadi (masalan merge tugallanmagan yoki "
            "fayl yo'li noto'g'ri aniqlangan bo'lishi mumkin)."
        )
        return DownloadResult(ok=False, error_code=UNKNOWN)

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
    "is_yt_dlp_available",
    "resolve_ffmpeg_location",
]
