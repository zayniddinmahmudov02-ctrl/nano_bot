from aiogram.fsm.state import State, StatesGroup


class PasswordLockStates(StatesGroup):
    """
    Bot paroli (inactivity lock) uchun FSM holati.

    Bu state ham `app/middlewares/password_lock.py`
    (challenge ko'rsatish/tekshirish uchun), ham
    `app/handlers/password_lock.py` (parolni qabul qilish
    uchun) tomonidan ishlatiladi — shuning uchun umumiy joyda.
    """

    waiting_password_challenge = State()


__all__ = [
    "PasswordLockStates",
]
