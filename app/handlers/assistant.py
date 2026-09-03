import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from app.database import AsyncSessionLocal
from app.keyboards.nano import (
    nano_assistant_input_keyboard,
    nano_assistant_menu_keyboard,
)
from app.services.instagram_downloader_service import (
    download as download_instagram,
)
from app.services.instagram_downloader_service import (
    validate_url as validate_instagram_url,
)
from app.services.media_downloader_common import cleanup_file
from app.services.user_service import get_user_language
from app.services.youtube_downloader_service import (
    download as download_youtube,
)
from app.services.youtube_downloader_service import (
    validate_url as validate_youtube_url,
)
from app.services.ytdlp_backend import is_ffmpeg_available
from app.texts import t

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

    if not is_ffmpeg_available():
        await callback.answer()

        await _safe_edit(
            callback,
            t("download_unavailable", lang),
            nano_assistant_menu_keyboard(lang),
        )
        return

    await state.set_state(
        AssistantStates.waiting_instagram_url
    )

    await callback.answer()

    await _safe_edit(
        callback,
        t("insta_prompt", lang),
        nano_assistant_input_keyboard("nano:assistant", lang),
    )


async def _handle_download(
    message: Message,
    state: FSMContext,
    *,
    validate_url,
    download_fn,
) -> None:
    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    if not message.text:
        await message.answer(t("download_invalid_url", lang))
        return

    url = message.text.strip()

    if not validate_url(url):
        await message.answer(t("download_invalid_url", lang))
        return

    await state.clear()

    status_message = await message.answer(
        t("download_in_progress", lang)
    )

    # MUHIM: havolaning o'zi (URL) hech qachon logga
    # yozilmaydi — faqat umumiy, xavfsiz xabarlar.
    result = await download_fn(url)

    if not result.ok:
        text_key = _ERROR_TEXT_KEYS.get(
            result.error_code, "download_failed"
        )

        try:
            await status_message.edit_text(t(text_key, lang))
        except Exception:
            await message.answer(t(text_key, lang))

        return

    try:
        video_file = FSInputFile(result.file_path)

        await message.answer_video(
            video_file,
            caption=(result.title or "")[:1024],
        )

        try:
            await status_message.delete()
        except Exception:
            pass

    except Exception:
        logger.exception(
            "Yuklab olingan videoni yuborishda xatolik."
        )

        try:
            await status_message.edit_text(
                t("download_failed", lang)
            )
        except Exception:
            pass

    finally:
        # Video Telegramga yuborilgach — vaqtinchalik fayl
        # DARHOL o'chiriladi. Hech qanday holatda diskda
        # qoldirilmaydi va PostgreSQL'ga yozilmaydi.
        cleanup_file(result.file_path)


@router.message(AssistantStates.waiting_youtube_url)
async def assistant_receive_youtube_url(
    message: Message,
    state: FSMContext,
) -> None:
    await _handle_download(
        message,
        state,
        validate_url=validate_youtube_url,
        download_fn=download_youtube,
    )


@router.message(AssistantStates.waiting_instagram_url)
async def assistant_receive_instagram_url(
    message: Message,
    state: FSMContext,
) -> None:
    await _handle_download(
        message,
        state,
        validate_url=validate_instagram_url,
        download_fn=download_instagram,
    )


__all__ = [
    "router",
    "AssistantStates",
]
