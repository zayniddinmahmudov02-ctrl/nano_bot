from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import is_admin
from app.database import AsyncSessionLocal
from app.services.activity_service import get_or_create_subscription
from app.services.payment_service import (
    approve_payment,
    get_package,
    get_payment_by_payment_id,
    reject_payment,
)
from app.services.security_service import (
    SecuritySeverity,
    record_security_event,
)
from app.services.user_service import get_user_language
from app.texts import t

logger = logging.getLogger(__name__)

router = Router()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _guard_admin(callback: CallbackQuery) -> bool:
    """
    MUHIM (8/18-bo'lim — Callback security): to'lovlar kanalidagi
    "✅ Tasdiqlash"/"❌ Rad etish" tugmalarini FAQAT ADMIN_IDS
    ro'yxatidagi foydalanuvchi bosishi mumkin. Kanalda boshqa
    a'zolar ham xabarni ko'rishi mumkin bo'lsa-da, callback bu
    yerda mustaqil ravishda qayta tekshiriladi.
    """

    telegram_id = int(callback.from_user.id)

    if is_admin(telegram_id):
        return True

    await record_security_event(
        event_type="unauthorized_payment_approval_attempt",
        severity=SecuritySeverity.HIGH,
        safe_description=(
            "Admin bo'lmagan foydalanuvchi to'lov "
            "tasdiqlash/rad etish tugmasini bosishga urindi."
        ),
        source="payment_channel",
    )

    await callback.answer(
        "⛔ Sizda bu amalni bajarish huquqi yo'q.",
        show_alert=True,
    )

    return False


def _parse_payment_id(callback_data: str) -> str:
    return callback_data.split(":", 2)[-1]


async def _edit_channel_message(
    callback: CallbackQuery,
    extra_line: str,
) -> None:
    try:
        original = callback.message.html_text or ""
    except Exception:
        original = ""

    new_text = f"{original}\n\n{extra_line}" if original else extra_line

    try:
        if callback.message.photo or callback.message.document:
            await callback.message.edit_caption(
                caption=new_text,
                reply_markup=None,
            )
        else:
            await callback.message.edit_text(
                new_text,
                reply_markup=None,
            )
    except Exception:
        logger.exception(
            "To'lov kanalidagi kartani yangilab bo'lmadi."
        )


@router.callback_query(F.data.startswith("admin_pay:approve:"))
async def admin_payment_approve(callback: CallbackQuery) -> None:
    if not await _guard_admin(callback):
        return

    payment_id = _parse_payment_id(callback.data)
    admin_telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        payment = await get_payment_by_payment_id(
            session,
            payment_id,
        )

        if payment is None:
            await callback.answer(
                "❌ To'lov topilmadi.",
                show_alert=True,
            )
            return

        if payment.status != "PENDING":
            await callback.answer(
                "⚠️ Bu to'lov allaqachon ko'rib chiqilgan.",
                show_alert=True,
            )
            return

        package = get_package(payment.package)

        payment = await approve_payment(
            session,
            payment,
            admin_telegram_id,
        )

        subscription = await get_or_create_subscription(
            session,
            payment.user_id,
        )

        expiry = subscription.activity_expires_at
        target_telegram_id = payment.telegram_id

        await session.commit()

    await callback.answer("✅ Tasdiqlandi.")

    await _edit_channel_message(
        callback,
        f"✅ TASDIQLANDI (admin: <code>{admin_telegram_id}</code>)",
    )

    await record_security_event(
        event_type="payment_approved",
        severity=SecuritySeverity.MEDIUM,
        safe_description=(
            "Admin to'lovni tasdiqladi."
        ),
        source="payment_channel",
    )

    logger.info(
        "PAYMENT_APPROVED: payment_id=%s user_id=%s "
        "admin_id=%s",
        payment_id,
        payment.user_id,
        admin_telegram_id,
    )

    if target_telegram_id and expiry is not None:
        try:
            async with AsyncSessionLocal() as session:
                lang = await get_user_language(
                    session,
                    target_telegram_id,
                )

            await callback.bot.send_message(
                target_telegram_id,
                t(
                    "activity_approved_notification",
                    lang,
                    package=(
                        package.label_uz
                        if package is not None
                        else payment.package
                    ),
                    expiry=expiry.strftime("%d.%m.%Y"),
                ),
            )
        except Exception:
            logger.exception(
                "Userga tasdiqlash haqida xabar yuborilmadi "
                "(payment_id=%s).",
                payment_id,
            )


@router.callback_query(F.data.startswith("admin_pay:reject:"))
async def admin_payment_reject(callback: CallbackQuery) -> None:
    if not await _guard_admin(callback):
        return

    payment_id = _parse_payment_id(callback.data)
    admin_telegram_id = int(callback.from_user.id)

    async with AsyncSessionLocal() as session:
        payment = await get_payment_by_payment_id(
            session,
            payment_id,
        )

        if payment is None:
            await callback.answer(
                "❌ To'lov topilmadi.",
                show_alert=True,
            )
            return

        if payment.status != "PENDING":
            await callback.answer(
                "⚠️ Bu to'lov allaqachon ko'rib chiqilgan.",
                show_alert=True,
            )
            return

        payment = await reject_payment(
            session,
            payment,
            admin_telegram_id,
        )

        target_telegram_id = payment.telegram_id

        await session.commit()

    await callback.answer("❌ Rad etildi.")

    await _edit_channel_message(
        callback,
        f"❌ RAD ETILDI (admin: <code>{admin_telegram_id}</code>)",
    )

    await record_security_event(
        event_type="payment_rejected",
        severity=SecuritySeverity.MEDIUM,
        safe_description=(
            "Admin to'lovni rad etdi."
        ),
        source="payment_channel",
    )

    logger.info(
        "PAYMENT_REJECTED: payment_id=%s user_id=%s "
        "admin_id=%s",
        payment_id,
        payment.user_id,
        admin_telegram_id,
    )

    if target_telegram_id:
        try:
            async with AsyncSessionLocal() as session:
                lang = await get_user_language(
                    session,
                    target_telegram_id,
                )

            await callback.bot.send_message(
                target_telegram_id,
                t("activity_rejected_notification", lang),
            )
        except Exception:
            logger.exception(
                "Userga rad etish haqida xabar yuborilmadi "
                "(payment_id=%s).",
                payment_id,
            )


__all__ = [
    "router",
]
