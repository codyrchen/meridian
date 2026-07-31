"""Integration fixtures. These tests need a running PostgreSQL (make db-up).

They skip with an explicit message when the database is unreachable so the
unit suite stays runnable anywhere, but Epic 0 is only done when they pass.
"""

from collections.abc import Iterator

import pytest
from meridian_pipelines.db import make_engine
from sqlalchemy import Engine, text


def _postgres_available(engine: Engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def pg_engine() -> Iterator[Engine]:
    engine = make_engine()
    if not _postgres_available(engine):
        pytest.skip(
            "PostgreSQL unreachable at DATABASE_URL - run `make db-up` first "
            "(integration tests are required for Epic 0 completion)"
        )
    yield engine
    engine.dispose()


@pytest.fixture()
def clean_db(pg_engine: Engine) -> Iterator[Engine]:
    """Migrate to head from scratch for a pristine schema, then hand out the engine."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield pg_engine
