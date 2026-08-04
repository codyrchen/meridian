"""Loader-level behavior. Structural/taxonomy failure cases live in
test_curation_schema.py; these tests cover the loader's own gates."""

from pathlib import Path
from typing import cast

import pytest
import yaml
from meridian_pipelines.load_unlock_event import CuratedEventError, load_curated_file, seed_event
from sqlalchemy.orm import Session
from test_curation_schema import valid_data


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(CuratedEventError, match="not found"):
        load_curated_file(tmp_path / "nope.yaml")


def test_load_curated_file_returns_validated_model(tmp_path: Path) -> None:
    path = tmp_path / "event.yaml"
    path.write_text(yaml.safe_dump(valid_data()))
    parsed = load_curated_file(path)
    assert parsed.asset.coingecko_id == "synthetic-token"
    assert parsed.curation.status == "ready"


def test_seed_rejects_draft_status_before_touching_the_database(tmp_path: Path) -> None:
    data = valid_data()
    data["curation"]["status"] = "draft"
    path = tmp_path / "event.yaml"
    path.write_text(yaml.safe_dump(data))
    # The status gate fires before any session use, so no database is needed.
    with pytest.raises(CuratedEventError, match="ready"):
        seed_event(cast(Session, None), path, tmp_path)


def test_seed_rejects_missing_archive_before_touching_the_database(tmp_path: Path) -> None:
    path = tmp_path / "event.yaml"
    path.write_text(yaml.safe_dump(valid_data()))  # archive file never written
    with pytest.raises(CuratedEventError, match="missing"):
        seed_event(cast(Session, None), path, tmp_path)
