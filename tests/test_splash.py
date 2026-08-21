import pytest

from vaporeon_bot.splash import HUGE_MISS_MESSAGES, MOVE_FLAVOR, NEAR_FAINT_MESSAGES, SPLASH_MOVES, next_splash, splash_by_name, unlocked_splash


@pytest.mark.parametrize(("affection", "name"), [(0, "Gentle Splash"), (9, "Gentle Splash"), (10, "Water Gun"), (25, "Bubble Beam"), (50, "Aqua Jet"), (100, "Water Pulse"), (200, "Brine"), (300, "Aqua Tail"), (500, "Surf"), (750, "Hydro Pump"), (999, "Hydro Pump"), (1000, "Tidal Wave")])
def test_splash_moves_unlock_on_scaled_affection_thresholds(affection, name):
    assert unlocked_splash(affection).name == name


def test_next_splash_reports_the_next_unlock():
    assert next_splash(12).name == "Bubble Beam"
    assert next_splash(999).name == "Tidal Wave"
    assert next_splash(1000) is None


def test_negative_affection_is_rejected():
    with pytest.raises(ValueError):
        unlocked_splash(-1)


def test_splash_moves_can_be_selected_by_name():
    assert splash_by_name("gentle splash").fictional_damage == 1
    assert splash_by_name("hydro pump").fictional_damage == 100
    assert splash_by_name("  Surf ").name == "Surf"
    assert splash_by_name("not a move") is None


def test_every_splash_move_has_its_own_flavor_pool():
    assert {move.name for move in SPLASH_MOVES} == set(MOVE_FLAVOR)
    assert all(len(flavor) >= 3 for flavor in MOVE_FLAVOR.values())


def test_large_moves_have_dramatic_miss_and_near_faint_flavor():
    assert set(HUGE_MISS_MESSAGES) == {"Hydro Pump", "Tidal Wave"}
    assert all(len(messages) >= 3 for messages in HUGE_MISS_MESSAGES.values())
    assert all("{hp}" in message for message in NEAR_FAINT_MESSAGES)
