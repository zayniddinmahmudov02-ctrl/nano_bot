import logging
from typing import Optional, Tuple

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from app.database import AsyncSessionLocal
from app.keyboards.nano import (
    nano_assistant_input_keyboard,
    nano_assistant_menu_keyboard,
)
from app.services.access_guard import (
    guard_callback_access,
    guard_message_access,
)
from app.services.instagram_downloader_service import (
    download as download_instagram,
)
from app.services.instagram_downloader_service import (
    validate_url as validate_instagram_url,
)
from app.services.media_downloader_common import (
    DownloadResult,
    cleanup_file,
)
from app.services.user_service import get_user_language
from app.services.youtube_downloader_service import (
    download as download_youtube,
)
from app.services.youtube_downloader_service import (
    validate_url as validate_youtube_url,
)
from app.services.ytdlp_backend import is_ffmpeg_available
from app.texts import t, t_all

logger = logging.getLogger(__name__)

router = Router()


class AssistantStates(StatesGroup):
    waiting_youtube_url = State()
    waiting_instagram_url = State()


_ERROR_TEXT_KEYS = {
    "invalid_url": "download_invalid_url",
    "private": "download_private_blocked",
    "too_large": "download_too_large",
    "busy": "download_busy",
    "timeout": "download_failed",
    "unavailable": "download_unavailable",
    "failed": "download_failed",
}


# ============================================================
# AUTO DETECTION (spec 9/10-bo'lim)
# ============================================================
#
# MUHIM: bu FAQAT foydalanuvchi HECH QANDAY FSM holatida
# bo'lmaganda (StateFilter(None)) ishga tushadi. Shu sababli:
# - Auto Reply/First Message source-yig'ish (waiting_post,
#   waiting_message va h.k.) yoki boshqa har qanday FSM oqimi
#   davomida yuborilgan xabar — bu handlerga UMUMAN yetib
#   bormaydi (aiogram o'sha aniqroq state-filterlangan handlerni
#   birinchi topadi va shu yerda to'xtaydi);
# - Faqat "oddiy bot rejimi"da (hech qanday kutilayotgan
#   input yo'q) erkin yuborilgan xabar ichidan Instagram/YouTube
#   havolasi qidiriladi.
#
# Havola qidirish ATAYLAB yangi/kamroq tekshirilgan regex bilan
# emas, balki MAVJUD, allaqachon qat'iy tekshirilgan
# `validate_youtube_url`/`validate_instagram_url` funksiyalari
# bilan — matn bo'sh joy bo'yicha bo'laklarga ajratiladi va har
# bir bo'lak shu funksiyalar orqali tekshiriladi.

def _extract_recognized_link(
    text: str,
) -> Tuple[Optional[str], Optional[str]]:
    for token in text.split():
        if validate_youtube_url(token):
            return "youtube", token

        if validate_instagram_url(token):
            return "instagram", token

    return None, None


def _has_recognized_link(message: Message) -> bool:
    if not message.text:
        return False

    platform, _url = _extract_recognized_link(message.text)

    return platform is not None


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
                "Nano-Yordamchi xabarini yangilab bo'lmadi."
            )


@router.message(Command("assistant"))
@router.message(F.text.in_(t_all("btn_assistant")))
async def assistant_command(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Telegramning pastki Menu panelidan "/assistant" tanlanganda
    ishga tushadi.
    """

    await state.clear()

    if message.from_user is None:
        return

    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    if not await guard_message_access(message, lang):
        return

    await message.answer(
        t("assistant_menu_title", lang),
        reply_markup=nano_assistant_menu_keyboard(lang),
    )


@router.callback_query(F.data == "nano:assistant")
async def nano_assistant_menu(
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

    if not await guard_callback_access(callback, lang):
        return

    await callback.answer()

    await _safe_edit(
        callback,
        t("assistant_menu_title", lang),
        nano_assistant_menu_keyboard(lang),
    )


@router.callback_query(F.data == "nano:assistant:youtube")
async def assistant_youtube_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    # MUHIM (defense-in-depth): eski inline tugma orqali ham
    # kirish mumkin — shu sabab kirish huquqi mustaqil qayta
    # tekshiriladi.
    if not await guard_callback_access(callback, lang):
        return

    if not is_ffmpeg_available():
        await callback.answer()

        await _safe_edit(
            callback,
            t("download_unavailable", lang),
            nano_assistant_menu_keyboard(lang),
        )
        return

    await state.set_state(AssistantStates.waiting_youtube_url)

    await callback.answer()

    await _safe_edit(
        callback,
        t("youtube_prompt", lang),
        nano_assistant_input_keyboard("nano:assistant", lang),
    )


@router.callback_query(F.data == "nano:assistant:instagram")
async def assistant_instagram_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    # MUHIM (defense-in-depth): eski inline tugma orqali ham
    # kirish mumkin — shu sabab kirish huquqi mustaqil qayta
    # tekshiriladi.
    if not await guard_callback_access(callback, lang):
        return

    # MUHIM: Instagram (reel/post/video) kontenti deyarli har
    # doim allaqachon audio+video birlashtirilgan (pre-muxed)
    # holda keladi — ffmpeg ODATDA UMUMAN kerak emas (real
    # testlar bilan tasdiqlangan). Shu sabab, YouTube'dan farqli
    # o'laroq, Insta-Save ffmpeg yo'qligi sababli oldindan
    # butunlay TO'SIB QO'YILMAYDI — juda kam uchraydigan, alohida
    # oqimlarni talab qiladigan post bo'lsa, xatolik shu ANIQ
    # post uchun keyinroq (yuklab olish bosqichida) qaytariladi.

    await state.set_state(
        AssistantStates.waiting_instagram_url
    )

    await callback.answer()

    await _safe_edit(
        callback,
        t("insta_prompt", lang),
        nano_assistant_input_keyboard("nano:assistant", lang),
    )


_SEND_METHOD_BY_TYPE = {
    "photo": "answer_photo",
    "video": "answer_video",
    "audio": "answer_audio",
}


async def _send_media_file(
    message: Message,
    *,
    file_path: str,
    media_type: str,
    caption: Optional[str],
) -> bool:
    """
    Faylni turi bo'yicha to'g'ri Telegram metodi (photo/video/
    audio) bilan yuboradi. Agar format mos kelmay Telegram uni
    rad etsa (yoki turi noma'lum/"document" bo'lsa) — xavfsiz
    fallback sifatida document ko'rinishida yuboriladi (spec
    5-bo'lim).
    """

    safe_caption = (caption or "")[:1024] or None
    method_name = _SEND_METHOD_BY_TYPE.get(media_type)

    if method_name is not None:
        try:
            method = getattr(message, method_name)
            await method(
                FSInputFile(file_path),
                caption=safe_caption,
            )
            return True
        except Exception:
            logger.warning(
                "Media '%s' turi bilan yuborilmadi, document "
                "sifatida fallback qilinmoqda.",
                media_type,
            )

    try:
        await message.answer_document(
            FSInputFile(file_path),
            caption=safe_caption,
        )
        return True
    except Exception:
        logger.exception(
            "Yuklab olingan media faylni yuborishda xatolik."
        )
        return False


async def _run_download_flow(
    message: Message,
    lang: str,
    url: str,
    download_fn,
) -> None:
    """
    Instagram/YouTube Save uchun umumiy oqim: status xabari ->
    yuklab olish -> media(lar)ni to'g'ri turda yuborish -> vaqtin-
    cha fayllarni tozalash.

    MUHIM: havolaning o'zi (URL) hech qachon logga yozilmaydi —
    faqat umumiy, xavfsiz xabarlar.
    """

    status_message = await message.answer(
        t("download_in_progress", lang)
    )

    result: DownloadResult = await download_fn(url)

    if not result.ok:
        text_key = _ERROR_TEXT_KEYS.get(
            result.error_code, "download_failed"
        )

        try:
            await status_message.edit_text(t(text_key, lang))
        except Exception:
            await message.answer(t(text_key, lang))

        return

    all_files = [
        (result.file_path, result.media_type or "document", result.title)
    ]
    all_files.extend(result.extra_files or [])

    try:
        try:
            await status_message.edit_text(t("download_ready", lang))
        except Exception:
            pass

        sent_any = False

        for file_path, media_type, title in all_files:
            sent = await _send_media_file(
                message,
                file_path=file_path,
                media_type=media_type,
                caption=title,
            )
            sent_any = sent_any or sent

        if not sent_any:
            try:
                await status_message.edit_text(
                    t("download_failed", lang)
                )
            except Exception:
                await message.answer(t("download_failed", lang))

    finally:
        # Media Telegramga yuborilgach — vaqtinchalik fayl(lar)
        # DARHOL o'chiriladi. Hech qanday holatda diskda
        # qoldirilmaydi va PostgreSQL'ga yozilmaydi.
        cleanup_file(result.file_path)

        for file_path, _media_type, _title in (
            result.extra_files or []
        ):
            cleanup_file(file_path)


@router.message(AssistantStates.waiting_youtube_url)
async def assistant_receive_youtube_url(
    message: Message,
    state: FSMContext,
) -> None:
    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    if not await guard_message_access(message, lang):
        return

    if not message.text:
        await message.answer(t("download_invalid_url", lang))
        return

    url = message.text.strip()

    if not validate_youtube_url(url):
        await message.answer(t("download_invalid_url", lang))
        return

    await state.clear()

    await _run_download_flow(message, lang, url, download_youtube)


@router.message(AssistantStates.waiting_instagram_url)
async def assistant_receive_instagram_url(
    message: Message,
    state: FSMContext,
) -> None:
    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    if not await guard_message_access(message, lang):
        return

    if not message.text:
        await message.answer(t("download_invalid_url", lang))
        return

    url = message.text.strip()

    if not validate_instagram_url(url):
        await message.answer(t("download_invalid_url", lang))
        return

    await state.clear()

    await _run_download_flow(message, lang, url, download_instagram)


@router.message(StateFilter(None), _has_recognized_link)
async def assistant_auto_detect_link(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Foydalanuvchi HECH QANDAY tugma bosmasdan, oddiy bot
    rejimida to'g'ridan-to'g'ri Instagram/YouTube havolasi
    yuborsa — tegishli Save funksiyasi avtomatik ishga tushadi
    (spec 9-bo'lim).

    MUHIM: `StateFilter(None)` tufayli bu handler FAQAT hech
    qanday FSM oqimi (jumladan Auto Reply/First Message source-
    yig'ish) faol bo'lmaganda ishga tushadi — shu sabab boshqa
    hech qanday oqim bilan konflikt qilmaydi (spec 10-bo'lim).
    """

    platform, url = _extract_recognized_link(message.text or "")

    if platform is None or url is None:
        return

    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    if not await guard_message_access(message, lang):
        return

    if platform == "youtube":
        if not is_ffmpeg_available():
            await message.answer(t("download_unavailable", lang))
            return

        await _run_download_flow(message, lang, url, download_youtube)
        return

    await _run_download_flow(message, lang, url, download_instagram)


__all__ = [
    "router",
    "AssistantStates",
]
