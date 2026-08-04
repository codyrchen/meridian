"""Deterministic-identity guarantees the revision model depends on."""

from meridian_pipelines.ids import (
    asset_uuid,
    event_version_uuid,
    logical_event_uuid,
    vesting_series_uuid,
)

ASSET = asset_uuid("synthetic-token")
SCHEDULED = "2026-06-16T00:00:00+00:00"


def test_logical_id_stable_across_amount_corrections() -> None:
    logical = logical_event_uuid(ASSET, SCHEDULED, "investor")
    v1 = event_version_uuid(logical, "2026-08-01T00:00:00+00:00", "1000000")
    v2 = event_version_uuid(logical, "2026-08-02T00:00:00+00:00", "990000")
    assert v1 != v2  # corrected amount -> new version
    # ... but the logical identity does not depend on the amount at all.
    assert logical == logical_event_uuid(ASSET, SCHEDULED, "investor")


def test_logical_id_distinguishes_bucket_and_schedule() -> None:
    base = logical_event_uuid(ASSET, SCHEDULED, "investor")
    assert base != logical_event_uuid(ASSET, SCHEDULED, "team")
    assert base != logical_event_uuid(ASSET, "2026-07-16T00:00:00+00:00", "investor")


def test_version_id_deterministic_for_identical_inputs() -> None:
    logical = logical_event_uuid(ASSET, SCHEDULED, "investor")
    a = event_version_uuid(logical, "2026-08-01T00:00:00+00:00", "1000000")
    b = event_version_uuid(logical, "2026-08-01T00:00:00+00:00", "1000000")
    assert a == b  # re-running the loader must regenerate the same version id


def test_series_id_deterministic_per_asset_and_slug() -> None:
    a = vesting_series_uuid(ASSET, "synth-investor-monthly")
    assert a == vesting_series_uuid(ASSET, "synth-investor-monthly")
    assert a != vesting_series_uuid(ASSET, "synth-team-monthly")
    assert a != vesting_series_uuid(asset_uuid("other-token"), "synth-investor-monthly")
