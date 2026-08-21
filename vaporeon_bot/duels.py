"""Canonical, self-contained Tide Duel rules. Discord UI only calls this module."""
from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass, field
from enum import Enum


MAX_HP = MAX_TIDE = 100


class Move(str, Enum):
    GENTLE_SPLASH = "Gentle Splash"
    WATER_GUN = "Water Gun"
    BUBBLE_BEAM = "Bubble Beam"
    AQUA_JET = "Aqua Jet"
    WATER_VEIL = "Water Veil"
    MUDDY_WATER = "Muddy Water"
    SURF = "Surf"
    RAIN_DANCE = "Rain Dance"
    HYDRO_PUMP = "Hydro Pump"
    HYDRO_CANNON = "Hydro Cannon"


class Status(str, Enum):
    SOAKED = "Soaked"
    SLIPPERY = "Slippery"


@dataclass(frozen=True)
class MoveDefinition:
    move: Move
    damage: int
    accuracy: float | None
    tide_change: int
    cooldown_rounds: int
    affection_unlock: int
    status: Status | None = None
    status_chance: float = 0.0
    defensive_multiplier: float | None = None
    rain_damage_bonus: float = 0.0
    once_per_duel: bool = False
    description: str = ""


# The one runtime source of truth for engine, rules, private cards, and /moves.
MOVE_DEFINITIONS: dict[Move, MoveDefinition] = {
    Move.GENTLE_SPLASH: MoveDefinition(Move.GENTLE_SPLASH, 6, 1.0, 25, 0, 0, description="Primary Tide builder."),
    Move.WATER_GUN: MoveDefinition(Move.WATER_GUN, 12, .95, 15, 0, 10, description="Safe Tide builder."),
    Move.BUBBLE_BEAM: MoveDefinition(Move.BUBBLE_BEAM, 16, .90, 10, 1, 25, Status.SOAKED, .25, description="May apply Soaked."),
    Move.AQUA_JET: MoveDefinition(Move.AQUA_JET, 20, 1.0, -10, 1, 50, description="Very reliable pressure; it has no priority in simultaneous rounds."),
    Move.WATER_VEIL: MoveDefinition(Move.WATER_VEIL, 0, None, -15, 2, 100, defensive_multiplier=.5, description="Reduces all incoming damage this round by 50%, rounded down."),
    Move.MUDDY_WATER: MoveDefinition(Move.MUDDY_WATER, 25, .85, -25, 2, 200, Status.SLIPPERY, .30, description="May apply Slippery."),
    Move.SURF: MoveDefinition(Move.SURF, 32, .90, -40, 2, 300, rain_damage_bonus=.15, description="Deals +15% damage while Rain is active."),
    Move.RAIN_DANCE: MoveDefinition(Move.RAIN_DANCE, 0, None, -40, 0, 500, once_per_duel=True, description="Starts symmetrical Rain for the next 3 rounds; both players' damaging Water moves deal +15% damage."),
    Move.HYDRO_PUMP: MoveDefinition(Move.HYDRO_PUMP, 45, .70, -65, 3, 750, description="High-risk burst damage."),
    Move.HYDRO_CANNON: MoveDefinition(Move.HYDRO_CANNON, 60, .60, -100, 0, 1000, once_per_duel=True, description="Ultimate burst; usable once per duel."),
}


@dataclass(frozen=True)
class RippleReadResult:
    flavor: str
    properties: tuple[str, ...]
    possible_moves: tuple[Move, ...]


@dataclass
class DuelPlayer:
    user_id: int
    name: str
    affection: int = 0
    is_cpu: bool = False
    hp: int = MAX_HP
    tide: int = 0
    statuses: set[Status] = field(default_factory=set)
    cooldowns: dict[Move, int] = field(default_factory=dict)  # last used round
    history: list[Move] = field(default_factory=list)
    ripple_used: bool = False
    once_used: set[Move] = field(default_factory=set)


@dataclass(frozen=True)
class AttackReport:
    move: Move
    base_accuracy: float | None
    effective_accuracy: float | None
    hit: bool
    base_damage: int
    soaked_bonus: bool
    rain_bonus: bool
    veil_reduction: bool
    final_damage: int
    status_applied: Status | None
    slippery_consumed: bool


@dataclass(frozen=True)
class DuelUpdate:
    text: str
    round_resolved: bool
    finished: bool
    winner_id: int | None = None
    draw: bool = False


def _accuracy_text(value: float | None) -> str:
    return "always succeeds" if value is None else f"{value:.0%}"


def move_detail(definition: MoveDefinition, *, available: bool, reason: str = "") -> str:
    tide = f"+{definition.tide_change}" if definition.tide_change >= 0 else str(definition.tide_change)
    cd = "none" if not definition.cooldown_rounds else f"{definition.cooldown_rounds} round{'s' if definition.cooldown_rounds != 1 else ''}"
    lines = [f"**{definition.move.value}**", f"{definition.damage} dmg | {_accuracy_text(definition.accuracy)} accuracy | Tide: {tide} | Cooldown: {cd}"]
    if definition.status:
        effect = "Next successful outgoing damaging move deals +10% damage; misses do not consume it." if definition.status is Status.SOAKED else "Next incoming damaging attack loses 35 percentage points of accuracy; consumed after that attempt."
        lines.append(f"{definition.status_chance:.0%} chance to apply **{definition.status.value}** — {effect}")
    if definition.once_per_duel:
        lines.append("Once per duel.")
    lines.append(f"Effect: {definition.description}")
    if not available:
        lines.append(f"Unavailable: {reason}")
    return "\n".join(lines)


def recent_history(moves: list[Move]) -> str:
    return " → ".join(move.value for move in moves[-4:]) if moves else "No previous moves yet."


def _ripple_candidates(actual: Move) -> list[tuple[tuple[str, ...], tuple[Move, ...]]]:
    groups = []
    predicates = (
        (("Costs Tide",), lambda d: d.tide_change < 0),
        (("Generates Tide",), lambda d: d.tide_change > 0),
        (("Deals at least 20 base damage",), lambda d: d.damage >= 20),
        (("Deals at least 30 base damage",), lambda d: d.damage >= 30),
        (("Accuracy is at least 90%",), lambda d: d.accuracy is None or d.accuracy >= .90),
        (("Accuracy is below 90%",), lambda d: d.accuracy is not None and d.accuracy < .90),
        (("Can apply a status",), lambda d: d.status is not None),
        (("Cannot apply a status",), lambda d: d.status is None),
        (("Has a cooldown of 2+ rounds",), lambda d: d.cooldown_rounds >= 2),
        (("Does no damage",), lambda d: d.damage == 0),
    )
    for properties, predicate in predicates:
        possible = tuple(move for move, item in MOVE_DEFINITIONS.items() if predicate(item))
        if actual in possible and 2 <= len(possible) <= 4:
            groups.append((properties, possible))
    for index, (first_text, first) in enumerate(predicates):
        for second_text, second in predicates[index + 1:]:
            possible = tuple(move for move, item in MOVE_DEFINITIONS.items() if first(item) and second(item))
            if actual in possible and 2 <= len(possible) <= 4:
                groups.append((first_text + second_text, possible))
    return groups


def generate_ripple_read(actual_move: Move, rng: random.Random | None = None) -> RippleReadResult:
    source = rng or random.Random()
    properties, possible = source.choice(_ripple_candidates(actual_move))
    flavor = source.choice(("The current feels unusually revealing.", "Vaporeon watches the water carefully.", "The ripples settle into a readable pattern."))
    return RippleReadResult(flavor, properties, possible)


@dataclass
class DuelState:
    challenger: DuelPlayer
    opponent: DuelPlayer
    round_number: int = 1
    first_picker_id: int = 0
    rain_rounds_remaining: int = 0
    selections: dict[int, Move] = field(default_factory=dict)
    finished: bool = False
    _rng: random.Random = field(default_factory=random.Random, repr=False)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)

    def player(self, user_id: int) -> DuelPlayer:
        if user_id == self.challenger.user_id: return self.challenger
        if user_id == self.opponent.user_id: return self.opponent
        raise ValueError("User is not in this Ripple Duel.")

    def other(self, user_id: int) -> DuelPlayer:
        return self.opponent if user_id == self.challenger.user_id else self.challenger if user_id == self.opponent.user_id else (_ for _ in ()).throw(ValueError("User is not in this Ripple Duel."))

    def has_locked(self, user_id: int) -> bool: return user_id in self.selections

    def cpu_player(self) -> DuelPlayer | None:
        return self.challenger if self.challenger.is_cpu else self.opponent if self.opponent.is_cpu else None

    def lock_cpu_move(self) -> DuelUpdate | None:
        """Lock Vaporeon's legal practice move before the human chooses."""
        cpu = self.cpu_player()
        if cpu is None or self.finished or self.has_locked(cpu.user_id) or (not self.selections and self.first_picker_id != cpu.user_id):
            return None
        legal = [move for move in Move if self.availability(cpu, move)[0]]
        # Prefer the strongest currently affordable option; this is deliberately visible through history/read.
        move = max(legal, key=lambda item: (MOVE_DEFINITIONS[item].damage, MOVE_DEFINITIONS[item].tide_change))
        return self.lock_move(cpu.user_id, move)

    def cooldown_remaining(self, player: DuelPlayer, move: Move) -> int:
        definition = MOVE_DEFINITIONS[move]
        if move not in player.cooldowns: return 0
        return max(0, player.cooldowns[move] + definition.cooldown_rounds - self.round_number)

    def availability(self, player: DuelPlayer, move: Move) -> tuple[bool, str]:
        definition = MOVE_DEFINITIONS[move]
        if definition.tide_change < 0 and player.tide < -definition.tide_change:
            return False, f"Requires {-definition.tide_change} Tide; you have {player.tide}."
        remaining = self.cooldown_remaining(player, move)
        if remaining:
            return False, f"Cooldown: {remaining} round{'s' if remaining != 1 else ''} remaining."
        if definition.once_per_duel and move in player.once_used:
            return False, "USED — once per duel."
        return True, ""

    def can_ripple_read(self, user_id: int) -> tuple[bool, str]:
        player, opponent = self.player(user_id), self.other(user_id)
        if self.finished: return False, "This Ripple Duel is already over."
        if player.ripple_used: return False, "Your Ripple Read has already been used in this duel."
        if self.first_picker_id == user_id:
            return False, "You choose first this round. Ripple Read is available only to the responding player after the first move is locked."
        if self.has_locked(user_id): return False, "Your move is already locked for this round."
        if not self.has_locked(opponent.user_id): return False, "The ripples are still too unclear. Your opponent has not locked in yet."
        return True, ""

    def use_ripple_read(self, user_id: int) -> RippleReadResult:
        allowed, reason = self.can_ripple_read(user_id)
        if not allowed: raise ValueError(reason)
        self.player(user_id).ripple_used = True
        return generate_ripple_read(self.selections[self.other(user_id).user_id], self._rng)

    def lock_move(self, user_id: int, move: Move) -> DuelUpdate:
        player = self.player(user_id)
        if self.finished: raise ValueError("This Ripple Duel is already over.")
        if self.has_locked(user_id): raise ValueError("Your move is already locked for this round.")
        if not self.selections and user_id != self.first_picker_id:
            raise ValueError(f"Wait for **{self.player(self.first_picker_id).name}** to choose first this round.")
        if self.selections and user_id == self.first_picker_id:
            raise ValueError("You chose first this round. Wait for the responding player.")
        legal, reason = self.availability(player, move)
        if not legal: raise ValueError(f"**{move.value}** is unavailable. {reason}")
        self.selections[user_id] = move
        if len(self.selections) < 2:
            return DuelUpdate(f"🔒 **{player.name}** locked in a move. Waiting for the other duelist…", False, False)
        return self._resolve_round()

    def _attack(self, attacker: DuelPlayer, defender: DuelPlayer, move: Move, rain_active: bool) -> AttackReport:
        definition = MOVE_DEFINITIONS[move]
        if definition.damage == 0:
            return AttackReport(move, definition.accuracy, definition.accuracy, True, 0, False, False, False, 0, None, False)
        slippery = Status.SLIPPERY in defender.statuses
        effective = max(0.0, (definition.accuracy or 1.0) - (.35 if slippery else 0))
        hit = self._rng.random() < effective
        soaked = hit and Status.SOAKED in attacker.statuses
        damage = definition.damage
        if soaked: damage = math.floor(damage * 1.10)
        rain_bonus = hit and rain_active
        if rain_bonus: damage = math.floor(damage * 1.15)
        veil = hit and self.selections.get(defender.user_id) is Move.WATER_VEIL
        if veil: damage = math.floor(damage * .5)
        applied = definition.status if hit and definition.status and self._rng.random() < definition.status_chance else None
        return AttackReport(move, definition.accuracy, effective, hit, definition.damage, soaked, rain_bonus, veil, damage if hit else 0, applied, slippery)

    def _resolve_round(self) -> DuelUpdate:
        first, second = self.challenger, self.opponent
        first_move, second_move = self.selections[first.user_id], self.selections[second.user_id]
        rain_active = self.rain_rounds_remaining > 0
        first_report, second_report = self._attack(first, second, first_move, rain_active), self._attack(second, first, second_move, rain_active)
        # Apply all results only after both reports exist: damage is truly simultaneous.
        hp_before = {first.user_id: first.hp, second.user_id: second.hp}
        first.hp = max(0, first.hp - second_report.final_damage)
        second.hp = max(0, second.hp - first_report.final_damage)
        lines = [f"💦 **Round {self.round_number}**"]
        for attacker, defender, report in ((first, second, first_report), (second, first, second_report)):
            definition = MOVE_DEFINITIONS[report.move]
            lines.append(f"\n**{attacker.name} used {report.move.value}.**")
            if definition.damage == 0:
                lines.append("Result: always succeeds · Damage: 0")
            else:
                lines.append(f"Base accuracy: {_accuracy_text(report.base_accuracy)} · Effective accuracy: {_accuracy_text(report.effective_accuracy)} · Result: {'HIT' if report.hit else 'MISS'}")
                if report.slippery_consumed: lines.append("Slippery penalty: −35 percentage points; Slippery was consumed.")
                if report.hit:
                    modifiers = (["Soaked +10%"] if report.soaked_bonus else []) + (["Rain +15%"] if report.rain_bonus else []) + (["Water Veil ×0.50"] if report.veil_reduction else [])
                    lines.append(f"Base damage: {report.base_damage}" + (f" · {' · '.join(modifiers)}" if modifiers else "") + f" · Final damage: **{report.final_damage}**")
                else: lines.append("Damage: 0. Tide cost and cooldown still apply on a miss.")
                if definition.status:
                    status_result = f"**{report.status_applied.value} applied**" if report.status_applied else "did not apply"
                    lines.append(f"{definition.status.value} chance: {definition.status_chance:.0%}; result: {status_result}.")
            if definition.tide_change < 0: lines.append(f"Tide cost: {-definition.tide_change} (paid this round).")
            elif definition.tide_change: lines.append(f"Tide gained: +{definition.tide_change} (applied after resolution).")
        for player, move, report in ((first, first_move, first_report), (second, second_move, second_report)):
            definition = MOVE_DEFINITIONS[move]
            player.tide = min(MAX_TIDE, max(0, player.tide + definition.tide_change))
            if definition.cooldown_rounds: player.cooldowns[move] = self.round_number
            if definition.once_per_duel: player.once_used.add(move)
            if report.slippery_consumed: self.other(player.user_id).statuses.discard(Status.SLIPPERY)
            if report.hit and report.soaked_bonus: player.statuses.discard(Status.SOAKED)
            if report.status_applied: self.other(player.user_id).statuses.add(report.status_applied)
            player.history.append(move)
        if first_move is Move.RAIN_DANCE or second_move is Move.RAIN_DANCE:
            self.rain_rounds_remaining = 3
            lines.append("🌧️ Rain Dance started **Rain** for the next 3 rounds. Both players' damaging Water moves gain +15% damage.")
        elif rain_active:
            self.rain_rounds_remaining -= 1
        lines.append(f"\n**HP:** {first.name} {hp_before[first.user_id]} → {first.hp} · {second.name} {hp_before[second.user_id]} → {second.hp}")
        lines.append(f"**Tide:** {first.name} {first.tide}/100 · {second.name} {second.tide}/100")
        self.selections.clear()
        if first.hp == 0 and second.hp == 0:
            self.finished = True
            return DuelUpdate("\n".join(lines) + "\n\n💧 Both Vaporeon were washed into a perfectly even draw.", True, True, draw=True)
        if first.hp == 0 or second.hp == 0:
            self.finished = True
            winner = second if first.hp == 0 else first
            return DuelUpdate("\n".join(lines) + f"\n\n🏆 **{winner.name} wins the Tide Duel!**", True, True, winner.user_id)
        self.round_number += 1
        self.first_picker_id = self.opponent.user_id if self.first_picker_id == self.challenger.user_id else self.challenger.user_id
        return DuelUpdate("\n".join(lines), True, False)

    def card_text(self) -> str:
        def line(player: DuelPlayer) -> str:
            statuses = ", ".join(status.value for status in sorted(player.statuses, key=str)) or "None"
            phase = "Locked in ✅" if self.has_locked(player.user_id) else "Chooses first ▶" if player.user_id == self.first_picker_id and not self.selections else "Responds second ⏳"
            return f"**{player.name}**\nHP: **{player.hp}/100** · Tide: **{player.tide}/100**\nStatus: **{statuses}** · Ripple Read: **{'Used' if player.ripple_used else 'Available'}**\n{phase}"
        rain = f"**Rain:** {self.rain_rounds_remaining} round{'s' if self.rain_rounds_remaining != 1 else ''} remaining" if self.rain_rounds_remaining else "**Rain:** inactive"
        return f"**Round {self.round_number}**\n\n{line(self.challenger)}\n\n{line(self.opponent)}\n\n{rain}\n\n**Recent revealed moves** *(last four)*\n**{self.challenger.name}:** {recent_history(self.challenger.history)}\n**{self.opponent.name}:** {recent_history(self.opponent.history)}\n\nCurrent moves are hidden until both players lock in."


class DuelManager:
    def __init__(self) -> None: self._by_user: dict[int, DuelState | None] = {}
    def create_invitation(self, challenger_id: int, opponent_id: int) -> bool:
        if challenger_id == opponent_id or challenger_id in self._by_user or opponent_id in self._by_user: return False
        self._by_user[challenger_id] = self._by_user[opponent_id] = None; return True
    def accept_invitation(self, challenger_id: int, challenger_name: str, challenger_affection: int, opponent_id: int, opponent_name: str, opponent_affection: int, *, opponent_cpu: bool = False) -> DuelState:
        if challenger_id not in self._by_user or opponent_id not in self._by_user: raise ValueError("That duel invitation is no longer active.")
        state = new_duel(challenger_id, challenger_name, challenger_affection, opponent_id, opponent_name, opponent_affection, opponent_cpu=opponent_cpu)
        self._by_user[challenger_id] = self._by_user[opponent_id] = state; return state
    def is_active(self, user_id: int) -> bool: return user_id in self._by_user
    def remove_duel(self, *user_ids: int) -> None:
        for user_id in user_ids: self._by_user.pop(user_id, None)


def new_duel(challenger_id: int, challenger_name: str, challenger_affection: int, opponent_id: int, opponent_name: str, opponent_affection: int, *, opponent_cpu: bool = False, rng: random.Random | None = None) -> DuelState:
    return DuelState(DuelPlayer(challenger_id, challenger_name, challenger_affection), DuelPlayer(opponent_id, opponent_name, opponent_affection, is_cpu=opponent_cpu), first_picker_id=challenger_id, _rng=rng or random.Random())
