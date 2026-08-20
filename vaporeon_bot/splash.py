"""Playful, fictional water-move progression for Vaporeon splashes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SplashMove:
    affection_required: int
    name: str
    fictional_damage: int
    accuracy: float


SPLASH_MOVES = (
    SplashMove(0, "Gentle Splash", 5, 1.00),
    SplashMove(10, "Water Gun", 12, 0.95),
    SplashMove(20, "Bubble Beam", 20, 0.92),
    SplashMove(30, "Aqua Jet", 30, 0.99),
    SplashMove(40, "Water Pulse", 40, 0.88),
    SplashMove(50, "Brine", 50, 0.90),
    SplashMove(60, "Aqua Tail", 60, 0.85),
    SplashMove(70, "Surf", 75, 0.90),
    SplashMove(80, "Hydro Pump", 100, 0.70),
    SplashMove(90, "Tidal Wave", 125, 0.65),
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
