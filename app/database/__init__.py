import asyncio
import logging

from app.database.db import create_tables, check_database


logging.basicConfig(level=logging.INFO)


async def main() -> None:
    logging.info("PostgreSQL tekshirilmoqda...")

    if not await check_database():
        raise RuntimeError(
            "PostgreSQL bazasiga ulanib bo'lmadi."
        )

    logging.info("PostgreSQL ulandi.")

    await create_tables()

    logging.info(
        "Nano-Bot database jadvallari yaratildi."
    )


if __name__ == "__main__":
    asyncio.run(main())