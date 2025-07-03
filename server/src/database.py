from psycopg_pool import ConnectionPool
from contextlib import contextmanager
from typing import Optional

from .config import get_settings

settings = get_settings()

# Connection pool for efficient database connections
_connection_pool: Optional[ConnectionPool] = None


def init_connection_pool():
    """Initialize the connection pool."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = ConnectionPool(
            conninfo=settings.database_url, min_size=1, max_size=20
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
