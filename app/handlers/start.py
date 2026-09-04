import logging
from typing import Optional

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import (
    Referral,
    Statistics,
    Subscription,
    User,
    UserSettings,
)
from app.keyboards.nano import nano_main_reply_keyboard
from app.services.user_service import (
    get_or_create_user,
    get_user_language,
)
from app.texts import t

logger = logging.getLogger(__name__)

router = Router()

REFERRAL_DEEP_LINK_PREFIX = "ref_"


def _extract_referral_code(
    payload: Optional[str],
) -> Optional[str]:
    """
    "/start ref_XXXXX" ko'rinishidagi deep link payload'dan
    referral kodini ajratib oladi.
    """

    if not payload:
        return None

    payload = payload.strip()

    if not payload.startswith(REFERRAL_DEEP_LINK_PREFIX):
        return None

    code = payload[len(REFERRAL_DEEP_LINK_PREFIX):].strip()

    return code or None


async def initialize_user_data(user: User) -> None:
    """
    Foydalanuvchi uchun kerakli boshlang‘ich ma’lumotlarni yaratadi.

    Quyidagilar yaratiladi:
    - UserSettings
    - Statistics
    - Subscription
    - Referral
    """

    async with AsyncSessionLocal() as session:

        # -------------------------------------------------
        # USER SETTINGS
        # -------------------------------------------------

        result = await session.execute(
            select(UserSettings).where(
                UserSettings.user_id == user.id
            )
        )

        settings = result.scalar_one_or_none()

        if settings is None:
            settings = UserSettings(
                user_id=user.id,
                language=user.language or "uz",
                notifications_enabled=True,
            )

            session.add(settings)

        # -------------------------------------------------
        # STATISTICS
        # -------------------------------------------------

        result = await session.execute(
            select(Statistics).where(
                Statistics.user_id == user.id
            )
        )

        statistics = result.scalar_one_or_none()

        if statistics is None:
            statistics = Statistics(
                user_id=user.id,
                replied_people=0,
                auto_replies=0,
                first_messages_sent=0,
            )

            session.add(statistics)

        # -------------------------------------------------
        # SUBSCRIPTION
        # -------------------------------------------------

        result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id
            )
        )

        subscription = result.scalar_one_or_none()

        if subscription is None:
            subscription = Subscription(
                user_id=user.id,
                status="free",
            )

            session.add(subscription)

        # -------------------------------------------------
        # REFERRAL
        # -------------------------------------------------

        result = await session.execute(
            select(Referral).where(
                Referral.user_id == user.id
            )
        )

        referral = result.scalar_one_or_none()

        if referral is None:
            referral = Referral(
                user_id=user.id,
                referral_code=f"nano_{user.telegram_id}",
                referral_count=0,
            )

            session.add(referral)

        # -------------------------------------------------
        # SAVE
        # -------------------------------------------------

        await session.commit()


async def process_start(
    message: Message,
    referral_payload: Optional[str] = None,
    state: Optional[FSMContext] = None,
) -> None:
    telegram_user = message.from_user

    if telegram_user is None:
        return

    try:
        # -------------------------------------------------
        # FSM STATE
        # -------------------------------------------------
        # /start har doim asosiy menyuni ochadi — agar
        # foydalanuvchi biror oldingi FSM holatida (masalan
        # parol kiritish, kalit so'z kutish va h.k.) "qotib
        # qolgan" bo'lsa, u tozalanadi.

        if state is not None:
            await state.clear()

        # -------------------------------------------------
        # USER
        # -------------------------------------------------

        async with AsyncSessionLocal() as session:
            user = await get_or_create_user(
                session,
                telegram_user,
            )

            # MUHIM: flush() DB'ga yozadi, lekin commit()
            # qilinmaguncha tranzaksiya rollback bo'lishi
            # mumkin — shu sabab user hech qachon saqlanmay
            # qolib, keyingi FK insertlar (UserSettings va h.k.)
            # xato berishi mumkin edi.
            await session.commit()

        # -------------------------------------------------
        # USER DATA
        # -------------------------------------------------

        await initialize_user_data(user)

        # -------------------------------------------------
        # REFERRAL (deep link: t.me/bot?start=ref_XXXXX)
        # -------------------------------------------------

        referral_code = _extract_referral_code(
            referral_payload
        )

        if referral_code:
            try:
                # Circular importni oldini olish uchun
                # funksiya ichida import qilinadi.
                from app.handlers.referrals import (
                    apply_referral,
                )

                async with AsyncSessionLocal() as session:
                    applied = await apply_referral(
                        session,
                        new_user_id=user.id,
                        referral_code=referral_code,
                    )

                    await session.commit()

                if applied:
                    logger.info(
                        "Referral qo'llandi: new_user_id=%s",
                        user.id,
                    )

            except Exception:
                logger.exception(
                    "Referralni qo'llashda xatolik: "
                    "new_user_id=%s",
                    user.id,
                )

        # -------------------------------------------------
        # QISQA SALOMLASHUV + PASTKI MENU PANELI
        # -------------------------------------------------
        # MUHIM: chatga katta inline "bosh menyu" xabari
        # yuborilmaydi — faqat qisqa matn. Asosiy 5 bo'lim
        # Telegramning o'z PASTKI (Reply) klaviatura panelida
        # ko'rinadi — bu chat ichidagi alohida xabar emas,
        # Telegram interfeysining o'zi.

        async with AsyncSessionLocal() as session:
            lang = await get_user_language(
                session,
                telegram_user.id,
            )

        await message.answer(
            t("welcome_short", lang),
            reply_markup=nano_main_reply_keyboard(lang),
        )

    except Exception:
        logger.exception(
            "Start handlerda xatolik."
        )

        await message.answer(
            "❌ Xatolik yuz berdi.\n\n"
            "Iltimos, birozdan keyin qayta urinib ko‘ring."
        )


@router.message(CommandStart())
async def start_handler(
    message: Message,
    command: CommandObject,
    state: FSMContext,
) -> None:
    await process_start(message, command.args, state)


__all__ = [
    "router",
    "process_start",
    "initialize_user_data",
]