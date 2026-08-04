"""Epic 1 foundation: versioned event identity, multi-source lineage,
vesting series, supply observations.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-04

Upgrade backfills existing rows deterministically:
- logical_event_id = uuid5(namespace, "unlock-logical:{asset}:{scheduled}:{bucket}")
  (namespace duplicated from meridian_pipelines.ids by design: migrations must
  not import application code that can drift)
- the old single source_artifact_id link becomes an unlock_event_source row
  with role=primary, claim_type=other, and a migration locator excerpt
- amount_provenance backfills to 'derived' with an explicit backfill marker in
  derivation; the originating curated files remain the provenance record

Downgrade restores the 0001 shape. It requires every event version to have at
least one role=primary source link (fails loudly otherwise, because 0001's
source_artifact_id was NOT NULL).
"""

import uuid
from datetime import UTC

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Must match meridian_pipelines.ids._NAMESPACE (deliberate documented copy).
_NAMESPACE = uuid.UUID("a3f1c2d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d")

EVENT_KINDS = "'scheduled', 'observed_transfer', 'observed_exchange_deposit'"
AMOUNT_PROVENANCES = "'reported', 'derived'"
SOURCE_ROLES = "'primary', 'secondary_cross_check', 'onchain_verification'"
CLAIM_TYPES = "'schedule', 'amount', 'allocation', 'composition', 'supply', 'other'"
CADENCES = "'cliff', 'monthly', 'quarterly', 'continuous', 'irregular', 'unknown'"
SUPPLY_METHODS = "'reported', 'implied_market_cap'"

_BACKFILL_DERIVATION = (
    "migration-0002 backfill: provenance and derivation are recorded in the "
    "originating curated source file"
)


def _logical_event_id(asset_id: uuid.UUID, scheduled_at: object, bucket: str) -> uuid.UUID:
    scheduled_iso = scheduled_at.astimezone(UTC).isoformat()  # type: ignore[attr-defined]
    return uuid.uuid5(_NAMESPACE, f"unlock-logical:{asset_id}:{scheduled_iso}:{bucket}")


def upgrade() -> None:
    conn = op.get_bind()

    # --- versioned identity -------------------------------------------------
    op.alter_column("unlock_event", "id", new_column_name="event_version_id")

    op.create_table(
        "vesting_series",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("asset.id"), nullable=False),
        sa.Column("series_slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("cadence", sa.Text(), nullable=False),
        sa.Column("tranche_count", sa.Integer(), nullable=True),
        sa.Column("first_tranche_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_tranche_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("asset_id", "series_slug"),
        sa.CheckConstraint(f"cadence IN ({CADENCES})", name="ck_cadence_enum"),
        sa.CheckConstraint(
            "tranche_count IS NULL OR tranche_count >= 1", name="ck_tranche_count_positive"
        ),
    )

    op.add_column("unlock_event", sa.Column("logical_event_id", UUID(as_uuid=True), nullable=True))
    op.add_column(
        "unlock_event",
        sa.Column(
            "supersedes_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("unlock_event.event_version_id"),
            nullable=True,
        ),
    )
    op.add_column(
        "unlock_event",
        sa.Column("event_kind", sa.Text(), nullable=False, server_default="scheduled"),
    )
    op.add_column(
        "unlock_event",
        sa.Column("amount_provenance", sa.Text(), nullable=False, server_default="derived"),
    )
    op.add_column("unlock_event", sa.Column("derivation", sa.Text(), nullable=True))
    op.add_column("unlock_event", sa.Column("bucket_composition", JSONB, nullable=True))
    op.add_column(
        "unlock_event",
        sa.Column(
            "vesting_series_id",
            UUID(as_uuid=True),
            sa.ForeignKey("vesting_series.id"),
            nullable=True,
        ),
    )
    op.add_column("unlock_event", sa.Column("tranche_number", sa.Integer(), nullable=True))

    # Deterministic logical-id backfill for pre-existing rows.
    rows = conn.execute(
        sa.text("SELECT event_version_id, asset_id, scheduled_at, allocation_bucket FROM unlock_event")
    ).all()
    for version_id, asset_id, scheduled_at, bucket in rows:
        conn.execute(
            sa.text(
                "UPDATE unlock_event SET logical_event_id = :lid, derivation = :der "
                "WHERE event_version_id = :vid"
            ),
            {
                "lid": _logical_event_id(asset_id, scheduled_at, bucket),
                "der": _BACKFILL_DERIVATION,
                "vid": version_id,
            },
        )

    op.alter_column("unlock_event", "logical_event_id", nullable=False)
    op.create_check_constraint(
        "ck_event_kind_enum", "unlock_event", f"event_kind IN ({EVENT_KINDS})"
    )
    op.create_check_constraint(
        "ck_amount_provenance_enum",
        "unlock_event",
        f"amount_provenance IN ({AMOUNT_PROVENANCES})",
    )
    op.create_check_constraint(
        "ck_tranche_number_positive",
        "unlock_event",
        "tranche_number IS NULL OR tranche_number >= 1",
    )
    op.create_index(
        "uq_unlock_event_one_current_version",
        "unlock_event",
        ["logical_event_id"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )

    # --- multi-source lineage ----------------------------------------------
    op.create_table(
        "unlock_event_source",
        sa.Column(
            "event_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("unlock_event.event_version_id"),
            nullable=False,
        ),
        sa.Column(
            "source_artifact_id",
            UUID(as_uuid=True),
            sa.ForeignKey("source_artifact.id"),
            nullable=False,
        ),
        sa.Column("source_role", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.Text(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint(
            "event_version_id", "source_artifact_id", "source_role", "claim_type"
        ),
        sa.CheckConstraint(f"source_role IN ({SOURCE_ROLES})", name="ck_source_role_enum"),
        sa.CheckConstraint(f"claim_type IN ({CLAIM_TYPES})", name="ck_claim_type_enum"),
    )
    conn.execute(
        sa.text(
            "INSERT INTO unlock_event_source "
            "(event_version_id, source_artifact_id, source_role, claim_type, excerpt) "
            "SELECT event_version_id, source_artifact_id, 'primary', 'other', "
            "'migrated from single-source schema (migration 0001)' FROM unlock_event"
        )
    )
    op.drop_column("unlock_event", "source_artifact_id")

    # --- supply observations -------------------------------------------------
    op.create_table(
        "supply_observation",
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("asset.id"), nullable=False),
        sa.Column("ts", sa.Date(), nullable=False),
        sa.Column("circulating_supply", sa.Numeric(50, 18), nullable=True),
        sa.Column("total_supply", sa.Numeric(50, 18), nullable=True),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column(
            "source_artifact_id",
            UUID(as_uuid=True),
            sa.ForeignKey("source_artifact.id"),
            nullable=False,
        ),
        sa.Column("knowledge_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("asset_id", "ts", "source_artifact_id", "method"),
        sa.CheckConstraint(f"method IN ({SUPPLY_METHODS})", name="ck_supply_method_enum"),
        sa.CheckConstraint(
            "(circulating_supply IS NULL OR circulating_supply > 0) "
            "AND (total_supply IS NULL OR total_supply > 0)",
            name="ck_supply_positive",
        ),
        sa.CheckConstraint(
            "circulating_supply IS NOT NULL OR total_supply IS NOT NULL",
            name="ck_supply_at_least_one",
        ),
    )


def downgrade() -> None:
    conn = op.get_bind()

    op.drop_table("supply_observation")

    # Restore the single-source column from the association table (one primary
    # link per event required; 0001 declared the column NOT NULL).
    op.add_column(
        "unlock_event", sa.Column("source_artifact_id", UUID(as_uuid=True), nullable=True)
    )
    conn.execute(
        sa.text(
            "UPDATE unlock_event e SET source_artifact_id = ("
            "  SELECT s.source_artifact_id FROM unlock_event_source s"
            "  WHERE s.event_version_id = e.event_version_id AND s.source_role = 'primary'"
            "  ORDER BY s.claim_type, s.source_artifact_id LIMIT 1)"
        )
    )
    missing = conn.execute(
        sa.text("SELECT count(*) FROM unlock_event WHERE source_artifact_id IS NULL")
    ).scalar_one()
    if missing:
        raise RuntimeError(
            f"cannot downgrade: {missing} event version(s) lack a primary source link "
            "required by the 0001 NOT NULL source_artifact_id column"
        )
    op.alter_column("unlock_event", "source_artifact_id", nullable=False)
    op.create_foreign_key(
        "unlock_event_source_artifact_id_fkey",
        "unlock_event",
        "source_artifact",
        ["source_artifact_id"],
        ["id"],
    )
    op.drop_table("unlock_event_source")

    op.drop_index("uq_unlock_event_one_current_version", table_name="unlock_event")
    op.drop_constraint("ck_event_kind_enum", "unlock_event")
    op.drop_constraint("ck_amount_provenance_enum", "unlock_event")
    op.drop_constraint("ck_tranche_number_positive", "unlock_event")
    for column in (
        "tranche_number",
        "vesting_series_id",
        "bucket_composition",
        "derivation",
        "amount_provenance",
        "event_kind",
        "supersedes_version_id",
        "logical_event_id",
    ):
        op.drop_column("unlock_event", column)
    op.drop_table("vesting_series")

    op.alter_column("unlock_event", "event_version_id", new_column_name="id")
