from datetime import UTC, datetime, timedelta

import httpx
import pytest
from meridian_connectors.coingecko import (
    MIN_DAILY_GRANULARITY_DAYS,
    CoinGeckoClient,
    CoinGeckoError,
)

START = datetime(2026, 5, 10, tzinfo=UTC)
END = datetime(2026, 7, 20, tzinfo=UTC)
OK_BODY = {"prices": [[1780531200000, 0.5]], "market_caps": [], "total_volumes": []}


def make_client(
    handler: httpx.MockTransport, sleeps: list[float], api_key: str | None = None
) -> CoinGeckoClient:
    return CoinGeckoClient(
        api_key,
        transport=handler,
        max_retries=4,
        backoff_base_seconds=1.5,
        sleep=sleeps.append,
    )


def test_recovers_from_429_with_backoff() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(429, text="throttled")
        return httpx.Response(200, json=OK_BODY)

    sleeps: list[float] = []
    client = make_client(httpx.MockTransport(handler), sleeps)
    body = client.fetch_market_chart_range("arbitrum", "usd", START, END)
    assert b"prices" in body
    assert len(calls) == 3
    assert sleeps == [1.5, 3.0]  # exponential, bounded


def test_retry_exhaustion_raises_after_bounded_attempts() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(500, text="boom")

    sleeps: list[float] = []
    client = make_client(httpx.MockTransport(handler), sleeps)
    with pytest.raises(CoinGeckoError, match="after 4 attempts"):
        client.fetch_market_chart_range("arbitrum", "usd", START, END)
    assert len(calls) == 4
    assert len(sleeps) == 3


def test_non_retryable_client_error_fails_immediately() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(401, text="bad key")

    sleeps: list[float] = []
    client = make_client(httpx.MockTransport(handler), sleeps)
    with pytest.raises(CoinGeckoError, match="non-retryable HTTP 401"):
        client.fetch_market_chart_range("arbitrum", "usd", START, END)
    assert len(calls) == 1
    assert sleeps == []


def test_sends_demo_api_key_header_and_range_params() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=OK_BODY)

    client = make_client(httpx.MockTransport(handler), [], api_key="demo-key-123")
    client.fetch_market_chart_range("bitcoin", "usd", START, END)
    request = seen[0]
    assert request.headers["x-cg-demo-api-key"] == "demo-key-123"
    assert request.url.path.endswith("/coins/bitcoin/market_chart/range")
    # START..END spans <92 days, so `from` is widened backwards to guarantee
    # daily granularity; `to` never moves.
    widened = END - timedelta(days=MIN_DAILY_GRANULARITY_DAYS)
    assert request.url.params["from"] == str(int(widened.timestamp()))
    assert request.url.params["to"] == str(int(END.timestamp()))


def test_range_above_daily_granularity_threshold_passes_through_unchanged() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=OK_BODY)

    long_start = END - timedelta(days=MIN_DAILY_GRANULARITY_DAYS + 8)
    client = make_client(httpx.MockTransport(handler), [])
    client.fetch_market_chart_range("bitcoin", "usd", long_start, END)
    request = seen[0]
    assert request.url.params["from"] == str(int(long_start.timestamp()))
    assert request.url.params["to"] == str(int(END.timestamp()))
