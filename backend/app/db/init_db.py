"""
Database initialization module for Smart Battery AI.
Creates all database tables defined in SQLAlchemy ORM models.
Compatible with SQLite (local development) and PostgreSQL (cloud).
"""

import logging
from sqlalchemy import Engine
from app.db.session import engine as default_engine
from app.db.base import Base
# Import all models so that Base.metadata registers them
import app.models  # noqa: F401

logger = logging.getLogger(__name__)


def migrate_db(engine: Engine = default_engine) -> None:
    """Safely updates existing schemas with non-destructive column additions."""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            # Inspect existing charging_sessions columns
            res = conn.execute(text("PRAGMA table_info(charging_sessions);"))
            cols = [row[1] for row in res.fetchall()]
            if cols:
                if "data_source" not in cols:
                    logger.info("Migrating schema: adding data_source column to charging_sessions")
                    conn.execute(text("ALTER TABLE charging_sessions ADD COLUMN data_source VARCHAR(30) DEFAULT 'SYNTHETIC';"))
                if "idle_usage_minutes" not in cols:
                    logger.info("Migrating schema: adding idle_usage_minutes column to charging_sessions")
                    conn.execute(text("ALTER TABLE charging_sessions ADD COLUMN idle_usage_minutes FLOAT DEFAULT 0.0;"))
                if "previous_day_usage_minutes" not in cols:
                    logger.info("Migrating schema: adding previous_day_usage_minutes column to charging_sessions")
                    conn.execute(text("ALTER TABLE charging_sessions ADD COLUMN previous_day_usage_minutes FLOAT DEFAULT 0.0;"))
                conn.commit()
    except Exception as exc:
        logger.debug("Database migration note: %s", str(exc))


def init_db(engine: Engine = default_engine) -> None:
    """Creates all database tables in the configured database and runs migrations."""
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    migrate_db(engine=engine)
    logger.info("Database tables initialized successfully.")


def reset_db(engine: Engine = default_engine) -> None:
    """Drops and re-creates all database tables (useful for testing and migrations)."""
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("Database reset completed.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database tables created successfully.")
