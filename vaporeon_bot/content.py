"""Validated JSON-backed personality content."""

import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .constants import DATA_DIR
from .rarity import choose_item_by_rarity


class ContentError(ValueError):
    pass


def _load_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as error:
        raise ContentError(f"Missing content file: {path}") from error
    except json.JSONDecodeError as error:
        raise ContentError(f"Malformed JSON in {path}: {error}") from error


def _require_list(path: Path) -> list[dict[str, Any]]:
    value = _load_json(path)
    if not isinstance(value, list) or not all(isinstance(item, dict) and isinstance(item.get("text"), str) for item in value):
        raise ContentError(f"{path} must be a list of objects with text fields.")
    return value


@dataclass(frozen=True)
class ContentStore:
    speak: list[dict[str, Any]]
    ask: list[dict[str, Any]]
    fortunes: list[dict[str, Any]]
    reactions: dict[str, list[dict[str, Any]]]
    friendship: dict[str, list[str]]
    encounters: dict[str, list[str]]
    custom: dict[str, list[Any]]

    @classmethod
    def load(cls, directory: Path = DATA_DIR) -> "ContentStore":
        speak = _require_list(directory / "speak.json")
        ask = _require_list(directory / "ask.json")
        fortunes = _require_list(directory / "fortunes.json")
        reactions = _load_json(directory / "reactions.json")
        friendship = _load_json(directory / "friendship.json")
        encounters = _load_json(directory / "encounters.json")
        if not isinstance(reactions, dict) or not isinstance(friendship, dict) or not isinstance(encounters, dict):
            raise ContentError("Reaction, friendship, and encounter files must contain JSON objects.")
        for action, lines in reactions.items():
            if not isinstance(lines, list) or not all(isinstance(item, dict) and isinstance(item.get("text"), str) for item in lines):
                raise ContentError(f"Reaction category {action!r} must contain text entries.")
        required_encounter_keys = {"moods", "activities"}
        if not required_encounter_keys.issubset(encounters) or not all(isinstance(encounters[key], list) for key in required_encounter_keys):
            raise ContentError("encounters.json needs moods and activities lists.")
        custom_path = directory / "custom.json"
        custom = _load_json(custom_path) if custom_path.exists() else {}
        if not isinstance(custom, dict):
            raise ContentError("custom.json must contain a JSON object.")
        custom_speak = custom.get("speak", [])
        if not isinstance(custom_speak, list) or not all(isinstance(item, dict) and isinstance(item.get("text"), str) and ("tags" not in item or isinstance(item["tags"], list)) for item in custom_speak):
            raise ContentError("custom.json speak entries must have text fields.")
        custom_fortunes = custom.get("fortunes", [])
        custom_activities = custom.get("activities", [])
        if not isinstance(custom_fortunes, list) or not all(isinstance(item, dict) and isinstance(item.get("text"), str) for item in custom_fortunes):
            raise ContentError("custom.json fortune entries must have text fields.")
        if not isinstance(custom_activities, list) or not all(isinstance(item, str) for item in custom_activities):
            raise ContentError("custom.json activities entries must be strings.")
        speak.extend(custom_speak)
        fortunes.extend(custom_fortunes)
        encounters["activities"].extend(custom_activities)
        return cls(speak, ask, fortunes, reactions, friendship, encounters, custom)

    def random_speak(self, mood: str | None = None, now: datetime | None = None) -> tuple[dict[str, Any], str]:
        eligible = [line for line in self.speak if mood is None or line.get("category") == mood]
        current = now or datetime.now().astimezone()
        contexts = {"weekday" if current.weekday() < 5 else "weekend"}
        contexts.add("morning" if 5 <= current.hour < 12 else "late_night" if current.hour >= 23 or current.hour < 5 else "daytime")
        contextual = [line for line in eligible if line.get("context") in contexts]
        timeless = [line for line in eligible if not line.get("context")]
        if contextual and (not timeless or random.random() < 0.25):
            eligible = contextual
        elif timeless:
            eligible = timeless
        if not eligible:
            raise ContentError(f"No speak lines are available for mood {mood!r}.")
        return choose_item_by_rarity(eligible)

    def random_reaction(self, action: str) -> tuple[dict[str, Any], str]:
        lines = self.reactions.get(action)
        if not lines:
            raise ContentError(f"No reactions are available for {action!r}.")
        return choose_item_by_rarity(lines)
