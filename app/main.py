from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import BOT_TOKEN
from app.database.db import (
    check_database,
    close_database,
    create_tables,
)
from app.handlers import (
    start_router,
    telegram_connect_router,
    auto_replies_router,
    first_message_router,
    referrals_router,
    statistics_router,
    language_router,
    settings_router,
    premium_router,
)
from app.services.auto_reply_engine import auto_reply_engine
from app.telegram.user_client import telegram_client_manager


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("nano_bot")


# ============================================================
# BOT
# ============================================================

def create_bot() -> Bot:
    """
    Telegram Bot obyektini yaratadi.
    """

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. .env faylini tekshiring."
        )

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    return bot


# ============================================================
# DISPATCHER
# ============================================================

def create_dispatcher() -> Dispatcher:
    """
    Aiogram Dispatcher yaratadi.

    FSM uchun MemoryStorage default holatda ishlatiladi.
    """

    dp = Dispatcher()

    return dp


# ============================================================
# ROUTERS
# ============================================================

def register_routers(dp: Dispatcher) -> None:
    """
    Barcha handler routerlarini Dispatcher'ga ulaydi.
    """

    # Eng avval /start
    dp.include_router(start_router)

    # Telegram ulash
    dp.include_router(telegram_connect_router)

    # Avto javoblar
    dp.include_router(auto_replies_router)

    # Birinchi xabar
    dp.include_router(first_message_router)

    # Referallar
    dp.include_router(referrals_router)

    # Statistika
    dp.include_router(statistics_router)

    # Til
    dp.include_router(language_router)

    # Sozlamalar
    dp.include_router(settings_router)

    # Premium
    dp.include_router(premium_router)

    logger.info("Barcha handler routerlar yuklandi.")


# ============================================================
# STARTUP
# ============================================================

async def startup() -> None:
    """
    Bot ishga tushishidan oldingi barcha jarayonlar.
    """

    logger.info("========================================")
    logger.info("Nano-Bot startup boshlandi")
    logger.info("========================================")

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    logger.info("PostgreSQL tekshirilmoqda...")

    await check_database()

    logger.info("PostgreSQL ulandi.")

    # --------------------------------------------------------
    # TABLES
    # --------------------------------------------------------

    await create_tables()

    logger.info("Database jadvallari tayyor.")

    # --------------------------------------------------------
    # TELEGRAM USER SESSIONS
    # --------------------------------------------------------

    try:
        await telegram_client_manager.load_existing_sessions()

        logger.info(
            "Saqlangan Telegram sessiyalari yuklandi."
        )

    except Exception:
        logger.exception(
            "Telegram sessiyalarini yuklashda xatolik."
        )

    # --------------------------------------------------------
    # AUTO REPLY ENGINE
    # --------------------------------------------------------

    try:
        await auto_reply_engine.start()

        logger.info(
            "Auto Reply Engine ishga tushdi."
        )

    except Exception:
        logger.exception(
            "Auto Reply Engine ishga tushmadi."
        )

    logger.info("Nano-Bot ishga tayyor.")


# ============================================================
# SHUTDOWN
# ============================================================

async def shutdown() -> None:
    """
    Bot to'xtashidan oldingi tozalash jarayonlari.
    """

    logger.info("Nano-Bot shutdown boshlandi.")

    # --------------------------------------------------------
    # AUTO REPLY ENGINE
    # --------------------------------------------------------

    try:
        await auto_reply_engine.stop()

        logger.info(
            "Auto Reply Engine to'xtatildi."
        )

    except Exception:
        logger.exception(
            "Auto Reply Engine to'xtatishda xatolik."
        )

    # --------------------------------------------------------
    # TELEGRAM USER CLIENTS
    # --------------------------------------------------------

    try:
        await telegram_client_manager.shutdown()

        logger.info(
            "Telegram user clientlar to'xtatildi."
        )

    except Exception:
        logger.exception(
            "Telegram clientlarni to'xtatishda xatolik."
        )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    try:
        await close_database()

        logger.info(
            "Database connection yopildi."
        )

    except Exception:
        logger.exception(
            "Database yopishda xatolik."
        )

    logger.info("Nano-Bot shutdown tugadi.")


# ============================================================
# MAIN
# ============================================================

async def main() -> None:
    """
    Nano-Bot asosiy ishga tushirish funksiyasi.
    """

    bot = create_bot()
    dp = create_dispatcher()

    register_routers(dp)

    try:
        # Startup
        await startup()

        logger.info("========================================")
        logger.info("Nano-Bot ishga tushmoqda...")
        logger.info("Start polling")
        logger.info("========================================")

        # ----------------------------------------------------
        # POLLING
        # ----------------------------------------------------

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )

    except asyncio.CancelledError:
        logger.info(
            "Polling cancelled."
        )

    except KeyboardInterrupt:
        logger.info(
            "KeyboardInterrupt. Bot to'xtatilmoqda."
        )

    except Exception:
        logger.exception(
            "Nano-Bot ishlash vaqtida kritik xatolik."
        )

    finally:
        # ----------------------------------------------------
        # SHUTDOWN
        # ----------------------------------------------------

        await shutdown()

        try:
            await bot.session.close()
        except Exception:
            logger.exception(
                "Bot session yopishda xatolik."
            )

        logger.info(
            "Nano-Bot to'liq to'xtadi."
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info(
            "Nano-Bot foydalanuvchi tomonidan to'xtatildi."
        )