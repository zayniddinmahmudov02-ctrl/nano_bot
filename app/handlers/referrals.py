import logging
import secrets
import string

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import func, select

from app.config import BOT_USERNAME
from app.database import AsyncSessionLocal
from app.database.models import Referral, User
from app.keyboards.main import main_menu_keyboard
from app.keyboards.referral import referral_keyboard

logger = logging.getLogger(__name__)

router = Router()


# =========================================================
# REFERRAL LIMITS
# =========================================================

def get_auto_reply_limit(
    referral_count: int,
) -> int | None:
    """
    Referral soniga qarab AutoReply limitini qaytaradi.

    0-9   -> 3
    10-29 -> 10
    30-49 -> 20
    50+   -> None = cheksiz
    """

    if referral_count >= 50:
        return None

    if referral_count >= 30:
        return 20

    if referral_count >= 10:
        return 10

    return 3


def get_language_limit(
    referral_count: int,
) -> int:
    """
    Referral soniga qarab ruxsat etilgan tillar soni.

    0-29  -> 1 til
    30-49 -> 2 til
    50+   -> 3 til
    """

    if referral_count >= 50:
        return 3

    if referral_count >= 30:
        return 2

    return 1


def get_referral_level(
    referral_count: int,
) -> str:

    if referral_count >= 50:
        return "💎 Premium daraja"

    if referral_count >= 30:
        return "🥇 30+ referral"

    if referral_count >= 10:
        return "🥈 10+ referral"

    return "🥉 Boshlang‘ich"


# =========================================================
# REFERRAL CODE
# =========================================================

def generate_referral_code(
    length: int = 10,
) -> str:

    alphabet = (
        string.ascii_letters
        + string.digits
    )

    return "".join(
        secrets.choice(alphabet)
        for _ in range(length)
    )


async def get_or_create_referral(
    user_id: int,
) -> Referral:

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(Referral).where(
                Referral.user_id == user_id
            )
        )

        referral = (
            result.scalar_one_or_none()
        )

        if referral:
            return referral

        while True:

            code = generate_referral_code()

            exists = await session.execute(
                select(Referral).where(
                    Referral.referral_code == code
                )
            )

            if not exists.scalar_one_or_none():
                break

        referral = Referral(
            user_id=user_id,
            referral_code=code,
            referral_count=0,
            referred_by=None,
        )

        session.add(referral)

        await session.commit()

        await session.refresh(
            referral
        )

        return referral


# =========================================================
# APPLY REFERRAL
# =========================================================

async def apply_referral(
    new_user_id: int,
    referral_code: str | None,
) -> bool:
    """
    Yangi user referral orqali kelgan bo‘lsa,
    referral countni oshiradi.

    True = referral muvaffaqiyatli qo‘llandi.
    False = qo‘llanmadi.
    """

    if not referral_code:
        return False

    referral_code = (
        referral_code.strip()
    )

    if not referral_code:
        return False

    async with AsyncSessionLocal() as session:

        new_user_result = await session.execute(
            select(User).where(
                User.id == new_user_id
            )
        )

        new_user = (
            new_user_result.scalar_one_or_none()
        )

        if not new_user:
            return False

        referral_result = await session.execute(
            select(Referral).where(
                Referral.referral_code
                == referral_code
            )
        )

        referrer_referral = (
            referral_result.scalar_one_or_none()
        )

        if not referrer_referral:
            return False

        # O'zini o'zi referral qilishga yo'l yo'q.
        if (
            referrer_referral.user_id
            == new_user_id
        ):
            return False

        # Yangi userning referral yozuvi
        # allaqachon mavjud bo'lsa, qayta
        # referral hisoblanmaydi.
        existing_result = await session.execute(
            select(Referral).where(
                Referral.user_id
                == new_user_id
            )
        )

        new_referral = (
            existing_result.scalar_one_or_none()
        )

        if new_referral:
            if new_referral.referred_by:
                return False

            new_referral.referred_by = (
                referrer_referral.user_id
            )

        else:
            code = generate_referral_code()

            while True:
                exists = await session.execute(
                    select(Referral).where(
                        Referral.referral_code
                        == code
                    )
                )

                if not exists.scalar_one_or_none():
                    break

                code = generate_referral_code()

            new_referral = Referral(
                user_id=new_user_id,
                referred_by=(
                    referrer_referral.user_id
                ),
                referral_code=code,
                referral_count=0,
            )

            session.add(new_referral)

        referrer_referral.referral_count += 1

        await session.commit()

    logger.info(
        "Referral applied: new_user=%s referrer=%s",
        new_user_id,
        referrer_referral.user_id,
    )

    return True


# =========================================================
# MAIN REFERRAL MENU
# =========================================================

@router.message(F.text == "👥 Referallar")
async def referrals_menu(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    user_id = message.from_user.id

    referral = await get_or_create_referral(
        user_id
    )

    count = referral.referral_count

    limit = get_auto_reply_limit(
        count
    )

    language_limit = get_language_limit(
        count
    )

    level = get_referral_level(
        count
    )

    if limit is None:
        limit_text = "♾️ Cheksiz"
    else:
        limit_text = str(limit)

    await message.answer(
        "👥 <b>Referallar</b>\n\n"
        f"👤 Sizning referallaringiz: "
        f"<b>{count}</b>\n"
        f"🏆 Daraja: <b>{level}</b>\n\n"
        f"🤖 Avto xabar limiti: "
        f"<b>{limit_text}</b>\n"
        f"🌐 Til limiti: "
        f"<b>{language_limit} ta</b>\n\n"
        "🎯 <b>Darajalar:</b>\n"
        "0–9 → 3 ta avto xabar\n"
        "10 → 10 ta avto xabar\n"
        "30 → 20 ta + 2 til\n"
        "50 → ♾️ + 3 til",
        reply_markup=referral_keyboard(),
    )


# =========================================================
# REFERRAL LINK
# =========================================================

@router.message(
    F.text == "🔗 Referal havolam"
)
async def referral_link(
    message: Message,
) -> None:

    user_id = message.from_user.id

    referral = await get_or_create_referral(
        user_id
    )

    username = BOT_USERNAME

    if username:
        username = username.lstrip("@")
    else:
        username = "nano_go_bot"

    link = (
        f"https://t.me/{username}"
        f"?start=ref_{referral.referral_code}"
    )

    await message.answer(
        "🔗 <b>Sizning referal havolangiz:</b>\n\n"
        f"<code>{link}</code>\n\n"
        "Do‘stlaringiz shu havola orqali "
        "Nano-Botga kirsa, referalingizga "
        "qo‘shiladi."
    )


# =========================================================
# REFERRAL LEVEL
# =========================================================

@router.message(
    F.text == "🏆 Referal darajam"
)
async def referral_level(
    message: Message,
) -> None:

    user_id = message.from_user.id

    referral = await get_or_create_referral(
        user_id
    )

    count = referral.referral_count

    limit = get_auto_reply_limit(
        count
    )

    language_limit = get_language_limit(
        count
    )

    if limit is None:
        limit_text = "♾️ Cheksiz"
    else:
        limit_text = str(limit)

    if count < 10:
        next_goal = (
            f"Yana {10 - count} ta referral → "
            "10 ta avto xabar"
        )

    elif count < 30:
        next_goal = (
            f"Yana {30 - count} ta referral → "
            "20 ta avto xabar + 2 til"
        )

    elif count < 50:
        next_goal = (
            f"Yana {50 - count} ta referral → "
            "♾️ avto xabar + 3 til"
        )

    else:
        next_goal = (
            "🎉 Siz maksimal referral darajasiga "
            "yetdingiz!"
        )

    await message.answer(
        "🏆 <b>Referal darajangiz</b>\n\n"
        f"👥 Referral: <b>{count}</b>\n"
        f"🤖 Avto xabar: "
        f"<b>{limit_text}</b>\n"
        f"🌐 Til: <b>{language_limit} ta</b>\n\n"
        f"🎯 {next_goal}",
        reply_markup=referral_keyboard(),
    )


# =========================================================
# BACK
# =========================================================

@router.message(F.text == "⬅️ Orqaga")
async def referral_back(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    await message.answer(
        "🏠 <b>Asosiy menyu</b>",
        reply_markup=main_menu_keyboard(),
    )