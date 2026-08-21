"""Short-lived SQLite operations for private friendship state."""

import sqlite3
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .constants import DATABASE_PATH


@dataclass(frozen=True)
class UserStats:
    user_id: int
    display_name: str
    affection: int
    pets: int
    boops: int
    feeds: int
    hugs: int
    splashes: int
    encounters: int
    photos: int
    plays: int
    dives: int
    quests: int
    rainy_splashes: int
    equipped_title: str | None
    first_interaction: str
    last_interaction: str


@dataclass(frozen=True)
class BattleHit:
    hp_before: int
    hp_after: int
    damage_dealt: int
    recovered: bool
    fainted: bool


@dataclass(frozen=True)
class BattleCard:
    hp: int
    wins: int
    losses: int
    hits: int
    misses: int
    critical_hits: int
    current_streak: int
    best_streak: int
    last_attacker: str | None
    last_move: str | None
    protection_until: datetime | None
    hydro_pump_survivals: int


@dataclass(frozen=True)
class BattleEvent:
    attacker_name: str
    move_name: str
    outcome: str
    damage: int
    created_at: datetime


@dataclass(frozen=True)
class Discovery:
    name: str
    quantity: int
    first_found_at: datetime | None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(path: Path = DATABASE_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(path: Path = DATABASE_PATH) -> None:
    with _connect(path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL DEFAULT 'Unknown trainer',
                affection INTEGER NOT NULL DEFAULT 0,
                pets INTEGER NOT NULL DEFAULT 0,
                boops INTEGER NOT NULL DEFAULT 0,
                feeds INTEGER NOT NULL DEFAULT 0,
                hugs INTEGER NOT NULL DEFAULT 0,
                splashes INTEGER NOT NULL DEFAULT 0,
                encounters INTEGER NOT NULL DEFAULT 0,
                photos INTEGER NOT NULL DEFAULT 0,
                plays INTEGER NOT NULL DEFAULT 0,
                dives INTEGER NOT NULL DEFAULT 0,
                quests INTEGER NOT NULL DEFAULT 0,
                rainy_splashes INTEGER NOT NULL DEFAULT 0,
                equipped_title TEXT,
                first_interaction TEXT NOT NULL,
                last_interaction TEXT NOT NULL
            )
        """)
        existing_columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        migrations = {
            "display_name": "TEXT NOT NULL DEFAULT 'Unknown trainer'",
            "hugs": "INTEGER NOT NULL DEFAULT 0",
            "splashes": "INTEGER NOT NULL DEFAULT 0",
            "encounters": "INTEGER NOT NULL DEFAULT 0",
            "photos": "INTEGER NOT NULL DEFAULT 0",
            "plays": "INTEGER NOT NULL DEFAULT 0",
            "dives": "INTEGER NOT NULL DEFAULT 0",
            "quests": "INTEGER NOT NULL DEFAULT 0",
            "rainy_splashes": "INTEGER NOT NULL DEFAULT 0",
            "equipped_title": "TEXT",
        }
        for column, definition in migrations.items():
            if column not in existing_columns:
                connection.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS interaction_cooldowns (
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                last_used TEXT NOT NULL,
                PRIMARY KEY (user_id, action)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS daily_encounters (
                guild_id INTEGER NOT NULL,
                encounter_date TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (guild_id, encounter_date)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS daily_quests (
                user_id INTEGER NOT NULL,
                quest_date TEXT NOT NULL,
                action TEXT NOT NULL,
                completed_at TEXT,
                PRIMARY KEY (user_id, quest_date)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS battle_hp (
                user_id INTEGER PRIMARY KEY,
                hp INTEGER NOT NULL,
                last_hit_at TEXT NOT NULL,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                hits INTEGER NOT NULL DEFAULT 0,
                misses INTEGER NOT NULL DEFAULT 0,
                critical_hits INTEGER NOT NULL DEFAULT 0,
                current_streak INTEGER NOT NULL DEFAULT 0,
                best_streak INTEGER NOT NULL DEFAULT 0,
                last_attacker TEXT,
                last_move TEXT,
                protection_until TEXT
            )
        """)
        battle_columns = {row["name"] for row in connection.execute("PRAGMA table_info(battle_hp)")}
        battle_migrations = {
            "wins": "INTEGER NOT NULL DEFAULT 0",
            "losses": "INTEGER NOT NULL DEFAULT 0",
            "hits": "INTEGER NOT NULL DEFAULT 0",
            "misses": "INTEGER NOT NULL DEFAULT 0",
            "critical_hits": "INTEGER NOT NULL DEFAULT 0",
            "current_streak": "INTEGER NOT NULL DEFAULT 0",
            "best_streak": "INTEGER NOT NULL DEFAULT 0",
            "last_attacker": "TEXT",
            "last_move": "TEXT",
            "protection_until": "TEXT",
            "hydro_pump_survivals": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, definition in battle_migrations.items():
            if column not in battle_columns:
                connection.execute(f"ALTER TABLE battle_hp ADD COLUMN {column} {definition}")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS battle_statuses (
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                PRIMARY KEY (user_id, status)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS battle_weather (
                guild_id INTEGER PRIMARY KEY,
                weather TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS battle_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id INTEGER NOT NULL,
                attacker_name TEXT NOT NULL,
                move_name TEXT NOT NULL,
                outcome TEXT NOT NULL,
                damage INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity >= 0),
                PRIMARY KEY (user_id, item_name)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS discoveries (
                user_id INTEGER NOT NULL,
                discovery_name TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity >= 0),
                first_found_at TEXT,
                PRIMARY KEY (user_id, discovery_name)
            )
        """)
        discovery_columns = {row["name"] for row in connection.execute("PRAGMA table_info(discoveries)")}
        if "first_found_at" not in discovery_columns:
            connection.execute("ALTER TABLE discoveries ADD COLUMN first_found_at TEXT")
            connection.execute("UPDATE discoveries SET first_found_at = ? WHERE first_found_at IS NULL", (_now(),))


def get_or_create_user(user_id: int, path: Path = DATABASE_PATH, display_name: str | None = None) -> UserStats:
    initialize_database(path)
    now = _now()
    name = display_name.strip()[:80] if display_name and display_name.strip() else "Unknown trainer"
    with _connect(path) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO users (user_id, display_name, first_interaction, last_interaction) VALUES (?, ?, ?, ?)",
            (user_id, name, now, now),
        )
        if display_name:
            connection.execute("UPDATE users SET display_name = ? WHERE user_id = ?", (name, user_id))
        row = connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return UserStats(**dict(row))


def get_user_stats(user_id: int, path: Path = DATABASE_PATH) -> UserStats:
    return get_or_create_user(user_id, path)


def record_interaction(user_id: int, *, affection_gain: int = 0, counter: str | None = None, display_name: str | None = None, path: Path = DATABASE_PATH) -> UserStats:
    if (affection_gain < 0 and counter not in {"plays", "boops"}) or counter not in {None, "pets", "boops", "feeds", "hugs", "splashes", "encounters", "photos", "plays", "dives", "quests"}:
        raise ValueError("Invalid friendship update.")
    get_or_create_user(user_id, path, display_name)
    counter_sql = f", {counter} = {counter} + 1" if counter else ""
    with _connect(path) as connection:
        connection.execute(
            f"UPDATE users SET affection = MAX(0, affection + ?), last_interaction = ?{counter_sql} WHERE user_id = ?",
            (affection_gain, _now(), user_id),
        )
    return get_user_stats(user_id, path)


def record_pet(user_id: int, affection_gain: int, path: Path = DATABASE_PATH, display_name: str | None = None) -> UserStats:
    return record_interaction(user_id, affection_gain=affection_gain, counter="pets", display_name=display_name, path=path)


def record_boop(user_id: int, affection_gain: int, path: Path = DATABASE_PATH, display_name: str | None = None) -> UserStats:
    return record_interaction(user_id, affection_gain=affection_gain, counter="boops", display_name=display_name, path=path)


def record_feed(user_id: int, affection_gain: int, path: Path = DATABASE_PATH, display_name: str | None = None) -> UserStats:
    return record_interaction(user_id, affection_gain=affection_gain, counter="feeds", display_name=display_name, path=path)


def record_hug(user_id: int, display_name: str | None = None, path: Path = DATABASE_PATH) -> UserStats:
    return record_interaction(user_id, counter="hugs", display_name=display_name, path=path)


def record_splash(user_id: int, display_name: str | None = None, path: Path = DATABASE_PATH, *, rainy: bool = False) -> UserStats:
    get_or_create_user(user_id, path, display_name)
    with _connect(path) as connection:
        connection.execute(
            "UPDATE users SET splashes = splashes + 1, rainy_splashes = rainy_splashes + ?, last_interaction = ? WHERE user_id = ?",
            (1 if rainy else 0, _now(), user_id),
        )
    return get_user_stats(user_id, path)


def set_equipped_title(user_id: int, title: str | None, path: Path = DATABASE_PATH) -> UserStats:
    """Persist one cosmetic title selected by a user."""
    get_or_create_user(user_id, path)
    with _connect(path) as connection:
        connection.execute("UPDATE users SET equipped_title = ? WHERE user_id = ?", (title, user_id))
    return get_user_stats(user_id, path)


def record_encounter(user_id: int, display_name: str | None = None, path: Path = DATABASE_PATH) -> UserStats:
    return record_interaction(user_id, counter="encounters", display_name=display_name, path=path)


def record_photo(user_id: int, display_name: str | None = None, path: Path = DATABASE_PATH) -> UserStats:
    return record_interaction(user_id, counter="photos", display_name=display_name, path=path)


def record_play(user_id: int, affection_gain: int, display_name: str | None = None, path: Path = DATABASE_PATH) -> UserStats:
    return record_interaction(user_id, affection_gain=affection_gain, counter="plays", display_name=display_name, path=path)


def record_dive(user_id: int, affection_gain: int = 0, display_name: str | None = None, path: Path = DATABASE_PATH) -> UserStats:
    return record_interaction(user_id, affection_gain=affection_gain, counter="dives", display_name=display_name, path=path)


def record_quest(user_id: int, affection_gain: int, display_name: str | None = None, path: Path = DATABASE_PATH) -> UserStats:
    return record_interaction(user_id, affection_gain=affection_gain, counter="quests", display_name=display_name, path=path)


def server_totals(path: Path = DATABASE_PATH) -> dict[str, int]:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute("""
            SELECT COUNT(*) friends, COALESCE(SUM(affection), 0) affection,
                COALESCE(SUM(pets), 0) pets, COALESCE(SUM(boops), 0) boops,
                COALESCE(SUM(feeds), 0) feeds, COALESCE(SUM(hugs), 0) hugs,
                COALESCE(SUM(splashes), 0) splashes,
                COALESCE(SUM(encounters), 0) encounters, COALESCE(SUM(photos), 0) photos,
                COALESCE(SUM(plays), 0) plays, COALESCE(SUM(dives), 0) dives, COALESCE(SUM(quests), 0) quests
            FROM users
        """).fetchone()
    return dict(row)


def leaderboard(counter: str, limit: int = 3, path: Path = DATABASE_PATH) -> list[tuple[str, int]]:
    """Return the highest-ranked users for one safe, persistent activity counter."""
    if counter not in {"affection", "pets", "boops", "feeds", "hugs", "splashes", "encounters", "photos", "plays", "dives", "quests"}:
        raise ValueError("Unknown leaderboard counter.")
    if limit < 1:
        raise ValueError("Leaderboard limit must be positive.")
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute(
            f"SELECT display_name, {counter} FROM users WHERE {counter} > 0 ORDER BY {counter} DESC, display_name COLLATE NOCASE ASC LIMIT ?",
            (limit,),
        ).fetchall()
    return [(row["display_name"], row[counter]) for row in rows]


def unknown_user_ids(path: Path = DATABASE_PATH, limit: int = 100) -> list[int]:
    """Return historic records that predate display-name tracking."""
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT user_id FROM users WHERE display_name = 'Unknown trainer' ORDER BY last_interaction DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [row["user_id"] for row in rows]


def update_display_name(user_id: int, display_name: str, path: Path = DATABASE_PATH) -> None:
    """Replace a historic placeholder with a Discord display name."""
    name = display_name.strip()[:80]
    if not name:
        return
    initialize_database(path)
    with _connect(path) as connection:
        connection.execute("UPDATE users SET display_name = ? WHERE user_id = ?", (name, user_id))


def claim_cooldown(user_id: int, action: str, cooldown_seconds: int, path: Path = DATABASE_PATH, now: datetime | None = None) -> int:
    """Claim a per-user cooldown; return whole seconds remaining, or zero on success."""
    if cooldown_seconds < 0:
        raise ValueError("Cooldown must not be negative.")
    initialize_database(path)
    current = now or datetime.now(timezone.utc)
    with _connect(path) as connection:
        row = connection.execute("SELECT last_used FROM interaction_cooldowns WHERE user_id = ? AND action = ?", (user_id, action)).fetchone()
        if row:
            previous = datetime.fromisoformat(row["last_used"])
            remaining = cooldown_seconds - (current - previous).total_seconds()
            if remaining > 0:
                return math.ceil(remaining)
        connection.execute("INSERT INTO interaction_cooldowns (user_id, action, last_used) VALUES (?, ?, ?) ON CONFLICT(user_id, action) DO UPDATE SET last_used = excluded.last_used", (user_id, action, current.isoformat()))
    return 0


def cooldown_remaining(user_id: int, action: str, cooldown_seconds: int, path: Path = DATABASE_PATH, now: datetime | None = None) -> int:
    """Return whole seconds left on a cooldown without claiming or changing it."""
    if cooldown_seconds < 0:
        raise ValueError("Cooldown must not be negative.")
    initialize_database(path)
    current = now or datetime.now(timezone.utc)
    with _connect(path) as connection:
        row = connection.execute("SELECT last_used FROM interaction_cooldowns WHERE user_id = ? AND action = ?", (user_id, action)).fetchone()
    if not row:
        return 0
    return max(0, math.ceil(cooldown_seconds - (current - datetime.fromisoformat(row["last_used"])).total_seconds()))


def add_inventory_item(user_id: int, item_name: str, quantity: int = 1, path: Path = DATABASE_PATH) -> None:
    """Add a positive quantity of one named bag item."""
    if quantity < 1:
        raise ValueError("Item quantity must be positive.")
    initialize_database(path)
    with _connect(path) as connection:
        connection.execute(
            "INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, item_name) DO UPDATE SET quantity = inventory.quantity + excluded.quantity",
            (user_id, item_name, quantity),
        )


def inventory_for_user(user_id: int, path: Path = DATABASE_PATH) -> dict[str, int]:
    """Return a compact item-count bag for one user."""
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ? AND quantity > 0 ORDER BY item_name", (user_id,)).fetchall()
    return {row["item_name"]: row["quantity"] for row in rows}


def add_discovery(user_id: int, discovery_name: str, path: Path = DATABASE_PATH) -> None:
    """Add one cosmetic dive discovery to a user's collection."""
    initialize_database(path)
    found_at = _now()
    with _connect(path) as connection:
        connection.execute(
            "INSERT INTO discoveries (user_id, discovery_name, quantity, first_found_at) VALUES (?, ?, 1, ?) "
            "ON CONFLICT(user_id, discovery_name) DO UPDATE SET quantity = discoveries.quantity + 1",
            (user_id, discovery_name, found_at),
        )


def discoveries_for_user(user_id: int, path: Path = DATABASE_PATH) -> dict[str, int]:
    """Return all cosmetic discoveries collected by one user."""
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute("SELECT discovery_name, quantity FROM discoveries WHERE user_id = ? AND quantity > 0 ORDER BY discovery_name", (user_id,)).fetchall()
    return {row["discovery_name"]: row["quantity"] for row in rows}


def discovery_details_for_user(user_id: int, path: Path = DATABASE_PATH) -> dict[str, Discovery]:
    """Return cosmetic discoveries with their quantity and first-found time."""
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT discovery_name, quantity, first_found_at FROM discoveries WHERE user_id = ? AND quantity > 0 ORDER BY discovery_name",
            (user_id,),
        ).fetchall()
    return {
        row["discovery_name"]: Discovery(
            name=row["discovery_name"],
            quantity=row["quantity"],
            first_found_at=datetime.fromisoformat(row["first_found_at"]) if row["first_found_at"] else None,
        )
        for row in rows
    }


def discovery_count(user_id: int | None = None, path: Path = DATABASE_PATH) -> int:
    """Count all collected cosmetic finds, globally or for one user."""
    initialize_database(path)
    query = "SELECT COALESCE(SUM(quantity), 0) total FROM discoveries"
    params: tuple[int, ...] = ()
    if user_id is not None:
        query += " WHERE user_id = ?"
        params = (user_id,)
    with _connect(path) as connection:
        row = connection.execute(query, params).fetchone()
    return row["total"]


def consume_inventory_item(user_id: int, item_name: str, path: Path = DATABASE_PATH) -> bool:
    """Consume one item if present, returning whether the bag contained it."""
    initialize_database(path)
    with _connect(path) as connection:
        result = connection.execute(
            "UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_name = ? AND quantity > 0",
            (user_id, item_name),
        )
        if result.rowcount != 1:
            return False
        connection.execute("DELETE FROM inventory WHERE user_id = ? AND item_name = ? AND quantity = 0", (user_id, item_name))
    return True


def heal_battle_hp(user_id: int, amount: int | None, path: Path = DATABASE_PATH, now: datetime | None = None) -> tuple[int, int]:
    """Restore battle HP; None means a full heal. Returns before and after HP."""
    if amount is not None and amount < 1:
        raise ValueError("Healing amount must be positive.")
    initialize_database(path)
    current = now or datetime.now(timezone.utc)
    with _connect(path) as connection:
        row = connection.execute("SELECT hp, last_hit_at FROM battle_hp WHERE user_id = ?", (user_id,)).fetchone()
        before = BATTLE_MAX_HP if row is None or _is_recovered(row, current) else row["hp"]
        after = BATTLE_MAX_HP if amount is None else min(BATTLE_MAX_HP, before + amount)
        if after != before:
            connection.execute("UPDATE battle_hp SET hp = ?, last_hit_at = ? WHERE user_id = ?", (after, current.isoformat(), user_id))
    return before, after


def clear_battle_statuses(user_id: int, path: Path = DATABASE_PATH) -> int:
    """Clear all short-lived battle statuses and return the number removed."""
    initialize_database(path)
    with _connect(path) as connection:
        result = connection.execute("DELETE FROM battle_statuses WHERE user_id = ?", (user_id,))
    return result.rowcount


def get_or_create_daily_encounter(guild_id: int, encounter_date: str, payload: dict[str, str], path: Path = DATABASE_PATH) -> dict[str, str]:
    """Return one durable encounter per guild and UTC date."""
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute("SELECT payload FROM daily_encounters WHERE guild_id = ? AND encounter_date = ?", (guild_id, encounter_date)).fetchone()
        if row:
            return json.loads(row["payload"])
        encoded = json.dumps(payload)
        connection.execute("INSERT INTO daily_encounters (guild_id, encounter_date, payload) VALUES (?, ?, ?)", (guild_id, encounter_date, encoded))
    return payload


def get_or_create_daily_quest(user_id: int, quest_date: str, action: str, path: Path = DATABASE_PATH) -> tuple[str, bool, bool]:
    """Return a user's daily action, completion state, and whether it was just assigned."""
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute("SELECT action, completed_at FROM daily_quests WHERE user_id = ? AND quest_date = ?", (user_id, quest_date)).fetchone()
        if row:
            return row["action"], row["completed_at"] is not None, False
        connection.execute("INSERT INTO daily_quests (user_id, quest_date, action) VALUES (?, ?, ?)", (user_id, quest_date, action))
    return action, False, True


def complete_daily_quest(user_id: int, action: str, quest_date: str, path: Path = DATABASE_PATH) -> bool:
    """Claim an uncompleted daily quest only when its assigned action occurs."""
    initialize_database(path)
    with _connect(path) as connection:
        result = connection.execute(
            "UPDATE daily_quests SET completed_at = ? WHERE user_id = ? AND quest_date = ? AND action = ? AND completed_at IS NULL",
            (_now(), user_id, quest_date, action),
        )
    return result.rowcount == 1


BATTLE_MAX_HP = 100
BATTLE_RECOVERY = timedelta(minutes=30)
BATTLE_STATUS_DURATION = timedelta(minutes=5)
RAIN_DURATION = timedelta(hours=1)
DEATH_TIMER = timedelta(minutes=30)


def _is_recovered(row: sqlite3.Row | None, current: datetime) -> bool:
    return bool(row and current - datetime.fromisoformat(row["last_hit_at"]) >= BATTLE_RECOVERY)


def get_battle_hp(user_id: int, path: Path = DATABASE_PATH, now: datetime | None = None) -> int:
    """Return current Vaporeon-game HP, treating inactive players as recovered."""
    initialize_database(path)
    current = now or datetime.now(timezone.utc)
    with _connect(path) as connection:
        row = connection.execute("SELECT hp, last_hit_at FROM battle_hp WHERE user_id = ?", (user_id,)).fetchone()
    if not row or _is_recovered(row, current):
        return BATTLE_MAX_HP
    return row["hp"]


def get_battle_card(user_id: int, path: Path = DATABASE_PATH, now: datetime | None = None) -> BattleCard:
    """Return a player's durable battle record, with HP recovered after downtime."""
    initialize_database(path)
    current = now or datetime.now(timezone.utc)
    with _connect(path) as connection:
        row = connection.execute("SELECT * FROM battle_hp WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return BattleCard(BATTLE_MAX_HP, 0, 0, 0, 0, 0, 0, 0, None, None, None, 0)
    hp = BATTLE_MAX_HP if _is_recovered(row, current) else row["hp"]
    protection = datetime.fromisoformat(row["protection_until"]) if row["protection_until"] else None
    if row["hp"] == 0:
        protection = max(protection or current, datetime.fromisoformat(row["last_hit_at"]) + DEATH_TIMER)
    if protection and protection <= current:
        protection = None
    return BattleCard(
        hp, row["wins"], row["losses"], row["hits"], row["misses"], row["critical_hits"],
        row["current_streak"], row["best_streak"], row["last_attacker"], row["last_move"], protection, row["hydro_pump_survivals"],
    )


def get_active_statuses(user_id: int, path: Path = DATABASE_PATH, now: datetime | None = None) -> set[str]:
    """Return active short-lived battle statuses, removing expired records."""
    initialize_database(path)
    current = now or datetime.now(timezone.utc)
    with _connect(path) as connection:
        connection.execute("DELETE FROM battle_statuses WHERE expires_at <= ?", (current.isoformat(),))
        rows = connection.execute("SELECT status FROM battle_statuses WHERE user_id = ?", (user_id,)).fetchall()
    return {row["status"] for row in rows}


def get_active_status_details(user_id: int, path: Path = DATABASE_PATH, now: datetime | None = None) -> dict[str, datetime]:
    """Return active battle statuses and their expiry times."""
    initialize_database(path)
    current = now or datetime.now(timezone.utc)
    with _connect(path) as connection:
        connection.execute("DELETE FROM battle_statuses WHERE expires_at <= ?", (current.isoformat(),))
        rows = connection.execute("SELECT status, expires_at FROM battle_statuses WHERE user_id = ?", (user_id,)).fetchall()
    return {row["status"]: datetime.fromisoformat(row["expires_at"]) for row in rows}


def get_faint_protection(user_id: int, path: Path = DATABASE_PATH, now: datetime | None = None) -> datetime | None:
    """Return the active post-faint death-timer expiry, if one remains."""
    card = get_battle_card(user_id, path, now)
    return card.protection_until


def record_battle_miss(user_id: int, target_id: int, attacker_name: str, move_name: str, path: Path = DATABASE_PATH, now: datetime | None = None) -> None:
    """Record a missed splash attempt and a small target-facing history entry."""
    initialize_database(path)
    current = now or datetime.now(timezone.utc)
    with _connect(path) as connection:
        connection.execute(
            "INSERT INTO battle_hp (user_id, hp, last_hit_at, misses) VALUES (?, ?, ?, 1) "
            "ON CONFLICT(user_id) DO UPDATE SET misses = battle_hp.misses + 1",
            (user_id, BATTLE_MAX_HP, current.isoformat()),
        )
        connection.execute(
            "INSERT INTO battle_history (target_id, attacker_name, move_name, outcome, damage, created_at) VALUES (?, ?, ?, 'miss', 0, ?)",
            (target_id, attacker_name, move_name, current.isoformat()),
        )


def recent_battle_history(user_id: int, limit: int = 3, path: Path = DATABASE_PATH) -> list[BattleEvent]:
    """Return a player's most recent received splash attempts."""
    if limit < 1:
        raise ValueError("History limit must be positive.")
    initialize_database(path)
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT attacker_name, move_name, outcome, damage, created_at FROM battle_history WHERE target_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [BattleEvent(row["attacker_name"], row["move_name"], row["outcome"], row["damage"], datetime.fromisoformat(row["created_at"])) for row in rows]


def apply_battle_status(user_id: int, status: str, path: Path = DATABASE_PATH, now: datetime | None = None) -> None:
    """Apply or refresh one five-minute playful battle status."""
    if status not in {"soaked", "slippery", "waterlogged"}:
        raise ValueError("Unknown battle status.")
    initialize_database(path)
    current = now or datetime.now(timezone.utc)
    expires = current + BATTLE_STATUS_DURATION
    with _connect(path) as connection:
        connection.execute(
            "INSERT INTO battle_statuses (user_id, status, expires_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, status) DO UPDATE SET expires_at = excluded.expires_at",
            (user_id, status, expires.isoformat()),
        )


def consume_battle_status(user_id: int, status: str, path: Path = DATABASE_PATH, now: datetime | None = None) -> bool:
    """Consume an active status and report whether it was present."""
    if status not in {"soaked", "slippery", "waterlogged"}:
        raise ValueError("Unknown battle status.")
    current = now or datetime.now(timezone.utc)
    if status not in get_active_statuses(user_id, path, current):
        return False
    with _connect(path) as connection:
        result = connection.execute("DELETE FROM battle_statuses WHERE user_id = ? AND status = ?", (user_id, status))
    return result.rowcount == 1


def get_weather(guild_id: int | None, path: Path = DATABASE_PATH, now: datetime | None = None) -> tuple[str, datetime] | None:
    """Return the active per-server weather, if any."""
    if guild_id is None:
        return None
    initialize_database(path)
    current = now or datetime.now(timezone.utc)
    with _connect(path) as connection:
        connection.execute("DELETE FROM battle_weather WHERE expires_at <= ?", (current.isoformat(),))
        row = connection.execute("SELECT weather, expires_at FROM battle_weather WHERE guild_id = ?", (guild_id,)).fetchone()
    return (row["weather"], datetime.fromisoformat(row["expires_at"])) if row else None


def start_weather(guild_id: int | None, weather: str, path: Path = DATABASE_PATH, now: datetime | None = None) -> tuple[str, datetime] | None:
    """Start one hour of server-wide weather, unless there is no server context."""
    if guild_id is None:
        return None
    if weather not in {"rainy", "misty", "drizzle", "perfect_puddle_weather", "suspiciously_dry"}:
        raise ValueError("Unknown weather.")
    initialize_database(path)
    current = now or datetime.now(timezone.utc)
    expires = current + RAIN_DURATION
    with _connect(path) as connection:
        connection.execute(
            "INSERT INTO battle_weather (guild_id, weather, expires_at) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET weather = excluded.weather, expires_at = excluded.expires_at",
            (guild_id, weather, expires.isoformat()),
        )
    return weather, expires


def start_rain(guild_id: int | None, path: Path = DATABASE_PATH, now: datetime | None = None) -> tuple[str, datetime] | None:
    """Start one hour of meaningful Rainy weather."""
    return start_weather(guild_id, "rainy", path, now)


def apply_splash_damage(user_id: int, damage: int, path: Path = DATABASE_PATH, now: datetime | None = None, *, attacker_id: int | None = None, attacker_name: str | None = None, move_name: str | None = None, critical: bool = False) -> BattleHit:
    """Apply persistent in-game splash damage, with automatic recovery after inactivity."""
    if damage < 1:
        raise ValueError("Damage must be positive.")
    initialize_database(path)
    current = now or datetime.now(timezone.utc)
    with _connect(path) as connection:
        row = connection.execute("SELECT * FROM battle_hp WHERE user_id = ?", (user_id,)).fetchone()
        recovered = _is_recovered(row, current)
        before = BATTLE_MAX_HP if row is None or recovered else row["hp"]
        dealt = min(before, damage)
        after = before - dealt
        fainted = before > 0 and after == 0
        hydro_pump_survival = 1 if move_name == "Hydro Pump" and after > 0 else 0
        protection_until = (current + DEATH_TIMER).isoformat() if fainted else None
        connection.execute(
            "INSERT INTO battle_hp (user_id, hp, last_hit_at, last_attacker, last_move, losses, current_streak, protection_until, hydro_pump_survivals) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET hp = excluded.hp, last_hit_at = excluded.last_hit_at, "
            "last_attacker = excluded.last_attacker, last_move = excluded.last_move, losses = battle_hp.losses + excluded.losses, "
            "current_streak = CASE WHEN excluded.losses = 1 THEN 0 ELSE battle_hp.current_streak END, "
            "protection_until = CASE WHEN excluded.losses = 1 THEN excluded.protection_until ELSE battle_hp.protection_until END, "
            "hydro_pump_survivals = battle_hp.hydro_pump_survivals + excluded.hydro_pump_survivals",
            (user_id, after, current.isoformat(), attacker_name, move_name, 1 if fainted else 0, 0, protection_until, hydro_pump_survival),
        )
        if attacker_id is not None:
            connection.execute(
                "INSERT INTO battle_hp (user_id, hp, last_hit_at, hits, critical_hits) VALUES (?, ?, ?, 1, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET hits = battle_hp.hits + 1, critical_hits = battle_hp.critical_hits + excluded.critical_hits",
                (attacker_id, BATTLE_MAX_HP, current.isoformat(), 1 if critical else 0),
            )
        if attacker_id is not None and attacker_name and move_name:
            connection.execute(
                "INSERT INTO battle_history (target_id, attacker_name, move_name, outcome, damage, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, attacker_name, move_name, "faint" if fainted else "hit", dealt, current.isoformat()),
            )
        if fainted and attacker_id is not None and attacker_id != user_id:
            connection.execute(
                "INSERT INTO battle_hp (user_id, hp, last_hit_at, wins, losses, current_streak, best_streak) VALUES (?, ?, ?, 1, 0, 1, 1) "
                "ON CONFLICT(user_id) DO UPDATE SET wins = battle_hp.wins + 1, current_streak = battle_hp.current_streak + 1, "
                "best_streak = MAX(battle_hp.best_streak, battle_hp.current_streak + 1)",
                (attacker_id, BATTLE_MAX_HP, current.isoformat()),
            )
    return BattleHit(before, after, dealt, recovered, fainted)
