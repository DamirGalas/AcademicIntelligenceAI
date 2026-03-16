"""Central database connection and migration runner.

All schema changes live as numbered SQL files in db/migrations/.
On first connection each session, the runner applies any migrations
that haven't been recorded in the _migrations table yet.
"""

import sqlite3
from pathlib import Path

from academic_intelligence_ai.monitoring.logger import get_logger

logger = get_logger("db.connection")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = PROJECT_ROOT / "data" / "academic.db"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

_migrated = False


def get_connection() -> sqlite3.Connection:
    """Return a connection to the project database, running pending migrations."""
    global _migrated
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    if not _migrated:
        _run_migrations(conn)
        _migrated = True
    return conn


def _run_migrations(conn: sqlite3.Connection):
    """Apply any SQL migration files that haven't been applied yet."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()

    applied = {
        row[0]
        for row in conn.execute("SELECT filename FROM _migrations").fetchall()
    }

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for migration_file in migration_files:
        if migration_file.name in applied:
            continue

        logger.info("Applying migration: %s", migration_file.name)
        sql = migration_file.read_text(encoding="utf-8")

        # Execute each statement separately (split on ;)
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(statement)

        conn.execute(
            "INSERT INTO _migrations (filename) VALUES (?)",
            (migration_file.name,),
        )
        conn.commit()
        logger.info("Migration applied: %s", migration_file.name)


if __name__ == "__main__":
    conn = get_connection()

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print("Tables:", [t[0] for t in tables])

    migrations = conn.execute(
        "SELECT filename, applied_at FROM _migrations ORDER BY id"
    ).fetchall()
    print("Applied migrations:")
    for filename, applied_at in migrations:
        print(f"  {filename} ({applied_at})")

    conn.close()
