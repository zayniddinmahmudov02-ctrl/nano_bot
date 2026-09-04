from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import aiohttp
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import ExchangeRateCache

logger = logging.getLogger(__name__)

# MUHIM: bu — bepul, API-kalitsiz (keyless) USD->UZS kurs manbai.
# Yangi maxfiy qiymat (.env) talab qilmaydi. API ishlamay qolsa,
# oxirgi muvaffaqiyatli kurs (DB kesh) ishlatiladi — hech qachon
# botni yiqitmaydi.
EXCHANGE_RATE_API_URL = "https://open.er-api.com/v6/latest/USD"
EXCHANGE_RATE_SOURCE = "open.er-api.com"

# API ham, DB kesh ham hech qachon muvaffaqiyatli bo'lmagan
# holatdagi so'nggi, so'nggi chora fallback qiymati (taxminiy).
# Faqat botning umuman ishlashdan to'xtab qolmasligi uchun.
LAST_RESORT_FALLBACK_RATE = 12700.0

_REQUEST_TIMEOUT_SECONDS = 10

# Jarayon-ichi (in-memory) kesh — har bir foydalanuvchi so'rovida
# DB'ga ham murojaat qilinmasligi uchun.
_memory_cache: Optional["ExchangeRateSnapshot"] = None
_memory_cache_monotonic: float = 0.0
_MEMORY_CACHE_TTL_SECONDS = 300


@dataclass
class ExchangeRateSnapshot:
    rate: float
    source: str
    fetched_at: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _fetch_rate_from_api() -> Optional[float]:
    try:
        timeout = aiohttp.ClientTimeout(
            total=_REQUEST_TIMEOUT_SECONDS
        )

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:
            async with session.get(
                EXCHANGE_RATE_API_URL
            ) as response:
                if response.status != 200:
                    logger.warning(
                        "Exchange rate API status=%s",
                        response.status,
                    )
                    return None

                data = await response.json(
                    content_type=None
                )

        rates = data.get("rates") or {}
        uzs = rates.get("UZS")

        if uzs is None:
            logger.warning(
                "Exchange rate API javobida UZS topilmadi."
            )
            return None

        rate = float(uzs)

        if rate <= 0:
            return None

        return rate

    except Exception:
        # MUHIM: tarmoq/API xatosi bot crash qilishiga sabab
        # bo'lmasligi kerak — faqat xavfsiz log va None.
        logger.warning(
            "Exchange rate API'dan kurs olishda xatolik "
            "(fallback ishlatiladi).",
            exc_info=True,
        )
        return None


async def _load_db_cache() -> Optional[ExchangeRateSnapshot]:
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ExchangeRateCache).where(
                    ExchangeRateCache.id == 1
                )
            )

            row = result.scalar_one_or_none()

            if row is None:
                return None

            return ExchangeRateSnapshot(
                rate=float(row.rate),
                source=row.source or EXCHANGE_RATE_SOURCE,
                fetched_at=row.fetched_at,
            )

    except Exception:
        logger.exception(
            "Exchange rate DB keshini o'qishda xatolik."
        )
        return None


async def _save_db_cache(rate: float, source: str) -> None:
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ExchangeRateCache).where(
                    ExchangeRateCache.id == 1
                )
            )

            row = result.scalar_one_or_none()

            if row is None:
                row = ExchangeRateCache(
                    id=1,
                    rate=rate,
                    source=source,
                )
                session.add(row)
            else:
                row.rate = rate
                row.source = source

            await session.commit()

    except Exception:
        logger.exception(
            "Exchange rate DB keshiga yozishda xatolik."
        )


async def refresh_exchange_rate() -> Optional[ExchangeRateSnapshot]:
    """
    API'dan yangi kursni oladi va muvaffaqiyatli bo'lsa DB
    keshiga yozadi. Scheduler tomonidan muntazam chaqiriladi.

    API ishlamasa — hech narsa o'zgarmaydi, oxirgi muvaffaqiyatli
    qiymat (DB kesh) ishlatilaveradi. Hech qachon xatolik
    ko'tarmaydi.
    """

    global _memory_cache, _memory_cache_monotonic

    rate = await _fetch_rate_from_api()

    if rate is None:
        return None

    await _save_db_cache(rate, EXCHANGE_RATE_SOURCE)

    snapshot = ExchangeRateSnapshot(
        rate=rate,
        source=EXCHANGE_RATE_SOURCE,
        fetched_at=_now(),
    )

    _memory_cache = snapshot
    _memory_cache_monotonic = time.monotonic()

    logger.info("USD->UZS kursi yangilandi.")

    return snapshot


async def get_exchange_rate() -> ExchangeRateSnapshot:
    """
    Joriy USD->UZS kursini qaytaradi.

    Tartib:
    1. Jarayon-ichi kesh (agar hali "yangi" bo'lsa) — API/DB'ga
       umuman murojaat qilinmaydi.
    2. DB kesh (oxirgi muvaffaqiyatli qiymat).
    3. So'nggi chora — qattiq belgilangan taxminiy qiymat
       (bot hech qachon shu funksiya sababli yiqilmasligi
       uchun).

    MUHIM: bu funksiya HAR BIR user request'da tashqi API'ga
    murojaat QILMAYDI — faqat scheduler orqali muntazam
    (`refresh_exchange_rate`) yangilanadi.
    """

    global _memory_cache, _memory_cache_monotonic

    if (
        _memory_cache is not None
        and (
            time.monotonic() - _memory_cache_monotonic
            < _MEMORY_CACHE_TTL_SECONDS
        )
    ):
        return _memory_cache

    db_snapshot = await _load_db_cache()

    if db_snapshot is not None:
        _memory_cache = db_snapshot
        _memory_cache_monotonic = time.monotonic()
        return db_snapshot

    # DB'da hali hech qanday muvaffaqiyatli kurs yo'q — birinchi
    # marta jonli urinib ko'ramiz (masalan bot birinchi marta
    # ishga tushganda, scheduler hali ishlamagan bo'lishi mumkin).
    live_rate = await _fetch_rate_from_api()

    if live_rate is not None:
        await _save_db_cache(live_rate, EXCHANGE_RATE_SOURCE)

        snapshot = ExchangeRateSnapshot(
            rate=live_rate,
            source=EXCHANGE_RATE_SOURCE,
            fetched_at=_now(),
        )

        _memory_cache = snapshot
        _memory_cache_monotonic = time.monotonic()

        return snapshot

    logger.warning(
        "USD->UZS kursi hech qayerdan olinmadi — so'nggi "
        "chora fallback qiymati ishlatilmoqda."
    )

    return ExchangeRateSnapshot(
        rate=LAST_RESORT_FALLBACK_RATE,
        source="fallback",
        fetched_at=_now(),
    )


def convert_usd_to_uzs(
    usd_amount: float,
    rate: float,
) -> float:
    return round(usd_amount * rate, -2)


__all__ = [
    "ExchangeRateSnapshot",
    "refresh_exchange_rate",
    "get_exchange_rate",
    "convert_usd_to_uzs",
    "LAST_RESORT_FALLBACK_RATE",
]
