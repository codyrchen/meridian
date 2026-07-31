"""Idempotent daily market-bar ingestion.

Flow: fetch raw bytes -> archive immutably -> parse -> validate domain models
-> insert artifact + bars with ON CONFLICT DO NOTHING. The same payload always
maps to the same artifact id, so re-running with unchanged data inserts
nothing. Changed upstream data lands as new lineage rows (append-only
corrections); readers resolve by latest knowledge_timestamp."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from meridian_connectors.archive import RawArchive
from meridian_connectors.coingecko import parse_market_chart
from meridian_domain.enums import LicenseClass
from meridian_domain.models import MarketBar, SourceArtifactMeta
from sqlalchemy import CursorResult
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from meridian_pipelines.ids import asset_uuid
from meridian_pipelines.tables import AssetRow, MarketBarDailyRow, SourceArtifactRow

# (coin_id) -> (payload_bytes, source_uri) — live client or fixture reader.
PayloadFetcher = Callable[[str], tuple[bytes, str]]


@dataclass(frozen=True)
class IngestResult:
    coin_id: str
    asset_id: UUID
    artifact_checksum: str
    bars_total: int
    bars_inserted: int

    @property
    def bars_skipped(self) -> int:
        return self.bars_total - self.bars_inserted


def ensure_asset(session: Session, *, symbol: str, name: str, coingecko_id: str) -> UUID:
    asset_id = asset_uuid(coingecko_id)
    stmt = (
        insert(AssetRow)
        .values(
            id=asset_id,
            symbol=symbol,
            name=name,
            coingecko_id=coingecko_id,
            valid_from=datetime.now(tz=UTC),
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    session.execute(stmt)
    return asset_id


def ingest_daily_bars(
    session: Session,
    *,
    coin_id: str,
    asset_id: UUID,
    fetcher: PayloadFetcher,
    archive: RawArchive,
    quote_currency: str = "usd",
) -> IngestResult:
    payload, source_uri = fetcher(coin_id)
    now = datetime.now(tz=UTC)
    artifact = archive.archive(
        source_name="coingecko",
        payload=payload,
        retrieved_at=now,
        knowledge_timestamp=now,
        license_class=LicenseClass.ATTRIBUTION_REQUIRED,
        source_uri=source_uri,
        metadata={"coin_id": coin_id, "endpoint": "market_chart/range"},
    )
    points = parse_market_chart(payload)
    bars = [
        MarketBar(
            asset_id=asset_id,
            ts=point.ts,
            close=point.price,
            volume_usd=point.volume_usd,
            market_cap_usd=point.market_cap_usd,
            quote_currency=quote_currency,
            source_artifact_id=artifact.id,
            knowledge_timestamp=artifact.knowledge_timestamp,
        )
        for point in points
    ]

    _insert_artifact_row(session, artifact)
    inserted = 0
    for bar in bars:
        stmt = (
            insert(MarketBarDailyRow)
            .values(
                asset_id=bar.asset_id,
                ts=bar.ts,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume_usd=bar.volume_usd,
                market_cap_usd=bar.market_cap_usd,
                quote_currency=bar.quote_currency,
                source_artifact_id=bar.source_artifact_id,
                knowledge_timestamp=bar.knowledge_timestamp,
            )
            .on_conflict_do_nothing(index_elements=["asset_id", "ts", "source_artifact_id"])
        )
        inserted += cast(CursorResult[Any], session.execute(stmt)).rowcount or 0
    session.commit()
    return IngestResult(
        coin_id=coin_id,
        asset_id=asset_id,
        artifact_checksum=artifact.checksum_sha256,
        bars_total=len(bars),
        bars_inserted=inserted,
    )


def _insert_artifact_row(session: Session, artifact: SourceArtifactMeta) -> None:
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
