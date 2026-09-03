from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _nav_row(back_callback: str) -> list:
    """
    Har bir admin ekrani uchun umumiy navigatsiya qatori.

    ◀️ Orqaga — kontekstga mos ota-ekranga qaytaradi.
    🏠 Asosiy menyu — Admin Panel'dan butunlay chiqib,
    botning oddiy asosiy menyusiga qaytaradi.
    """

    return [
        InlineKeyboardButton(
            text="◀️ Orqaga",
            callback_data=back_callback,
        ),
        InlineKeyboardButton(
            text="🏠 Asosiy menyu",
            callback_data="admin:home",
        ),
    ]


def admin_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Statistika",
                    callback_data="admin:stats",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👥 Foydalanuvchilar",
                    callback_data="admin:users:page:1",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🤖 Auto Replies",
                    callback_data="admin:autoreplies",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👋 First Message",
                    callback_data="admin:firstmessage",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⭐ Premium",
                    callback_data="admin:premium",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💳 To'lovlar",
                    callback_data="admin:payments",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📢 Broadcast",
                    callback_data="admin:broadcast",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔐 Xavfsizlik",
                    callback_data="admin:security",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📜 Loglar",
                    callback_data="admin:logs",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🛑 Botni boshqarish",
                    callback_data="admin:control",
                ),
            ],
        ]
    )


def admin_simple_screen_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[_nav_row("admin:menu")]
    )


def admin_users_list_keyboard(
    user_ids_with_labels: list,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    rows = []

    for user_id, label in user_ids_with_labels:
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=(
                        f"admin:users:view:{user_id}:{page}"
                    ),
                ),
            ]
        )

    pagination_row = []

    if page > 1:
        pagination_row.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"admin:users:page:{page - 1}",
            )
        )

    pagination_row.append(
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data="admin:noop",
        )
    )

    if page < total_pages:
        pagination_row.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"admin:users:page:{page + 1}",
            )
        )

    rows.append(pagination_row)
    rows.append(_nav_row("admin:menu"))

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_user_detail_keyboard(page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            _nav_row(f"admin:users:page:{page}"),
        ]
    )


def admin_broadcast_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[_nav_row("admin:menu")]
    )


def admin_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data="admin:broadcast:confirm",
                ),
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data="admin:broadcast:cancel",
                ),
            ],
        ]
    )


def admin_control_keyboard(
    maintenance_enabled: bool,
) -> InlineKeyboardMarkup:
    maintenance_label = (
        "🛠 Maintenance Mode: 🟢 ON"
        if maintenance_enabled
        else "🛠 Maintenance Mode: ⚪️ OFF"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔴 Stop Bot",
                    callback_data="admin:control:stop:ask",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🟢 Start Bot",
                    callback_data="admin:control:start:ask",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Restart Bot",
                    callback_data="admin:control:restart:ask",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=maintenance_label,
                    callback_data=(
                        "admin:control:maintenance:toggle"
                    ),
                ),
            ],
            _nav_row("admin:menu"),
        ]
    )


def admin_confirm_keyboard(
    yes_callback: str,
    no_callback: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ha",
                    callback_data=yes_callback,
                ),
                InlineKeyboardButton(
                    text="❌ Yo'q",
                    callback_data=no_callback,
                ),
            ],
        ]
    )


__all__ = [
    "admin_main_menu_keyboard",
    "admin_simple_screen_keyboard",
    "admin_users_list_keyboard",
    "admin_user_detail_keyboard",
    "admin_broadcast_start_keyboard",
    "admin_broadcast_confirm_keyboard",
    "admin_control_keyboard",
    "admin_confirm_keyboard",
]
