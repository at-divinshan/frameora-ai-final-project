"""SQLAlchemy connection configuration for the existing MySQL database."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


# Connections are opened lazily, when a database operation is requested.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=False,
    hide_parameters=True,
    connect_args={"connect_timeout": 5, "read_timeout": 5, "write_timeout": 5},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """Close sessions (and roll back uncommitted work) after every request."""
    with SessionLocal() as session:
        yield session


def check_database_connection() -> bool:
    """Perform a read-only probe without accessing or modifying application tables."""
    with engine.connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1
