from vaporeon_bot.games import SCENARIOS


def test_every_play_scenario_has_one_risky_and_two_rewarding_choices():
    for scenario in SCENARIOS:
        assert sorted(choice["affection"] for choice in scenario["choices"]) == [-5, 2, 5]
