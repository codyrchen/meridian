import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from meridian_connectors.coingecko import MalformedPayloadError, parse_market_chart

FIXTURES = Path(__file__).parent / "fixtures"


def ms(day: str) -> int:
    return int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp() * 1000)


def payload(prices: list[list[float]], **extra: object) -> bytes:
    body: dict[str, object] = {"prices": prices, "market_caps": [], "total_volumes": []}
    body.update(extra)
    return json.dumps(body).encode()


def test_parses_committed_sample_fixture() -> None:
    points = parse_market_chart((FIXTURES / "coingecko_market_chart_sample.json").read_bytes())
    assert len(points) == 3
    assert points[0].ts.isoformat() == "2026-06-04"
    assert points[0].price == Decimal("0.5012")
    assert points[0].market_cap_usd == Decimal("2510000000.0")
    assert points[0].volume_usd == Decimal("181000000.0")
    assert [p.ts for p in points] == sorted(p.ts for p in points)


def test_missing_market_cap_for_a_day_is_none_not_error() -> None:
    points = parse_market_chart(payload([[ms("2026-06-04"), 1.5]]))
    assert points[0].market_cap_usd is None


def test_rejects_invalid_json() -> None:
    with pytest.raises(MalformedPayloadError, match="not valid JSON"):
        parse_market_chart(b"<html>rate limited</html>")


def test_rejects_missing_prices_key() -> None:
    with pytest.raises(MalformedPayloadError, match="missing 'prices'"):
        parse_market_chart(b'{"market_caps": []}')


def test_rejects_empty_price_series() -> None:
    with pytest.raises(MalformedPayloadError, match="no price observations"):
        parse_market_chart(payload([]))


def test_rejects_duplicate_dates() -> None:
    # Midnight point plus a same-day partial snapshot must fail, not be deduped.
    with pytest.raises(MalformedPayloadError, match="duplicate observations"):
        parse_market_chart(payload([[ms("2026-06-04"), 1.0], [ms("2026-06-04") + 7200_000, 1.1]]))


def test_rejects_nonpositive_price() -> None:
    with pytest.raises(MalformedPayloadError, match="non-positive"):
        parse_market_chart(payload([[ms("2026-06-04"), 0.0]]))


def test_rejects_malformed_row_shape() -> None:
    with pytest.raises(MalformedPayloadError, match="pair"):
        parse_market_chart(payload([[ms("2026-06-04")]]))
