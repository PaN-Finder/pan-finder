"""
Convert string-based filter values into typed columns in the `filter` table.

This module provides the class `FilterValueConverter`, which uses database-side
casting helpers to populate the following derived columns when possible:
- `value_boolean` via `cast_to_bool(value)` (excluding literal '1'/'0' strings)
- `value_numeric` via `cast_to_numeric(value)`
- `value_timestamp` via `cast_to_timestamp(value)` when `cast_to_float(value)` is NULL
- `value_si` via `to_unit(value_numeric, unit)` when `unit` is valid and `value_numeric` is not NULL
"""

import logging
from typing import Callable, ContextManager, Any


class FilterValueConverter:
    """Convert filter values to typed columns using DB-side casting helpers."""

    logger = logging.getLogger("FilterValueConverter")

    def __init__(self, db_conn_factory: Callable[[], ContextManager[Any]]) -> None:
        self.db_conn_factory = db_conn_factory

    def run(self) -> None:
        """Execute all updates in one transaction and log affected rows."""
        try:
            with self.db_conn_factory() as conn:
                with conn.cursor() as cursor:
                    # Boolean
                    cursor.execute(
                        """
                        UPDATE filter
                        SET value_boolean = cast_to_bool(value)
                        WHERE cast_to_bool(value) IS NOT NULL
                          AND value NOT IN ('1', '0')
                          AND (value_boolean IS DISTINCT FROM cast_to_bool(value))
                        """
                    )
                    self.logger.info("Updated value_boolean rows: %s", cursor.rowcount)

                    # Numeric
                    cursor.execute(
                        """
                        UPDATE filter
                        SET value_numeric = cast_to_numeric(value)
                        WHERE cast_to_numeric(value) IS NOT NULL
                          AND (value_numeric IS DISTINCT FROM cast_to_numeric(value))
                        """
                    )
                    self.logger.info("Updated value_numeric rows: %s", cursor.rowcount)

                    # Timestamp
                    cursor.execute(
                        """
                        UPDATE filter
                        SET value_timestamp = cast_to_timestamp(value)
                        WHERE cast_to_timestamp(value) IS NOT NULL
                          AND cast_to_float(value) IS NULL
                          AND (value_timestamp IS DISTINCT FROM cast_to_timestamp(value))
                        """
                    )
                    self.logger.info(
                        "Updated value_timestamp rows: %s", cursor.rowcount
                    )

                    # SI unit
                    cursor.execute(
                        """
                        UPDATE filter
                        SET value_si = to_unit(value_numeric, unit)
                        WHERE unit IS NOT NULL
                          AND lower(unit) NOT IN ('na', 'none', '')
                          AND value_numeric IS NOT NULL
                          AND (value_si IS DISTINCT FROM to_unit(value_numeric, unit));
                        """
                    )
                    self.logger.info("Updated value_si rows: %s", cursor.rowcount)
                conn.commit()
            self.logger.info("Filter value conversion completed.")
        except Exception as e:
            self.logger.error(f"Filter value conversion failed: {e}")
            raise
