from datetime import datetime, timedelta, timezone
from vaporeon_bot.database import add_discovery, add_inventory_item, claim_cooldown, complete_daily_quest, consume_inventory_item, cooldown_remaining, daily_quest_status, discovery_details_for_user, discoveries_for_user, discovery_count, get_or_create_daily_encounter, get_or_create_daily_quest, get_ripple_duel_stats, get_user_stats, inventory_for_user, leaderboard, leaderboard_with_titles, record_boop, record_daily_participation, record_dive, record_duel_result, record_encounter, record_feed, record_hug, record_pet, record_photo, record_play, record_ripple_duel_result, record_splash, record_tide_duel_result, server_totals, set_equipped_title, tide_duel_move_uses, transfer_discovery, transfer_inventory_item, unknown_user_ids, update_display_name
from vaporeon_bot.constants import BOOP_OUTCOME_WEIGHTS
from vaporeon_bot.duels import Move, new_duel

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
    assert get_or_create_daily_quest(9, "2026-08-20", "hug", path) == ("hug", False, True)
    assert get_or_create_daily_quest(9, "2026-08-20", "pet", path) == ("hug", False, False)
    assert not complete_daily_quest(9, "pet", "2026-08-20", path)
    assert complete_daily_quest(9, "hug", "2026-08-20", path)
    assert not complete_daily_quest(9, "hug", "2026-08-20", path)
    assert daily_quest_status(9, "2026-08-20", path) == ("hug", True)
    assert daily_quest_status(9, "2026-08-21", path) is None


def test_play_counter_tracks_affection(tmp_path):
    path = tmp_path / "vaporeon.db"
    stats = record_play(9, 3, display_name="Player", path=path)
    assert (stats.plays, stats.affection) == (1, 3)
    assert leaderboard("plays", path=path) == [("Player", 1)]


def test_play_can_reduce_affection_without_going_below_zero(tmp_path):
    path = tmp_path / "vaporeon.db"
    record_play(9, 3, display_name="Player", path=path)
    stats = record_play(9, -5, display_name="Player", path=path)
    assert (stats.plays, stats.affection) == (2, 0)


def test_dive_counter_and_inventory_are_durable(tmp_path):
    path = tmp_path / "vaporeon.db"
    stats = record_dive(9, 5, display_name="Diver", path=path)
    add_inventory_item(9, "Potion", path=path)
    add_inventory_item(9, "Potion", 2, path=path)
    assert (stats.dives, stats.affection) == (1, 5)
    assert inventory_for_user(9, path) == {"Potion": 3}
    assert consume_inventory_item(9, "Potion", path)
    assert inventory_for_user(9, path) == {"Potion": 2}


def test_cooldown_status_is_read_only(tmp_path):
    path = tmp_path / "vaporeon.db"
    now = datetime(2026, 8, 20, tzinfo=timezone.utc)
    assert claim_cooldown(9, "dive", 3600, path, now) == 0
    assert cooldown_remaining(9, "dive", 3600, path, now + timedelta(minutes=15)) == 45 * 60
    assert cooldown_remaining(9, "dive", 3600, path, now + timedelta(hours=1)) == 0


def test_cosmetic_discoveries_are_separate_from_the_item_bag(tmp_path):
    path = tmp_path / "vaporeon.db"
    add_discovery(9, "Pearl", path)
    add_discovery(9, "Pearl", path)
    add_discovery(4, "Sea Glass", path)
    assert discoveries_for_user(9, path) == {"Pearl": 2}
    assert discovery_count(9, path) == 2
    assert discovery_count(path=path) == 3


def test_discoveries_record_the_first_found_date(tmp_path):
    path = tmp_path / "vaporeon.db"
    add_discovery(9, "Tiny Blue Bottle", path)
    details = discovery_details_for_user(9, path)
    assert details["Tiny Blue Bottle"].quantity == 1
    assert details["Tiny Blue Bottle"].first_found_at is not None


def test_boop_can_lose_one_affection_without_going_below_zero(tmp_path):
    path = tmp_path / "vaporeon.db"
    stats = record_boop(9, -1, display_name="Booper", path=path)
    assert (stats.boops, stats.affection) == (1, 0)
    assert sum(BOOP_OUTCOME_WEIGHTS.values()) == 1
    average = BOOP_OUTCOME_WEIGHTS["accept"] + BOOP_OUTCOME_WEIGHTS["splash"] - BOOP_OUTCOME_WEIGHTS["offended"]
    assert round(average, 2) == 0.75


def test_titles_and_rainy_splashes_are_durable(tmp_path):
    path = tmp_path / "vaporeon.db"
    record_splash(9, path=path, rainy=True)
    set_equipped_title(9, "First Splash", path)
    stats = get_user_stats(9, path)
    assert (stats.rainy_splashes, stats.equipped_title) == (1, "First Splash")
    assert leaderboard_with_titles("splashes", path=path) == [("Unknown trainer", 1, "First Splash")]


def test_daily_participation_keeps_best_streak_after_a_missed_day(tmp_path):
    path = tmp_path / "vaporeon.db"
    first, added = record_daily_participation(9, "2026-08-20", path)
    second, added_second = record_daily_participation(9, "2026-08-21", path)
    after_gap, added_gap = record_daily_participation(9, "2026-08-23", path)
    repeated, added_repeat = record_daily_participation(9, "2026-08-23", path)
    assert (added, added_second, added_gap, added_repeat) == (True, True, True, False)
    assert (first.daily_current_streak, second.daily_current_streak) == (1, 2)
    assert (after_gap.daily_participations, after_gap.daily_current_streak, after_gap.daily_best_streak) == (3, 1, 2)
    assert repeated == after_gap


def test_gifts_transfer_safe_items_and_only_spare_common_cosmetics(tmp_path):
    path = tmp_path / "vaporeon.db"
    add_inventory_item(9, "Potion", path=path)
    assert transfer_inventory_item(9, 4, "Potion", path)
    assert inventory_for_user(9, path) == {}
    assert inventory_for_user(4, path) == {"Potion": 1}
    add_discovery(9, "Sea Glass", path)
    assert not transfer_discovery(9, 4, "Sea Glass", path)
    add_discovery(9, "Sea Glass", path)
    assert transfer_discovery(9, 4, "Sea Glass", path)
    assert discoveries_for_user(9, path) == {"Sea Glass": 1}
    assert discoveries_for_user(4, path) == {"Sea Glass": 1}


def test_duel_results_are_durable_and_do_not_change_affection(tmp_path):
    path = tmp_path / "vaporeon.db"
    winner, loser = record_duel_result(9, 4, path, winner_name="Winner", loser_name="Loser")
    assert (winner.duels, winner.duel_wins, winner.affection) == (1, 1, 0)
    assert (loser.duels, loser.duel_losses, loser.affection) == (1, 1, 0)
    assert server_totals(path)["duels"] == 1
    assert leaderboard("duel_wins", path=path) == [("Winner", 1)]


def test_ripple_duel_stats_are_durable_and_do_not_change_affection(tmp_path):
    path = tmp_path / "vaporeon.db"
    record_ripple_duel_result(9, 4, winner_name="Winner", loser_name="Loser", winner_rounds=3, loser_rounds=1, ties=2,
                              winner_moves={"Aqua Jet": 3, "Hydro Charge": 2}, loser_moves={"Water Veil": 3},
                              winner_ripple_used=True, loser_ripple_used=False, path=path)
    winner, loser = get_ripple_duel_stats(9, path), get_ripple_duel_stats(4, path)
    assert (winner.duels_played, winner.duels_won, winner.rounds_won, winner.ties, winner.aqua_jet_uses, winner.ripple_reads_used) == (1, 1, 3, 2, 3, 1)
    assert (loser.duels_played, loser.duels_lost, loser.rounds_lost, loser.water_veil_uses) == (1, 1, 3, 3)
    assert get_user_stats(9, path).affection == 0


def test_tide_duel_persists_only_aggregate_outcomes_and_move_uses(tmp_path):
    path = tmp_path / "vaporeon.db"
    duel = new_duel(9, "Winner", 1000, 4, "Loser", 1000)
    duel.challenger.history = [Move.GENTLE_SPLASH, Move.HYDRO_PUMP]
    duel.opponent.history = [Move.WATER_GUN, Move.WATER_VEIL]
    duel.challenger.ripple_used = True
    record_tide_duel_result(9, duel.challenger, duel.opponent, path)
    stats = get_ripple_duel_stats(9, path)
    assert (stats.duels_played, stats.duels_won, stats.rounds_played, stats.ripple_reads_used) == (1, 1, 2, 1)
    assert tide_duel_move_uses(9, path) == {"Gentle Splash": 1, "Hydro Pump": 1}
    assert get_user_stats(9, path).affection == 0
