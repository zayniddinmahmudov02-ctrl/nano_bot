from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def auto_reply_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="➕ Avto xabar qo‘shish"
                ),
            ],
            [
                KeyboardButton(
                    text="📋 Avto xabarlarim"
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


def auto_reply_cancel_keyboard() -> ReplyKeyboardMarkup:
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


def auto_reply_edit_keyboard(
    auto_reply_id: int,
    is_active: bool = True,
) -> ReplyKeyboardMarkup:
    status_text = (
        "⏸ O‘chirish"
        if is_active
        else "▶️ Yoqish"
    )

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="✏️ Tahrirlash"
                ),
                KeyboardButton(
                    text="🗑 O‘chirish"
                ),
            ],
            [
                KeyboardButton(
                    text=status_text
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


def media_type_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📝 Matn"
                ),
                KeyboardButton(
                    text="🖼 Rasm"
                ),
            ],
            [
                KeyboardButton(
                    text="🎥 Video"
                ),
                KeyboardButton(
                    text="📎 Fayl"
                ),
            ],
            [
                KeyboardButton(
                    text="🔗 Link"
                ),
            ],
            [
                KeyboardButton(
                    text="❌ Bekor qilish"
                ),
            ],
        ],
        resize_keyboard=True,
    )