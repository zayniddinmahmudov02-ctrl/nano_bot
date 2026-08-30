from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def language_keyboard(
    uzbek: bool = True,
    russian: bool = True,
    english: bool = False,
    german: bool = False,
) -> ReplyKeyboardMarkup:

    buttons = []

    if uzbek:
        buttons.append(
            KeyboardButton(
                text="🇺🇿 O‘zbekcha"
            )
        )

    if russian:
        buttons.append(
            KeyboardButton(
                text="🇷🇺 Русский"
            )
        )

    if english:
        buttons.append(
            KeyboardButton(
                text="🇬🇧 English"
            )
        )

    if german:
        buttons.append(
            KeyboardButton(
                text="🇩🇪 Deutsch"
            )
        )

    rows = []

    for index in range(0, len(buttons), 2):
        rows.append(buttons[index:index + 2])

    rows.append(
        [
            KeyboardButton(
                text="⬅️ Orqaga"
            )
        ]
    )

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
    )