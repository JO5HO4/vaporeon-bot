import json
from pathlib import Path
import pytest
from vaporeon_bot.content import ContentError, ContentStore
from vaporeon_bot.logic import parse_options
from vaporeon_bot.photos import discover_photos
from vaporeon_bot.discoveries import COLLECTION_SETS, completed_set_titles

def test_content_loads_seed_data():
    assert len(ContentStore.load().speak) >= 20

def test_malformed_content_fails(tmp_path: Path):
    (tmp_path / "speak.json").write_text("{")
    with pytest.raises(ContentError): ContentStore.load(tmp_path)

def test_choose_parser():
    assert parse_options("pizza | sushi | tacos") == ["pizza", "sushi", "tacos"]
    with pytest.raises(ValueError): parse_options("one")

def test_photo_discovery_filters_extensions(tmp_path: Path):
    image = tmp_path / "rare" / "sleepy" / "ok.png"; image.parent.mkdir(parents=True); image.write_bytes(b"x")
    (image.parent / "no.txt").write_text("x")
    found = discover_photos(tmp_path)
    assert len(found) == 1 and found[0].path == image


def test_collection_sets_unlock_only_after_every_item_is_found():
    beachcomber = set(COLLECTION_SETS["Beachcomber"]["items"])
    assert "Beachcomber" not in completed_set_titles(beachcomber - {"Pearl"})
    assert "Beachcomber" in completed_set_titles(beachcomber)
