import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from meridian_connectors.archive import ArchiveIntegrityError, RawArchive
from meridian_domain.enums import LicenseClass

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


def make_archive(tmp_path: Path) -> RawArchive:
    return RawArchive(tmp_path / "raw")


def test_archives_payload_with_checksum_and_file_uri(tmp_path: Path) -> None:
    archive = make_archive(tmp_path)
    payload = b'{"prices": []}'
    meta = archive.archive(
        source_name="coingecko",
        payload=payload,
        retrieved_at=NOW,
        knowledge_timestamp=NOW,
        license_class=LicenseClass.ATTRIBUTION_REQUIRED,
        source_uri="https://api.coingecko.com/x",
    )
    assert meta.checksum_sha256 == hashlib.sha256(payload).hexdigest()
    assert meta.object_uri.startswith("file://")
    stored = Path(meta.object_uri.removeprefix("file://"))
    assert stored.read_bytes() == payload


def test_identical_payload_dedupes_to_same_artifact_id(tmp_path: Path) -> None:
    archive = make_archive(tmp_path)
    kwargs: dict[str, Any] = {
        "source_name": "coingecko",
        "payload": b"same-bytes",
        "retrieved_at": NOW,
        "knowledge_timestamp": NOW,
        "license_class": LicenseClass.ATTRIBUTION_REQUIRED,
    }
    first = archive.archive(**kwargs)
    second = archive.archive(**kwargs)
    assert first.id == second.id
    assert first.checksum_sha256 == second.checksum_sha256
    files = list((tmp_path / "raw" / "coingecko").iterdir())
    assert len(files) == 1


def test_never_overwrites_corrupted_existing_file(tmp_path: Path) -> None:
    archive = make_archive(tmp_path)
    payload = b"original"
    meta = archive.archive(
        source_name="coingecko",
        payload=payload,
        retrieved_at=NOW,
        knowledge_timestamp=NOW,
        license_class=LicenseClass.PUBLIC,
    )
    stored = Path(meta.object_uri.removeprefix("file://"))
    stored.write_bytes(b"tampered")  # simulate on-disk corruption
    with pytest.raises(ArchiveIntegrityError):
        archive.archive(
            source_name="coingecko",
            payload=payload,
            retrieved_at=NOW,
            knowledge_timestamp=NOW,
            license_class=LicenseClass.PUBLIC,
        )
    assert stored.read_bytes() == b"tampered"  # untouched, surfaced loudly


def test_different_sources_do_not_collide(tmp_path: Path) -> None:
    archive = make_archive(tmp_path)
    a = archive.archive(
        source_name="coingecko",
        payload=b"payload",
        retrieved_at=NOW,
        knowledge_timestamp=NOW,
        license_class=LicenseClass.PUBLIC,
    )
    b = archive.archive(
        source_name="arbitrum_docs",
        payload=b"payload",
        retrieved_at=NOW,
        knowledge_timestamp=NOW,
        license_class=LicenseClass.PUBLIC,
    )
    assert a.id != b.id
