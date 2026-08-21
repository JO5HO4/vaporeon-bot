from vaporeon_bot.duels import TIDE_BURST_COST, new_duel


class FixedRng:
    def __init__(self, *values: float) -> None:
        self.values = iter(values)

    def random(self) -> float:
        return next(self.values)


def test_bubble_combo_brace_and_tide_are_tactical():
    duel = new_duel(1, "Josh", 2, "Alex", rng=FixedRng(0.5, 0.5, 0.5, 0.5))
    first = duel.resolve(1, "bubble_beam")
    assert first.next_player_id == 2
    assert (duel.opponent.hp, duel.challenger.tide, duel.opponent.tide, duel.opponent.drenched) == (86, 20, 10, True)
    duel.resolve(2, "brace")
    duel.resolve(1, "aqua_jet")
    assert duel.opponent.hp == 76  # Drenched bonus is reduced by Brace.
    assert duel.opponent.brace is False


def test_rain_dance_and_tide_burst_have_distinct_roles():
    duel = new_duel(1, "Josh", 2, "Alex", rng=FixedRng(0.5, 0.5, 0.5, 0.5))
    duel.resolve(1, "rain_dance")
    assert duel.rain_turns == 4
    duel.resolve(2, "brace")
    duel.challenger.tide = TIDE_BURST_COST
    assert "tide_burst" in duel.available_actions(1, potion_available=False)
    duel.resolve(1, "tide_burst")
    assert duel.challenger.tide < TIDE_BURST_COST


def test_potion_is_limited_to_one_per_duel():
    duel = new_duel(1, "Josh", 2, "Alex")
    duel.challenger.hp = 50
    duel.resolve(1, "potion", potion_available=True)
    assert duel.challenger.hp == 70
    duel.resolve(2, "brace")
    assert "potion" not in duel.available_actions(1, potion_available=True)
