from datetime import datetime, timedelta, timezone
from vaporeon_bot.database import claim_cooldown, complete_daily_quest, get_or_create_daily_encounter, get_or_create_daily_quest, get_user_stats, leaderboard, record_boop, record_encounter, record_feed, record_hug, record_pet, record_photo, record_play, record_splash, server_totals, unknown_user_ids, update_display_name

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


def test_activity_leaderboards_use_display_names_and_top_three(tmp_path):
    path = tmp_path / "vaporeon.db"
    record_pet(1, 1, path, display_name="Misty")
    record_pet(2, 1, path, display_name="Brock")
    record_pet(2, 1, path, display_name="Brock")
    record_pet(3, 1, path, display_name="May")
    record_pet(4, 1, path, display_name="Dawn")
    record_splash(1, display_name="Misty", path=path)
    record_hug(1, display_name="Misty", path=path)
    record_encounter(1, display_name="Misty", path=path)
    record_photo(1, display_name="Misty", path=path)
    assert leaderboard("pets", path=path) == [("Brock", 2), ("Dawn", 1), ("May", 1)]
    totals = server_totals(path)
    assert (totals["pets"], totals["hugs"], totals["splashes"], totals["encounters"], totals["photos"]) == (5, 1, 1, 1, 1)


def test_historic_display_names_can_be_backfilled(tmp_path):
    path = tmp_path / "vaporeon.db"
    record_pet(9, 1, path)
    assert unknown_user_ids(path) == [9]
    update_display_name(9, "Vaporeon Fan", path)
    assert unknown_user_ids(path) == []
    assert leaderboard("pets", path=path) == [("Vaporeon Fan", 1)]


def test_daily_quest_is_personal_and_can_only_complete_once(tmp_path):
    path = tmp_path / "vaporeon.db"
    assert get_or_create_daily_quest(9, "2026-08-20", "hug", path) == ("hug", False)
    assert get_or_create_daily_quest(9, "2026-08-20", "pet", path) == ("hug", False)
    assert not complete_daily_quest(9, "pet", "2026-08-20", path)
    assert complete_daily_quest(9, "hug", "2026-08-20", path)
    assert not complete_daily_quest(9, "hug", "2026-08-20", path)


def test_play_counter_tracks_affection(tmp_path):
    path = tmp_path / "vaporeon.db"
    stats = record_play(9, 3, display_name="Player", path=path)
    assert (stats.plays, stats.affection) == (1, 3)
    assert leaderboard("plays", path=path) == [("Player", 1)]
