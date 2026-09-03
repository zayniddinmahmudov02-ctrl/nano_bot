import logging
import secrets
import string

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.config import BOT_USERNAME
from app.database import AsyncSessionLocal
from app.database.models import Referral
from app.keyboards.nano import nano_referrals_keyboard
from app.services.user_service import (
    get_user_by_telegram_id,
    get_user_language,
)
from app.texts import t

from ..keyboards.main import main_menu_keyboard
from ..keyboards.referral import (
    referral_back_keyboard,
    referral_keyboard,
    referral_level_keyboard,
    referral_link_keyboard,
)

logger = logging.getLogger(__name__)

router = Router()


def get_referral_level(referral_count: int) -> int:
    if referral_count >= 50:
        return 4

    if referral_count >= 30:
        return 3

    if referral_count >= 10:
        return 2

    return 1


def get_referral_limit(referral_count: int) -> str:
    if referral_count >= 50:
        return "♾ Cheksiz"

    if referral_count >= 30:
        return "20 ta"

    if referral_count >= 10:
        return "10 ta"

    return "3 ta"


def generate_referral_code(length: int = 10) -> str:
    characters = string.ascii_letters + string.digits

    return "".join(
        secrets.choice(characters)
        for _ in range(length)
    )


async def get_or_create_referral(
    session,
    user_id: int,
) -> Referral:
    result = await session.execute(
        select(Referral).where(
            Referral.user_id == user_id
        )
    )

    referral = result.scalar_one_or_none()

    if referral is not None:
        return referral

    while True:
        code = generate_referral_code()

        result = await session.execute(
            select(Referral).where(
                Referral.referral_code == code
            )
        )

        exists = result.scalar_one_or_none()

        if exists is None:
            break

    referral = Referral(
        user_id=user_id,
        referred_by=None,
        referral_code=code,
        referral_count=0,
    )

    session.add(referral)

    await session.flush()

    return referral


async def apply_referral(
    session,
    new_user_id: int,
    referral_code: str,
) -> bool:
    """
    Yangi user uchun referralni bir marta qo‘llaydi.

    new_user_id — users.id.
    referral_code — referal havoladagi kod.
    """

    referral_code = referral_code.strip()

    if not referral_code:
        return False

    result = await session.execute(
        select(Referral).where(
            Referral.referral_code == referral_code
        )
    )

    referrer = result.scalar_one_or_none()

    if referrer is None:
        return False

    # O‘zini o‘zi referal qilishni taqiqlash
    if referrer.user_id == new_user_id:
        return False

    # Yangi foydalanuvchining referral yozuvini topamiz
    result = await session.execute(
        select(Referral).where(
            Referral.user_id == new_user_id
        )
    )

    new_user_referral = result.scalar_one_or_none()

    if new_user_referral is None:
        new_user_referral = Referral(
            user_id=new_user_id,
            referred_by=referrer.user_id,
            referral_code=generate_referral_code(),
            referral_count=0,
        )

        session.add(new_user_referral)

    elif new_user_referral.referred_by is not None:
        # Referral oldin berilgan
        return False

    else:
        new_user_referral.referred_by = (
            referrer.user_id
        )

    # Refererning hisoblagichini oshiramiz
    referrer.referral_count = (
        referrer.referral_count + 1
    )

    await session.flush()

    return True


@router.message(F.text == "👥 Referallar")
async def referral_menu(
    message: Message,
) -> None:
    await message.answer(
        "👥 <b>Referallar</b>\n\n"
        "Do‘stlaringizni Nano-Botga taklif qiling "
        "va qo‘shimcha imkoniyatlarni oching.\n\n"
        "🎁 <b>10 referal</b> → 10 ta avto javob\n"
        "🎁 <b>30 referal</b> → 20 ta avto javob + 2 til\n"
        "🎁 <b>50 referal</b> → cheksiz avto javob + 3 til",
        reply_markup=referral_keyboard(),
    )


@router.message(F.text == "🔗 Referal havolam")
async def referral_link(
    message: Message,
) -> None:
    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            await message.answer(
                "❌ Foydalanuvchi topilmadi.\n\n"
                "Iltimos, /start buyrug‘ini bosing.",
                reply_markup=main_menu_keyboard(),
            )
            return

        referral = await get_or_create_referral(
            session,
            user.id,
        )

        await session.commit()

        code = referral.referral_code
        count = referral.referral_count

    bot_username = BOT_USERNAME.lstrip("@")

    link = (
        f"https://t.me/{bot_username}"
        f"?start=ref_{code}"
    )

    await message.answer(
        "🔗 <b>Sizning referal havolangiz</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"👥 Referallar: <b>{count}</b>\n"
        f"📈 Daraja: <b>{get_referral_level(count)}</b>\n"
        f"📌 Avto javob limiti: "
        f"<b>{get_referral_limit(count)}</b>\n\n"
        "Havolani do‘stlaringizga yuboring.",
        reply_markup=referral_link_keyboard(),
    )


@router.message(F.text == "📊 Referal statistikasi")
async def referral_statistics(
    message: Message,
) -> None:
    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            await message.answer(
                "❌ Foydalanuvchi topilmadi.",
                reply_markup=main_menu_keyboard(),
            )
            return

        referral = await get_or_create_referral(
            session,
            user.id,
        )

        await session.commit()

        count = referral.referral_count

    level = get_referral_level(count)

    if count < 10:
        next_level = 10
    elif count < 30:
        next_level = 30
    elif count < 50:
        next_level = 50
    else:
        next_level = None

    if next_level is None:
        progress = "🏆 Maksimal daraja!"
    else:
        remaining = next_level - count
        progress = (
            f"🎯 Keyingi darajagacha: "
            f"<b>{remaining}</b> ta referal"
        )

    await message.answer(
        "📊 <b>Referal statistikasi</b>\n\n"
        f"👥 Jami referallar: <b>{count}</b>\n"
        f"🏆 Daraja: <b>{level}</b>\n"
        f"📌 Avto javob limiti: "
        f"<b>{get_referral_limit(count)}</b>\n\n"
        f"{progress}",
        reply_markup=referral_link_keyboard(),
    )


@router.message(F.text == "🏆 Darajam")
async def referral_level(
    message: Message,
) -> None:
    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            await message.answer(
                "❌ Foydalanuvchi topilmadi.",
                reply_markup=main_menu_keyboard(),
            )
            return

        referral = await get_or_create_referral(
            session,
            user.id,
        )

        await session.commit()

        count = referral.referral_count

    level = get_referral_level(count)

    if level == 1:
        title = "🥉 Boshlang‘ich"
        requirement = "0–9 referal"
        benefit = "3 ta avto javob"

    elif level == 2:
        title = "🥈 Faol"
        requirement = "10–29 referal"
        benefit = "10 ta avto javob"

    elif level == 3:
        title = "🥇 Kuchli"
        requirement = "30–49 referal"
        benefit = (
            "20 ta avto javob + 2 ta til"
        )

    else:
        title = "💎 Premium daraja"
        requirement = "50+ referal"
        benefit = (
            "♾ Cheksiz avto javob + 3 ta til"
        )

    await message.answer(
        "🏆 <b>Sizning darajangiz</b>\n\n"
        f"{title}\n"
        f"👥 Referallar: <b>{count}</b>\n"
        f"📌 Talab: <b>{requirement}</b>\n"
        f"🎁 Imtiyoz: <b>{benefit}</b>",
        reply_markup=referral_level_keyboard(),
    )


@router.message(F.text == "🏠 Bosh menyu")
async def referral_back(
    message: Message,
) -> None:
    await message.answer(
        "🏠 <b>Bosh menyu</b>",
        reply_markup=main_menu_keyboard(),
    )


# ============================================================
# INLINE ENTRY POINT (Bosh menyu → 👥 Referallar)
# ============================================================
#
# Mavjud referral business logic (get_or_create_referral,
# get_referral_level, get_referral_limit) o'zgarishsiz qayta
# ishlatiladi — faqat taqdim etish (presentation) qatlami
# inline'ga o'tkazildi.

_LEVEL_BENEFITS = {
    1: "3 ta Auto Reply",
    2: "10 ta Auto Reply",
    3: "20 ta Auto Reply + 2 til",
    4: "♾ Cheksiz Auto Reply + 3 til",
}

_LEVEL_THRESHOLDS = {1: "0-9", 2: "10-29", 3: "30-49", 4: "50+"}


async def _safe_edit_referral(
    callback: CallbackQuery,
    text: str,
    reply_markup,
) -> None:
    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
        )
    except Exception:
        try:
            await callback.message.answer(
                text,
                reply_markup=reply_markup,
            )
        except Exception:
            logger.exception(
                "Referal xabarini yangilab bo'lmadi."
            )


async def _render_referrals_text(
    telegram_id: int,
    lang: str,
) -> str:
    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            return t("user_not_found", lang)

        referral = await get_or_create_referral(
            session,
            user.id,
        )

        await session.commit()

        code = referral.referral_code
        count = referral.referral_count

    bot_username = BOT_USERNAME.lstrip("@")
    link = f"https://t.me/{bot_username}?start=ref_{code}"

    current_level = get_referral_level(count)

    level_lines = "\n".join(
        (
            f"{'👉 ' if level == current_level else ''}"
            f"{level}-daraja "
            f"({_LEVEL_THRESHOLDS[level]} referral): "
            f"{_LEVEL_BENEFITS[level]}"
        )
        for level in (1, 2, 3, 4)
    )

    return (
        f"{t('referrals_title', lang)}\n\n"
        f"🔗 Sizning referal havolangiz:\n"
        f"<code>{link}</code>\n\n"
        f"👤 Taklif qilinganlar: <b>{count}</b>\n\n"
        f"🏆 <b>Darajalar:</b>\n{level_lines}\n\n"
        "🎁 <b>Bonuslar:</b>\n"
        "Har bir taklif qilingan foydalanuvchi Auto Reply "
        "limitingizni oshiradi."
    )


@router.message(Command("referrals"))
async def referrals_command(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Telegramning pastki Menu panelidan "/referrals" tanlanganda
    ishga tushadi.
    """

    await state.clear()

    if message.from_user is None:
        return

    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    text = await _render_referrals_text(telegram_id, lang)

    await message.answer(
        text,
        reply_markup=nano_referrals_keyboard(lang),
    )


@router.callback_query(F.data == "nano:referrals")
async def nano_referrals_menu(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    text = await _render_referrals_text(telegram_id, lang)

    await callback.answer()

    await _safe_edit_referral(
        callback,
        text,
        nano_referrals_keyboard(lang),
    )


@router.callback_query(F.data == "nano:referrals:share")
async def nano_referrals_share(
    callback: CallbackQuery,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    text = await _render_referrals_text(telegram_id, lang)

    await callback.answer(
        "🔗 Havolangiz quyida — do'stlaringizga yuboring."
    )

    await _safe_edit_referral(
        callback,
        text,
        nano_referrals_keyboard(lang),
    )


@router.callback_query(F.data == "nano:referrals:stats")
async def nano_referrals_stats(
    callback: CallbackQuery,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        lang = await get_user_language(session, telegram_id)

        if user is None:
            await callback.answer(
                "❌ Foydalanuvchi topilmadi.",
                show_alert=True,
            )
            return

        referral = await get_or_create_referral(
            session,
            user.id,
        )

        await session.commit()

        count = referral.referral_count

    level = get_referral_level(count)

    if count < 10:
        next_level = 10
    elif count < 30:
        next_level = 30
    elif count < 50:
        next_level = 50
    else:
        next_level = None

    if next_level is None:
        progress = "🏆 Maksimal daraja!"
    else:
        remaining = next_level - count
        progress = (
            f"🎯 Keyingi darajagacha: <b>{remaining}</b> ta "
            "referral"
        )

    await callback.answer()

    await _safe_edit_referral(
        callback,
        f"📊 <b>Referal statistikasi</b>\n\n"
        f"👥 Jami referallar: <b>{count}</b>\n"
        f"🏆 Daraja: <b>{level}</b>\n"
        f"📌 Avto javob limiti: "
        f"<b>{get_referral_limit(count)}</b>\n\n"
        f"{progress}",
        nano_referrals_keyboard(lang),
    )


__all__ = [
    "router",
    "get_referral_level",
    "get_referral_limit",
    "get_or_create_referral",
    "apply_referral",
]