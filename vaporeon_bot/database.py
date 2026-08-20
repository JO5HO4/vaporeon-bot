"""Short-lived SQLite operations for private friendship state."""

import sqlite3
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
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


def get_or_create_daily_quest(user_id: int, quest_date: str, action: str, path: Path = DATABASE_PATH) -> tuple[str, bool]:
    """Return a user's durable daily action and whether they have completed it."""
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute("SELECT action, completed_at FROM daily_quests WHERE user_id = ? AND quest_date = ?", (user_id, quest_date)).fetchone()
        if row:
            return row["action"], row["completed_at"] is not None
        connection.execute("INSERT INTO daily_quests (user_id, quest_date, action) VALUES (?, ?, ?)", (user_id, quest_date, action))
    return action, False


def complete_daily_quest(user_id: int, action: str, quest_date: str, path: Path = DATABASE_PATH) -> bool:
    """Claim an uncompleted daily quest only when its assigned action occurs."""
    initialize_database(path)
    with _connect(path) as connection:
        result = connection.execute(
            "UPDATE daily_quests SET completed_at = ? WHERE user_id = ? AND quest_date = ? AND action = ? AND completed_at IS NULL",
            (_now(), user_id, quest_date, action),
        )
    return result.rowcount == 1
