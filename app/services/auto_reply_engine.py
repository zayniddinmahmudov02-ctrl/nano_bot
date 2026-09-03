import logging
from typing import Dict, Set

from sqlalchemy import select
from telethon import events

from app.database import AsyncSessionLocal
from app.database.models import (
    AutoReply,
    AutoReplyKeyword,
    Statistics,
    TelegramAccount,
    User,
)
from app.services.media_service import send_stored_post
from app.telegram.user_client import telegram_client_manager

logger = logging.getLogger(__name__)


class AutoReplyEngine:
    def __init__(self) -> None:
        self._running = False

        # Telegram ID -> event handler
        self._handlers: Dict[int, object] = {}

        # Active Telegram accounts
        self._active_accounts: Set[int] = set()

    # =====================================================
    # DATABASE
    # =====================================================

    async def _get_connected_accounts(self):
        """
        DBdan faqat kerakli ustunlarni oladi.

        Muhim:
        TelegramAccount modelidagi is_connected kabi
        eski DBda yo‘q bo‘lishi mumkin bo‘lgan ustunlar
        SELECT qilinmaydi.
        """

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(
                    TelegramAccount.id,
                    TelegramAccount.user_id,
                    TelegramAccount.telegram_id,
                    TelegramAccount.status,
                    TelegramAccount.auto_reply_enabled,
                )
                .join(
                    User,
                    User.id == TelegramAccount.user_id,
                )
                .where(
                    TelegramAccount.status == "connected",
                    TelegramAccount.auto_reply_enabled.is_(True),
                )
            )

            return result.all()

    async def _get_auto_replies(
        self,
        db_user_id: int,
        telegram_account_id: int,
    ):
        async with AsyncSessionLocal() as session:
            # MUHIM: barcha FAOL Auto Reply qoidalari olinadi
            # (.all() — .first() emas). Har bir qoida keyinroq
            # _handle_message ichida mustaqil ravishda tekshiriladi.
            # ORDER BY — moslik tartibini bashorat qilinadigan
            # qiladi (eng oldin yaratilgan qoida birinchi
            # tekshiriladi).
            result = await session.execute(
                select(AutoReply)
                .where(
                    AutoReply.user_id == db_user_id,
                    AutoReply.telegram_account_id
                    == telegram_account_id,
                    AutoReply.is_active.is_(True),
                )
                .order_by(AutoReply.id.asc())
            )

            replies = result.scalars().unique().all()

            prepared = []

            for auto_reply in replies:
                keyword_result = await session.execute(
                    select(AutoReplyKeyword.keyword).where(
                        AutoReplyKeyword.auto_reply_id
                        == auto_reply.id
                    )
                )

                keywords = [
                    keyword.lower().strip()
                    for keyword in keyword_result.scalars().all()
                    if keyword and keyword.strip()
                ]

                prepared.append(
                    {
                        "id": auto_reply.id,
                        "message_type": auto_reply.message_type,
                        "message_text": auto_reply.message_text,
                        "file_id": auto_reply.file_id,
                        "link": auto_reply.link,
                        "storage_chat_id": auto_reply.storage_chat_id,
                        "storage_message_id": (
                            auto_reply.storage_message_id
                        ),
                        "keywords": keywords,
                    }
                )

            return prepared

    # =====================================================
    # MATCHING
    # =====================================================

    @staticmethod
    def _keyword_matches(
        text: str,
        keywords: list[str],
    ) -> bool:
        if not text:
            return False

        normalized_text = text.lower().strip()

        for keyword in keywords:
            if not keyword:
                continue

            if keyword in normalized_text:
                return True

        return False

    # =====================================================
    # SEND
    # =====================================================

    async def _send_auto_reply(
        self,
        client,
        event,
        auto_reply: dict,
    ) -> bool:
        try:
            auto_reply_id = auto_reply.get("id")
            message_type = auto_reply["message_type"]
            message_text = auto_reply["message_text"]
            file_id = auto_reply["file_id"]
            link = auto_reply["link"]
            storage_chat_id = auto_reply.get("storage_chat_id")
            storage_message_id = auto_reply.get(
                "storage_message_id"
            )

            # Auto Reply 2.0: media Storage Channel orqali,
            # forward emas — yangi xabar sifatida yuboriladi.
            if storage_chat_id and storage_message_id:
                return await send_stored_post(
                    telethon_client=client,
                    storage_chat_id=storage_chat_id,
                    storage_message_id=storage_message_id,
                    target_chat_id=event.chat_id,
                )

            if message_type == "text":
                if not message_text:
                    return False

                await event.respond(
                    message_text
                )

            elif message_type in (
                "photo",
                "video",
                "document",
            ):
                # MUHIM: bu yerga faqat Storage Channel'ga hali
                # ko'chirilmagan ESKI (legacy) yozuvlar tushadi
                # (storage_chat_id/storage_message_id yo'q).
                #
                # Ularda saqlangan file_id — Telegram Bot API
                # file_id, Telethon uchun yaroqsiz. Uni
                # client.send_file()'ga to'g'ridan-to'g'ri
                # uzatish doimo:
                #   ValueError: Failed to convert ... to media
                # xatosiga olib keladi. Shu sababli bunday
                # urinish butunlay OLIB TASHLANDI — o'rniga
                # xavfsiz "skip" qilinadi va logga yoziladi.
                logger.warning(
                    "Legacy Auto Reply (id=%s) uchun Storage "
                    "reference topilmadi — eski Bot API "
                    "file_id Telethon orqali yuborilmaydi. "
                    "Auto Reply'ni tahrirlash orqali qayta "
                    "saqlang.",
                    auto_reply_id,
                )
                return False

            elif message_type == "link":
                if not link:
                    return False

                if message_text:
                    response = (
                        f"{message_text}\n\n"
                        f"{link}"
                    )
                else:
                    response = link

                await event.respond(response)

            else:
                logger.warning(
                    "Noma'lum auto reply turi: %s",
                    message_type,
                )
                return False

            return True

        except Exception:
            logger.exception(
                "Auto reply yuborishda xatolik."
            )
            return False

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

                statistics.auto_replies += 1

                await session.commit()

        except Exception:
            logger.exception(
                "Auto reply statistikasi yangilanmadi."
            )

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

        client = telegram_client_manager.get_client(
            telegram_id
        )

        if client is None:
            logger.warning(
                "Telegram client topilmadi: %s",
                telegram_id,
            )
            return False

        try:
            if not client.is_connected():
                await client.connect()

            if not await client.is_user_authorized():
                logger.warning(
                    "Telegram akkaunt avtorizatsiyadan o‘tmagan: %s",
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
                "Auto reply listener ishga tushdi: %s",
                telegram_id,
            )

            return True

        except Exception:
            logger.exception(
                "Auto reply listener ishga tushmadi: %s",
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
            # O‘zimiz yuborgan xabarni ignore qilamiz.
            if getattr(event, "out", False):
                return

            message = event.message

            if message is None:
                return

            text = message.message or ""

            if not text:
                return

            auto_replies = await self._get_auto_replies(
                db_user_id=db_user_id,
                telegram_account_id=telegram_account_id,
            )

            if not auto_replies:
                return

            logger.debug(
                "Incoming message: telegram_id=%s, "
                "tekshiriladigan qoidalar soni=%s",
                telegram_id,
                len(auto_replies),
            )

            # MUHIM: har bir FAOL qoida MUSTAQIL tekshiriladi.
            # Bitta xabarga faqat birinchi mos kelgan qoida
            # javob beradi (loyihadagi mavjud
            # duplicate-prevention xatti-harakati saqlanadi) —
            # lekin har bir alohida xabar o'zining mos keluvchi
            # qoidasini har doim topadi, chunki ro'yxat har safar
            # bazadan to'liq qayta olinadi (.all(), .first() emas).
            for auto_reply in auto_replies:
                keywords = auto_reply["keywords"]

                matched = self._keyword_matches(
                    text,
                    keywords,
                )

                logger.debug(
                    "Auto Reply id=%s tekshirildi: mos=%s",
                    auto_reply.get("id"),
                    matched,
                )

                if not matched:
                    continue

                sent = await self._send_auto_reply(
                    client=telegram_client_manager.get_client(
                        telegram_id
                    ),
                    event=event,
                    auto_reply=auto_reply,
                )

                logger.info(
                    "Auto Reply id=%s mos keldi "
                    "(telegram_id=%s): yuborildi=%s",
                    auto_reply.get("id"),
                    telegram_id,
                    sent,
                )

                if sent:
                    await self._update_statistics(
                        db_user_id
                    )

                # Bir xabarga birinchi mos kelgan
                # auto reply yetarli.
                break

        except Exception:
            logger.exception(
                "Incoming message qayta ishlashda xatolik."
            )

    # =====================================================
    # START
    # =====================================================

    async def start(self) -> None:
        if self._running:
            logger.info(
                "AutoReplyEngine allaqachon ishlayapti."
            )
            return

        self._running = True

        try:
            accounts = await self._get_connected_accounts()

            logger.info(
                "Auto reply uchun %s ta Telegram akkaunt topildi.",
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
            self._running = False

            logger.exception(
                "AutoReplyEngine ishga tushmadi."
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
                        TelegramAccount.auto_reply_enabled,
                    ).where(
                        TelegramAccount.user_id
                        == db_user_id,
                        TelegramAccount.status
                        == "connected",
                        TelegramAccount.auto_reply_enabled.is_(True),
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
                "Foydalanuvchi uchun auto reply engine "
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
                        TelegramAccount.user_id
                        == db_user_id
                    )
                )

                telegram_ids = result.scalars().all()

            for telegram_id in telegram_ids:
                await self._stop_account(
                    telegram_id
                )

        except Exception:
            logger.exception(
                "Foydalanuvchi auto reply engine "
                "to‘xtatilmadi: %s",
                db_user_id,
            )

    # =====================================================
    # STOP ACCOUNT
    # =====================================================

    async def _stop_account(
        self,
        telegram_id: int,
    ) -> None:
        handler = self._handlers.pop(
            telegram_id,
            None,
        )

        client = telegram_client_manager.get_client(
            telegram_id
        )

        if client is not None and handler is not None:
            try:
                client.remove_event_handler(
                    handler
                )
            except Exception:
                logger.exception(
                    "Event handler olib tashlanmadi: %s",
                    telegram_id,
                )

        self._active_accounts.discard(
            telegram_id
        )

    # =====================================================
    # STOP ALL
    # =====================================================

    async def stop(self) -> None:
        if not self._active_accounts:
            self._running = False
            return

        telegram_ids = list(
            self._active_accounts
        )

        for telegram_id in telegram_ids:
            await self._stop_account(
                telegram_id
            )

        self._running = False

        logger.info(
            "AutoReplyEngine to‘xtatildi."
        )

    # =====================================================
    # STATUS (monitoring uchun)
    # =====================================================

    def active_account_count(self) -> int:
        return len(self._active_accounts)

    def is_running(self) -> bool:
        return self._running


auto_reply_engine = AutoReplyEngine()


__all__ = [
    "AutoReplyEngine",
    "auto_reply_engine",
]