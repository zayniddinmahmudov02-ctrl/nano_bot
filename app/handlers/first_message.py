import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import FirstMessage
from app.keyboards.first_message import (
    INTERVAL_LABELS,
    first_message_card_keyboard,
    first_message_delete_confirm_keyboard,
    first_message_empty_keyboard,
    first_message_input_cancel_keyboard,
    first_message_interval_keyboard,
)
from app.keyboards.main import main_menu_keyboard
from app.services.media_service import (
    StoragePostTooLarge,
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

INTERVAL_HOUR = 3600
INTERVAL_DAY = 86400

UNSUPPORTED_POST_TYPE_TEXT = (
    "❌ Bu turdagi xabar qo‘llab-quvvatlanmaydi.\n\n"
    "Matn, rasm, video, hujjat, audio, ovozli xabar yoki "
    "GIF yuboring."
)

TOO_LARGE_TEXT = (
    "❌ Fayl juda katta.\n\n"
    "Telegram Bot API orqali yuklab bo‘lmaydigan hajmda "
    "(taxminan 20MB dan katta). Kichikroq fayl yuboring."
)


class FirstMessageStates(StatesGroup):
    waiting_message = State()
    waiting_edit_message = State()


# ============================================================
# RENDER HELPERS
# ============================================================

def _interval_label(seconds: int) -> str:
    return INTERVAL_LABELS.get(seconds, f"{seconds} soniya")


def _render_card_text(first_message: FirstMessage) -> str:
    status = (
        "🟢 Faol" if first_message.active else "🔴 O‘chirilgan"
    )

    preview = (
        first_message.text
        if first_message.text
        else f"[{first_message.message_type} saqlangan]"
    )

    if len(preview) > 300:
        preview = preview[:300] + "…"

    return (
        "1️⃣ <b>Birinchi xabar</b>\n\n"
        f"{status}\n"
        f"📦 Tur: <code>{first_message.message_type}</code>\n"
        f"🔁 Qayta yuborish: "
        f"<b>{_interval_label(first_message.repeat_interval_seconds)}</b>"
        "\n\n"
        f"📨 <b>Xabar:</b>\n{preview}"
    )


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
                "First Message xabarini yangilab bo'lmadi."
            )


# ============================================================
# MAIN CARD
# ============================================================

@router.callback_query(F.data == "nano:agent:first")
async def first_message_card(
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

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        first_message = result.scalar_one_or_none()

    await callback.answer()

    if first_message is None:
        await _safe_edit(
            callback,
            "1️⃣ <b>Birinchi xabar</b>\n\n"
            "Sizda hozircha birinchi xabar sozlanmagan.\n\n"
            "Yangi xabar yarating — u sizga birinchi marta "
            "yozgan foydalanuvchiga avtomatik yuboriladi.",
            first_message_empty_keyboard(),
        )
        return

    await _safe_edit(
        callback,
        _render_card_text(first_message),
        first_message_card_keyboard(first_message.active),
    )


# ============================================================
# CREATE
# ============================================================

@router.callback_query(F.data == "nano:agent:first:create")
async def first_message_create_start(
    callback: CallbackQuery,
    state: FSMContext,
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

        if user is None:
            await callback.answer(
                "❌ Foydalanuvchi topilmadi.",
                show_alert=True,
            )
            return

        account = await get_connected_telegram_account(
            session,
            user.id,
        )

        if account is None:
            await callback.answer(
                "❌ Avval Telegram akkauntingizni ulang.",
                show_alert=True,
            )
            return

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        existing = result.scalar_one_or_none()

    if existing:
        await callback.answer(
            "⚠️ Birinchi xabar allaqachon mavjud.",
            show_alert=True,
        )
        return

    await state.set_state(FirstMessageStates.waiting_message)

    await state.update_data(
        fm_chat_id=callback.message.chat.id,
        fm_message_id=callback.message.message_id,
    )

    await callback.answer()

    await _safe_edit(
        callback,
        "📩 <b>Birinchi xabarni yuboring</b>\n\n"
        "Matn, rasm, video yoki hujjat yuborishingiz mumkin.\n\n"
        "Bu xabar sizning Telegram akkauntingizga birinchi "
        "marta yozgan foydalanuvchiga yuboriladi.\n\n"
        "⚠️ <b>Eslatma:</b>\n"
        "Post alohida Nano-Bot Storage kanalida saqlanadi va "
        "kerak bo‘lganda shu kanal orqali yuboriladi.\n\n"
        "❗ Iltimos, konfiguratsiya jarayonidagi xabarlarni "
        "o‘chirmang.",
        first_message_input_cancel_keyboard(),
    )


@router.callback_query(F.data == "nano:agent:first:cancel")
async def first_message_cancel_input(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    await callback.answer("❌ Bekor qilindi.")

    await first_message_card(callback, state)


@router.message(FirstMessageStates.waiting_message)
async def receive_first_message(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    fm_chat_id = data.get("fm_chat_id")
    fm_message_id = data.get("fm_message_id")

    message_type, text, file_id, file_name = (
        detect_post_content(message)
    )

    if message_type is None:
        await message.answer(UNSUPPORTED_POST_TYPE_TEXT)
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

        account = await get_connected_telegram_account(
            session,
            user.id,
        )

        if account is None:
            await state.clear()

            await message.answer(
                "❌ Avval Telegram akkauntingizni ulang."
            )
            return

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        existing = result.scalar_one_or_none()

        if existing:
            await state.clear()

            await message.answer(
                "⚠️ Birinchi xabar allaqachon mavjud."
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
            "Birozdan keyin qayta urinib ko‘ring."
        )
        return

    telethon_client = telegram_client_manager.get_client(
        telegram_id
    )

    if telethon_client is None:
        await message.answer(
            "❌ Telegram akkaunt ulanishi topilmadi."
        )
        return

    try:
        storage_message_id = await send_post_to_storage(
            bot=message.bot,
            telethon_client=telethon_client,
            storage_chat_id=storage_channel.chat_id,
            message_type=message_type,
            text=text,
            file_id=file_id,
            file_name=file_name,
        )
    except StoragePostTooLarge:
        await state.clear()
        await message.answer(TOO_LARGE_TEXT)
        return

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

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        existing = result.scalar_one_or_none()

        if existing:
            await state.clear()

            await message.answer(
                "⚠️ Birinchi xabar allaqachon mavjud."
            )
            return

        first_message = FirstMessage(
            user_id=user.id,
            message_type=message_type,
            text=text,
            link=None,
            storage_chat_id=storage_channel.chat_id,
            storage_message_id=storage_message_id,
            repeat_interval_seconds=INTERVAL_HOUR,
            active=True,
        )

        session.add(first_message)

        await session.commit()
        await session.refresh(first_message)

        card_text = _render_card_text(first_message)
        is_active = first_message.active

    await state.clear()

    await message.answer("✅ Birinchi xabar yaratildi!")

    if fm_chat_id and fm_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=fm_chat_id,
                message_id=fm_message_id,
                text=card_text,
                reply_markup=first_message_card_keyboard(
                    is_active
                ),
            )
        except Exception:
            logger.exception(
                "First Message kartasini yangilab bo'lmadi."
            )


# ============================================================
# EDIT
# ============================================================

@router.callback_query(F.data == "nano:agent:first:edit")
async def first_message_edit_start(
    callback: CallbackQuery,
    state: FSMContext,
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

        if user is None:
            await callback.answer(
                "❌ Foydalanuvchi topilmadi.",
                show_alert=True,
            )
            return

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        existing = result.scalar_one_or_none()

    if existing is None:
        await callback.answer(
            "❌ Birinchi xabar hali yaratilmagan.",
            show_alert=True,
        )
        return

    await state.set_state(
        FirstMessageStates.waiting_edit_message
    )

    await state.update_data(
        fm_chat_id=callback.message.chat.id,
        fm_message_id=callback.message.message_id,
    )

    await callback.answer()

    await _safe_edit(
        callback,
        "✏️ <b>Yangi birinchi xabarni yuboring.</b>\n\n"
        "Eski xabar yangi xabar bilan almashtiriladi.\n\n"
        "Matn, rasm, video yoki hujjat yuborishingiz mumkin.",
        first_message_input_cancel_keyboard(),
    )


@router.message(FirstMessageStates.waiting_edit_message)
async def receive_edit_first_message(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    fm_chat_id = data.get("fm_chat_id")
    fm_message_id = data.get("fm_message_id")

    message_type, text, file_id, file_name = (
        detect_post_content(message)
    )

    if message_type is None:
        await message.answer(UNSUPPORTED_POST_TYPE_TEXT)
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

        account = await get_connected_telegram_account(
            session,
            user.id,
        )

        if account is None:
            await state.clear()

            await message.answer(
                "❌ Avval Telegram akkauntingizni ulang."
            )
            return

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        first_message = result.scalar_one_or_none()

        if first_message is None:
            await state.clear()

            await message.answer(
                "❌ Birinchi xabar topilmadi."
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
            "❌ Storage kanalni tayyorlashda xatolik yuz berdi."
        )
        return

    telethon_client = telegram_client_manager.get_client(
        telegram_id
    )

    if telethon_client is None:
        await message.answer(
            "❌ Telegram akkaunt ulanishi topilmadi."
        )
        return

    try:
        storage_message_id = await send_post_to_storage(
            bot=message.bot,
            telethon_client=telethon_client,
            storage_chat_id=storage_channel.chat_id,
            message_type=message_type,
            text=text,
            file_id=file_id,
            file_name=file_name,
        )
    except StoragePostTooLarge:
        await state.clear()
        await message.answer(TOO_LARGE_TEXT)
        return

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

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        first_message = result.scalar_one_or_none()

        if first_message is None:
            await state.clear()

            await message.answer(
                "❌ Birinchi xabar topilmadi."
            )
            return

        first_message.message_type = message_type
        first_message.text = text
        first_message.file_id = None
        first_message.link = None
        first_message.storage_chat_id = storage_channel.chat_id
        first_message.storage_message_id = storage_message_id

        await session.commit()

        card_text = _render_card_text(first_message)
        is_active = first_message.active

    await state.clear()

    await message.answer("✅ Birinchi xabar yangilandi!")

    if fm_chat_id and fm_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=fm_chat_id,
                message_id=fm_message_id,
                text=card_text,
                reply_markup=first_message_card_keyboard(
                    is_active
                ),
            )
        except Exception:
            logger.exception(
                "First Message kartasini yangilab bo'lmadi."
            )


# ============================================================
# INTERVAL
# ============================================================

@router.callback_query(F.data == "nano:agent:first:interval")
async def first_message_interval_menu(
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

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        first_message = result.scalar_one_or_none()

    if first_message is None:
        await callback.answer(
            "❌ Avval birinchi xabar yarating.",
            show_alert=True,
        )
        return

    await callback.answer()

    current_label = _interval_label(
        first_message.repeat_interval_seconds
    )

    await _safe_edit(
        callback,
        "⏱ <b>Qayta yuborish vaqti</b>\n\n"
        f"Hozirgi tanlov: <b>{current_label}</b>\n\n"
        "Bir kontaktga qachon qayta yuborilishini tanlang:",
        first_message_interval_keyboard(),
    )


@router.callback_query(
    F.data.startswith("nano:agent:first:interval:set:")
)
async def set_first_message_interval(
    callback: CallbackQuery,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    try:
        interval_seconds = int(callback.data.split(":")[-1])
    except (IndexError, ValueError):
        await callback.answer(
            "❌ Noto‘g‘ri tanlov.",
            show_alert=True,
        )
        return

    if interval_seconds not in INTERVAL_LABELS:
        await callback.answer(
            "❌ Noto‘g‘ri tanlov.",
            show_alert=True,
        )
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

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        first_message = result.scalar_one_or_none()

        if first_message is None:
            await callback.answer(
                "❌ Birinchi xabar topilmadi.",
                show_alert=True,
            )
            return

        first_message.repeat_interval_seconds = interval_seconds

        await session.commit()

    label = INTERVAL_LABELS[interval_seconds]

    await callback.answer("✅ Saqlandi")

    await _safe_edit(
        callback,
        "⏱ <b>Qayta yuborish vaqti</b>\n\n"
        f"✅ Saqlandi: <b>{label}</b>",
        first_message_interval_keyboard(),
    )


# ============================================================
# TOGGLE
# ============================================================

@router.callback_query(F.data == "nano:agent:first:toggle")
async def toggle_first_message(
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

        if user is None:
            await callback.answer(
                "❌ Foydalanuvchi topilmadi.",
                show_alert=True,
            )
            return

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        first_message = result.scalar_one_or_none()

        if first_message is None:
            await callback.answer(
                "❌ Avval birinchi xabar yarating.",
                show_alert=True,
            )
            return

        first_message.active = not first_message.active

        await session.commit()

        card_text = _render_card_text(first_message)
        is_active = first_message.active

    await callback.answer(
        "🟢 Yoqildi." if is_active else "🔴 O‘chirildi."
    )

    await _safe_edit(
        callback,
        card_text,
        first_message_card_keyboard(is_active),
    )


# ============================================================
# DELETE
# ============================================================

@router.callback_query(F.data == "nano:agent:first:delete:ask")
async def first_message_delete_ask(
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

        if user is None:
            await callback.answer(
                "❌ Foydalanuvchi topilmadi.",
                show_alert=True,
            )
            return

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        first_message = result.scalar_one_or_none()

    if first_message is None:
        await callback.answer(
            "❌ Birinchi xabar topilmadi.",
            show_alert=True,
        )
        return

    await callback.answer()

    await _safe_edit(
        callback,
        "⚠️ Birinchi xabarni o‘chirishni xohlaysizmi?",
        first_message_delete_confirm_keyboard(),
    )


@router.callback_query(F.data == "nano:agent:first:delete:no")
async def first_message_delete_no(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await callback.answer("❌ Bekor qilindi.")

    await first_message_card(callback, state)


@router.callback_query(F.data == "nano:agent:first:delete:yes")
async def first_message_delete_yes(
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

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        first_message = result.scalar_one_or_none()

        if first_message is None:
            await callback.answer(
                "❌ Birinchi xabar topilmadi.",
                show_alert=True,
            )
            return

        await session.delete(first_message)
        await session.commit()

    logger.info(
        "First message deleted: telegram_id=%s",
        telegram_id,
    )

    await callback.answer("🗑 O‘chirildi.")

    await _safe_edit(
        callback,
        "1️⃣ <b>Birinchi xabar</b>\n\n"
        "Sizda hozircha birinchi xabar sozlanmagan.\n\n"
        "Yangi xabar yarating — u sizga birinchi marta "
        "yozgan foydalanuvchiga avtomatik yuboriladi.",
        first_message_empty_keyboard(),
    )


__all__ = [
    "router",
    "FirstMessageStates",
]
