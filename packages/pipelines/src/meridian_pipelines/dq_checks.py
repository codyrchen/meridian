"""Data-quality checks that block bad reads and writes. Failures raise; nothing
is silently cleaned, deduplicated, or imputed."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from meridian_pipelines.tables import MarketBarDailyRow, UnlockEventRow, UnlockEventSourceRow


class DataQualityError(Exception):
    pass


def check_no_duplicate_unlock_events(session: Session) -> None:
    """Duplicate = same asset/time/bucket/amount appearing under distinct
    *current* versions. Superseded versions are legitimate history, not
    duplicates. (Curation-validity layer.)"""
    stmt = (
        select(
            UnlockEventRow.asset_id,
            UnlockEventRow.scheduled_at,
            UnlockEventRow.allocation_bucket,
            UnlockEventRow.amount_tokens,
            func.count(UnlockEventRow.event_version_id).label("n"),
        )
        .where(UnlockEventRow.valid_to.is_(None))
        .group_by(
            UnlockEventRow.asset_id,
            UnlockEventRow.scheduled_at,
            UnlockEventRow.allocation_bucket,
            UnlockEventRow.amount_tokens,
        )
        .having(func.count(UnlockEventRow.event_version_id) > 1)
    )
    duplicates = session.execute(stmt).all()
    if duplicates:
        first = duplicates[0]
        raise DataQualityError(
            f"{len(duplicates)} duplicate unlock event group(s); first: asset={first.asset_id} "
            f"scheduled_at={first.scheduled_at} bucket={first.allocation_bucket} n={first.n}"
        )


def check_event_source_lineage(session: Session) -> None:
    """Every current event version must link to at least one primary source
    artifact through unlock_event_source. (Curation-validity layer.)"""
    linked = select(UnlockEventSourceRow.event_version_id).where(
        UnlockEventSourceRow.source_role == "primary"
    )
    stmt = select(func.count(UnlockEventRow.event_version_id)).where(
        UnlockEventRow.valid_to.is_(None),
        UnlockEventRow.event_version_id.not_in(linked),
    )
    orphans = session.execute(stmt).scalar_one()
    if orphans:
        raise DataQualityError(
            f"{orphans} current event version(s) lack a primary source link in unlock_event_source"
        )


def latest_closes(session: Session, asset_id: UUID) -> dict[date, Decimal]:
    """Point-in-time read: for each date keep the row with the newest
    knowledge_timestamp (corrections are append-only). Ties with conflicting
    closes are a data-quality failure, never silently resolved."""
    rows = session.execute(
        select(
            MarketBarDailyRow.ts,
            MarketBarDailyRow.close,
            MarketBarDailyRow.knowledge_timestamp,
        ).where(MarketBarDailyRow.asset_id == asset_id)
    ).all()
    best: dict[date, tuple[Decimal, datetime]] = {}
    for ts, close, knowledge_ts in rows:
        current = best.get(ts)
        if current is None or knowledge_ts > current[1]:
            best[ts] = (close, knowledge_ts)
        elif knowledge_ts == current[1] and close != current[0]:
            raise DataQualityError(
                f"conflicting closes for asset {asset_id} on {ts}: "
                f"{close} vs {current[0]} at identical knowledge_timestamp"
            )
    return {ts: close for ts, (close, _) in best.items()}
