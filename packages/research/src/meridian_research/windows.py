"""Event-window alignment.

Day 0 is the UTC calendar date of the unlock. The window is [-pre_days,
+post_days] in calendar days (crypto trades continuously). Computing the
return on day -pre_days requires a price on day -(pre_days + 1), so that date
is part of the required coverage. Missing observations fail loudly; nothing
is interpolated or imputed.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal


class MissingObservationError(Exception):
    """Required daily observations are absent from the input snapshot."""


@dataclass(frozen=True)
class EventWindow:
    pre_days: int = 30
    post_days: int = 30

    def __post_init__(self) -> None:
        if self.pre_days < 0 or self.post_days < 0:
            raise ValueError("window sides must be non-negative")

    @property
    def offsets(self) -> list[int]:
        """Offsets with a computable return: -pre_days .. +post_days."""
        return list(range(-self.pre_days, self.post_days + 1))

    def required_dates(self, event_day: date) -> list[date]:
        """All dates a price is required for, including day -(pre_days+1)."""
        return [
            event_day + timedelta(days=offset)
            for offset in range(-self.pre_days - 1, self.post_days + 1)
        ]


def align_prices(
    prices: dict[date, Decimal],
    event_day: date,
    window: EventWindow,
    *,
    series_name: str,
) -> list[Decimal]:
    """Return prices for offsets -(pre+1) .. +post, failing loudly on gaps."""
    required = window.required_dates(event_day)
    missing = [d for d in required if d not in prices]
    if missing:
        shown = ", ".join(d.isoformat() for d in missing[:5])
        raise MissingObservationError(
            f"{series_name}: missing {len(missing)} required daily observation(s) "
            f"in [{required[0].isoformat()}, {required[-1].isoformat()}]: {shown}"
            + ("..." if len(missing) > 5 else "")
        )
    return [prices[d] for d in required]
