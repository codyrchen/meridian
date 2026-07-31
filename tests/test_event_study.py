import math
from datetime import date, timedelta
from decimal import Decimal

import pytest
from meridian_research.event_study import compute_event_study
from meridian_research.windows import EventWindow, MissingObservationError, align_prices

EVENT_DAY = date(2026, 6, 16)


def constant_series(days: range, value: str) -> dict[date, Decimal]:
    return {EVENT_DAY + timedelta(days=d): Decimal(value) for d in days}


def doubling_series(days: range, base: float = 100.0) -> dict[date, Decimal]:
    """Price doubles every day: log return is exactly ln(2) each day."""
    return {EVENT_DAY + timedelta(days=d): Decimal(str(base * 2.0**d)) for d in days}


class TestWindow:
    def test_offsets_and_required_dates(self) -> None:
        window = EventWindow(pre_days=30, post_days=30)
        assert len(window.offsets) == 61
        required = window.required_dates(EVENT_DAY)
        assert len(required) == 62  # includes day -31 for the day -30 return
        assert required[0] == EVENT_DAY - timedelta(days=31)
        assert required[-1] == EVENT_DAY + timedelta(days=30)

    def test_missing_dates_fail_loudly_with_names(self) -> None:
        window = EventWindow(pre_days=2, post_days=2)
        prices = constant_series(range(-3, 2), "1")  # missing day +2
        with pytest.raises(MissingObservationError, match="2026-06-18"):
            align_prices(prices, EVENT_DAY, window, series_name="asset")

    def test_rejects_negative_window(self) -> None:
        with pytest.raises(ValueError):
            EventWindow(pre_days=-1, post_days=30)


class TestEventStudy:
    def test_hand_computed_car_doubling_asset_flat_benchmark(self) -> None:
        window = EventWindow(pre_days=2, post_days=2)
        asset = doubling_series(range(-3, 3))
        benchmark = constant_series(range(-3, 3), "50000")
        df = compute_event_study(asset, benchmark, EVENT_DAY, window)

        assert df.height == 5
        assert df["offset_day"].to_list() == [-2, -1, 0, 1, 2]
        ln2 = math.log(2.0)
        for i, row in enumerate(df.iter_rows(named=True)):
            assert row["asset_log_return"] == pytest.approx(ln2)
            assert row["benchmark_log_return"] == pytest.approx(0.0)
            assert row["abnormal_return"] == pytest.approx(ln2)
            assert row["car"] == pytest.approx((i + 1) * ln2)
            assert row["asset_cum_log_return"] == pytest.approx((i + 1) * ln2)

    def test_car_is_zero_when_asset_tracks_benchmark(self) -> None:
        window = EventWindow(pre_days=2, post_days=2)
        asset = doubling_series(range(-3, 3), base=1.0)
        benchmark = doubling_series(range(-3, 3), base=60000.0)
        df = compute_event_study(asset, benchmark, EVENT_DAY, window)
        assert all(abs(v) < 1e-12 for v in df["car"].to_list())
        assert df["asset_cum_log_return"][-1] == pytest.approx(5 * math.log(2.0))

    def test_day_zero_row_has_event_date(self) -> None:
        window = EventWindow(pre_days=1, post_days=1)
        df = compute_event_study(
            constant_series(range(-2, 2), "2"),
            constant_series(range(-2, 2), "3"),
            EVENT_DAY,
            window,
        )
        day0 = df.filter(df["offset_day"] == 0)
        assert day0["date"][0] == EVENT_DAY

    def test_full_window_has_61_rows(self) -> None:
        window = EventWindow()
        df = compute_event_study(
            constant_series(range(-31, 31), "2"),
            constant_series(range(-31, 31), "3"),
            EVENT_DAY,
            window,
        )
        assert df.height == 61

    def test_missing_benchmark_coverage_raises(self) -> None:
        window = EventWindow(pre_days=2, post_days=2)
        with pytest.raises(MissingObservationError, match="benchmark"):
            compute_event_study(
                constant_series(range(-3, 3), "2"),
                constant_series(range(-3, 2), "3"),  # missing final day
                EVENT_DAY,
                window,
            )
