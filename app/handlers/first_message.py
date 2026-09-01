import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import FirstMessage
from app.keyboards.main import main_menu_keyboard
from app.services.user_service import get_user_by_telegram_id

logger = logging.getLogger(__name__)

router = Router()


class FirstMessageStates(StatesGroup):
    waiting_message = State()
    waiting_edit_message = State()


def first_message_keyboard():
    """
    First message menyusi.
    """

    from aiogram.types import ReplyKeyboardMarkup
    from aiogram.utils.keyboard import ReplyKeyboardBuilder

    builder = ReplyKeyboardBuilder()

    builder.button(text="➕ Birinchi xabar yaratish")
    builder.button(text="✏️ Birinchi xabarni o‘zgartirish")
    builder.button(text="🗑 Birinchi xabarni o‘chirish")
    builder.button(text="🔄 Yoqish / O‘chirish")
    builder.button(text="📋 Birinchi xabar holati")
    builder.button(text="🏠 Bosh menyu")

    builder.adjust(2, 2, 1, 1)

    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
    )


@router.message(F.text == "1️⃣ Birinchi xabar")
async def first_message_menu(
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
                "❌ Foydalanuvchi topilmadi.\n\n"
                "Iltimos, /start buyrug‘ini bosing.",
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
        await message.answer(
            "1️⃣ <b>Birinchi xabar</b>\n\n"
            "Sizda hozircha birinchi xabar "
            "sozlanmagan.\n\n"
            "Yangi xabar yarating. U sizga "
            "birinchi marta yozgan foydalanuvchiga "
            "yuboriladi.",
            reply_markup=first_message_keyboard(),
        )
        return

    status = (
        "🟢 Faol"
        if first_message.active
        else "🔴 O‘chiq"
    )

    await message.answer(
        "1️⃣ <b>Birinchi xabar</b>\n\n"
        f"📦 Tur: <code>{first_message.message_type}</code>\n"
        f"📊 Holat: <b>{status}</b>\n\n"
        "Birinchi marta yozgan foydalanuvchiga "
        "avtomatik yuboriladigan xabarni "
        "boshqarishingiz mumkin.",
        reply_markup=first_message_keyboard(),
    )


@router.message(F.text == "➕ Birinchi xabar yaratish")
async def create_first_message_start(
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
        await message.answer(
            "⚠️ Sizda allaqachon birinchi xabar mavjud.\n\n"
            "Uni yangi xabar bilan almashtirish uchun "
            "✏️ <b>Birinchi xabarni o‘zgartirish</b> "
            "tugmasidan foydalaning.",
            reply_markup=first_message_keyboard(),
        )
        return

    await state.clear()
    await state.set_state(
        FirstMessageStates.waiting_message
    )

    await message.answer(
        "📩 <b>Birinchi xabarni yuboring</b>\n\n"
        "Matn, rasm, video yoki hujjat yuborishingiz mumkin.\n\n"
        "Bu xabar sizning Telegram akkauntingizga "
        "birinchi marta yozgan foydalanuvchiga yuboriladi.\n\n"
        "Bekor qilish uchun:\n"
        "❌ Bekor qilish"
    )


@router.message(
    FirstMessageStates.waiting_message,
    F.text == "❌ Bekor qilish",
)
async def cancel_create_first_message(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "❌ Birinchi xabar yaratish bekor qilindi.",
        reply_markup=first_message_keyboard(),
    )


@router.message(
    FirstMessageStates.waiting_message,
)
async def receive_first_message(
    message: Message,
    state: FSMContext,
) -> None:
    message_type = None
    text = None
    file_id = None

    if message.text:
        message_type = "text"
        text = message.text

    elif message.photo:
        message_type = "photo"
        file_id = message.photo[-1].file_id
        text = message.caption

    elif message.video:
        message_type = "video"
        file_id = message.video.file_id
        text = message.caption

    elif message.document:
        message_type = "document"
        file_id = message.document.file_id
        text = message.caption

    else:
        await message.answer(
            "❌ Bu turdagi xabar qo‘llab-quvvatlanmaydi.\n\n"
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

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        existing = result.scalar_one_or_none()

        if existing:
            await state.clear()

            await message.answer(
                "⚠️ Birinchi xabar allaqachon mavjud.",
                reply_markup=first_message_keyboard(),
            )
            return

        first_message = FirstMessage(
            user_id=user.id,
            message_type=message_type,
            text=text,
            file_id=file_id,
            link=None,
            active=True,
        )

        session.add(first_message)

        await session.commit()

    await state.clear()

    await message.answer(
        "✅ <b>Birinchi xabar yaratildi!</b>\n\n"
        f"📦 Tur: <code>{message_type}</code>\n"
        "🟢 Holat: <b>Faol</b>\n\n"
        "Endi birinchi marta yozgan foydalanuvchilarga "
        "ushbu xabar yuboriladi.",
        reply_markup=first_message_keyboard(),
    )


@router.message(F.text == "✏️ Birinchi xabarni o‘zgartirish")
async def edit_first_message_start(
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

    if existing is None:
        await message.answer(
            "❌ Birinchi xabar hali yaratilmagan.",
            reply_markup=first_message_keyboard(),
        )
        return

    await state.clear()
    await state.set_state(
        FirstMessageStates.waiting_edit_message
    )

    await message.answer(
        "✏️ <b>Yangi birinchi xabarni yuboring.</b>\n\n"
        "Eski xabar yangi xabar bilan almashtiriladi.\n\n"
        "Matn, rasm, video yoki hujjat yuborishingiz mumkin.\n\n"
        "Bekor qilish:\n"
        "❌ Bekor qilish"
    )


@router.message(
    FirstMessageStates.waiting_edit_message,
    F.text == "❌ Bekor qilish",
)
async def cancel_edit_first_message(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "❌ O‘zgartirish bekor qilindi.",
        reply_markup=first_message_keyboard(),
    )


@router.message(
    FirstMessageStates.waiting_edit_message,
)
async def receive_edit_first_message(
    message: Message,
    state: FSMContext,
) -> None:
    message_type = None
    text = None
    file_id = None

    if message.text:
        message_type = "text"
        text = message.text

    elif message.photo:
        message_type = "photo"
        file_id = message.photo[-1].file_id
        text = message.caption

    elif message.video:
        message_type = "video"
        file_id = message.video.file_id
        text = message.caption

    elif message.document:
        message_type = "document"
        file_id = message.document.file_id
        text = message.caption

    else:
        await message.answer(
            "❌ Bu turdagi xabar qo‘llab-quvvatlanmaydi."
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

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        first_message = result.scalar_one_or_none()

        if first_message is None:
            await state.clear()

            await message.answer(
                "❌ Birinchi xabar topilmadi.",
                reply_markup=first_message_keyboard(),
            )
            return

        first_message.message_type = message_type
        first_message.text = text
        first_message.file_id = file_id
        first_message.link = None

        await session.commit()

    await state.clear()

    await message.answer(
        "✅ <b>Birinchi xabar yangilandi!</b>\n\n"
        f"📦 Tur: <code>{message_type}</code>",
        reply_markup=first_message_keyboard(),
    )


@router.message(F.text == "🗑 Birinchi xabarni o‘chirish")
async def delete_first_message(
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

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        first_message = result.scalar_one_or_none()

        if first_message is None:
            await message.answer(
                "ℹ️ O‘chirish uchun birinchi xabar mavjud emas.",
                reply_markup=first_message_keyboard(),
            )
            return

        await session.delete(first_message)
        await session.commit()

    await message.answer(
        "🗑 <b>Birinchi xabar o‘chirildi.</b>",
        reply_markup=first_message_keyboard(),
    )


@router.message(F.text == "🔄 Yoqish / O‘chirish")
async def toggle_first_message(
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

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        first_message = result.scalar_one_or_none()

        if first_message is None:
            await message.answer(
                "❌ Avval birinchi xabar yarating.",
                reply_markup=first_message_keyboard(),
            )
            return

        first_message.active = (
            not first_message.active
        )

        await session.commit()

        status = (
            "🟢 Faol"
            if first_message.active
            else "🔴 O‘chiq"
        )

    await message.answer(
        "🔄 <b>Birinchi xabar holati o‘zgartirildi.</b>\n\n"
        f"📊 Holat: <b>{status}</b>",
        reply_markup=first_message_keyboard(),
    )


@router.message(F.text == "📋 Birinchi xabar holati")
async def first_message_status(
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

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user.id
            )
        )

        first_message = result.scalar_one_or_none()

    if first_message is None:
        await message.answer(
            "❌ Birinchi xabar sozlanmagan.",
            reply_markup=first_message_keyboard(),
        )
        return

    status = (
        "🟢 Faol"
        if first_message.active
        else "🔴 O‘chiq"
    )

    preview = (
        first_message.text
        if first_message.text
        else f"[{first_message.message_type}]"
    )

    if len(preview) > 300:
        preview = preview[:300] + "..."

    await message.answer(
        "📋 <b>Birinchi xabar holati</b>\n\n"
        f"📊 Holat: <b>{status}</b>\n"
        f"📦 Tur: <code>{first_message.message_type}</code>\n\n"
        "📝 Xabar:\n"
        f"<code>{preview}</code>",
        reply_markup=first_message_keyboard(),
    )


@router.message(F.text == "🏠 Bosh menyu")
async def first_message_back(
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
    "FirstMessageStates",
    "first_message_keyboard",
]