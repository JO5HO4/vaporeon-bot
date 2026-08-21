"""Cosmetic treasures Vaporeon can bring back from a dive."""

COLLECTIBLES = {
    "Pearl": "A soft, luminous pearl with excellent underwater manners.",
    "Sea Glass": "A smooth piece of sea glass in Vaporeon's favorite shade of blue.",
    "Message in a Bottle": "The note simply says: “remember to hydrate.”",
    "Moon Shell": "A shell that looks faintly silver whenever it is late.",
    "Lucky Pebble": "A perfectly round pebble that Vaporeon has declared lucky.",
    "Driftwood Charm": "A tiny piece of driftwood with suspiciously cozy energy.",
}

COLLECTIBLE_WEIGHTS = {
    "Pearl": 0.08,
    "Sea Glass": 0.30,
    "Message in a Bottle": 0.12,
    "Moon Shell": 0.10,
    "Lucky Pebble": 0.25,
    "Driftwood Charm": 0.15,
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
