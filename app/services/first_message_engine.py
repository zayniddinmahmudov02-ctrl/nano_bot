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
    ) -> bool:
        try:
            storage_chat_id = first_message["storage_chat_id"]
            storage_message_id = first_message["storage_message_id"]

            if storage_chat_id and storage_message_id:
                return await send_stored_post(
                    telethon_client=client,
                    storage_chat_id=storage_chat_id,
                    storage_message_id=storage_message_id,
                    target_chat_id=target_chat_id,
                )

            # Legacy fallback: eski file_id asosidagi yozuvlar
            # uchun eng yaxshi urinish (Storage Channel'ga hali
            # ko'chirilmagan eski ma'lumotlar).
            message_type = first_message["message_type"]
            text = first_message["text"]
            file_id = first_message["file_id"]

            if message_type == "text":
                if not text:
                    return False

                await client.send_message(
                    target_chat_id,
                    text,
                )
                return True

            if file_id:
                await client.send_file(
                    target_chat_id,
                    file_id,
                    caption=text or None,
                )
                return True

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

            @client.on(events.NewMessage(incoming=True))
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
            # O'zimiz yuborgan xabarni ignore qilamiz.
            if getattr(event, "out", False):
                return

            # Faqat shaxsiy (private) chatlar uchun ishlaydi.
            if not event.is_private:
                return

            message = event.message

            if message is None:
                return

            # Service (action) xabarlarni e'tiborsiz qoldiramiz.
            if getattr(message, "action", None) is not None:
                return

            peer_id = int(event.chat_id)
            now = datetime.now(timezone.utc)

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
            )

            if sent:
                await self._update_statistics(db_user_id)

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


first_message_engine = FirstMessageEngine()


__all__ = [
    "FirstMessageEngine",
    "first_message_engine",
]
