"""Reusable rarity selection with deterministic RNG support."""

import random
from collections.abc import Iterable, Mapping
from typing import Any, TypeVar

from .constants import RARITY_WEIGHTS

T = TypeVar("T")


def choose_rarity(rng: random.Random | None = None) -> str:
    generator = rng or random
    roll = generator.random()
    cumulative = 0.0
    for rarity, weight in RARITY_WEIGHTS.items():
        cumulative += weight
        if roll < cumulative:
            return rarity
    return next(reversed(RARITY_WEIGHTS))


def choose_weighted_item(items: Iterable[T], weights: Iterable[float], rng: random.Random | None = None) -> T:
    values, item_weights = list(items), list(weights)
    if not values or len(values) != len(item_weights) or sum(item_weights) <= 0:
        raise ValueError("Items and positive weights are required.")
    return (rng or random).choices(values, weights=item_weights, k=1)[0]


def choose_item_by_rarity(items: Iterable[Mapping[str, Any]], rng: random.Random | None = None) -> tuple[Mapping[str, Any], str]:
    """Choose a curated item, gracefully falling back when a tier is empty."""
    values = list(items)
    if not values:
        raise ValueError("No content is available.")
    selected = choose_rarity(rng)
    matching = [item for item in values if item.get("rarity", "common") == selected]
    if matching:
        return (rng or random).choice(matching), selected
    available = [tier for tier in RARITY_WEIGHTS if any(item.get("rarity", "common") == tier for item in values)]
    fallback = choose_weighted_item(available, [RARITY_WEIGHTS[tier] for tier in available], rng)
    return (rng or random).choice([item for item in values if item.get("rarity", "common") == fallback]), fallback
