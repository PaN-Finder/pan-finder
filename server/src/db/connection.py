from psycopg_pool import ConnectionPool
from contextlib import contextmanager
from typing import Dict
import time
from psycopg import OperationalError
from ..utils import get_logger
from ..config import get_settings
from dataclasses import dataclass

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class DatabaseConfig:
    """Configuration for a database connection."""

    conninfo: str
    min_size: int = 1
    max_size: int = 20
    connection_timeout: int = 30
    max_idle: int = 300
    max_lifetime: int = 3600
    application_name: str = "pan-finder-server"

    def __post_init__(self):
        """Ensure application_name is in conninfo."""
        if "application_name" not in self.conninfo:
            separator = "&" if "?" in self.conninfo else "?"
            self.conninfo += f"{separator}application_name={self.application_name}"


class DatabaseManager:
    """
    Manages multiple database connection pools with different configurations.
    """

    def __init__(self):
        self._pools: Dict[str, ConnectionPool] = {}
        self._configs: Dict[str, DatabaseConfig] = {}

    def register_database(self, name: str, config: DatabaseConfig) -> None:
        """
        Register a new database configuration.

        Args:
            name: Unique identifier for this database
            config: Database configuration
        """
        self._configs[name] = config
        logger.info(f"Registered database configuration: {name}")

    def get_pool(self, name: str) -> ConnectionPool:
        """
        Get connection pool for a specific database, initializing if necessary.

        Args:
            name: Database identifier

        Returns:
            ConnectionPool instance
        """
        if name not in self._pools:
            self._init_pool(name)
        return self._pools[name]

    def _init_pool(self, name: str) -> None:
        """Initialize connection pool for a specific database."""
        if name not in self._configs:
            raise ValueError(f"Database '{name}' not registered")

        config = self._configs[name]

        try:
            self._pools[name] = ConnectionPool(
                conninfo=config.conninfo,
                min_size=config.min_size,
                max_size=config.max_size,
                check=ConnectionPool.check_connection,
                timeout=config.connection_timeout,
                max_idle=config.max_idle,
                max_lifetime=config.max_lifetime,
                num_workers=3,
                kwargs={
                    "connect_timeout": 10,
                },
            )
            logger.info(
                f"Database connection pool '{name}' initialized successfully "
                f"(min_size={config.min_size}, "
                f"max_size={config.max_size}, "
                f"timeout={config.connection_timeout}s)"
            )
        except Exception as e:
            logger.error(f"Failed to initialize connection pool '{name}': {e}")
            raise

    def reset_pool(self, name: str) -> None:
        """Reset a specific connection pool."""
        if name in self._pools:
            try:
                self._pools[name].close()
                logger.info(f"Connection pool '{name}' closed")
            except Exception as e:
                logger.warning(f"Error closing connection pool '{name}': {e}")
            finally:
                del self._pools[name]
        self._init_pool(name)

    def check_health(self, name: str) -> bool:
        """
        Check if a specific database is healthy and accessible.

        Args:
            name: Database identifier

        Returns:
            True if database is healthy, False otherwise
        """
        try:
            with self.get_connection(name, retry_count=1) as conn:
                conn.execute("SELECT 1")
                logger.debug(f"Database '{name}' health check passed")
                return True
        except Exception as e:
            logger.error(f"Database '{name}' health check failed: {e}")
            return False

    def cleanup_all(self) -> None:
        """Clean up all connection pools."""
        for name, pool in self._pools.items():
            try:
                pool.close()
                logger.info(f"Connection pool '{name}' closed successfully")
            except Exception as e:
                logger.error(f"Error closing connection pool '{name}': {e}")
        self._pools.clear()

    @contextmanager
    def get_connection(self, name: str, retry_count: int = 3):
        """
        Context manager to get a database connection with retry logic.

        Args:
            name: Database identifier
            retry_count: Number of times to retry getting a connection
        """
        pool = self.get_pool(name)
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
                    f"Database '{name}' connection attempt {attempt + 1}/{retry_count} failed: {e}"
                )

                if attempt < retry_count - 1:
                    # Wait before retrying (exponential backoff)
                    wait_time = min(2**attempt, 10)  # Cap at 10 seconds
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)

                    # If this is the last retry before giving up, try resetting the pool
                    if attempt == retry_count - 2:
                        logger.warning(
                            f"Resetting connection pool '{name}' before final retry"
                        )
                        try:
                            self.reset_pool(name)
                            pool = self.get_pool(name)
                        except Exception as reset_error:
                            logger.error(
                                f"Failed to reset connection pool '{name}': {reset_error}"
                            )
                else:
                    logger.error(
                        f"All connection attempts failed for '{name}'. Last error: {e}"
                    )

        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError(
                f"Failed to establish database connection to '{name}' after retries"
            )


# Global database manager instance
_db_manager = DatabaseManager()

# Register the default database from settings
_default_config = DatabaseConfig(
    conninfo=settings.database_url,
    min_size=settings.db_pool_min_size,
    max_size=settings.db_pool_max_size,
    connection_timeout=settings.db_connection_timeout,
    max_idle=settings.db_max_idle,
    max_lifetime=settings.db_max_lifetime,
)
_db_manager.register_database("default", _default_config)


# Public API functions
def register_database(name: str, config: DatabaseConfig) -> None:
    """
    Register a new database configuration.

    Args:
        name: Unique identifier for this database
        config: Database configuration
    """
    _db_manager.register_database(name, config)


def get_database_pool(name: str) -> ConnectionPool:
    """
    Get connection pool for a specific database.

    Args:
        name: Database identifier

    Returns:
        ConnectionPool instance
    """
    return _db_manager.get_pool(name)


@contextmanager
def get_database_connection(name: str = "default", retry_count: int = 3):
    """
    Context manager to get a connection from a specific database.

    Args:
        name: Database identifier (defaults to "default")
        retry_count: Number of times to retry getting a connection
    """
    with _db_manager.get_connection(name, retry_count) as conn:
        yield conn


def check_database_health(name: str = "default") -> bool:
    """
    Check if a specific database is healthy and accessible.

    Args:
        name: Database identifier (defaults to "default")

    Returns:
        True if database is healthy, False otherwise
    """
    return _db_manager.check_health(name)


def reset_database_pool(name: str = "default") -> None:
    """
    Reset a specific connection pool.

    Args:
        name: Database identifier (defaults to "default")
    """
    _db_manager.reset_pool(name)


def cleanup_connection_pools() -> None:
    """Clean up all connection pools."""
    _db_manager.cleanup_all()
