from psycopg_pool import ConnectionPool
from contextlib import contextmanager
from typing import Optional
import time
from psycopg import OperationalError
from .setup_logging import get_logger
from .config import get_settings

settings = get_settings()
logger = get_logger(__name__)

# Connection pool for efficient database connections
_connection_pool: Optional[ConnectionPool] = None


def init_connection_pool():
    """Initialize the connection pool with robust configuration."""
    global _connection_pool
    if _connection_pool is None:
        try:
            # Add application name to connection string if not already present
            conninfo = settings.database_url
            if "application_name" not in conninfo:
                separator = "&" if "?" in conninfo else "?"
                conninfo += f"{separator}application_name=pan-finder-server"

            _connection_pool = ConnectionPool(
                conninfo=conninfo,
                min_size=settings.db_pool_min_size,
                max_size=settings.db_pool_max_size,
                # Check connections before reusing them
                check=ConnectionPool.check_connection,
                # Timeout for getting a connection from the pool
                timeout=settings.db_connection_timeout,
                # Maximum time a connection can stay in the pool
                max_idle=settings.db_max_idle,
                # Maximum lifetime of a connection
                max_lifetime=settings.db_max_lifetime,
                # Number of connections to attempt when pool is growing
                num_workers=3,
                # Configure connection parameters for better reliability
                kwargs={
                    "connect_timeout": 10,
                },
            )
            logger.info(
                f"Database connection pool initialized successfully "
                f"(min_size={settings.db_pool_min_size}, "
                f"max_size={settings.db_pool_max_size}, "
                f"timeout={settings.db_connection_timeout}s)"
            )
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise


def get_connection_pool() -> ConnectionPool:
    """Get the connection pool, initializing if necessary."""
    global _connection_pool
    if _connection_pool is None:
        init_connection_pool()
    assert _connection_pool is not None, "Connection pool not initialized"
    return _connection_pool


def reset_connection_pool():
    """Reset the connection pool in case of persistent issues."""
    global _connection_pool
    if _connection_pool is not None:
        try:
            _connection_pool.close()
            logger.info("Connection pool closed")
        except Exception as e:
            logger.warning(f"Error closing connection pool: {e}")
        finally:
            _connection_pool = None
    init_connection_pool()


def check_database_health() -> bool:
    """
    Check if the database is healthy and accessible.

    Returns:
        True if database is healthy, False otherwise
    """
    try:
        with get_db_connection(retry_count=1) as conn:
            conn.execute("SELECT 1")
            logger.debug("Database health check passed")
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


def cleanup_connection_pool():
    """Clean up the connection pool on application shutdown."""
    global _connection_pool
    if _connection_pool is not None:
        try:
            _connection_pool.close()
            logger.info("Connection pool closed successfully")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
        finally:
            _connection_pool = None


@contextmanager
def get_db_connection(retry_count: int = 3):
    """
    Context manager to get a database connection from the pool with retry logic.

    Args:
        retry_count: Number of times to retry getting a connection
    """
    pool = get_connection_pool()
    last_exception = None

    for attempt in range(retry_count):
        try:
            with pool.connection() as conn:
                # Test the connection before yielding it
                conn.execute("SELECT 1")
                yield conn
                return
        except (OperationalError, ConnectionError, OSError) as e:
            last_exception = e
            logger.warning(
                f"Database connection attempt {attempt + 1}/{retry_count} failed: {e}"
            )

            if attempt < retry_count - 1:
                # Wait before retrying (exponential backoff)
                wait_time = min(2**attempt, 10)  # Cap at 10 seconds
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

                # If this is the last retry before giving up, try resetting the pool
                if attempt == retry_count - 2:
                    logger.warning("Resetting connection pool before final retry")
                    try:
                        reset_connection_pool()
                        pool = get_connection_pool()
                    except Exception as reset_error:
                        logger.error(f"Failed to reset connection pool: {reset_error}")
            else:
                logger.error(f"All connection attempts failed. Last error: {e}")

    # If we get here, all retries failed
    if last_exception:
        raise last_exception
    else:
        raise RuntimeError("Failed to establish database connection after retries")
