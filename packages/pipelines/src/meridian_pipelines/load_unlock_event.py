"""Load a manually curated unlock event (template v2) plus its archived sources.

Every archived source is re-hashed against its recorded checksum before any
row is written. Inserts use deterministic ids + ON CONFLICT DO NOTHING against
the one-current-version-per-logical-event partial index, so re-running the
loader is an idempotent no-op and never mutates existing rows. Revisions are
a deliberate operation (meridian_pipelines.event_versions.supersede_event_version),
never a side effect of seeding.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast
from uuid import UUID

from meridian_connectors.archive import artifact_id
from meridian_domain.models import BucketComponent, SourceArtifactMeta, UnlockEvent
from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from meridian_pipelines.curation_schema import (
    CurationFile,
    CurationFileError,
    CurationSource,
    parse_curation_file,
    verify_source_archives,
)
from meridian_pipelines.ids import (
    asset_uuid,
    event_version_uuid,
    logical_event_uuid,
    vesting_series_uuid,
)
from meridian_pipelines.tables import (
    AssetRow,
    SourceArtifactRow,
    UnlockEventRow,
    UnlockEventSourceRow,
    VestingSeriesRow,
)

# Backwards-compatible name: curation errors surface under the same exception.
CuratedEventError = CurationFileError

# Declarative __table__ is typed FromClause; cast once for typed Core inserts.
_ASSET_TABLE = cast(Table, AssetRow.__table__)
_SOURCE_ARTIFACT_TABLE = cast(Table, SourceArtifactRow.__table__)
_UNLOCK_EVENT_TABLE = cast(Table, UnlockEventRow.__table__)
_EVENT_SOURCE_TABLE = cast(Table, UnlockEventSourceRow.__table__)
_VESTING_SERIES_TABLE = cast(Table, VestingSeriesRow.__table__)


@dataclass(frozen=True)
class SeedResult:
    asset_id: UUID
    logical_event_id: UUID
    event_version_id: UUID
    vesting_series_id: UUID | None
    source_artifact_ids: tuple[UUID, ...]
    source_link_count: int
    created_event: bool


def load_curated_file(path: Path) -> CurationFile:
    """Parse and mechanically validate a template-v2 curation file."""
    return parse_curation_file(path)


def seed_event(session: Session, curated_path: Path, repo_root: Path) -> SeedResult:
    curation = load_curated_file(curated_path)
    if curation.curation.status != "ready":
        raise CuratedEventError(
            f"{curated_path}: curation.status must be 'ready' before seeding "
            f"(found '{curation.curation.status}')"
        )
    archives = verify_source_archives(curation, repo_root)

    artifacts = _build_artifacts(curation, archives)
    knowledge_timestamp = max(a.retrieved_at for a in artifacts.values())

    asset_id = asset_uuid(curation.asset.coingecko_id)
    for artifact in artifacts.values():
        _insert_artifact(session, artifact)
    _insert_asset(session, asset_id, curation, knowledge_timestamp)
    # Series references the asset, the event references both: insert in order.
    series_id = _seed_series(session, curation, asset_id)
    event = _build_event(curation, asset_id, series_id, knowledge_timestamp)
    created = _insert_event(session, event)
    link_count = _insert_source_links(session, curation, event.event_version_id, artifacts)
    session.commit()
    return SeedResult(
        asset_id=asset_id,
        logical_event_id=event.logical_event_id,
        event_version_id=event.event_version_id,
        vesting_series_id=series_id,
        source_artifact_ids=tuple(a.id for a in artifacts.values()),
        source_link_count=link_count,
        created_event=created,
    )


def _build_artifacts(
    curation: CurationFile, archives: dict[str, Path]
) -> dict[str, SourceArtifactMeta]:
    """One artifact per archived source, keyed by checksum."""
    artifacts: dict[str, SourceArtifactMeta] = {}
    for source in curation.sources:
        if source.checksum_sha256 is None or source.retrieved_at is None:
            continue  # secondary cross-check without an archive: metadata-only
        artifacts[source.checksum_sha256] = SourceArtifactMeta(
            id=artifact_id(source.source_name, source.checksum_sha256),
            source_name=source.source_name,
            source_uri=source.source_uri,
            retrieved_at=source.retrieved_at,
            knowledge_timestamp=source.retrieved_at,
            checksum_sha256=source.checksum_sha256,
            license_class=source.license_class,
            object_uri=archives[source.checksum_sha256].resolve().as_uri(),
            metadata={
                "role": source.role.value,
                "claims": [c.value for c in source.claims],
                "redistributable": source.redistributable,
            },
        )
    return artifacts


def _build_event(
    curation: CurationFile,
    asset_id: UUID,
    series_id: UUID | None,
    knowledge_timestamp: datetime,
) -> UnlockEvent:
    spec = curation.event
    logical_id = logical_event_uuid(
        asset_id, spec.scheduled_at.isoformat(), spec.allocation_bucket.value
    )
    version_id = event_version_uuid(
        logical_id, knowledge_timestamp.isoformat(), str(spec.amount_tokens)
    )
    composition = (
        None
        if spec.bucket_composition is None
        else [BucketComponent(**c.model_dump()) for c in spec.bucket_composition]
    )
    return UnlockEvent(
        event_version_id=version_id,
        logical_event_id=logical_id,
        asset_id=asset_id,
        scheduled_at=spec.scheduled_at,
        transferable_at=spec.transferable_at,
        event_kind=spec.event_kind,
        release_type=spec.release_type,
        allocation_bucket=spec.allocation_bucket,
        bucket_composition=composition,
        amount_tokens=spec.amount_tokens,
        amount_provenance=spec.amount_provenance,
        derivation=spec.derivation,
        percent_current_circulating=spec.percent_current_circulating,
        percent_total_supply=spec.percent_total_supply,
        vesting_series_id=series_id,
        tranche_number=spec.tranche_number,
        source_confidence=spec.source_confidence,
        knowledge_timestamp=knowledge_timestamp,
        valid_from=knowledge_timestamp,
        ambiguity_flags=list(spec.ambiguity_flags),
    )


def _seed_series(session: Session, curation: CurationFile, asset_id: UUID) -> UUID | None:
    series = curation.vesting_series
    if series is None:
        return None
    series_id = vesting_series_uuid(asset_id, series.series_slug)
    stmt = (
        insert(_VESTING_SERIES_TABLE)
        .values(
            id=series_id,
            asset_id=asset_id,
            series_slug=series.series_slug,
            name=series.name,
            cadence=series.cadence.value,
            tranche_count=series.tranche_count,
            first_tranche_at=series.first_tranche_at,
            last_tranche_at=series.last_tranche_at,
            notes=series.notes,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    session.execute(stmt)
    return series_id


def _insert_artifact(session: Session, artifact: SourceArtifactMeta) -> None:
    stmt = (
        insert(_SOURCE_ARTIFACT_TABLE)
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
    session: Session, asset_id: UUID, curation: CurationFile, valid_from: datetime
) -> None:
    asset = curation.asset
    stmt = (
        insert(_ASSET_TABLE)
        .values(
            id=asset_id,
            symbol=asset.symbol,
            name=asset.name,
            chain_id=asset.chain_id,
            contract_address=asset.contract_address,
            decimals=asset.decimals,
            coingecko_id=asset.coingecko_id,
            valid_from=valid_from,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    session.execute(stmt)


def _insert_event(session: Session, event: UnlockEvent) -> bool:
    stmt = (
        insert(_UNLOCK_EVENT_TABLE)
        .values(
            event_version_id=event.event_version_id,
            logical_event_id=event.logical_event_id,
            supersedes_version_id=event.supersedes_version_id,
            asset_id=event.asset_id,
            scheduled_at=event.scheduled_at,
            transferable_at=event.transferable_at,
            event_kind=event.event_kind.value,
            release_type=event.release_type.value,
            allocation_bucket=event.allocation_bucket.value,
            bucket_composition=(
                None
                if event.bucket_composition is None
                else [c.model_dump(mode="json") for c in event.bucket_composition]
            ),
            amount_tokens=event.amount_tokens,
            amount_provenance=event.amount_provenance.value,
            derivation=event.derivation,
            percent_current_circulating=event.percent_current_circulating,
            percent_total_supply=event.percent_total_supply,
            vesting_series_id=event.vesting_series_id,
            tranche_number=event.tranche_number,
            source_confidence=event.source_confidence.value,
            knowledge_timestamp=event.knowledge_timestamp,
            valid_from=event.valid_from,
            ambiguity_flags=event.ambiguity_flags,
        )
        # Conflict target: the partial unique index enforcing one current
        # version per logical event. Seeding never auto-revises; while a
        # current version exists, re-seeding is a no-op. RETURNING makes the
        # created/no-op distinction exact.
        .on_conflict_do_nothing(
            index_elements=["logical_event_id"],
            index_where=_UNLOCK_EVENT_TABLE.c.valid_to.is_(None),
        )
        .returning(_UNLOCK_EVENT_TABLE.c.event_version_id)
    )
    return session.execute(stmt).first() is not None


def _insert_source_links(
    session: Session,
    curation: CurationFile,
    event_version_id: UUID,
    artifacts: dict[str, SourceArtifactMeta],
) -> int:
    linked = 0
    for source in curation.sources:
        if source.checksum_sha256 is None:
            continue
        artifact = artifacts[source.checksum_sha256]
        for claim in source.claims:
            stmt = (
                insert(_EVENT_SOURCE_TABLE)
                .values(
                    event_version_id=event_version_id,
                    source_artifact_id=artifact.id,
                    source_role=source.role.value,
                    claim_type=claim.value,
                    excerpt=_link_excerpt(source),
                )
                .on_conflict_do_nothing()
            )
            session.execute(stmt)
            linked += 1
    return linked


def _link_excerpt(source: CurationSource) -> str | None:
    if source.excerpt:
        return source.excerpt
    return source.reports
