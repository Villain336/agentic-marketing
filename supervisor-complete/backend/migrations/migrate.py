"""
Database Migration Runner
Tracks applied migrations and runs pending ones in order.
Works with Supabase (PostgreSQL) via the existing db module.
"""
from __future__ import annotations
import logging
import os
from pathlib import Path

logger = logging.getLogger("supervisor.migrations")

MIGRATIONS_DIR = Path(__file__).parent

# Migration tracking table (created automatically)
TRACKING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS _migrations (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum TEXT
);
"""


async def get_applied_migrations(db_module) -> set[str]:
    """Get set of already-applied migration filenames."""
    try:
        await db_module.execute_sql(TRACKING_TABLE_SQL)
        rows = await db_module.query_sql("SELECT filename FROM _migrations ORDER BY id")
        return {row["filename"] for row in rows}
    except Exception as e:
        logger.warning(f"Could not check migration status: {e}")
        return set()


def discover_migrations() -> list[Path]:
    """Find all .sql migration files, sorted by name."""
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


async def run_pending_migrations(db_module) -> list[str]:
    """Run all pending migrations and return list of applied filenames."""
    applied = await get_applied_migrations(db_module)
    migrations = discover_migrations()
    newly_applied = []

    for migration_path in migrations:
        filename = migration_path.name
        if filename in applied:
            continue

        logger.info(f"Applying migration: {filename}")
        sql = migration_path.read_text()

        try:
            await db_module.execute_sql(sql)
            await db_module.execute_sql(
                "INSERT INTO _migrations (filename) VALUES ($1)",
                filename,
            )
            newly_applied.append(filename)
            logger.info(f"Migration applied: {filename}")
        except Exception as e:
            logger.error(f"Migration failed: {filename}: {e}")
            raise

    if newly_applied:
        logger.info(f"Applied {len(newly_applied)} migrations: {newly_applied}")
    else:
        logger.info("No pending migrations")

    return newly_applied


async def migration_status(db_module) -> dict:
    """Return migration status for health checks."""
    applied = await get_applied_migrations(db_module)
    all_migrations = [p.name for p in discover_migrations()]
    pending = [m for m in all_migrations if m not in applied]
    return {
        "applied": sorted(applied),
        "pending": pending,
        "total": len(all_migrations),
        "up_to_date": len(pending) == 0,
    }
