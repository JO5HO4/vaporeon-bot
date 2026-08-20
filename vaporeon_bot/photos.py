"""Discover locally curated Vaporeon images without bundling artwork."""

from dataclasses import dataclass
from pathlib import Path

from .constants import IMAGE_EXTENSIONS, PHOTOS_DIR


@dataclass(frozen=True)
class Photo:
    path: Path


def discover_photos(root: Path = PHOTOS_DIR) -> list[Photo]:
    if not root.exists():
        return []
    photos: list[Photo] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        photos.append(Photo(path))
    return photos
