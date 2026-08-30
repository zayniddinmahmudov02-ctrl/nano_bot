import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.database.models import (
    AutoReply,
    AutoReplyKeyword,
    Statistics,
    TelegramAccount,
)
from app.telegram.user_client import telegram_client_manager

logger = logging.getLogger(__name__)


class AutoReplyEngine:
    """
    Ulangan Telegram akkauntlaridagi xabarlarni kuzatadi
    va mos AutoReplylarni yuboradi.
    """

    def __init__(self) -> None:
        self._running = False
        self._tasks: dict[int, asyncio.Task] = {}

    # =====================================================
    # START / STOP
    # =====================================================

    async def start(self) -> None:
        """
        Database'dagi barcha ulangan Telegram akkauntlar
        uchun listenerlarni ishga tushiradi.
        """

        if self._running:
            return

        self._running = True

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(TelegramAccount).where(
                    TelegramAccount.is_connected.is_(True)
                )
            )

            accounts = result.scalars().all()

        for account in accounts:
            await self.start_for_user(
                account.user_id
            )

        logger.info(
            "AutoReply Engine ishga tushdi. "
            "Ulangan akkauntlar: %s",
            len(accounts),
        )

    async def start_for_user(
        self,
        user_id: int,
    ) -> bool:
        """
        Bitta user uchun Telegram listenerni ishga tushiradi.
        """

        if user_id in self._tasks:
            task = self._tasks[user_id]

            if not task.done():
                return True

        if not self._running:
            return False

        client = (
            await telegram_client_manager
            .get_client(user_id)
        )

        if client is None:
            logger.warning(
                "AutoReply: user %s uchun "
                "Telegram client mavjud emas.",
                user_id,
            )
            return False

        try:
            from telethon import events

            async def handler(event):
                await self.handle_message(
                    user_id=user_id,
                    event=event,
                )

            client.add_event_handler(
                handler,
                events.NewMessage(
                    incoming=True
                ),
            )

            task = asyncio.create_task(
                self._run_client(
                    user_id=user_id,
                    client=client,
                )
            )

            self._tasks[user_id] = task

            logger.info(
                "AutoReply listener ishga tushdi: "
                "user=%s",
                user_id,
            )

            return True

        except Exception:
            logger.exception(
                "AutoReply listener ishga tushmadi: "
                "user=%s",
                user_id,
            )

            return False

    async def stop_for_user(
        self,
        user_id: int,
    ) -> None:
        """
        Bitta user listenerini to'xtatadi.
        """

        task = self._tasks.pop(
            user_id,
            None,
        )

        if task and not task.done():
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info(
            "AutoReply listener to'xtatildi: user=%s",
            user_id,
        )

    async def stop(self) -> None:
        """
        Barcha listenerlarni to'xtatadi.
        """

        self._running = False

        user_ids = list(
            self._tasks.keys()
        )

        for user_id in user_ids:
            await self.stop_for_user(
                user_id
            )

        logger.info(
            "AutoReply Engine to'xtatildi."
        )

    async def _run_client(
        self,
        user_id: int,
        client: Any,
    ) -> None:
        """
        Telethon clientni listener rejimida ushlab turadi.
        """

        try:
            await client.run_until_disconnected()

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "Telegram client uzildi: user=%s",
                user_id,
            )

        finally:
            self._tasks.pop(
                user_id,
                None,
            )

    # =====================================================
    # MESSAGE PROCESSING
    # =====================================================

    async def handle_message(
        self,
        user_id: int,
        event: Any,
    ) -> None:
        """
        Kelgan Telegram xabarini tekshiradi.
        """

        try:
            message = event.message

            if not message:
                return

            # O'zimiz yuborgan xabarlarni qayta
            # process qilmaymiz.
            if getattr(
                message,
                "out",
                False,
            ):
                return

            text = (
                getattr(
                    message,
                    "message",
                    None,
                )
                or ""
            )

            text = text.strip()

            # Bo'sh media xabarlar uchun ham
            # keyword topish mumkin emas.
            if not text:
                return

            matched_reply = (
                await self.find_matching_reply(
                    user_id=user_id,
                    text=text,
                )
            )

            if not matched_reply:
                return

            await self.send_reply(
                user_id=user_id,
                event=event,
                auto_reply=matched_reply,
            )

            sender_id = None

            try:
                sender_id = await event.get_sender()

                if sender_id:
                    sender_id = sender_id.id

            except Exception:
                pass

            await self.update_statistics(
                user_id=user_id,
                sender_id=sender_id,
            )

            logger.info(
                "AutoReply yuborildi: "
                "user=%s reply_id=%s",
                user_id,
                matched_reply.id,
            )

        except Exception:
            logger.exception(
                "AutoReply xabarni qayta ishlashda "
                "xatolik: user=%s",
                user_id,
            )

    # =====================================================
    # KEYWORD MATCHING
    # =====================================================

    async def find_matching_reply(
        self,
        user_id: int,
        text: str,
    ) -> AutoReply | None:
        """
        Keyword bo'yicha mos AutoReplyni topadi.

        Matching:
        - katta/kichik harf farqsiz
        - keyword matn ichida bo'lsa ishlaydi
        """

        normalized_text = (
            text.casefold().strip()
        )

        async with AsyncSessionLocal() as session:

            result = await session.execute(
                select(AutoReply)
                .where(
                    AutoReply.user_id == user_id,
                    AutoReply.is_active.is_(True),
                )
                .order_by(
                    AutoReply.id.asc()
                )
            )

            replies = result.scalars().all()

            for reply in replies:

                keyword_result = (
                    await session.execute(
                        select(AutoReplyKeyword).where(
                            AutoReplyKeyword.auto_reply_id
                            == reply.id
                        )
                    )
                )

                keywords = (
                    keyword_result.scalars().all()
                )

                for keyword in keywords:

                    value = (
                        keyword.keyword
                        .casefold()
                        .strip()
                    )

                    if not value:
                        continue

                    if value in normalized_text:
                        return reply

        return None

    # =====================================================
    # SEND REPLY
    # =====================================================

    async def send_reply(
        self,
        user_id: int,
        event: Any,
        auto_reply: AutoReply,
    ) -> None:
        """
        AutoReply turiga qarab Telegramga javob yuboradi.
        """

        client = (
            await telegram_client_manager
            .get_client(user_id)
        )

        if client is None:
            return

        chat = await event.get_chat()

        message_type = (
            auto_reply.message_type
        )

        text = (
            auto_reply.message_text
            or ""
        )

        # -------------------------------------------------
        # TEXT
        # -------------------------------------------------

        if message_type == "text":

            if not text:
                return

            await client.send_message(
                chat,
                text,
                reply_to=event.message.id,
            )

            return

        # -------------------------------------------------
        # PHOTO / VIDEO / DOCUMENT
        # -------------------------------------------------

        if message_type in {
            "photo",
            "video",
            "document",
        }:

            if not auto_reply.file_id:
                return

            caption = text or None

            await client.send_file(
                chat,
                auto_reply.file_id,
                caption=caption,
                reply_to=event.message.id,
            )

            return

        # -------------------------------------------------
        # LINK
        # -------------------------------------------------

        if message_type == "link":

            if not auto_reply.link:
                return

            await client.send_message(
                chat,
                auto_reply.link,
                reply_to=event.message.id,
            )

            return

        logger.warning(
            "Noma'lum AutoReply turi: %s",
            message_type,
        )

    # =====================================================
    # STATISTICS
    # =====================================================

    async def update_statistics(
        self,
        user_id: int,
        sender_id: int | None,
    ) -> None:
        """
        Faqat statistika hisoblagichlarini yangilaydi.

        Xabar mazmuni saqlanmaydi.
        """

        async with AsyncSessionLocal() as session:

            result = await session.execute(
                select(Statistics).where(
                    Statistics.user_id
                    == user_id
                )
            )

            statistics = (
                result.scalar_one_or_none()
            )

            if not statistics:
                statistics = Statistics(
                    user_id=user_id,
                    people_replied=0,
                    total_auto_replies=0,
                    today_replies=0,
                    month_replies=0,
                )

                session.add(statistics)

            statistics.total_auto_replies += 1
            statistics.today_replies += 1
            statistics.month_replies += 1

            # people_replied uchun sender ID
            # alohida jadvalda saqlanmaydi.
            #
            # Talab bo'yicha suhbat mazmuni saqlanmaydi.
            # Shu sabab bu hisoblagich auto-reply
            # yuborilgan holatda oshiriladi.
            statistics.people_replied += 1

            await session.commit()


auto_reply_engine = AutoReplyEngine()