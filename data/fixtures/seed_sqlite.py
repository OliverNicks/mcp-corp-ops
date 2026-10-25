"""
SQLite Database Fixture Generator for Local Development, CI, and FastMCP Testing.
Loads OpenCart best4baby schema and mock data directly from init_best4baby_sqlite.sql.
"""

from pathlib import Path
import sqlite3
from typing import Optional

from src.core.config import settings


def get_default_db_path() -> str:
    """Resolves the default SQLite database path using Pydantic Settings."""
    return settings.sqlite_path


def seed_sqlite(db_path: Optional[str] = None) -> str:
    """
    Seeds SQLite database by executing data/fixtures/init_best4baby_sqlite.sql.
    Supports file-based path as well as in-memory ':memory:' database.
    """
    target_path = db_path or get_default_db_path()

    # Load SQLite SQL script from the sibling fixture file
    sql_file = Path(__file__).parent / "init_best4baby_sqlite.sql"
    if not sql_file.exists():
        raise FileNotFoundError(f"Fixture SQL file not found at: {sql_file}")

    sql_script = sql_file.read_text(encoding="utf-8")

    if target_path != ":memory:":
        Path(target_path).parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(target_path) as conn:
        conn.executescript(sql_script)

    return target_path


if __name__ == "__main__":
    path = seed_sqlite()
    print(f"Successfully seeded SQLite fixtures at: {path}")
