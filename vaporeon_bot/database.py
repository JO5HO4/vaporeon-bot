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
    quests: int
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
    last_attacker: str | None
    last_move: str | None


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
                quests INTEGER NOT NULL DEFAULT 0,
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
            "quests": "INTEGER NOT NULL DEFAULT 0",
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
                last_attacker TEXT,
                last_move TEXT
            )
        """)
        battle_columns = {row["name"] for row in connection.execute("PRAGMA table_info(battle_hp)")}
        battle_migrations = {
            "wins": "INTEGER NOT NULL DEFAULT 0",
            "losses": "INTEGER NOT NULL DEFAULT 0",
            "last_attacker": "TEXT",
            "last_move": "TEXT",
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
    if affection_gain < 0 or counter not in {None, "pets", "boops", "feeds", "hugs", "splashes", "encounters", "photos", "plays", "quests"}:
        raise ValueError("Invalid friendship update.")
    get_or_create_user(user_id, path, display_name)
    counter_sql = f", {counter} = {counter} + 1" if counter else ""
    with _connect(path) as connection:
        connection.execute(
            f"UPDATE users SET affection = affection + ?, last_interaction = ?{counter_sql} WHERE user_id = ?",
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


def record_splash(user_id: int, display_name: str | None = None, path: Path = DATABASE_PATH) -> UserStats:
    return record_interaction(user_id, counter="splashes", display_name=display_name, path=path)


def record_encounter(user_id: int, display_name: str | None = None, path: Path = DATABASE_PATH) -> UserStats:
    return record_interaction(user_id, counter="encounters", display_name=display_name, path=path)


def record_photo(user_id: int, display_name: str | None = None, path: Path = DATABASE_PATH) -> UserStats:
    return record_interaction(user_id, counter="photos", display_name=display_name, path=path)


def record_play(user_id: int, affection_gain: int, display_name: str | None = None, path: Path = DATABASE_PATH) -> UserStats:
    return record_interaction(user_id, affection_gain=affection_gain, counter="plays", display_name=display_name, path=path)


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
                COALESCE(SUM(plays), 0) plays, COALESCE(SUM(quests), 0) quests
            FROM users
        """).fetchone()
    return dict(row)


def leaderboard(counter: str, limit: int = 3, path: Path = DATABASE_PATH) -> list[tuple[str, int]]:
    """Return the highest-ranked users for one safe, persistent activity counter."""
    if counter not in {"affection", "pets", "boops", "feeds", "hugs", "splashes", "encounters", "photos", "plays", "quests"}:
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
        return BattleCard(BATTLE_MAX_HP, 0, 0, None, None)
    hp = BATTLE_MAX_HP if _is_recovered(row, current) else row["hp"]
    return BattleCard(hp, row["wins"], row["losses"], row["last_attacker"], row["last_move"])


def get_active_statuses(user_id: int, path: Path = DATABASE_PATH, now: datetime | None = None) -> set[str]:
    """Return active short-lived battle statuses, removing expired records."""
    initialize_database(path)
    current = now or datetime.now(timezone.utc)
    with _connect(path) as connection:
        connection.execute("DELETE FROM battle_statuses WHERE expires_at <= ?", (current.isoformat(),))
        rows = connection.execute("SELECT status FROM battle_statuses WHERE user_id = ?", (user_id,)).fetchall()
    return {row["status"] for row in rows}


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


def start_rain(guild_id: int | None, path: Path = DATABASE_PATH, now: datetime | None = None) -> tuple[str, datetime] | None:
    """Start one hour of server-wide rain, unless there is no server context."""
    if guild_id is None:
        return None
    initialize_database(path)
    current = now or datetime.now(timezone.utc)
    expires = current + RAIN_DURATION
    with _connect(path) as connection:
        connection.execute(
            "INSERT INTO battle_weather (guild_id, weather, expires_at) VALUES (?, 'rainy', ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET weather = excluded.weather, expires_at = excluded.expires_at",
            (guild_id, expires.isoformat()),
        )
    return "rainy", expires


def apply_splash_damage(user_id: int, damage: int, path: Path = DATABASE_PATH, now: datetime | None = None, *, attacker_id: int | None = None, attacker_name: str | None = None, move_name: str | None = None) -> BattleHit:
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
        connection.execute(
            "INSERT INTO battle_hp (user_id, hp, last_hit_at, last_attacker, last_move, losses) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET hp = excluded.hp, last_hit_at = excluded.last_hit_at, "
            "last_attacker = excluded.last_attacker, last_move = excluded.last_move, losses = battle_hp.losses + excluded.losses",
            (user_id, after, current.isoformat(), attacker_name, move_name, 1 if fainted else 0),
        )
        if fainted and attacker_id is not None and attacker_id != user_id:
            connection.execute(
                "INSERT INTO battle_hp (user_id, hp, last_hit_at, wins, losses) VALUES (?, ?, ?, 1, 0) "
                "ON CONFLICT(user_id) DO UPDATE SET wins = battle_hp.wins + 1",
                (attacker_id, BATTLE_MAX_HP, current.isoformat()),
            )
    return BattleHit(before, after, dealt, recovered, fainted)
