import pytest

from vaporeon_bot.splash import next_splash, unlocked_splash


@pytest.mark.parametrize(("affection", "name"), [(0, "Gentle Splash"), (9, "Gentle Splash"), (10, "Water Gun"), (49, "Water Pulse"), (80, "Hydro Pump"), (999, "Tidal Wave")])
def test_splash_moves_unlock_every_ten_affection(affection, name):
    assert unlocked_splash(affection).name == name


def test_next_splash_reports_the_next_unlock():
    assert next_splash(12).name == "Bubble Beam"
    assert next_splash(90) is None


def test_negative_affection_is_rejected():
    with pytest.raises(ValueError):
        unlocked_splash(-1)
