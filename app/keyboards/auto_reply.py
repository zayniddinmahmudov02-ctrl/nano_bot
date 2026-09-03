from typing import List, Tuple

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def auto_reply_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    builder.button(text="➕ Avto javob qo‘shish")
    builder.button(text="📋 Avto javoblarim")
    builder.button(text="🏠 Bosh menyu")

    builder.adjust(2, 1)

    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
    )


def auto_reply_back_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    builder.button(text="⬅️ Orqaga")
    builder.button(text="🏠 Bosh menyu")

    builder.adjust(2)

    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
    )


def auto_reply_cancel_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    builder.button(text="❌ Bekor qilish")

    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
    )


# ============================================================
# INLINE — "📋 Avto javoblarim" ro'yxati va tafsilotlari
# ============================================================

_KEYCAPS = {
    0: "0️⃣", 1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣",
    5: "5️⃣", 6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣",
    10: "🔟",
}


def _keycap(number: int) -> str:
    if number in _KEYCAPS:
        return _KEYCAPS[number]

    return f"{number}."


def auto_reply_list_inline_keyboard(
    indexed_ids: List[Tuple[int, int]],
) -> InlineKeyboardMarkup:
    """
    indexed_ids: [(ko'rsatiladigan tartib raqami, auto_reply_id), ...]
    """

    rows = [
        [
            InlineKeyboardButton(
                text=f"{_keycap(index)} Avto xabar",
                callback_data=f"ar:view:{auto_reply_id}",
            )
        ]
        for index, auto_reply_id in indexed_ids
    ]

    # Reply-keyboard orqali navigatsiya olib tashlangani sababli
    # (yangi yagona inline navigatsiya standarti), ro'yxat
    # ekranida ham "orqaga" tugmasi bo'lishi shart — Nano-Agent
    # menyusiga qaytaradi.
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Orqaga",
                callback_data="nano:agent",
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def auto_reply_detail_inline_keyboard(
    auto_reply_id: int,
    is_active: bool,
) -> InlineKeyboardMarkup:
    toggle_button = InlineKeyboardButton(
        text=(
            "🔴 O‘chirish" if is_active else "🟢 Yoqish"
        ),
        callback_data=f"ar:toggle:{auto_reply_id}",
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Tahrirlash",
                    callback_data=f"ar:edit:menu:{auto_reply_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 O‘chirish",
                    callback_data=f"ar:delete:ask:{auto_reply_id}",
                ),
            ],
            [toggle_button],
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data="ar:list",
                ),
            ],
        ]
    )


def auto_reply_delete_confirm_keyboard(
    auto_reply_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ha, o‘chirish",
                    callback_data=f"ar:delete:yes:{auto_reply_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data=f"ar:delete:no:{auto_reply_id}",
                ),
            ],
        ]
    )


def auto_reply_edit_menu_keyboard(
    auto_reply_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔑 Kalit so‘zlarni tahrirlash",
                    callback_data=f"ar:edit:keywords:{auto_reply_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📩 Javob postini tahrirlash",
                    callback_data=f"ar:edit:post:{auto_reply_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data=f"ar:view:{auto_reply_id}",
                ),
            ],
        ]
    )


def auto_reply_edit_cancel_inline_keyboard(
    auto_reply_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data=f"ar:edit:cancel:{auto_reply_id}",
                ),
            ],
        ]
    )


__all__ = [
    "auto_reply_keyboard",
    "auto_reply_back_keyboard",
    "auto_reply_cancel_keyboard",
    "auto_reply_list_inline_keyboard",
    "auto_reply_detail_inline_keyboard",
    "auto_reply_delete_confirm_keyboard",
    "auto_reply_edit_menu_keyboard",
    "auto_reply_edit_cancel_inline_keyboard",
]
