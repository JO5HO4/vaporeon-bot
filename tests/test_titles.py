from datetime import datetime, timezone

from vaporeon_bot.database import apply_splash_damage, get_battle_card, record_feed, record_splash
from vaporeon_bot.titles import unlocked_titles


def test_activity_titles_unlock_from_durable_stats(tmp_path):
    path = tmp_path / "vaporeon.db"
    record_splash(9, path=path)
    for _ in range(25):
        record_feed(9, 2, path)
    apply_splash_damage(9, 50, path, datetime(2026, 8, 20, tzinfo=timezone.utc), move_name="Hydro Pump")
    from vaporeon_bot.database import get_user_stats

    titles = unlocked_titles(get_user_stats(9, path), get_battle_card(9, path), ())
    assert {"First Splash", "Berry Benefactor", "Hydro Pump Survivor"}.issubset(titles)
