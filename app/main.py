import asyncio
import logging

from app.telegram.bot import (
    create_bot,
    create_dispatcher,
)
from app.handlers import (
    start_router,
    settings_router,
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
    dp = create_dispatcher()

    dp.include_router(start_router)
    dp.include_router(settings_router)

    logging.info("Nano-Bot ishga tushmoqda...")

    try:
        await dp.start_polling(bot)

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())