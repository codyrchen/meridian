from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from meridian_domain.enums import AllocationBucket, ReleaseType, SourceConfidence
from meridian_domain.models import MarketBar, UnlockEvent
from pydantic import ValidationError

UTC_NOW = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


def make_event(**overrides: object) -> UnlockEvent:
    base: dict[str, object] = {
        "id": uuid4(),
        "asset_id": uuid4(),
        "scheduled_at": datetime(2026, 6, 16, 12, 55, tzinfo=UTC),
        "release_type": ReleaseType.LINEAR,
        "allocation_bucket": AllocationBucket.INVESTOR,
        "amount_tokens": Decimal("92650000"),
        "source_artifact_id": uuid4(),
        "source_confidence": SourceConfidence.VERIFIED_PRIMARY,
        "knowledge_timestamp": UTC_NOW,
        "valid_from": UTC_NOW,
    }
    base.update(overrides)
    return UnlockEvent.model_validate(base)


def make_bar(**overrides: object) -> MarketBar:
    base: dict[str, object] = {
        "asset_id": uuid4(),
        "ts": datetime(2026, 6, 16, tzinfo=UTC).date(),
        "close": Decimal("0.51"),
        "source_artifact_id": uuid4(),
        "knowledge_timestamp": UTC_NOW,
    }
    base.update(overrides)
    return MarketBar.model_validate(base)


class TestUnlockEvent:
    def test_valid_event_round_trips(self) -> None:
        event = make_event()
        assert event.amount_tokens == Decimal("92650000")

    def test_event_day_is_utc_calendar_date(self) -> None:
        # 2026-06-16 20:00 in UTC-5 is 2026-06-17 01:00 UTC -> day 0 is the 17th.
        utc_minus_5 = timezone(timedelta(hours=-5))
        event = make_event(scheduled_at=datetime(2026, 6, 16, 20, 0, tzinfo=utc_minus_5))
        assert event.event_day_utc.isoformat() == "2026-06-17"

    def test_rejects_negative_amount(self) -> None:
        with pytest.raises(ValidationError):
            make_event(amount_tokens=Decimal("-1"))

    def test_rejects_zero_amount(self) -> None:
        with pytest.raises(ValidationError):
            make_event(amount_tokens=Decimal("0"))

    def test_rejects_naive_datetime(self) -> None:
        with pytest.raises(ValidationError):
            make_event(scheduled_at=datetime(2026, 6, 16, 12, 55))  # noqa: DTZ001

    def test_rejects_unknown_enum_value(self) -> None:
        with pytest.raises(ValidationError):
            make_event(source_confidence="probably_fine")

    def test_rejects_percent_over_100(self) -> None:
        with pytest.raises(ValidationError):
            make_event(percent_total_supply=Decimal("101"))


class TestMarketBar:
    def test_valid_bar(self) -> None:
        bar = make_bar()
        assert bar.quote_currency == "usd"

    def test_rejects_nonpositive_close(self) -> None:
        with pytest.raises(ValidationError):
            make_bar(close=Decimal("0"))

    def test_rejects_negative_volume(self) -> None:
        with pytest.raises(ValidationError):
            make_bar(volume_usd=Decimal("-5"))

    def test_rejects_high_below_low(self) -> None:
        with pytest.raises(ValidationError):
            make_bar(high=Decimal("1"), low=Decimal("2"))

    def test_rejects_naive_knowledge_timestamp(self) -> None:
        with pytest.raises(ValidationError):
            make_bar(knowledge_timestamp=datetime(2026, 6, 16))  # noqa: DTZ001
