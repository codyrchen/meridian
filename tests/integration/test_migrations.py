import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "source_artifact",
    "asset",
    "unlock_event",
    "market_bar_daily",
    "vesting_series",
    "unlock_event_source",
    "supply_observation",
}


def test_upgrade_downgrade_upgrade_roundtrip(clean_db: Engine) -> None:
    cfg = Config("alembic.ini")
    assert EXPECTED_TABLES <= set(inspect(clean_db).get_table_names())

    command.downgrade(cfg, "base")
    remaining = set(inspect(clean_db).get_table_names())
    assert not (EXPECTED_TABLES & remaining)

    command.upgrade(cfg, "head")
    assert EXPECTED_TABLES <= set(inspect(clean_db).get_table_names())


def test_market_bar_has_quote_currency_and_checks(clean_db: Engine) -> None:
    inspector = inspect(clean_db)
    columns = {c["name"] for c in inspector.get_columns("market_bar_daily")}
    assert "quote_currency" in columns
    checks = {c["name"] for c in inspector.get_check_constraints("unlock_event")}
    assert {
        "ck_release_type_enum",
        "ck_allocation_bucket_enum",
        "ck_source_confidence_enum",
        "ck_amount_tokens_positive",
    } <= checks
