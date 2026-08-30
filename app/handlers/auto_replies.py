import logging
from typing import Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import delete, select

from app.database import AsyncSessionLocal
from app.database.models import (
    AutoReply,
    AutoReplyKeyword,
    TelegramAccount,
)
from app.keyboards.auto_reply import (
    auto_reply_cancel_keyboard,
    auto_reply_menu_keyboard,
    media_type_keyboard,
)
from app.keyboards.main import main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router()


# =========================================================
# STATES
# =========================================================

class AutoReplyStates(StatesGroup):
    waiting_keywords = State()
    waiting_message = State()


# =========================================================
# HELPERS
# =========================================================

async def get_user_auto_reply_limit(
    user_id: int,
) -> Optional[int]:
    """
    Referral darajasiga qarab avto-javob limitini qaytaradi.

    0-9   -> 3
    10-29 -> 10
    30-49 -> 20
    50+   -> None (cheksiz)
    """

    from app.database.models import Referral

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Referral).where(
                Referral.user_id == user_id
            )
        )

        referral = result.scalar_one_or_none()

    count = (
        referral.referral_count
        if referral
        else 0
    )

    if count >= 50:
        return None

    if count >= 30:
        return 20

    if count >= 10:
        return 10

    return 3


async def get_auto_reply_count(
    user_id: int,
) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AutoReply).where(
                AutoReply.user_id == user_id
            )
        )

        return len(
            result.scalars().all()
        )


async def get_connected_account(
    user_id: int,
) -> Optional[TelegramAccount]:

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TelegramAccount).where(
                TelegramAccount.user_id == user_id,
                TelegramAccount.is_connected.is_(True),
            )
        )

        return result.scalar_one_or_none()


def extract_message_data(
    message: Message,
) -> dict:

    if message.photo:
        return {
            "message_type": "photo",
            "message_text": (
                message.caption
                or ""
            ),
            "file_id": message.photo[-1].file_id,
            "link": None,
        }

    if message.video:
        return {
            "message_type": "video",
            "message_text": (
                message.caption
                or ""
            ),
            "file_id": message.video.file_id,
            "link": None,
        }

    if message.document:
        return {
            "message_type": "document",
            "message_text": (
                message.caption
                or ""
            ),
            "file_id": message.document.file_id,
            "link": None,
        }

    if message.text:
        return {
            "message_type": "text",
            "message_text": message.text,
            "file_id": None,
            "link": None,
        }

    return {
        "message_type": "text",
        "message_text": "",
        "file_id": None,
        "link": None,
    }


# =========================================================
# MAIN MENU
# =========================================================

@router.message(F.text == "🤖 Avto javoblar")
async def auto_reply_menu(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    user_id = message.from_user.id

    count = await get_auto_reply_count(
        user_id
    )

    limit = await get_user_auto_reply_limit(
        user_id
    )

    account = await get_connected_account(
        user_id
    )

    if limit is None:
        limit_text = "♾️ Cheksiz"
    else:
        limit_text = str(limit)

    connection_text = (
        "🟢 Telegram ulangan"
        if account
        else "🔴 Telegram ulanmagan"
    )

    await message.answer(
        "🤖 <b>Avto javoblar</b>\n\n"
        f"📊 Mavjud: <b>{count}</b> / "
        f"<b>{limit_text}</b>\n"
        f"📱 Telegram: <b>{connection_text}</b>\n\n"
        "Kalit so‘zlarga mos avtomatik "
        "javoblarni shu yerda boshqarasiz.",
        reply_markup=auto_reply_menu_keyboard(),
    )


# =========================================================
# ADD AUTO REPLY
# =========================================================

@router.message(
    F.text == "➕ Avto xabar qo‘shish"
)
async def add_auto_reply_start(
    message: Message,
    state: FSMContext,
) -> None:

    user_id = message.from_user.id

    account = await get_connected_account(
        user_id
    )

    if not account:
        await message.answer(
            "❌ <b>Avval Telegram akkauntingizni ulang.</b>\n\n"
            "Avto javoblar sizning shaxsiy "
            "Telegram akkauntingiz orqali ishlaydi."
        )
        return

    count = await get_auto_reply_count(
        user_id
    )

    limit = await get_user_auto_reply_limit(
        user_id
    )

    if limit is not None and count >= limit:
        if limit == 3:
            referral_text = (
                "10 ta referral → 10 ta avto xabar\n"
                "30 ta referral → 20 ta avto xabar\n"
                "50 ta referral → ♾️"
            )
        else:
            referral_text = (
                "Keyingi limit uchun ko‘proq "
                "referral yig‘ing."
            )

        await message.answer(
            "⚠️ <b>Avto xabar limiti tugadi.</b>\n\n"
            f"Joriy limit: <b>{limit}</b>\n\n"
            f"{referral_text}"
        )
        return

    await state.set_state(
        AutoReplyStates.waiting_keywords
    )

    await message.answer(
        "🔑 <b>Kalit so‘zlarni kiriting</b>\n\n"
        "Bir yoki bir nechta kalit so‘z kiriting.\n\n"
        "Masalan:\n"
        "<code>salom, assalomu alaykum, hello</code>\n\n"
        "Kalit so‘zlarni vergul bilan ajrating.",
        reply_markup=auto_reply_cancel_keyboard(),
    )


# =========================================================
# KEYWORDS
# =========================================================

@router.message(
    AutoReplyStates.waiting_keywords,
    F.text == "❌ Bekor qilish",
)
async def cancel_keywords(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    await message.answer(
        "❌ Avto xabar yaratish bekor qilindi.",
        reply_markup=auto_reply_menu_keyboard(),
    )


@router.message(
    AutoReplyStates.waiting_keywords,
    F.text,
)
async def receive_keywords(
    message: Message,
    state: FSMContext,
) -> None:

    raw = message.text.strip()

    keywords = [
        item.strip()
        for item in raw.split(",")
        if item.strip()
    ]

    if not keywords:
        await message.answer(
            "❌ Kamida bitta kalit so‘z kiriting."
        )
        return

    # Duplicate keywordlarni olib tashlash
    unique_keywords = []

    for keyword in keywords:
        normalized = keyword.lower()

        if normalized not in [
            x.lower()
            for x in unique_keywords
        ]:
            unique_keywords.append(
                keyword
            )

    await state.update_data(
        keywords=unique_keywords
    )

    await state.set_state(
        AutoReplyStates.waiting_message
    )

    keyword_text = "\n".join(
        f"• {keyword}"
        for keyword in unique_keywords
    )

    await message.answer(
        "✅ <b>Kalit so‘zlar qabul qilindi.</b>\n\n"
        f"{keyword_text}\n\n"
        "📩 Endi bunga mos <b>avto xabarni</b> yuboring.\n\n"
        "📝 Matn\n"
        "🖼 Rasm\n"
        "🎥 Video\n"
        "📎 Fayl\n"
        "🔗 Link\n\n"
        "Xabarni shu yerga yuboring.",
        reply_markup=auto_reply_cancel_keyboard(),
    )


# =========================================================
# RESPONSE MESSAGE
# =========================================================

@router.message(
    AutoReplyStates.waiting_message,
    F.text == "❌ Bekor qilish",
)
async def cancel_message(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    await message.answer(
        "❌ Avto xabar yaratish bekor qilindi.",
        reply_markup=auto_reply_menu_keyboard(),
    )


@router.message(
    AutoReplyStates.waiting_message,
)
async def receive_auto_reply_message(
    message: Message,
    state: FSMContext,
) -> None:

    user_id = message.from_user.id

    data = await state.get_data()

    keywords = data.get(
        "keywords",
        [],
    )

    if not keywords:
        await state.clear()

        await message.answer(
            "❌ Kalit so‘zlar topilmadi.",
            reply_markup=auto_reply_menu_keyboard(),
        )
        return

    message_data = extract_message_data(
        message
    )

    if (
        message_data["message_type"] == "text"
        and not message_data["message_text"]
    ):
        await message.answer(
            "❌ Iltimos, matn, rasm, video "
            "yoki fayl yuboring."
        )
        return

    account = await get_connected_account(
        user_id
    )

    if not account:
        await state.clear()

        await message.answer(
            "❌ Telegram akkaunt ulanmagan.",
            reply_markup=main_menu_keyboard(),
        )
        return

    async with AsyncSessionLocal() as session:

        auto_reply = AutoReply(
            user_id=user_id,
            telegram_account_id=account.id,
            message_type=message_data[
                "message_type"
            ],
            message_text=message_data[
                "message_text"
            ],
            file_id=message_data[
                "file_id"
            ],
            link=message_data[
                "link"
            ],
            is_active=True,
        )

        session.add(auto_reply)

        await session.flush()

        for keyword in keywords:
            session.add(
                AutoReplyKeyword(
                    auto_reply_id=auto_reply.id,
                    keyword=keyword.strip(),
                )
            )

        await session.commit()

        auto_reply_id = auto_reply.id

    await state.clear()

    keyword_text = ", ".join(
        keywords
    )

    await message.answer(
        "✅ <b>Avto xabar yaratildi!</b>\n\n"
        f"🆔 ID: <code>{auto_reply_id}</code>\n"
        f"🔑 Kalit so‘zlar: <b>{keyword_text}</b>\n"
        f"📩 Tur: <b>{message_data['message_type']}</b>\n"
        "🟢 Holat: <b>Faol</b>",
        reply_markup=auto_reply_menu_keyboard(),
    )


# =========================================================
# LIST
# =========================================================

@router.message(
    F.text == "📋 Avto xabarlarim"
)
async def list_auto_replies(
    message: Message,
) -> None:

    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(AutoReply)
            .where(
                AutoReply.user_id == user_id
            )
            .order_by(
                AutoReply.id.desc()
            )
        )

        replies = result.scalars().all()

        if not replies:
            await message.answer(
                "📭 <b>Avto xabarlar mavjud emas.</b>\n\n"
                "➕ Avto xabar qo‘shish tugmasini "
                "bosib birinchi avtomatik javobingizni yarating.",
                reply_markup=auto_reply_menu_keyboard(),
            )
            return

        texts = [
            "📋 <b>Mening avto xabarlarim</b>\n"
        ]

        for reply in replies:

            keyword_result = await session.execute(
                select(AutoReplyKeyword).where(
                    AutoReplyKeyword.auto_reply_id
                    == reply.id
                )
            )

            keywords = (
                keyword_result.scalars().all()
            )

            keyword_text = ", ".join(
                x.keyword
                for x in keywords
            )

            status = (
                "🟢 Faol"
                if reply.is_active
                else "🔴 O‘chiq"
            )

            texts.append(
                f"\n<b>#{reply.id}</b>\n"
                f"🔑 {keyword_text}\n"
                f"📩 {reply.message_type}\n"
                f"{status}"
            )

        await message.answer(
            "".join(texts),
            reply_markup=auto_reply_menu_keyboard(),
        )


# =========================================================
# DIRECT COMMAND SUPPORT
# =========================================================

@router.message(
    F.text.startswith("/auto")
)
async def auto_reply_command(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    await message.answer(
        "🤖 <b>Avto javoblar</b>\n\n"
        "Quyidagi menyudan foydalaning.",
        reply_markup=auto_reply_menu_keyboard(),
    )