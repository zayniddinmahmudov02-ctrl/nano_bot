import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.database import AsyncSessionLocal
from app.keyboards.nano import nano_main_menu_keyboard
from app.services.user_service import get_user_language
from app.texts import t

logger = logging.getLogger(__name__)

router = Router()


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
                "Bosh menyu xabarini yangilab bo'lmadi."
            )


@router.callback_query(F.data == "nano:main")
async def nano_main_menu(
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
        t("main_menu_title", lang),
        nano_main_menu_keyboard(lang),
    )


__all__ = [
    "router",
]
