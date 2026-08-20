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
    SplashMove(0, "Gentle Splash", 5, 1.00, "Always lands; may leave the target Waterlogged.", "waterlogged", 0.35),
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
