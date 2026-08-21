from datetime import datetime, timezone

from vaporeon_bot.game_time import game_day, pacific_now, seconds_until_next_game_day


def test_daily_content_uses_pacific_calendar_day():
    utc_evening = datetime(2026, 8, 21, 6, 30, tzinfo=timezone.utc)
    assert pacific_now(utc_evening).isoformat().startswith("2026-08-20T23:30")
    assert game_day(utc_evening) == "2026-08-20"
    assert seconds_until_next_game_day(utc_evening) == 30 * 60


def test_pacific_time_handles_daylight_saving_time():
    utc_time = datetime(2026, 7, 1, 7, 0, tzinfo=timezone.utc)
    assert pacific_now(utc_time).utcoffset().total_seconds() == -7 * 60 * 60
