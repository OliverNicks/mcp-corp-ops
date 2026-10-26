"""
Dual-Engine Database Abstraction (MySQL + SQLite).
Supports connection pooling for MySQL and thread-safe fixtures for SQLite.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool, StaticPool

from src.core.config import Settings
from src.core.config import settings as default_settings

logger = logging.getLogger("db")


class DatabaseManager:
    """
    Manages database engines, connection pooling, and session lifecycles
    for both MySQL 8.0 and SQLite.
    """

    def __init__(self, config: Settings | None = None):
        self.config = config or default_settings
        self._engine: Engine | None = None
        self._session_factory: sessionmaker | None = None

    @property
    def engine(self) -> Engine:
        """Lazy-initializes and returns the active SQLAlchemy Engine."""
        if self._engine is None:
            self._engine = self._create_engine()
            self._session_factory = sessionmaker(
                bind=self._engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )
        return self._engine

    def _create_engine(self) -> Engine:
        """Constructs an engine with appropriate pooling and driver parameters."""
        db_engine_type = self.config.db_engine.lower()
        if db_engine_type == "sqlite":
            return self._create_sqlite_engine()
        elif db_engine_type == "mysql":
            return self._create_mysql_engine()
        else:
            raise ValueError(
                f"Unsupported DB_ENGINE: '{db_engine_type}'. Choose 'sqlite' or 'mysql'."
            )

    def _create_sqlite_engine(self) -> Engine:
        """Builds an SQLite engine tailored for local testing and CI fixtures."""
        sqlite_path = self.config.sqlite_path
        # If file-based SQLite, ensure parent directory exists
        if sqlite_path != ":memory:":
            Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{sqlite_path}"
        logger.info("Initializing SQLite database engine at %s", url)
        # In-memory SQLite requires StaticPool so connections share the same memory space
        if sqlite_path == ":memory:":
            return create_engine(
                url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        # File-based SQLite: allow multi-threaded access from FastMCP / Uvicorn threads
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,  # SQLite handles file locks better without persistent connection pools
        )

    def _create_mysql_engine(self) -> Engine:
        """Builds a high-concurrency MySQL engine with QueuePool connection pooling."""
        url = self.config.database_url
        logger.info(
            "Initializing MySQL database engine at %s:%d/%s",
            self.config.db_host,
            self.config.db_port,
            self.config.db_name,
        )
        return create_engine(
            url,
            poolclass=QueuePool,
            pool_size=10,  # Normal pool capacity
            max_overflow=20,  # Extra surge connections allowed under load (Locust 50 VU)
            pool_timeout=30.0,  # Wait up to 30s for an available socket before raising TimeoutError
            pool_recycle=1800,  # Recycle sockets older than 30 mins to prevent MySQL wait_timeout drops
            pool_pre_ping=True,  # Tests connection liveness with SELECT 1 before checkout
            echo=self.config.debug,
        )

    # -------------------------------------------------------------------------
    # Context Managers
    # -------------------------------------------------------------------------
    @contextmanager
    def get_connection(self) -> Generator[Connection, None, None]:
        """Provides a managed connection from the pool, closing it upon exit."""
        connection = self.engine.connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Provides a managed SQLAlchemy ORM session."""
        if self._session_factory is None:
            _ = self.engine  # Trigger lazy creation
        session: Session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # -------------------------------------------------------------------------
    # High-Level Query Execution
    # -------------------------------------------------------------------------
    def execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Executes a raw SQL statement and returns the rows as a list of dictionaries.
        Used by catalog_tool, sales_tool, and sql_tool.
        """
        stmt = text(query)
        with self.get_connection() as conn:
            result = conn.execute(stmt, params or {})
            if result.returns_rows:
                return [dict(row) for row in result.mappings().all()]
            conn.commit()
            return []

    def check_health(self) -> bool:
        """Verifies database connectivity with a lightweight ping query."""
        try:
            with self.get_connection() as conn:
                res = conn.execute(text("SELECT 1")).scalar()
                return res == 1
        except Exception as exc:
            logger.error("Database health check failed: %s", exc)
            return False

    def dispose(self) -> None:
        """Disposes connection pool resources on shutdown."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None


# Global singleton instance
db = DatabaseManager()
