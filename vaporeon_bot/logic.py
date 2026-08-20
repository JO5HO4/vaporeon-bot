"""Small Discord-independent helpers used by command handlers."""

import random


def parse_options(options: str) -> list[str]:
    parsed = [option.strip() for option in options.split("|") if option.strip()]
    if len(parsed) < 2:
        raise ValueError("Please provide at least two options separated by |.")
    return parsed


def deterministic_rating(thing: str) -> float:
    """A stable per-text playful rating, without implying real analysis."""
    return random.Random(thing.casefold().strip()).randint(0, 100) / 10
