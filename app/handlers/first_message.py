import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import FirstMessage
from app.keyboards.main import main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router()


class FirstMessageStates(StatesGroup):
    waiting_message = State()
    waiting_edit_message = State()


# =========================================================
# HELPERS
# =========================================================

def extract_message_data(message: Message) -> dict:
    """
    Telegram botga yuborilgan xabardan media/text ma'lumotini oladi.
    """

    if message.photo:
        return {
            "message_type": "photo",
            "message_text": message.caption or "",
            "file_id": message.photo[-1].file_id,
            "link": None,
        }

    if message.video:
        return {
            "message_type": "video",
            "message_text": message.caption or "",
            "file_id": message.video.file_id,
            "link": None,
        }

    if message.document:
        return {
            "message_type": "document",
            "message_text": message.caption or "",
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


async def get_first_message(
    user_id: int,
) -> FirstMessage | None:

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user_id
            )
        )

        return result.scalar_one_or_none()


def first_message_keyboard():
    from aiogram.types import KeyboardButton
    from aiogram.types import ReplyKeyboardMarkup

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="✏️ Birinchi xabarni tahrirlash"
                ),
            ],
            [
                KeyboardButton(
                    text="🗑 Birinchi xabarni o‘chirish"
                ),
            ],
            [
                KeyboardButton(
                    text="🔄 Yoqish/O‘chirish"
                ),
            ],
            [
                KeyboardButton(
                    text="⬅️ Orqaga"
                ),
            ],
        ],
        resize_keyboard=True,
    )


def first_message_cancel_keyboard():
    from aiogram.types import KeyboardButton
    from aiogram.types import ReplyKeyboardMarkup

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="❌ Bekor qilish"
                ),
            ],
        ],
        resize_keyboard=True,
    )


# =========================================================
# MAIN MENU
# =========================================================

@router.message(F.text == "1️⃣ Birinchi xabar")
async def first_message_menu(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    user_id = message.from_user.id

    first_message = await get_first_message(
        user_id
    )

    if not first_message:
        await message.answer(
            "1️⃣ <b>Birinchi xabar</b>\n\n"
            "Sizga birinchi marta yozgan odamga "
            "yuboriladigan xabar hali sozlanmagan.\n\n"
            "📩 Yangi birinchi xabar yaratish uchun "
            "xabarni yuboring.\n\n"
            "📝 Matn\n"
            "🖼 Rasm\n"
            "🎥 Video\n"
            "📎 Fayl",
            reply_markup=first_message_cancel_keyboard(),
        )

        await state.set_state(
            FirstMessageStates.waiting_message
        )

        return

    status = (
        "🟢 Faol"
        if first_message.is_active
        else "🔴 O‘chiq"
    )

    preview = (
        first_message.message_text
        or "Media xabar"
    )

    await message.answer(
        "1️⃣ <b>Birinchi xabar</b>\n\n"
        f"📩 Turi: <b>{first_message.message_type}</b>\n"
        f"🟢 Holat: <b>{status}</b>\n\n"
        "📄 <b>Xabar:</b>\n"
        f"{preview[:1000]}",
        reply_markup=first_message_keyboard(),
    )


# =========================================================
# CREATE
# =========================================================

@router.message(
    FirstMessageStates.waiting_message,
    F.text == "❌ Bekor qilish",
)
async def cancel_first_message_create(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    await message.answer(
        "❌ Birinchi xabar yaratish bekor qilindi.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(
    FirstMessageStates.waiting_message,
)
async def save_first_message(
    message: Message,
    state: FSMContext,
) -> None:

    user_id = message.from_user.id

    data = extract_message_data(
        message
    )

    if (
        data["message_type"] == "text"
        and not data["message_text"]
    ):
        await message.answer(
            "❌ Iltimos, matn, rasm, video "
            "yoki fayl yuboring."
        )
        return

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user_id
            )
        )

        first_message = (
            result.scalar_one_or_none()
        )

        if first_message:
            first_message.message_type = (
                data["message_type"]
            )
            first_message.message_text = (
                data["message_text"]
            )
            first_message.file_id = (
                data["file_id"]
            )
            first_message.link = (
                data["link"]
            )
            first_message.is_active = True

        else:
            first_message = FirstMessage(
                user_id=user_id,
                message_type=data[
                    "message_type"
                ],
                message_text=data[
                    "message_text"
                ],
                file_id=data[
                    "file_id"
                ],
                link=data[
                    "link"
                ],
                is_active=True,
            )

            session.add(first_message)

        await session.commit()

    await state.clear()

    await message.answer(
        "✅ <b>Birinchi xabar saqlandi!</b>\n\n"
        f"📩 Turi: <b>{data['message_type']}</b>\n"
        "🟢 Holat: <b>Faol</b>\n\n"
        "Endi sizga birinchi marta yozgan "
        "odamga ushbu xabar yuboriladi.",
        reply_markup=first_message_keyboard(),
    )


# =========================================================
# EDIT
# =========================================================

@router.message(
    F.text == "✏️ Birinchi xabarni tahrirlash"
)
async def edit_first_message_start(
    message: Message,
    state: FSMContext,
) -> None:

    first_message = await get_first_message(
        message.from_user.id
    )

    if not first_message:
        await message.answer(
            "📭 Birinchi xabar hali yaratilmagan."
        )
        return

    await state.set_state(
        FirstMessageStates.waiting_edit_message
    )

    await message.answer(
        "✏️ <b>Birinchi xabarni tahrirlash</b>\n\n"
        "Yangi xabarni yuboring.\n\n"
        "📝 Matn\n"
        "🖼 Rasm\n"
        "🎥 Video\n"
        "📎 Fayl",
        reply_markup=first_message_cancel_keyboard(),
    )


@router.message(
    FirstMessageStates.waiting_edit_message,
    F.text == "❌ Bekor qilish",
)
async def cancel_first_message_edit(
    message: Message,
    state: FSMContext,
) -> None:

    await state.clear()

    await message.answer(
        "❌ Tahrirlash bekor qilindi.",
        reply_markup=first_message_keyboard(),
    )


@router.message(
    FirstMessageStates.waiting_edit_message,
)
async def edit_first_message(
    message: Message,
    state: FSMContext,
) -> None:

    user_id = message.from_user.id

    data = extract_message_data(
        message
    )

    if (
        data["message_type"] == "text"
        and not data["message_text"]
    ):
        await message.answer(
            "❌ Yaroqli xabar yuboring."
        )
        return

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user_id
            )
        )

        first_message = (
            result.scalar_one_or_none()
        )

        if not first_message:
            await state.clear()

            await message.answer(
                "❌ Birinchi xabar topilmadi.",
                reply_markup=main_menu_keyboard(),
            )
            return

        first_message.message_type = (
            data["message_type"]
        )
        first_message.message_text = (
            data["message_text"]
        )
        first_message.file_id = (
            data["file_id"]
        )
        first_message.link = (
            data["link"]
        )
        first_message.is_active = True

        await session.commit()

    await state.clear()

    await message.answer(
        "✅ <b>Birinchi xabar yangilandi!</b>\n\n"
        f"📩 Turi: <b>{data['message_type']}</b>\n"
        "🟢 Holat: <b>Faol</b>",
        reply_markup=first_message_keyboard(),
    )


# =========================================================
# DELETE
# =========================================================

@router.message(
    F.text == "🗑 Birinchi xabarni o‘chirish"
)
async def delete_first_message(
    message: Message,
) -> None:

    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user_id
            )
        )

        first_message = (
            result.scalar_one_or_none()
        )

        if not first_message:
            await message.answer(
                "📭 Birinchi xabar mavjud emas.",
                reply_markup=main_menu_keyboard(),
            )
            return

        await session.delete(
            first_message
        )

        await session.commit()

    await message.answer(
        "🗑 <b>Birinchi xabar o‘chirildi.</b>",
        reply_markup=main_menu_keyboard(),
    )


# =========================================================
# ENABLE / DISABLE
# =========================================================

@router.message(
    F.text == "🔄 Yoqish/O‘chirish"
)
async def toggle_first_message(
    message: Message,
) -> None:

    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == user_id
            )
        )

        first_message = (
            result.scalar_one_or_none()
        )

        if not first_message:
            await message.answer(
                "📭 Birinchi xabar mavjud emas."
            )
            return

        first_message.is_active = (
            not first_message.is_active
        )

        await session.commit()

        active = first_message.is_active

    status = (
        "🟢 Faollashtirildi"
        if active
        else "🔴 O‘chirildi"
    )

    await message.answer(
        f"✅ <b>Birinchi xabar {status}.</b>",
        reply_markup=first_message_keyboard(),
    )