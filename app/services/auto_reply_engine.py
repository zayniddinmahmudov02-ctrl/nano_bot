import asyncio
import logging
from typing import Dict, Optional, Set

from telethon import events

from app.database import AsyncSessionLocal
from app.database.models import (
    AutoReply,
    AutoReplyKeyword,
    Statistics,
    TelegramAccount,
    User,
)
from app.telegram.user_client import telegram_client_manager

logger = logging.getLogger(__name__)


class AutoReplyEngine:
    def __init__(self) -> None:
        self._running = False

        # Telegram ID -> asyncio task
        self._tasks: Dict[int, asyncio.Task] = {}

        # Telegram ID -> handler
        self._handlers: Dict[int, object] = {}

        # Bir akkauntga bir nechta listener
        # ulanib qolishining oldini olish.
        self._registered_accounts: Set[int] = set()

    # ---------------------------------------------------------
    # START
    # ---------------------------------------------------------

    async def start(self) -> None:
        """
        Server ishga tushganda barcha ulangan
        Telegram akkauntlar uchun engine'ni ishga tushiradi.
        """

        if self._running:
            return

        self._running = True

        logger.info("AutoReplyEngine starting...")

        async with AsyncSessionLocal() as session:
            accounts = (
                await self._get_connected_accounts(session)
            )

        for account_id, db_user_id, telegram_id in accounts:
            try:
                await self.start_for_user(
                    telegram_id=telegram_id,
                    db_user_id=db_user_id,
                    account_id=account_id,
                )
            except Exception:
                logger.exception(
                    "Failed to start AutoReplyEngine "
                    "for telegram_id=%s",
                    telegram_id,
                )

        logger.info(
            "AutoReplyEngine started. Accounts=%s",
            len(accounts),
        )

    # ---------------------------------------------------------
    # GET CONNECTED ACCOUNTS
    # ---------------------------------------------------------

    async def _get_connected_accounts(
        self,
        session,
    ):
        """
        Return:
            account_id,
            users.id,
            users.telegram_id

        Muhim:
        Telegram ID va DB user ID alohida olinadi.
        """

        result = await session.execute(
            (
                TelegramAccount,
                User,
            )
        )

        # Yuqoridagi tuple-select turli SQLAlchemy
        # versiyalarida noqulay bo‘lishi mumkin.
        # Shuning uchun explicit query ishlatamiz.
        from sqlalchemy import select

        result = await session.execute(
            select(
                TelegramAccount.id,
                TelegramAccount.user_id,
                User.telegram_id,
            )
            .join(
                User,
                User.id == TelegramAccount.user_id,
            )
            .where(
                TelegramAccount.is_connected.is_(True)
            )
        )

        return result.all()

    # ---------------------------------------------------------
    # START FOR USER
    # ---------------------------------------------------------

    async def start_for_user(
        self,
        telegram_id: int,
        db_user_id: int,
        account_id: Optional[int] = None,
    ) -> None:
        """
        AutoReply listener'ni bitta Telegram akkauntga ulaydi.

        telegram_id:
            Telethon client manager uchun.

        db_user_id:
            PostgreSQL foreign key uchun.

        account_id:
            TelegramAccount.id.
        """

        telegram_id = int(telegram_id)
        db_user_id = int(db_user_id)

        if telegram_id in self._registered_accounts:
            logger.info(
                "AutoReplyEngine already running "
                "for telegram_id=%s",
                telegram_id,
            )
            return

        client = telegram_client_manager.get_client(
            telegram_id
        )

        if client is None:
            logger.warning(
                "Telethon client not found "
                "for telegram_id=%s",
                telegram_id,
            )
            return

        try:
            if not await client.is_user_authorized():
                logger.warning(
                    "Telegram client is not authorized "
                    "for telegram_id=%s",
                    telegram_id,
                )
                return
        except Exception:
            logger.exception(
                "Authorization check failed "
                "for telegram_id=%s",
                telegram_id,
            )
            return

        async def handler(event) -> None:
            await self._handle_message(
                event=event,
                telegram_id=telegram_id,
                db_user_id=db_user_id,
                account_id=account_id,
            )

        client.add_event_handler(
            handler,
            events.NewMessage(incoming=True),
        )

        self._handlers[telegram_id] = handler
        self._registered_accounts.add(telegram_id)

        logger.info(
            "AutoReply listener registered "
            "for telegram_id=%s, db_user_id=%s",
            telegram_id,
            db_user_id,
        )

    # ---------------------------------------------------------
    # HANDLE MESSAGE
    # ---------------------------------------------------------

    async def _handle_message(
        self,
        event,
        telegram_id: int,
        db_user_id: int,
        account_id: Optional[int],
    ) -> None:

        try:
            message = event.message

            if message is None:
                return

            # Outgoing xabarlarni o'tkazib yuboramiz.
            if getattr(message, "out", False):
                return

            text = message.raw_text or ""

            if not text.strip():
                return

            text_normalized = text.casefold().strip()

            async with AsyncSessionLocal() as session:

                # Faqat shu userga tegishli aktiv
                # auto reply'larni olamiz.
                query = (
                    select(AutoReply)
                    .where(
                        AutoReply.user_id == db_user_id
                    )
                    .where(
                        AutoReply.is_active.is_(True)
                    )
                )

                if account_id is not None:
                    query = query.where(
                        (
                            AutoReply.telegram_account_id
                            == account_id
                        )
                        |
                        (
                            AutoReply.telegram_account_id
                            .is_(None)
                        )
                    )

                result = await session.execute(query)

                auto_replies = result.scalars().all()

                if not auto_replies:
                    return

                matched = False

                for auto_reply in auto_replies:

                    keyword_result = await session.execute(
                        select(
                            AutoReplyKeyword
                        ).where(
                            AutoReplyKeyword.auto_reply_id
                            == auto_reply.id
                        )
                    )

                    keywords = (
                        keyword_result.scalars().all()
                    )

                    for keyword in keywords:
                        keyword_text = (
                            keyword.keyword or ""
                        ).strip().casefold()

                        if not keyword_text:
                            continue

                        if keyword_text in text_normalized:
                            matched = True

                            await self._send_reply(
                                client=(
                                    telegram_client_manager
                                    .get_client(
                                        telegram_id
                                    )
                                ),
                                event=event,
                                auto_reply=auto_reply,
                            )

                            await self._update_statistics(
                                session=session,
                                db_user_id=db_user_id,
                            )

                            break

                    if matched:
                        break

                await session.commit()

        except Exception:
            logger.exception(
                "AutoReplyEngine message handler failed "
                "for telegram_id=%s",
                telegram_id,
            )

    # ---------------------------------------------------------
    # SEND REPLY
    # ---------------------------------------------------------

    async def _send_reply(
        self,
        client,
        event,
        auto_reply: AutoReply,
    ) -> None:

        if client is None:
            logger.warning(
                "Cannot send auto reply: client is None"
            )
            return

        message_type = (
            auto_reply.message_type or "text"
        )

        if message_type == "text":
            text = auto_reply.message_text or ""

            if text:
                await event.respond(text)

        elif message_type == "photo":
            if auto_reply.file_id:
                await client.send_file(
                    event.chat_id,
                    auto_reply.file_id,
                    caption=auto_reply.message_text or None,
                )

        elif message_type == "video":
            if auto_reply.file_id:
                await client.send_file(
                    event.chat_id,
                    auto_reply.file_id,
                    caption=auto_reply.message_text or None,
                )

        elif message_type == "document":
            if auto_reply.file_id:
                await client.send_file(
                    event.chat_id,
                    auto_reply.file_id,
                    caption=auto_reply.message_text or None,
                )

        elif message_type == "link":
            if auto_reply.link:
                await event.respond(
                    auto_reply.link
                )

        else:
            logger.warning(
                "Unknown auto reply message_type=%s",
                message_type,
            )

    # ---------------------------------------------------------
    # STATISTICS
    # ---------------------------------------------------------

    async def _update_statistics(
        self,
        session,
        db_user_id: int,
    ) -> None:

        from sqlalchemy import select

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

        statistics.auto_replies = (
            statistics.auto_replies + 1
        )

        statistics.replied_people = (
            statistics.replied_people + 1
        )

    # ---------------------------------------------------------
    # STOP FOR USER
    # ---------------------------------------------------------

    async def stop_for_user(
        self,
        telegram_id: int,
    ) -> None:

        telegram_id = int(telegram_id)

        client = telegram_client_manager.get_client(
            telegram_id
        )

        handler = self._handlers.get(
            telegram_id
        )

        if client is not None and handler is not None:
            try:
                client.remove_event_handler(
                    handler
                )
            except Exception:
                logger.exception(
                    "Failed to remove event handler "
                    "for telegram_id=%s",
                    telegram_id,
                )

        self._handlers.pop(
            telegram_id,
            None,
        )

        self._registered_accounts.discard(
            telegram_id
        )

        task = self._tasks.pop(
            telegram_id,
            None,
        )

        if task is not None:
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception(
                    "AutoReply task shutdown failed "
                    "for telegram_id=%s",
                    telegram_id,
                )

        logger.info(
            "AutoReplyEngine stopped "
            "for telegram_id=%s",
            telegram_id,
        )

    # ---------------------------------------------------------
    # STOP ALL
    # ---------------------------------------------------------

    async def stop(self) -> None:

        if not self._running:
            return

        self._running = False

        telegram_ids = list(
            self._registered_accounts
        )

        for telegram_id in telegram_ids:
            try:
                await self.stop_for_user(
                    telegram_id
                )
            except Exception:
                logger.exception(
                    "Failed to stop AutoReplyEngine "
                    "for telegram_id=%s",
                    telegram_id,
                )

        self._tasks.clear()
        self._handlers.clear()
        self._registered_accounts.clear()

        logger.info(
            "AutoReplyEngine stopped."
        )


# -------------------------------------------------------------
# SINGLETON
# -------------------------------------------------------------

auto_reply_engine = AutoReplyEngine()


__all__ = [
    "AutoReplyEngine",
    "auto_reply_engine",
]