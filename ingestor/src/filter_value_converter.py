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

    def update_filter_value_boolean(self) -> None:
        try:
            with self.db_conn_factory() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE filter
                        SET value_boolean = cast_to_bool(value)
                        WHERE cast_to_bool(value) IS NOT NULL AND value not in ('1', '0')
                        """
                    )
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error updating filter value boolean: {e}")
            raise

    def update_filter_value_numeric(self) -> None:
        try:
            with self.db_conn_factory() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE filter
                        SET value_numeric = cast_to_numeric(value)
                        WHERE cast_to_numeric(value) IS NOT NULL
                        """
                    )
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error updating filter value numeric: {e}")
            raise

    def update_filter_value_timestamp(self) -> None:
        try:
            with self.db_conn_factory() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE filter
                        SET value_timestamp = cast_to_timestamp(value)
                        WHERE cast_to_timestamp(value) IS NOT NULL AND cast_to_float(value) IS NULL
                        """
                    )
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error updating filter value timestamp: {e}")
            raise

    def update_filter_value_unit(self) -> None:
        try:
            with self.db_conn_factory() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE filter
                        SET value_si = to_unit(value_numeric, unit)
                        WHERE unit is not null and lower(unit) not in ('na', 'none', '') and value_numeric is not null;
                        """
                    )
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error updating filter value unit: {e}")
            raise

    def run(self) -> None:
        self.logger.info("Updating filter value boolean...")
        self.update_filter_value_boolean()
        self.logger.info("Filter value boolean update completed.")

        self.logger.info("Updating filter value numeric...")
        self.update_filter_value_numeric()
        self.logger.info("Filter value numeric update completed.")

        self.logger.info("Updating filter value timestamp...")
        self.update_filter_value_timestamp()
        self.logger.info("Filter value timestamp update completed.")

        self.logger.info("Updating filter value unit...")
        self.update_filter_value_unit()
        self.logger.info("Filter value unit update completed.")
