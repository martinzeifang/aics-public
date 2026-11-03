"""Eingebettetes Dev-PostgreSQL (Docker-frei, Windows + Linux + macOS).

Nach der SQLite→PostgreSQL-Migration (#15) braucht auch der lokale Test ein
Postgres. Damit Entwickler **kein Docker und kein System-PostgreSQL** installieren
müssen, startet dieser Helfer bei Bedarf eine eingebettete PostgreSQL-Instanz über
das `pgserver`-Paket (gebündelte PG-Binaries, läuft ohne root) und setzt
``DATABASE_URL`` darauf.

Greift NUR, wenn ``DATABASE_URL`` nicht bereits gesetzt ist — in Produktion
(Container mit echtem Postgres) passiert hier also nichts. Die Daten liegen unter
``data/pg-dev`` (gitignored) und bleiben über Neustarts erhalten.

Aktivierung: ``from shared.dev_postgres import ensure_dev_database_url`` VOR dem
ersten Import von ``server.app`` aufrufen (siehe ``run_dev.py``).
"""
from __future__ import annotations

import os
from pathlib import Path

# Server-Handle festhalten, damit die Instanz nicht vorzeitig gestoppt wird.
_server = None


def ensure_dev_database_url() -> str | None:
    """Sorgt für ein nutzbares ``DATABASE_URL`` für den lokalen Lauf.

    - Ist ``DATABASE_URL`` gesetzt → unverändert zurückgeben (Prod/CI/Custom).
    - Sonst eingebettetes Postgres via ``pgserver`` starten und ``DATABASE_URL``
      darauf setzen. Ist ``pgserver`` nicht installiert, wird ``None`` geliefert
      (der Aufrufer zeigt dann einen klaren Hinweis).

    Returns: die genutzte DSN oder ``None``, wenn kein Embedded-Postgres möglich.
    """
    global _server

    existing = os.environ.get("DATABASE_URL")
    if existing:
        return existing

    try:
        import pgserver
    except ImportError:
        return None

    data_dir = Path(
        os.environ.get(
            "AICS_DEV_PGDATA",
            Path(__file__).resolve().parent.parent / "data" / "pg-dev",
        )
    )
    data_dir.mkdir(parents=True, exist_ok=True)

    # get_server ist idempotent: vorhandene Instanz wird wiederverwendet.
    _server = pgserver.get_server(str(data_dir))
    uri = _server.get_uri()
    os.environ["DATABASE_URL"] = uri
    return uri
