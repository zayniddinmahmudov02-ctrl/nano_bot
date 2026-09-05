from __future__ import annotations

# ============================================================
# Instagram Save / YouTube Save uchun MARKAZLASHTIRILGAN xatolik
# tasnifi.
# ============================================================
#
# MUHIM: bu yagona joy — yt-dlp/tarmoq xatolarini standart,
# barqaror kodlar to'plamiga aylantiradi. Handler (assistant.py)
# va matn qatlami (nano_texts.py) faqat shu kodlarga qarab ish
# yuritadi — yt-dlp xabarlarining o'zi (inglizcha, tez-tez
# o'zgaradigan) hech qayerda foydalanuvchiga to'g'ridan-to'g'ri
# ko'rsatilmaydi.
#
# Kodlar ataylab platformalar orasida UMUMIY (bitta classifier,
# ikkala provider — Instagram va YouTube — bir xil yt-dlp orqali
# ishlaydi). Ba'zi kodlar (masalan AGE_RESTRICTED) amalda faqat
# YouTube uchun uchraydi, lekin buni Instagram uchun ham
# ishlatishga to'sqinlik yo'q — classifier xabar matniga qarab
# ishlaydi, platformaga emas.

YT_DLP_UNAVAILABLE = "YT_DLP_UNAVAILABLE"
INVALID_URL = "INVALID_URL"
BUSY = "BUSY"
PRIVATE = "PRIVATE"
LOGIN_REQUIRED = "LOGIN_REQUIRED"
AGE_RESTRICTED = "AGE_RESTRICTED"
VIDEO_UNAVAILABLE = "VIDEO_UNAVAILABLE"
NOT_FOUND = "NOT_FOUND"
GEO_RESTRICTED = "GEO_RESTRICTED"
RATE_LIMITED = "RATE_LIMITED"
TIMEOUT = "TIMEOUT"
NETWORK_ERROR = "NETWORK_ERROR"
FILE_TOO_LARGE = "FILE_TOO_LARGE"
FFMPEG_ERROR = "FFMPEG_ERROR"
EXTRACTOR_ERROR = "EXTRACTOR_ERROR"
UNKNOWN = "UNKNOWN"

# MUHIM (spec 4/5-bo'lim — "AUTHENTICATION"): loyihada hozircha
# userning shaxsiy YouTube/Instagram akkaunti uchun xavfsiz
# cookie/session saqlash arxitekturasi YO'Q (Telethon faqat
# TELEGRAM akkauntlari uchun ishlaydi — bu boshqa tizim). Yangi
# bunday tizim qurish (cookie fayllarni har user uchun alohida,
# shifrlangan holda saqlash, yangilash, hech qachon log qilmaslik)
# — jiddiy YANGI xavfsizlik yuzasi va spec buni ANIQ shart
# qilmagan ("agar mavjud architecture yetarli bo'lmasa — aniq
# limitation yoz" deb ruxsat berilgan). Shu sabab LOGIN_REQUIRED/
# AGE_RESTRICTED holatlarida foydalanuvchiga xolis va aniq
# tushuntirish beriladi ("bu kontent tizimga kirilgan holatda
# ko'rish mumkin, hozircha qo'llab-quvvatlanmaydi"), lekin hech
# qanday parol/login/2FA so'ralmaydi va bypass qilinmaydi.

_ORDERED_MARKERS = (
    (
        AGE_RESTRICTED,
        (
            "confirm your age",
            "age-restricted",
            "age restricted",
            "inappropriate for some users",
        ),
    ),
    (
        # MUHIM (tartib ataylab): PRIVATE — LOGIN_REQUIRED'dan
        # OLDIN tekshiriladi. Sabab: haqiqiy YouTube xabari
        # "Private video. Sign in if you've been granted access..."
        # ham "sign in" so'zini o'z ichiga oladi, lekin bu aslida
        # LOGIN talabi emas — bu kontent shu foydalanuvchi UCHUN
        # UMUMAN mo'ljallanmagan (private) degani, boshqa hech
        # qanday login bu yerda yordam bermaydi.
        PRIVATE,
        (
            "private video",
            "private account",
            "this is a private",
            "private profile",
            "is private",
        ),
    ),
    (
        # MUHIM (real production sinovi bilan topilgan): YouTube
        # ba'zan xuddi shu bot-tekshiruvini video MA'LUMOTLARINI
        # yuklab olish bosqichida (CDN darajasida) oddiy "HTTP
        # Error 403: Forbidden" sifatida ham namoyon qiladi —
        # sahifa darajasidagi aniq "sign in" xabarisiz. Shu sabab
        # "403"/"forbidden" ham shu toifaga kiritildi.
        LOGIN_REQUIRED,
        (
            "sign in to confirm you're not a bot",
            "sign in",
            "log in",
            "login required",
            "use --cookies",
            "requires authentication",
            "403",
            "forbidden",
        ),
    ),
    (
        GEO_RESTRICTED,
        (
            "available in your country",
            "not available on this app",
            "blocked it in your country",
            "geo-restrict",
            "georestrict",
        ),
    ),
    (
        NOT_FOUND,
        (
            "404",
            "unable to find",
            "no longer exists",
            "page not found",
            "content unavailable",
        ),
    ),
    (
        VIDEO_UNAVAILABLE,
        (
            "video unavailable",
            "video has been removed",
            "no longer available",
            "has been deleted",
            "this content isn't available",
            "unavailable",
        ),
    ),
    (
        RATE_LIMITED,
        (
            "429",
            "too many requests",
            "rate-limit",
            "rate limit",
        ),
    ),
    (
        FFMPEG_ERROR,
        ("ffmpeg",),
    ),
    (
        FILE_TOO_LARGE,
        ("max-filesize", "too large", "filesize"),
    ),
    (
        TIMEOUT,
        ("timed out", "timeout"),
    ),
    (
        NETWORK_ERROR,
        (
            "network",
            "connection reset",
            "connection refused",
            "name resolution",
            "unreachable",
            "temporary failure in name resolution",
            "handshake",
        ),
    ),
    (
        EXTRACTOR_ERROR,
        (
            "unsupported url",
            "no video formats found",
            "unable to extract",
            "requested format is not available",
            "failed to parse",
            "unable to download webpage",
        ),
    ),
)


def classify_download_exception(exc: BaseException) -> str:
    """
    Berilgan istisnoni standart xatolik kodlaridan biriga
    aylantiradi. Faqat exception matni (xavfsiz, umumiy tarzda)
    tekshiriladi — hech qanday URL/token/secret bu yerga
    berilmaydi va logga yozilmaydi.
    """

    if isinstance(exc, ImportError):
        return YT_DLP_UNAVAILABLE

    if isinstance(exc, TimeoutError):
        return TIMEOUT

    message = str(exc).lower()

    for code, markers in _ORDERED_MARKERS:
        if any(marker in message for marker in markers):
            return code

    return UNKNOWN


__all__ = [
    "YT_DLP_UNAVAILABLE",
    "INVALID_URL",
    "BUSY",
    "PRIVATE",
    "LOGIN_REQUIRED",
    "AGE_RESTRICTED",
    "VIDEO_UNAVAILABLE",
    "NOT_FOUND",
    "GEO_RESTRICTED",
    "RATE_LIMITED",
    "TIMEOUT",
    "NETWORK_ERROR",
    "FILE_TOO_LARGE",
    "FFMPEG_ERROR",
    "EXTRACTOR_ERROR",
    "UNKNOWN",
    "classify_download_exception",
]
