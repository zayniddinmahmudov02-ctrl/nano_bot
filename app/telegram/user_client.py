from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Optional

from telethon import TelegramClient
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)

from app.config import (
    TELEGRAM_API_HASH,
    TELEGRAM_API_ID,
    TELEGRAM_SESSION_DIR,
)

logger = logging.getLogger(__name__)


class TelegramClientManager:
    """
    Foydalanuvchilarning shaxsiy Telegram akkauntlarini
    Telethon orqali boshqaradi.

    DIQQAT:
    Bu yerda user_id sifatida Telegram ID ishlatiladi.

    Database foreign key uchun esa users.id ishlatiladi.
    """

    def __init__(self) -> None:
        self.api_id = int(TELEGRAM_API_ID)
        self.api_hash = TELEGRAM_API_HASH

        self.session_dir = Path(
            TELEGRAM_SESSION_DIR
        )

        self.session_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            os.chmod(
                self.session_dir,
                0o700,
            )
        except OSError:
            pass

        # Telegram ID -> active client
        self.clients: Dict[
            int,
            TelegramClient,
        ] = {}

        # Telegram ID -> temporary login client
        self.pending_clients: Dict[
            int,
            TelegramClient,
        ] = {}

        # Telegram ID -> phone number
        self.pending_phones: Dict[
            int,
            str,
        ] = {}

        # Har bir Telegram ID uchun alohida lock
        self.locks: Dict[
            int,
            asyncio.Lock,
        ] = {}

    # =========================================================
    # INTERNAL HELPERS
    # =========================================================

    def _get_lock(
        self,
        telegram_id: int,
    ) -> asyncio.Lock:
        telegram_id = int(telegram_id)

        if telegram_id not in self.locks:
            self.locks[telegram_id] = asyncio.Lock()

        return self.locks[telegram_id]

    def _session_path(
        self,
        telegram_id: int,
    ) -> str:
        """
        Session fayl nomi faqat Telegram ID asosida yaratiladi.
        """

        telegram_id = int(telegram_id)

        return str(
            self.session_dir / f"{telegram_id}.session"
        )

    def _create_client(
        self,
        telegram_id: int,
    ) -> TelegramClient:
        """
        Yangi Telethon client yaratadi.
        """

        session_path = self._session_path(
            telegram_id
        )

        client = TelegramClient(
            session_path,
            self.api_id,
            self.api_hash,
            device_model="Nano-Bot",
            system_version="1.0",
            app_version="1.0",
            lang_code="en",
            system_lang_code="en",
        )

        return client

    # =========================================================
    # GET CLIENT
    # =========================================================

    def get_client(
        self,
        telegram_id: int,
    ) -> Optional[TelegramClient]:
        """
        Active Telegram clientni qaytaradi.
        """

        telegram_id = int(telegram_id)

        return self.clients.get(
            telegram_id
        )

    # =========================================================
    # START PHONE LOGIN
    # =========================================================

    async def start_phone_login(
        self,
        telegram_id: int,
        phone: str,
    ) -> bool:
        """
        Telefon raqam orqali login jarayonini boshlaydi.

        Telegram'dan login kodi yuboriladi.
        """

        telegram_id = int(telegram_id)

        lock = self._get_lock(
            telegram_id
        )

        async with lock:

            # Eski pending client bo‘lsa,
            # uni yopamiz.
            old_client = self.pending_clients.get(
                telegram_id
            )

            if old_client is not None:
                try:
                    await old_client.disconnect()
                except Exception:
                    logger.exception(
                        "Failed to disconnect old pending client"
                    )

            client = self._create_client(
                telegram_id
            )

            await client.connect()

            try:
                await client.send_code_request(
                    phone
                )
            except Exception:
                try:
                    await client.disconnect()
                except Exception:
                    pass

                raise

            self.pending_clients[
                telegram_id
            ] = client

            self.pending_phones[
                telegram_id
            ] = phone

            logger.info(
                "Telegram login code requested: telegram_id=%s",
                telegram_id,
            )

            return True

    # =========================================================
    # SIGN IN CODE
    # =========================================================

    async def sign_in_code(
        self,
        telegram_id: int,
        code: str,
    ) -> bool:
        """
        Telegram tomonidan yuborilgan login kodini
        tekshiradi.

        Agar 2FA yoqilgan bo‘lsa:
        SessionPasswordNeededError qaytaradi.
        """

        telegram_id = int(telegram_id)

        lock = self._get_lock(
            telegram_id
        )

        async with lock:

            client = self.pending_clients.get(
                telegram_id
            )

            phone = self.pending_phones.get(
                telegram_id
            )

            if client is None or phone is None:
                raise RuntimeError(
                    "Login sessiyasi topilmadi. "
                    "Qaytadan telefon raqamingizni yuboring."
                )

            try:
                await client.sign_in(
                    phone=phone,
                    code=code.strip(),
                )

            except SessionPasswordNeededError:
                logger.info(
                    "2FA password required: telegram_id=%s",
                    telegram_id,
                )

                raise

            except PhoneCodeInvalidError:
                logger.warning(
                    "Invalid Telegram login code: telegram_id=%s",
                    telegram_id,
                )

                raise

            except PhoneCodeExpiredError:
                logger.warning(
                    "Expired Telegram login code: telegram_id=%s",
                    telegram_id,
                )

                raise

            await self._activate_client(
                telegram_id,
                client,
            )

            logger.info(
                "Telegram login successful: telegram_id=%s",
                telegram_id,
            )

            return True

    # =========================================================
    # SIGN IN PASSWORD
    # =========================================================

    async def sign_in_password(
        self,
        telegram_id: int,
        password: str,
    ) -> bool:
        """
        Telegram 2FA parolini tekshiradi.
        """

        telegram_id = int(telegram_id)

        lock = self._get_lock(
            telegram_id
        )

        async with lock:

            client = self.pending_clients.get(
                telegram_id
            )

            if client is None:
                raise RuntimeError(
                    "Login sessiyasi topilmadi. "
                    "Qaytadan login jarayonini boshlang."
                )

            await client.sign_in(
                password=password
            )

            await self._activate_client(
                telegram_id,
                client,
            )

            logger.info(
                "Telegram 2FA login successful: telegram_id=%s",
                telegram_id,
            )

            return True

    # =========================================================
    # ACTIVATE CLIENT
    # =========================================================

    async def _activate_client(
        self,
        telegram_id: int,
        client: TelegramClient,
    ) -> None:
        """
        Pending clientni active clientga aylantiradi.
        """

        telegram_id = int(telegram_id)

        old_client = self.clients.get(
            telegram_id
        )

        if old_client is not None and old_client is not client:
            try:
                await old_client.disconnect()
            except Exception:
                logger.exception(
                    "Failed to disconnect old active client"
                )

        self.clients[
            telegram_id
        ] = client

        self.pending_clients.pop(
            telegram_id,
            None,
        )

        self.pending_phones.pop(
            telegram_id,
            None,
        )

        try:
            os.chmod(
                self._session_path(
                    telegram_id
                ),
                0o600,
            )
        except OSError:
            pass

    # =========================================================
    # GET ME
    # =========================================================

    async def get_me(
        self,
        telegram_id: int,
    ):
        """
        Ulangan Telegram akkaunt ma'lumotlarini qaytaradi.
        """

        telegram_id = int(telegram_id)

        client = self.get_client(
            telegram_id
        )

        if client is None:
            return None

        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            return None

        return await client.get_me()

    # =========================================================
    # IS AUTHORIZED
    # =========================================================

    async def is_authorized(
        self,
        telegram_id: int,
    ) -> bool:
        telegram_id = int(telegram_id)

        client = self.get_client(
            telegram_id
        )

        if client is None:
            return False

        try:
            if not client.is_connected():
                await client.connect()

            return await client.is_user_authorized()

        except Exception:
            logger.exception(
                "Authorization check failed: telegram_id=%s",
                telegram_id,
            )

            return False

    # =========================================================
    # LOGOUT
    # =========================================================

    async def logout(
        self,
        telegram_id: int,
    ) -> bool:
        """
        Telegram akkauntini logout qiladi.
        """

        telegram_id = int(telegram_id)

        lock = self._get_lock(
            telegram_id
        )

        async with lock:

            client = self.clients.pop(
                telegram_id,
                None,
            )

            pending_client = self.pending_clients.pop(
                telegram_id,
                None,
            )

            self.pending_phones.pop(
                telegram_id,
                None,
            )

            # Active client
            if client is not None:
                try:
                    if client.is_connected():
                        await client.log_out()
                except Exception:
                    logger.exception(
                        "Telegram logout failed: telegram_id=%s",
                        telegram_id,
                    )

                try:
                    await client.disconnect()
                except Exception:
                    pass

            # Pending client
            if (
                pending_client is not None
                and pending_client is not client
            ):
                try:
                    await pending_client.disconnect()
                except Exception:
                    pass

            logger.info(
                "Telegram client logged out: telegram_id=%s",
                telegram_id,
            )

            return True

    # =========================================================
    # LOAD EXISTING SESSIONS
    # =========================================================

    async def load_existing_sessions(self) -> None:
        """
        Server qayta ishga tushganda mavjud .session
        fayllarni yuklaydi.

        Faqat haqiqiy Telegram session fayllari yuklanadi.
        """

        if not self.session_dir.exists():
            return

        session_files = list(
            self.session_dir.glob("*.session")
        )

        if not session_files:
            logger.info(
                "No existing Telegram sessions found."
            )
            return

        loaded = 0

        for session_file in session_files:

            try:
                telegram_id = int(
                    session_file.stem
                )
            except ValueError:
                logger.warning(
                    "Skipping invalid session filename: %s",
                    session_file.name,
                )
                continue

            try:
                client = self._create_client(
                    telegram_id
                )

                await client.connect()

                if not await client.is_user_authorized():
                    await client.disconnect()

                    logger.warning(
                        "Session is not authorized: telegram_id=%s",
                        telegram_id,
                    )

                    continue

                self.clients[
                    telegram_id
                ] = client

                try:
                    os.chmod(
                        session_file,
                        0o600,
                    )
                except OSError:
                    pass

                loaded += 1

                logger.info(
                    "Telegram session loaded: telegram_id=%s",
                    telegram_id,
                )

            except Exception:
                logger.exception(
                    "Failed to load Telegram session: %s",
                    session_file.name,
                )

        logger.info(
            "Existing Telegram sessions loaded: %s",
            loaded,
        )

    # =========================================================
    # SHUTDOWN
    # =========================================================

    async def shutdown(self) -> None:
        """
        Barcha Telethon clientlarni xavfsiz yopadi.
        """

        all_clients = list(
            self.clients.items()
        )

        self.clients.clear()

        self.pending_clients.clear()
        self.pending_phones.clear()

        for telegram_id, client in all_clients:

            try:
                if client.is_connected():
                    await client.disconnect()

                logger.info(
                    "Telegram client disconnected: telegram_id=%s",
                    telegram_id,
                )

            except Exception:
                logger.exception(
                    "Failed to disconnect Telegram client: telegram_id=%s",
                    telegram_id,
                )

        self.locks.clear()

        logger.info(
            "TelegramClientManager shutdown complete."
        )


# =============================================================
# SINGLETON
# =============================================================

telegram_client_manager = TelegramClientManager()


__all__ = [
    "TelegramClientManager",
    "telegram_client_manager",
]