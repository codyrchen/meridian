"""Versioned event queries and the deliberate revision operation.

SCD2 semantics: every row is one version; the single permitted UPDATE is
closing the superseded version's valid_to at revision time. Nothing is ever
deleted or rewritten.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import cast
from uuid import UUID

from meridian_domain.models import UnlockEvent, UnlockEventSource
from sqlalchemy import Table, literal, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from meridian_pipelines.tables import UnlockEventRow, UnlockEventSourceRow

_UNLOCK_EVENT_TABLE = cast(Table, UnlockEventRow.__table__)
_EVENT_SOURCE_TABLE = cast(Table, UnlockEventSourceRow.__table__)


class RevisionError(Exception):
    pass


def current_event_versions(session: Session, asset_id: UUID | None = None) -> list[UnlockEventRow]:
    """Current state: the one version per logical event with valid_to IS NULL."""
    stmt = select(UnlockEventRow).where(UnlockEventRow.valid_to.is_(None))
    if asset_id is not None:
        stmt = stmt.where(UnlockEventRow.asset_id == asset_id)
    stmt = stmt.order_by(UnlockEventRow.scheduled_at, UnlockEventRow.logical_event_id)
    return list(session.execute(stmt).scalars())


def event_versions_as_of(
    session: Session, as_of: datetime, asset_id: UUID | None = None
) -> list[UnlockEventRow]:
    """Point-in-time state: for each logical event, the latest version whose
    knowledge_timestamp <= as_of. Versions learned later are invisible, which
    is exactly the look-ahead guarantee research code relies on."""
    stmt = select(UnlockEventRow).where(UnlockEventRow.knowledge_timestamp <= as_of)
    if asset_id is not None:
        stmt = stmt.where(UnlockEventRow.asset_id == asset_id)
    best: dict[UUID, UnlockEventRow] = {}
    for row in session.execute(stmt).scalars():
        incumbent = best.get(row.logical_event_id)
        if incumbent is None or row.knowledge_timestamp > incumbent.knowledge_timestamp:
            best[row.logical_event_id] = row
    return sorted(best.values(), key=lambda r: (r.scheduled_at, r.logical_event_id))


def supersede_event_version(
    session: Session,
    old_version_id: UUID,
    new_event: UnlockEvent,
    source_links: Sequence[UnlockEventSource] | None = None,
) -> UUID:
    """Replace the current version of a logical event with a corrected one.

    The old version's valid_to is closed at the new version's valid_from; the
    new version records supersedes_version_id. Both rows remain queryable.

    Source lineage: pass source_links when the revision rests on new sources;
    otherwise the superseded version's links are copied, because every version
    must keep at least one primary source link."""
    old = session.get(UnlockEventRow, old_version_id)
    if old is None:
        raise RevisionError(f"unknown event version: {old_version_id}")
    if old.valid_to is not None:
        raise RevisionError(
            f"version {old_version_id} is already superseded (valid_to={old.valid_to})"
        )
    if new_event.logical_event_id != old.logical_event_id:
        raise RevisionError(
            "revision must keep the same logical_event_id "
            f"({new_event.logical_event_id} != {old.logical_event_id})"
        )
    if new_event.supersedes_version_id != old_version_id:
        raise RevisionError("new version must set supersedes_version_id to the old version id")
    if new_event.knowledge_timestamp <= old.knowledge_timestamp:
        raise RevisionError("revision knowledge_timestamp must move forward")

    session.execute(
        update(_UNLOCK_EVENT_TABLE)
        .where(_UNLOCK_EVENT_TABLE.c.event_version_id == old_version_id)
        .values(valid_to=new_event.valid_from)
    )
    stmt = insert(_UNLOCK_EVENT_TABLE).values(
        event_version_id=new_event.event_version_id,
        logical_event_id=new_event.logical_event_id,
        supersedes_version_id=new_event.supersedes_version_id,
        asset_id=new_event.asset_id,
        scheduled_at=new_event.scheduled_at,
        transferable_at=new_event.transferable_at,
        event_kind=new_event.event_kind.value,
        release_type=new_event.release_type.value,
        allocation_bucket=new_event.allocation_bucket.value,
        bucket_composition=(
            None
            if new_event.bucket_composition is None
            else [c.model_dump(mode="json") for c in new_event.bucket_composition]
        ),
        amount_tokens=new_event.amount_tokens,
        amount_provenance=new_event.amount_provenance.value,
        derivation=new_event.derivation,
        percent_current_circulating=new_event.percent_current_circulating,
        percent_total_supply=new_event.percent_total_supply,
        vesting_series_id=new_event.vesting_series_id,
        tranche_number=new_event.tranche_number,
        source_confidence=new_event.source_confidence.value,
        knowledge_timestamp=new_event.knowledge_timestamp,
        valid_from=new_event.valid_from,
        ambiguity_flags=new_event.ambiguity_flags,
    )
    session.execute(stmt)

    if source_links is None:
        copy_select = select(
            literal(new_event.event_version_id),
            _EVENT_SOURCE_TABLE.c.source_artifact_id,
            _EVENT_SOURCE_TABLE.c.source_role,
            _EVENT_SOURCE_TABLE.c.claim_type,
            _EVENT_SOURCE_TABLE.c.excerpt,
        ).where(_EVENT_SOURCE_TABLE.c.event_version_id == old_version_id)
        session.execute(
            _EVENT_SOURCE_TABLE.insert().from_select(
                ["event_version_id", "source_artifact_id", "source_role", "claim_type", "excerpt"],
                copy_select,
            )
        )
    else:
        for link in source_links:
            session.execute(
                insert(_EVENT_SOURCE_TABLE)
                .values(
                    event_version_id=new_event.event_version_id,
                    source_artifact_id=link.source_artifact_id,
                    source_role=link.source_role.value,
                    claim_type=link.claim_type.value,
                    excerpt=link.excerpt,
                )
                .on_conflict_do_nothing()
            )
    session.commit()
    return new_event.event_version_id
