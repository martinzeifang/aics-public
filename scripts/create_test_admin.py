#!/usr/bin/env python3
"""Legt einen dedizierten Test-Admin an (idempotent) — OHNE öffentliche
Default-Credentials.

Hintergrund: Der Demo-Login (admin@example.com / admin-password) ist öffentlich
bekannt und wird in FLASK_ENV=production bewusst NICHT angelegt (#744-Härtung).
Dieses Skript erzeugt stattdessen ein eigenes Admin-Konto mit selbst gewähltem
Passwort — geeignet für Test-Anmeldungen auf localhost UND auf produktiven
Hosts (docker02), ohne die Härtung aufzuweichen.

Aufruf (Passwort NIE als Argument — nur per ENV, damit es nicht in der
Shell-History/Prozessliste landet):

    TEST_ADMIN_EMAIL=testadmin@aics.local \\
    TEST_ADMIN_PASSWORD='<starkes-passwort>' \\
    python scripts/create_test_admin.py

Im Container analog:

    docker exec -i -e TEST_ADMIN_EMAIL=... -e TEST_ADMIN_PASSWORD='...' \\
        <container> python scripts/create_test_admin.py

Optional: TEST_ADMIN_DB (Pfad zur users.sqlite), TEST_ADMIN_ROLES (CSV,
Default 'admin').
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Repo-Root in den Importpfad (Skript kann von überall laufen).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.auth.users_db import (  # noqa: E402
    DEFAULT_DB_PATH,
    create_user,
    get_user_by_email,
    update_user,
)


def main() -> int:
    email = (os.environ.get('TEST_ADMIN_EMAIL') or 'testadmin@aics.local').strip().lower()
    password = os.environ.get('TEST_ADMIN_PASSWORD') or ''
    roles = [r.strip() for r in os.environ.get('TEST_ADMIN_ROLES', 'admin').split(',') if r.strip()]
    db_path = Path(os.environ['TEST_ADMIN_DB']) if os.environ.get('TEST_ADMIN_DB') else DEFAULT_DB_PATH

    if not password or len(password) < 12:
        print('FEHLER: TEST_ADMIN_PASSWORD muss gesetzt sein (>= 12 Zeichen).',
              file=sys.stderr)
        return 2

    existing = get_user_by_email(email, db_path=db_path)
    if existing:
        update_user(existing['id'], password=password, roles=roles,
                    active=True, db_path=db_path)
        action = 'aktualisiert'
    else:
        create_user(email=email, password=password, roles=roles,
                    display_name='Test-Admin', db_path=db_path)
        action = 'angelegt'

    # Passwort NICHT ausgeben — nur Bestätigung.
    print(f'Test-Admin {action}: {email} (roles={roles}) in {db_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
