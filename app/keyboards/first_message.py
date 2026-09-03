from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

INTERVAL_HOUR = 3600
INTERVAL_DAY = 86400

INTERVAL_LABELS = {
    INTERVAL_HOUR: "⏱ Har 1 soatdan keyin",
    INTERVAL_DAY: "📅 Har 1 kundan keyin",
}


def first_message_empty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Yaratish",
                    callback_data="nano:agent:first:create",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data="nano:agent",
                ),
            ],
        ]
    )


def first_message_card_keyboard(
    is_active: bool,
) -> InlineKeyboardMarkup:
    toggle_button = InlineKeyboardButton(
        text=("🔴 O‘chirish" if is_active else "🟢 Yoqish"),
        callback_data="nano:agent:first:toggle",
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Tahrirlash",
                    callback_data="nano:agent:first:edit",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⏱ Vaqtni o‘zgartirish",
                    callback_data="nano:agent:first:interval",
                ),
            ],
            [toggle_button],
            [
                InlineKeyboardButton(
                    text="🗑 O‘chirish",
                    callback_data="nano:agent:first:delete:ask",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data="nano:agent",
                ),
            ],
        ]
    )


def first_message_interval_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=INTERVAL_LABELS[INTERVAL_HOUR],
                    callback_data=(
                        f"nano:agent:first:interval:set:"
                        f"{INTERVAL_HOUR}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=INTERVAL_LABELS[INTERVAL_DAY],
                    callback_data=(
                        f"nano:agent:first:interval:set:"
                        f"{INTERVAL_DAY}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data="nano:agent:first",
                ),
            ],
        ]
    )


def first_message_delete_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ha, o‘chirish",
                    callback_data="nano:agent:first:delete:yes",
                ),
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data="nano:agent:first:delete:no",
                ),
            ],
        ]
    )


def first_message_input_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data="nano:agent:first:cancel",
                ),
            ],
        ]
    )


__all__ = [
    "INTERVAL_HOUR",
    "INTERVAL_DAY",
    "INTERVAL_LABELS",
    "first_message_empty_keyboard",
    "first_message_card_keyboard",
    "first_message_interval_keyboard",
    "first_message_delete_confirm_keyboard",
    "first_message_input_cancel_keyboard",
]
