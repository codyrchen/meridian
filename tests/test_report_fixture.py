"""Fixture mode must be offline, DB-free, and byte-deterministic for the CSV."""

import json
from pathlib import Path

from meridian_pipelines.cli import main


def run_fixture(tmp_path: Path, name: str) -> Path:
    output_dir = tmp_path / name
    assert main(["report-fixture", "--output-dir", str(output_dir)]) == 0
    return output_dir


def test_fixture_report_writes_all_three_artifacts(tmp_path: Path) -> None:
    out = run_fixture(tmp_path, "run")
    assert (out / "event_study.csv").exists()
    assert (out / "car_chart.png").stat().st_size > 0
    manifest = json.loads((out / "run_manifest.json").read_text())
    assert manifest["row_count"] == 61
    assert manifest["window"] == {"pre_days": 30, "post_days": 30}
    assert manifest["methodology"]["abnormal_return"] == (
        "asset_log_return_t - benchmark_log_return_t"
    )
    assert manifest["data_snapshot"]["mode"] == "synthetic-fixture"
    assert manifest["generated_at"] == "2026-01-01T00:00:00+00:00"


def test_fixture_csv_has_61_rows_and_expected_columns(tmp_path: Path) -> None:
    out = run_fixture(tmp_path, "run")
    lines = (out / "event_study.csv").read_text().splitlines()
    assert len(lines) == 62  # header + 61 data rows
    assert lines[0] == (
        "offset_day,date,asset_close,benchmark_close,asset_log_return,"
        "benchmark_log_return,asset_cum_log_return,abnormal_return,car"
    )
    first = lines[1].split(",")
    assert first[0] == "-30"
    assert first[1] == "2026-05-17"
    last = lines[-1].split(",")
    assert last[0] == "30"
    assert last[1] == "2026-07-16"


def test_fixture_csv_is_byte_identical_across_runs(tmp_path: Path) -> None:
    first = run_fixture(tmp_path, "a") / "event_study.csv"
    second = run_fixture(tmp_path, "b") / "event_study.csv"
    assert first.read_bytes() == second.read_bytes()
