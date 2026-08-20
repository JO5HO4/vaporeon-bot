from datetime import datetime, timedelta, timezone

from vaporeon_bot.database import (
    apply_battle_status,
    apply_splash_damage,
    consume_battle_status,
    get_active_statuses,
    get_battle_card,
    get_battle_hp,
    get_weather,
    start_rain,
)


def test_splash_damage_persists_and_caps_at_zero(tmp_path):
    path = tmp_path / "vaporeon.db"
    now = datetime(2026, 8, 20, tzinfo=timezone.utc)
    first = apply_splash_damage(9, 30, path, now)
    second = apply_splash_damage(9, 90, path, now + timedelta(minutes=1))
    assert (first.hp_before, first.hp_after, first.damage_dealt) == (100, 70, 30)
    assert (second.hp_before, second.hp_after, second.damage_dealt) == (70, 0, 70)


def test_battle_hp_recovers_after_thirty_minutes(tmp_path):
    path = tmp_path / "vaporeon.db"
    now = datetime(2026, 8, 20, tzinfo=timezone.utc)
    apply_splash_damage(9, 30, path, now)
    assert get_battle_hp(9, path, now + timedelta(minutes=29)) == 70
    assert get_battle_hp(9, path, now + timedelta(minutes=30)) == 100
    hit = apply_splash_damage(9, 10, path, now + timedelta(minutes=30))
    assert (hit.recovered, hit.hp_before, hit.hp_after) == (True, 100, 90)


def test_battle_card_records_faints_and_last_attack(tmp_path):
    path = tmp_path / "vaporeon.db"
    now = datetime(2026, 8, 20, tzinfo=timezone.utc)
    hit = apply_splash_damage(9, 100, path, now, attacker_id=4, attacker_name="Splashy", move_name="Hydro Pump")
    target = get_battle_card(9, path, now)
    attacker = get_battle_card(4, path, now)
    assert hit.fainted is True
    assert (target.hp, target.losses, target.last_attacker, target.last_move) == (0, 1, "Splashy", "Hydro Pump")
    assert attacker.wins == 1


def test_statuses_expire_and_can_be_consumed(tmp_path):
    path = tmp_path / "vaporeon.db"
    now = datetime(2026, 8, 20, tzinfo=timezone.utc)
    apply_battle_status(9, "soaked", path, now)
    assert get_active_statuses(9, path, now) == {"soaked"}
    assert consume_battle_status(9, "soaked", path, now) is True
    assert get_active_statuses(9, path, now) == set()
    apply_battle_status(9, "slippery", path, now)
    assert get_active_statuses(9, path, now + timedelta(minutes=5)) == set()


def test_rain_is_scoped_to_server_and_expires(tmp_path):
    path = tmp_path / "vaporeon.db"
    now = datetime(2026, 8, 20, tzinfo=timezone.utc)
    weather = start_rain(100, path, now)
    assert weather is not None and weather[0] == "rainy"
    assert get_weather(101, path, now) is None
    assert get_weather(100, path, now) is not None
    assert get_weather(100, path, now + timedelta(hours=1)) is None
