"""Market-adjusted event study over daily closes.

abnormal_return_t = asset_log_return_t - benchmark_log_return_t
CAR_t = cumulative sum of abnormal returns from day -pre_days through t.

Pure computation over explicitly passed snapshots; no I/O, no hidden state.
"""

import math
from datetime import date, timedelta
from decimal import Decimal

import polars as pl

from meridian_research.windows import EventWindow, align_prices

SCHEMA = {
    "offset_day": pl.Int64,
    "date": pl.Date,
    "asset_close": pl.Float64,
    "benchmark_close": pl.Float64,
    "asset_log_return": pl.Float64,
    "benchmark_log_return": pl.Float64,
    "asset_cum_log_return": pl.Float64,
    "abnormal_return": pl.Float64,
    "car": pl.Float64,
}


def compute_event_study(
    asset_prices: dict[date, Decimal],
    benchmark_prices: dict[date, Decimal],
    event_day: date,
    window: EventWindow,
) -> pl.DataFrame:
    """One row per offset day in [-pre_days, +post_days]."""
    asset = align_prices(asset_prices, event_day, window, series_name="asset")
    benchmark = align_prices(benchmark_prices, event_day, window, series_name="benchmark")

    offsets = window.offsets
    rows: list[dict[str, object]] = []
    asset_cum = 0.0
    car = 0.0
    # asset[0] is day -(pre+1); asset[i] is the price for offsets[i - 1] ... so
    # for offset index j, price index is j + 1 and previous price index is j.
    for j, offset in enumerate(offsets):
        asset_r = math.log(float(asset[j + 1]) / float(asset[j]))
        bench_r = math.log(float(benchmark[j + 1]) / float(benchmark[j]))
        abnormal = asset_r - bench_r
        asset_cum += asset_r
        car += abnormal
        rows.append(
            {
                "offset_day": offset,
                "date": event_day + timedelta(days=offset),
                "asset_close": float(asset[j + 1]),
                "benchmark_close": float(benchmark[j + 1]),
                "asset_log_return": asset_r,
                "benchmark_log_return": bench_r,
                "asset_cum_log_return": asset_cum,
                "abnormal_return": abnormal,
                "car": car,
            }
        )
    return pl.DataFrame(rows, schema=SCHEMA)
