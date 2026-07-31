"""End-to-end CLI smoke test against PostgreSQL using synthetic data only.

seed-event -> ingest (fixture dir, offline) -> report. Also proves ingest and
seed idempotency at the database level."""

import hashlib
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from meridian_pipelines import synthetic
from meridian_pipelines.cli import main
from meridian_pipelines.db import make_session
from meridian_pipelines.dq_checks import (
    DataQualityError,
    check_no_duplicate_unlock_events,
    latest_closes,
)
from meridian_pipelines.ids import asset_uuid
from meridian_pipelines.tables import MarketBarDailyRow, SourceArtifactRow, UnlockEventRow
from sqlalchemy import Engine, func, select

pytestmark = pytest.mark.integration


@pytest.fixture()
def workspace(tmp_path: Path) -> dict[str, Path]:
    """Temp config + curated event + fixture payloads, all synthetic."""
    fixture_dir = tmp_path / "payloads"
    fixture_dir.mkdir()
    for coin in (synthetic.FIXTURE_ASSET, synthetic.FIXTURE_BENCHMARK):
        (fixture_dir / f"{coin}.json").write_bytes(synthetic.synthetic_market_chart_payload(coin))

    doc = b"synthetic vesting schedule document (not a real source)"
    archive_dir = tmp_path / "raw" / "synthetic_docs"
    archive_dir.mkdir(parents=True)
    checksum = hashlib.sha256(doc).hexdigest()
    archived = archive_dir / f"{checksum}.raw"
    archived.write_bytes(doc)

    curated = tmp_path / "synthetic_event.yaml"
    curated.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "asset": {
                    "symbol": "SYNTH",
                    "name": "Synthetic Token",
                    "coingecko_id": synthetic.FIXTURE_ASSET,
                    "decimals": 18,
                },
                "primary_source": {
                    "source_name": "synthetic_docs",
                    "source_uri": "fixture://synthetic",
                    "archived_path": str(archived),
                    "checksum_sha256": checksum,
                    "retrieved_at": "2026-07-30T00:00:00Z",
                    "license_class": "public",
                },
                "event": {
                    "scheduled_at": "2026-06-16T13:00:00Z",
                    "release_type": "cliff",
                    "allocation_bucket": "investor",
                    "amount_tokens": "92650000",
                    "percent_total_supply": "0.9265",
                    "percent_current_circulating": None,
                    "source_confidence": "unverified",
                    "ambiguity_flags": ["synthetic test data"],
                },
            }
        )
    )

    config = tmp_path / "slice.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "asset": {
                    "coingecko_id": synthetic.FIXTURE_ASSET,
                    "symbol": "SYNTH",
                    "name": "Synthetic Token",
                },
                "benchmark": {
                    "coingecko_id": synthetic.FIXTURE_BENCHMARK,
                    "symbol": "SYNBENCH",
                    "name": "Synthetic Benchmark",
                },
                "event_file": str(curated),
                "window": {"pre_days": 30, "post_days": 30},
                "vs_currency": "usd",
                "fetch_buffer_days": 3,
                "archive_root": str(tmp_path / "raw"),
                "output_root": str(tmp_path / "outputs"),
            }
        )
    )
    return {"config": config, "fixture_dir": fixture_dir, "outputs": tmp_path / "outputs"}


def test_seed_ingest_report_end_to_end(
    clean_db: Engine, workspace: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    config = str(workspace["config"])

    assert main(["seed-event", "--config", config]) == 0
    assert "created" in capsys.readouterr().out

    # Seeding again is an idempotent no-op, not a duplicate.
    assert main(["seed-event", "--config", config]) == 0
    assert "no-op" in capsys.readouterr().out

    assert main(["ingest", "--config", config, "--fixture-dir", str(workspace["fixture_dir"])]) == 0
    out = capsys.readouterr().out
    assert re.search(r"76 bars parsed, 76 inserted", out)

    # Second ingest of identical payloads inserts nothing.
    assert main(["ingest", "--config", config, "--fixture-dir", str(workspace["fixture_dir"])]) == 0
    out = capsys.readouterr().out
    assert re.search(r"76 bars parsed, 0 inserted, 76 already present", out)

    with make_session(clean_db) as session:
        assert session.execute(select(func.count(UnlockEventRow.id))).scalar_one() == 1
        bar_count = session.execute(select(func.count(MarketBarDailyRow.ts))).scalar_one()
        assert bar_count == 152  # 76 days x 2 assets, no duplicates
        # Lineage: every bar and the event point at archived artifacts.
        orphan_bars = session.execute(
            select(func.count(MarketBarDailyRow.ts)).where(
                MarketBarDailyRow.source_artifact_id.not_in(select(SourceArtifactRow.id))
            )
        ).scalar_one()
        assert orphan_bars == 0

    assert main(["report", "--config", config]) == 0
    report_out = capsys.readouterr().out
    assert "event study rows: 61" in report_out

    run_dirs = list(workspace["outputs"].iterdir())
    assert len(run_dirs) == 1
    produced = {p.name for p in run_dirs[0].iterdir()}
    assert produced == {"event_study.csv", "car_chart.png", "run_manifest.json"}
    csv_lines = (run_dirs[0] / "event_study.csv").read_text().splitlines()
    assert len(csv_lines) == 62


def test_duplicate_unlock_events_fail_dq(clean_db: Engine) -> None:
    now = datetime(2026, 7, 30, tzinfo=UTC)
    with make_session(clean_db) as session:
        session.add(
            SourceArtifactRow(
                id=uuid4(),
                source_name="synthetic",
                retrieved_at=now,
                knowledge_timestamp=now,
                checksum_sha256="0" * 64,
                license_class="public",
                object_uri="file:///dev/null",
                metadata_={},
            )
        )
        session.flush()
        artifact_id = session.execute(select(SourceArtifactRow.id)).scalar_one()
        from meridian_pipelines.tables import AssetRow

        asset_id = asset_uuid("dup-test")
        session.add(
            AssetRow(id=asset_id, symbol="DUP", name="Dup", coingecko_id="dup-test", valid_from=now)
        )
        for _ in range(2):  # same natural key, distinct ids -> duplicate
            session.add(
                UnlockEventRow(
                    id=uuid4(),
                    asset_id=asset_id,
                    scheduled_at=now,
                    release_type="cliff",
                    allocation_bucket="investor",
                    amount_tokens=Decimal("1000"),
                    source_artifact_id=artifact_id,
                    source_confidence="unverified",
                    knowledge_timestamp=now,
                    valid_from=now,
                    ambiguity_flags=[],
                )
            )
        session.commit()
        with pytest.raises(DataQualityError, match="duplicate unlock event"):
            check_no_duplicate_unlock_events(session)


def test_latest_closes_prefers_newest_knowledge_timestamp(clean_db: Engine) -> None:
    from meridian_pipelines.tables import AssetRow

    older = datetime(2026, 7, 1, tzinfo=UTC)
    newer = datetime(2026, 7, 15, tzinfo=UTC)
    with make_session(clean_db) as session:
        asset_id = asset_uuid("pit-test")
        session.add(
            AssetRow(
                id=asset_id, symbol="PIT", name="Pit", coingecko_id="pit-test", valid_from=older
            )
        )
        for i, (ts_knowledge, close) in enumerate([(older, "1.00"), (newer, "1.05")]):
            artifact = SourceArtifactRow(
                id=uuid4(),
                source_name="synthetic",
                retrieved_at=ts_knowledge,
                knowledge_timestamp=ts_knowledge,
                checksum_sha256=str(i) * 64,
                license_class="public",
                object_uri="file:///dev/null",
                metadata_={},
            )
            session.add(artifact)
            session.flush()
            session.add(
                MarketBarDailyRow(
                    asset_id=asset_id,
                    ts=datetime(2026, 6, 16, tzinfo=UTC).date(),
                    close=Decimal(close),
                    quote_currency="usd",
                    source_artifact_id=artifact.id,
                    knowledge_timestamp=ts_knowledge,
                )
            )
        session.commit()
        closes = latest_closes(session, asset_id)
        assert closes[datetime(2026, 6, 16, tzinfo=UTC).date()] == Decimal("1.05")
