from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# Engine configuration with support for SQLite and PostgreSQL
connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_engine(
    settings.resolved_database_url,
    connect_args=connect_args,
    echo=(settings.APP_ENV == "development" and not settings.is_sqlite),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
