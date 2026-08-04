"""Canonical domain models.

Invariants enforced here (not in the database) so every entry path shares them:
- all datetimes are timezone-aware UTC,
- token quantities and prices are Decimals and non-negative where required,
- point-in-time fields (knowledge_timestamp) are mandatory.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from meridian_domain.enums import (
    AllocationBucket,
    AmountProvenance,
    ClaimType,
    EventKind,
    LicenseClass,
    ReleaseType,
    SourceConfidence,
    SourceRole,
    SupplyMethod,
    VestingCadence,
)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


class SourceArtifactMeta(BaseModel):
    """Metadata for an immutable raw payload archived outside the database."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    source_name: str = Field(min_length=1)
    source_uri: str | None = None
    retrieved_at: datetime
    knowledge_timestamp: datetime
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    license_class: LicenseClass
    object_uri: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    _utc = field_validator("retrieved_at", "knowledge_timestamp")(_require_utc)


class Asset(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    symbol: str = Field(min_length=1)
    name: str = Field(min_length=1)
    chain_id: str | None = None
    contract_address: str | None = None
    decimals: int | None = Field(default=None, ge=0, le=36)
    coingecko_id: str | None = None
    valid_from: datetime
    valid_to: datetime | None = None

    _utc = field_validator("valid_from")(_require_utc)


class BucketComponent(BaseModel):
    """One constituent of an unsplit combined tranche (allocation_bucket=unknown)."""

    model_config = ConfigDict(frozen=True)

    bucket: AllocationBucket
    amount_tokens: Decimal | None = Field(default=None, gt=0)
    provenance: SourceRole
    note: str | None = None


class VestingSeries(BaseModel):
    """A vesting schedule whose tranches share a stable identity."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    asset_id: UUID
    series_slug: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1)
    cadence: VestingCadence
    tranche_count: int | None = Field(default=None, ge=1)
    first_tranche_at: datetime | None = None
    last_tranche_at: datetime | None = None
    notes: str | None = None

    @field_validator("first_tranche_at", "last_tranche_at")
    @classmethod
    def _utc_optional(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _require_utc(value)


class UnlockEvent(BaseModel):
    """One *version* of a canonical unlock event (SCD2).

    logical_event_id is stable across revisions; event_version_id is unique
    per version; supersedes_version_id chains corrections. Sources are linked
    through UnlockEventSource records, never a single artifact FK."""

    model_config = ConfigDict(frozen=True)

    event_version_id: UUID
    logical_event_id: UUID
    supersedes_version_id: UUID | None = None
    asset_id: UUID
    scheduled_at: datetime
    transferable_at: datetime | None = None
    event_kind: EventKind = EventKind.SCHEDULED
    release_type: ReleaseType
    allocation_bucket: AllocationBucket
    bucket_composition: list[BucketComponent] | None = None
    amount_tokens: Decimal = Field(gt=0)
    amount_provenance: AmountProvenance
    derivation: str | None = None
    percent_current_circulating: Decimal | None = Field(default=None, ge=0, le=100)
    percent_total_supply: Decimal | None = Field(default=None, ge=0, le=100)
    vesting_series_id: UUID | None = None
    tranche_number: int | None = Field(default=None, ge=1)
    source_confidence: SourceConfidence
    knowledge_timestamp: datetime
    valid_from: datetime
    valid_to: datetime | None = None
    ambiguity_flags: list[str] = Field(default_factory=list)

    _utc = field_validator("scheduled_at", "knowledge_timestamp", "valid_from")(_require_utc)

    @model_validator(mode="after")
    def _derived_requires_derivation(self) -> "UnlockEvent":
        if self.amount_provenance is AmountProvenance.DERIVED and not (
            self.derivation and self.derivation.strip()
        ):
            raise ValueError("amount_provenance=derived requires a recorded derivation")
        return self

    @property
    def event_day_utc(self) -> date:
        """Day 0 of the event window: the UTC calendar date of the unlock."""
        return self.scheduled_at.astimezone(UTC).date()


class UnlockEventSource(BaseModel):
    """Link between one event version and one archived artifact for one claim."""

    model_config = ConfigDict(frozen=True)

    event_version_id: UUID
    source_artifact_id: UUID
    source_role: SourceRole
    claim_type: ClaimType
    excerpt: str | None = None


class SupplyObservation(BaseModel):
    """Point-in-time supply for one asset/date, with method and lineage."""

    model_config = ConfigDict(frozen=True)

    asset_id: UUID
    ts: date
    circulating_supply: Decimal | None = Field(default=None, gt=0)
    total_supply: Decimal | None = Field(default=None, gt=0)
    method: SupplyMethod
    source_artifact_id: UUID
    knowledge_timestamp: datetime

    _utc = field_validator("knowledge_timestamp")(_require_utc)

    @model_validator(mode="after")
    def _at_least_one_supply(self) -> "SupplyObservation":
        if self.circulating_supply is None and self.total_supply is None:
            raise ValueError("at least one of circulating_supply/total_supply is required")
        return self


class MarketBar(BaseModel):
    """One daily observation. CoinGecko supplies daily price points, not OHLC,
    so open/high/low may be absent while close is required."""

    model_config = ConfigDict(frozen=True)

    asset_id: UUID
    ts: date
    open: Decimal | None = Field(default=None, ge=0)
    high: Decimal | None = Field(default=None, ge=0)
    low: Decimal | None = Field(default=None, ge=0)
    close: Decimal = Field(gt=0)
    volume_usd: Decimal | None = Field(default=None, ge=0)
    market_cap_usd: Decimal | None = Field(default=None, ge=0)
    quote_currency: str = "usd"
    source_artifact_id: UUID
    knowledge_timestamp: datetime

    _utc = field_validator("knowledge_timestamp")(_require_utc)

    @model_validator(mode="after")
    def _ohlc_consistent(self) -> "MarketBar":
        if self.high is not None and self.low is not None and self.high < self.low:
            raise ValueError("high must be >= low")
        return self
