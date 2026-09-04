from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from aiogram import Bot
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    PAYMENT_CARD_NUMBER,
    PAYMENT_CARD_TYPE,
    PAYMENT_CHANNEL_ID,
)
from app.database import AsyncSessionLocal
from app.database.models import Payment, User
from app.services.activity_service import grant_activity

logger = logging.getLogger(__name__)

STATUS_PENDING = "PENDING"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"
STATUS_CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class ActivityPackage:
    key: str
    duration_days: int
    usd_price: float
    label_uz: str


# MUHIM: narxlar spec bo'yicha QATTIQ belgilangan (hardcode) —
# bular Faollik narxlari, valyuta kursi emas (kurs alohida,
# exchange_rate_service orqali dinamik olinadi).
ACTIVITY_PACKAGES = {
    "1m": ActivityPackage("1m", 30, 1.00, "1 oy"),
    "3m": ActivityPackage("3m", 90, 2.50, "3 oy"),
    "6m": ActivityPackage("6m", 180, 4.00, "6 oy"),
    "1y": ActivityPackage("1y", 365, 6.00, "1 yil"),
}

PACKAGE_ORDER = ("1m", "3m", "6m", "1y")


def get_package(key: str) -> Optional[ActivityPackage]:
    return ACTIVITY_PACKAGES.get(key)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_payment_id() -> str:
    return uuid.uuid4().hex[:16]


async def create_payment_request(
    session: AsyncSession,
    *,
    user: User,
    package: ActivityPackage,
    uzs_amount: float,
    exchange_rate: float,
    receipt_file_id: Optional[str],
    receipt_file_type: Optional[str],
) -> Payment:
    payment = Payment(
        user_id=user.id,
        telegram_id=user.telegram_id,
        amount=package.usd_price,
        currency="USD",
        status=STATUS_PENDING,
        payment_id=generate_payment_id(),
        package=package.key,
        duration_days=package.duration_days,
        usd_amount=package.usd_price,
        uzs_amount=uzs_amount,
        exchange_rate=exchange_rate,
        receipt_file_id=receipt_file_id,
        receipt_file_type=receipt_file_type,
    )

    session.add(payment)
    await session.flush()

    return payment


def _payment_channel_configured() -> bool:
    return bool(PAYMENT_CHANNEL_ID)


def _build_request_caption(
    payment: Payment,
    user: User,
    package: ActivityPackage,
) -> str:
    display_name = (
        user.first_name
        or user.username
        or str(user.telegram_id)
    )

    sent_at = payment.created_at or _now()

    return (
        "💳 <b>YANGI FAOLLIK TO'LOVI</b>\n\n"
        f"👤 User: {display_name}\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"📦 Paket: {package.label_uz}\n"
        f"💵 USD: ${package.usd_price:.2f}\n"
        f"🇺🇿 UZS: ~{payment.uzs_amount:,.0f} so'm\n"
        f"💳 {PAYMENT_CARD_TYPE}: "
        f"<code>{PAYMENT_CARD_NUMBER}</code>\n\n"
        f"📅 Yuborilgan vaqt: "
        f"{sent_at:%d.%m.%Y %H:%M} UTC\n"
        f"🧾 Payment ID: <code>{payment.payment_id}</code>\n"
        f"⏳ Status: {payment.status}"
    ).replace(",", " ")


def _approve_reject_keyboard(
    payment_id: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data=f"admin_pay:approve:{payment_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"admin_pay:reject:{payment_id}",
                ),
            ],
        ]
    )


async def send_payment_request_to_channel(
    bot: Bot,
    payment: Payment,
    user: User,
) -> bool:
    """
    Yangi to'lov so'rovini to'lovlar kanaliga yuboradi (chek/
    skrinshot bo'lsa — u bilan birga). Kanaldagi kartaning
    message_id'si keyinchalik tasdiqlash/rad etishda xabarni
    tahrirlash uchun `payment.admin_channel_message_id`ga
    yoziladi.

    MUHIM: bu Bot API orqali botning O'Z to'lovlar kanaliga
    yuborilayotgan oddiy xabar — Storage Channel/Telethon
    arxitekturasi bilan aloqasi yo'q (u faqat foydalanuvchining
    shaxsiy Auto Reply/First Message medialariga tegishli).
    """

    if not _payment_channel_configured():
        logger.warning(
            "PAYMENT_CHANNEL_ID sozlanmagan — to'lov so'rovi "
            "kanalga yuborilmadi (payment_id=%s).",
            payment.payment_id,
        )
        return False

    package = get_package(payment.package)

    if package is None:
        logger.error(
            "Noma'lum paket kaliti: %s (payment_id=%s)",
            payment.package,
            payment.payment_id,
        )
        return False

    caption = _build_request_caption(payment, user, package)
    keyboard = _approve_reject_keyboard(payment.payment_id)

    try:
        if payment.receipt_file_id:
            if payment.receipt_file_type == "photo":
                sent = await bot.send_photo(
                    PAYMENT_CHANNEL_ID,
                    payment.receipt_file_id,
                    caption=caption,
                    reply_markup=keyboard,
                )
            else:
                sent = await bot.send_document(
                    PAYMENT_CHANNEL_ID,
                    payment.receipt_file_id,
                    caption=caption,
                    reply_markup=keyboard,
                )
        else:
            sent = await bot.send_message(
                PAYMENT_CHANNEL_ID,
                caption,
                reply_markup=keyboard,
            )

        async with AsyncSessionLocal() as session:
            db_payment = await session.get(Payment, payment.id)

            if db_payment is not None:
                db_payment.admin_channel_message_id = (
                    sent.message_id
                )
                await session.commit()

        return True

    except Exception:
        # MUHIM: to'lovlar kanaliga yuborishda xatolik (masalan
        # bot kanalga admin emas) userning to'lov so'rovini
        # yo'qotmasligi kerak — Payment PENDING holda DB'da
        # qoladi, faqat xavfsiz log yoziladi.
        logger.exception(
            "To'lov so'rovini kanalga yuborishda xatolik "
            "(payment_id=%s).",
            payment.payment_id,
        )
        return False


async def get_payment_by_payment_id(
    session: AsyncSession,
    payment_id: str,
) -> Optional[Payment]:
    result = await session.execute(
        select(Payment).where(Payment.payment_id == payment_id)
    )

    return result.scalar_one_or_none()


async def approve_payment(
    session: AsyncSession,
    payment: Payment,
    admin_telegram_id: int,
) -> Payment:
    package = get_package(payment.package)

    duration_days = (
        package.duration_days
        if package is not None
        else (payment.duration_days or 0)
    )

    await grant_activity(
        session,
        user_id=payment.user_id,
        duration_days=duration_days,
    )

    payment.status = STATUS_APPROVED
    payment.approved_at = _now()
    payment.approved_by = admin_telegram_id

    await session.flush()

    return payment


async def reject_payment(
    session: AsyncSession,
    payment: Payment,
    admin_telegram_id: int,
) -> Payment:
    payment.status = STATUS_REJECTED
    payment.rejected_at = _now()
    payment.approved_by = admin_telegram_id

    await session.flush()

    return payment


async def count_pending_for_user(
    session: AsyncSession,
    user_id: int,
) -> int:
    result = await session.execute(
        select(func.count(Payment.id)).where(
            Payment.user_id == user_id,
            Payment.status == STATUS_PENDING,
        )
    )

    return result.scalar_one()


__all__ = [
    "STATUS_PENDING",
    "STATUS_APPROVED",
    "STATUS_REJECTED",
    "STATUS_CANCELLED",
    "ActivityPackage",
    "ACTIVITY_PACKAGES",
    "PACKAGE_ORDER",
    "get_package",
    "generate_payment_id",
    "create_payment_request",
    "send_payment_request_to_channel",
    "get_payment_by_payment_id",
    "approve_payment",
    "reject_payment",
    "count_pending_for_user",
]
