from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Set

from sqlalchemy import select
from telethon import events

from app.database import AsyncSessionLocal
from app.database.models import (
    FirstMessage,
    FirstMessageContact,
    Statistics,
    TelegramAccount,
    User,
)
from app.services.media_service import send_stored_post
from app.services.telegram_event_filters import (
    get_peer_display_info,
    is_private_incoming_event,
    validate_private_user_event,
)
from app.services.unanswered_chat_service import (
    mark_answered,
    record_outgoing_message,
)
from app.services.user_stats_service import (
    FIRST_MESSAGE_EVENT,
    record_statistics_event,
)
from app.telegram.user_client import telegram_client_manager

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 3600


class FirstMessageEngine:
    """
    Foydalanuvchining shaxsiy Telegram akkauntiga birinchi marta
    (yoki sozlangan interval o'tgandan keyin qayta) yozgan
    kontaktlarga avtomatik First Message yuboradi.

    MUHIM:
    First Message har bir kelgan xabarga javob bermaydi —
    faqat tanlangan interval o'tganidan keyin qayta trigger bo'ladi.
    """

    def __init__(self) -> None:
        self._handlers: Dict[int, object] = {}
        self._active_accounts: Set[int] = set()

    # =====================================================
    # DATABASE
    # =====================================================

    async def _get_connected_accounts(self):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(
                    TelegramAccount.id,
                    TelegramAccount.user_id,
                    TelegramAccount.telegram_id,
                )
                .join(
                    User,
                    User.id == TelegramAccount.user_id,
                )
                .where(
                    TelegramAccount.status == "connected",
                )
            )

            return result.all()

    async def _get_active_first_message(
        self,
        session,
        db_user_id: int,
    ) -> Optional[dict]:
        result = await session.execute(
            select(FirstMessage).where(
                FirstMessage.user_id == db_user_id,
                FirstMessage.active.is_(True),
            )
        )

        first_message = result.scalar_one_or_none()

        if first_message is None:
            return None

        return {
            "id": first_message.id,
            "message_type": first_message.message_type,
            "text": first_message.text,
            "file_id": first_message.file_id,
            "link": first_message.link,
            "storage_chat_id": first_message.storage_chat_id,
            "storage_message_id": first_message.storage_message_id,
            "repeat_interval_seconds": (
                first_message.repeat_interval_seconds
                or DEFAULT_INTERVAL_SECONDS
            ),
        }

    async def _get_or_create_contact(
        self,
        session,
        db_user_id: int,
        telegram_account_id: int,
        peer_id: int,
    ) -> FirstMessageContact:
        result = await session.execute(
            select(FirstMessageContact).where(
                FirstMessageContact.telegram_account_id
                == telegram_account_id,
                FirstMessageContact.peer_id == peer_id,
            )
        )

        contact = result.scalar_one_or_none()

        if contact is None:
            contact = FirstMessageContact(
                user_id=db_user_id,
                telegram_account_id=telegram_account_id,
                peer_id=peer_id,
            )

            session.add(contact)
            await session.flush()

        return contact

    # =====================================================
    # STORAGE SOURCE STATUS
    # =====================================================

    async def _mark_needs_resave(
        self,
        first_message_id: Optional[int],
    ) -> None:
        """
        Storage Channel/post endi topilmayotganda chaqiriladi
        (spec 12-bo'lim, AutoReplyEngine bilan bir xil qoida).
        Record o'CHIRILMAYDI — faqat `source_status =
        NEEDS_RESAVE` deb belgilanadi.
        """

        if first_message_id is None:
            return

        try:
            async with AsyncSessionLocal() as session:
                first_message = await session.get(
                    FirstMessage,
                    first_message_id,
                )

                if first_message is None:
                    return

                if first_message.source_status != "NEEDS_RESAVE":
                    first_message.source_status = "NEEDS_RESAVE"
                    await session.commit()

        except Exception:
            logger.exception(
                "First Message source_status'ni NEEDS_RESAVE "
                "deb belgilashda xatolik: first_message_id=%s",
                first_message_id,
            )

    # =====================================================
    # STATISTICS
    # =====================================================

    async def _update_statistics(
        self,
        db_user_id: int,
    ) -> None:
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Statistics).where(
                        Statistics.user_id == db_user_id
                    )
                )

                statistics = result.scalar_one_or_none()

                if statistics is None:
                    statistics = Statistics(
                        user_id=db_user_id,
                        replied_people=0,
                        auto_replies=0,
                        first_messages_sent=0,
                    )

                    session.add(statistics)

                statistics.first_messages_sent += 1

                # "Bugun/7 kun/30 kun" statistikasi uchun
                # yengil hodisa yozuvi (xabar mazmuni emas).
                await record_statistics_event(
                    session,
                    db_user_id,
                    FIRST_MESSAGE_EVENT,
                )

                await session.commit()

        except Exception:
            logger.exception(
                "First message statistikasi yangilanmadi."
            )

    # =====================================================
    # SEND
    # =====================================================

    async def _send_first_message(
        self,
        client,
        target_chat_id: int,
        first_message: dict,
        telegram_account_id: Optional[int] = None,
        db_user_id: Optional[int] = None,
    ) -> bool:
        try:
            storage_chat_id = first_message["storage_chat_id"]
            storage_message_id = first_message["storage_message_id"]

            if storage_chat_id and storage_message_id:
                result = await send_stored_post(
                    telethon_client=client,
                    storage_chat_id=storage_chat_id,
                    storage_message_id=storage_message_id,
                    target_chat_id=target_chat_id,
                    user_id=db_user_id,
                    account_id=telegram_account_id,
                )

                logger.info(
                    "first_message_send: first_message_id=%s, "
                    "account_id=%s, peer_id=%s, "
                    "storage_chat_id=%s, storage_message_id=%s, "
                    "result=%s",
                    first_message.get("id"),
                    telegram_account_id,
                    target_chat_id,
                    storage_chat_id,
                    storage_message_id,
                    "success" if result.success else "failed",
                )

                if not result.success and result.not_found:
                    # MUHIM (spec 12-bo'lim, Auto Reply bilan bir
                    # xil qoida): record o'chirilmaydi, faqat
                    # NEEDS_RESAVE deb belgilanadi.
                    await self._mark_needs_resave(
                        first_message.get("id")
                    )

                return result.success

            # MUHIM: bu yerga faqat Storage Channel'ga hali
            # ko'chirilmagan ESKI (legacy) yozuvlar tushadi
            # (storage_chat_id/storage_message_id yo'q).
            #
            # Eski yozuvlarda saqlangan file_id — Telegram Bot
            # API file_id, Telethon uchun yaroqsiz. Uni
            # client.send_file()'ga to'g'ridan-to'g'ri uzatish
            # doimo:
            #   ValueError: Failed to convert ... to media
            # xatosiga olib keladi. Shu sababli bunday urinish
            # butunlay OLIB TASHLANDI — matn bo'lsa xavfsiz
            # yuboriladi, media bo'lsa xavfsiz "skip" qilinadi
            # va logga yoziladi.
            message_type = first_message["message_type"]
            text = first_message["text"]

            if message_type == "text":
                if not text:
                    return False

                await client.send_message(
                    target_chat_id,
                    text,
                )
                return True

            logger.warning(
                "Legacy First Message (id=%s) uchun Storage "
                "reference topilmadi — eski Bot API file_id "
                "Telethon orqali yuborilmaydi. First Message'ni "
                "tahrirlash orqali qayta saqlang.",
                first_message.get("id"),
            )
            return False

        except Exception:
            logger.exception(
                "First message yuborishda xatolik."
            )
            return False

    # =====================================================
    # ACCOUNT LISTENER
    # =====================================================

    async def _start_account(
        self,
        db_user_id: int,
        telegram_id: int,
        telegram_account_id: int,
    ) -> bool:
        if telegram_id in self._active_accounts:
            return True

        client = telegram_client_manager.get_client(telegram_id)

        if client is None:
            logger.warning(
                "First message: Telegram client topilmadi: %s",
                telegram_id,
            )
            return False

        try:
            if not client.is_connected():
                await client.connect()

            if not await client.is_user_authorized():
                logger.warning(
                    "First message: akkaunt avtorizatsiyadan "
                    "o'tmagan: %s",
                    telegram_id,
                )
                return False

            # MUHIM: `func=` — Telethon darajasidagi ARZON,
            # sinxron filter. Guruh/superguruh/kanal xabarlari
            # va o'zimiz yuborgan xabarlar `_handle_message()`
            # chaqirilishidan OLDIN chetlab o'tiladi (keraksiz
            # task yaratilmaydi). To'liq (sender turi kabi)
            # tekshiruv baribir `_handle_message()` ichida ham
            # qayta bajariladi — bu ikkinchi, defensiv qatlam.
            @client.on(
                events.NewMessage(
                    incoming=True,
                    func=is_private_incoming_event,
                )
            )
            async def handle_new_message(event):
                await self._handle_message(
                    db_user_id=db_user_id,
                    telegram_id=telegram_id,
                    telegram_account_id=telegram_account_id,
                    event=event,
                )

            self._handlers[telegram_id] = handle_new_message
            self._active_accounts.add(telegram_id)

            logger.info(
                "First message listener ishga tushdi: %s",
                telegram_id,
            )

            return True

        except Exception:
            logger.exception(
                "First message listener ishga tushmadi: %s",
                telegram_id,
            )
            return False

    async def _handle_message(
        self,
        db_user_id: int,
        telegram_id: int,
        telegram_account_id: int,
        event,
    ) -> None:
        try:
            # MUHIM ARXITEKTURA QOIDASI: barcha defensiv
            # tekshiruvlar (private chat, real User, bot emas,
            # service xabar emas, self-message emas) — DB
            # so'rovlaridan OLDIN, yagona umumiy filter orqali
            # bajariladi. Telethon event obuna darajasidagi
            # `func=is_private_incoming_event` filtri faqat
            # arzon/sinxron holatlarni oldindan chetlab o'tadi —
            # bu yerdagi tekshiruv har doim MUSTAQIL qayta
            # bajariladi (ichki processing funksiyasi sifatida).
            if not await validate_private_user_event(
                event,
                log_prefix="First Message",
            ):
                return

            message = event.message

            if message is None:
                return

            peer_id = int(event.chat_id)
            now = datetime.now(timezone.utc)

            # MUHIM (Javob berilmagan chatlar — spec 2/6-bo'lim):
            # bu tekshiruv First Message konfiguratsiya
            # qilingan-qilinmaganidan qat'iy nazar, HAR bir
            # kiruvchi shaxsiy xabar uchun bajariladi (quyidagi
            # "first_message is None" erta-return'idan OLDIN) —
            # chunki javobsiz chat Auto Reply orqali ham ochilgan
            # bo'lishi mumkin, va foydalanuvchi javob yozganda u
            # har doim resolve qilinishi kerak.
            await mark_answered(
                telegram_account_id=telegram_account_id,
                peer_id=peer_id,
                replied_at=now,
            )

            should_send = False
            first_message: Optional[dict] = None

            async with AsyncSessionLocal() as session:
                first_message = await self._get_active_first_message(
                    session,
                    db_user_id,
                )

                if first_message is None:
                    return

                contact = await self._get_or_create_contact(
                    session,
                    db_user_id,
                    telegram_account_id,
                    peer_id,
                )

                interval = timedelta(
                    seconds=first_message[
                        "repeat_interval_seconds"
                    ]
                )

                if contact.last_first_message_at is None:
                    should_send = True
                elif (
                    now - contact.last_first_message_at
                    >= interval
                ):
                    should_send = True

                contact.last_incoming_at = now

                if should_send:
                    contact.last_first_message_at = now

                await session.commit()

            if not should_send or first_message is None:
                return

            client = telegram_client_manager.get_client(
                telegram_id
            )

            if client is None:
                return

            sent = await self._send_first_message(
                client=client,
                target_chat_id=event.chat_id,
                first_message=first_message,
                telegram_account_id=telegram_account_id,
                db_user_id=db_user_id,
            )

            if sent:
                await self._update_statistics(db_user_id)

                peer_name, peer_username = (
                    await get_peer_display_info(event)
                )

                await record_outgoing_message(
                    telegram_account_id=telegram_account_id,
                    peer_id=peer_id,
                    peer_name=peer_name,
                    peer_username=peer_username,
                    sent_at=now,
                )

        except Exception:
            logger.exception(
                "First message incoming xabarni qayta "
                "ishlashda xatolik."
            )

    # =====================================================
    # START
    # =====================================================

    async def start(self) -> None:
        try:
            accounts = await self._get_connected_accounts()

            logger.info(
                "First message uchun %s ta Telegram akkaunt topildi.",
                len(accounts),
            )

            for account in accounts:
                try:
                    await self._start_account(
                        db_user_id=account.user_id,
                        telegram_id=account.telegram_id,
                        telegram_account_id=account.id,
                    )

                except Exception:
                    logger.exception(
                        "Akkaunt listenerida xatolik: %s",
                        account.telegram_id,
                    )

        except Exception:
            logger.exception(
                "FirstMessageEngine ishga tushmadi."
            )
            raise

    # =====================================================
    # START FOR ONE USER
    # =====================================================

    async def start_for_user(
        self,
        db_user_id: int,
    ) -> bool:
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(
                        TelegramAccount.id,
                        TelegramAccount.telegram_id,
                        TelegramAccount.status,
                    ).where(
                        TelegramAccount.user_id == db_user_id,
                        TelegramAccount.status == "connected",
                    )
                )

                accounts = result.all()

            success = False

            for account in accounts:
                started = await self._start_account(
                    db_user_id=db_user_id,
                    telegram_id=account.telegram_id,
                    telegram_account_id=account.id,
                )

                if started:
                    success = True

            return success

        except Exception:
            logger.exception(
                "Foydalanuvchi uchun first message engine "
                "ishga tushmadi: %s",
                db_user_id,
            )
            return False

    # =====================================================
    # STOP ONE USER
    # =====================================================

    async def stop_for_user(
        self,
        db_user_id: int,
    ) -> None:
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(
                        TelegramAccount.telegram_id
                    ).where(
                        TelegramAccount.user_id == db_user_id
                    )
                )

                telegram_ids = result.scalars().all()

            for telegram_id in telegram_ids:
                await self._stop_account(telegram_id)

        except Exception:
            logger.exception(
                "Foydalanuvchi first message engine "
                "to'xtatilmadi: %s",
                db_user_id,
            )

    # =====================================================
    # STOP ACCOUNT
    # =====================================================

    async def _stop_account(
        self,
        telegram_id: int,
    ) -> None:
        handler = self._handlers.pop(telegram_id, None)

        client = telegram_client_manager.get_client(telegram_id)

        if client is not None and handler is not None:
            try:
                client.remove_event_handler(handler)
            except Exception:
                logger.exception(
                    "Event handler olib tashlanmadi: %s",
                    telegram_id,
                )

        self._active_accounts.discard(telegram_id)

    # =====================================================
    # STOP ALL
    # =====================================================

    async def stop(self) -> None:
        telegram_ids = list(self._active_accounts)

        for telegram_id in telegram_ids:
            await self._stop_account(telegram_id)

        logger.info("FirstMessageEngine to'xtatildi.")

    # =====================================================
    # STATUS (monitoring uchun)
    # =====================================================

    def active_account_count(self) -> int:
        return len(self._active_accounts)


first_message_engine = FirstMessageEngine()


__all__ = [
    "FirstMessageEngine",
    "first_message_engine",
]
