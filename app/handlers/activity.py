from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.database import AsyncSessionLocal
from app.keyboards.nano import (
    nano_activity_menu_keyboard,
    nano_activity_package_keyboard,
    nano_activity_receipt_cancel_keyboard,
    nano_settings_menu_keyboard,
)
from app.services.activity_service import (
    get_access_status,
    get_or_create_subscription,
    AccessStatus,
)
from app.services.exchange_rate_service import (
    convert_usd_to_uzs,
    get_exchange_rate,
)
from app.services.payment_service import (
    create_payment_request,
    get_package,
    send_payment_request_to_channel,
)
from app.services.user_service import (
    get_user_by_telegram_id,
    get_user_language,
)
from app.texts import t

logger = logging.getLogger(__name__)

router = Router()


class ActivityStates(StatesGroup):
    waiting_receipt = State()


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
                "Faollik xabarini yangilab bo'lmadi."
            )


def _format_uzs(amount: float) -> str:
    return f"{amount:,.0f}".replace(",", " ")


# ============================================================
# MENU
# ============================================================

@router.callback_query(F.data == "nano:activity")
async def nano_activity_menu(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()

    if callback.from_user is None:
        await callback.answer()
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        lang = await get_user_language(session, telegram_id)

        if user is None:
            await callback.answer(
                "❌ Foydalanuvchi topilmadi.",
                show_alert=True,
            )
            return

        subscription = await get_or_create_subscription(
            session,
            user.id,
        )

        await session.commit()

        status = get_access_status(subscription)
        expiry = subscription.activity_expires_at

    await callback.answer()

    if status == AccessStatus.TRIAL:
        status_text = t("activity_status_trial", lang)
    elif status == AccessStatus.ACTIVE:
        status_text = t("activity_status_active", lang)
    else:
        status_text = t("activity_status_expired", lang)

    lines = [
        t("activity_title", lang),
        "",
        status_text,
    ]

    if expiry is not None:
        lines.append(
            t(
                "activity_expiry_line",
                lang,
                date=expiry.strftime("%d.%m.%Y"),
            )
        )

    lines.append("")
    lines.append(t("activity_intro", lang))

    await _safe_edit(
        callback,
        "\n".join(lines),
        nano_activity_menu_keyboard(lang),
    )


# ============================================================
# PACKAGE DETAIL
# ============================================================

@router.callback_query(F.data.startswith("nano:activity:package:"))
async def nano_activity_package_detail(
    callback: CallbackQuery,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    package_key = callback.data.split(":")[-1]
    package = get_package(package_key)

    if package is None:
        await callback.answer("❌ Xatolik.", show_alert=True)
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    rate_snapshot = await get_exchange_rate()
    uzs_amount = convert_usd_to_uzs(
        package.usd_price,
        rate_snapshot.rate,
    )

    await callback.answer()

    text = t(
        "activity_package_detail",
        lang,
        label=package.label_uz,
        usd=package.usd_price,
        uzs=_format_uzs(uzs_amount),
    )

    await _safe_edit(
        callback,
        text,
        nano_activity_package_keyboard(package_key, lang),
    )


# ============================================================
# BUY (start receipt collection)
# ============================================================

@router.callback_query(F.data.startswith("nano:activity:buy:"))
async def nano_activity_buy_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    package_key = callback.data.split(":")[-1]
    package = get_package(package_key)

    if package is None:
        await callback.answer("❌ Xatolik.", show_alert=True)
        return

    telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    await state.set_state(ActivityStates.waiting_receipt)
    await state.update_data(package_key=package_key)

    await callback.answer()

    await _safe_edit(
        callback,
        t("activity_payment_instructions", lang),
        nano_activity_receipt_cancel_keyboard(lang),
    )


# ============================================================
# RECEIVE RECEIPT
# ============================================================

@router.message(ActivityStates.waiting_receipt)
async def activity_receive_receipt(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    package_key = data.get("package_key")
    package = get_package(package_key) if package_key else None

    telegram_id = int(message.from_user.id)

    async with AsyncSessionLocal() as session:
        lang = await get_user_language(session, telegram_id)

    if package is None:
        await state.clear()
        await message.answer(t("generic_error", lang))
        return

    receipt_file_id = None
    receipt_file_type = None

    if message.photo:
        receipt_file_id = message.photo[-1].file_id
        receipt_file_type = "photo"
    elif message.document:
        receipt_file_id = message.document.file_id
        receipt_file_type = "document"
    else:
        await message.answer(t("activity_receipt_invalid", lang))
        return

    rate_snapshot = await get_exchange_rate()
    uzs_amount = convert_usd_to_uzs(
        package.usd_price,
        rate_snapshot.rate,
    )

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(
            session,
            telegram_id,
        )

        if user is None:
            await state.clear()
            await message.answer(t("user_not_found", lang))
            return

        payment = await create_payment_request(
            session,
            user=user,
            package=package,
            uzs_amount=uzs_amount,
            exchange_rate=rate_snapshot.rate,
            receipt_file_id=receipt_file_id,
            receipt_file_type=receipt_file_type,
        )

        await session.commit()
        await session.refresh(payment)

        payment_id = payment.payment_id

    sent_ok = await send_payment_request_to_channel(
        message.bot,
        payment,
        user,
    )

    if not sent_ok:
        logger.warning(
            "To'lov so'rovi kanalga yuborilmadi "
            "(payment_id=%s) — PENDING holda DB'da qoladi.",
            payment_id,
        )

    await state.clear()

    logger.info(
        "Faollik to'lov so'rovi yaratildi: "
        "telegram_id=%s, payment_id=%s, package=%s",
        telegram_id,
        payment_id,
        package_key,
    )

    await message.answer(
        t("activity_request_sent", lang),
        reply_markup=nano_settings_menu_keyboard(lang),
    )


__all__ = [
    "router",
    "ActivityStates",
]
