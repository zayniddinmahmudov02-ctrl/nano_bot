import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.database import AsyncSessionLocal
from app.keyboards.nano import nano_info_menu_keyboard, nano_info_sub_keyboard
from app.services.terms_service import (
    TERMS_PAGE_COUNT,
    get_terms_page,
)
from app.services.user_service import get_user_language
from app.texts import t, t_all

logger = logging.getLogger(__name__)

router = Router()

PRIVACY_TEXT = (
    "🔒 <b>Maxfiylik</b>\n\n"
    "• Chat (yozishmalar) mazmuni doimiy ravishda "
    "saqlanmaydi.\n"
    "• Xizmat ishlashi uchun zarur texnik va autentifikatsiya "
    "ma'lumotlari (masalan: hisob identifikatorlari, Storage "
    "kanalidagi post havolasi, statistik hisoblagichlar) "
    "saqlanishi mumkin.\n"
    "• Telegram OTP va 2FA parolingiz hech qachon bazaga "
    "yozilmaydi.\n"
    "• Auto Reply/First Message media fayllari PostgreSQL'da "
    "binary ko'rinishda saqlanmaydi — ular alohida shaxsiy "
    "Nano-Bot Storage kanalida saqlanadi.\n"
    "• Bot paroli faqat xavfsiz xesh (bcrypt) ko'rinishida "
    "saqlanadi, hech qachon oddiy matn (plain text) sifatida "
    "emas.\n\n"
    "To'liq shartlar uchun «📄 Shartlar» bo'limiga qarang."
)

FAQ_TEXT = (
    "❓ <b>Savol-javob</b>\n\n"
    "<b>Bot paroli Telegram parolimmi?</b>\n"
    "Yo'q. Bu — faqat Nano-Botning o'ziga kirishni "
    "himoyalovchi qo'shimcha, ixtiyoriy parol.\n\n"
    "<b>Auto Reply ishlamayapti, nega?</b>\n"
    "Telegram akkauntingiz ulanganini va Auto Reply "
    "faol (🟢) ekanligini tekshiring.\n\n"
    "<b>Media qayerda saqlanadi?</b>\n"
    "Sizning shaxsiy Nano-Bot Storage kanalingizda — "
    "bazada emas.\n\n"
    "<b>Ma'lumotlarim xavfsizmi?</b>\n"
    "Ha — batafsil «🔒 Maxfiylik» bo'limida."
)

GUIDE_STEPS = [
    (
        "1️⃣ Telegramni ulash",
        "📱 <b>Telegramni ulash</b>\n\n"
        "Nano-Agent → 📱 Telegram ulash bo'limiga kiring, "
        "shartlarni qabul qiling va telefon raqamingiz "
        "orqali shaxsiy Telegram akkauntingizni ulang.",
    ),
    (
        "2️⃣ Auto Reply yaratish",
        "🤖 <b>Nano-Agentdan Auto Reply yaratish</b>\n\n"
        "Nano-Agent → 🤖 Avto xabar → ➕ Avto javob "
        "qo'shish orqali yangi avtomatik javob yaratasiz.",
    ),
    (
        "3️⃣ Keywordlarni sozlash",
        "🔑 <b>Auto Reply keywordlarini sozlash</b>\n\n"
        "Avto javob yaratishda yoki uni tahrirlashda "
        "kalit so'zlarni vergul bilan ajratib kiritasiz.",
    ),
    (
        "4️⃣ First Message sozlash",
        "1️⃣ <b>First Message sozlash</b>\n\n"
        "Nano-Agent → 1️⃣ Birinchi xabar bo'limida yangi "
        "xabar yarating va qayta yuborish vaqtini "
        "(1 soat/1 kun) tanlang.",
    ),
    (
        "5️⃣ Statistikalarni ko'rish",
        "📊 <b>Statistikalarni ko'rish</b>\n\n"
        "Nano-Agent → 📊 Statistikalar bo'limida "
        "bugungi, 7 kunlik, 30 kunlik va umumiy "
        "ko'rsatkichlarni ko'rasiz.",
    ),
    (
        "6️⃣ Nano-Yordamchi orqali video",
        "🤝 <b>Nano-Yordamchi orqali video link yuborish</b>\n\n"
        "Nano-Yordamchi → ▶️ YouTube Save yoki 📥 "
        "Instagram Save bo'limiga kirib, ochiq (public) "
        "havolani yuboring.",
    ),
    (
        "7️⃣ Tilni o'zgartirish",
        "🌐 <b>Sozlamalardan tilni o'zgartirish</b>\n\n"
        "Sozlamalar → 🌐 Til bo'limida kerakli tilni "
        "tanlang.",
    ),
    (
        "8️⃣ Shaxsiy ma'lumotlar",
        "👤 <b>Shaxsiy ma'lumotlarni boshqarish</b>\n\n"
        "Sozlamalar → 👤 Shaxsiy ma'lumotlar bo'limida "
        "ismingizni tahrirlashingiz mumkin.",
    ),
    (
        "9️⃣ Bot parolini yoqish",
        "🔐 <b>Bot parolini yoqish</b>\n\n"
        "Sozlamalar → 🔐 Bot paroli bo'limida parol "
        "o'rnatib, botga kirishni himoyalashingiz mumkin.",
    ),
    (
        "🔟 Referral tizimi",
        "👥 <b>Referral tizimidan foydalanish</b>\n\n"
        "👥 Referallar bo'limidan havolangizni oling va "
        "do'stlaringizni taklif qilib, Auto Reply "
        "limitingizni oshiring.",
    ),
]


async def _safe_edit(
    callback: CallbackQuery,
    text: str,
    reply_markup,
) -> None:
    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
        )
    except Exception:
        try:
            await callback.message.answer(
                text,
                reply_markup=reply_markup,
            )
        except Exception:
            logger.exception(
                "Nano-Info xabarini yangilab bo'lmadi."
            )


@router.message(Command("info"))
@router.message(F.text.in_(t_all("btn_info")))
async def info_command(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Telegramning pastki Menu panelidan "/info" tanlanganda
    ishga tushadi.
    """

    await state.clear()

    if message.from_user is None:
        return

    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    await message.answer(
        t("info_menu_title", lang),
        reply_markup=nano_info_menu_keyboard(lang),
    )


@router.callback_query(F.data == "nano:info")
async def nano_info_menu(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    await callback.answer()

    await _safe_edit(
        callback,
        t("info_menu_title", lang),
        nano_info_menu_keyboard(lang),
    )


# ============================================================
# GUIDE (har bir bosqich alohida inline ochiladi)
# ============================================================

def _guide_list_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=title,
                callback_data=f"nano:info:guide:step:{index}",
            )
        ]
        for index, (title, _body) in enumerate(GUIDE_STEPS)
    ]

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Orqaga",
                callback_data="nano:info",
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _guide_step_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data="nano:info:guide",
                ),
            ],
        ]
    )


@router.callback_query(F.data == "nano:info:guide")
async def nano_info_guide(callback: CallbackQuery) -> None:
    await callback.answer()

    await _safe_edit(
        callback,
        "📖 <b>Foydalanish yo'riqnomasi</b>\n\n"
        "Kerakli bosqichni tanlang:",
        _guide_list_keyboard(),
    )


@router.callback_query(F.data.startswith("nano:info:guide:step:"))
async def nano_info_guide_step(callback: CallbackQuery) -> None:
    try:
        index = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ Xatolik.", show_alert=True)
        return

    if index < 0 or index >= len(GUIDE_STEPS):
        await callback.answer("❌ Xatolik.", show_alert=True)
        return

    await callback.answer()

    _title, body = GUIDE_STEPS[index]

    await _safe_edit(callback, body, _guide_step_keyboard())


# ============================================================
# TERMS (mavjud terms_service — pagination bilan)
# ============================================================

def _info_terms_page_keyboard(index: int) -> InlineKeyboardMarkup:
    nav_row = []

    if index > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="◀️ Oldingi",
                callback_data=f"nano:info:terms:page:{index - 1}",
            )
        )

    if index < TERMS_PAGE_COUNT - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="Keyingi ▶️",
                callback_data=f"nano:info:terms:page:{index + 1}",
            )
        )

    rows = []

    if nav_row:
        rows.append(nav_row)

    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Orqaga",
                callback_data="nano:info",
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "nano:info:terms")
async def nano_info_terms(callback: CallbackQuery) -> None:
    await callback.answer()

    await _safe_edit(
        callback,
        get_terms_page(0),
        _info_terms_page_keyboard(0),
    )


@router.callback_query(F.data.startswith("nano:info:terms:page:"))
async def nano_info_terms_page(callback: CallbackQuery) -> None:
    try:
        index = int(callback.data.split(":")[-1])
    except ValueError:
        index = 0

    await callback.answer()

    await _safe_edit(
        callback,
        get_terms_page(index),
        _info_terms_page_keyboard(index),
    )


# ============================================================
# PRIVACY
# ============================================================

@router.callback_query(F.data == "nano:info:privacy")
async def nano_info_privacy(callback: CallbackQuery) -> None:
    await callback.answer()

    await _safe_edit(
        callback,
        PRIVACY_TEXT,
        nano_info_sub_keyboard(),
    )


# ============================================================
# FAQ
# ============================================================

@router.callback_query(F.data == "nano:info:faq")
async def nano_info_faq(callback: CallbackQuery) -> None:
    await callback.answer()

    await _safe_edit(
        callback,
        FAQ_TEXT,
        nano_info_sub_keyboard(),
    )


__all__ = [
    "router",
]
