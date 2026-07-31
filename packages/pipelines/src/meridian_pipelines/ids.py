"""Deterministic UUIDs for canonical entities so re-running loaders is idempotent."""

import uuid

_NAMESPACE = uuid.UUID("a3f1c2d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d")


def asset_uuid(natural_key: str) -> uuid.UUID:
    """natural_key: coingecko_id, or chain:contract when no coingecko id exists."""
    return uuid.uuid5(_NAMESPACE, f"asset:{natural_key}")


def unlock_event_uuid(
    asset_id: uuid.UUID, scheduled_at_iso: str, allocation_bucket: str, amount_tokens: str
) -> uuid.UUID:
    return uuid.uuid5(
        _NAMESPACE,
        f"unlock:{asset_id}:{scheduled_at_iso}:{allocation_bucket}:{amount_tokens}",
    )
