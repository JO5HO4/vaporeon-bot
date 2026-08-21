"""Shared Pacific-time calendar rules for Vaporeon's daily content."""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


PACIFIC_TIME = ZoneInfo("America/Los_Angeles")


def pacific_now(now: datetime | None = None) -> datetime:
    """Return the current time in Los Angeles, including daylight-saving changes."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("Daily game time must be timezone-aware.")
    return current.astimezone(PACIFIC_TIME)


def game_day(now: datetime | None = None) -> str:
    """Return the Pacific-calendar day used for daily quests and encounters."""
    return pacific_now(now).date().isoformat()


def seconds_until_next_game_day(now: datetime | None = None) -> int:
    """Return seconds until the next midnight in Pacific time."""
    local = pacific_now(now)
    next_midnight = datetime.combine(local.date() + timedelta(days=1), time.min, tzinfo=PACIFIC_TIME)
    return max(1, int((next_midnight - local).total_seconds()))
