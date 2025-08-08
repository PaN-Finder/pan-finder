import os
import glob
from datetime import datetime
from .connection import get_db_connection
from psycopg import sql
from ..utils import get_logger

logger = get_logger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


def get_migration_files():
    files = glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))
    return sorted(files)


def ensure_migrations_table():
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS migration (
                id SERIAL PRIMARY KEY,
                filename TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            """
        )


def get_applied_migrations():
    with get_db_connection() as conn:
        result = conn.execute("SELECT filename FROM migration").fetchall()
        return set(row[0] for row in result)


def apply_migration(filename):
    logger.info(f"Applying migration file: {os.path.basename(filename)}")
    with open(filename, "r") as f:
        sql_content = f.read()
    statements = [s.strip() for s in sql_content.split(";") if s.strip()]
    with get_db_connection() as conn:
        for i, statement in enumerate(statements):
            try:
                logger.debug(
                    f"Executing statement {i+1}/{len(statements)} in {os.path.basename(filename)}"
                )
                conn.execute(sql.SQL(statement))  # type: ignore
            except Exception as e:
                logger.error(
                    f"Error executing statement {i+1} in {os.path.basename(filename)}: {e}"
                )
                raise
        conn.execute(
            sql.SQL("INSERT INTO migration (filename, applied_at) VALUES (%s, %s)"),
            (os.path.basename(filename), datetime.now()),
        )
    logger.info(f"Migration {os.path.basename(filename)} applied successfully.")


def run_migrations():
    logger.info("Starting database migrations...")
    ensure_migrations_table()
    applied = get_applied_migrations()
    files = get_migration_files()
    applied_count = 0
    for file in files:
        base = os.path.basename(file)
        if base not in applied:
            try:
                apply_migration(file)
                applied_count += 1
            except Exception as e:
                logger.error(f"Migration failed for {base}: {e}")
                raise
        else:
            logger.info(f"Migration already applied: {base}")
    logger.info(
        f"Migrations complete. {applied_count} new migration(s) applied, {len(files) - applied_count} already applied."
    )
