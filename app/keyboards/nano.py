from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.texts import DEFAULT_LANGUAGE, LANGUAGE_LABELS, SUPPORTED_LANGUAGES, t


# ============================================================
# ASOSIY MENU — Telegramning pastki (Reply) klaviatura paneli
# ============================================================
#
# MUHIM: bu — CHAT ICHIGA yuborilgan alohida "menu message" ham,
# ichki inline navigatsiya ham EMAS. Bu Telegramning o'zining
# pastki klaviatura panelidagi doimiy tugmalar — yozish
# maydonining tepasida (⌨️ belgisi orqali ochib-yopiladigan)
# joyda ko'rinadi, xuddi so'ralgan referens (Vizu Bot) kabi.
#
# `resize_keyboard=True` — panel tugmalar soniga moslab
# ixchamlashtiriladi.
# `is_persistent=True` — panel doimiy ko'rinib turadi (Telegram
# uni "yopilgan" holatda ham ⌨️ belgisi orqali darhol qayta
# ochish imkonini beradi).

def nano_main_reply_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t("btn_agent", lang)),
                KeyboardButton(text=t("btn_assistant", lang)),
            ],
            [
                KeyboardButton(text=t("btn_settings", lang)),
                KeyboardButton(text=t("btn_info", lang)),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=t("menu_placeholder", lang),
    )


def _back(callback_data: str, lang: str) -> list:
    return [
        InlineKeyboardButton(
            text=t("btn_back", lang),
            callback_data=callback_data,
        ),
    ]


def _back_main(lang: str) -> list:
    """
    Bosh menyuga TO'G'RIDAN-TO'G'RI qaytaradigan tugma qatori
    ("⬅️ Bosh menyu"). Nano-Agent, Nano-Yordamchi, Sozlamalar,
    Nano-Info va Referallar — bularning barchasi bosh menyuning
    bevosita bolalari, shu sabab ularning "orqaga" tugmasi aynan
    shu maxsus yorliqni ishlatadi (chuqurroq ichki sahifalar esa
    kontekstual "⬅️ Orqaga"ni davom ettiradi).
    """

    return [
        InlineKeyboardButton(
            text=t("btn_back_main", lang),
            callback_data="nano:main",
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
            _back_main(lang),
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
            _back_main(lang),
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
                    text=t("btn_settings_activity", lang),
                    callback_data="nano:activity",
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
            _back_main(lang),
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


# ============================================================
# FAOLLIK (ACTIVITY)
# ============================================================

def nano_activity_menu_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_package_1m", lang),
                    callback_data="nano:activity:package:1m",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_package_3m", lang),
                    callback_data="nano:activity:package:3m",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_package_6m", lang),
                    callback_data="nano:activity:package:6m",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_package_1y", lang),
                    callback_data="nano:activity:package:1y",
                ),
            ],
            _back("nano:settings", lang),
        ]
    )


def nano_activity_receipt_cancel_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[_back("nano:activity", lang)]
    )


def nano_access_denied_keyboard(
    lang: str = DEFAULT_LANGUAGE,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_activity_open", lang),
                    callback_data="nano:activity",
                ),
            ],
        ]
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
            _back_main(lang),
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
            _back_main(lang),
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
    "nano_main_reply_keyboard",
    "nano_main_menu_keyboard",
    "nano_agent_menu_keyboard",
    "nano_assistant_menu_keyboard",
    "nano_assistant_input_keyboard",
    "nano_settings_menu_keyboard",
    "nano_language_keyboard",
    "nano_activity_menu_keyboard",
    "nano_activity_receipt_cancel_keyboard",
    "nano_access_denied_keyboard",
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
