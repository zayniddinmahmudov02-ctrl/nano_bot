async def create_tables() -> None:
    from app.database import models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )