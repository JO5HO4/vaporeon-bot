import random
from vaporeon_bot.rarity import choose_item_by_rarity, choose_rarity

def test_rarity_is_deterministic_with_rng():
    assert choose_rarity(random.Random(1)) == "common"

def test_rarity_falls_back_when_selected_tier_is_missing():
    item, rarity = choose_item_by_rarity([{"text": "only", "rarity": "rare"}], random.Random(1))
    assert item["text"] == "only" and rarity == "rare"
