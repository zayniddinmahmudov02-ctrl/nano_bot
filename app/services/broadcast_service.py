from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import User

logger = logging.getLogger(__name__)

# Har bir xabar orasidagi tanaffus — Telegram flood limitlariga
# yiqilmaslik uchun.
_SEND_DELAY_SECONDS = 0.05


async def _get_active_telegram_ids() -> list:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.telegram_id).where(
                User.active.is_(True)
            )
        )

        return list(result.scalars().all())


async def run_broadcast(
    bot: Bot,
    admin_telegram_id: int,
    text: str,
) -> None:
    """
    Barcha faol foydalanuvchilarga xabar yuboradi.

    Fon vazifasi sifatida ishga tushiriladi — admin panelni
    bloklamaydi. Yakunida admin'ga natija haqida qisqa hisobot
    yuboriladi.
    """

    telegram_ids = await _get_active_telegram_ids()

    sent = 0
    failed = 0

    for telegram_id in telegram_ids:
        try:
            await bot.send_message(telegram_id, text)
            sent += 1

        except TelegramForbiddenError:
            failed += 1

        except TelegramRetryAfter as error:
            try:
                await asyncio.sleep(error.retry_after)
                await bot.send_message(telegram_id, text)
                sent += 1
            except Exception:
                failed += 1

        except Exception:
            logger.exception(
                "Broadcast xabari yuborilmadi: telegram_id=%s",
                telegram_id,
            )
            failed += 1

        await asyncio.sleep(_SEND_DELAY_SECONDS)

    logger.info(
        "Broadcast yakunlandi: sent=%s failed=%s",
        sent,
        failed,
    )

    try:
        await bot.send_message(
            admin_telegram_id,
            "📢 <b>Broadcast yakunlandi.</b>\n\n"
            f"✅ Yuborildi: <b>{sent}</b>\n"
            f"❌ Yuborilmadi: <b>{failed}</b>",
        )
    except Exception:
        logger.exception(
            "Broadcast yakun hisobotini adminga yuborib "
            "bo'lmadi."
        )


__all__ = [
    "run_broadcast",
]
