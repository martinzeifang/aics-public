"""#1066 — Word-Vorlagen-Lesepfad darf auf frischer DB nicht 500en
(template_registry wird via ensure_db im Lese-Pfad angelegt)."""
from pathlib import Path

import pytest

from shared.templates import db as tdb

# DB-Pfade müssen innerhalb des Repo-Roots liegen (security_utils.ensure_within_root).
_DB_DIR = Path("data/db")


@pytest.fixture
def fresh_db():
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    p = _DB_DIR / "_pytest_templates_1066.sqlite"
    for suffix in ("", "-wal", "-shm"):
        Path(str(p) + suffix).unlink(missing_ok=True)
    yield p
    for suffix in ("", "-wal", "-shm"):
        Path(str(p) + suffix).unlink(missing_ok=True)


def test_list_templates_on_fresh_db_returns_empty(fresh_db):
    # Kein vorheriger Upload/ensure_db — frühere Version warf hier OperationalError
    assert tdb.list_templates(fresh_db) == []
    assert tdb.list_templates(fresh_db, modul="cra") == []


def test_get_template_on_fresh_db_returns_none(fresh_db):
    assert tdb.get_template(fresh_db, 123) is None
