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
    User,
    UserSettings,
)
from app.keyboards.nano import nano_main_reply_keyboard
from app.services.activity_service import get_or_create_subscription
from app.services.user_service import (
    get_or_create_user,
    get_user_language,
)
from app.texts import t

logger = logging.getLogger(__name__)

router = Router()


async def initialize_user_data(user: User) -> None:
    """
    Foydalanuvchi uchun kerakli boshlang‘ich ma’lumotlarni yaratadi.

    Quyidagilar yaratiladi:
    - UserSettings
    - Statistics
    - Subscription (Faollik) — YANGI foydalanuvchi uchun shu
      yerda 7 kunlik bepul TRIAL ham avtomatik boshlanadi
      (`activity_service.get_or_create_subscription` orqali,
      faqat qator hali mavjud bo'lmasa — shu sabab qayta-qayta
      trial berilmaydi).
    - Referral (eski, endi UI'da ko'rinmaydigan tizim uchun —
      mavjud ma'lumot tuzilishini buzmaslik uchun saqlanadi)
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

        await session.flush()

        # -------------------------------------------------
        # SUBSCRIPTION (FAOLLIK) + 7 KUNLIK TRIAL
        # -------------------------------------------------

        await get_or_create_subscription(session, user.id)

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

        # MUHIM: Referral tizimi vaqtincha butunlay olib
        # tashlangan (14-bo'lim) — deep link orqali referral
        # qo'llash endi ishlamaydi. Eski DB ma'lumotlari
        # (Referral jadvali) buzilmaydi/o'chirilmaydi, faqat
        # endi hech narsa ularni yangilamaydi.

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