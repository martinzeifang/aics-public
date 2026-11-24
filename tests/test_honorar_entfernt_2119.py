"""#2119 — Honorar ist aus der Suite entfernt (Code; Daten via Ops-Skript).

Guard in beide Richtungen: das Thema taucht im Produktionscode nicht mehr auf,
und die ehemaligen Endpunkte sind weg. Das Ops-Skript (bewusster, von Hand
auszuführender Datenlöscher) ist ausgenommen.
"""
import pathlib
import re


WURZEL = pathlib.Path(__file__).resolve().parent.parent
# Begriffe, die das Honorar-Thema tragen.
BEGRIFFE = re.compile(r"honorar|gutachten_zeitbuch|JVEG|rechnung\.pdf|build_rechnung",
                      re.IGNORECASE)
# Bewusste Ausnahmen: der Datenlöscher und dieser Test selbst.
AUSNAHMEN = {
    "scripts/ops/honorar_entfernen.py",
    "tests/test_honorar_entfernt_2119.py",
}


def _dateien():
    for muster in ("gutachten/**/*.py", "server/**/*.py", "shared/**/*.py",
                   "compliance_audit/**/*.py",
                   "frontend/src/**/*.vue", "frontend/src/**/*.ts"):
        for f in WURZEL.glob(muster):
            rel = f.relative_to(WURZEL).as_posix()
            if rel in AUSNAHMEN or "/node_modules/" in rel:
                continue
            yield rel, f


def test_honorar_py_ist_weg():
    assert not (WURZEL / "gutachten" / "honorar.py").exists()


def test_kein_honorar_im_produktionscode():
    treffer = []
    for rel, f in _dateien():
        try:
            txt = f.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in BEGRIFFE.finditer(txt):
            zeile = txt[:m.start()].count("\n") + 1
            treffer.append(f"{rel}:{zeile}  {m.group(0)}")
    assert not treffer, "Honorar-Reste im Code:\n" + "\n".join(treffer)


def test_honorar_endpunkte_sind_weg(client, auth_headers):
    from server import license_state
    cur = license_state._current
    prev = (cur.state, list(cur.modules))
    cur.state, cur.modules = 'ok', ['gutachten']
    try:
        for pfad in ('/api/gutachten/honorar/eintraege',
                     '/api/gutachten/honorar/kategorien',
                     '/api/gutachten/honorar/summary'):
            r = client.get(pfad, headers=auth_headers)
            assert r.status_code == 404, (pfad, r.status_code)
        r = client.get('/api/gutachten/gerichts/Demo/rechnung.pdf', headers=auth_headers)
        assert r.status_code == 404, r.status_code
    finally:
        cur.state, cur.modules = prev[0], prev[1]
