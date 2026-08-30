from datetime import datetime, timedelta
from secrets import token_urlsafe

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TRIAL_DAYS
from app.database.models import (
    Referral,
    Statistics,
    Subscription,
    User,
    UserSettings,
)


async def get_or_create_user(
    db: AsyncSession,
    telegram_user,
    referral_code: str | None = None,
) -> tuple[User, bool]:

    result = await db.execute(
        select(User).where(
            User.telegram_id == telegram_user.id
        )
    )

    user = result.scalar_one_or_none()

    if user:
        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
        user.last_name = telegram_user.last_name

        await db.commit()

        return user, False

    user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name,
        language="uz",
        is_active=True,
    )

    db.add(user)

    await db.flush()

    settings = UserSettings(
        user_id=user.id,
        display_first_name=telegram_user.first_name,
        display_last_name=telegram_user.last_name,
        language="uz",
    )

    statistics = Statistics(
        user_id=user.id,
        people_replied=0,
        total_auto_replies=0,
        today_replies=0,
        month_replies=0,
        last_reset_date=datetime.utcnow(),
    )

    now = datetime.utcnow()

    subscription = Subscription(
        user_id=user.id,
        status="trial",
        trial_started_at=now,
        trial_ends_at=now + timedelta(days=TRIAL_DAYS),
    )

    referral = Referral(
        user_id=user.id,
        referral_code=generate_referral_code(),
        referral_count=0,
    )

    db.add(settings)
    db.add(statistics)
    db.add(subscription)
    db.add(referral)

    await db.flush()

    # Referral mavjud bo'lsa, uni tekshiramiz.
    if referral_code:
        result = await db.execute(
            select(Referral).where(
                Referral.referral_code == referral_code
            )
        )

        inviter = result.scalar_one_or_none()

        if inviter and inviter.user_id != user.id:
            inviter.referral_count += 1
            referral.referred_by = inviter.user_id

    await db.commit()

    return user, True


def generate_referral_code() -> str:
    return token_urlsafe(6).replace("-", "").replace("_", "")[:10]