"""Revision flow: supersede a seeded event version and prove both the
current-state and point-in-time (as-of) views."""

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from meridian_domain.enums import (
    AllocationBucket,
    AmountProvenance,
    EventKind,
    ReleaseType,
    SourceConfidence,
)
from meridian_domain.models import UnlockEvent
from meridian_pipelines.db import make_session
from meridian_pipelines.event_versions import (
    RevisionError,
    current_event_versions,
    event_versions_as_of,
    supersede_event_version,
)
from meridian_pipelines.ids import event_version_uuid
from meridian_pipelines.load_unlock_event import seed_event
from meridian_pipelines.tables import UnlockEventRow
from sqlalchemy import Engine

pytestmark = pytest.mark.integration

SEED_KNOWLEDGE = datetime(2026, 7, 30, tzinfo=UTC)


def write_curation_file(tmp_path: Path) -> Path:
    doc = b"synthetic vesting schedule for revision test"
    checksum = hashlib.sha256(doc).hexdigest()
    archive_dir = tmp_path / "data" / "raw" / "revision_docs"
    archive_dir.mkdir(parents=True)
    (archive_dir / f"{checksum}.raw").write_bytes(doc)

    path = tmp_path / "event.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "curation": {
                    "status": "ready",
                    "curator": "revision-test",
                    "curated_on": "2026-07-30",
                },
                "asset": {
                    "symbol": "REV",
                    "name": "Revision Token",
                    "coingecko_id": "revision-test-token",
                },
                "sources": [
                    {
                        "source_name": "revision_docs",
                        "source_uri": "fixture://revision",
                        "role": "primary",
                        "claims": ["schedule", "amount"],
                        "archived_path": f"data/raw/revision_docs/{checksum}.raw",
                        "checksum_sha256": checksum,
                        "retrieved_at": SEED_KNOWLEDGE.isoformat(),
                        "license_class": "public",
                        "excerpt": "1,000,000 REV unlocks 2026-06-16",
                    }
                ],
                "vesting_series": {
                    "series_slug": "rev-investor-monthly",
                    "name": "REV investor monthly vesting",
                    "cadence": "monthly",
                    "tranche_count": 24,
                },
                "event": {
                    "scheduled_at": "2026-06-16T00:00:00Z",
                    "release_type": "cliff",
                    "allocation_bucket": "investor",
                    "amount_tokens": "1000000",
                    "amount_provenance": "reported",
                    "tranche_number": 3,
                    "source_confidence": "unverified",
                },
                "checklist": dict.fromkeys(
                    [
                        "date_verified_from_primary",
                        "amount_reported_or_derivation_recorded",
                        "primary_source_archived_and_checksummed",
                        "secondary_cross_check_recorded",
                        "no_unresolved_source_conflicts",
                        "unknown_fields_left_null_not_guessed",
                    ],
                    True,
                ),
            }
        )
    )
    return path


def test_supersede_and_both_query_views(clean_db: Engine, tmp_path: Path) -> None:
    path = write_curation_file(tmp_path)
    revision_knowledge = SEED_KNOWLEDGE + timedelta(days=3)

    with make_session(clean_db) as session:
        seeded = seed_event(session, path, tmp_path)

        # Re-seeding is an idempotent no-op while a current version exists.
        assert seed_event(session, path, tmp_path).created_event is False

        corrected = UnlockEvent(
            event_version_id=event_version_uuid(
                seeded.logical_event_id, revision_knowledge.isoformat(), "990000"
            ),
            logical_event_id=seeded.logical_event_id,
            supersedes_version_id=seeded.event_version_id,
            asset_id=seeded.asset_id,
            scheduled_at=datetime(2026, 6, 16, tzinfo=UTC),
            event_kind=EventKind.SCHEDULED,
            release_type=ReleaseType.CLIFF,
            allocation_bucket=AllocationBucket.INVESTOR,
            amount_tokens=Decimal("990000"),
            amount_provenance=AmountProvenance.REPORTED,
            source_confidence=SourceConfidence.UNVERIFIED,
            knowledge_timestamp=revision_knowledge,
            valid_from=revision_knowledge,
            ambiguity_flags=["revision test correction"],
        )
        new_version_id = supersede_event_version(session, seeded.event_version_id, corrected)

        # Current state: exactly the corrected version.
        current = current_event_versions(session)
        assert [r.event_version_id for r in current] == [new_version_id]
        assert current[0].supersedes_version_id == seeded.event_version_id
        assert current[0].amount_tokens == Decimal("990000")

        # Point-in-time: before the correction was known, the old version.
        before = event_versions_as_of(session, SEED_KNOWLEDGE + timedelta(days=1))
        assert [r.event_version_id for r in before] == [seeded.event_version_id]
        assert before[0].amount_tokens == Decimal("1000000")

        # Point-in-time: after the correction, the new version.
        after = event_versions_as_of(session, revision_knowledge + timedelta(hours=1))
        assert [r.event_version_id for r in after] == [new_version_id]

        # Source lineage is carried onto the new version (copied by default).
        from meridian_pipelines.tables import UnlockEventSourceRow
        from sqlalchemy import func, select

        new_links = session.execute(
            select(func.count(UnlockEventSourceRow.source_artifact_id)).where(
                UnlockEventSourceRow.event_version_id == new_version_id,
                UnlockEventSourceRow.source_role == "primary",
            )
        ).scalar_one()
        assert new_links >= 1

        # SCD2 bookkeeping: the old row is closed, not rewritten.
        old_row = session.get(UnlockEventRow, seeded.event_version_id)
        assert old_row is not None
        assert old_row.valid_to == revision_knowledge
        assert old_row.amount_tokens == Decimal("1000000")

        # Superseding an already-superseded version is refused.
        with pytest.raises(RevisionError, match="already superseded"):
            supersede_event_version(session, seeded.event_version_id, corrected)

        # Unknown version id is refused.
        with pytest.raises(RevisionError, match="unknown event version"):
            supersede_event_version(session, uuid4(), corrected)
