from datetime import datetime, timedelta, timezone
from vaporeon_bot.database import claim_cooldown, get_or_create_daily_encounter, get_user_stats, record_boop, record_feed, record_pet

def test_database_counters_and_affection(tmp_path):
    path = tmp_path / "vaporeon.db"
    assert get_user_stats(9, path).affection == 0
    assert record_pet(9, 1, path).pets == 1
    assert record_boop(9, 0, path).boops == 1
    stats = record_feed(9, 2, path)
    assert (stats.affection, stats.feeds) == (3, 1)

def test_cooldown_and_daily_encounter_are_durable(tmp_path):
    path = tmp_path / "vaporeon.db"; now = datetime(2026, 8, 20, tzinfo=timezone.utc)
    assert claim_cooldown(9, "pet", 300, path, now) == 0
    assert claim_cooldown(9, "pet", 300, path, now + timedelta(seconds=1)) == 299
    first = get_or_create_daily_encounter(10, "2026-08-20", {"mood": "Cozy"}, path)
    assert get_or_create_daily_encounter(10, "2026-08-20", {"mood": "Different"}, path) == first
