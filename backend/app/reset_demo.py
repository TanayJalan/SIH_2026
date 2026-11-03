"""Rebuild the demo database from migrations and the seed data.

``make reset-demo`` runs this module inside the backend container. It drops the
``public`` schema and lets :func:`app.seed.seed` run ``alembic upgrade head``
again, so the database returns to the exact state of a fresh ``make seed``.

A plain ``TRUNCATE`` is not enough: reference rows such as ``deadline_rules``
and ``workflow_definitions`` are inserted by the migrations, not by the seeder,
and truncating them would leave the demo without statutory clocks.
"""

from __future__ import annotations

import logging
import time

from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger("app.reset_demo")


def drop_schema() -> None:
    """Drop and recreate the ``public`` schema.

    Every table, sequence, index and enum is owned by ``public``, so this is the
    fastest way back to an empty database that the migrations can rebuild.
    """
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    # The pool still holds connections prepared against the dropped schema.
    engine.dispose()


def reset_demo() -> None:
    """Drop the demo schema and rebuild it through the seeder."""
    started = time.perf_counter()
    drop_schema()
    logger.info(" dropped and recreated the public schema")

    from app.seed import seed

    seed(database=True)
    logger.info(" demo reset finished in %.1fs", time.perf_counter() - started)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    reset_demo()
