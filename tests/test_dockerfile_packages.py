"""Das Image muss jedes Paket enthalten, das der Server importiert.

Anlass (v7.4.0): Das Dockerfile kopiert die Python-Pakete über eine **explizite
Positivliste** (``COPY --chown=aics:aics <paket>/ /app/<paket>/``). Beim neuen Modul
``compliance_audit`` wurde der Eintrag vergessen. Lokal lief alles — Tests, App-Start,
Frontend-Build —, weil dort der Quellbaum vollständig vorliegt. Im Image fehlte das
Paket, und **alle drei Instanzen** kamen nicht mehr hoch:

    File "/app/server/api/compliance_audit.py", line 52, in <module>
        from compliance_audit import db as audit_db
    ModuleNotFoundError: No module named 'compliance_audit'

Ein Importfehler beim Blueprint-Registrieren killt den gunicorn-Worker beim Boot, also
startet der Container gar nicht. Das ist der unangenehmste Fehlertyp: nichts am Code war
falsch, nur eine Liste war unvollständig — und keine der üblichen Prüfungen schaut auf
diese Liste.

Dieser Test schließt die Lücke, indem er die Positivliste gegen die tatsächlichen
Importe des Servers hält.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: Verzeichnisse, die keine importierbaren Python-Pakete des Servers sind.
IGNORIEREN = {
    'tests', 'frontend', 'docs', 'node_modules', 'data', 'out', 'scripts',
    'tools', 'build', 'dist', '.git', '.github', 'venv', '.venv', '__pycache__',
}

#: Einstiegspunkte, deren Importbaum im Image vorhanden sein muss.
EINSTIEGE = ('server', 'shared', 'wsgi.py', 'security_utils.py')


def _lokale_pakete() -> set[str]:
    """Top-Level-Pakete des Repos (Verzeichnis mit ``__init__.py``)."""
    out = set()
    for p in REPO.iterdir():
        if p.is_dir() and p.name not in IGNORIEREN and (p / '__init__.py').exists():
            out.add(p.name)
    return out


def _kopierte_pakete() -> set[str]:
    """Pakete, die das Dockerfile ins Image kopiert."""
    text = (REPO / 'Dockerfile').read_text()
    # COPY [--chown=...] <paket>/ /app/<paket>/
    return set(re.findall(r'^COPY\s+(?:--chown=\S+\s+)?([A-Za-z_][\w]*)/\s+/app/\1/\s*$',
                          text, re.MULTILINE))


def _dateien(einstieg: str):
    p = REPO / einstieg
    if p.is_file():
        yield p
    else:
        yield from p.rglob('*.py')


def _importierte_pakete(lokal: set[str]) -> dict[str, list[str]]:
    """Welches lokale Paket wird von welcher Datei importiert?

    Erfasst den **ganzen** AST, nicht nur die Modulebene: Die Suite importiert viel
    träge in Funktionen (``from compliance_audit import db``), und genau so ein
    Import hat v7.4.0 zu Fall gebracht.
    """
    treffer: dict[str, list[str]] = {}
    for einstieg in EINSTIEGE:
        for datei in _dateien(einstieg):
            try:
                baum = ast.parse(datei.read_text(encoding='utf-8'))
            except (SyntaxError, UnicodeDecodeError):  # pragma: no cover
                continue
            for knoten in ast.walk(baum):
                namen: list[str] = []
                if isinstance(knoten, ast.Import):
                    namen = [a.name for a in knoten.names]
                elif isinstance(knoten, ast.ImportFrom) and knoten.level == 0 and knoten.module:
                    namen = [knoten.module]
                for name in namen:
                    wurzel = name.split('.', 1)[0]
                    if wurzel in lokal:
                        treffer.setdefault(wurzel, []).append(
                            str(datei.relative_to(REPO)))
    return treffer


def test_dockerfile_kopiert_jedes_importierte_paket():
    """Kein Paket darf importiert werden, das im Image fehlt."""
    lokal = _lokale_pakete()
    kopiert = _kopierte_pakete()
    importiert = _importierte_pakete(lokal)

    fehlend = {pkg: sorted(set(dateien))[:3]
               for pkg, dateien in importiert.items()
               if pkg not in kopiert and pkg not in ('server', 'shared')}

    assert not fehlend, (
        'Diese Pakete werden vom Server importiert, fehlen aber im Dockerfile '
        '(COPY ...) — der Container startet damit nicht:\n' +
        '\n'.join(f'  {pkg}: importiert u. a. in {", ".join(d)}'
                  for pkg, d in sorted(fehlend.items())) +
        '\n\nFix: je Paket eine Zeile '
        '"COPY --chown=aics:aics <paket>/ /app/<paket>/" ins Dockerfile.'
    )


def test_dockerfile_kopiert_keine_verschwundenen_pakete():
    """Umgekehrt: eine COPY-Zeile ohne Paket im Repo lässt den Build scheitern."""
    kopiert = _kopierte_pakete()
    lokal = _lokale_pakete()
    verwaist = sorted(p for p in kopiert if not (REPO / p).is_dir())
    assert not verwaist, (
        f'Dockerfile kopiert nicht vorhandene Verzeichnisse: {verwaist}')
    # Sanity: die Erkennung funktioniert überhaupt.
    assert 'server' in kopiert and 'shared' in kopiert
    assert lokal, 'keine lokalen Pakete erkannt — Erkennung kaputt?'


def test_compliance_audit_ist_im_image():
    """Regression zum konkreten Vorfall (v7.4.0)."""
    assert 'compliance_audit' in _kopierte_pakete()
