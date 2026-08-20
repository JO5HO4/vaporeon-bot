"""Pure friendship tier and progress-bar calculations."""

from dataclasses import dataclass

from .constants import FRIENDSHIP_THRESHOLDS, PROGRESS_BAR_WIDTH


@dataclass(frozen=True)
class FriendshipTier:
    name: str
    minimum: int
    maximum: int | None


TIERS = tuple(FriendshipTier(*threshold) for threshold in FRIENDSHIP_THRESHOLDS)


def friendship_level(affection: int) -> FriendshipTier:
    if affection < 0:
        raise ValueError("Affection cannot be negative.")
    return next(tier for tier in reversed(TIERS) if affection >= tier.minimum)


def progress_to_next_tier(affection: int) -> float:
    tier = friendship_level(affection)
    if tier.maximum is None:
        return 1.0
    return (affection - tier.minimum) / (tier.maximum - tier.minimum + 1)


def build_progress_bar(progress: float, width: int = PROGRESS_BAR_WIDTH) -> str:
    if width <= 0:
        raise ValueError("Progress-bar width must be positive.")
    filled = max(0, min(width, int(progress * width)))
    return "█" * filled + "░" * (width - filled)
