import random

import pytest

from vaporeon_bot.duels import MOVE_DEFINITIONS, DuelManager, Move, Status, generate_ripple_read, move_detail, new_duel, recent_history
from vaporeon_bot.duel_views import final_results_embed


class FixedRng:
    def __init__(self, *values): self.values = iter(values)
    def random(self): return next(self.values, 0.0)
    def choice(self, values): return tuple(values)[0]


def duel(*, rng=None): return new_duel(1, "Joshua", 1000, 2, "Alex", 1000, rng=rng or FixedRng())


def resolve(state, left, right):
    if state.first_picker_id == 1:
        state.lock_move(1, left)
        return state.lock_move(2, right)
    state.lock_move(2, right)
    return state.lock_move(1, left)


def test_canonical_move_definitions_match_the_published_v1_values():
    expected = {
        Move.GENTLE_SPLASH: (6, 1.0, 25, 0, 0), Move.WATER_GUN: (12, .95, 15, 0, 10),
        Move.BUBBLE_BEAM: (16, .90, 10, 1, 25), Move.AQUA_JET: (20, 1.0, -10, 1, 50),
        Move.WATER_VEIL: (0, None, -15, 2, 100), Move.MUDDY_WATER: (25, .85, -25, 2, 200),
        Move.SURF: (32, .90, -40, 2, 300), Move.HYDRO_PUMP: (45, .70, -65, 3, 750),
        Move.HYDRO_CANNON: (60, .60, -100, 0, 1000),
    }
    for move, values in expected.items():
        definition = MOVE_DEFINITIONS[move]
        assert (definition.damage, definition.accuracy, definition.tide_change, definition.cooldown_rounds, definition.affection_unlock) == values
    assert MOVE_DEFINITIONS[Move.BUBBLE_BEAM].status is Status.SOAKED
    assert MOVE_DEFINITIONS[Move.MUDDY_WATER].status is Status.SLIPPERY


def test_tide_builds_caps_and_costs_are_validated_before_locking():
    state = duel(); state.challenger.tide = 90
    resolve(state, Move.GENTLE_SPLASH, Move.GENTLE_SPLASH)
    assert state.challenger.tide == 100
    state.challenger.tide = 64
    state.lock_move(2, Move.GENTLE_SPLASH)
    with pytest.raises(ValueError, match="Requires 65 Tide"):
        state.lock_move(1, Move.HYDRO_PUMP)
    state.challenger.tide = 65
    state.opponent.tide = 0
    state.lock_move(1, Move.HYDRO_PUMP)
    assert state.challenger.tide == 0


def test_all_duel_moves_ignore_affection_but_still_respect_tide_and_cooldowns():
    state = new_duel(1, "Joshua", 0, 2, "Alex", 0)
    assert state.availability(state.challenger, Move.BUBBLE_BEAM)[0]
    assert state.availability(state.challenger, Move.HYDRO_CANNON)[1].startswith("Requires 100 Tide")


def test_cost_and_cooldown_apply_on_miss_and_cooldown_has_exact_round_timing():
    state = duel(rng=FixedRng(.99, 0.0)); state.challenger.tide = 65
    resolve(state, Move.HYDRO_PUMP, Move.GENTLE_SPLASH)
    assert state.challenger.tide == 0 and state.cooldown_remaining(state.challenger, Move.HYDRO_PUMP) == 2
    resolve(state, Move.GENTLE_SPLASH, Move.GENTLE_SPLASH)
    assert state.cooldown_remaining(state.challenger, Move.HYDRO_PUMP) == 1
    resolve(state, Move.GENTLE_SPLASH, Move.GENTLE_SPLASH)
    assert state.cooldown_remaining(state.challenger, Move.HYDRO_PUMP) == 0


@pytest.mark.parametrize("base,effective", [(1.0, .65), (.95, .60), (.90, .55), (.85, .50), (.70, .35), (.60, .25)])
def test_slippery_reduces_accuracy_by_35_points(base, effective):
    state = duel(); state.opponent.statuses.add(Status.SLIPPERY)
    definition = next(item for item in MOVE_DEFINITIONS.values() if item.accuracy == base)
    report = state._attack(state.challenger, state.opponent, definition.move, False)
    assert report.effective_accuracy == pytest.approx(effective)


def test_soaked_bonus_consumes_only_on_successful_damage_and_water_veil_rounds_down():
    state = duel(rng=FixedRng(.99, 0.0)); state.challenger.statuses.add(Status.SOAKED)
    resolve(state, Move.WATER_GUN, Move.GENTLE_SPLASH)
    assert Status.SOAKED in state.challenger.statuses  # Water Gun missed.
    state._rng = FixedRng(0.0, 0.0)
    resolve(state, Move.WATER_GUN, Move.WATER_VEIL)
    assert Status.SOAKED not in state.challenger.statuses
    # 12 × 1.10 = floor(13); Water Veil then floor(6.5) = 6.
    assert state.opponent.hp == 94


def test_slippery_is_consumed_on_an_incoming_attack_attempt_even_when_it_misses():
    state = duel(rng=FixedRng(.99, 0.0)); state.opponent.statuses.add(Status.SLIPPERY)
    resolve(state, Move.WATER_GUN, Move.GENTLE_SPLASH)
    assert Status.SLIPPERY not in state.opponent.statuses


def test_first_picker_lethal_prevents_the_responding_move_from_resolving():
    state = duel(); state.challenger.hp = state.opponent.hp = 20
    state.challenger.tide = state.opponent.tide = 40
    update = resolve(state, Move.SURF, Move.SURF)
    assert update.finished and update.winner_id == 1
    assert state.challenger.hp == 20 and state.opponent.hp == 0
    assert "before it could resolve" in update.text


def test_rain_benefits_both_players_for_three_following_rounds():
    state = duel(); state.challenger.tide = state.opponent.tide = 40
    resolve(state, Move.RAIN_DANCE, Move.RAIN_DANCE)
    assert state.rain_rounds_remaining == 3
    resolve(state, Move.WATER_GUN, Move.WATER_GUN)
    assert state.challenger.hp == state.opponent.hp == 87  # floor(12 * 1.15)
    assert state.rain_rounds_remaining == 2


def test_ripple_reads_are_truthful_nonidentifying_and_private_engine_data():
    for actual in Move:
        for seed in range(10):
            clue = generate_ripple_read(actual, random.Random(seed))
            assert clue.flavor and actual in clue.possible_moves and 2 <= len(clue.possible_moves) <= 4
            for move in clue.possible_moves:
                definition = MOVE_DEFINITIONS[move]
                for property_line in clue.properties:
                    assert (property_line != "Costs Tide" or definition.tide_change < 0)
                    assert (property_line != "Generates Tide" or definition.tide_change > 0)
                    assert (property_line != "Deals at least 20 base damage" or definition.damage >= 20)
                    assert (property_line != "Deals at least 30 base damage" or definition.damage >= 30)


def test_history_is_last_four_and_hidden_choice_never_appears_in_card():
    state = duel(); state.challenger.history = [Move.GENTLE_SPLASH, Move.WATER_GUN, Move.BUBBLE_BEAM, Move.AQUA_JET, Move.SURF]
    assert recent_history(state.challenger.history) == "Water Gun → Bubble Beam → Aqua Jet → Surf"
    state.challenger.tide = 100
    state.lock_move(1, Move.HYDRO_CANNON)
    assert "Hydro Cannon" not in state.card_text()


def test_all_move_cards_render_damage_accuracy_tide_cooldown_effect_and_unlock():
    for definition in MOVE_DEFINITIONS.values():
        rendered = move_detail(definition, available=False, reason="test")
        assert definition.move.value in rendered
        assert f"{definition.damage} dmg" in rendered and "accuracy" in rendered and "Tide:" in rendered and "Cooldown:" in rendered and "Effect:" in rendered
        if definition.status: assert f"{definition.status_chance:.0%} chance" in rendered


def test_manager_excludes_duplicate_invitations_and_cleans_up():
    manager = DuelManager(); assert manager.create_invitation(1, 2); assert not manager.create_invitation(1, 3)
    manager.remove_duel(1, 2); assert not manager.is_active(1)


def test_first_picker_alternates_and_only_responder_can_use_ripple_read():
    state = duel()
    assert state.first_picker_id == 1
    assert not state.can_ripple_read(1)[0]
    with pytest.raises(ValueError, match="Wait for"):
        state.lock_move(2, Move.GENTLE_SPLASH)
    state.lock_move(1, Move.GENTLE_SPLASH)
    assert state.can_ripple_read(2)[0]
    state.lock_move(2, Move.GENTLE_SPLASH)
    assert state.first_picker_id == 2


def test_vaporeon_cpu_locks_only_legal_moves_and_can_begin_each_round():
    state = new_duel(1, "Joshua", 1000, 99, "Vaporeon (CPU)", 1000, opponent_cpu=True)
    opening = state.lock_cpu_move()
    if opening is None:
        state.lock_move(1, Move.GENTLE_SPLASH)
        update = state.lock_cpu_move()
        assert update and update.round_resolved and not state.finished
    else:
        assert state.first_picker_id == 99
        update = state.lock_move(1, Move.GENTLE_SPLASH)
        assert update.round_resolved and not state.finished
    next_cpu = state.lock_cpu_move()
    if state.first_picker_id == 99:
        assert next_cpu and not next_cpu.round_resolved and state.has_locked(99)
    else:
        assert next_cpu is None


def test_final_results_embed_has_clear_outcome_and_final_state():
    state = duel(); state.challenger.hp, state.challenger.tide = 12, 34
    embed = final_results_embed(state, "Round result text", 1)
    assert embed.title == "🏆 Tide Duel Complete"
    assert "Joshua wins" in embed.description and "12/100 HP" in embed.description and "Round result text" in embed.description
