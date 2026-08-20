"""Small, useful item set for Vaporeon's dive and bag commands."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BagItem:
    name: str
    description: str
    heal_amount: int | None = None
    clears_statuses: bool = False


ITEMS = {
    "Potion": BagItem("Potion", "Restores 20 battle HP.", heal_amount=20),
    "Super Potion": BagItem("Super Potion", "Restores 50 battle HP.", heal_amount=50),
    "Max Potion": BagItem("Max Potion", "Restores battle HP to 100.", heal_amount=None),
    "Full Heal": BagItem("Full Heal", "Clears Soaked, Slippery, and Waterlogged.", clears_statuses=True),
}

ITEM_DROP_WEIGHTS = {
    "Potion": 0.50,
    "Super Potion": 0.30,
    "Max Potion": 0.10,
    "Full Heal": 0.10,
}

TRASH_FINDS = (
    "a soggy receipt. The ink has become interpretive art.",
    "one bottle cap. Vaporeon insists it may be treasure anyway.",
    "a very wet leaf with no apparent purpose.",
    "a suspiciously smooth rock. It is probably just a rock.",
    "an old sock. Vaporeon declines to elaborate.",
)
