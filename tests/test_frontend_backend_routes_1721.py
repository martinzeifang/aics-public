"""Jeder Frontend-API-Aufruf muss eine Backend-Route haben (#1721).

Anlass: Bei der Modultrennung (#1713) sind die Audit-Endpunkte von
``/api/gutachten/...`` nach ``/api/compliance-audit/...`` gewandert. View und Store
des Audits habe ich umgestellt, die Admin-Seite **Framework-Bibliothek** aber
übersehen — sie rief weiter ``/gutachten/frameworks`` auf. Ergebnis: „Not Found"
auf der Seite, und ohne eingelesenen Framework-Korpus ließ sich das neue Modul
überhaupt nicht benutzen.

Kein bestehender Test konnte das finden: Die Backend-Tests prüfen Routen, die
Frontend-Prüfung ist ein Typecheck, und beide sehen die Verbindung nicht. Dieser
Test schließt die Lücke, indem er die tatsächlich aufgerufenen Pfade gegen die
registrierte Flask-URL-Map hält.

Vergleich segmentweise: Ein ``${...}``-Platzhalter im Frontend und ein
``<converter>`` im Backend gelten als Treffer für ein beliebiges Segment, ein
``<path:...>`` schluckt mehrere. So bleibt der Test tolerant gegen dynamisch
gebaute Pfade, erkennt aber ein falsches **Prefix** — und genau das war der Fehler.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FRONTEND = REPO / 'frontend/src'

#: Pfade, die sich statisch nicht auflösen lassen (Segment wird erst zur Laufzeit
#: zusammengesetzt). Jeder Eintrag braucht eine Begründung — die Liste ist ein
#: Zugeständnis, kein Sammelbecken.
BEKANNTE_AUSNAHMEN = {
    # Der Bereichsname wird aus einer Variable gebaut (`/dsgvo-${area}/...`),
    # der Prefix entsteht also erst zur Laufzeit.
    '/api/X',
}


def _segmente(pfad: str) -> list[str]:
    return [s for s in pfad.strip('/').split('/') if s != '']


def _frontend_aufrufe() -> dict[str, set[str]]:
    """``/api/...``-Pfade je Quelldatei, Platzhalter als ``*`` normalisiert."""
    out: dict[str, set[str]] = {}
    muster = re.compile(r"""apiClient\.\w+\(\s*[`'"]([^`'"]+)""")
    for datei in FRONTEND.rglob('*.*'):
        if datei.suffix not in ('.ts', '.vue'):
            continue
        txt = datei.read_text(encoding='utf-8', errors='replace')
        for m in muster.finditer(txt):
            roh = m.group(1)
            if not roh.startswith('/'):
                continue
            # Template-Ausdrücke → Platzhalter; Query/Fragment abschneiden.
            pfad = re.sub(r'\$\{[^}]*\}', '*', roh).split('?')[0].split('#')[0]
            pfad = '/api' + pfad.rstrip('/')
            # Ein Platzhalter kann Teil eines Segments sein ("docx*") — das ist
            # dann ein Wildcard-Segment.
            pfad = '/'.join('*' if '*' in s else s for s in pfad.split('/'))
            out.setdefault(pfad, set()).add(str(datei.relative_to(FRONTEND)))
    return out


def _backend_routen() -> list[list[str]]:
    """Segmentlisten aller registrierten Routen; Converter als ``*``/``**``."""
    from server.app import create_app

    app = create_app()
    routen = []
    for regel in app.url_map.iter_rules():
        segs = []
        for s in _segmente(str(regel)):
            if s.startswith('<') and s.endswith('>'):
                segs.append('**' if s.startswith('<path:') else '*')
            else:
                segs.append(s)
        routen.append(segs)
    return routen


def _passt(aufruf: list[str], route: list[str]) -> bool:
    """Segmentweiser Vergleich; ``**`` schluckt den Rest."""
    if route and route[-1] == '**':
        if len(aufruf) < len(route) - 1:
            return False
        route, aufruf = route[:-1], aufruf[:len(route) - 1]
    if len(aufruf) != len(route):
        return False
    return all(a == b or a == '*' or b == '*' for a, b in zip(aufruf, route))


@pytest.fixture(scope='module')
def routen():
    return _backend_routen()


def test_jeder_frontend_aufruf_hat_eine_route(routen):
    aufrufe = _frontend_aufrufe()
    assert len(aufrufe) > 300, f'nur {len(aufrufe)} Aufrufe gefunden — Erkennung kaputt?'

    fehlend: dict[str, set[str]] = {}
    for pfad, dateien in aufrufe.items():
        if pfad in BEKANNTE_AUSNAHMEN:
            continue
        if not any(_passt(_segmente(pfad), r) for r in routen):
            fehlend[pfad] = dateien

    assert not fehlend, (
        'Diese Frontend-Aufrufe haben keine Backend-Route — die Oberfläche läuft '
        'dort in „Not Found":\n' +
        '\n'.join(f'  {p}\n      {", ".join(sorted(d))}'
                  for p, d in sorted(fehlend.items())))


def test_erkennung_findet_einen_falschen_pfad(routen):
    """Gegenprobe: Der Test muss ein falsches Prefix überhaupt melden können.

    Ohne diese Zusicherung könnte der Matcher so tolerant sein, dass er alles
    durchlässt — und der Test wäre wertlos.
    """
    assert not any(_passt(_segmente('/api/gutachten/frameworks'), r) for r in routen), \
        ('/api/gutachten/frameworks darf es nicht mehr geben — die Framework-Bibliothek '
         'gehört seit #1713 zum Compliance-Audit.')
    assert any(_passt(_segmente('/api/compliance-audit/frameworks'), r) for r in routen), \
        'die Framework-Bibliothek muss unter /api/compliance-audit/frameworks liegen'


def test_framework_bibliothek_zeigt_auf_das_audit():
    """Die Admin-Seite muss die verschobenen Endpunkte nutzen (#1721)."""
    view = (FRONTEND / 'views/admin/FrameworksView.vue').read_text()
    assert '/gutachten/frameworks' not in view, \
        'FrameworksView.vue ruft noch die alten Gutachten-Pfade auf'
    assert view.count('/compliance-audit/frameworks') >= 4, \
        'FrameworksView.vue muss Liste, Download, Ingest und Upload über das Audit aufrufen'
