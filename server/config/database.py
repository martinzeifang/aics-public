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
from sqlalchemy.pool import StaticPool

from shared.db_security import connect_sqlite


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
        """Erstelle SQLAlchemy Engine mit sicheren Defaults."""
        # Für SQLite: URI mit file-URL
        db_uri = f"sqlite:///{self.db_path.as_posix()}"

        # Optionen für SQLite
        connect_args = {
            "timeout": 30,  # Seconds to wait for DB lock
            "check_same_thread": False,  # Allow multi-threaded access
        }

        # Erstelle Engine mit Connection-Pool
        engine = create_engine(
            db_uri,
            connect_args=connect_args,
            pool_size=10,  # Max connections in pool
            max_overflow=5,  # Additional connections if pool full
            pool_pre_ping=True,  # Verify connections before using
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        )

        # Hardening: Stelle sicher, dass DB-Verzeichnis sicher ist
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        from shared.db_security import ensure_private_dir
        ensure_private_dir(_DB_DIR)

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
