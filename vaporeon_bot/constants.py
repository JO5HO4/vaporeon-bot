"""Central configuration for the Vaporeon bot."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PHOTOS_DIR = DATA_DIR / "photos"
DATABASE_PATH = DATA_DIR / "vaporeon.db"

WATER_BLUE = 0x4FA9E8
RARITY_WEIGHTS = {"common": 0.95, "rare": 0.045, "legendary": 0.005}
RARITIES = tuple(RARITY_WEIGHTS)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

FRIENDSHIP_THRESHOLDS = (
    ("Stranger", 0, 19),
    ("Acquaintance", 20, 99),
    ("Friend", 100, 299),
    ("Best Friend", 300, 999),
    ("Vaporeon's Chosen Human", 1000, None),
)

PROGRESS_BAR_WIDTH = 20
BOOP_OUTCOME_WEIGHTS = {"accept": 0.70, "offended": 0.20, "splash": 0.10}
PET_RARE_AFFECTION = 5
FEED_RARE_AFFECTION = 10
INTERACTION_RARE_CHANCE = 0.03
PET_COOLDOWN_SECONDS = 5 * 60
BOOP_COOLDOWN_SECONDS = 5 * 60
FEED_COOLDOWN_SECONDS = 60 * 60
SPLASH_COOLDOWN_SECONDS = 3 * 60
DIVE_COOLDOWN_SECONDS = 60 * 60
