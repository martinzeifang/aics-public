"""Tests #1207: PSIRT-SLA-Tracking gegen offene CVEs.

- SLA-Text → strukturierte Dauer geparst.
- Soll-Fix-Datum + on_track/faellig/ueberfaellig pro offenem CVE.
- Aggregat-Endpoint /projekte/<p>/vuln/sla-status.
"""
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

CRA = '/api/cra'
FIRMA = 'pytest-firma-1207'
PROJ = 'pytest-cra-1207'


@pytest.fixture(autouse=True)
def _full_license():
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['*']
    yield
    cur.state, cur.modules = prev[0], prev[1]


def _ws_db() -> Path:
    db = Path('data/db') / f'pytest-1207-{uuid.uuid4().hex}.sqlite'
    db.parent.mkdir(parents=True, exist_ok=True)
    return db


def _cleanup(db: Path):
    for suffix in ('', '-wal', '-shm'):
        p = db.with_name(db.name + suffix)
        if p.exists():
            p.unlink()


def _set_discovered(db: Path, cve: str, iso: str):
    import sqlite3
    con = sqlite3.connect(str(db))
    con.execute("UPDATE cra_vuln SET discovered_at=? WHERE cve_id=?", (iso, cve))
    con.commit()
    con.close()


def test_compute_sla_overdue_and_ontrack():
    from cra.db import save_psirt, save_vuln
    from cra.sla_tracking import compute_sla_status
    db = _ws_db()
    try:
        save_psirt(db, PROJ, {'fix_sla_critical': '7 Tage', 'fix_sla_high': '30 Tage'})
        old = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        fresh = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        save_vuln(db, PROJ, {'cve_id': 'CVE-OLD', 'schwere': 'critical', 'status': 'open'})
        save_vuln(db, PROJ, {'cve_id': 'CVE-NEW', 'schwere': 'high', 'status': 'open'})
        save_vuln(db, PROJ, {'cve_id': 'CVE-FIXED', 'schwere': 'critical', 'status': 'fixed'})
        _set_discovered(db, 'CVE-OLD', old)
        _set_discovered(db, 'CVE-NEW', fresh)
        res = compute_sla_status(db, PROJ)
        assert res['psirt_set'] is True
        assert res['total_open'] == 2  # fixed nicht enthalten
        by_cve = {i['cve_id']: i for i in res['items']}
        assert by_cve['CVE-OLD']['status'] == 'ueberfaellig'   # 20d > 7d SLA
        assert by_cve['CVE-NEW']['status'] == 'on_track'        # 1d < 30d SLA
        assert res['violations'] == 1
    finally:
        _cleanup(db)


def test_sla_status_endpoint(client, auth_headers):
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)
    client.post(f'{CRA}/projekte', headers=auth_headers,
                json={'name': PROJ, 'unternehmen': FIRMA})
    r = client.get(f'{CRA}/projekte/{PROJ}/vuln/sla-status', headers=auth_headers)
    assert r.status_code == 200, r.json
    assert 'items' in r.json and 'violations' in r.json
    client.delete(f'{CRA}/projekte/{PROJ}', headers=auth_headers)
