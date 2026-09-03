from typing import List, Tuple

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ============================================================
# MUHIM: bu modul endi FAQAT InlineKeyboardMarkup ishlatadi —
# ReplyKeyboardMarkup/KeyboardButton butunlay olib tashlandi.
#
# `auto_reply_keyboard()` va `auto_reply_cancel_keyboard()`
# ataylab nomi o'zgartirilmasdan saqlab qolindi, chunki
# `app/handlers/auto_replies.py` ichida ko'plab joyda
# `reply_markup=auto_reply_keyboard()` shaklida chaqiriladi —
# funksiya endi inline klaviatura qaytargani uchun, barcha bu
# chaqiruv joylari boshqa hech narsa o'zgartirmasdan avtomatik
# ravishda inline'ga o'tadi.
# ============================================================


def auto_reply_keyboard() -> InlineKeyboardMarkup:
    """
    Avto javoblar bo'limidagi umumiy "davom etish" klaviaturasi
    (yaratish/xatolik/limit xabarlaridan keyin ko'rsatiladi).
    """

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Avto javoblarim",
                    callback_data="nano:agent:auto",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Nano-Agent",
                    callback_data="nano:agent",
                ),
            ],
        ]
    )


def auto_reply_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    Yangi Avto javob yaratish jarayonida (kalit so'z/post
    kiritish bosqichlari) ko'rsatiladigan "Bekor qilish".
    """

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data="ar:add:cancel",
                ),
            ],
        ]
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

    rows.append(
        [
            InlineKeyboardButton(
                text="➕ Yangi avto javob",
                callback_data="ar:add",
            ),
        ]
    )

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
    "auto_reply_cancel_keyboard",
    "auto_reply_list_inline_keyboard",
    "auto_reply_detail_inline_keyboard",
    "auto_reply_delete_confirm_keyboard",
    "auto_reply_edit_menu_keyboard",
    "auto_reply_edit_cancel_inline_keyboard",
]
