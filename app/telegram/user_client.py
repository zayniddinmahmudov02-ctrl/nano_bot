import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)

logger = logging.getLogger(__name__)


class TelegramUserClient:
    """
    Nano-Bot uchun shaxsiy Telegram akkauntlarini boshqaradi.

    Har bir user uchun alohida Telethon session ishlatiladi.
    """

    def __init__(self) -> None:
        self.api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
        self.api_hash = os.getenv("TELEGRAM_API_HASH", "")

        self.session_dir = Path(
            os.getenv(
                "TELEGRAM_SESSION_DIR",
                "data/sessions",
            )
        )

        self.session_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.clients: dict[int, TelegramClient] = {}
        self.phone_codes: dict[int, str] = {}

        if not self.api_id or not self.api_hash:
            logger.warning(
                "TELEGRAM_API_ID yoki "
                "TELEGRAM_API_HASH mavjud emas."
            )

    def _session_path(self, user_id: int) -> str:
        """
        Har bir Nano-Bot user uchun alohida session.
        """
        return str(
            self.session_dir / f"user_{user_id}"
        )

    def _get_client(self, user_id: int) -> TelegramClient:
        """
        Mavjud clientni qaytaradi yoki yangi yaratadi.
        """

        if user_id in self.clients:
            return self.clients[user_id]

        client = TelegramClient(
            self._session_path(user_id),
            self.api_id,
            self.api_hash,
        )

        self.clients[user_id] = client

        return client

    async def start_phone_login(
        self,
        user_id: int,
        phone: str,
    ) -> dict:
        """
        Telefon raqam orqali Telegram login jarayonini boshlaydi.
        """

        client = self._get_client(user_id)

        if not client.is_connected():
            await client.connect()

        if await client.is_user_authorized():
            return {
                "status": "already_authorized",
            }

        try:
            result = await client.send_code_request(
                phone
            )

            self.phone_codes[user_id] = result.phone_code_hash

            return {
                "status": "code_sent",
                "phone": phone,
            }

        except FloodWaitError as e:
            return {
                "status": "flood_wait",
                "seconds": e.seconds,
            }

        except Exception as e:
            logger.exception(
                "Telegram code yuborishda xato: %s",
                e,
            )

            return {
                "status": "error",
                "message": str(e),
            }

    async def sign_in_code(
        self,
        user_id: int,
        phone: str,
        code: str,
    ) -> dict:
        """
        Telegram yuborgan login kodini tekshiradi.
        """

        client = self._get_client(user_id)

        if not client.is_connected():
            await client.connect()

        phone_code_hash = self.phone_codes.get(
            user_id
        )

        if not phone_code_hash:
            return {
                "status": "error",
                "message": (
                    "Login kodi topilmadi. "
                    "Qaytadan kod so'rang."
                ),
            }

        try:
            await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash,
            )

            self.phone_codes.pop(
                user_id,
                None,
            )

            me = await client.get_me()

            return {
                "status": "authorized",
                "telegram_id": me.id if me else None,
                "username": (
                    me.username
                    if me
                    else None
                ),
                "first_name": (
                    me.first_name
                    if me
                    else None
                ),
                "last_name": (
                    me.last_name
                    if me
                    else None
                ),
            }

        except SessionPasswordNeededError:
            return {
                "status": "password_required",
            }

        except PhoneCodeInvalidError:
            return {
                "status": "invalid_code",
            }

        except PhoneCodeExpiredError:
            self.phone_codes.pop(
                user_id,
                None,
            )

            return {
                "status": "expired_code",
            }

        except FloodWaitError as e:
            return {
                "status": "flood_wait",
                "seconds": e.seconds,
            }

        except Exception as e:
            logger.exception(
                "Telegram login xatosi: %s",
                e,
            )

            return {
                "status": "error",
                "message": str(e),
            }

    async def sign_in_password(
        self,
        user_id: int,
        password: str,
    ) -> dict:
        """
        Telegram 2FA passwordni tekshiradi.
        """

        client = self._get_client(user_id)

        if not client.is_connected():
            await client.connect()

        try:
            await client.sign_in(
                password=password
            )

            me = await client.get_me()

            return {
                "status": "authorized",
                "telegram_id": me.id if me else None,
                "username": (
                    me.username
                    if me
                    else None
                ),
                "first_name": (
                    me.first_name
                    if me
                    else None
                ),
                "last_name": (
                    me.last_name
                    if me
                    else None
                ),
            }

        except PasswordHashInvalidError:
            return {
                "status": "invalid_password",
            }

        except Exception as e:
            logger.exception(
                "Telegram 2FA xatosi: %s",
                e,
            )

            return {
                "status": "error",
                "message": str(e),
            }

    async def is_authorized(
        self,
        user_id: int,
    ) -> bool:
        """
        User Telegram akkaunti ulanganmi?
        """

        client = self._get_client(user_id)

        if not client.is_connected():
            await client.connect()

        try:
            return await client.is_user_authorized()
        except Exception:
            return False

    async def get_me(
        self,
        user_id: int,
    ):
        """
        Ulangan Telegram akkaunt ma'lumotlarini qaytaradi.
        """

        client = self._get_client(user_id)

        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            return None

        return await client.get_me()

    async def get_client(
        self,
        user_id: int,
    ) -> Optional[TelegramClient]:
        """
        Avto-javob engine uchun authorized client.
        """

        client = self._get_client(user_id)

        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            return None

        return client

    async def disconnect(
        self,
        user_id: int,
    ) -> None:
        """
        Telegram akkauntni vaqtincha uzadi.
        """

        client = self.clients.get(user_id)

        if client:
            await client.disconnect()

    async def logout(
        self,
        user_id: int,
    ) -> None:
        """
        Telegram akkauntdan to'liq logout.
        """

        client = self.clients.get(user_id)

        if client:
            try:
                if not client.is_connected():
                    await client.connect()

                if await client.is_user_authorized():
                    await client.log_out()

            finally:
                await client.disconnect()

            self.clients.pop(
                user_id,
                None,
            )

        session_file = Path(
            f"{self._session_path(user_id)}.session"
        )

        if session_file.exists():
            session_file.unlink()

        self.phone_codes.pop(
            user_id,
            None,
        )


telegram_client_manager = TelegramUserClient()