"""Database Configuration & Multi-DB Management.

Verwaltet separate SQLAlchemy-Engines für:
- users.sqlite: User, Roles, Permissions
- cra.sqlite: CRA-Daten, Kontrollen, Bewertungen
- audit.sqlite: Audit-Logs, Audit-Trail

Pattern: DbManager(db_name: str) → SQLAlchemy Session
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


# Datenbank-Mapping: db_name → Dateiname
_DB_FILES = {
    "users": "users.sqlite",
    "cra": "cra.sqlite",
    "audit": "audit.sqlite",
}

# Datenbank-Verzeichnis (relativ zum Projekt-Root)
_DB_DIR = Path(__file__).parent.parent.parent / "data" / "db"


class DbManager:
    """Verwaltet mehrere SQLite-Datenbanken mit separaten Engines."""

    def __init__(self, db_name: str):
        """
        Args:
            db_name: Name der Datenbank ('users', 'cra', 'audit')

        Raises:
            ValueError: Wenn db_name nicht bekannt ist
        """
        if db_name not in _DB_FILES:
            raise ValueError(
                f"Unknown database: {db_name}. Available: {list(_DB_FILES.keys())}"
            )

        self.db_name = db_name
        self.db_path = _DB_DIR / _DB_FILES[db_name]
        self._engine: Engine | None = None
        self._session_factory: sessionmaker | None = None

    @property
    def engine(self) -> Engine:
        """Lazy-initialize SQLAlchemy Engine."""
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    @property
    def session_factory(self) -> sessionmaker:
        """Lazy-initialize Session Factory."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(bind=self.engine)
        return self._session_factory

    def _create_engine(self) -> Engine:
        """SQLAlchemy-Engine auf PostgreSQL (Migration #15), Schema je db_name."""
        from sqlalchemy import event

        from shared.db import database_url, schema_for
        schema = schema_for(self.db_path)
        # SQLAlchemy nutzt psycopg3 über das +psycopg-Dialekt-Präfix.
        url = database_url().replace("postgresql://", "postgresql+psycopg://", 1)
        engine = create_engine(
            url,
            pool_size=10,
            max_overflow=5,
            pool_pre_ping=True,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        )

        @event.listens_for(engine, "connect")
        def _set_search_path(dbapi_conn, _rec):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            cur.execute(f'SET search_path TO "{schema}", public')
            cur.close()

        return engine

    def session(self) -> Session:
        """Erstelle neue Datenbankses sion."""
        return self.session_factory()

    @contextmanager
    def transaction(self) -> Generator[Session, None, None]:
        """Context-Manager für sichere Transaktionen.

        Beispiel:
            with DbManager('users').transaction() as session:
                user = session.query(User).first()
                session.commit()  # Automatisch
        """
        session = self.session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def health_check(self) -> bool:
        """Prüfe, ob Datenbankverbindung funktioniert."""
        try:
            with self.transaction() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print(f"Database health check failed for {self.db_name}: {e}")
            return False


# Globale Instanzen (Lazy-initialized)
_managers: dict[str, DbManager] = {}


def get_db_manager(db_name: str) -> DbManager:
    """Hole oder erstelle DbManager für Datenbank.

    Args:
        db_name: Name der Datenbank ('users', 'cra', 'audit')

    Returns:
        DbManager-Instanz (gecacht)
    """
    if db_name not in _managers:
        _managers[db_name] = DbManager(db_name)
    return _managers[db_name]


def get_session(db_name: str) -> Session:
    """Hole neue Session für Datenbank.

    Shortcut für: get_db_manager(db_name).session()
    """
    return get_db_manager(db_name).session()


@contextmanager
def transaction(db_name: str) -> Generator[Session, None, None]:
    """Context-Manager für Transaktion.

    Shortcut für: get_db_manager(db_name).transaction()

    Beispiel:
        from server.config.database import transaction

        with transaction('users') as session:
            user = session.query(User).first()
            user.email = 'new@example.com'
            # Auto-commit bei Erfolg, Rollback bei Exception
    """
    manager = get_db_manager(db_name)
    with manager.transaction() as session:
        yield session


def initialize_databases() -> bool:
    """Initialisiere alle Datenbanken.

    Wird beim App-Start aufgerufen, um sicherzustellen,
    dass alle DB-Verbindungen funktionieren.

    Returns:
        True wenn alle DBs OK, False wenn Fehler
    """
    results = {}
    for db_name in _DB_FILES.keys():
        manager = get_db_manager(db_name)
        results[db_name] = manager.health_check()
        status = "✓ OK" if results[db_name] else "✗ FAIL"
        print(f"  {db_name:10} {status}")

    return all(results.values())
