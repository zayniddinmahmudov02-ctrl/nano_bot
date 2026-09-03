import logging
from typing import Optional, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import delete, func, select

from app.database import AsyncSessionLocal
from app.database.models import (
    AutoReply,
    AutoReplyKeyword,
    Referral,
    TelegramAccount,
)
from app.keyboards.auto_reply import (
    auto_reply_cancel_keyboard,
    auto_reply_delete_confirm_keyboard,
    auto_reply_detail_inline_keyboard,
    auto_reply_edit_cancel_inline_keyboard,
    auto_reply_edit_menu_keyboard,
    auto_reply_keyboard,
    auto_reply_list_inline_keyboard,
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
    waiting_edit_keywords = State()
    waiting_edit_reply_post = State()


MESSAGE_TYPE_LABELS = {
    "text": "📝 Matn",
    "photo": "🖼 Rasm",
    "video": "🎥 Video",
    "document": "📄 Hujjat",
    "link": "🔗 Link",
}


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
# OWNERSHIP + RENDER HELPERS
# ============================================================

async def _get_owned_auto_reply(
    session,
    telegram_id: int,
    auto_reply_id: int,
):
    """
    auto_reply_id berilgan foydalanuvchiga tegishli ekanligini
    tekshiradi.

    MUHIM (ownership check):
    Agar Auto Reply boshqa foydalanuvchiga tegishli bo'lsa yoki
    umuman mavjud bo'lmasa — ikkala holatda ham xuddi shu
    (user, None) natijasi qaytariladi, shunday qilib callback_data
    orqali boshqa userning ID'sini "sinab ko'rish" imkonsiz bo'ladi.
    """

    user = await get_user_by_telegram_id(session, telegram_id)

    if user is None:
        return None, None

    result = await session.execute(
        select(AutoReply).where(
            AutoReply.id == auto_reply_id,
            AutoReply.user_id == user.id,
        )
    )

    return user, result.scalar_one_or_none()


def _build_preview_text(auto_reply: AutoReply) -> str:
    if auto_reply.message_type == "text":
        preview = auto_reply.message_text or "—"
    else:
        type_label = MESSAGE_TYPE_LABELS.get(
            auto_reply.message_type,
            auto_reply.message_type,
        )

        # MUHIM: haqiqiy media faylning o'zi bu yerda hech
        # qachon ko'rsatilmaydi/yuklab olinmaydi — bot Storage
        # Channel'ga a'zo emas (ataylab shunday arxitektura
        # tanlangan). Faqat matnli preview ko'rsatiladi.
        preview = f"[{type_label} saqlangan]"

        if auto_reply.message_text:
            preview += f"\n{auto_reply.message_text}"

    if len(preview) > 300:
        preview = preview[:300] + "…"

    return preview


async def _render_detail_text(
    session,
    auto_reply: AutoReply,
) -> str:
    keyword_result = await session.execute(
        select(AutoReplyKeyword.keyword).where(
            AutoReplyKeyword.auto_reply_id == auto_reply.id
        )
    )

    keywords = keyword_result.scalars().all()
    keyword_text = ", ".join(keywords) if keywords else "—"

    status = (
        "🟢 Faol" if auto_reply.is_active else "🔴 O‘chirilgan"
    )

    preview = _build_preview_text(auto_reply)

    return (
        f"📩 <b>Avto xabar #{auto_reply.id}</b>\n\n"
        f"{status}\n\n"
        f"🔑 <b>Kalit so‘zlar:</b>\n"
        f"{keyword_text}\n\n"
        f"📨 <b>Javob:</b>\n"
        f"{preview}"
    )


async def _render_list(
    session,
    user_id: int,
) -> Tuple[str, Optional[list]]:
    result = await session.execute(
        select(AutoReply.id)
        .where(AutoReply.user_id == user_id)
        .order_by(AutoReply.id.asc())
    )

    auto_reply_ids = result.scalars().all()

    if not auto_reply_ids:
        return (
            "📋 <b>Avto javoblaringiz</b>\n\n"
            "Hozircha avto javoblar mavjud emas.\n\n"
            "➕ Yangi avto javob qo‘shishingiz mumkin.",
            None,
        )

    indexed_ids = list(
        enumerate(auto_reply_ids, start=1)
    )

    text = (
        "📋 <b>Avto javoblaringiz</b>\n\n"
        "Kerakli avto javobni tanlang:"
    )

    return text, indexed_ids


async def _safe_edit(
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
                "Auto Reply xabarini yangilab bo'lmadi."
            )


def _parse_callback_id(
    data: str,
) -> Optional[int]:
    try:
        return int(data.split(":")[-1])
    except (IndexError, ValueError):
        return None


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
# LIST (INLINE)
# ============================================================

@router.message(F.text == "📋 Avto javoblarim")
async def list_auto_replies(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

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

        text, indexed_ids = await _render_list(
            session,
            user.id,
        )

    keyboard = (
        auto_reply_list_inline_keyboard(indexed_ids)
        if indexed_ids
        else None
    )

    await message.answer(
        text,
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "ar:list")
async def ar_back_to_list(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            await callback.answer(
                "❌ Foydalanuvchi topilmadi.",
                show_alert=True,
            )
            return

        text, indexed_ids = await _render_list(
            session,
            user.id,
        )

    await callback.answer()

    keyboard = (
        auto_reply_list_inline_keyboard(indexed_ids)
        if indexed_ids
        else None
    )

    await _safe_edit(callback, text, keyboard)


# ============================================================
# DETAIL (INLINE)
# ============================================================

@router.callback_query(F.data.startswith("ar:view:"))
async def ar_view_detail(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    if callback.from_user is None:
        await callback.answer()
        return

    auto_reply_id = _parse_callback_id(callback.data)

    if auto_reply_id is None:
        await callback.answer(
            "❌ Xatolik.",
            show_alert=True,
        )
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        user, auto_reply = await _get_owned_auto_reply(
            session,
            telegram_id,
            auto_reply_id,
        )

        if user is None:
            await callback.answer(
                "❌ Foydalanuvchi topilmadi.",
                show_alert=True,
            )
            return

        if auto_reply is None:
            await callback.answer(
                "❌ Avto javob topilmadi.",
                show_alert=True,
            )
            return

        text = await _render_detail_text(
            session,
            auto_reply,
        )

        is_active = auto_reply.is_active

    await callback.answer()

    await _safe_edit(
        callback,
        text,
        auto_reply_detail_inline_keyboard(
            auto_reply_id,
            is_active,
        ),
    )


# ============================================================
# TOGGLE (FAOL / O'CHIRILGAN)
# ============================================================

@router.callback_query(F.data.startswith("ar:toggle:"))
async def ar_toggle(
    callback: CallbackQuery,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    auto_reply_id = _parse_callback_id(callback.data)

    if auto_reply_id is None:
        await callback.answer(
            "❌ Xatolik.",
            show_alert=True,
        )
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        user, auto_reply = await _get_owned_auto_reply(
            session,
            telegram_id,
            auto_reply_id,
        )

        if user is None or auto_reply is None:
            await callback.answer(
                "❌ Avto javob topilmadi.",
                show_alert=True,
            )
            return

        auto_reply.is_active = not auto_reply.is_active

        await session.commit()

        is_active = auto_reply.is_active

        text = await _render_detail_text(
            session,
            auto_reply,
        )

    await callback.answer(
        "🟢 Yoqildi." if is_active else "🔴 O‘chirildi."
    )

    await _safe_edit(
        callback,
        text,
        auto_reply_detail_inline_keyboard(
            auto_reply_id,
            is_active,
        ),
    )


# ============================================================
# DELETE
# ============================================================

@router.callback_query(F.data.startswith("ar:delete:ask:"))
async def ar_delete_ask(
    callback: CallbackQuery,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    auto_reply_id = _parse_callback_id(callback.data)

    if auto_reply_id is None:
        await callback.answer(
            "❌ Xatolik.",
            show_alert=True,
        )
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        user, auto_reply = await _get_owned_auto_reply(
            session,
            telegram_id,
            auto_reply_id,
        )

        if user is None or auto_reply is None:
            await callback.answer(
                "❌ Avto javob topilmadi.",
                show_alert=True,
            )
            return

    await callback.answer()

    await _safe_edit(
        callback,
        "⚠️ Bu Auto Reply'ni o‘chirishni xohlaysizmi?",
        auto_reply_delete_confirm_keyboard(auto_reply_id),
    )


@router.callback_query(F.data.startswith("ar:delete:no:"))
async def ar_delete_no(
    callback: CallbackQuery,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    auto_reply_id = _parse_callback_id(callback.data)

    if auto_reply_id is None:
        await callback.answer(
            "❌ Xatolik.",
            show_alert=True,
        )
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        user, auto_reply = await _get_owned_auto_reply(
            session,
            telegram_id,
            auto_reply_id,
        )

        if user is None or auto_reply is None:
            await callback.answer(
                "❌ Avto javob topilmadi.",
                show_alert=True,
            )
            return

        text = await _render_detail_text(
            session,
            auto_reply,
        )

        is_active = auto_reply.is_active

    await callback.answer("❌ Bekor qilindi.")

    await _safe_edit(
        callback,
        text,
        auto_reply_detail_inline_keyboard(
            auto_reply_id,
            is_active,
        ),
    )


@router.callback_query(F.data.startswith("ar:delete:yes:"))
async def ar_delete_yes(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    if callback.from_user is None:
        await callback.answer()
        return

    auto_reply_id = _parse_callback_id(callback.data)

    if auto_reply_id is None:
        await callback.answer(
            "❌ Xatolik.",
            show_alert=True,
        )
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        user, auto_reply = await _get_owned_auto_reply(
            session,
            telegram_id,
            auto_reply_id,
        )

        if user is None or auto_reply is None:
            await callback.answer(
                "❌ Avto javob topilmadi.",
                show_alert=True,
            )
            return

        # AutoReplyKeyword yozuvlari DB darajasidagi
        # ON DELETE CASCADE orqali avtomatik o'chadi.
        await session.delete(auto_reply)
        await session.commit()

        text, indexed_ids = await _render_list(
            session,
            user.id,
        )

    logger.info(
        "Auto reply deleted: telegram_id=%s, auto_reply_id=%s",
        telegram_id,
        auto_reply_id,
    )

    await callback.answer("🗑 O‘chirildi.")

    keyboard = (
        auto_reply_list_inline_keyboard(indexed_ids)
        if indexed_ids
        else None
    )

    await _safe_edit(callback, text, keyboard)


# ============================================================
# EDIT MENU
# ============================================================

@router.callback_query(F.data.startswith("ar:edit:menu:"))
async def ar_edit_menu(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    if callback.from_user is None:
        await callback.answer()
        return

    auto_reply_id = _parse_callback_id(callback.data)

    if auto_reply_id is None:
        await callback.answer(
            "❌ Xatolik.",
            show_alert=True,
        )
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        user, auto_reply = await _get_owned_auto_reply(
            session,
            telegram_id,
            auto_reply_id,
        )

        if user is None or auto_reply is None:
            await callback.answer(
                "❌ Avto javob topilmadi.",
                show_alert=True,
            )
            return

    await callback.answer()

    await _safe_edit(
        callback,
        f"✏️ <b>Avto xabar #{auto_reply_id}</b>\n\n"
        "Nimani tahrirlaysiz?",
        auto_reply_edit_menu_keyboard(auto_reply_id),
    )


# ============================================================
# EDIT — KEYWORDS
# ============================================================

@router.callback_query(F.data.startswith("ar:edit:keywords:"))
async def ar_edit_keywords_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    auto_reply_id = _parse_callback_id(callback.data)

    if auto_reply_id is None:
        await callback.answer(
            "❌ Xatolik.",
            show_alert=True,
        )
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        user, auto_reply = await _get_owned_auto_reply(
            session,
            telegram_id,
            auto_reply_id,
        )

        if user is None or auto_reply is None:
            await callback.answer(
                "❌ Avto javob topilmadi.",
                show_alert=True,
            )
            return

    await state.set_state(
        AutoReplyStates.waiting_edit_keywords
    )

    await state.update_data(
        edit_auto_reply_id=auto_reply_id,
        edit_chat_id=callback.message.chat.id,
        edit_message_id=callback.message.message_id,
    )

    await callback.answer()

    await _safe_edit(
        callback,
        "🔑 <b>Yangi kalit so‘zlarni kiriting</b>\n\n"
        "Bir nechta kalit so‘zni vergul bilan ajrating.\n\n"
        "Masalan:\n"
        "<code>salom, assalomu alaykum, hello</code>",
        auto_reply_edit_cancel_inline_keyboard(auto_reply_id),
    )


@router.message(
    AutoReplyStates.waiting_edit_keywords,
    F.text == "❌ Bekor qilish",
)
async def cancel_edit_keywords(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "❌ Tahrirlash bekor qilindi.",
        reply_markup=auto_reply_keyboard(),
    )


@router.message(AutoReplyStates.waiting_edit_keywords)
async def ar_receive_edit_keywords(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    auto_reply_id = data.get("edit_auto_reply_id")
    edit_chat_id = data.get("edit_chat_id")
    edit_message_id = data.get("edit_message_id")

    if not auto_reply_id:
        await state.clear()

        await message.answer(
            "❌ Sessiya ma’lumotlari topilmadi. "
            "Qaytadan boshlang.",
            reply_markup=auto_reply_keyboard(),
        )
        return

    if not message.text:
        await message.answer(
            "❌ Kalit so‘zlarni matn ko‘rinishida yuboring."
        )
        return

    raw_keywords = message.text.strip()

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

    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        user, auto_reply = await _get_owned_auto_reply(
            session,
            telegram_id,
            auto_reply_id,
        )

        if user is None or auto_reply is None:
            await state.clear()

            await message.answer(
                "❌ Avto javob topilmadi.",
                reply_markup=auto_reply_keyboard(),
            )
            return

        await session.execute(
            delete(AutoReplyKeyword).where(
                AutoReplyKeyword.auto_reply_id
                == auto_reply_id
            )
        )

        for keyword_text in keywords:
            session.add(
                AutoReplyKeyword(
                    auto_reply_id=auto_reply_id,
                    keyword=keyword_text,
                )
            )

        auto_reply.title = keywords[0][:100]

        await session.commit()

        detail_text = await _render_detail_text(
            session,
            auto_reply,
        )

        is_active = auto_reply.is_active

    await state.clear()

    await message.answer(
        "✅ Kalit so‘zlar yangilandi.",
        reply_markup=auto_reply_keyboard(),
    )

    if edit_chat_id and edit_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=edit_chat_id,
                message_id=edit_message_id,
                text=detail_text,
                reply_markup=auto_reply_detail_inline_keyboard(
                    auto_reply_id,
                    is_active,
                ),
            )
        except Exception:
            logger.exception(
                "Auto Reply detail xabarini yangilab bo'lmadi."
            )


# ============================================================
# EDIT — JAVOB POSTI
# ============================================================

@router.callback_query(F.data.startswith("ar:edit:post:"))
async def ar_edit_post_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    auto_reply_id = _parse_callback_id(callback.data)

    if auto_reply_id is None:
        await callback.answer(
            "❌ Xatolik.",
            show_alert=True,
        )
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        user, auto_reply = await _get_owned_auto_reply(
            session,
            telegram_id,
            auto_reply_id,
        )

        if user is None or auto_reply is None:
            await callback.answer(
                "❌ Avto javob topilmadi.",
                show_alert=True,
            )
            return

    await state.set_state(
        AutoReplyStates.waiting_edit_reply_post
    )

    await state.update_data(
        edit_auto_reply_id=auto_reply_id,
        edit_chat_id=callback.message.chat.id,
        edit_message_id=callback.message.message_id,
    )

    await callback.answer()

    await _safe_edit(
        callback,
        "📩 <b>Yangi javob postini yuboring</b>\n\n"
        "Matn, rasm, video yoki hujjat yuborishingiz mumkin.\n\n"
        "⚠️ Eski post Nano-Bot Storage kanalida qoladi, "
        "yangisi alohida saqlanadi.",
        auto_reply_edit_cancel_inline_keyboard(auto_reply_id),
    )


@router.message(
    AutoReplyStates.waiting_edit_reply_post,
    F.text == "❌ Bekor qilish",
)
async def cancel_edit_post(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "❌ Tahrirlash bekor qilindi.",
        reply_markup=auto_reply_keyboard(),
    )


@router.message(AutoReplyStates.waiting_edit_reply_post)
async def ar_receive_edit_post(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    auto_reply_id = data.get("edit_auto_reply_id")
    edit_chat_id = data.get("edit_chat_id")
    edit_message_id = data.get("edit_message_id")

    if not auto_reply_id:
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
        user, auto_reply = await _get_owned_auto_reply(
            session,
            telegram_id,
            auto_reply_id,
        )

        if user is None or auto_reply is None:
            await state.clear()

            await message.answer(
                "❌ Avto javob topilmadi.",
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
        user, auto_reply = await _get_owned_auto_reply(
            session,
            telegram_id,
            auto_reply_id,
        )

        if user is None or auto_reply is None:
            await state.clear()

            await message.answer(
                "❌ Avto javob topilmadi.",
                reply_markup=auto_reply_keyboard(),
            )
            return

        # DBda faqat texnik reference saqlanadi — media
        # binary hech qachon PostgreSQL'ga yozilmaydi.
        auto_reply.message_type = message_type
        auto_reply.message_text = text
        auto_reply.storage_chat_id = storage_channel.chat_id
        auto_reply.storage_message_id = storage_message_id

        # Eski (legacy) Bot API file_id/link endi ishlatilmaydi.
        auto_reply.file_id = None
        auto_reply.link = None

        await session.commit()

        detail_text = await _render_detail_text(
            session,
            auto_reply,
        )

        is_active = auto_reply.is_active

    await state.clear()

    logger.info(
        "Auto reply post updated: "
        "telegram_id=%s, auto_reply_id=%s",
        telegram_id,
        auto_reply_id,
    )

    await message.answer(
        "✅ Javob posti yangilandi.",
        reply_markup=auto_reply_keyboard(),
    )

    if edit_chat_id and edit_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=edit_chat_id,
                message_id=edit_message_id,
                text=detail_text,
                reply_markup=auto_reply_detail_inline_keyboard(
                    auto_reply_id,
                    is_active,
                ),
            )
        except Exception:
            logger.exception(
                "Auto Reply detail xabarini yangilab bo'lmadi."
            )


# ============================================================
# EDIT — CANCEL (INLINE)
# ============================================================

@router.callback_query(F.data.startswith("ar:edit:cancel:"))
async def ar_edit_cancel(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    if callback.from_user is None:
        await callback.answer()
        return

    auto_reply_id = _parse_callback_id(callback.data)

    if auto_reply_id is None:
        await callback.answer(
            "❌ Xatolik.",
            show_alert=True,
        )
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        user, auto_reply = await _get_owned_auto_reply(
            session,
            telegram_id,
            auto_reply_id,
        )

        if user is None or auto_reply is None:
            await callback.answer(
                "❌ Avto javob topilmadi.",
                show_alert=True,
            )
            return

        text = await _render_detail_text(
            session,
            auto_reply,
        )

        is_active = auto_reply.is_active

    await callback.answer("❌ Bekor qilindi.")

    await _safe_edit(
        callback,
        text,
        auto_reply_detail_inline_keyboard(
            auto_reply_id,
            is_active,
        ),
    )


# ============================================================
# CANCEL (umumiy — reply keyboard)
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
