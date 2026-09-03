from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, ErrorEvent, MenuButtonCommands

from app.config import BOT_TOKEN, LOG_LEVEL
from app.database.db import (
    check_database,
    close_database,
    create_tables,
    run_manual_migrations,
)
from app.handlers import (
    start_router,
    main_router,
    password_lock_router,
    telegram_connect_router,
    agent_router,
    auto_replies_router,
    first_message_router,
    assistant_router,
    referrals_router,
    statistics_router,
    language_router,
    settings_router,
    premium_router,
    info_router,
    admin_router,
)
from app.middlewares import MaintenanceMiddleware, PasswordLockMiddleware
from app.services.auto_reply_engine import auto_reply_engine
from app.services.first_message_engine import first_message_engine
from app.services.security_service import set_bot_instance
from app.telegram.user_client import telegram_client_manager
from app.utils.logger import configure_logging


# ============================================================
# LOGGING
# ============================================================

configure_logging(
    level=getattr(logging, LOG_LEVEL, logging.INFO)
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
# TELEGRAM MENU BUTTON / BOT COMMANDS
# ============================================================
#
# Bot uchun standart Telegram "Menu" tugmasini "commands"
# rejimida sozlaydi — bosilganda foydalanuvchiga bot
# buyruqlari (kamida /start) ro'yxati ko'rsatiladi.
#
# MUHIM: Bot API'da "commands" rejimidagi Menu tugmasi matni
# Telegram klienti tomonidan o'zi belgilanadi ("Menu" so'zi) —
# bu faqat MenuButtonWebApp uchun moslashtiriladigan `text`
# maydoniga ega, u esa boshqa (web app ochish) maqsad uchun.
# Shu sababli bu yerda to'g'ri "commands" rejimi ishlatiladi.

async def configure_bot_ui(bot: Bot) -> None:
    try:
        await bot.set_my_commands(
            [
                BotCommand(
                    command="start",
                    description="Bosh menyu",
                ),
            ]
        )

        await bot.set_chat_menu_button(
            menu_button=MenuButtonCommands()
        )

        logger.info(
            "Telegram Menu Button va BotCommand'lar "
            "sozlandi."
        )

    except Exception:
        logger.exception(
            "Telegram Menu Button/BotCommand sozlashda "
            "xatolik."
        )


# ============================================================
# GLOBAL ERROR HANDLING (25-bo'lim)
# ============================================================
#
# Har bir handler o'zining try/except'iga ega, lekin bu —
# oxirgi xavfsizlik chizig'i: kutilmagan (handler ichida
# tutilmagan) har qanday xatolik shu yerda ushlanadi.
#
# Foydalanuvchiga faqat xavfsiz, umumiy xabar ko'rsatiladi.
# Logda texnik exception bo'lishi mumkin, lekin
# SecretRedactingFormatter orqali maxfiy qiymatlar avtomatik
# yashiriladi.

async def global_error_handler(event: ErrorEvent) -> None:
    logger.exception(
        "Kutilmagan (global) xatolik: %s",
        type(event.exception).__name__,
        exc_info=event.exception,
    )

    update = event.update

    chat_id = None

    if update.message is not None:
        chat_id = update.message.chat.id
    elif (
        update.callback_query is not None
        and update.callback_query.message is not None
    ):
        chat_id = update.callback_query.message.chat.id

    if chat_id is None:
        return

    try:
        await event.update.bot.send_message(
            chat_id,
            "❌ Xatolik yuz berdi. Iltimos, qayta urinib "
            "ko'ring.",
        )
    except Exception:
        logger.exception(
            "Global error handler xabarni yubora olmadi."
        )


# ============================================================
# DISPATCHER
# ============================================================

def create_dispatcher() -> Dispatcher:
    """
    Aiogram Dispatcher yaratadi.

    FSM uchun MemoryStorage default holatda ishlatiladi.
    """

    dp = Dispatcher()

    dp.errors.register(global_error_handler)

    # Maintenance mode yoqilganda admin bo'lmagan foydalanuvchi
    # so'rovlarini bloklaydi (admin uchun har doim o'tkaziladi).
    maintenance_middleware = MaintenanceMiddleware()
    dp.message.outer_middleware(maintenance_middleware)
    dp.callback_query.outer_middleware(maintenance_middleware)

    # Bot paroli (inactivity lock) — Maintenance'dan KEYIN
    # ro'yxatdan o'tkaziladi, shunda texnik ishlar rejimi
    # ustuvorlikka ega bo'ladi.
    password_lock_middleware = PasswordLockMiddleware()
    dp.message.outer_middleware(password_lock_middleware)
    dp.callback_query.outer_middleware(password_lock_middleware)

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

    # Bot paroli (inactivity lock) challenge handleri —
    # yuqori ustuvorlik.
    dp.include_router(password_lock_router)

    # Yangi inline Bosh menyu (nano:main)
    dp.include_router(main_router)

    # Nano-Agent (nano:agent va uning menyusi)
    dp.include_router(agent_router)

    # Telegram ulash (nano:agent:telegram + eski flow)
    dp.include_router(telegram_connect_router)

    # Avto javoblar (mavjud inline tizim, ar:*)
    dp.include_router(auto_replies_router)

    # Birinchi xabar (nano:agent:first)
    dp.include_router(first_message_router)

    # Nano-Yordamchi (YouTube-Save / Insta-Save)
    dp.include_router(assistant_router)

    # Referallar
    dp.include_router(referrals_router)

    # Statistika (legacy)
    dp.include_router(statistics_router)

    # Til (legacy — endi Sozlamalar ichida ham mavjud)
    dp.include_router(language_router)

    # Sozlamalar (til/premium/profil/parol)
    dp.include_router(settings_router)

    # Premium (legacy)
    dp.include_router(premium_router)

    # Nano-Info
    dp.include_router(info_router)

    # Admin panel
    dp.include_router(admin_router)

    logger.info("Barcha handler routerlar yuklandi.")


# ============================================================
# STARTUP
# ============================================================

async def startup(bot: Bot) -> None:
    """
    Bot ishga tushishidan oldingi barcha jarayonlar.
    """

    logger.info("========================================")
    logger.info("Nano-Bot startup boshlandi")
    logger.info("========================================")

    # --------------------------------------------------------
    # TELEGRAM MENU BUTTON / COMMANDS
    # --------------------------------------------------------

    await configure_bot_ui(bot)

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
    # MANUAL MIGRATIONS (yangi ustunlar)
    # --------------------------------------------------------

    try:
        await run_manual_migrations()

    except Exception:
        logger.exception(
            "Manual migratsiyalarda xatolik."
        )

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

    # --------------------------------------------------------
    # FIRST MESSAGE ENGINE
    # --------------------------------------------------------

    try:
        await first_message_engine.start()

        logger.info(
            "First Message Engine ishga tushdi."
        )

    except Exception:
        logger.exception(
            "First Message Engine ishga tushmadi."
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
    # FIRST MESSAGE ENGINE
    # --------------------------------------------------------

    try:
        await first_message_engine.stop()

        logger.info(
            "First Message Engine to'xtatildi."
        )

    except Exception:
        logger.exception(
            "First Message Engine to'xtatishda xatolik."
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

    # Security alertlarni admin(lar)ga yuborish uchun Bot
    # obyektiga referens beriladi.
    set_bot_instance(bot)

    register_routers(dp)

    try:
        # Startup
        await startup(bot)

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