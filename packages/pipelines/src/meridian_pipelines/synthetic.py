"""Deterministic synthetic market data for fixture mode and tests.

Prices come from closed-form formulas (no RNG), so every run produces the
same payload bytes. The synthetic asset is clearly labeled SYNTH — it is not
ARB and never mixes with real ingested data."""

import json
import math
from datetime import UTC, date, datetime, time, timedelta

FIXTURE_EVENT_DAY = date(2026, 6, 16)
FIXTURE_ASSET = "synthetic-asset"
FIXTURE_BENCHMARK = "synthetic-benchmark"
FIXTURE_GENERATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _price(coin_id: str, offset: int) -> float:
    if coin_id == FIXTURE_ASSET:
        # Mild uptrend before the event, deliberate drawdown after it.
        drift = 0.002 * offset if offset < 0 else -0.005 * offset
        return 0.50 * math.exp(drift + 0.01 * math.sin(offset / 3.0))
    if coin_id == FIXTURE_BENCHMARK:
        return 65000.0 * math.exp(0.001 * offset + 0.005 * math.sin(offset / 7.0))
    raise ValueError(f"unknown synthetic coin id: {coin_id}")


def synthetic_market_chart_payload(
    coin_id: str,
    event_day: date = FIXTURE_EVENT_DAY,
    start_offset: int = -40,
    end_offset: int = 35,
) -> bytes:
    prices: list[list[float]] = []
    caps: list[list[float]] = []
    volumes: list[list[float]] = []
    for offset in range(start_offset, end_offset + 1):
        day = event_day + timedelta(days=offset)
        ts_ms = int(datetime.combine(day, time.min, tzinfo=UTC).timestamp() * 1000)
        price = round(_price(coin_id, offset), 8)
        prices.append([ts_ms, price])
        caps.append([ts_ms, round(price * 5_000_000_000, 2)])
        volumes.append([ts_ms, round(price * 400_000_000, 2)])
    body = {"prices": prices, "market_caps": caps, "total_volumes": volumes}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
