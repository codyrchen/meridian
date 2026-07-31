"""Data-quality checks that block bad reads and writes. Failures raise; nothing
is silently cleaned, deduplicated, or imputed."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from meridian_pipelines.tables import MarketBarDailyRow, UnlockEventRow


class DataQualityError(Exception):
    pass


def check_no_duplicate_unlock_events(session: Session) -> None:
    """Duplicate = same asset/time/bucket/amount appearing under distinct event ids."""
    stmt = (
        select(
            UnlockEventRow.asset_id,
            UnlockEventRow.scheduled_at,
            UnlockEventRow.allocation_bucket,
            UnlockEventRow.amount_tokens,
            func.count(UnlockEventRow.id).label("n"),
        )
        .group_by(
            UnlockEventRow.asset_id,
            UnlockEventRow.scheduled_at,
            UnlockEventRow.allocation_bucket,
            UnlockEventRow.amount_tokens,
        )
        .having(func.count(UnlockEventRow.id) > 1)
    )
    duplicates = session.execute(stmt).all()
    if duplicates:
        first = duplicates[0]
        raise DataQualityError(
            f"{len(duplicates)} duplicate unlock event group(s); first: asset={first.asset_id} "
            f"scheduled_at={first.scheduled_at} bucket={first.allocation_bucket} n={first.n}"
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
