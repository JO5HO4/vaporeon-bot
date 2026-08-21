"""Cosmetic treasures Vaporeon can bring back from a dive."""

COLLECTIBLES = {
    "Pearl": "A soft, luminous pearl with excellent underwater manners.",
    "Sea Glass": "A smooth piece of sea glass in Vaporeon's favorite shade of blue.",
    "Message in a Bottle": "The note simply says: “remember to hydrate.”",
    "Moon Shell": "A shell that looks faintly silver whenever it is late.",
    "Lucky Pebble": "A perfectly round pebble that Vaporeon has declared lucky.",
    "Driftwood Charm": "A tiny piece of driftwood with suspiciously cozy energy.",
    "Berry Seed": "A tiny seed that Vaporeon insists has enormous berry potential.",
    "Berry Wrapper": "A crinkly little wrapper that still smells faintly like a snack.",
    "Perfectly Round Berry": "A berry so round that Vaporeon has been rolling it around with great focus.",
}

COLLECTIBLE_WEIGHTS = {
    "Pearl": 0.08,
    "Sea Glass": 0.30,
    "Message in a Bottle": 0.12,
    "Moon Shell": 0.10,
    "Lucky Pebble": 0.25,
    "Driftwood Charm": 0.15,
    "Berry Seed": 0.08,
    "Berry Wrapper": 0.08,
    "Perfectly Round Berry": 0.08,
}

RARE_COLLECTIBLES = {
    "Tiny Blue Bottle": "A tiny bottle full of blue light. Vaporeon will not explain where it came from.",
    "Shiny Pebble": "A pebble so shiny that Vaporeon checks it twice every time you look at it.",
    "Ancient Spoon": "An extremely old spoon with no obvious connection to the ocean. Important, somehow.",
    "Extremely Important Stick": "A very serious stick. Vaporeon carried it home with ceremonial care.",
}

COLLECTIBLE_RARITIES = {
    **{name: "Common" for name in COLLECTIBLES},
    **{name: "Rare" for name in RARE_COLLECTIBLES},
}

ALL_COLLECTIBLES = {**COLLECTIBLES, **RARE_COLLECTIBLES}

COLLECTION_SETS = {
    "Beachcomber": {
        "title": "Beachcomber",
        "items": ("Pearl", "Sea Glass", "Moon Shell", "Driftwood Charm"),
    },
    "Berry": {
        "title": "Berry Connoisseur",
        "items": ("Berry Seed", "Berry Wrapper", "Perfectly Round Berry"),
    },
    "Rainy Day": {
        "title": "Rainy Day Friend",
        "items": ("Tiny Blue Bottle", "Message in a Bottle", "Shiny Pebble"),
    },
    "Nap Time": {
        "title": "Nap Archivist",
        "items": ("Moon Shell", "Lucky Pebble", "Extremely Important Stick"),
    },
    "Trash Treasures": {
        "title": "Certified Treasure Finder",
        "items": ("Ancient Spoon", "Extremely Important Stick", "Berry Wrapper"),
    },
}


def completed_set_titles(found_names: set[str]) -> tuple[str, ...]:
    """Return cosmetic titles unlocked by the user's unique discoveries."""
    return tuple(
        details["title"]
        for details in COLLECTION_SETS.values()
        if set(details["items"]).issubset(found_names)
    )
