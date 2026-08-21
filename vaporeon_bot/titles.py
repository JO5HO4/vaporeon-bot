"""Cosmetic achievement titles for long-term Vaporeon activity."""

from .database import BattleCard, UserStats


def achievement_titles(stats: UserStats, battle: BattleCard) -> tuple[str, ...]:
    """Return titles earned from durable friendship and battle statistics."""
    titles: list[str] = []
    if stats.splashes >= 1:
        titles.append("First Splash")
    if stats.rainy_splashes >= 10:
        titles.append("Rain Dancer")
    if battle.hydro_pump_survivals >= 1:
        titles.append("Hydro Pump Survivor")
    if stats.feeds >= 25:
        titles.append("Berry Benefactor")
    if stats.splashes >= 25:
        titles.append("Frequently Damp")
    if stats.splashes >= 100:
        titles.append("Professional Menace")
    if stats.encounters >= 25:
        titles.append("Nap Enthusiast")
    if stats.pets >= 1000:
        titles.append("1000 Pets")
    if stats.dives >= 50:
        titles.append("Deep Sea Regular")
    if stats.quests >= 25:
        titles.append("Quest Keeper")
    if stats.duel_wins >= 1:
        titles.append("Duelist")
    if stats.duel_wins >= 10:
        titles.append("Puddle Champion")
    return tuple(titles)


def unlocked_titles(stats: UserStats, battle: BattleCard, collection_titles: tuple[str, ...]) -> tuple[str, ...]:
    """Combine achievement and collection titles without duplicates."""
    return tuple(dict.fromkeys((*achievement_titles(stats, battle), *collection_titles)))
