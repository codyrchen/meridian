"""Epic 0 command-line entry points.

Commands:
  seed-event      load the curated unlock event + archived primary source
  ingest          ingest daily bars for asset + benchmark (live or fixture dir)
  report          run the [-30,+30] event study from the database and write
                  CSV / chart / manifest
  report-fixture  deterministic offline report from synthetic data (no DB,
                  no network)
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

import yaml
from meridian_connectors.archive import RawArchive
from meridian_connectors.coingecko import CoinGeckoClient, parse_market_chart
from meridian_research.event_study import compute_event_study
from meridian_research.report import RunContext, write_report
from meridian_research.windows import EventWindow
from sqlalchemy.orm import Session

from meridian_pipelines import synthetic
from meridian_pipelines.db import make_engine, make_session
from meridian_pipelines.dq_checks import check_no_duplicate_unlock_events, latest_closes
from meridian_pipelines.ids import asset_uuid
from meridian_pipelines.ingest_market_data import ensure_asset, ingest_daily_bars
from meridian_pipelines.load_unlock_event import load_curated_file, seed_event

REPO_ROOT = Path.cwd()


@dataclass(frozen=True)
class SliceConfig:
    path: Path
    raw: dict[str, Any]

    @property
    def window(self) -> EventWindow:
        cfg = self.raw.get("window", {})
        return EventWindow(
            pre_days=int(cfg.get("pre_days", 30)), post_days=int(cfg.get("post_days", 30))
        )

    @property
    def config_hash(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


def load_config(path: str) -> SliceConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text())
    if not isinstance(raw, dict):
        raise SystemExit(f"config is not a mapping: {path}")
    return SliceConfig(path=config_path, raw=raw)


def code_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=10
        )
        return out.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def _event_day(config: SliceConfig) -> Any:
    curated = load_curated_file(REPO_ROOT / config.raw["event_file"])
    scheduled = datetime.fromisoformat(str(curated["event"]["scheduled_at"]).replace("Z", "+00:00"))
    return scheduled.astimezone(UTC).date()


def cmd_seed_event(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    engine = make_engine()
    with make_session(engine) as session:
        result = seed_event(session, REPO_ROOT / config.raw["event_file"], REPO_ROOT)
    status = "created" if result.created_event else "already present (idempotent no-op)"
    print(f"unlock event {result.event_id}: {status}")
    print(f"asset:           {result.asset_id}")
    print(f"source artifact: {result.source_artifact_id}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    window = config.window
    event_day = _event_day(config)
    buffer_days = int(config.raw.get("fetch_buffer_days", 3))
    start = datetime.combine(
        event_day - timedelta(days=window.pre_days + 1 + buffer_days), time.min, tzinfo=UTC
    )
    end = datetime.combine(
        event_day + timedelta(days=window.post_days + buffer_days), time.max, tzinfo=UTC
    )

    archive = RawArchive(REPO_ROOT / config.raw.get("archive_root", "data/raw"))
    vs_currency = str(config.raw.get("vs_currency", "usd"))

    if args.fixture_dir:
        fixture_dir = Path(args.fixture_dir)

        def fetcher(coin_id: str) -> tuple[bytes, str]:
            path = fixture_dir / f"{coin_id}.json"
            if not path.exists():
                raise SystemExit(f"fixture payload not found: {path}")
            return path.read_bytes(), f"fixture://{path.name}"

    else:
        client = CoinGeckoClient(os.environ.get("COINGECKO_API_KEY") or None)

        def fetcher(coin_id: str) -> tuple[bytes, str]:
            payload = client.fetch_market_chart_range(coin_id, vs_currency, start, end)
            return payload, f"coingecko:/coins/{coin_id}/market_chart/range"

    engine = make_engine()
    with make_session(engine) as session:
        for role in ("asset", "benchmark"):
            cfg = config.raw[role]
            asset_id = ensure_asset(
                session,
                symbol=cfg["symbol"],
                name=cfg["name"],
                coingecko_id=cfg["coingecko_id"],
            )
            result = ingest_daily_bars(
                session,
                coin_id=cfg["coingecko_id"],
                asset_id=asset_id,
                fetcher=fetcher,
                archive=archive,
                quote_currency=vs_currency,
            )
            print(
                f"{result.coin_id}: {result.bars_total} bars parsed, "
                f"{result.bars_inserted} inserted, {result.bars_skipped} already present "
                f"(artifact {result.artifact_checksum[:12]})"
            )
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    window = config.window
    event_day = _event_day(config)
    asset_cfg = config.raw["asset"]
    benchmark_cfg = config.raw["benchmark"]

    engine = make_engine()
    with make_session(engine) as session:
        check_no_duplicate_unlock_events(session)
        asset_id = asset_uuid(asset_cfg["coingecko_id"])
        benchmark_id = asset_uuid(benchmark_cfg["coingecko_id"])
        asset_prices = latest_closes(session, asset_id)
        benchmark_prices = latest_closes(session, benchmark_id)
        snapshot = _data_snapshot(session, config, event_day)

    df = compute_event_study(asset_prices, benchmark_prices, event_day, window)

    run_id = f"{event_day.isoformat()}_{datetime.now(tz=UTC):%Y%m%dT%H%M%SZ}"
    output_dir = REPO_ROOT / config.raw.get("output_root", "outputs") / run_id
    context = RunContext(
        run_id=run_id,
        asset_symbol=asset_cfg["symbol"],
        benchmark_symbol=benchmark_cfg["symbol"],
        event_day=event_day.isoformat(),
        window_pre_days=window.pre_days,
        window_post_days=window.post_days,
        code_sha=code_sha(),
        config_hash=config.config_hash,
        data_snapshot=snapshot,
    )
    paths = write_report(df, output_dir, context)
    day0_car = df.filter(df["offset_day"] == 0)["car"][0]
    final_car = df["car"][-1]
    print(f"event study rows: {df.height}")
    print(f"CAR at day 0:  {day0_car:+.6f}")
    print(f"CAR at day +{window.post_days}: {final_car:+.6f}")
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


def _data_snapshot(session: Session, config: SliceConfig, event_day: Any) -> dict[str, object]:
    from sqlalchemy import func, select

    from meridian_pipelines.tables import MarketBarDailyRow, SourceArtifactRow, UnlockEventRow

    bar_stats = session.execute(
        select(
            func.count(MarketBarDailyRow.ts),
            func.max(MarketBarDailyRow.knowledge_timestamp),
        )
    ).one()
    artifact_checksums = [
        row[0]
        for row in session.execute(
            select(SourceArtifactRow.checksum_sha256).order_by(SourceArtifactRow.checksum_sha256)
        )
    ]
    event_count = session.execute(select(func.count(UnlockEventRow.id))).scalar_one()
    return {
        "event_day_utc": event_day.isoformat(),
        "unlock_event_count": event_count,
        "market_bar_rows": bar_stats[0],
        "max_knowledge_timestamp": bar_stats[1].isoformat() if bar_stats[1] else None,
        "source_artifact_checksums": artifact_checksums,
    }


def cmd_report_fixture(args: argparse.Namespace) -> int:
    """Offline deterministic run: synthetic payloads -> real parser -> real
    event study -> real report writer. Byte-identical CSV on every run."""
    window = EventWindow(pre_days=30, post_days=30)
    payload_asset = synthetic.synthetic_market_chart_payload(synthetic.FIXTURE_ASSET)
    payload_benchmark = synthetic.synthetic_market_chart_payload(synthetic.FIXTURE_BENCHMARK)

    def closes(payload: bytes) -> dict[Any, Any]:
        return {p.ts: p.price for p in parse_market_chart(payload)}

    df = compute_event_study(
        closes(payload_asset), closes(payload_benchmark), synthetic.FIXTURE_EVENT_DAY, window
    )
    output_dir = Path(args.output_dir)
    context = RunContext(
        run_id="fixture",
        asset_symbol="SYNTH",
        benchmark_symbol="SYNBENCH",
        event_day=synthetic.FIXTURE_EVENT_DAY.isoformat(),
        window_pre_days=window.pre_days,
        window_post_days=window.post_days,
        code_sha=code_sha(),
        config_hash=hashlib.sha256(payload_asset + payload_benchmark).hexdigest(),
        data_snapshot={
            "mode": "synthetic-fixture",
            "asset_payload_sha256": hashlib.sha256(payload_asset).hexdigest(),
            "benchmark_payload_sha256": hashlib.sha256(payload_benchmark).hexdigest(),
        },
        generated_at=synthetic.FIXTURE_GENERATED_AT,
    )
    paths = write_report(df, output_dir, context)
    print(f"fixture event study rows: {df.height}")
    print(json.dumps({k: str(v) for k, v in paths.items()}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="meridian", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed-event", help="load the curated unlock event")
    p_seed.add_argument("--config", default="config/slice.yaml")
    p_seed.set_defaults(func=cmd_seed_event)

    p_ingest = sub.add_parser("ingest", help="ingest daily bars for asset + benchmark")
    p_ingest.add_argument("--config", default="config/slice.yaml")
    p_ingest.add_argument(
        "--fixture-dir",
        default=None,
        help="read <coin_id>.json payloads from this directory instead of the live API",
    )
    p_ingest.set_defaults(func=cmd_ingest)

    p_report = sub.add_parser("report", help="run the event study and write artifacts")
    p_report.add_argument("--config", default="config/slice.yaml")
    p_report.set_defaults(func=cmd_report)

    p_fixture = sub.add_parser("report-fixture", help="deterministic offline report")
    p_fixture.add_argument("--output-dir", default="outputs/fixture")
    p_fixture.set_defaults(func=cmd_report_fixture)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
