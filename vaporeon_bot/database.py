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
    affection: int
    pets: int
    boops: int
    feeds: int
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
                affection INTEGER NOT NULL DEFAULT 0,
                pets INTEGER NOT NULL DEFAULT 0,
                boops INTEGER NOT NULL DEFAULT 0,
                feeds INTEGER NOT NULL DEFAULT 0,
                first_interaction TEXT NOT NULL,
                last_interaction TEXT NOT NULL
            )
        """)
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


def get_or_create_user(user_id: int, path: Path = DATABASE_PATH) -> UserStats:
    initialize_database(path)
    now = _now()
    with _connect(path) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO users (user_id, first_interaction, last_interaction) VALUES (?, ?, ?)",
            (user_id, now, now),
        )
        row = connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return UserStats(**dict(row))


def get_user_stats(user_id: int, path: Path = DATABASE_PATH) -> UserStats:
    return get_or_create_user(user_id, path)


def record_interaction(user_id: int, *, affection_gain: int = 0, counter: str | None = None, path: Path = DATABASE_PATH) -> UserStats:
    if affection_gain < 0 or counter not in {None, "pets", "boops", "feeds"}:
        raise ValueError("Invalid friendship update.")
    get_or_create_user(user_id, path)
    counter_sql = f", {counter} = {counter} + 1" if counter else ""
    with _connect(path) as connection:
        connection.execute(
            f"UPDATE users SET affection = affection + ?, last_interaction = ?{counter_sql} WHERE user_id = ?",
            (affection_gain, _now(), user_id),
        )
    return get_user_stats(user_id, path)


def record_pet(user_id: int, affection_gain: int, path: Path = DATABASE_PATH) -> UserStats:
    return record_interaction(user_id, affection_gain=affection_gain, counter="pets", path=path)


def record_boop(user_id: int, affection_gain: int, path: Path = DATABASE_PATH) -> UserStats:
    return record_interaction(user_id, affection_gain=affection_gain, counter="boops", path=path)


def record_feed(user_id: int, affection_gain: int, path: Path = DATABASE_PATH) -> UserStats:
    return record_interaction(user_id, affection_gain=affection_gain, counter="feeds", path=path)


def server_totals(path: Path = DATABASE_PATH) -> dict[str, int]:
    initialize_database(path)
    with _connect(path) as connection:
        row = connection.execute("SELECT COUNT(*) friends, COALESCE(SUM(pets), 0) pets, COALESCE(SUM(boops), 0) boops, COALESCE(SUM(feeds), 0) feeds FROM users").fetchone()
    return dict(row)


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
