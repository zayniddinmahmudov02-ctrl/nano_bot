from __future__ import annotations

from typing import Dict

# ============================================================
# Nano-Bot i18n moduli
# ============================================================
#
# QAMROV: bu modul yangi Bosh menyu / Nano-Agent / Nano-Yordamchi
# / Sozlamalar / Nano-Info / Referallar navigatsiyasi va yangi
# Bot Paroli ekranlari uchun TO'LIQ 4 tilni qamrab oladi.
#
# MUHIM CHEKLOV (ochiq va aniq hujjatlashtirilgan):
# Auto Reply/First Message forma matnlari, Telegram ulash
# Terms matni kabi CHUQUR, oldindan mavjud bo'lgan ekranlar
# hozircha faqat o'zbek tilida qoladi — ularni to'liq va sifatli
# tarjima qilish alohida, katta hajmli ish talab qiladi va
# noto'g'ri tarjima huquqiy/UX xatarlarga olib kelishi mumkin.
# Infratuzilma (shu modul) ularni ham keyinchalik osongina
# qo'shish imkonini beradi.

SUPPORTED_LANGUAGES = ("uz", "ru", "en", "de")
DEFAULT_LANGUAGE = "uz"

LANGUAGE_LABELS: Dict[str, str] = {
    "uz": "🇺🇿 O'zbek",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "de": "🇩🇪 Deutsch",
}


_TEXTS: Dict[str, Dict[str, str]] = {
    # --------------------------------------------------
    # COMMON
    # --------------------------------------------------
    "btn_back": {
        "uz": "⬅️ Orqaga",
        "ru": "⬅️ Назад",
        "en": "⬅️ Back",
        "de": "⬅️ Zurück",
    },
    "btn_back_main": {
        "uz": "⬅️ Bosh menyu",
        "ru": "⬅️ Главное меню",
        "en": "⬅️ Main menu",
        "de": "⬅️ Hauptmenü",
    },
    "btn_home": {
        "uz": "🏠 Bosh menyu",
        "ru": "🏠 Главное меню",
        "en": "🏠 Main menu",
        "de": "🏠 Hauptmenü",
    },
    "generic_error": {
        "uz": "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.",
        "ru": "❌ Произошла ошибка. Попробуйте ещё раз.",
        "en": "❌ Something went wrong. Please try again.",
        "de": "❌ Ein Fehler ist aufgetreten. Bitte versuchen Sie es erneut.",
    },
    "not_found_generic": {
        "uz": "❌ Topilmadi.",
        "ru": "❌ Не найдено.",
        "en": "❌ Not found.",
        "de": "❌ Nicht gefunden.",
    },
    "user_not_found": {
        "uz": "❌ Foydalanuvchi topilmadi.\n\nIltimos, /start buyrug'ini bosing.",
        "ru": "❌ Пользователь не найден.\n\nПожалуйста, нажмите /start.",
        "en": "❌ User not found.\n\nPlease press /start.",
        "de": "❌ Benutzer nicht gefunden.\n\nBitte drücken Sie /start.",
    },

    # --------------------------------------------------
    # MAIN MENU
    # --------------------------------------------------
    "main_menu_title": {
        "uz": "🏠 <b>Bosh menyu</b>\n\nKerakli bo'limni tanlang:",
        "ru": "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        "en": "🏠 <b>Main menu</b>\n\nChoose a section:",
        "de": "🏠 <b>Hauptmenü</b>\n\nWählen Sie einen Bereich:",
    },
    "btn_agent": {
        "uz": "🤖 Nano-Agent",
        "ru": "🤖 Nano-Agent",
        "en": "🤖 Nano-Agent",
        "de": "🤖 Nano-Agent",
    },
    "btn_assistant": {
        "uz": "🤝 Nano-Yordamchi",
        "ru": "🤝 Nano-Помощник",
        "en": "🤝 Nano-Assistant",
        "de": "🤝 Nano-Assistent",
    },
    "btn_settings": {
        "uz": "⚙️ Sozlamalar",
        "ru": "⚙️ Настройки",
        "en": "⚙️ Settings",
        "de": "⚙️ Einstellungen",
    },
    "btn_info": {
        "uz": "ℹ️ Nano-Info",
        "ru": "ℹ️ Nano-Info",
        "en": "ℹ️ Nano-Info",
        "de": "ℹ️ Nano-Info",
    },
    "btn_referrals": {
        "uz": "👥 Referallar",
        "ru": "👥 Рефералы",
        "en": "👥 Referrals",
        "de": "👥 Empfehlungen",
    },

    # --------------------------------------------------
    # NANO-AGENT
    # --------------------------------------------------
    "agent_menu_title": {
        "uz": "🤖 <b>Nano-Agent</b>\n\nTelegram avtomatlashtirish imkoniyatlari:",
        "ru": "🤖 <b>Nano-Agent</b>\n\nВозможности автоматизации Telegram:",
        "en": "🤖 <b>Nano-Agent</b>\n\nTelegram automation features:",
        "de": "🤖 <b>Nano-Agent</b>\n\nTelegram-Automatisierungsfunktionen:",
    },
    "btn_agent_telegram": {
        "uz": "📱 Telegram ulash",
        "ru": "📱 Подключить Telegram",
        "en": "📱 Connect Telegram",
        "de": "📱 Telegram verbinden",
    },
    "btn_agent_auto": {
        "uz": "🤖 Avto xabar",
        "ru": "🤖 Автоответ",
        "en": "🤖 Auto reply",
        "de": "🤖 Auto-Antwort",
    },
    "btn_agent_first": {
        "uz": "1️⃣ Birinchi xabar",
        "ru": "1️⃣ Первое сообщение",
        "en": "1️⃣ First message",
        "de": "1️⃣ Erste Nachricht",
    },
    "btn_agent_stats": {
        "uz": "📊 Statistikalar",
        "ru": "📊 Статистика",
        "en": "📊 Statistics",
        "de": "📊 Statistiken",
    },

    # --------------------------------------------------
    # NANO-YORDAMCHI
    # --------------------------------------------------
    "assistant_menu_title": {
        "uz": "🤝 <b>Nano-Yordamchi</b>\n\nMedia yordamchisi imkoniyatlari:",
        "ru": "🤝 <b>Nano-Помощник</b>\n\nВозможности медиапомощника:",
        "en": "🤝 <b>Nano-Assistant</b>\n\nMedia assistant features:",
        "de": "🤝 <b>Nano-Assistent</b>\n\nMedien-Assistent-Funktionen:",
    },
    "btn_youtube_save": {
        "uz": "▶️ YouTube-Save",
        "ru": "▶️ YouTube-Save",
        "en": "▶️ YouTube-Save",
        "de": "▶️ YouTube-Save",
    },
    "btn_insta_save": {
        "uz": "📸 Insta-Save",
        "ru": "📸 Insta-Save",
        "en": "📸 Insta-Save",
        "de": "📸 Insta-Save",
    },
    "youtube_prompt": {
        "uz": "▶️ <b>YouTube-Save</b>\n\n🎬 YouTube video havolasini yuboring.",
        "ru": "▶️ <b>YouTube-Save</b>\n\n🎬 Отправьте ссылку на видео YouTube.",
        "en": "▶️ <b>YouTube-Save</b>\n\n🎬 Send a YouTube video link.",
        "de": "▶️ <b>YouTube-Save</b>\n\n🎬 Senden Sie einen YouTube-Video-Link.",
    },
    "insta_prompt": {
        "uz": "📸 <b>Insta-Save</b>\n\n📎 Instagram havolasini yuboring.",
        "ru": "📸 <b>Insta-Save</b>\n\n📎 Отправьте ссылку на Instagram.",
        "en": "📸 <b>Insta-Save</b>\n\n📎 Send an Instagram link.",
        "de": "📸 <b>Insta-Save</b>\n\n📎 Senden Sie einen Instagram-Link.",
    },
    "download_invalid_url": {
        "uz": "❌ Havola noto'g'ri yoki qo'llab-quvvatlanmaydi.",
        "ru": "❌ Ссылка неверна или не поддерживается.",
        "en": "❌ The link is invalid or not supported.",
        "de": "❌ Der Link ist ungültig oder wird nicht unterstützt.",
    },
    "download_private_blocked": {
        "uz": "❌ Faqat ochiq (public) kontent bilan ishlaymiz. Maxfiy/himoyalangan akkaunt kontenti yuklab bo'lmaydi.",
        "ru": "❌ Работаем только с публичным контентом. Контент закрытого аккаунта скачать нельзя.",
        "en": "❌ Only public content is supported. Content from private/protected accounts cannot be downloaded.",
        "de": "❌ Nur öffentliche Inhalte werden unterstützt. Inhalte privater/geschützter Konten können nicht heruntergeladen werden.",
    },
    "download_in_progress": {
        "uz": "⏳ Yuklab olinmoqda, biroz kuting...",
        "ru": "⏳ Загрузка, подождите...",
        "en": "⏳ Downloading, please wait...",
        "de": "⏳ Wird heruntergeladen, bitte warten...",
    },
    "download_too_large": {
        "uz": "❌ Fayl hajmi ruxsat etilgan chegaradan katta.",
        "ru": "❌ Размер файла превышает допустимый лимит.",
        "en": "❌ File size exceeds the allowed limit.",
        "de": "❌ Die Dateigröße überschreitet das zulässige Limit.",
    },
    "download_busy": {
        "uz": "⏳ Hozircha yuklab olishlar band. Birozdan keyin qayta urinib ko'ring.",
        "ru": "⏳ Сейчас все загрузки заняты. Попробуйте немного позже.",
        "en": "⏳ All download slots are busy right now. Please try again shortly.",
        "de": "⏳ Alle Download-Plätze sind derzeit belegt. Bitte versuchen Sie es später erneut.",
    },
    "download_failed": {
        "uz": "❌ Yuklab olishda xatolik yuz berdi. Havolani tekshirib qayta urinib ko'ring.",
        "ru": "❌ Ошибка при загрузке. Проверьте ссылку и попробуйте снова.",
        "en": "❌ Download failed. Please check the link and try again.",
        "de": "❌ Download fehlgeschlagen. Bitte überprüfen Sie den Link und versuchen Sie es erneut.",
    },
    "download_unavailable": {
        "uz": "⚠️ Bu funksiya hozircha serverda sozlanmagan.",
        "ru": "⚠️ Эта функция пока не настроена на сервере.",
        "en": "⚠️ This feature is not configured on the server yet.",
        "de": "⚠️ Diese Funktion ist auf dem Server noch nicht konfiguriert.",
    },

    # --------------------------------------------------
    # SETTINGS
    # --------------------------------------------------
    "settings_menu_title": {
        "uz": "⚙️ <b>Sozlamalar</b>",
        "ru": "⚙️ <b>Настройки</b>",
        "en": "⚙️ <b>Settings</b>",
        "de": "⚙️ <b>Einstellungen</b>",
    },
    "btn_settings_language": {
        "uz": "🌐 Til",
        "ru": "🌐 Язык",
        "en": "🌐 Language",
        "de": "🌐 Sprache",
    },
    "btn_settings_premium": {
        "uz": "💎 Premium",
        "ru": "💎 Premium",
        "en": "💎 Premium",
        "de": "💎 Premium",
    },
    "btn_settings_profile": {
        "uz": "👤 Shaxsiy ma'lumotlar",
        "ru": "👤 Личные данные",
        "en": "👤 Personal data",
        "de": "👤 Persönliche Daten",
    },
    "btn_settings_password": {
        "uz": "🔐 Bot paroli",
        "ru": "🔐 Пароль бота",
        "en": "🔐 Bot password",
        "de": "🔐 Bot-Passwort",
    },
    "language_menu_title": {
        "uz": "🌐 <b>Tilni tanlang</b>",
        "ru": "🌐 <b>Выберите язык</b>",
        "en": "🌐 <b>Choose a language</b>",
        "de": "🌐 <b>Sprache wählen</b>",
    },
    "language_updated": {
        "uz": "✅ Til muvaffaqiyatli o'zgartirildi.",
        "ru": "✅ Язык успешно изменён.",
        "en": "✅ Language changed successfully.",
        "de": "✅ Sprache erfolgreich geändert.",
    },

    # --------------------------------------------------
    # PREMIUM
    # --------------------------------------------------
    "premium_title": {
        "uz": "💎 <b>Premium</b>",
        "ru": "💎 <b>Premium</b>",
        "en": "💎 <b>Premium</b>",
        "de": "💎 <b>Premium</b>",
    },
    "premium_status_free": {
        "uz": "Joriy status:\n🟢 Free",
        "ru": "Текущий статус:\n🟢 Free",
        "en": "Current status:\n🟢 Free",
        "de": "Aktueller Status:\n🟢 Free",
    },
    "premium_status_active": {
        "uz": "Joriy status:\n💎 Premium (faol)",
        "ru": "Текущий статус:\n💎 Premium (активен)",
        "en": "Current status:\n💎 Premium (active)",
        "de": "Aktueller Status:\n💎 Premium (aktiv)",
    },

    # --------------------------------------------------
    # PERSONAL DATA
    # --------------------------------------------------
    "profile_title": {
        "uz": "👤 <b>Shaxsiy ma'lumotlar</b>",
        "ru": "👤 <b>Личные данные</b>",
        "en": "👤 <b>Personal data</b>",
        "de": "👤 <b>Persönliche Daten</b>",
    },
    "btn_edit_name": {
        "uz": "✏️ Ismni tahrirlash",
        "ru": "✏️ Изменить имя",
        "en": "✏️ Edit name",
        "de": "✏️ Namen bearbeiten",
    },
    "edit_name_prompt": {
        "uz": "✏️ <b>Yangi ismingizni kiriting:</b>",
        "ru": "✏️ <b>Введите новое имя:</b>",
        "en": "✏️ <b>Enter your new name:</b>",
        "de": "✏️ <b>Geben Sie Ihren neuen Namen ein:</b>",
    },
    "edit_name_success": {
        "uz": "✅ Ismingiz muvaffaqiyatli o'zgartirildi.",
        "ru": "✅ Ваше имя успешно изменено.",
        "en": "✅ Your name has been changed successfully.",
        "de": "✅ Ihr Name wurde erfolgreich geändert.",
    },
    "edit_name_empty": {
        "uz": "❌ Ism bo'sh bo'lishi mumkin emas.",
        "ru": "❌ Имя не может быть пустым.",
        "en": "❌ Name cannot be empty.",
        "de": "❌ Der Name darf nicht leer sein.",
    },
    "edit_name_too_long": {
        "uz": "❌ Ism juda uzun (maksimal 100 belgi).",
        "ru": "❌ Имя слишком длинное (максимум 100 символов).",
        "en": "❌ Name is too long (max 100 characters).",
        "de": "❌ Der Name ist zu lang (max. 100 Zeichen).",
    },

    # --------------------------------------------------
    # BOT PASSWORD
    # --------------------------------------------------
    "password_title": {
        "uz": "🔐 <b>Bot paroli</b>",
        "ru": "🔐 <b>Пароль бота</b>",
        "en": "🔐 <b>Bot password</b>",
        "de": "🔐 <b>Bot-Passwort</b>",
    },
    "password_not_set_description": {
        "uz": "Botga kirishni parol bilan himoyalash:",
        "ru": "Защитите вход в бота паролем:",
        "en": "Protect access to the bot with a password:",
        "de": "Schützen Sie den Zugang zum Bot mit einem Passwort:",
    },
    "password_enabled_status": {
        "uz": "🟢 Himoya yoqilgan",
        "ru": "🟢 Защита включена",
        "en": "🟢 Protection enabled",
        "de": "🟢 Schutz aktiviert",
    },
    "btn_password_set": {
        "uz": "🔑 Parol o'rnatish",
        "ru": "🔑 Установить пароль",
        "en": "🔑 Set password",
        "de": "🔑 Passwort festlegen",
    },
    "btn_password_change": {
        "uz": "🔄 Parolni almashtirish",
        "ru": "🔄 Изменить пароль",
        "en": "🔄 Change password",
        "de": "🔄 Passwort ändern",
    },
    "btn_password_disable": {
        "uz": "❌ Himoyani o'chirish",
        "ru": "❌ Отключить защиту",
        "en": "❌ Disable protection",
        "de": "❌ Schutz deaktivieren",
    },
    "password_set_prompt": {
        "uz": "🔑 <b>Yangi parolni kiriting:</b>\n\nKamida 4 ta belgi.",
        "ru": "🔑 <b>Введите новый пароль:</b>\n\nМинимум 4 символа.",
        "en": "🔑 <b>Enter a new password:</b>\n\nAt least 4 characters.",
        "de": "🔑 <b>Neues Passwort eingeben:</b>\n\nMindestens 4 Zeichen.",
    },
    "password_set_success": {
        "uz": "✅ Bot paroli o'rnatildi. Endi 1 soat harakatsizlikdan so'ng parol so'raladi.",
        "ru": "✅ Пароль бота установлен. Теперь после 1 часа бездействия будет запрошен пароль.",
        "en": "✅ Bot password set. A password will now be requested after 1 hour of inactivity.",
        "de": "✅ Bot-Passwort festgelegt. Nach 1 Stunde Inaktivität wird nun ein Passwort verlangt.",
    },
    "password_disabled_success": {
        "uz": "✅ Bot paroli himoyasi o'chirildi.",
        "ru": "✅ Защита паролем бота отключена.",
        "en": "✅ Bot password protection disabled.",
        "de": "✅ Bot-Passwortschutz deaktiviert.",
    },

    # --------------------------------------------------
    # NANO-INFO
    # --------------------------------------------------
    "info_menu_title": {
        "uz": "ℹ️ <b>Nano-Info</b>",
        "ru": "ℹ️ <b>Nano-Info</b>",
        "en": "ℹ️ <b>Nano-Info</b>",
        "de": "ℹ️ <b>Nano-Info</b>",
    },
    "btn_info_guide": {
        "uz": "📖 Foydalanish yo'riqnomasi",
        "ru": "📖 Руководство пользователя",
        "en": "📖 User guide",
        "de": "📖 Benutzerhandbuch",
    },
    "btn_info_terms": {
        "uz": "📄 Shartlar",
        "ru": "📄 Условия",
        "en": "📄 Terms",
        "de": "📄 Bedingungen",
    },
    "btn_info_privacy": {
        "uz": "🔒 Maxfiylik",
        "ru": "🔒 Конфиденциальность",
        "en": "🔒 Privacy",
        "de": "🔒 Datenschutz",
    },
    "btn_info_faq": {
        "uz": "❓ Savol-javob",
        "ru": "❓ Вопросы и ответы",
        "en": "❓ FAQ",
        "de": "❓ FAQ",
    },

    # --------------------------------------------------
    # STATISTICS
    # --------------------------------------------------
    "stats_title": {
        "uz": "📊 <b>Statistikalar</b>",
        "ru": "📊 <b>Статистика</b>",
        "en": "📊 <b>Statistics</b>",
        "de": "📊 <b>Statistiken</b>",
    },
    "stats_period_today": {
        "uz": "📅 Bugun",
        "ru": "📅 Сегодня",
        "en": "📅 Today",
        "de": "📅 Heute",
    },
    "stats_period_7d": {
        "uz": "📅 7 kun",
        "ru": "📅 7 дней",
        "en": "📅 7 days",
        "de": "📅 7 Tage",
    },
    "stats_period_30d": {
        "uz": "📅 30 kun",
        "ru": "📅 30 дней",
        "en": "📅 30 days",
        "de": "📅 30 Tage",
    },
    "stats_period_all": {
        "uz": "📈 Umumiy",
        "ru": "📈 Всего",
        "en": "📈 All time",
        "de": "📈 Insgesamt",
    },

    # --------------------------------------------------
    # REFERRALS
    # --------------------------------------------------
    "referrals_title": {
        "uz": "👥 <b>Referal tizimi</b>",
        "ru": "👥 <b>Реферальная система</b>",
        "en": "👥 <b>Referral system</b>",
        "de": "👥 <b>Empfehlungssystem</b>",
    },
    "btn_referral_share": {
        "uz": "🔗 Havolani ulashish",
        "ru": "🔗 Поделиться ссылкой",
        "en": "🔗 Share link",
        "de": "🔗 Link teilen",
    },
    "btn_referral_stats": {
        "uz": "📊 Referal statistikasi",
        "ru": "📊 Реферальная статистика",
        "en": "📊 Referral statistics",
        "de": "📊 Empfehlungsstatistik",
    },
}


def t(
    key: str,
    lang: str = DEFAULT_LANGUAGE,
    **kwargs,
) -> str:
    """
    Berilgan kalit va til bo'yicha UI matnini qaytaradi.

    - Noma'lum til → DEFAULT_LANGUAGE (uz) bilan almashtiriladi.
    - Berilgan tilda tarjima yo'q → uz varianti ishlatiladi.
    - Kalitning o'zi topilmasa → xatolik ko'tarmaslik uchun
      kalitning o'zi qaytariladi (fail-safe).
    """

    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    entry = _TEXTS.get(key)

    if entry is None:
        return key

    template = (
        entry.get(lang)
        or entry.get(DEFAULT_LANGUAGE)
        or key
    )

    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template

    return template


__all__ = [
    "SUPPORTED_LANGUAGES",
    "DEFAULT_LANGUAGE",
    "LANGUAGE_LABELS",
    "t",
]
