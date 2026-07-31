"""CoinGecko market-data client and parser.

The client fetches raw bytes (archived before parsing); the parser is a pure
function from payload bytes to daily price points. Retries are bounded and
logged; 429/5xx trigger exponential backoff; exhaustion raises. No silent
data cleaning: duplicate or non-positive observations raise.
"""

import json
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.coingecko.com/api/v3"


class CoinGeckoError(Exception):
    """Request failed after bounded retries."""


class MalformedPayloadError(Exception):
    """Payload does not match the documented market_chart/range shape."""


@dataclass(frozen=True)
class DailyPricePoint:
    ts: date
    price: Decimal
    market_cap_usd: Decimal | None
    volume_usd: Decimal | None


class CoinGeckoClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        max_retries: int = 4,
        backoff_base_seconds: float = 1.5,
        sleep: Callable[[float], None] | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        headers = {"x-cg-demo-api-key": api_key} if api_key else {}
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers=headers,
            timeout=timeout_seconds,
            transport=transport,
        )
        self._max_retries = max_retries
        self._backoff_base = backoff_base_seconds
        self._sleep = sleep if sleep is not None else _default_sleep

    def fetch_market_chart_range(
        self, coin_id: str, vs_currency: str, start: datetime, end: datetime
    ) -> bytes:
        """Return the raw response body for /coins/{id}/market_chart/range."""
        params = {
            "vs_currency": vs_currency,
            "from": str(int(start.astimezone(UTC).timestamp())),
            "to": str(int(end.astimezone(UTC).timestamp())),
        }
        url = f"/coins/{coin_id}/market_chart/range"
        last_error: str = "no attempts made"
        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._client.get(url, params=params)
            except httpx.HTTPError as exc:
                last_error = f"transport error: {exc}"
            else:
                if response.status_code == 200:
                    return response.content
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = f"HTTP {response.status_code}"
                else:
                    raise CoinGeckoError(
                        f"{url} failed with non-retryable HTTP {response.status_code}: "
                        f"{response.text[:200]}"
                    )
            if attempt < self._max_retries:
                delay = self._backoff_base * (2 ** (attempt - 1))
                logger.warning(
                    "coingecko retry %d/%d after %s (sleeping %.1fs)",
                    attempt,
                    self._max_retries,
                    last_error,
                    delay,
                )
                self._sleep(delay)
        raise CoinGeckoError(f"{url} failed after {self._max_retries} attempts: {last_error}")

    def close(self) -> None:
        self._client.close()


def _default_sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


def parse_market_chart(payload: bytes) -> list[DailyPricePoint]:
    """Parse a market_chart/range payload into one point per UTC date.

    Fails loudly on malformed shapes, non-positive/non-finite prices, and
    duplicate dates (e.g. a partial current-day snapshot alongside the
    midnight point). Nothing is imputed or dropped.
    """
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise MalformedPayloadError(f"payload is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or "prices" not in data:
        raise MalformedPayloadError("payload missing 'prices' key")

    def series_by_date(key: str) -> dict[date, Decimal | None]:
        rows = data.get(key, [])
        if not isinstance(rows, list):
            raise MalformedPayloadError(f"'{key}' is not a list")
        out: dict[date, Decimal | None] = {}
        for row in rows:
            if not isinstance(row, list) or len(row) != 2:
                raise MalformedPayloadError(f"'{key}' row is not a [timestamp, value] pair: {row}")
            ts_ms, value = row
            if not isinstance(ts_ms, int | float):
                raise MalformedPayloadError(f"'{key}' timestamp is not numeric: {ts_ms}")
            day = datetime.fromtimestamp(ts_ms / 1000.0, tz=UTC).date()
            if day in out:
                raise MalformedPayloadError(
                    f"'{key}' has duplicate observations for {day.isoformat()}"
                )
            if value is None:
                out[day] = None
                continue
            if not isinstance(value, int | float) or not math.isfinite(value):
                raise MalformedPayloadError(f"'{key}' value is not finite: {value!r}")
            out[day] = Decimal(str(value))
        return out

    prices = series_by_date("prices")
    if not prices:
        raise MalformedPayloadError("payload contains no price observations")
    caps = series_by_date("market_caps")
    volumes = series_by_date("total_volumes")

    points: list[DailyPricePoint] = []
    for day in sorted(prices):
        price = prices[day]
        if price is None or price <= 0:
            raise MalformedPayloadError(f"non-positive or missing price on {day.isoformat()}")
        points.append(
            DailyPricePoint(
                ts=day,
                price=price,
                market_cap_usd=caps.get(day),
                volume_usd=volumes.get(day),
            )
        )
    return points
