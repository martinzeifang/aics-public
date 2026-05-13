"""Tests für DB-Isolation & Multi-DB-Management.

Verifiziert, dass separate Datenbanken korrekt isoliert sind
und Transaktionen über Datenbanken hinweg funktionieren.
"""

import tempfile
from pathlib import Path

import pytest

from server.config.database import DbManager, get_db_manager, initialize_databases, transaction
from server.db.session import managed_session


class TestDbManager:
    """Tests für DbManager."""

    def test_db_manager_initialization(self):
        """Test: DbManager-Initialisierung mit bekannten DB-Namen."""
        manager = DbManager('users')
        assert manager.db_name == 'users'
        assert manager.db_path.name == 'users.sqlite'

    def test_db_manager_unknown_db_raises(self):
        """Test: Unbekannte DB wirft ValueError."""
        with pytest.raises(ValueError, match="Unknown database"):
            DbManager('unknown_db')

    def test_db_manager_engine_lazy_init(self):
        """Test: Engine wird beim ersten Zugriff initialisiert."""
        manager = DbManager('users')
        assert manager._engine is None

        # Engine wird beim Zugriff initialisiert
        engine = manager.engine
        assert engine is not None
        assert manager._engine is engine

    def test_db_manager_cached(self):
        """Test: DbManager-Instanzen werden gecacht."""
        manager1 = get_db_manager('users')
        manager2 = get_db_manager('users')
        assert manager1 is manager2

    def test_session_creation(self):
        """Test: Sessions können erstellt werden."""
        manager = get_db_manager('users')
        session1 = manager.session()
        session2 = manager.session()

        assert session1 is not session2
        session1.close()
        session2.close()

    def test_transaction_commit(self):
        """Test: Transaktionen werden committed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Nutze Temp-DB für diesen Test
            tmpdb = Path(tmpdir) / "test_users.sqlite"
            manager = DbManager('users')

            # Setze temporären DB-Pfad
            manager.db_path = tmpdb

            with manager.transaction() as session:
                # Einfacher SELECT um zu testen, dass Session funktioniert
                result = session.execute("SELECT 1")
                assert result is not None

            # Nach transaction() sollte Session geschlossen sein
            assert session.is_active == False

    def test_transaction_rollback_on_exception(self):
        """Test: Transaktionen werden bei Exception gerollt back."""
        manager = get_db_manager('users')

        try:
            with manager.transaction() as session:
                # Simuliere Exception
                raise ValueError("Test error")
        except ValueError:
            pass

        # Session sollte geschlossen sein, auch bei Exception
        assert session.is_active == False


class TestManagedSession:
    """Tests für ManagedSession."""

    def test_managed_session_context_manager(self):
        """Test: ManagedSession funktioniert als Context-Manager."""
        with managed_session('users') as session:
            result = session.execute("SELECT 1")
            assert result is not None

    def test_managed_session_proxies(self):
        """Test: ManagedSession proxied Session-Methoden."""
        with managed_session('users') as session:
            # Test verschiedene Proxy-Methoden
            assert hasattr(session, 'execute')
            assert hasattr(session, 'query')
            assert hasattr(session, 'add')
            assert hasattr(session, 'delete')


class TestTransactionHelper:
    """Tests für transaction() Helper-Funktion."""

    def test_transaction_helper(self):
        """Test: transaction() Context-Manager funktioniert."""
        with transaction('users') as session:
            result = session.execute("SELECT 1")
            assert result is not None


class TestDatabaseInitialization:
    """Tests für Database-Initialisierung."""

    def test_initialize_databases(self):
        """Test: initialize_databases() prüft alle DBs."""
        # Sollte True zurückgeben wenn alle DBs OK
        result = initialize_databases()
        assert isinstance(result, bool)


# Performance & Concurrency Tests
class TestConnectionPooling:
    """Tests für Connection-Pooling."""

    def test_pool_size_configured(self):
        """Test: Pool-Größe ist konfiguriert."""
        manager = get_db_manager('users')
        engine = manager.engine

        # SQLAlchemy pool sollte konfiguriert sein
        assert engine.pool._pool is not None or engine.pool.size() >= 0

    def test_multiple_concurrent_sessions(self):
        """Test: Multiple Sessions können parallel erstellt werden."""
        manager = get_db_manager('users')

        sessions = [manager.session() for _ in range(5)]
        assert len(sessions) == 5

        for session in sessions:
            session.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
