import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)

from app.config import TELEGRAM_API_HASH, TELEGRAM_API_ID

logger = logging.getLogger(__name__)


class TelegramClientManager:
    """
    Nano-Bot foydalanuvchilarining shaxsiy Telegram
    akkauntlarini boshqaradi.

    Session fayllari database'ga emas, serverdagi
    alohida papkaga saqlanadi.
    """

    def __init__(self) -> None:
        if not TELEGRAM_API_ID:
            raise RuntimeError(
                "TELEGRAM_API_ID .env faylida belgilanmagan."
            )

        if not TELEGRAM_API_HASH:
            raise RuntimeError(
                "TELEGRAM_API_HASH .env faylida belgilanmagan."
            )

        self.api_id = int(
            TELEGRAM_API_ID
        )

        self.api_hash = (
            TELEGRAM_API_HASH
        )

        self.session_dir = Path(
            os.getenv(
                "TELEGRAM_SESSION_DIR",
                "/opt/nano_bot/sessions",
            )
        )

        self.session_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.clients: dict[
            int,
            TelegramClient,
        ] = {}

        self.pending_clients: dict[
            int,
            TelegramClient,
        ] = {}

        self.pending_phones: dict[
            int,
            str,
        ] = {}

        self._locks: dict[
            int,
            asyncio.Lock,
        ] = {}

    # =====================================================
    # LOCK
    # =====================================================

    def _get_lock(
        self,
        user_id: int,
    ) -> asyncio.Lock:

        if user_id not in self._locks:
            self._locks[user_id] = (
                asyncio.Lock()
            )

        return self._locks[user_id]

    # =====================================================
    # SESSION PATH
    # =====================================================

    def _session_path(
        self,
        user_id: int,
    ) -> str:

        return str(
            self.session_dir
            / f"user_{user_id}"
        )

    # =====================================================
    # CREATE CLIENT
    # =====================================================

    def _create_client(
        self,
        user_id: int,
    ) -> TelegramClient:

        return TelegramClient(
            self._session_path(user_id),
            self.api_id,
            self.api_hash,
            device_model="Nano-Bot",
            system_version="1.0",
            app_version="1.0",
            lang_code="en",
            system_lang_code="en",
        )

    # =====================================================
    # GET CLIENT
    # =====================================================

    async def get_client(
        self,
        user_id: int,
    ) -> TelegramClient | None:

        if user_id in self.clients:
            return self.clients[user_id]

        session_file = (
            Path(
                self._session_path(
                    user_id
                )
            ).with_suffix(".session")
        )

        if not session_file.exists():
            return None

        client = self._create_client(
            user_id
        )

        try:
            await client.connect()

            if not await client.is_user_authorized():
                await client.disconnect()
                return None

            self.clients[user_id] = client

            return client

        except Exception:
            logger.exception(
                "Telegram clientni ulashda xatolik: "
                "user=%s",
                user_id,
            )

            try:
                await client.disconnect()
            except Exception:
                pass

            return None

    # =====================================================
    # START PHONE LOGIN
    # =====================================================

    async def start_phone_login(
        self,
        user_id: int,
        phone: str,
    ) -> dict[str, Any]:

        lock = self._get_lock(user_id)

        async with lock:

            try:
                old_client = (
                    self.pending_clients.get(
                        user_id
                    )
                )

                if old_client:
                    try:
                        await old_client.disconnect()
                    except Exception:
                        pass

                client = self._create_client(
                    user_id
                )

                await client.connect()

                if await client.is_user_authorized():

                    self.clients[user_id] = client

                    return {
                        "status": "already_authorized",
                        "telegram_id": (
                            await self._get_telegram_id(
                                client
                            )
                        ),
                    }

                await client.send_code_request(
                    phone
                )

                self.pending_clients[
                    user_id
                ] = client

                self.pending_phones[
                    user_id
                ] = phone

                return {
                    "status": "code_sent"
                }

            except FloodWaitError as error:

                return {
                    "status": "flood_wait",
                    "seconds": error.seconds,
                }

            except Exception as error:

                logger.exception(
                    "Telegram code yuborishda "
                    "xatolik: user=%s",
                    user_id,
                )

                return {
                    "status": "error",
                    "error": str(error),
                }

    # =====================================================
    # SIGN IN CODE
    # =====================================================

    async def sign_in_code(
        self,
        user_id: int,
        phone: str,
        code: str,
    ) -> dict[str, Any]:

        client = self.pending_clients.get(
            user_id
        )

        if client is None:
            return {
                "status": "session_not_found"
            }

        try:

            await client.sign_in(
                phone=phone,
                code=code,
            )

            telegram_id = (
                await self._get_telegram_id(
                    client
                )
            )

            self.clients[user_id] = client

            self.pending_clients.pop(
                user_id,
                None,
            )

            self.pending_phones.pop(
                user_id,
                None,
            )

            return {
                "status": "authorized",
                "telegram_id": telegram_id,
                "username": (
                    await self._get_username(
                        client
                    )
                ),
            }

        except SessionPasswordNeededError:

            return {
                "status": "password_required"
            }

        except PhoneCodeInvalidError:

            return {
                "status": "invalid_code"
            }

        except PhoneCodeExpiredError:

            await self._cleanup_pending(
                user_id
            )

            return {
                "status": "expired_code"
            }

        except FloodWaitError as error:

            return {
                "status": "flood_wait",
                "seconds": error.seconds,
            }

        except Exception as error:

            logger.exception(
                "Telegram code login error: "
                "user=%s",
                user_id,
            )

            return {
                "status": "error",
                "error": str(error),
            }

    # =====================================================
    # SIGN IN PASSWORD
    # =====================================================

    async def sign_in_password(
        self,
        user_id: int,
        password: str,
    ) -> dict[str, Any]:

        client = self.pending_clients.get(
            user_id
        )

        if client is None:
            return {
                "status": "session_not_found"
            }

        try:

            await client.sign_in(
                password=password
            )

            telegram_id = (
                await self._get_telegram_id(
                    client
                )
            )

            self.clients[user_id] = client

            self.pending_clients.pop(
                user_id,
                None,
            )

            self.pending_phones.pop(
                user_id,
                None,
            )

            return {
                "status": "authorized",
                "telegram_id": telegram_id,
                "username": (
                    await self._get_username(
                        client
                    )
                ),
            }

        except PasswordHashInvalidError:

            return {
                "status": "invalid_password"
            }

        except FloodWaitError as error:

            return {
                "status": "flood_wait",
                "seconds": error.seconds,
            }

        except Exception as error:

            logger.exception(
                "Telegram 2FA error: user=%s",
                user_id,
            )

            return {
                "status": "error",
                "error": str(error),
            }

    # =====================================================
    # GET ME
    # =====================================================

    async def get_me(
        self,
        user_id: int,
    ) -> Any | None:

        client = await self.get_client(
            user_id
        )

        if client is None:
            return None

        try:
            return await client.get_me()

        except Exception:
            logger.exception(
                "get_me xatosi: user=%s",
                user_id,
            )

            return None

    # =====================================================
    # AUTHORIZED
    # =====================================================

    async def is_authorized(
        self,
        user_id: int,
    ) -> bool:

        client = await self.get_client(
            user_id
        )

        if client is None:
            return False

        try:
            return await client.is_user_authorized()

        except Exception:
            return False

    # =====================================================
    # LOGOUT
    # =====================================================

    async def logout(
        self,
        user_id: int,
    ) -> bool:

        lock = self._get_lock(user_id)

        async with lock:

            client = self.clients.pop(
                user_id,
                None,
            )

            if client is None:
                client = (
                    self.pending_clients.pop(
                        user_id,
                        None,
                    )
                )

            self.pending_phones.pop(
                user_id,
                None,
            )

            if client:

                try:

                    if await client.is_connected():
                        await client.log_out()

                except Exception:
                    logger.exception(
                        "Telegram logout xatosi: "
                        "user=%s",
                        user_id,
                    )

                try:
                    await client.disconnect()
                except Exception:
                    pass

            session_file = Path(
                self._session_path(
                    user_id
                )
            ).with_suffix(".session")

            if session_file.exists():
                try:
                    session_file.unlink()
                except Exception:
                    logger.exception(
                        "Session faylini o'chirishda "
                        "xatolik: user=%s",
                        user_id,
                    )

            return True

    # =====================================================
    # CLEANUP
    # =====================================================

    async def _cleanup_pending(
        self,
        user_id: int,
    ) -> None:

        client = self.pending_clients.pop(
            user_id,
            None,
        )

        self.pending_phones.pop(
            user_id,
            None,
        )

        if client:

            try:
                await client.disconnect()
            except Exception:
                pass

    # =====================================================
    # HELPERS
    # =====================================================

    async def _get_telegram_id(
        self,
        client: TelegramClient,
    ) -> int:

        me = await client.get_me()

        if not me:
            raise RuntimeError(
                "Telegram user ma'lumotlari olinmadi."
            )

        return int(me.id)

    async def _get_username(
        self,
        client: TelegramClient,
    ) -> str | None:

        me = await client.get_me()

        if not me:
            return None

        return getattr(
            me,
            "username",
            None,
        )

    # =====================================================
    # START EXISTING SESSIONS
    # =====================================================

    async def load_existing_sessions(
        self,
    ) -> list[int]:

        loaded_users: list[int] = []

        session_files = list(
            self.session_dir.glob(
                "*.session"
            )
        )

        for session_file in session_files:

            try:

                name = session_file.stem

                if not name.startswith(
                    "user_"
                ):
                    continue

                user_id = int(
                    name.replace(
                        "user_",
                        "",
                        1,
                    )
                )

                client = self._create_client(
                    user_id
                )

                await client.connect()

                if await client.is_user_authorized():

                    self.clients[
                        user_id
                    ] = client

                    loaded_users.append(
                        user_id
                    )

                else:

                    await client.disconnect()

            except Exception:
                logger.exception(
                    "Session yuklashda xatolik: %s",
                    session_file,
                )

        logger.info(
            "Mavjud Telegram sessionlar yuklandi: %s",
            len(loaded_users),
        )

        return loaded_users

    # =====================================================
    # SHUTDOWN
    # =====================================================

    async def shutdown(self) -> None:

        clients = list(
            self.clients.values()
        )

        pending = list(
            self.pending_clients.values()
        )

        self.clients.clear()
        self.pending_clients.clear()
        self.pending_phones.clear()

        for client in (
            clients + pending
        ):

            try:
                if client.is_connected():
                    await client.disconnect()
            except Exception:
                logger.exception(
                    "Telegram client shutdown xatosi."
                )

        logger.info(
            "Telegram Client Manager to'xtatildi."
        )


telegram_client_manager = (
    TelegramClientManager()
)