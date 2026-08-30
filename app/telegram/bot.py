import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import BOT_TOKEN

logger = logging.getLogger(__name__)


def create_bot() -> Bot:
    """
    Nano-Bot Telegram Bot API clientini yaratadi.
    """

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN .env faylida belgilanmagan."
        )

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    logger.info("Telegram Bot API client yaratildi.")

    return bot


async def close_bot(bot: Bot) -> None:
    """
    Bot sessionini to'g'ri yopadi.
    """

    try:
        await bot.session.close()
        logger.info(
            "Telegram Bot API session yopildi."
        )
    except Exception:
        logger.exception(
            "Bot sessionini yopishda xatolik."
        )