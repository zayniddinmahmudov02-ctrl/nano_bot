from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.texts import DEFAULT_LANGUAGE, LANGUAGE_LABELS, SUPPORTED_LANGUAGES, t


def _back(callback_data: str, lang: str) -> list:
    return [
        InlineKeyboardButton(
            text=t("btn_back", lang),
            callback_data=callback_data,
        ),
    ]


# ============================================================
# MAIN MENU
# ============================================================

def nano_main_menu_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_agent", lang),
                    callback_data="nano:agent",
                ),
                InlineKeyboardButton(
                    text=t("btn_assistant", lang),
                    callback_data="nano:assistant",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_settings", lang),
                    callback_data="nano:settings",
                ),
                InlineKeyboardButton(
                    text=t("btn_info", lang),
                    callback_data="nano:info",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_referrals", lang),
                    callback_data="nano:referrals",
                ),
            ],
        ]
    )


# ============================================================
# NANO-AGENT
# ============================================================

def nano_agent_menu_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_agent_telegram", lang),
                    callback_data="nano:agent:telegram",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_agent_auto", lang),
                    callback_data="nano:agent:auto",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_agent_first", lang),
                    callback_data="nano:agent:first",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_agent_stats", lang),
                    callback_data="nano:agent:stats",
                ),
            ],
            _back("nano:main", lang),
        ]
    )


# ============================================================
# NANO-YORDAMCHI
# ============================================================

def nano_assistant_menu_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_youtube_save", lang),
                    callback_data="nano:assistant:youtube",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_insta_save", lang),
                    callback_data="nano:assistant:instagram",
                ),
            ],
            _back("nano:main", lang),
        ]
    )


def nano_assistant_input_keyboard(
    back_callback: str,
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[_back(back_callback, lang)]
    )


# ============================================================
# SETTINGS
# ============================================================

def nano_settings_menu_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_settings_language", lang),
                    callback_data="nano:settings:language",
                ),
                InlineKeyboardButton(
                    text=t("btn_settings_premium", lang),
                    callback_data="nano:settings:premium",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_settings_profile", lang),
                    callback_data="nano:settings:profile",
                ),
                InlineKeyboardButton(
                    text=t("btn_settings_password", lang),
                    callback_data="nano:settings:password",
                ),
            ],
            _back("nano:main", lang),
        ]
    )


def nano_language_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=LANGUAGE_LABELS[code],
                callback_data=f"nano:settings:language:set:{code}",
            )
        ]
        for code in SUPPORTED_LANGUAGES
    ]

    rows.append(_back("nano:settings", lang))

    return InlineKeyboardMarkup(inline_keyboard=rows)


def nano_premium_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[_back("nano:settings", lang)]
    )


def nano_profile_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_edit_name", lang),
                    callback_data="nano:settings:profile:edit_name",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_settings_password", lang),
                    callback_data="nano:settings:password",
                ),
            ],
            _back("nano:settings", lang),
        ]
    )


def nano_profile_input_cancel_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            _back("nano:settings:profile", lang),
        ]
    )


# ============================================================
# BOT PASSWORD
# ============================================================

def nano_password_not_set_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_password_set", lang),
                    callback_data="nano:settings:password:set",
                ),
            ],
            _back("nano:settings", lang),
        ]
    )


def nano_password_enabled_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_password_change", lang),
                    callback_data="nano:settings:password:set",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_password_disable", lang),
                    callback_data="nano:settings:password:disable:ask",
                ),
            ],
            _back("nano:settings", lang),
        ]
    )


def nano_password_disable_confirm_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ha",
                    callback_data="nano:settings:password:disable:yes",
                ),
                InlineKeyboardButton(
                    text="❌ Yo'q",
                    callback_data="nano:settings:password:disable:no",
                ),
            ],
        ]
    )


def nano_password_input_cancel_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            _back("nano:settings:password", lang),
        ]
    )


# ============================================================
# NANO-INFO
# ============================================================

def nano_info_menu_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_info_guide", lang),
                    callback_data="nano:info:guide",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_info_terms", lang),
                    callback_data="nano:info:terms",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_info_privacy", lang),
                    callback_data="nano:info:privacy",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_info_faq", lang),
                    callback_data="nano:info:faq",
                ),
            ],
            _back("nano:main", lang),
        ]
    )


def nano_info_sub_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[_back("nano:info", lang)]
    )


# ============================================================
# REFERRALS
# ============================================================

def nano_referrals_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_referral_share", lang),
                    callback_data="nano:referrals:share",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_referral_stats", lang),
                    callback_data="nano:referrals:stats",
                ),
            ],
            _back("nano:main", lang),
        ]
    )


# ============================================================
# STATISTICS
# ============================================================

def nano_stats_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[_back("nano:agent", lang)]
    )


__all__ = [
    "nano_main_menu_keyboard",
    "nano_agent_menu_keyboard",
    "nano_assistant_menu_keyboard",
    "nano_assistant_input_keyboard",
    "nano_settings_menu_keyboard",
    "nano_language_keyboard",
    "nano_premium_keyboard",
    "nano_profile_keyboard",
    "nano_profile_input_cancel_keyboard",
    "nano_password_not_set_keyboard",
    "nano_password_enabled_keyboard",
    "nano_password_disable_confirm_keyboard",
    "nano_password_input_cancel_keyboard",
    "nano_info_menu_keyboard",
    "nano_info_sub_keyboard",
    "nano_referrals_keyboard",
    "nano_stats_keyboard",
]
