"""Database engine, session factory and FastAPI dependency."""

import json
from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _json_serializer(value: Any) -> str:
    """Serialise UUIDs, datetimes and other values stored in JSONB columns."""
    return json.dumps(value, default=str, separators=(",", ":"))


_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    json_serializer=_json_serializer,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for the duration of a request."""
    with SessionLocal() as session:
        yield session
