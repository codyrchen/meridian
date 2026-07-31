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

from meridian_domain.enums import AllocationBucket, LicenseClass, ReleaseType, SourceConfidence


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


class UnlockEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    asset_id: UUID
    scheduled_at: datetime
    transferable_at: datetime | None = None
    release_type: ReleaseType
    allocation_bucket: AllocationBucket
    amount_tokens: Decimal = Field(gt=0)
    percent_current_circulating: Decimal | None = Field(default=None, ge=0, le=100)
    percent_total_supply: Decimal | None = Field(default=None, ge=0, le=100)
    source_artifact_id: UUID
    source_confidence: SourceConfidence
    knowledge_timestamp: datetime
    valid_from: datetime
    valid_to: datetime | None = None
    ambiguity_flags: list[str] = Field(default_factory=list)

    _utc = field_validator("scheduled_at", "knowledge_timestamp", "valid_from")(_require_utc)

    @property
    def event_day_utc(self) -> date:
        """Day 0 of the event window: the UTC calendar date of the unlock."""
        return self.scheduled_at.astimezone(UTC).date()


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
