import asyncio
import logging

from aiogram.fsm.storage.memory import MemoryStorage

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

    logging.info("Nano-Bot ishga tushmoqda...")

    try:
        await dp.start_polling(bot)

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())