"""Load a manually curated unlock event (YAML) plus its archived primary source.

The curated file references an already-archived primary source; loading
verifies the archived bytes still match the recorded checksum before any row
is written. Inserts use deterministic ids + ON CONFLICT DO NOTHING, so
re-running the loader is idempotent and never mutates existing rows
(corrections are append-only new records)."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import yaml
from meridian_connectors.archive import ArchiveIntegrityError, artifact_id
from meridian_domain.enums import AllocationBucket, LicenseClass, ReleaseType, SourceConfidence
from meridian_domain.models import SourceArtifactMeta, UnlockEvent
from sqlalchemy import CursorResult
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from meridian_pipelines.ids import asset_uuid, unlock_event_uuid
from meridian_pipelines.tables import AssetRow, SourceArtifactRow, UnlockEventRow


class CuratedEventError(Exception):
    pass


@dataclass(frozen=True)
class SeedResult:
    asset_id: UUID
    event_id: UUID
    source_artifact_id: UUID
    created_event: bool


def load_curated_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CuratedEventError(f"curated event file not found: {path}")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise CuratedEventError(f"curated event file is not a mapping: {path}")
    for key in ("asset", "primary_source", "event"):
        if key not in data:
            raise CuratedEventError(f"curated event file missing '{key}' section: {path}")
    return data


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise CuratedEventError(f"timestamp must carry a timezone: {value}")
    return parsed.astimezone(UTC)


def seed_event(session: Session, curated_path: Path, repo_root: Path) -> SeedResult:
    data = load_curated_file(curated_path)
    asset_cfg = data["asset"]
    source_cfg = data["primary_source"]
    event_cfg = data["event"]

    archived_path = repo_root / source_cfg["archived_path"]
    if not archived_path.exists():
        raise CuratedEventError(f"archived primary source missing: {archived_path}")
    actual_checksum = hashlib.sha256(archived_path.read_bytes()).hexdigest()
    if actual_checksum != source_cfg["checksum_sha256"]:
        raise ArchiveIntegrityError(
            f"archived source {archived_path} checksum {actual_checksum} does not match "
            f"curated record {source_cfg['checksum_sha256']}"
        )

    retrieved_at = _parse_utc(source_cfg["retrieved_at"])
    artifact = SourceArtifactMeta(
        id=artifact_id(source_cfg["source_name"], actual_checksum),
        source_name=source_cfg["source_name"],
        source_uri=source_cfg.get("source_uri"),
        retrieved_at=retrieved_at,
        knowledge_timestamp=retrieved_at,
        checksum_sha256=actual_checksum,
        license_class=LicenseClass(source_cfg["license_class"]),
        object_uri=archived_path.resolve().as_uri(),
        metadata={"verification": data.get("verification", {})},
    )

    asset_id = asset_uuid(asset_cfg["coingecko_id"])
    scheduled_at = _parse_utc(event_cfg["scheduled_at"])
    amount = Decimal(str(event_cfg["amount_tokens"]))
    event = UnlockEvent(
        id=unlock_event_uuid(
            asset_id,
            scheduled_at.isoformat(),
            event_cfg["allocation_bucket"],
            str(amount),
        ),
        asset_id=asset_id,
        scheduled_at=scheduled_at,
        transferable_at=(
            _parse_utc(event_cfg["transferable_at"]) if event_cfg.get("transferable_at") else None
        ),
        release_type=ReleaseType(event_cfg["release_type"]),
        allocation_bucket=AllocationBucket(event_cfg["allocation_bucket"]),
        amount_tokens=amount,
        percent_current_circulating=_optional_decimal(event_cfg, "percent_current_circulating"),
        percent_total_supply=_optional_decimal(event_cfg, "percent_total_supply"),
        source_artifact_id=artifact.id,
        source_confidence=SourceConfidence(event_cfg["source_confidence"]),
        knowledge_timestamp=retrieved_at,
        valid_from=retrieved_at,
        ambiguity_flags=list(event_cfg.get("ambiguity_flags", [])),
    )

    _insert_artifact(session, artifact)
    _insert_asset(session, asset_id, asset_cfg, retrieved_at)
    created = _insert_event(session, event)
    session.commit()
    return SeedResult(
        asset_id=asset_id,
        event_id=event.id,
        source_artifact_id=artifact.id,
        created_event=created,
    )


def _optional_decimal(cfg: dict[str, Any], key: str) -> Decimal | None:
    value = cfg.get(key)
    return None if value is None else Decimal(str(value))


def _insert_artifact(session: Session, artifact: SourceArtifactMeta) -> None:
    stmt = (
        insert(SourceArtifactRow)
        .values(
            id=artifact.id,
            source_name=artifact.source_name,
            source_uri=artifact.source_uri,
            retrieved_at=artifact.retrieved_at,
            knowledge_timestamp=artifact.knowledge_timestamp,
            checksum_sha256=artifact.checksum_sha256,
            license_class=artifact.license_class.value,
            object_uri=artifact.object_uri,
            metadata=artifact.metadata,
        )
        .on_conflict_do_nothing()
    )
    session.execute(stmt)


def _insert_asset(
    session: Session, asset_id: UUID, asset_cfg: dict[str, Any], valid_from: datetime
) -> None:
    stmt = (
        insert(AssetRow)
        .values(
            id=asset_id,
            symbol=asset_cfg["symbol"],
            name=asset_cfg["name"],
            chain_id=asset_cfg.get("chain_id"),
            contract_address=asset_cfg.get("contract_address"),
            decimals=asset_cfg.get("decimals"),
            coingecko_id=asset_cfg["coingecko_id"],
            valid_from=valid_from,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    session.execute(stmt)


def _insert_event(session: Session, event: UnlockEvent) -> bool:
    stmt = (
        insert(UnlockEventRow)
        .values(
            id=event.id,
            asset_id=event.asset_id,
            scheduled_at=event.scheduled_at,
            transferable_at=event.transferable_at,
            release_type=event.release_type.value,
            allocation_bucket=event.allocation_bucket.value,
            amount_tokens=event.amount_tokens,
            percent_current_circulating=event.percent_current_circulating,
            percent_total_supply=event.percent_total_supply,
            source_artifact_id=event.source_artifact_id,
            source_confidence=event.source_confidence.value,
            knowledge_timestamp=event.knowledge_timestamp,
            valid_from=event.valid_from,
            ambiguity_flags=event.ambiguity_flags,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    result = cast(CursorResult[Any], session.execute(stmt))
    return bool(result.rowcount)
