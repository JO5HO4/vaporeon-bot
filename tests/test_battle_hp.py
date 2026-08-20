from datetime import datetime, timedelta, timezone

from vaporeon_bot.database import apply_splash_damage, get_battle_hp


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
