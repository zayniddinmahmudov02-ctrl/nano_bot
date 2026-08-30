from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage

from app.config import BOT_TOKEN


def create_bot() -> Bot:
    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN .env faylida belgilanmagan."
        )

    return Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )


def create_dispatcher(
    storage: BaseStorage | None = None,
) -> Dispatcher:
    return Dispatcher(
        storage=storage,
    )