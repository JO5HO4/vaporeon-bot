import random

import pytest

from vaporeon_bot.duels import BEATS, DuelManager, Move, generate_ripple_read, new_duel, recent_history, resolve_round


@pytest.mark.parametrize("winner,loser", [(Move.AQUA_JET, Move.HYDRO_CHARGE), (Move.HYDRO_CHARGE, Move.WATER_VEIL), (Move.WATER_VEIL, Move.AQUA_JET)])
def test_every_rps_matchup_and_reverse(winner, loser):
    assert resolve_round(winner, loser).winner is winner
    assert resolve_round(loser, winner).winner is winner
    assert BEATS[winner] is loser


@pytest.mark.parametrize("move", list(Move))
def test_same_move_is_a_tie(move):
    result = resolve_round(move, move)
    assert result.tied and result.winner is None


@pytest.mark.parametrize("actual", list(Move))
def test_ripple_read_always_contains_actual_move_and_two_distinct_choices(actual):
    pairs = set()
    for seed in range(20):
        clue = generate_ripple_read(actual, random.Random(seed))
        assert clue.flavor
        assert len(clue.possible_moves) == 2
        assert actual in clue.possible_moves
        assert clue.possible_moves[0] != clue.possible_moves[1]
        assert all(isinstance(move, Move) for move in clue.possible_moves)
        pairs.add(frozenset(clue.possible_moves))
    assert len(pairs) == 2


def test_history_displays_only_last_four_revealed_moves():
    history = [Move.AQUA_JET, Move.HYDRO_CHARGE, Move.WATER_VEIL, Move.AQUA_JET, Move.AQUA_JET, Move.HYDRO_CHARGE]
    assert recent_history(history) == "Water Veil → Aqua Jet → Aqua Jet → Hydro Charge"
    assert recent_history([]) == "No previous moves yet."


def test_best_of_five_progression_and_ties_do_not_award_points():
    duel = new_duel(1, "Joshua", 2, "Alex", rng=random.Random(1))
    tie = duel.lock_move(1, Move.AQUA_JET)
    assert not tie.round_resolved
    update = duel.lock_move(2, Move.AQUA_JET)
    assert update.tied and (duel.challenger.wins, duel.opponent.wins) == (0, 0)
    for a, b, score in ((Move.AQUA_JET, Move.HYDRO_CHARGE, (1, 0)), (Move.HYDRO_CHARGE, Move.WATER_VEIL, (2, 0)), (Move.WATER_VEIL, Move.AQUA_JET, (3, 0))):
        duel.lock_move(1, a)
        update = duel.lock_move(2, b)
        assert (duel.challenger.wins, duel.opponent.wins) == score
    assert update.finished and update.winner_id == 1
    assert len(duel.challenger.history) == len(duel.opponent.history) == 4


def test_ripple_read_requires_opponent_lock_and_is_consumed_once():
    duel = new_duel(1, "Joshua", 2, "Alex")
    allowed, _ = duel.can_ripple_read(1)
    assert not allowed
    duel.lock_move(2, Move.HYDRO_CHARGE)
    allowed, _ = duel.can_ripple_read(1)
    assert allowed
    clue = duel.use_ripple_read(1)
    assert Move.HYDRO_CHARGE in clue.possible_moves
    assert duel.player(1).ripple_used
    assert not duel.can_ripple_read(1)[0]
    duel.lock_move(1, Move.AQUA_JET)
    assert duel.challenger.history == [Move.AQUA_JET]
    assert duel.opponent.history == [Move.HYDRO_CHARGE]


def test_locked_choice_is_not_in_shared_card_and_cannot_change():
    duel = new_duel(1, "Joshua", 2, "Alex")
    duel.lock_move(1, Move.WATER_VEIL)
    assert "**Joshua:** Water Veil" not in duel.card_text()
    with pytest.raises(ValueError, match="already locked"):
        duel.lock_move(1, Move.AQUA_JET)


def test_manager_prevents_two_active_duels_and_cleans_up():
    manager = DuelManager()
    assert manager.create_invitation(1, 2)
    assert not manager.create_invitation(1, 3)
    duel = manager.accept_invitation(1, "Joshua", 2, "Alex")
    assert manager.find_duel(1) is duel
    manager.remove_duel(1, 2)
    assert not manager.is_active(1)
