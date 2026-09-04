from app.handlers.start import router as start_router
from app.handlers.main import router as main_router
from app.handlers.password_lock import router as password_lock_router
from app.handlers.telegram_connect import router as telegram_connect_router
from app.handlers.agent import router as agent_router
from app.handlers.auto_replies import router as auto_replies_router
from app.handlers.first_message import router as first_message_router
from app.handlers.assistant import router as assistant_router
from app.handlers.statistics import router as statistics_router
from app.handlers.language import router as language_router
from app.handlers.settings import router as settings_router
from app.handlers.activity import router as activity_router
from app.handlers.info import router as info_router
from app.handlers.admin import router as admin_router
from app.handlers.admin_payments import router as admin_payments_router


__all__ = [
    "start_router",
    "main_router",
    "password_lock_router",
    "telegram_connect_router",
    "agent_router",
    "auto_replies_router",
    "first_message_router",
    "assistant_router",
    "statistics_router",
    "language_router",
    "settings_router",
    "activity_router",
    "info_router",
    "admin_router",
    "admin_payments_router",
]
