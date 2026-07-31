"""Initial canonical schema: source_artifact, asset, unlock_event, market_bar_daily.

Revision ID: 0001
Revises:
Create Date: 2026-07-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

RELEASE_TYPES = "'cliff', 'linear', 'emission', 'milestone', 'governance', 'unknown'"
ALLOCATION_BUCKETS = (
    "'team', 'investor', 'foundation', 'community', 'ecosystem', "
    "'treasury', 'airdrop', 'rewards', 'unknown'"
)
SOURCE_CONFIDENCES = "'verified_primary', 'verified_secondary', 'unverified'"


def upgrade() -> None:
    op.create_table(
        "source_artifact",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("knowledge_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checksum_sha256", sa.Text(), nullable=False),
        sa.Column("license_class", sa.Text(), nullable=False),
        sa.Column("object_uri", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("source_name", "checksum_sha256"),
    )
    op.create_table(
        "asset",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("chain_id", sa.Text(), nullable=True),
        sa.Column("contract_address", sa.Text(), nullable=True),
        sa.Column("decimals", sa.Integer(), nullable=True),
        sa.Column("coingecko_id", sa.Text(), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("chain_id", "contract_address", "valid_from"),
    )
    op.create_table(
        "unlock_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("asset.id"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("transferable_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_type", sa.Text(), nullable=False),
        sa.Column("allocation_bucket", sa.Text(), nullable=False),
        sa.Column("amount_tokens", sa.Numeric(50, 18), nullable=False),
        sa.Column("percent_current_circulating", sa.Numeric(20, 10), nullable=True),
        sa.Column("percent_total_supply", sa.Numeric(20, 10), nullable=True),
        sa.Column(
            "source_artifact_id",
            UUID(as_uuid=True),
            sa.ForeignKey("source_artifact.id"),
            nullable=False,
        ),
        sa.Column("source_confidence", sa.Text(), nullable=False),
        sa.Column("knowledge_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "ambiguity_flags", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.CheckConstraint(f"release_type IN ({RELEASE_TYPES})", name="ck_release_type_enum"),
        sa.CheckConstraint(
            f"allocation_bucket IN ({ALLOCATION_BUCKETS})", name="ck_allocation_bucket_enum"
        ),
        sa.CheckConstraint(
            f"source_confidence IN ({SOURCE_CONFIDENCES})", name="ck_source_confidence_enum"
        ),
        sa.CheckConstraint("amount_tokens > 0", name="ck_amount_tokens_positive"),
    )
    op.create_table(
        "market_bar_daily",
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("asset.id"), nullable=False),
        sa.Column("ts", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(30, 12), nullable=True),
        sa.Column("high", sa.Numeric(30, 12), nullable=True),
        sa.Column("low", sa.Numeric(30, 12), nullable=True),
        sa.Column("close", sa.Numeric(30, 12), nullable=False),
        sa.Column("volume_usd", sa.Numeric(40, 8), nullable=True),
        sa.Column("market_cap_usd", sa.Numeric(40, 8), nullable=True),
        sa.Column("quote_currency", sa.Text(), nullable=False, server_default="usd"),
        sa.Column(
            "source_artifact_id",
            UUID(as_uuid=True),
            sa.ForeignKey("source_artifact.id"),
            nullable=False,
        ),
        sa.Column("knowledge_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("asset_id", "ts", "source_artifact_id"),
        sa.CheckConstraint(
            "(open IS NULL OR open >= 0) AND (high IS NULL OR high >= 0) "
            "AND (low IS NULL OR low >= 0) AND close > 0",
            name="ck_prices_nonnegative",
        ),
        sa.CheckConstraint(
            "(volume_usd IS NULL OR volume_usd >= 0) "
            "AND (market_cap_usd IS NULL OR market_cap_usd >= 0)",
            name="ck_volumes_nonnegative",
        ),
    )


def downgrade() -> None:
    op.drop_table("market_bar_daily")
    op.drop_table("unlock_event")
    op.drop_table("asset")
    op.drop_table("source_artifact")
