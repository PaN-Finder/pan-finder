"""
Logging configuration for the Pan Finder API application.
"""

import logging
import os
from typing import Optional


def setup_logging(log_level: Optional[str] = None) -> logging.Logger:
    """
    Configure logging for the entire FastAPI application.

    Args:
        log_level: Optional log level override. If not provided, uses LOG_LEVEL env var or defaults to INFO

    Returns:
        Logger instance for the application
    """
    # Determine log level
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    else:
        log_level = log_level.upper()

    # Validate log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in valid_levels:
        log_level = "INFO"

    # Create a formatter with timestamp and elapsed time
    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Create console handler and set formatter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Configure basic logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        handlers=[console_handler],  # Console output for Docker
        force=True,  # Override any existing configuration
    )

    # Create and configure application logger
    app_logger = logging.getLogger("pan-finder")
    app_logger.info(f"Logging configuration completed - Level: {log_level}")

    return app_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Usually __name__ from the calling module

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Application logger instance - can be imported by other modules
app_logger = setup_logging()
