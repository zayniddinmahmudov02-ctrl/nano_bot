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
    auto_reply_cancel_keyboard,
    auto_reply_keyboard,
)
from app.keyboards.main import main_menu_keyboard
from app.services.media_service import (
    detect_post_content,
    send_post_to_storage,
)
from app.services.storage_channel_service import ensure_storage_channel
from app.services.user_service import (
    get_connected_telegram_account,
    get_user_by_telegram_id,
)
from app.telegram.user_client import telegram_client_manager

logger = logging.getLogger(__name__)

router = Router()


class AutoReplyStates(StatesGroup):
    waiting_keywords = State()
    waiting_post = State()


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
        AutoReplyStates.waiting_post
    )

    await message.answer(
        "📩 <b>Yuborilishi kerak bo‘lgan postni joylang</b>\n\n"
        "Auto Reply sifatida yuborilishini xohlagan postni "
        "shu chatga yuboring.\n\n"
        "⚠️ <b>Eslatma:</b>\n"
        "Bot chat tarixidagi xabarlarni doimiy media storage "
        "sifatida ishlatmaydi. Post alohida Nano-Bot Storage "
        "kanalida saqlanadi va kerak bo‘lganda shu kanal orqali "
        "yuboriladi.\n\n"
        "❗ Iltimos, konfiguratsiya jarayonidagi xabarlarni "
        "o‘chirmang.",
        reply_markup=auto_reply_cancel_keyboard(),
    )


# ============================================================
# CANCEL POST
# ============================================================

@router.message(
    AutoReplyStates.waiting_post,
    F.text == "❌ Bekor qilish",
)
async def cancel_post(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "❌ Amal bekor qilindi.",
        reply_markup=auto_reply_keyboard(),
    )


# ============================================================
# SAVE (Auto Reply 2.0 — Storage Channel asosida)
# ============================================================

@router.message(
    AutoReplyStates.waiting_post
)
async def receive_post(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    keywords = data.get("keywords", [])

    if not keywords:
        await state.clear()

        await message.answer(
            "❌ Sessiya ma’lumotlari topilmadi. "
            "Qaytadan boshlang.",
            reply_markup=auto_reply_keyboard(),
        )
        return

    message_type, text, file_id, file_name = (
        detect_post_content(message)
    )

    if message_type is None:
        await message.answer(
            "❌ Qo‘llab-quvvatlanmaydigan post turi.\n\n"
            "Matn, rasm, video yoki hujjat yuboring."
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

        account = await get_connected_telegram_account(
            session,
            user.id,
        )

        if account is None:
            await state.clear()

            await message.answer(
                "❌ Avval Telegram akkauntingizni ulang.\n\n"
                "📱 «Telegram ulash» bo‘limiga kiring.",
                reply_markup=main_menu_keyboard(),
            )
            return

        db_user_id = user.id
        telegram_account_id = account.id

    storage_channel = await ensure_storage_channel(
        telegram_id=telegram_id,
        db_user_id=db_user_id,
        telegram_account_id=telegram_account_id,
    )

    if storage_channel is None:
        await message.answer(
            "❌ Storage kanalni tayyorlashda xatolik yuz berdi.\n\n"
            "Birozdan keyin qayta urinib ko‘ring yoki Telegram "
            "akkauntingizni qayta ulang."
        )
        return

    telethon_client = telegram_client_manager.get_client(
        telegram_id
    )

    if telethon_client is None:
        await message.answer(
            "❌ Telegram akkaunt ulanishi topilmadi.\n\n"
            "Iltimos, akkauntingizni qayta ulang."
        )
        return

    storage_message_id = await send_post_to_storage(
        bot=message.bot,
        telethon_client=telethon_client,
        storage_chat_id=storage_channel.chat_id,
        message_type=message_type,
        text=text,
        file_id=file_id,
        file_name=file_name,
    )

    if storage_message_id is None:
        await message.answer(
            "❌ Postni saqlashda xatolik yuz berdi.\n\n"
            "Qayta urinib ko‘ring."
        )
        return

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

        auto_reply = AutoReply(
            user_id=user.id,
            telegram_account_id=telegram_account_id,
            title=(
                keywords[0][:100]
                if keywords
                else "Auto Reply"
            ),
            message_type=message_type,
            message_text=text,
            storage_chat_id=storage_channel.chat_id,
            storage_message_id=storage_message_id,
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
        db_user_id,
        auto_reply_id,
    )

    await message.answer(
        "✅ <b>Avto javob yaratildi!</b>\n\n"
        f"🔑 Kalit so‘zlar: "
        f"<b>{', '.join(keywords)}</b>\n"
        f"📩 Post turi: "
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