"""Migration 0002: backfill correctness with pre-existing 0001-shaped data,
full downgrade, and the one-current-version invariant."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from meridian_pipelines.ids import asset_uuid, logical_event_uuid
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration

SCHEDULED = datetime(2026, 6, 16, 13, 0, tzinfo=UTC)
KNOWLEDGE = datetime(2026, 7, 30, tzinfo=UTC)


def _seed_0001_shaped_data(engine: Engine) -> tuple[object, object, object]:
    artifact_id, asset_id, event_id = uuid4(), asset_uuid("migration-test"), uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO source_artifact (id, source_name, retrieved_at, "
                "knowledge_timestamp, checksum_sha256, license_class, object_uri, metadata) "
                "VALUES (:id, 'migration_test_docs', :ts, :ts, :ck, 'public', "
                "'file:///dev/null', '{}'::jsonb)"
            ),
            {"id": artifact_id, "ts": KNOWLEDGE, "ck": "f" * 64},
        )
        conn.execute(
            text(
                "INSERT INTO asset (id, symbol, name, coingecko_id, valid_from) "
                "VALUES (:id, 'MIG', 'Migration Test', 'migration-test', :ts)"
            ),
            {"id": asset_id, "ts": KNOWLEDGE},
        )
        conn.execute(
            text(
                "INSERT INTO unlock_event (id, asset_id, scheduled_at, release_type, "
                "allocation_bucket, amount_tokens, source_artifact_id, source_confidence, "
                "knowledge_timestamp, valid_from, ambiguity_flags) "
                "VALUES (:id, :asset, :sched, 'cliff', 'investor', 1000, :artifact, "
                "'unverified', :kts, :kts, '[]'::jsonb)"
            ),
            {
                "id": event_id,
                "asset": asset_id,
                "sched": SCHEDULED,
                "artifact": artifact_id,
                "kts": KNOWLEDGE,
            },
        )
    return artifact_id, asset_id, event_id


def test_upgrade_backfills_identity_and_lineage_then_downgrades(clean_db: Engine) -> None:
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "0001")  # empty schema at head -> downgrade is data-safe
    artifact_id, asset_id, event_id = _seed_0001_shaped_data(clean_db)

    command.upgrade(cfg, "head")

    with clean_db.connect() as conn:
        row = conn.execute(
            text(
                "SELECT event_version_id, logical_event_id, event_kind, amount_provenance, "
                "derivation FROM unlock_event"
            )
        ).one()
        assert row.event_version_id == event_id  # rename preserved the value
        expected_logical = logical_event_uuid(
            asset_id, SCHEDULED.astimezone(UTC).isoformat(), "investor"
        )
        assert row.logical_event_id == expected_logical  # deterministic backfill
        assert row.event_kind == "scheduled"
        assert row.amount_provenance == "derived"
        assert "backfill" in row.derivation

        link = conn.execute(
            text(
                "SELECT event_version_id, source_artifact_id, source_role, claim_type "
                "FROM unlock_event_source"
            )
        ).one()
        assert link.event_version_id == event_id
        assert link.source_artifact_id == artifact_id
        assert link.source_role == "primary"
        assert link.claim_type == "other"

        columns = {c["name"] for c in inspect(conn).get_columns("unlock_event")}
        assert "source_artifact_id" not in columns
        assert {"logical_event_id", "supersedes_version_id", "vesting_series_id"} <= columns

    # Downgrade restores the 0001 shape including the single-source column.
    command.downgrade(cfg, "0001")
    with clean_db.connect() as conn:
        row = conn.execute(text("SELECT id, source_artifact_id FROM unlock_event")).one()
        assert row.id == event_id
        assert row.source_artifact_id == artifact_id
        columns = {c["name"] for c in inspect(conn).get_columns("unlock_event")}
        assert "logical_event_id" not in columns

    command.upgrade(cfg, "head")


def test_one_current_version_per_logical_event_enforced(clean_db: Engine) -> None:
    artifact_id, asset_id, event_id = uuid4(), asset_uuid("index-test"), uuid4()
    logical = uuid4()
    with clean_db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO source_artifact (id, source_name, retrieved_at, "
                "knowledge_timestamp, checksum_sha256, license_class, object_uri, metadata) "
                "VALUES (:id, 'index_test_docs', :ts, :ts, :ck, 'public', "
                "'file:///dev/null', '{}'::jsonb)"
            ),
            {"id": artifact_id, "ts": KNOWLEDGE, "ck": "e" * 64},
        )
        conn.execute(
            text(
                "INSERT INTO asset (id, symbol, name, coingecko_id, valid_from) "
                "VALUES (:id, 'IDX', 'Index Test', 'index-test', :ts)"
            ),
            {"id": asset_id, "ts": KNOWLEDGE},
        )
        conn.execute(
            text(
                "INSERT INTO unlock_event (event_version_id, logical_event_id, asset_id, "
                "scheduled_at, release_type, allocation_bucket, amount_tokens, "
                "amount_provenance, source_confidence, knowledge_timestamp, valid_from, "
                "ambiguity_flags) VALUES (:vid, :lid, :asset, :sched, 'cliff', 'investor', "
                "1000, 'reported', 'unverified', :kts, :kts, '[]'::jsonb)"
            ),
            {
                "vid": event_id,
                "lid": logical,
                "asset": asset_id,
                "sched": SCHEDULED,
                "kts": KNOWLEDGE,
            },
        )

    # A second *current* version of the same logical event must be impossible.
    with pytest.raises(IntegrityError, match="uq_unlock_event_one_current_version"):
        with clean_db.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO unlock_event (event_version_id, logical_event_id, asset_id, "
                    "scheduled_at, release_type, allocation_bucket, amount_tokens, "
                    "amount_provenance, source_confidence, knowledge_timestamp, valid_from, "
                    "ambiguity_flags) VALUES (:vid, :lid, :asset, :sched, 'cliff', 'investor', "
                    "990, 'reported', 'unverified', :kts, :kts, '[]'::jsonb)"
                ),
                {
                    "vid": uuid4(),
                    "lid": logical,
                    "asset": asset_id,
                    "sched": SCHEDULED,
                    "kts": KNOWLEDGE,
                },
            )
