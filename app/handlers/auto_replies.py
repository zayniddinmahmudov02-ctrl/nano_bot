import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.database.models import (
    AutoReply,
    AutoReplyKeyword,
    Referral,
    TelegramAccount,
)
from app.keyboards.auto_reply import (
    auto_reply_keyboard,
    auto_reply_media_keyboard,
)
from app.keyboards.main import main_menu_keyboard
from app.services.user_service import get_user_by_telegram_id

logger = logging.getLogger(__name__)

router = Router()


class AutoReplyStates(StatesGroup):
    waiting_keywords = State()
    waiting_message_type = State()
    waiting_message = State()


# ============================================================
# LIMIT
# ============================================================

async def get_auto_reply_limit(
    session,
    user_id: int,
) -> int | None:
    """
    None = unlimited.

    0-9 referrals  -> 3
    10-29           -> 10
    30-49           -> 20
    50+             -> unlimited
    """

    result = await session.execute(
        select(func.coalesce(Referral.referral_count, 0))
        .where(Referral.user_id == user_id)
    )

    referral_count = result.scalar_one()

    if referral_count >= 50:
        return None

    if referral_count >= 30:
        return 20

    if referral_count >= 10:
        return 10

    return 3


# ============================================================
# CONNECTED TELEGRAM ACCOUNT
# ============================================================

async def has_connected_account(
    session,
    user_id: int,
) -> bool:
    result = await session.execute(
        select(TelegramAccount.id)
        .where(
            TelegramAccount.user_id == user_id
        )
        .where(
            TelegramAccount.is_connected.is_(True)
        )
        .limit(1)
    )

    return result.scalar_one_or_none() is not None


# ============================================================
# MENU
# ============================================================

@router.message(F.text == "🤖 Avto javoblar")
async def auto_reply_menu(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "🤖 <b>Avto javoblar</b>\n\n"
        "Bu bo‘lim orqali Telegram akkauntingizga "
        "keladigan xabarlarga avtomatik javob "
        "berishingiz mumkin.",
        reply_markup=auto_reply_keyboard(),
    )


# ============================================================
# ADD
# ============================================================

@router.message(F.text == "➕ Avto javob qo‘shish")
async def add_auto_reply_start(
    message: Message,
    state: FSMContext,
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

        if not await has_connected_account(
            session,
            user.id,
        ):
            await message.answer(
                "❌ Avto javoblardan foydalanish uchun "
                "avval Telegram akkauntingizni ulang.\n\n"
                "📱 «Telegram ulash» bo‘limiga kiring.",
                reply_markup=main_menu_keyboard(),
            )
            return

        limit = await get_auto_reply_limit(
            session,
            user.id,
        )

        result = await session.execute(
            select(func.count(AutoReply.id))
            .where(
                AutoReply.user_id == user.id
            )
        )

        current_count = result.scalar_one()

    if limit is not None and current_count >= limit:
        await message.answer(
            "⚠️ <b>Limitga yetdingiz</b>\n\n"
            f"📊 Hozirgi avto javoblar: "
            f"<b>{current_count}</b>\n"
            f"🔒 Limitingiz: <b>{limit}</b>\n\n"
            "🎁 Ko‘proq referal yig‘ib, "
            "limitingizni oshirishingiz mumkin.",
            reply_markup=auto_reply_keyboard(),
        )
        return

    await state.set_state(
        AutoReplyStates.waiting_keywords
    )

    await message.answer(
        "🔑 <b>Kalit so‘zlarni kiriting</b>\n\n"
        "Bir nechta kalit so‘zni vergul bilan ajrating.\n\n"
        "Masalan:\n"
        "<code>salom, assalomu alaykum, hello</code>",
        reply_markup=auto_reply_keyboard(),
    )


# ============================================================
# KEYWORDS
# ============================================================

@router.message(
    AutoReplyStates.waiting_keywords
)
async def receive_keywords(
    message: Message,
    state: FSMContext,
) -> None:
    if not message.text:
        await message.answer(
            "❌ Kalit so‘zlarni matn ko‘rinishida yuboring."
        )
        return

    raw_keywords = message.text.strip()

    if not raw_keywords:
        await message.answer(
            "❌ Kamida bitta kalit so‘z kiriting."
        )
        return

    keywords = []

    for item in raw_keywords.split(","):
        keyword = item.strip()

        if not keyword:
            continue

        if keyword.casefold() not in {
            existing.casefold()
            for existing in keywords
        }:
            keywords.append(keyword)

    if not keywords:
        await message.answer(
            "❌ Yaroqli kalit so‘z topilmadi."
        )
        return

    if len(keywords) > 20:
        await message.answer(
            "❌ Bir avto javob uchun ko‘pi bilan "
            "<b>20 ta</b> kalit so‘z qo‘shishingiz mumkin."
        )
        return

    await state.update_data(
        keywords=keywords
    )

    await state.set_state(
        AutoReplyStates.waiting_message_type
    )

    await message.answer(
        "📩 <b>Javob turini tanlang:</b>",
        reply_markup=auto_reply_media_keyboard(),
    )


# ============================================================
# MESSAGE TYPE
# ============================================================

@router.message(
    AutoReplyStates.waiting_message_type
)
async def receive_message_type(
    message: Message,
    state: FSMContext,
) -> None:
    type_map = {
        "📝 Matn": "text",
        "🖼 Rasm": "photo",
        "🎥 Video": "video",
        "📄 Hujjat": "document",
        "🔗 Link": "link",
    }

    message_type = type_map.get(
        message.text or ""
    )

    if message_type is None:
        if message.text == "❌ Bekor qilish":
            await state.clear()

            await message.answer(
                "❌ Amal bekor qilindi.",
                reply_markup=auto_reply_keyboard(),
            )
            return

        await message.answer(
            "❌ Iltimos, tugmalardan birini tanlang."
        )
        return

    await state.update_data(
        message_type=message_type
    )

    await state.set_state(
        AutoReplyStates.waiting_message
    )

    instructions = {
        "text": (
            "📝 <b>Javob matnini yuboring:</b>"
        ),
        "photo": (
            "🖼 <b>Rasmni yuboring.</b>\n\n"
            "Rasmga izoh ham qo‘shishingiz mumkin."
        ),
        "video": (
            "🎥 <b>Videoni yuboring.</b>\n\n"
            "Videoga izoh ham qo‘shishingiz mumkin."
        ),
        "document": (
            "📄 <b>Hujjatni yuboring.</b>\n\n"
            "Hujjatga izoh ham qo‘shishingiz mumkin."
        ),
        "link": (
            "🔗 <b>Linkni yuboring:</b>\n\n"
            "Masalan:\n"
            "<code>https://example.com</code>"
        ),
    }

    await message.answer(
        instructions[message_type],
        reply_markup=auto_reply_media_keyboard(),
    )


# ============================================================
# SAVE
# ============================================================

@router.message(
    AutoReplyStates.waiting_message
)
async def receive_message(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    keywords = data.get("keywords", [])
    message_type = data.get("message_type")

    if not keywords or not message_type:
        await state.clear()

        await message.answer(
            "❌ Sessiya ma’lumotlari topilmadi. "
            "Qaytadan boshlang.",
            reply_markup=auto_reply_keyboard(),
        )
        return

    if message.text == "❌ Bekor qilish":
        await state.clear()

        await message.answer(
            "❌ Amal bekor qilindi.",
            reply_markup=auto_reply_keyboard(),
        )
        return

    message_text = None
    file_id = None
    link = None

    # -------------------------
    # TEXT
    # -------------------------

    if message_type == "text":
        if not message.text:
            await message.answer(
                "❌ Matnli javob yuboring."
            )
            return

        message_text = message.text.strip()

        if not message_text:
            await message.answer(
                "❌ Javob matni bo‘sh bo‘lishi mumkin emas."
            )
            return

    # -------------------------
    # PHOTO
    # -------------------------

    elif message_type == "photo":
        if not message.photo:
            await message.answer(
                "❌ Iltimos, rasm yuboring."
            )
            return

        file_id = message.photo[-1].file_id
        message_text = message.caption

    # -------------------------
    # VIDEO
    # -------------------------

    elif message_type == "video":
        if not message.video:
            await message.answer(
                "❌ Iltimos, video yuboring."
            )
            return

        file_id = message.video.file_id
        message_text = message.caption

    # -------------------------
    # DOCUMENT
    # -------------------------

    elif message_type == "document":
        if not message.document:
            await message.answer(
                "❌ Iltimos, hujjat yuboring."
            )
            return

        file_id = message.document.file_id
        message_text = message.caption

    # -------------------------
    # LINK
    # -------------------------

    elif message_type == "link":
        if not message.text:
            await message.answer(
                "❌ Linkni matn ko‘rinishida yuboring."
            )
            return

        link = message.text.strip()

        if not (
            link.startswith("http://")
            or link.startswith("https://")
        ):
            await message.answer(
                "❌ Link <code>http://</code> yoki "
                "<code>https://</code> bilan boshlanishi kerak."
            )
            return

    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            await state.clear()

            await message.answer(
                "❌ Foydalanuvchi topilmadi.",
                reply_markup=main_menu_keyboard(),
            )
            return

        limit = await get_auto_reply_limit(
            session,
            user.id,
        )

        result = await session.execute(
            select(func.count(AutoReply.id))
            .where(
                AutoReply.user_id == user.id
            )
        )

        current_count = result.scalar_one()

        if (
            limit is not None
            and current_count >= limit
        ):
            await state.clear()

            await message.answer(
                "⚠️ Avto javob limiti to‘lib qolgan.",
                reply_markup=auto_reply_keyboard(),
            )
            return

        result = await session.execute(
            select(TelegramAccount)
            .where(
                TelegramAccount.user_id == user.id
            )
            .where(
                TelegramAccount.is_connected.is_(True)
            )
            .order_by(
                TelegramAccount.id.asc()
            )
            .limit(1)
        )

        account = result.scalar_one_or_none()

        auto_reply = AutoReply(
            user_id=user.id,
            telegram_account_id=(
                account.id
                if account is not None
                else None
            ),
            title=(
                keywords[0][:100]
                if keywords
                else "Auto Reply"
            ),
            message_type=message_type,
            message_text=message_text,
            file_id=file_id,
            link=link,
            is_active=True,
        )

        session.add(auto_reply)

        await session.flush()

        for keyword_text in keywords:
            keyword = AutoReplyKeyword(
                auto_reply_id=auto_reply.id,
                keyword=keyword_text,
            )

            session.add(keyword)

        await session.commit()

        auto_reply_id = auto_reply.id

    await state.clear()

    logger.info(
        "Auto reply created: "
        "telegram_id=%s, db_user_id=%s, auto_reply_id=%s",
        telegram_id,
        user.id,
        auto_reply_id,
    )

    await message.answer(
        "✅ <b>Avto javob yaratildi!</b>\n\n"
        f"🔑 Kalit so‘zlar: "
        f"<b>{', '.join(keywords)}</b>\n"
        f"📩 Javob turi: "
        f"<b>{message_type}</b>\n"
        "🟢 Holat: <b>Faol</b>\n\n"
        "Endi mos keladigan xabar kelganda "
        "avtomatik javob yuboriladi.",
        reply_markup=auto_reply_keyboard(),
    )


# ============================================================
# LIST
# ============================================================

@router.message(F.text == "📋 Avto javoblarim")
async def list_auto_replies(
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

        result = await session.execute(
            select(AutoReply)
            .where(
                AutoReply.user_id == user.id
            )
            .order_by(
                AutoReply.id.desc()
            )
        )

        auto_replies = result.scalars().all()

        if not auto_replies:
            await message.answer(
                "📋 <b>Avto javoblaringiz</b>\n\n"
                "Hozircha avto javoblar mavjud emas.\n\n"
                "➕ Yangi avto javob qo‘shishingiz mumkin.",
                reply_markup=auto_reply_keyboard(),
            )
            return

        lines = [
            "📋 <b>Avto javoblaringiz</b>\n"
        ]

        for index, auto_reply in enumerate(
            auto_replies,
            start=1,
        ):
            keyword_result = await session.execute(
                select(AutoReplyKeyword.keyword)
                .where(
                    AutoReplyKeyword.auto_reply_id
                    == auto_reply.id
                )
            )

            keywords = (
                keyword_result.scalars().all()
            )

            status = (
                "🟢 Faol"
                if auto_reply.is_active
                else "🔴 O‘chiq"
            )

            keyword_text = (
                ", ".join(keywords)
                if keywords
                else "—"
            )

            lines.append(
                f"<b>{index}.</b> "
                f"{status}\n"
                f"🔑 {keyword_text}\n"
                f"📩 {auto_reply.message_type}\n"
            )

        text = "\n".join(lines)

    await message.answer(
        text,
        reply_markup=auto_reply_keyboard(),
    )


# ============================================================
# CANCEL
# ============================================================

@router.message(F.text == "❌ Bekor qilish")
async def cancel_auto_reply(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "❌ Amal bekor qilindi.",
        reply_markup=auto_reply_keyboard(),
    )


# ============================================================
# HOME
# ============================================================

@router.message(F.text == "🏠 Bosh menyu")
async def auto_reply_home(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "🏠 <b>Bosh menyu</b>",
        reply_markup=main_menu_keyboard(),
    )


__all__ = [
    "router",
    "AutoReplyStates",
    "get_auto_reply_limit",
]