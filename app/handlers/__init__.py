from app.handlers.start import router as start_router
from app.handlers.telegram_connect import router as telegram_connect_router
from app.handlers.auto_replies import router as auto_replies_router
from app.handlers.first_message import router as first_message_router
from app.handlers.referrals import router as referrals_router
from app.handlers.statistics import router as statistics_router
from app.handlers.premium import router as premium_router
from app.handlers.language import router as language_router
from app.handlers.settings import router as settings_router
from app.handlers.admin import router as admin_router


__all__ = [
    "start_router",
    "telegram_connect_router",
    "auto_replies_router",
    "first_message_router",
    "referrals_router",
    "statistics_router",
    "premium_router",
    "language_router",
    "settings_router",
    "admin_router",
]