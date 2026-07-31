"""SQLAlchemy 2 table definitions. Canonical naming follows sql/initial_schema.sql
with corrections recorded in docs/decision-log.md (quote_currency, enum CHECKs)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from meridian_domain.enums import AllocationBucket, ReleaseType, SourceConfidence
from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import DateTime


def _enum_check(column: str, values: type[Any]) -> CheckConstraint:
    quoted = ", ".join(f"'{v.value}'" for v in values)
    return CheckConstraint(f"{column} IN ({quoted})", name=f"ck_{column}_enum")


class Base(DeclarativeBase):
    type_annotation_map = {  # noqa: RUF012 - SQLAlchemy declarative config, not instance state
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
        list[str]: JSONB,
    }


class SourceArtifactRow(Base):
    __tablename__ = "source_artifact"
    __table_args__ = (UniqueConstraint("source_name", "checksum_sha256"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(Text)
    source_uri: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime]
    knowledge_timestamp: Mapped[datetime]
    checksum_sha256: Mapped[str] = mapped_column(Text)
    license_class: Mapped[str] = mapped_column(Text)
    object_uri: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class AssetRow(Base):
    __tablename__ = "asset"
    __table_args__ = (UniqueConstraint("chain_id", "contract_address", "valid_from"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    chain_id: Mapped[str | None] = mapped_column(Text)
    contract_address: Mapped[str | None] = mapped_column(Text)
    decimals: Mapped[int | None] = mapped_column(Integer)
    coingecko_id: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[datetime]
    valid_to: Mapped[datetime | None]


class UnlockEventRow(Base):
    __tablename__ = "unlock_event"
    __table_args__ = (
        _enum_check("release_type", ReleaseType),
        _enum_check("allocation_bucket", AllocationBucket),
        _enum_check("source_confidence", SourceConfidence),
        CheckConstraint("amount_tokens > 0", name="ck_amount_tokens_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    asset_id: Mapped[UUID] = mapped_column(ForeignKey("asset.id"))
    scheduled_at: Mapped[datetime]
    transferable_at: Mapped[datetime | None]
    release_type: Mapped[str] = mapped_column(Text)
    allocation_bucket: Mapped[str] = mapped_column(Text)
    amount_tokens: Mapped[Decimal] = mapped_column(Numeric(50, 18))
    percent_current_circulating: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    percent_total_supply: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    source_artifact_id: Mapped[UUID] = mapped_column(ForeignKey("source_artifact.id"))
    source_confidence: Mapped[str] = mapped_column(Text)
    knowledge_timestamp: Mapped[datetime]
    valid_from: Mapped[datetime]
    valid_to: Mapped[datetime | None]
    ambiguity_flags: Mapped[list[str]] = mapped_column(JSONB, default=list)


class MarketBarDailyRow(Base):
    __tablename__ = "market_bar_daily"
    __table_args__ = (
        PrimaryKeyConstraint("asset_id", "ts", "source_artifact_id"),
        CheckConstraint(
            "(open IS NULL OR open >= 0) AND (high IS NULL OR high >= 0) "
            "AND (low IS NULL OR low >= 0) AND close > 0",
            name="ck_prices_nonnegative",
        ),
        CheckConstraint(
            "(volume_usd IS NULL OR volume_usd >= 0) "
            "AND (market_cap_usd IS NULL OR market_cap_usd >= 0)",
            name="ck_volumes_nonnegative",
        ),
    )

    asset_id: Mapped[UUID] = mapped_column(ForeignKey("asset.id"))
    ts: Mapped[date] = mapped_column(Date)
    open: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    high: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    low: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    close: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    volume_usd: Mapped[Decimal | None] = mapped_column(Numeric(40, 8))
    market_cap_usd: Mapped[Decimal | None] = mapped_column(Numeric(40, 8))
    quote_currency: Mapped[str] = mapped_column(Text, default="usd", server_default="usd")
    source_artifact_id: Mapped[UUID] = mapped_column(ForeignKey("source_artifact.id"))
    knowledge_timestamp: Mapped[datetime]
