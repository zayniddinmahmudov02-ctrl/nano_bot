import asyncio
import logging

from aiogram.fsm.storage.memory import MemoryStorage

from app.database.db import (
    check_database,
    close_database,
    create_tables,
)

from app.telegram.bot import (
    create_bot,
    create_dispatcher,
)

from app.handlers import (
    start_router,
    telegram_connect_router,
    auto_replies_router,
    first_message_router,
    referrals_router,
    statistics_router,
    premium_router,
    language_router,
    settings_router,
    admin_router,
)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
    )

    logging.info("PostgreSQL tekshirilmoqda...")

    if not await check_database():
        raise RuntimeError(
            "PostgreSQL bazasiga ulanib bo'lmadi."
        )

    logging.info("PostgreSQL ulandi.")

    await create_tables()

    logging.info(
        "Database jadvallari tayyor."
    )

    bot = create_bot()

    dp = create_dispatcher(
        storage=MemoryStorage()
    )

    dp.include_router(start_router)
    dp.include_router(telegram_connect_router)
    dp.include_router(auto_replies_router)
    dp.include_router(first_message_router)
    dp.include_router(referrals_router)
    dp.include_router(statistics_router)
    dp.include_router(premium_router)
    dp.include_router(language_router)
    dp.include_router(settings_router)
    dp.include_router(admin_router)

    logging.info(
        "Nano-Bot ishga tushmoqda..."
    )

    try:
        await dp.start_polling(bot)

    finally:
        await bot.session.close()
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())