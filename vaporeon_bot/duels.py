"""Small turn-based Vaporeon duels, deliberately separate from casual splashes."""

from __future__ import annotations

import random
from dataclasses import dataclass, field


DUEL_MAX_HP = 100
TIDE_BURST_COST = 75


@dataclass
class DuelPlayer:
    user_id: int
    name: str
    hp: int = DUEL_MAX_HP
    tide: int = 0
    brace: bool = False
    drenched: bool = False
    item_used: bool = False


@dataclass(frozen=True)
class DuelTurn:
    text: str
    winner_id: int | None
    next_player_id: int | None


@dataclass
class DuelState:
    challenger: DuelPlayer
    opponent: DuelPlayer
    current_player_id: int
    rain_turns: int = 0
    turn_number: int = 1
    finished: bool = False
    _rng: random.Random = field(default_factory=random.Random, repr=False)

    def player(self, user_id: int) -> DuelPlayer:
        if self.challenger.user_id == user_id:
            return self.challenger
        if self.opponent.user_id == user_id:
            return self.opponent
        raise ValueError("User is not in this duel.")

    def other(self, user_id: int) -> DuelPlayer:
        if self.challenger.user_id == user_id:
            return self.opponent
        if self.opponent.user_id == user_id:
            return self.challenger
        raise ValueError("User is not in this duel.")

    def current_player(self) -> DuelPlayer:
        return self.player(self.current_player_id)

    def available_actions(self, user_id: int, *, potion_available: bool) -> tuple[str, ...]:
        if self.finished or user_id != self.current_player_id:
            return ()
        actions = ["bubble_beam", "aqua_jet", "surf", "hydro_pump", "brace", "rain_dance"]
        if self.player(user_id).tide >= TIDE_BURST_COST:
            actions.append("tide_burst")
        if potion_available and not self.player(user_id).item_used:
            actions.append("potion")
        return tuple(actions)

    def resolve(self, user_id: int, action: str, *, potion_available: bool = False) -> DuelTurn:
        if self.finished:
            raise ValueError("This duel is already over.")
        if user_id != self.current_player_id:
            raise ValueError("It is not your turn.")
        if action not in self.available_actions(user_id, potion_available=potion_available):
            raise ValueError("That action is unavailable.")

        attacker, target = self.player(user_id), self.other(user_id)
        rain_before = self.rain_turns
        lines: list[str] = []
        if action == "brace":
            attacker.brace = True
            attacker.tide = min(100, attacker.tide + 10)
            lines.append(f"🛡️ **{attacker.name}** braces for the next hit and gains 10 Tide.")
        elif action == "rain_dance":
            self.rain_turns = 4
            attacker.tide = min(100, attacker.tide + 10)
            lines.append(f"🌧️ **{attacker.name}** used **Rain Dance**! Rain will last for the next 4 turns.")
        elif action == "potion":
            before = attacker.hp
            attacker.hp = min(DUEL_MAX_HP, attacker.hp + 20)
            attacker.item_used = True
            lines.append(f"💊 **{attacker.name}** used a **Potion**: {before} → {attacker.hp} HP. Their one duel item is spent.")
        else:
            lines.extend(self._attack(attacker, target, action, rain_before))

        if self.finished:
            return DuelTurn("\n".join(lines), attacker.user_id, None)
        if action != "rain_dance" and rain_before > 0:
            self.rain_turns -= 1
        self.current_player_id = target.user_id
        self.turn_number += 1
        return DuelTurn("\n".join(lines), None, target.user_id)

    def _attack(self, attacker: DuelPlayer, target: DuelPlayer, action: str, rain_before: int) -> list[str]:
        moves = {
            "bubble_beam": ("Bubble Beam", 14, 0.96),
            "aqua_jet": ("Aqua Jet", 18, 0.99),
            "surf": ("Surf", 26, 0.90),
            "hydro_pump": ("Hydro Pump", 40, 0.70),
            "tide_burst": ("Tide Burst", 34, 1.00),
        }
        name, base_damage, accuracy = moves[action]
        if action == "tide_burst":
            attacker.tide -= TIDE_BURST_COST
        if self._rng.random() > accuracy:
            miss = "Hydro Pump has successfully attacked the concept of distance." if action == "hydro_pump" else "The water attack missed with surprisingly elegant form."
            return [f"💨 **{attacker.name}** used **{name}**, but it missed! {miss}"]

        critical_chance = 0.20 if action == "aqua_jet" and target.drenched else 0.10
        critical = self._rng.random() < critical_chance
        multiplier = 1.5 if critical else 1.0
        modifiers: list[str] = []
        if critical:
            modifiers.append("critical hit ×1.5")
        if target.drenched:
            multiplier *= 1.10
            target.drenched = False
            modifiers.append("Drenched +10%")
        if action == "surf" and rain_before > 0:
            multiplier *= 1.30
            modifiers.append("Rainy Surf +30%")
        if target.brace:
            multiplier *= 0.50
            target.brace = False
            modifiers.append("Brace −50%")
        damage = max(1, round(base_damage * multiplier))
        before = target.hp
        target.hp = max(0, target.hp - damage)
        attacker.tide = min(100, attacker.tide + (20 if action == "bubble_beam" else 15))
        target.tide = min(100, target.tide + 10)
        if action == "bubble_beam":
            target.drenched = True
            modifiers.append("target is Drenched")
        modifier_text = f" ({' · '.join(modifiers)})" if modifiers else ""
        lines = [f"💦 **{attacker.name}** used **{name}** on **{target.name}** for **{damage} damage**! {target.name}: **{before} → {target.hp} HP**{modifier_text}."]
        if target.hp == 0:
            self.finished = True
            lines.append(f"🏆 **{attacker.name} wins the duel!** {target.name} returns to the cozy shore.")
        return lines

    def card_text(self) -> str:
        weather = f"🌧️ Rain: {self.rain_turns} turns" if self.rain_turns else "☀️ Clear"
        current = self.current_player().name if not self.finished else "Complete"
        return (
            f"**{self.challenger.name}** — HP **{self.challenger.hp}/100** · Tide **{self.challenger.tide}/100**\n"
            f"**{self.opponent.name}** — HP **{self.opponent.hp}/100** · Tide **{self.opponent.tide}/100**\n\n"
            f"{weather}\n**Turn {self.turn_number}:** {current}"
        )


def new_duel(challenger_id: int, challenger_name: str, opponent_id: int, opponent_name: str, *, rng: random.Random | None = None) -> DuelState:
    """Create a 100-HP duel with the challenger taking the first turn."""
    return DuelState(DuelPlayer(challenger_id, challenger_name), DuelPlayer(opponent_id, opponent_name), challenger_id, _rng=rng or random.Random())
