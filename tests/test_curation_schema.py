"""Mechanical validation of template-v2 curation files: one valid baseline,
then one test per rule the validator must enforce."""

import hashlib
from pathlib import Path
from typing import Any

import pytest
import yaml
from meridian_pipelines.curation_schema import (
    CurationFileError,
    parse_curation_file,
    verify_source_archives,
)

CHECKSUM = "ab" * 32


def valid_data(**event_overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema_version": 2,
        "curation": {"status": "ready", "curator": "tester", "curated_on": "2026-08-04"},
        "asset": {
            "symbol": "SYNTH",
            "name": "Synthetic Token",
            "coingecko_id": "synthetic-token",
            "decimals": 18,
        },
        "sources": [
            {
                "source_name": "synthetic_docs",
                "source_uri": "https://example.invalid/tokenomics",
                "role": "primary",
                "claims": ["schedule", "amount", "allocation"],
                "archived_path": f"data/raw/synthetic_docs/{CHECKSUM}.raw",
                "checksum_sha256": CHECKSUM,
                "retrieved_at": "2026-08-01T00:00:00Z",
                "license_class": "public",
                "excerpt": "10% of supply unlocks on 2026-06-16",
            },
            {
                "source_name": "synthetic_aggregator",
                "source_uri": "https://example.invalid/aggregator",
                "role": "secondary_cross_check",
                "claims": ["amount"],
                "license_class": "restricted",
                "reports": "agrees: 1,000,000 SYNTH on 2026-06-16",
                "agrees": True,
            },
        ],
        "vesting_series": {
            "series_slug": "synth-investor-monthly",
            "name": "SYNTH investor monthly vesting",
            "cadence": "monthly",
            "tranche_count": 36,
        },
        "event": {
            "event_kind": "scheduled",
            "scheduled_at": "2026-06-16T00:00:00Z",
            "release_type": "linear",
            "allocation_bucket": "investor",
            "amount_tokens": "1000000",
            "amount_provenance": "reported",
            "tranche_number": 12,
            "source_confidence": "verified_primary",
            "ambiguity_flags": ["synthetic test data"],
        },
        "checklist": {
            "date_verified_from_primary": True,
            "amount_reported_or_derivation_recorded": True,
            "primary_source_archived_and_checksummed": True,
            "secondary_cross_check_recorded": True,
            "no_unresolved_source_conflicts": True,
            "unknown_fields_left_null_not_guessed": True,
        },
    }
    data["event"].update(event_overrides)
    return data


def write_and_parse(tmp_path: Path, data: dict[str, Any]) -> Any:
    path = tmp_path / "event.yaml"
    path.write_text(yaml.safe_dump(data))
    return parse_curation_file(path)


def test_valid_file_parses(tmp_path: Path) -> None:
    parsed = write_and_parse(tmp_path, valid_data())
    assert parsed.event.tranche_number == 12
    assert parsed.vesting_series is not None
    assert len(parsed.sources) == 2


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(CurationFileError, match="not found"):
        parse_curation_file(tmp_path / "nope.yaml")


def test_non_mapping_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("- just\n- a\n- list\n")
    with pytest.raises(CurationFileError, match="not a mapping"):
        parse_curation_file(path)


def test_wrong_schema_version_raises(tmp_path: Path) -> None:
    data = valid_data()
    data["schema_version"] = 1
    with pytest.raises(CurationFileError, match="schema_version must be 2"):
        write_and_parse(tmp_path, data)


@pytest.mark.parametrize("missing", ["curation", "asset", "sources", "event", "checklist"])
def test_missing_section_raises(tmp_path: Path, missing: str) -> None:
    data = valid_data()
    del data[missing]
    with pytest.raises(CurationFileError, match=missing):
        write_and_parse(tmp_path, data)


def test_unknown_extra_field_rejected(tmp_path: Path) -> None:
    data = valid_data()
    data["event"]["scheduled_att"] = "2026-06-16T00:00:00Z"  # typo must not pass silently
    with pytest.raises(CurationFileError):
        write_and_parse(tmp_path, data)


def test_derived_without_derivation_rejected(tmp_path: Path) -> None:
    with pytest.raises(CurationFileError, match="derivation"):
        write_and_parse(tmp_path, valid_data(amount_provenance="derived", derivation=None))


def test_derived_with_derivation_accepted(tmp_path: Path) -> None:
    parsed = write_and_parse(
        tmp_path, valid_data(amount_provenance="derived", derivation="total * 0.10 per docs")
    )
    assert parsed.event.derivation is not None


def test_no_primary_source_rejected(tmp_path: Path) -> None:
    data = valid_data()
    data["sources"] = [data["sources"][1]]  # secondary only
    with pytest.raises(CurationFileError, match="role=primary"):
        write_and_parse(tmp_path, data)


def test_schedule_claim_must_be_primary_backed(tmp_path: Path) -> None:
    data = valid_data()
    data["sources"][0]["claims"] = ["amount", "allocation"]  # schedule claim lost
    with pytest.raises(CurationFileError, match="schedule"):
        write_and_parse(tmp_path, data)


def test_amount_claim_must_be_primary_backed(tmp_path: Path) -> None:
    data = valid_data()
    data["sources"][0]["claims"] = ["schedule"]
    with pytest.raises(CurationFileError, match="amount"):
        write_and_parse(tmp_path, data)


def test_primary_without_archive_rejected(tmp_path: Path) -> None:
    data = valid_data()
    for key in ("archived_path", "checksum_sha256", "retrieved_at"):
        del data["sources"][0][key]
    with pytest.raises(CurationFileError, match="archived"):
        write_and_parse(tmp_path, data)


def test_partial_archive_fields_rejected(tmp_path: Path) -> None:
    data = valid_data()
    del data["sources"][0]["retrieved_at"]
    with pytest.raises(CurationFileError, match="together"):
        write_and_parse(tmp_path, data)


def test_bad_checksum_format_rejected(tmp_path: Path) -> None:
    data = valid_data()
    data["sources"][0]["checksum_sha256"] = "NOT-A-CHECKSUM"
    with pytest.raises(CurationFileError):
        write_and_parse(tmp_path, data)


def test_secondary_without_agrees_rejected(tmp_path: Path) -> None:
    data = valid_data()
    del data["sources"][1]["agrees"]
    with pytest.raises(CurationFileError, match="agrees"):
        write_and_parse(tmp_path, data)


def test_disagreeing_secondary_blocks_file(tmp_path: Path) -> None:
    data = valid_data()
    data["sources"][1]["agrees"] = False
    with pytest.raises(CurationFileError, match="exclusions"):
        write_and_parse(tmp_path, data)


def test_ready_with_unchecked_item_rejected(tmp_path: Path) -> None:
    data = valid_data()
    data["checklist"]["no_unresolved_source_conflicts"] = False
    with pytest.raises(CurationFileError, match="checklist"):
        write_and_parse(tmp_path, data)


def test_draft_with_unchecked_items_parses(tmp_path: Path) -> None:
    data = valid_data()
    data["curation"]["status"] = "draft"
    data["checklist"]["no_unresolved_source_conflicts"] = False
    parsed = write_and_parse(tmp_path, data)
    assert parsed.curation.status == "draft"


def test_naive_timestamp_rejected(tmp_path: Path) -> None:
    with pytest.raises(CurationFileError, match="timezone"):
        write_and_parse(tmp_path, valid_data(scheduled_at="2026-06-16T00:00:00"))


def test_tranche_number_without_series_rejected(tmp_path: Path) -> None:
    data = valid_data()
    del data["vesting_series"]
    with pytest.raises(CurationFileError, match="vesting_series"):
        write_and_parse(tmp_path, data)


def test_tranche_number_beyond_count_rejected(tmp_path: Path) -> None:
    with pytest.raises(CurationFileError, match="tranche_count"):
        write_and_parse(tmp_path, valid_data(tranche_number=37))


def test_bucket_composition_parses(tmp_path: Path) -> None:
    parsed = write_and_parse(
        tmp_path,
        valid_data(
            allocation_bucket="unknown",
            bucket_composition=[
                {"bucket": "team", "provenance": "secondary_cross_check", "note": "aggregator"},
                {"bucket": "investor", "provenance": "secondary_cross_check"},
            ],
        ),
    )
    assert parsed.event.bucket_composition is not None
    assert len(parsed.event.bucket_composition) == 2


def test_archive_verification_checksum_mismatch(tmp_path: Path) -> None:
    payload = b"synthetic tokenomics document"
    checksum = hashlib.sha256(payload).hexdigest()
    archive = tmp_path / "data" / "raw" / "synthetic_docs"
    archive.mkdir(parents=True)
    (archive / f"{checksum}.raw").write_bytes(payload)

    data = valid_data()
    data["sources"][0]["archived_path"] = f"data/raw/synthetic_docs/{checksum}.raw"
    data["sources"][0]["checksum_sha256"] = "00" * 32  # wrong on purpose
    parsed = write_and_parse(tmp_path, data)
    with pytest.raises(CurationFileError, match="does not match"):
        verify_source_archives(parsed, tmp_path)


def test_archive_verification_success_and_missing_file(tmp_path: Path) -> None:
    payload = b"synthetic tokenomics document"
    checksum = hashlib.sha256(payload).hexdigest()
    archive = tmp_path / "data" / "raw" / "synthetic_docs"
    archive.mkdir(parents=True)
    (archive / f"{checksum}.raw").write_bytes(payload)

    data = valid_data()
    data["sources"][0]["archived_path"] = f"data/raw/synthetic_docs/{checksum}.raw"
    data["sources"][0]["checksum_sha256"] = checksum
    parsed = write_and_parse(tmp_path, data)
    verified = verify_source_archives(parsed, tmp_path)
    assert set(verified) == {checksum}  # secondary without archive is skipped

    (archive / f"{checksum}.raw").rename(archive / "moved.raw")
    with pytest.raises(CurationFileError, match="missing"):
        verify_source_archives(parsed, tmp_path)
