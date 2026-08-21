"""Playful, fictional water-move progression for Vaporeon splashes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SplashMove:
    affection_required: int
    name: str
    fictional_damage: int
    accuracy: float
    special: str
    status: str | None = None
    status_chance: float = 0.0
    ignores_slippery: bool = False
    critical_chance: float = 0.10
    rain_multiplier: float = 1.15
    low_hp_multiplier: float = 1.0


SPLASH_MOVES = (
    SplashMove(0, "Gentle Splash", 1, 1.00, "Always lands; may leave the target Waterlogged.", "waterlogged", 0.35),
    SplashMove(10, "Water Gun", 12, 0.95, "Reliable, straightforward water pressure."),
    SplashMove(25, "Bubble Beam", 20, 0.92, "May leave the target Soaked.", "soaked", 0.35),
    SplashMove(50, "Aqua Jet", 30, 0.99, "Ignores Slippery and has an elevated critical chance.", ignores_slippery=True, critical_chance=0.15),
    SplashMove(100, "Water Pulse", 40, 0.88, "May leave the target Slippery.", "slippery", 0.25),
    SplashMove(200, "Brine", 50, 0.90, "Deals 25% more damage to targets at half HP or lower.", low_hp_multiplier=1.25),
    SplashMove(300, "Aqua Tail", 60, 0.85, "A high-impact tail sweep with a 15% critical chance.", critical_chance=0.15),
    SplashMove(500, "Surf", 75, 0.90, "Gets a larger boost during Rainy weather.", rain_multiplier=1.30),
    SplashMove(750, "Hydro Pump", 100, 0.70, "Huge hit, but its accuracy is risky."),
    SplashMove(1000, "Tidal Wave", 125, 0.65, "The biggest wave, with the biggest chance to miss."),
)

FAINT_MESSAGES = (
    "was washed away by the wave!",
    "returned to the cozy shore to recover.",
    "was defeated by dampness.",
    "was carried away by a suspiciously determined current.",
    "has been declared extremely soggy by Vaporeon.",
    "needs a towel, a snack, and several business minutes.",
    "was outplayed by hydration itself.",
    "has entered the official Vaporeon recovery puddle.",
)

MOVE_FLAVOR = {
    "Gentle Splash": (
        "One single droplet arrives with the confidence of a tidal wave.",
        "Vaporeon flicks a fin. The water is almost apologetic.",
        "A tiny ripple travels with enormous ceremonial importance.",
    ),
    "Water Gun": (
        "Vaporeon takes aim with the seriousness of a garden hose technician.",
        "A crisp stream of water launches with excellent posture.",
        "The nearest puddle provides tactical encouragement.",
    ),
    "Bubble Beam": (
        "A bright chain of bubbles floats forward, each one extremely committed.",
        "Vaporeon releases bubbles with suspiciously precise spacing.",
        "The air briefly becomes a highly organized bubble situation.",
    ),
    "Aqua Jet": (
        "Vaporeon vanishes into a blur of blue and reappears somewhere dramatic.",
        "A tiny wake streaks across the floor at unreasonable speed.",
        "The splash arrives before anyone has time to object.",
    ),
    "Water Pulse": (
        "Concentric rings of water hum with mysterious aquatic energy.",
        "The wave pulses outward with an almost musical little thrum.",
        "Vaporeon gives the water a thoughtful, psychic-looking nudge.",
    ),
    "Brine": (
        "The water has acquired an alarming amount of sea attitude.",
        "Vaporeon summons a briny wave with professional beach energy.",
        "Somewhere, a seagull would approve of this technique.",
    ),
    "Aqua Tail": (
        "Vaporeon's tail arcs through the water with impeccable form.",
        "A glittering tail-sweep sends a wave curving through the air.",
        "The tail has entered its competitive splash era.",
    ),
    "Surf": (
        "A whole friendly wave rises up as if it has somewhere important to be.",
        "Vaporeon rides a compact surf break with unnecessary elegance.",
        "The room briefly has beach episode energy.",
    ),
    "Hydro Pump": (
        "Vaporeon inhales. The nearby water becomes nervous.",
        "A high-pressure roar announces that subtlety has left the building.",
        "The puddle has been promoted to industrial equipment.",
    ),
    "Tidal Wave": (
        "The water rises with the theatrical timing of a season finale.",
        "Every tiny puddle nearby has joined a very large union.",
        "Vaporeon looks serene. The wave does not.",
    ),
}

MISS_MESSAGES = (
    "The water lands in a dramatically empty spot.",
    "A nearby plant receives an unexpected spa treatment.",
    "The wave misses, but its form was still beautiful.",
    "Vaporeon checks the trajectory, then pretends that was intentional.",
    "One heroic droplet arrives late and has no idea what happened.",
    "The splash sails past with a small, embarrassed ripple.",
)

HUGE_MISS_MESSAGES = {
    "Hydro Pump": (
        "Hydro Pump has successfully attacked the concept of distance.",
        "The pressure was incredible. The aim has gone on a short vacation.",
        "Somewhere far away, a wall has become unexpectedly hydrated.",
    ),
    "Tidal Wave": (
        "The tidal wave has arrived magnificently at a location nobody requested.",
        "The ocean made an entrance. The target was not invited to it.",
        "A distant puddle is now having the most dramatic day of its life.",
    ),
}

NEAR_FAINT_MESSAGES = (
    "Vaporeon stares at the remaining {hp} HP with professional concern.",
    "{hp} HP remains. Vaporeon quietly offers a towel and a moment to reflect.",
    "Vaporeon notices the last {hp} HP and becomes extremely polite about it.",
    "Only {hp} HP is left. The recovery puddle is being prepared just in case.",
)

CRITICAL_MESSAGES = (
    "The splash achieves a level of drama usually reserved for waterfalls.",
    "For one perfect second, Vaporeon becomes the entire ocean.",
    "The water hits with startling cinematic timing.",
    "Even the puddle seems impressed by that one.",
    "A tiny aquatic choir sings a single triumphant note.",
)


def unlocked_splash(affection: int) -> SplashMove:
    """Return the strongest water move unlocked by the current affection tier."""
    if affection < 0:
        raise ValueError("Affection cannot be negative.")
    return max((move for move in SPLASH_MOVES if move.affection_required <= affection), key=lambda move: move.affection_required)


def next_splash(affection: int) -> SplashMove | None:
    """Return the next move to unlock, if any."""
    return next((move for move in SPLASH_MOVES if move.affection_required > affection), None)


def splash_by_name(name: str) -> SplashMove | None:
    """Find a move by its user-facing name, ignoring capitalization."""
    normalized = name.strip().casefold()
    return next((move for move in SPLASH_MOVES if move.name.casefold() == normalized), None)
