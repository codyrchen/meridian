"""Engine/session helpers. DATABASE_URL comes from the environment (see .env.example)."""

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

DEFAULT_DATABASE_URL = "postgresql+psycopg://meridian:meridian_local_dev@localhost:5432/meridian"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or database_url())


def make_session(engine: Engine) -> Session:
    return Session(engine, expire_on_commit=False)
