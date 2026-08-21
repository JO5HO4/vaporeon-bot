"""Pure rules and lifecycle helpers for the Ripple Duel minigame."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from enum import Enum


class Move(str, Enum):
    AQUA_JET = "Aqua Jet"
    HYDRO_CHARGE = "Hydro Charge"
    WATER_VEIL = "Water Veil"


BEATS = {
    Move.AQUA_JET: Move.HYDRO_CHARGE,
    Move.HYDRO_CHARGE: Move.WATER_VEIL,
    Move.WATER_VEIL: Move.AQUA_JET,
}


@dataclass(frozen=True)
class RoundResult:
    winner: Move | None
    loser: Move | None
    tied: bool


@dataclass(frozen=True)
class RippleReadResult:
    flavor: str
    possible_moves: tuple[Move, Move]


RIPPLE_FLAVOR = {
    frozenset((Move.AQUA_JET, Move.HYDRO_CHARGE)): (
        "The water around them seems restless.",
        "A quick current keeps interrupting a gathering wave.",
        "The ripples are moving with impatient energy.",
    ),
    frozenset((Move.AQUA_JET, Move.WATER_VEIL)): (
        "The ripples feel unusually reactive.",
        "A sudden dart of water disappears behind a soft shimmer.",
        "The surface cannot decide whether to race or reflect.",
    ),
    frozenset((Move.HYDRO_CHARGE, Move.WATER_VEIL)): (
        "The water feels strangely patient.",
        "A deep swell lingers beneath a calm surface.",
        "The pool is quiet, but something is gathering underneath.",
    ),
}
WIN_FLAVOR = {
    (Move.AQUA_JET, Move.HYDRO_CHARGE): ("Aqua Jet darts forward before Hydro Charge can finish building!", "Aqua Jet slips through the opening before the wave gathers."),
    (Move.HYDRO_CHARGE, Move.WATER_VEIL): ("Hydro Charge crashes through the Water Veil!", "The gathering tide rolls straight through Water Veil."),
    (Move.WATER_VEIL, Move.AQUA_JET): ("Water Veil redirects the incoming Aqua Jet!", "Aqua Jet meets a gleaming Water Veil and swerves away."),
}
TIE_FLAVOR = {
    Move.AQUA_JET: "Both Vaporeon choose Aqua Jet and collide in an extremely damp stalemate.",
    Move.HYDRO_CHARGE: "Both Vaporeon gather Hydro Charge at once. The pool holds its breath and nothing gives.",
    Move.WATER_VEIL: "Both Vaporeon raise Water Veil. The duel briefly becomes two very polite puddles.",
}


def resolve_round(move_a: Move, move_b: Move) -> RoundResult:
    """Resolve one RPS round without changing any duel state."""
    if move_a == move_b:
        return RoundResult(None, None, True)
    if BEATS[move_a] == move_b:
        return RoundResult(move_a, move_b, False)
    return RoundResult(move_b, move_a, False)


def generate_ripple_read(actual_move: Move, rng: random.Random | None = None) -> RippleReadResult:
    """Return a truthful two-move clue which never directly reveals a move."""
    source = rng or random.Random()
    candidates = [pair for pair in RIPPLE_FLAVOR if actual_move in pair]
    pair = source.choice(candidates)
    ordered = tuple(move for move in Move if move in pair)
    return RippleReadResult(source.choice(RIPPLE_FLAVOR[pair]), ordered)  # type: ignore[arg-type]


def recent_history(moves: list[Move]) -> str:
    """Format only the last four *resolved* choices for display."""
    return " → ".join(move.value for move in moves[-4:]) if moves else "No previous moves yet."


@dataclass
class DuelPlayer:
    user_id: int
    name: str
    wins: int = 0
    history: list[Move] = field(default_factory=list)
    ripple_used: bool = False


@dataclass(frozen=True)
class DuelUpdate:
    text: str
    round_resolved: bool
    finished: bool
    winner_id: int | None = None
    tied: bool = False
    moves: tuple[Move, Move] | None = None


@dataclass
class DuelState:
    challenger: DuelPlayer
    opponent: DuelPlayer
    round_number: int = 1
    selections: dict[int, Move] = field(default_factory=dict)
    finished: bool = False
    _rng: random.Random = field(default_factory=random.Random, repr=False)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)

    def player(self, user_id: int) -> DuelPlayer:
        if user_id == self.challenger.user_id:
            return self.challenger
        if user_id == self.opponent.user_id:
            return self.opponent
        raise ValueError("User is not in this Ripple Duel.")

    def other(self, user_id: int) -> DuelPlayer:
        if user_id == self.challenger.user_id:
            return self.opponent
        if user_id == self.opponent.user_id:
            return self.challenger
        raise ValueError("User is not in this Ripple Duel.")

    def has_locked(self, user_id: int) -> bool:
        return user_id in self.selections

    def can_ripple_read(self, user_id: int) -> tuple[bool, str]:
        player, opponent = self.player(user_id), self.other(user_id)
        if self.finished:
            return False, "This Ripple Duel is already over."
        if player.ripple_used:
            return False, "Your Ripple Read has already been used in this duel."
        if self.has_locked(user_id):
            return False, "Your move is already locked for this round, so the ripples cannot change your choice."
        if not self.has_locked(opponent.user_id):
            return False, "The ripples are still too unclear. Your opponent has not locked in yet."
        return True, ""

    def use_ripple_read(self, user_id: int) -> RippleReadResult:
        allowed, reason = self.can_ripple_read(user_id)
        if not allowed:
            raise ValueError(reason)
        self.player(user_id).ripple_used = True
        return generate_ripple_read(self.selections[self.other(user_id).user_id], self._rng)

    def lock_move(self, user_id: int, move: Move) -> DuelUpdate:
        if self.finished:
            raise ValueError("This Ripple Duel is already over.")
        self.player(user_id)
        if self.has_locked(user_id):
            raise ValueError("Your move is already locked for this round.")
        self.selections[user_id] = move
        if len(self.selections) < 2:
            return DuelUpdate(f"🔒 **{self.player(user_id).name}** locked in a choice. Waiting for the other duelist…", False, False)
        return self._resolve_locked_round()

    def _resolve_locked_round(self) -> DuelUpdate:
        first, second = self.challenger, self.opponent
        move_a, move_b = self.selections[first.user_id], self.selections[second.user_id]
        result = resolve_round(move_a, move_b)
        first.history.append(move_a)
        second.history.append(move_b)
        if result.tied:
            text = (f"{TIE_FLAVOR[move_a]}\n\n**{first.name}** chose **{move_a.value}**.\n**{second.name}** chose **{move_b.value}**.\n\nSame move: **tie round**. No point is awarded.\n**Score:**\n{first.name} {first.wins} — {second.wins} {second.name}")
            self.selections.clear()
            self.round_number += 1
            return DuelUpdate(text, True, False, tied=True, moves=(move_a, move_b))
        winner = first if result.winner == move_a else second
        winner.wins += 1
        flavor = self._rng.choice(WIN_FLAVOR[(result.winner, result.loser)])
        text = (f"{flavor}\n\n**{first.name}** chose **{move_a.value}**.\n**{second.name}** chose **{move_b.value}**.\n\n**{result.winner.value}** beats **{result.loser.value}**.\n**{winner.name} wins the round.**\n**Score:**\n{first.name} {first.wins} — {second.wins} {second.name}")
        self.selections.clear()
        if winner.wins == 3:
            self.finished = True
            return DuelUpdate(text, True, True, winner.user_id, moves=(move_a, move_b))
        self.round_number += 1
        return DuelUpdate(text, True, False, moves=(move_a, move_b))

    def card_text(self) -> str:
        def status(player: DuelPlayer) -> str:
            return "Locked in ✅" if self.has_locked(player.user_id) else "Choosing… ⏳"
        return (f"**{self.challenger.name}**                      **{self.opponent.name}**\n**{self.challenger.wins} wins**                      **{self.opponent.wins} wins**\n\n**Round {self.round_number}** · First to **3** wins\n\n**Status**\n{self.challenger.name}: {status(self.challenger)}\n{self.opponent.name}: {status(self.opponent)}\n\n**Recent moves** *(revealed rounds only; last four)*\n**{self.challenger.name}:** {recent_history(self.challenger.history)}\n**{self.opponent.name}:** {recent_history(self.opponent.history)}\n\n**Aqua Jet** > **Hydro Charge**\n**Hydro Charge** > **Water Veil**\n**Water Veil** > **Aqua Jet**\n\nChoose privately. Your choice is revealed only after both players lock in.")


class DuelManager:
    """Small in-memory lifecycle registry; a user may be in one invite/match."""
    def __init__(self) -> None:
        self._by_user: dict[int, DuelState | None] = {}

    def create_invitation(self, challenger_id: int, opponent_id: int) -> bool:
        if challenger_id == opponent_id or challenger_id in self._by_user or opponent_id in self._by_user:
            return False
        self._by_user[challenger_id] = self._by_user[opponent_id] = None
        return True

    def accept_invitation(self, challenger_id: int, challenger_name: str, opponent_id: int, opponent_name: str) -> DuelState:
        if challenger_id not in self._by_user or opponent_id not in self._by_user:
            raise ValueError("That duel invitation is no longer active.")
        state = new_duel(challenger_id, challenger_name, opponent_id, opponent_name)
        self._by_user[challenger_id] = self._by_user[opponent_id] = state
        return state

    def find_duel(self, user_id: int) -> DuelState | None:
        return self._by_user.get(user_id)

    def is_active(self, user_id: int) -> bool:
        return user_id in self._by_user

    def remove_duel(self, *user_ids: int) -> None:
        for user_id in user_ids:
            self._by_user.pop(user_id, None)


def new_duel(challenger_id: int, challenger_name: str, opponent_id: int, opponent_name: str, *, rng: random.Random | None = None) -> DuelState:
    return DuelState(DuelPlayer(challenger_id, challenger_name), DuelPlayer(opponent_id, opponent_name), _rng=rng or random.Random())
