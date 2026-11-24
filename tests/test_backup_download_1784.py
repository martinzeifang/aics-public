"""Backups sind herunterladbar — und der Abzug steht im Revisionspfad (#1784).

Die Backup-Verwaltung konnte ein Archiv **erstellen** (`POST /backup`), eines
**hochladen** (`POST /backup/upload`, #356) und daraus **wiederherstellen** —
aber nicht herunterladen. Damit lag jede Sicherung genau dort, wo auch die Daten
liegen: im Container bzw. auf demselben Volume. Gegen einen Volume- oder
Hardware-Verlust half sie nicht, und genau dafür legt man sie an. Herausholen
ließ sich die Datei nur über eine Shell im Container — ein Weg, den ein
Administrator in einer gehosteten Installation nicht hat.

Zwei Zusagen hält dieses Modul fest:

* Die heruntergeladene Datei ist dieselbe, die der Upload wieder annimmt — der
  Weg führt also zurück. Ein Backup, das man exportieren aber nicht
  reimportieren kann, wäre eine Attrappe.
* Der Download erzeugt einen Audit-Eintrag **mit Akteur**. Der Abzug enthält
  alle Modul-Datenbanken samt Benutzertabelle; wer eine vollständige Kopie des
  Datenbestands aus dem Haus trägt, ist die Frage, die nach einem Vorfall
  gestellt wird. ``shared.audit.audit_event`` trägt den Handelnden *nicht* von
  selbst nach (``actor`` kommt aus ``details['user_id']``) — ohne das Feld
  stünde dort „irgendwer".
"""
from __future__ import annotations

import io
import uuid
import zipfile

import pytest


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    """Eigenes Ablageverzeichnis — der Test schreibt nicht in ``out/backup``."""
    from server.api import admin as admin_api

    ziel = tmp_path / 'backup'
    ziel.mkdir()
    monkeypatch.setattr(admin_api, 'BACKUP_DIR', ziel)
    return ziel


@pytest.fixture
def backup_id(backup_dir):
    """Ein abgelegtes Backup in der Struktur, die auch ``create_backup`` erzeugt.

    Absichtlich nicht über ``POST /backup``: Das Erstellen liest am Ende die
    Live-Config (Retention) und hängt damit an einem Zustand, der mit dem
    Herunterladen nichts zu tun hat.
    """
    bid = 'backup_20261023_120000'
    with zipfile.ZipFile(backup_dir / f'{bid}.zip', 'w') as zf:
        zf.writestr('MANIFEST.json', '{"version": "1.0.0"}')
        zf.writestr('data/db/users.sqlite', b'SQLite format 3\x00' + b'\x00' * 64)
    return bid


def test_backup_laesst_sich_herunterladen(client, auth_headers, backup_id):
    res = client.get(f'/api/admin/backup/{backup_id}/download',
                     headers=auth_headers)
    assert res.status_code == 200, res.get_data(as_text=True)
    assert res.mimetype == 'application/zip'
    # Als Anhang, mit dem Namen des Archivs — sonst zeigt der Browser Binärmüll.
    cd = res.headers.get('Content-Disposition', '')
    assert 'attachment' in cd and f'{backup_id}.zip' in cd

    with zipfile.ZipFile(io.BytesIO(res.data)) as zf:
        namen = zf.namelist()
    assert any(n.lower() == 'manifest.json' for n in namen)
    assert any(n.startswith('data/db/') and n.endswith('.sqlite') for n in namen)


def test_der_weg_fuehrt_zurueck(client, auth_headers, backup_id):
    """Download → Upload. Sonst wäre der Export eine Einbahnstraße."""
    runter = client.get(f'/api/admin/backup/{backup_id}/download',
                        headers=auth_headers)
    assert runter.status_code == 200

    res = client.post(
        '/api/admin/backup/upload',
        data={'file': (io.BytesIO(runter.data), 'mein-backup.zip')},
        content_type='multipart/form-data', headers=auth_headers)
    assert res.status_code == 201, res.get_data(as_text=True)
    assert res.get_json()['uploaded'] is True


def test_download_steht_mit_akteur_im_audit(client, auth_headers, backup_id):
    client.get(f'/api/admin/backup/{backup_id}/download', headers=auth_headers)

    res = client.get('/api/admin/audit/events?action=admin.backup.downloaded',
                     headers=auth_headers)
    assert res.status_code == 200, res.get_data(as_text=True)
    treffer = res.get_json().get('events') or []
    assert treffer, 'Der Abzug des Datenbestands muss im Revisionspfad stehen.'
    jung = treffer[0]
    # Ohne Akteur beantwortet der Eintrag die Frage nicht, für die er da ist.
    assert jung.get('actor'), 'Audit-Eintrag ohne Akteur ist wertlos.'
    assert backup_id in str(jung.get('details') or '')


def test_gruppenaenderung_nennt_den_akteur(client, auth_headers):
    """Gegenprobe zum gemeinsamen Helfer (#1779).

    ``_audit_gruppe`` versprach im Docstring „wer wann wem welche Rechte gegeben
    hat" und gab das Feld nicht mit — der Eintrag nannte die Gruppe, nicht den
    Entscheider. Beide Wege laufen jetzt über ``_audit_admin``.
    """
    # Eindeutiger Name: Das ``users``-Schema überlebt die Test-Isolation
    # (``_pg_isolate`` lässt users/audit/scheduler stehen), ein fester Name
    # kollidierte also beim zweiten Lauf mit sich selbst.
    name = f'pytest-akteur-1784-{uuid.uuid4().hex[:8]}'
    res = client.post('/api/admin/groups',
                      json={'name': name, 'roles': ['viewer']},
                      headers=auth_headers)
    assert res.status_code == 201, res.get_data(as_text=True)
    gid = res.get_json().get('id')
    try:
        res = client.get('/api/admin/audit/events?action=admin.group.created',
                         headers=auth_headers)
        treffer = res.get_json().get('events') or []
        assert treffer and treffer[0].get('actor')
    finally:
        client.delete(f'/api/admin/groups/{gid}', headers=auth_headers)


def test_fremde_pfade_kommen_nicht_durch(client, auth_headers, backup_dir):
    """Aus der ID entsteht ein Dateiname — Positivliste, nicht Negativliste."""
    for boese in ('nicht_backup', 'backup_..', 'backup_../../etc/passwd',
                  'backup_%2e%2e'):
        res = client.get(f'/api/admin/backup/{boese}/download',
                         headers=auth_headers)
        # 400 (ID abgelehnt) oder 404 (Routing greift schon) — nur nie 200.
        assert res.status_code in (400, 404), f'{boese} → {res.status_code}'


def test_unbekanntes_backup_meldet_404(client, auth_headers, backup_dir):
    res = client.get('/api/admin/backup/backup_20200101_000000/download',
                     headers=auth_headers)
    assert res.status_code == 404


def test_download_braucht_das_recht(client):
    """Ohne Anmeldung kein Vollabzug."""
    res = client.get('/api/admin/backup/backup_20200101_000000/download')
    assert res.status_code in (401, 422)
