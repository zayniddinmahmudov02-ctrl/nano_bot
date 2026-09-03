import logging
from datetime import datetime, timezone

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import User
from app.services.password_service import check_password_attempt
from app.services.user_service import get_user_by_telegram_id
from app.states.password_lock import PasswordLockStates

logger = logging.getLogger(__name__)

router = Router()


@router.message(PasswordLockStates.waiting_password_challenge)
async def receive_password_challenge(
    message: Message,
    state: FSMContext,
) -> None:
    telegram_id = int(message.from_user.id)

    # Foydalanuvchi yuborgan parolni chatdan tozalashga
    # harakat qilamiz (maxfiylik uchun) — muvaffaqiyatsiz
    # bo'lsa ham davom etaveramiz.
    try:
        await message.delete()
    except Exception:
        pass

    if not message.text:
        await message.answer(
            "🔐 Iltimos, parolni matn ko'rinishida kiriting."
        )
        return

    plain_password = message.text.strip()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )

        user = result.scalar_one_or_none()

    if user is None:
        await state.clear()

        await message.answer(
            "❌ Foydalanuvchi topilmadi.\n\n"
            "Iltimos, /start buyrug'ini bosing."
        )
        return

    # MUHIM: kiritilgan parol hech qachon logga yozilmaydi.
    result = await check_password_attempt(
        user.id,
        plain_password,
    )

    if result.ok:
        await state.clear()

        await message.answer(
            "✅ Parol to'g'ri. Davom etishingiz mumkin.\n\n"
            "🏠 Bosh menyuga qaytish uchun /start buyrug'ini "
            "bosing."
        )

        logger.info(
            "Password challenge passed: telegram_id=%s",
            telegram_id,
        )
        return

    if result.locked:
        minutes = 0

        if result.locked_until is not None:
            delta = result.locked_until - datetime.now(
                timezone.utc
            )
            minutes = max(1, int(delta.total_seconds() // 60))

        await message.answer(
            "🚫 <b>Juda ko'p noto'g'ri urinish.</b>\n\n"
            f"Iltimos, {minutes} daqiqadan keyin qayta "
            "urinib ko'ring."
        )

        logger.warning(
            "Password challenge locked out: telegram_id=%s",
            telegram_id,
        )
        return

    remaining = (
        result.attempts_remaining
        if result.attempts_remaining is not None
        else 0
    )

    await message.answer(
        "❌ <b>Parol noto'g'ri.</b>\n\n"
        f"Qolgan urinishlar: {remaining}\n\n"
        "Davom etish uchun parolni qayta kiriting:"
    )

    logger.warning(
        "Password challenge failed: telegram_id=%s",
        telegram_id,
    )


__all__ = [
    "router",
]
