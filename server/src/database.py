import os
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from contextlib import contextmanager
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://usr:pwd@pgvector:5432/pan-finder"
)
# Connection pool for efficient database connections
_connection_pool: Optional[ConnectionPool] = None
_connection_pool = None


def init_connection_pool():
    """Initialize the connection pool."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = ConnectionPool(
            conninfo=DATABASE_URL, min_size=1, max_size=20
        )


def get_connection_pool() -> ConnectionPool:
    """Get the connection pool, initializing if necessary."""
    global _connection_pool
    if _connection_pool is None:
        init_connection_pool()
    assert _connection_pool is not None, "Connection pool not initialized"
    return _connection_pool


@contextmanager
def get_db_connection():
    """Context manager to get a database connection from the pool."""
    pool = get_connection_pool()
    with pool.connection() as conn:
        yield conn


@contextmanager
def get_db_cursor():
    """Context manager to get a database cursor."""
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            yield cursor


# Dependency for FastAPI to get DB cursor
def get_db():
    """Dependency function for FastAPI routes."""
    with get_db_cursor() as cursor:
        yield cursor
