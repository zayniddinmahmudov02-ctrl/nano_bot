from app.handlers.start import router as start_router
from app.handlers.settings import router as settings_router
from app.handlers.onboarding import router as onboarding_router

__all__ = [
    "start_router",
    "settings_router",
    "onboarding_router",
]