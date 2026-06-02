"""Session & Transaction Management.

Erweitert die DbManager-Klasse mit zusätzlicher Kontrolle
über Transaktionen und Lifecycle-Hooks.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from server.config.database import DbManager, get_db_manager
from sqlalchemy.orm import Session


class ManagedSession:
    """Wrapper um SQLAlchemy Session mit zusätzlichen Features."""

    def __init__(self, session: Session, db_name: str):
        """
        Args:
            session: SQLAlchemy Session
            db_name: Datenbank-Name (für Logging/Debugging)
        """
        self._session = session
        self._db_name = db_name
        self._is_closed = False

    def __enter__(self):
        """Context-Manager: __enter__"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context-Manager: __exit__"""
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()
        return False

    def commit(self):
        """Commit mit Fehlerbehandlung."""
        if not self._is_closed:
            self._session.commit()

    def rollback(self):
        """Rollback mit Fehlerbehandlung."""
        if not self._is_closed:
            self._session.rollback()

    def close(self):
        """Schließe Session."""
        if not self._is_closed:
            self._session.close()
            self._is_closed = True

    def execute(self, *args, **kwargs):
        """Proxy: session.execute()"""
        return self._session.execute(*args, **kwargs)

    def query(self, *args, **kwargs):
        """Proxy: session.query()"""
        return self._session.query(*args, **kwargs)

    def add(self, *args, **kwargs):
        """Proxy: session.add()"""
        return self._session.add(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Proxy: session.delete()"""
        return self._session.delete(*args, **kwargs)

    def flush(self, *args, **kwargs):
        """Proxy: session.flush()"""
        return self._session.flush(*args, **kwargs)

    def refresh(self, *args, **kwargs):
        """Proxy: session.refresh()"""
        return self._session.refresh(*args, **kwargs)


@contextmanager
def managed_session(db_name: str) -> Generator[ManagedSession, None, None]:
    """Context-Manager für ManagedSession.

    Auto-commit bei Erfolg, Auto-rollback bei Exception.

    Beispiel:
        from server.db.session import managed_session

        with managed_session('users') as session:
            user = session.query(User).filter_by(id=1).first()
            user.email = 'new@example.com'
            # Auto-commit
    """
    manager = get_db_manager(db_name)
    session = manager.session()
    managed = ManagedSession(session, db_name)

    try:
        yield managed
        if not managed._is_closed:
            managed.commit()
    except Exception:
        if not managed._is_closed:
            managed.rollback()
        raise
    finally:
        if not managed._is_closed:
            managed.close()
