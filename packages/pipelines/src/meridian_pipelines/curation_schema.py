"""Curation-file schema (template v2) and mechanical validation.

This is the curation-validity layer's first gate: structure, taxonomy,
provenance and checklist rules that can be checked without a database.
Archive integrity (checksums on disk) is checked by verify_source_archives.
Nothing here touches the network or fabricates values: unknown stays null.
"""

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import yaml
from meridian_domain.enums import (
    AllocationBucket,
    AmountProvenance,
    ClaimType,
    EventKind,
    LicenseClass,
    ReleaseType,
    SourceConfidence,
    SourceRole,
    VestingCadence,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

_CHECKSUM_PATTERN = r"^[0-9a-f]{64}$"
_SLUG_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"


class CurationFileError(Exception):
    """Curation file is missing, malformed, or violates a curation rule."""


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware (use e.g. 2026-08-04T00:00:00Z)")
    return value.astimezone(UTC)


class CurationMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["draft", "ready"]
    curator: str = Field(min_length=1)
    curated_on: date


class CurationAsset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(min_length=1)
    name: str = Field(min_length=1)
    chain_id: str | None = None
    contract_address: str | None = None
    decimals: int | None = Field(default=None, ge=0, le=36)
    coingecko_id: str = Field(min_length=1)


class CurationSource(BaseModel):
    """One source consulted during curation. Primary and on-chain sources must
    be archived; secondary cross-checks must record what they report and
    whether they agree."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_name: str = Field(pattern=_SLUG_PATTERN)
    source_uri: str = Field(min_length=1)
    role: SourceRole
    claims: list[ClaimType] = Field(min_length=1)
    archived_path: str | None = None
    checksum_sha256: str | None = Field(default=None, pattern=_CHECKSUM_PATTERN)
    retrieved_at: datetime | None = None
    license_class: LicenseClass
    redistributable: bool = False
    excerpt: str | None = None
    agrees: bool | None = None
    reports: str | None = None

    @field_validator("retrieved_at")
    @classmethod
    def _utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _require_utc(value)

    @model_validator(mode="after")
    def _role_rules(self) -> "CurationSource":
        archive_fields = (self.archived_path, self.checksum_sha256, self.retrieved_at)
        if any(f is not None for f in archive_fields) and not all(
            f is not None for f in archive_fields
        ):
            raise ValueError(
                f"source {self.source_name}: archived_path, checksum_sha256 and retrieved_at "
                "must be provided together"
            )
        if self.role in (SourceRole.PRIMARY, SourceRole.ONCHAIN_VERIFICATION):
            if self.archived_path is None:
                raise ValueError(
                    f"source {self.source_name}: role {self.role.value} requires an archived "
                    "snapshot (archived_path, checksum_sha256, retrieved_at)"
                )
            if not (self.excerpt and self.excerpt.strip()):
                raise ValueError(
                    f"source {self.source_name}: role {self.role.value} requires a supporting "
                    "excerpt or locator"
                )
        if self.role is SourceRole.SECONDARY_CROSS_CHECK:
            if self.agrees is None:
                raise ValueError(
                    f"source {self.source_name}: secondary_cross_check requires an explicit "
                    "agrees: true/false"
                )
            if not (self.reports and self.reports.strip()):
                raise ValueError(
                    f"source {self.source_name}: secondary_cross_check must record what the "
                    "source reports"
                )
        return self


class CurationSeries(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    series_slug: str = Field(pattern=_SLUG_PATTERN)
    name: str = Field(min_length=1)
    cadence: VestingCadence
    tranche_count: int | None = Field(default=None, ge=1)
    first_tranche_at: datetime | None = None
    last_tranche_at: datetime | None = None
    notes: str | None = None

    @field_validator("first_tranche_at", "last_tranche_at")
    @classmethod
    def _utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _require_utc(value)


class CurationBucketComponent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    bucket: AllocationBucket
    amount_tokens: Decimal | None = Field(default=None, gt=0)
    provenance: SourceRole
    note: str | None = None


class CurationEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_kind: EventKind = EventKind.SCHEDULED
    scheduled_at: datetime
    transferable_at: datetime | None = None
    release_type: ReleaseType
    allocation_bucket: AllocationBucket
    bucket_composition: list[CurationBucketComponent] | None = None
    amount_tokens: Decimal = Field(gt=0)
    amount_provenance: AmountProvenance
    derivation: str | None = None
    percent_total_supply: Decimal | None = Field(default=None, ge=0, le=100)
    percent_current_circulating: Decimal | None = Field(default=None, ge=0, le=100)
    tranche_number: int | None = Field(default=None, ge=1)
    source_confidence: SourceConfidence
    ambiguity_flags: list[str] = Field(default_factory=list)

    _utc = field_validator("scheduled_at")(_require_utc)

    @field_validator("transferable_at")
    @classmethod
    def _utc_optional(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _require_utc(value)

    @model_validator(mode="after")
    def _derived_requires_derivation(self) -> "CurationEvent":
        if self.amount_provenance is AmountProvenance.DERIVED and not (
            self.derivation and self.derivation.strip()
        ):
            raise ValueError("amount_provenance=derived requires a recorded derivation")
        return self


class CurationChecklist(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    date_verified_from_primary: bool
    amount_reported_or_derivation_recorded: bool
    primary_source_archived_and_checksummed: bool
    secondary_cross_check_recorded: bool
    no_unresolved_source_conflicts: bool
    unknown_fields_left_null_not_guessed: bool


class CurationFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[2]
    curation: CurationMeta
    asset: CurationAsset
    sources: list[CurationSource] = Field(min_length=1)
    vesting_series: CurationSeries | None = None
    event: CurationEvent
    checklist: CurationChecklist

    @model_validator(mode="after")
    def _file_rules(self) -> "CurationFile":
        primaries = [s for s in self.sources if s.role is SourceRole.PRIMARY]
        if not primaries:
            raise ValueError("at least one source with role=primary is required")

        verifying = [
            s
            for s in self.sources
            if s.role in (SourceRole.PRIMARY, SourceRole.ONCHAIN_VERIFICATION)
        ]
        for claim in (ClaimType.SCHEDULE, ClaimType.AMOUNT):
            if not any(claim in s.claims for s in verifying):
                raise ValueError(
                    f"claim '{claim.value}' must be backed by a primary or "
                    "onchain_verification source"
                )

        disagreeing = [s.source_name for s in self.sources if s.agrees is False]
        if disagreeing:
            raise ValueError(
                f"source(s) {disagreeing} disagree with the curated event; resolve the "
                "conflict or record the event in data/curated/exclusions.yaml instead"
            )

        if self.curation.status == "ready":
            unchecked = [k for k, v in self.checklist.model_dump().items() if v is not True]
            if unchecked:
                raise ValueError(
                    f"status=ready requires every checklist item true; false: {unchecked}"
                )

        if self.event.tranche_number is not None and self.vesting_series is None:
            raise ValueError("tranche_number requires a vesting_series section")
        if (
            self.vesting_series is not None
            and self.vesting_series.tranche_count is not None
            and self.event.tranche_number is not None
            and self.event.tranche_number > self.vesting_series.tranche_count
        ):
            raise ValueError("tranche_number exceeds the series tranche_count")
        return self


def parse_curation_file(path: Path) -> CurationFile:
    if not path.exists():
        raise CurationFileError(f"curated event file not found: {path}")
    data: Any = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise CurationFileError(f"curated event file is not a mapping: {path}")
    if data.get("schema_version") != 2:
        raise CurationFileError(
            f"{path}: schema_version must be 2 (see docs/curation/event-template.yaml)"
        )
    try:
        return CurationFile.model_validate(data)
    except ValidationError as exc:
        raise CurationFileError(f"{path}: {exc}") from exc


def verify_source_archives(curation: CurationFile, repo_root: Path) -> dict[str, Path]:
    """Re-hash every archived source; return checksum -> resolved path.

    Fails loudly on missing files or checksum mismatches. Sources without an
    archive (secondary cross-checks) are skipped."""
    verified: dict[str, Path] = {}
    for source in curation.sources:
        if source.archived_path is None or source.checksum_sha256 is None:
            continue
        candidate = Path(source.archived_path)
        resolved = candidate if candidate.is_absolute() else repo_root / candidate
        if not resolved.exists():
            raise CurationFileError(f"archived source missing for {source.source_name}: {resolved}")
        actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if actual != source.checksum_sha256:
            raise CurationFileError(
                f"archived source {resolved} checksum {actual} does not match curated "
                f"record {source.checksum_sha256}"
            )
        verified[source.checksum_sha256] = resolved
    return verified
