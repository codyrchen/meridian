from pathlib import Path

import pytest
from meridian_pipelines.load_unlock_event import CuratedEventError, load_curated_file


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(CuratedEventError, match="not found"):
        load_curated_file(tmp_path / "nope.yaml")


def test_non_mapping_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("- just\n- a\n- list\n")
    with pytest.raises(CuratedEventError, match="not a mapping"):
        load_curated_file(path)


@pytest.mark.parametrize("missing", ["asset", "primary_source", "event"])
def test_missing_required_section_raises(tmp_path: Path, missing: str) -> None:
    sections = {"asset": "{}", "primary_source": "{}", "event": "{}"}
    del sections[missing]
    path = tmp_path / "partial.yaml"
    path.write_text("\n".join(f"{k}: {v}" for k, v in sections.items()) + "\n")
    with pytest.raises(CuratedEventError, match=missing):
        load_curated_file(path)
