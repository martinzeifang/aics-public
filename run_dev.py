#!/usr/bin/env python3
"""Development Server Entry Point.

Startet Flask-Entwicklungsserver mit HTTPS und Hot-Reload.

Usage:
    python run_dev.py              # Auf https://localhost:5000
    python run_dev.py --port 8000
    python run_dev.py --http       # HTTP nur für dev (unsicher!)
"""

import argparse
import os
from pathlib import Path

# Dev-Server = Testumgebung: Testuser + Test-Banner standardmäßig aktiv.
# setdefault → explizite Vorgaben (z.B. aus start-dev.sh oder Shell) gewinnen.
# MUSS vor dem Import von server.app stehen, da dieser beim Import bereits
# die users-DB initialisiert (und Demo-User idempotent seedet).
os.environ.setdefault('ENABLE_DEMO_USERS', 'true')
os.environ.setdefault('FLASK_ENV', 'development')
# Dev-Komfort: Config-Integritäts-Sidecar bei lokalen/Out-of-band-Änderungen automatisch
# reparieren statt fail-closed (500). Prod-Stacks setzen das ebenfalls; lokal sonst bricht
# jeder direkte Edit an ai_compliance_suite.config.json die Settings-Endpoints.
os.environ.setdefault('AICS_CONFIG_AUTO_REPAIR_SIDECAR', '1')

# Nach der PostgreSQL-Migration (#15) braucht auch der lokale Lauf ein Postgres.
# Ist DATABASE_URL nicht gesetzt, wird ein eingebettetes Dev-Postgres (pgserver,
# Docker-frei, Windows + Linux) gestartet. MUSS vor dem server.app-Import stehen,
# da dieser beim Import bereits die DB anspricht.
if not os.environ.get('DATABASE_URL'):
    try:
        from shared.dev_postgres import ensure_dev_database_url
        _dsn = ensure_dev_database_url()
        if _dsn:
            print('🐘 Eingebettetes Dev-Postgres aktiv (data/pg-dev)')
        else:
            print('⚠ Kein DATABASE_URL und pgserver nicht installiert — '
                  'bitte `pip install pgserver` oder DATABASE_URL setzen.')
    except Exception as _exc:  # pragma: no cover - nur Dev-Komfort
        print(f'⚠ Eingebettetes Dev-Postgres nicht gestartet: {_exc!r}')

from server.app import create_app
from server.ssl import ensure_ssl_certs


def main():
    parser = argparse.ArgumentParser(description='Run development server')
    parser.add_argument('--host', default='localhost', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', default=True, help='Enable debug mode')
    parser.add_argument('--http', action='store_true', help='Run on HTTP (insecure, dev only)')
    args = parser.parse_args()

    app = create_app()

    # Setup HTTPS (generate self-signed certs if needed)
    protocol = 'http' if args.http else 'https'
    ssl_context = None

    if not args.http:
        cert_dir = Path(__file__).parent / 'certs'
        cert_path, key_path = ensure_ssl_certs(cert_dir)
        ssl_context = (str(cert_path), str(key_path))
        print(f"\n🔒 HTTPS enabled with self-signed certificate")
        print(f"   ⚠️  Browser will show certificate warning (expected in dev)")

    print(f"\n🚀 Starting Flask dev server on {protocol}://{args.host}:{args.port}")
    print(f"   Frontend proxy: {protocol}://localhost:5173 → {protocol}://localhost:{args.port}/api")
    print(f"   Login: {protocol}://{args.host}:{args.port}")
    print()

    # Werkzeug-Reloader: nur Source-Änderungen triggern Reload.
    # Datenverzeichnisse, Logs, Backups, generierte Files ausschließen — sonst
    # killen Backup-Erstellung, SQLite-WAL-Updates etc. den laufenden Request
    # mid-action. `exclude_patterns` sind fnmatch-Patterns gegen abs. Pfade.
    workspace = str(Path(__file__).parent.resolve())
    exclude_patterns = [
        f'{workspace}/data/*', f'{workspace}/data/**/*',
        f'{workspace}/logs/*',
        f'{workspace}/out/*',  f'{workspace}/out/**/*',
        f'{workspace}/var/*',  f'{workspace}/var/**/*',
        f'{workspace}/backups/*',
        f'{workspace}/certs/*',
        f'{workspace}/frontend/node_modules/*', f'{workspace}/frontend/node_modules/**/*',
        f'{workspace}/frontend/dist/*',
        f'{workspace}/site/*',
        # Spezifisch das __pycache__ und reload-trigger-Files
        f'{workspace}/**/__pycache__/*',
        f'{workspace}/**/*.pyc',
    ]

    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=True,
        ssl_context=ssl_context,
        exclude_patterns=exclude_patterns,
        # Mehrere gleichzeitige Requests bedienen (das SPA feuert beim
        # Projektwechsel 6+ parallele Calls). Ohne threaded blockiert ein
        # langsamer/hängender Request (z.B. Lizenz-Heartbeat) alle anderen →
        # Status-0/Timeouts, Speichern „hängt". Prod nutzt gunicorn gthread.
        threaded=True,
    )


if __name__ == '__main__':
    main()
