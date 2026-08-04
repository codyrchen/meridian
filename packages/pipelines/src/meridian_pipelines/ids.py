"""Deterministic UUIDs for canonical entities so re-running loaders is idempotent."""

import uuid

_NAMESPACE = uuid.UUID("a3f1c2d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d")


def asset_uuid(natural_key: str) -> uuid.UUID:
    """natural_key: coingecko_id, or chain:contract when no coingecko id exists."""
    return uuid.uuid5(_NAMESPACE, f"asset:{natural_key}")


def logical_event_uuid(
    asset_id: uuid.UUID, scheduled_at_iso: str, allocation_bucket: str
) -> uuid.UUID:
    """Stable across revisions: amount is deliberately excluded so a corrected
    amount stays the same logical event."""
    return uuid.uuid5(
        _NAMESPACE,
        f"unlock-logical:{asset_id}:{scheduled_at_iso}:{allocation_bucket}",
    )


def event_version_uuid(
    logical_event_id: uuid.UUID, knowledge_timestamp_iso: str, amount_tokens: str
) -> uuid.UUID:
    return uuid.uuid5(
        _NAMESPACE,
        f"unlock-version:{logical_event_id}:{knowledge_timestamp_iso}:{amount_tokens}",
    )


def vesting_series_uuid(asset_id: uuid.UUID, series_slug: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, f"vesting-series:{asset_id}:{series_slug}")
