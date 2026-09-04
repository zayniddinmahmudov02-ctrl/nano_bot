from __future__ import annotations

import asyncio
import logging
import sys
from html import escape as html_escape
from typing import Optional, Tuple

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.config import NANO_BOT_SYSTEMD_SERVICE, is_admin
from app.keyboards.admin import (
    admin_broadcast_confirm_keyboard,
    admin_broadcast_start_keyboard,
    admin_confirm_keyboard,
    admin_control_keyboard,
    admin_main_menu_keyboard,
    admin_simple_screen_keyboard,
    admin_user_detail_keyboard,
    admin_users_list_keyboard,
)
from app.keyboards.main import main_menu_keyboard
from app.services.admin_stats_service import (
    get_activity_stats,
    get_auto_reply_stats,
    get_first_message_stats,
    get_overview_stats,
    get_payment_stats,
    get_security_stats,
    get_user_detail,
    get_users_page,
)
from app.services.bot_settings_service import (
    get_bot_settings,
    set_maintenance_mode,
)
from app.services.broadcast_service import run_broadcast
from app.services.exchange_rate_service import get_exchange_rate
from app.services.health_service import get_system_status
from app.services.security_service import (
    SecuritySeverity,
    record_security_event,
)
from app.utils.logger import read_recent_log_lines

logger = logging.getLogger(__name__)

router = Router()

USERS_PAGE_SIZE = 5

CONTROL_CONFIRM_TEXTS = {
    "stop": "⚠️ Nano-Botni to‘xtatmoqchimisiz?",
    "restart": "⚠️ Nano-Botni qayta ishga tushirmoqchimisiz?",
    "start": "⚠️ Nano-Botni ishga tushirmoqchimisiz?",
}


class AdminStates(StatesGroup):
    waiting_broadcast_message = State()


# ============================================================
# GUARDS
# ============================================================

async def _guard_admin_message(message: Message) -> bool:
    telegram_id = int(message.from_user.id)

    if is_admin(telegram_id):
        return True

    await record_security_event(
        event_type="unauthorized_admin_access",
        severity=SecuritySeverity.HIGH,
        safe_description=(
            "Admin bo'lmagan foydalanuvchi /admin buyrug'ini "
            "ishlatishga urindi."
        ),
        source="admin_panel",
    )

    await message.answer(
        "⛔ Sizda admin huquqi mavjud emas."
    )

    return False


async def _guard_admin_callback(callback: CallbackQuery) -> bool:
    telegram_id = int(callback.from_user.id)

    if is_admin(telegram_id):
        return True

    await record_security_event(
        event_type="unauthorized_admin_access",
        severity=SecuritySeverity.HIGH,
        safe_description=(
            "Admin bo'lmagan foydalanuvchi admin panel "
            "callback'iga urindi."
        ),
        source="admin_panel",
    )

    await callback.answer(
        "⛔ Sizda admin huquqi mavjud emas.",
        show_alert=True,
    )

    return False


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
                "Admin panel xabarini yangilab bo'lmadi."
            )


# ============================================================
# RENDER HELPERS
# ============================================================

async def _render_stats_text() -> str:
    stats = await get_overview_stats()
    new_users = stats.new_users

    return (
        "📊 <b>NANO-BOT STATISTIKA</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stats.total_users}</b>\n"
        f"🟢 Faol foydalanuvchilar: "
        f"<b>{stats.active_users}</b>\n"
        f"📱 Ulangan Telegramlar: "
        f"<b>{stats.connected_accounts}</b>\n"
        f"🤖 Jami Auto Reply: "
        f"<b>{stats.total_auto_replies}</b>\n"
        f"🟢 Faol Auto Reply: "
        f"<b>{stats.active_auto_replies}</b>\n"
        f"💬 First Message: "
        f"<b>{stats.total_first_messages}</b>\n"
        f"⚡ Faol Faollik (pullik) userlar: "
        f"<b>{stats.active_activity_users}</b>\n"
        f"📨 Yuborilgan Auto Reply: "
        f"<b>{stats.auto_replies_sent}</b>\n"
        f"📩 Yuborilgan First Message: "
        f"<b>{stats.first_messages_sent}</b>\n"
        f"👥 Referral orqali kelganlar: "
        f"<b>{stats.referred_users}</b>\n"
        f"💳 To'lovlar: <b>{stats.total_payments}</b>\n"
        f"💰 Umumiy daromad: "
        f"<b>{stats.total_revenue:.2f} {stats.currency}</b>\n\n"
        "📈 <b>Yangi foydalanuvchilar:</b>\n"
        f"   • Bugun: <b>{new_users.today}</b>\n"
        f"   • 7 kun: <b>{new_users.last_7_days}</b>\n"
        f"   • 30 kun: <b>{new_users.last_30_days}</b>\n"
        f"   • Umumiy: <b>{new_users.all_time}</b>"
    )


async def _render_users_list(
    page: int,
) -> Tuple[str, list, int, int]:
    items, total, total_pages, page = await get_users_page(
        page,
        USERS_PAGE_SIZE,
    )

    if not items:
        return (
            "👥 <b>FOYDALANUVCHILAR</b>\n\n"
            "Hozircha foydalanuvchilar mavjud emas.",
            [],
            1,
            1,
        )

    lines = ["👥 <b>FOYDALANUVCHILAR</b>\n"]
    button_entries = []

    start_index = (page - 1) * USERS_PAGE_SIZE

    for offset, item in enumerate(items, start=1):
        idx = start_index + offset

        username = (
            f"@{html_escape(item.username)}"
            if item.username
            else "—"
        )

        display_name = html_escape(
            item.first_name or "—"
        )

        status_icon = "🟢" if item.active else "🔴"
        activity_icon = "⚡" if item.has_active_access else "—"
        fm_icon = "👋" if item.has_first_message else "—"
        registered = item.created_at.strftime("%d.%m.%Y")

        lines.append(
            f"<b>{idx}.</b> {status_icon} "
            f"{display_name} ({username})\n"
            f"    🆔 <code>{item.telegram_id}</code>\n"
            f"    📅 {registered} | "
            f"📱 {item.account_count} | "
            f"🤖 {item.auto_reply_count} | "
            f"{fm_icon} | {activity_icon}\n"
            f"    👥 Referral: {item.referral_count}\n"
        )

        button_entries.append(
            (
                item.id,
                f"🔍 {idx}. "
                f"{item.first_name or item.telegram_id}"[:40],
            )
        )

    lines.append(
        f"\n📄 Sahifa: {page}/{total_pages} (jami {total})"
    )

    return "\n".join(lines), button_entries, page, total_pages


async def _render_user_detail(
    user_id: int,
) -> Optional[str]:
    detail = await get_user_detail(user_id)

    if detail is None:
        return None

    username = (
        f"@{html_escape(detail.username)}"
        if detail.username
        else "—"
    )

    full_name = html_escape(
        f"{detail.first_name or ''} "
        f"{detail.last_name or ''}".strip()
        or "—"
    )

    status_label = (
        "🟢 Faol" if detail.active else "🔴 Faol emas"
    )

    if detail.has_first_message:
        fm_status = (
            "faol" if detail.first_message_active else "o‘chiq"
        )
        first_message_label = f"✅ bor ({fm_status})"
    else:
        first_message_label = "➖ yo‘q"

    referral_line = (
        f"👥 Referral: <b>{detail.referral_count}</b> taklif"
    )

    if detail.referred_by:
        referral_line += (
            f" | taklif qilgan: ID {detail.referred_by}"
        )

    return (
        "👤 <b>USER INFO</b>\n\n"
        f"ID: <code>{detail.telegram_id}</code>\n"
        f"Username: {username}\n"
        f"Ism: {full_name}\n"
        f"Til: {detail.language}\n"
        f"Ro‘yxatdan o‘tgan: "
        f"{detail.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"Holat: {status_label}\n\n"
        f"📱 Telegram accounts: "
        f"<b>{detail.account_count}</b> "
        f"({detail.connected_account_count} ulangan)\n"
        f"🤖 Auto Replies: "
        f"<b>{detail.auto_reply_count}</b> "
        f"({detail.active_auto_reply_count} faol)\n"
        f"1️⃣ First Message: {first_message_label}\n"
        f"⚡ Faollik: {detail.activity_status}\n"
        f"{referral_line}"
    )


async def _render_auto_reply_text() -> str:
    stats = await get_auto_reply_stats()

    if stats.top_keywords:
        keyword_lines = "\n".join(
            f"   {index}. {html_escape(keyword)} "
            f"({count})"
            for index, (keyword, count) in enumerate(
                stats.top_keywords, start=1
            )
        )
    else:
        keyword_lines = "   —"

    return (
        "🤖 <b>AUTO REPLIES</b>\n\n"
        f"Jami: <b>{stats.total}</b>\n"
        f"Active: <b>{stats.active}</b>\n"
        f"Inactive: <b>{stats.inactive}</b>\n"
        f"Messages sent: <b>{stats.messages_sent}</b>\n\n"
        "<b>Eng ko'p ishlatilgan kalit so'zlar:</b>\n"
        f"{keyword_lines}"
    )


async def _render_first_message_text() -> str:
    stats = await get_first_message_stats()

    return (
        "👋 <b>FIRST MESSAGE</b>\n\n"
        f"Jami: <b>{stats.total}</b>\n"
        f"Active: <b>{stats.active}</b>\n"
        f"Inactive: <b>{stats.inactive}</b>\n"
        f"Messages sent: <b>{stats.messages_sent}</b>"
    )


async def _render_activity_text() -> str:
    stats = await get_activity_stats()

    return (
        "⚡ <b>FAOLLIK</b>\n\n"
        f"🎁 Trial (faol): <b>{stats.trial_users}</b>\n"
        f"🟢 Pullik Faollik (faol): "
        f"<b>{stats.active_paid_users}</b>\n"
        f"⏳ Tez orada tugaydi (7 kun ichida): "
        f"<b>{stats.expiring_soon}</b>\n"
        f"💰 Tasdiqlangan tushum: "
        f"<b>${stats.approved_revenue:.2f}</b>"
    )


async def _render_payments_text() -> str:
    stats = await get_payment_stats()
    rate = await get_exchange_rate()

    if stats.package_breakdown:
        package_lines = "\n".join(
            f"   {item.label}: {item.count}"
            for item in stats.package_breakdown
        )
    else:
        package_lines = "   —"

    return (
        "💳 <b>TO'LOVLAR STATISTIKASI</b>\n\n"
        f"📊 Jami: <b>{stats.total}</b>\n"
        f"⏳ Kutilmoqda: <b>{stats.pending}</b>\n"
        f"✅ Tasdiqlangan: <b>{stats.approved}</b>\n"
        f"❌ Rad etilgan: <b>{stats.rejected}</b>\n\n"
        f"💰 <b>Tasdiqlangan tushum:</b>\n"
        f"${stats.approved_revenue:.2f}\n\n"
        f"📦 <b>Paketlar:</b>\n{package_lines}\n\n"
        f"📅 Bugun: 💵 ${stats.today_revenue:.2f} "
        f"({stats.today_count} ta)\n"
        f"📅 Shu oy: {stats.month_count} ta\n\n"
        f"💱 <b>USD → UZS kursi:</b> "
        f"{rate.rate:,.0f} ({rate.source})\n"
        f"🕐 Yangilangan: "
        f"{rate.fetched_at:%d.%m.%Y %H:%M} UTC"
    ).replace(",", " ")


async def _render_security_text() -> str:
    stats = await get_security_stats()

    status_line = (
        "🟢 System Security: OK"
        if stats.recent_critical_24h == 0
        else "🟠 System Security: Diqqat talab qilinadi"
    )

    lines = [
        "🔐 <b>SECURITY</b>\n",
        status_line,
        "",
        f"🚨 High Events: <b>{stats.high_count}</b>",
        f"🚨 Critical Events: <b>{stats.critical_count}</b>",
        "",
        "<b>Oxirgi hodisalar:</b>",
    ]

    if not stats.recent_events:
        lines.append("— hodisalar yo‘q —")
    else:
        for event in stats.recent_events:
            time_label = event.created_at.strftime(
                "%d.%m %H:%M"
            )

            lines.append(
                f"• {time_label} [{event.severity}] "
                f"{html_escape(event.event_type)}\n"
                f"  {html_escape(event.safe_description)}"
            )

    return "\n".join(lines)


async def _render_control_text() -> str:
    settings = await get_bot_settings()

    mode_label = (
        "🛠 MAINTENANCE"
        if settings.maintenance_mode
        else "🟢 RUNNING"
    )

    lines = [
        "🛑 <b>BOTNI BOSHQARISH</b>\n",
        f"🔘 Bot holati: <b>{mode_label}</b>\n",
        "🖥 <b>SYSTEM STATUS</b>",
    ]

    try:
        components = await get_system_status()

        for component in components:
            detail = (
                f" — {component.detail}"
                if component.detail
                else ""
            )
            lines.append(
                f"{component.status} {component.name}"
                f"{detail}"
            )

    except Exception:
        logger.exception(
            "System status'ni olishda xatolik."
        )
        lines.append("⚠️ Holatni olib bo'lmadi.")

    return "\n".join(lines)


# ============================================================
# SYSTEMD CONTROL (ixtiyoriy, faqat sozlangan bo'lsa ishlaydi)
# ============================================================

async def _run_systemd_action(
    action: str,
) -> Tuple[bool, str]:
    if not NANO_BOT_SYSTEMD_SERVICE:
        return False, (
            "⚠️ Bu funksiya sozlanmagan.\n\n"
            "Serverda <code>NANO_BOT_SYSTEMD_SERVICE</code> "
            "muhit o'zgaruvchisini nano_bot xizmati nomiga "
            "o'rnating (masalan: <code>nano_bot.service</code>)."
        )

    if not sys.platform.startswith("linux"):
        return False, (
            "⚠️ Bu funksiya faqat Linux/systemd serverida "
            "ishlaydi."
        )

    try:
        process = await asyncio.create_subprocess_exec(
            "systemctl",
            action,
            NANO_BOT_SYSTEMD_SERVICE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=15,
        )

        if process.returncode == 0:
            return True, (
                f"✅ <code>systemctl {action} "
                f"{NANO_BOT_SYSTEMD_SERVICE}</code> "
                "muvaffaqiyatli bajarildi."
            )

        error_text = html_escape(
            stderr.decode(errors="replace").strip()[:300]
        )

        return False, (
            f"❌ systemctl {action} xato qaytardi.\n\n"
            f"<code>{error_text}</code>"
        )

    except asyncio.TimeoutError:
        return False, (
            "❌ Buyruq vaqt tugashi bilan yakunlandi."
        )

    except FileNotFoundError:
        return False, "❌ systemctl topilmadi."

    except Exception:
        logger.exception(
            "systemctl %s xatosi.",
            action,
        )
        return False, (
            "❌ Buyruqni bajarishda kutilmagan xatolik "
            "yuz berdi."
        )


# ============================================================
# ENTRY
# ============================================================

@router.message(Command("admin"))
async def admin_entry(
    message: Message,
    state: FSMContext,
) -> None:
    if not await _guard_admin_message(message):
        return

    await state.clear()

    await record_security_event(
        event_type="admin_panel_access",
        severity=SecuritySeverity.LOW,
        safe_description="Admin panelga kirildi.",
        source="admin_panel",
    )

    await message.answer(
        "👑 <b>ADMIN PANEL</b>",
        reply_markup=admin_main_menu_keyboard(),
    )


@router.callback_query(F.data == "admin:noop")
async def admin_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "admin:home")
async def admin_home(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not await _guard_admin_callback(callback):
        return

    await state.clear()
    await callback.answer()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        "🏠 <b>Bosh menyu</b>",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "admin:menu")
async def admin_menu(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not await _guard_admin_callback(callback):
        return

    await state.clear()
    await callback.answer()

    await _safe_edit(
        callback,
        "👑 <b>ADMIN PANEL</b>",
        admin_main_menu_keyboard(),
    )


# ============================================================
# 6.1 STATISTICS
# ============================================================

@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery) -> None:
    if not await _guard_admin_callback(callback):
        return

    await callback.answer()

    text = await _render_stats_text()

    await _safe_edit(
        callback,
        text,
        admin_simple_screen_keyboard(),
    )


# ============================================================
# 6.2 USERS
# ============================================================

@router.callback_query(F.data.startswith("admin:users:page:"))
async def admin_users_list(callback: CallbackQuery) -> None:
    if not await _guard_admin_callback(callback):
        return

    try:
        page = int(callback.data.split(":")[-1])
    except ValueError:
        page = 1

    await callback.answer()

    text, button_entries, page, total_pages = (
        await _render_users_list(page)
    )

    keyboard = admin_users_list_keyboard(
        button_entries,
        page,
        total_pages,
    )

    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("admin:users:view:"))
async def admin_user_view(callback: CallbackQuery) -> None:
    if not await _guard_admin_callback(callback):
        return

    parts = callback.data.split(":")

    try:
        user_id = int(parts[3])
        page = int(parts[4])
    except (IndexError, ValueError):
        await callback.answer(
            "❌ Xatolik.",
            show_alert=True,
        )
        return

    await callback.answer()

    text = await _render_user_detail(user_id)

    if text is None:
        text = "❌ Foydalanuvchi topilmadi."

    await _safe_edit(
        callback,
        text,
        admin_user_detail_keyboard(page),
    )


# ============================================================
# 6.3 AUTO REPLIES
# ============================================================

@router.callback_query(F.data == "admin:autoreplies")
async def admin_auto_replies(callback: CallbackQuery) -> None:
    if not await _guard_admin_callback(callback):
        return

    await callback.answer()

    text = await _render_auto_reply_text()

    await _safe_edit(
        callback,
        text,
        admin_simple_screen_keyboard(),
    )


# ============================================================
# FIRST MESSAGE
# ============================================================

@router.callback_query(F.data == "admin:firstmessage")
async def admin_first_message(callback: CallbackQuery) -> None:
    if not await _guard_admin_callback(callback):
        return

    await callback.answer()

    text = await _render_first_message_text()

    await _safe_edit(
        callback,
        text,
        admin_simple_screen_keyboard(),
    )


# ============================================================
# 6.4 FAOLLIK (ACTIVITY)
# ============================================================

@router.callback_query(F.data == "admin:activity")
async def admin_activity(callback: CallbackQuery) -> None:
    if not await _guard_admin_callback(callback):
        return

    await callback.answer()

    text = await _render_activity_text()

    await _safe_edit(
        callback,
        text,
        admin_simple_screen_keyboard(),
    )


# ============================================================
# 6.5 PAYMENTS
# ============================================================

@router.callback_query(F.data == "admin:payments")
async def admin_payments(callback: CallbackQuery) -> None:
    if not await _guard_admin_callback(callback):
        return

    await callback.answer()

    text = await _render_payments_text()

    await _safe_edit(
        callback,
        text,
        admin_simple_screen_keyboard(),
    )


# ============================================================
# 6.6 BROADCAST
# ============================================================

@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not await _guard_admin_callback(callback):
        return

    await callback.answer()

    await state.set_state(
        AdminStates.waiting_broadcast_message
    )

    await _safe_edit(
        callback,
        "📢 <b>Broadcast</b>\n\n"
        "Barcha foydalanuvchilarga yuboriladigan xabar "
        "matnini kiriting.",
        admin_broadcast_start_keyboard(),
    )


@router.message(AdminStates.waiting_broadcast_message)
async def admin_broadcast_receive(
    message: Message,
    state: FSMContext,
) -> None:
    if not await _guard_admin_message(message):
        await state.clear()
        return

    if not message.text:
        await message.answer(
            "❌ Iltimos, faqat matn ko'rinishida yuboring."
        )
        return

    text = message.text.strip()

    if not text:
        await message.answer(
            "❌ Xabar bo'sh bo'lishi mumkin emas."
        )
        return

    if len(text) > 3500:
        await message.answer(
            "❌ Xabar juda uzun "
            "(maksimal 3500 belgi)."
        )
        return

    await state.update_data(broadcast_text=text)

    await message.answer(
        "📢 <b>Xabar preview:</b>\n\n"
        f"{text}\n\n"
        "⚠️ Xabar barcha foydalanuvchilarga yuboriladi.",
        reply_markup=admin_broadcast_confirm_keyboard(),
    )


@router.callback_query(F.data == "admin:broadcast:cancel")
async def admin_broadcast_cancel(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not await _guard_admin_callback(callback):
        return

    await state.clear()
    await callback.answer("❌ Bekor qilindi.")

    await _safe_edit(
        callback,
        "❌ Broadcast bekor qilindi.",
        admin_simple_screen_keyboard(),
    )


@router.callback_query(F.data == "admin:broadcast:confirm")
async def admin_broadcast_confirm(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not await _guard_admin_callback(callback):
        return

    data = await state.get_data()
    text = data.get("broadcast_text")

    await state.clear()

    if not text:
        await callback.answer(
            "❌ Xabar topilmadi. Qaytadan boshlang.",
            show_alert=True,
        )
        return

    await callback.answer("📢 Boshlandi.")

    await _safe_edit(
        callback,
        "📢 Broadcast boshlandi.\n\n"
        "Yakunlanganda natija haqida xabar beriladi.",
        admin_simple_screen_keyboard(),
    )

    await record_security_event(
        event_type="admin_broadcast",
        severity=SecuritySeverity.MEDIUM,
        safe_description=(
            f"Admin broadcast yubordi ({len(text)} belgi)."
        ),
        source="admin_panel",
    )

    asyncio.create_task(
        run_broadcast(
            callback.bot,
            callback.from_user.id,
            text,
        )
    )


# ============================================================
# 6.7 SECURITY
# ============================================================

@router.callback_query(F.data == "admin:security")
async def admin_security(callback: CallbackQuery) -> None:
    if not await _guard_admin_callback(callback):
        return

    await callback.answer()

    text = await _render_security_text()

    await _safe_edit(
        callback,
        text,
        admin_simple_screen_keyboard(),
    )


# ============================================================
# 6.8 LOGS
# ============================================================

@router.callback_query(F.data == "admin:logs")
async def admin_logs(callback: CallbackQuery) -> None:
    if not await _guard_admin_callback(callback):
        return

    await callback.answer()

    content = read_recent_log_lines(max_chars=3000)
    escaped = html_escape(content)

    if len(escaped) > 3800:
        escaped = escaped[-3800:]

    text = "📜 <b>LOGLAR</b>\n\n<code>" + escaped + "</code>"

    await _safe_edit(
        callback,
        text,
        admin_simple_screen_keyboard(),
    )


# ============================================================
# 6.9 BOT CONTROL
# ============================================================

@router.callback_query(F.data == "admin:control")
async def admin_control(callback: CallbackQuery) -> None:
    if not await _guard_admin_callback(callback):
        return

    await callback.answer()

    text = await _render_control_text()
    settings = await get_bot_settings()

    await _safe_edit(
        callback,
        text,
        admin_control_keyboard(settings.maintenance_mode),
    )


@router.callback_query(
    F.data == "admin:control:maintenance:toggle"
)
async def admin_toggle_maintenance(
    callback: CallbackQuery,
) -> None:
    if not await _guard_admin_callback(callback):
        return

    settings = await get_bot_settings(force_refresh=True)
    new_value = not settings.maintenance_mode
    settings = await set_maintenance_mode(new_value)

    await callback.answer(
        "🛠 Maintenance yoqildi."
        if new_value
        else "🟢 Maintenance o'chirildi."
    )

    await record_security_event(
        event_type="admin_maintenance_toggle",
        severity=SecuritySeverity.MEDIUM,
        safe_description=(
            "Admin maintenance mode'ni "
            + ("yoqdi." if new_value else "o‘chirdi.")
        ),
        source="admin_panel",
    )

    text = await _render_control_text()

    await _safe_edit(
        callback,
        text,
        admin_control_keyboard(settings.maintenance_mode),
    )


@router.callback_query(
    F.data.in_(
        {
            "admin:control:stop:ask",
            "admin:control:restart:ask",
            "admin:control:start:ask",
        }
    )
)
async def admin_control_ask(callback: CallbackQuery) -> None:
    if not await _guard_admin_callback(callback):
        return

    action = callback.data.split(":")[2]

    await callback.answer()

    text = CONTROL_CONFIRM_TEXTS.get(
        action,
        "⚠️ Ushbu amalni bajarmoqchimisiz?",
    )

    keyboard = admin_confirm_keyboard(
        yes_callback=f"admin:control:{action}:yes",
        no_callback=f"admin:control:{action}:no",
    )

    await _safe_edit(callback, text, keyboard)


@router.callback_query(
    F.data.in_(
        {
            "admin:control:stop:no",
            "admin:control:restart:no",
            "admin:control:start:no",
        }
    )
)
async def admin_control_cancel(callback: CallbackQuery) -> None:
    if not await _guard_admin_callback(callback):
        return

    await callback.answer("❌ Bekor qilindi.")

    text = await _render_control_text()
    settings = await get_bot_settings()

    await _safe_edit(
        callback,
        text,
        admin_control_keyboard(settings.maintenance_mode),
    )


@router.callback_query(
    F.data.in_(
        {
            "admin:control:stop:yes",
            "admin:control:restart:yes",
            "admin:control:start:yes",
        }
    )
)
async def admin_control_execute(
    callback: CallbackQuery,
) -> None:
    if not await _guard_admin_callback(callback):
        return

    action = callback.data.split(":")[2]

    await callback.answer("⏳ Bajarilmoqda...")

    ok, result_message = await _run_systemd_action(action)

    await record_security_event(
        event_type=f"admin_bot_{action}",
        severity=(
            SecuritySeverity.HIGH
            if ok
            else SecuritySeverity.MEDIUM
        ),
        safe_description=(
            f"Admin '{action}' amalini bajarishga urindi. "
            f"Natija: "
            + ("muvaffaqiyatli." if ok else "amalga oshmadi.")
        ),
        source="admin_panel",
    )

    text = await _render_control_text()
    settings = await get_bot_settings()

    full_text = f"{result_message}\n\n{text}"

    await _safe_edit(
        callback,
        full_text,
        admin_control_keyboard(settings.maintenance_mode),
    )


__all__ = [
    "router",
    "AdminStates",
]
