"""Report artifacts: 61-row CSV, CAR chart with day 0 marked, run manifest.

The CSV uses explicit fixed-precision formatting so identical inputs produce
byte-identical output. The manifest records everything needed to reproduce
the run (code SHA, config hash, data snapshot summary, package versions).
"""

import csv
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path

import polars as pl

_FLOAT_COLUMNS = [
    "asset_close",
    "benchmark_close",
    "asset_log_return",
    "benchmark_log_return",
    "asset_cum_log_return",
    "abnormal_return",
    "car",
]
_TRACKED_PACKAGES = ["polars", "matplotlib", "pydantic", "sqlalchemy", "httpx"]


@dataclass(frozen=True)
class RunContext:
    run_id: str
    asset_symbol: str
    benchmark_symbol: str
    event_day: str
    window_pre_days: int
    window_post_days: int
    code_sha: str
    config_hash: str
    data_snapshot: dict[str, object] = field(default_factory=dict)
    generated_at: datetime | None = None  # pinned in fixture mode for determinism


def write_report(df: pl.DataFrame, output_dir: Path, context: RunContext) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv": output_dir / "event_study.csv",
        "chart": output_dir / "car_chart.png",
        "manifest": output_dir / "run_manifest.json",
    }
    _write_csv(df, paths["csv"])
    _write_chart(df, paths["chart"], context)
    _write_manifest(df, paths["manifest"], context)
    return paths


def _write_csv(df: pl.DataFrame, path: Path) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(df.columns)
        for row in df.iter_rows(named=True):
            writer.writerow(
                [
                    row["offset_day"],
                    row["date"].isoformat(),
                    *(f"{row[col]:.10f}" for col in _FLOAT_COLUMNS),
                ]
            )


def _write_chart(df: pl.DataFrame, path: Path, context: RunContext) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    offsets = df["offset_day"].to_list()
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(offsets, df["car"].to_list(), label=f"CAR vs {context.benchmark_symbol}", linewidth=2)
    ax.plot(
        offsets,
        df["asset_cum_log_return"].to_list(),
        label=f"{context.asset_symbol} raw cumulative log return",
        linewidth=1.5,
        linestyle="--",
    )
    ax.axvline(0, color="crimson", linestyle=":", linewidth=1.5)
    ax.annotate(
        f"day 0 = {context.event_day} (UTC)",
        xy=(0, 0),
        xycoords=("data", "axes fraction"),
        xytext=(6, 12),
        textcoords="offset points",
        color="crimson",
        fontsize=9,
    )
    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_xlabel("Event day (UTC calendar days from unlock)")
    ax.set_ylabel("Cumulative log return")
    ax.set_title(
        f"{context.asset_symbol} unlock {context.event_day}: "
        f"[-{context.window_pre_days}, +{context.window_post_days}] event window"
    )
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150, metadata={"Software": None})
    plt.close(fig)


def _write_manifest(df: pl.DataFrame, path: Path, context: RunContext) -> None:
    generated_at = context.generated_at or datetime.now(tz=UTC)
    manifest = {
        "run_id": context.run_id,
        "asset_symbol": context.asset_symbol,
        "benchmark_symbol": context.benchmark_symbol,
        "event_day_utc": context.event_day,
        "window": {"pre_days": context.window_pre_days, "post_days": context.window_post_days},
        "row_count": df.height,
        "methodology": {
            "returns": "daily log returns on close",
            "abnormal_return": "asset_log_return_t - benchmark_log_return_t",
            "car": "cumulative sum of abnormal returns over the window",
        },
        "code_sha": context.code_sha,
        "config_hash_sha256": context.config_hash,
        "data_snapshot": context.data_snapshot,
        "package_versions": {name: _version(name) for name in _TRACKED_PACKAGES},
        "generated_at": generated_at.isoformat(),
    }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def _version(name: str) -> str:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return "not-installed"
