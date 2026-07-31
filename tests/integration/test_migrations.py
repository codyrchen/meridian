import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {"source_artifact", "asset", "unlock_event", "market_bar_daily"}


def test_upgrade_downgrade_upgrade_roundtrip(pg_engine: Engine) -> None:
    cfg = Config("alembic.ini")

    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    assert EXPECTED_TABLES <= set(inspect(pg_engine).get_table_names())

    command.downgrade(cfg, "base")
    remaining = set(inspect(pg_engine).get_table_names())
    assert not (EXPECTED_TABLES & remaining)

    command.upgrade(cfg, "head")
    assert EXPECTED_TABLES <= set(inspect(pg_engine).get_table_names())


def test_market_bar_has_quote_currency_and_checks(pg_engine: Engine) -> None:
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    inspector = inspect(pg_engine)
    columns = {c["name"] for c in inspector.get_columns("market_bar_daily")}
    assert "quote_currency" in columns
    checks = {c["name"] for c in inspector.get_check_constraints("unlock_event")}
    assert {
        "ck_release_type_enum",
        "ck_allocation_bucket_enum",
        "ck_source_confidence_enum",
        "ck_amount_tokens_positive",
    } <= checks
