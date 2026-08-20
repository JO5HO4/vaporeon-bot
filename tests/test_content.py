import json
from pathlib import Path
import pytest
from vaporeon_bot.content import ContentError, ContentStore
from vaporeon_bot.logic import parse_options
from vaporeon_bot.photos import discover_photos

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
