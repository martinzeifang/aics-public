"""Die vier Funde des Funktionstests vom 25.10.2026 (#1814–#1817).

Gefunden beim systematischen Durchlauf über alle Module (Firefox + REST,
107 Schritte, 97 Screenshots). Jeder Fund war reproduzierbar belegt, bevor er
hier festgehalten wurde — die Tests beschreiben den Zustand nach dem Fix und
lassen rot werden, wer ihn rückgängig macht.

Der schwerste Fund (#1814) hat seinen eigenen Test:
``tests/test_doc_pflichtfelder_1814.py``.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


# ── #1815 · Fehlende Konfiguration ist kein Serverfehler ────────────────────

def test_issue_backend_hat_eigenen_fehlertyp():
    """Ohne Token endete „Issue anlegen" in HTTP 500.

    Die Issue-Anlage steht in mehreren Modulen (cra, nis2, aiact, dsgvo …).
    Alle einzeln zu reparieren wäre die nächste Spiegel-Liste (#1731/#1735) —
    deshalb ein eigener Fehlertyp in der VCS-Schicht und **ein** Handler.
    """
    from vcs.errors import IssueBackendFehlt
    assert issubclass(IssueBackendFehlt, RuntimeError), \
        "Muss von RuntimeError erben — bestehende Aufrufer fangen den weiter"

    gh = Path("vcs/github_issues.py").read_text(encoding="utf-8")
    gl = Path("vcs/gitlab_issues.py").read_text(encoding="utf-8")
    assert "IssueBackendFehlt" in gh, "GitHub wirft den Typ nicht"
    assert "IssueBackendFehlt" in gl, "GitLab wirft den Typ nicht"


def test_app_liefert_412_statt_500():
    quelle = Path("server/app.py").read_text(encoding="utf-8")
    assert "IssueBackendFehlt" in quelle, "Kein Handler für den Fehlertyp"
    stelle = quelle[quelle.index("IssueBackendFehlt"):][:900]
    assert "412" in stelle, "Der Handler liefert keinen 412"
    assert "issue-tracker-nicht-konfiguriert" in quelle, \
        "Die Antwort trägt keinen maschinenlesbaren Code"


def test_fehlertext_nennt_die_loesung():
    """Die Meldung muss sagen, was zu tun ist — sie erreichte den Anwender nie."""
    from vcs.errors import IssueBackendFehlt
    import vcs.github_issues as gh

    monkey = getattr(gh, "_token", None)
    assert monkey is not None
    # Ohne Token und ohne CLI muss der Typ fliegen, nicht ein nackter RuntimeError.
    import shutil
    import unittest.mock as mock
    with mock.patch.object(gh, "_token", return_value=""), \
         mock.patch.object(shutil, "which", return_value=None):
        with pytest.raises(IssueBackendFehlt) as e:
            gh.create_issue(repo="owner/name", title="t", body="b")
    text = str(e.value)
    assert "Issue-Tracker" in text and "konfiguriert" in text, text


# ── #1816 · Kein eval/new Function unter der CSP ────────────────────────────

def test_i18n_ohne_laufzeit_compiler():
    """vue-i18n übersetzte Nachrichten mit `new Function()` — die CSP verbietet das."""
    idx = Path("frontend/src/i18n/index.ts").read_text(encoding="utf-8")
    assert "alsFunktionen" in idx, \
        "Die Nachrichten werden nicht mehr als Funktionen übergeben"

    vite = Path("frontend/vite.config.ts").read_text(encoding="utf-8")
    assert "vue-i18n.runtime.esm-bundler" in vite, \
        "Der Alias auf den Runtime-Build fehlt — der Compiler landet wieder im Bundle"


def test_platzhalter_brauchen_keinen_laufzeit_compiler():
    """Hier stand bis 8.3.4 das Gegenteil — und das war richtig, bis es das nicht mehr war.

    Der ursprüngliche Test verlangte, dass **kein** Text einen `{name}`
    enthält: Eine fertige Funktion `() => 'Speichern'` kann keinen Platzhalter
    füllen, und der Dateikopf nannte als Ausweg die Vorkompilierung über
    `@intlify/unplugin-vue-i18n`.

    Mit #1954 ist die Voraussetzung entfallen, aber **nicht** durch die
    Vorkompilierung. `frontend/src/i18n/kompilierer.ts` setzt Platzhalter aus
    Textstücken zusammen, ohne eine Zeile Code zu erzeugen — damit bleibt die
    Zusicherung aus #1816 (kein `new Function` unter `script-src 'self'`)
    unangetastet, ohne eine neue Abhängigkeit, die gegen Vite 8/Rolldown zu
    erproben wäre.

    Der alte Test hätte die Übersetzung blockiert; ihn einfach zu löschen
    hätte den CSP-Schutz mitgenommen. Also prüft er jetzt die Stelle, die
    tatsächlich trägt: dass der Kompilierer existiert und keinen Code erzeugt.
    Die Kataloge selbst (Parität, Platzhalter-Gleichheit, Pluralzweige,
    benutzte Schlüssel) sind Sache von `tests/test_i18n_katalog_1954.py`.
    """
    komp = Path("frontend/src/i18n/kompilierer.ts")
    assert komp.is_file(), (
        "frontend/src/i18n/kompilierer.ts fehlt — ohne ihn können die "
        "Nachrichten keine Platzhalter füllen (#1954)")
    quelle = komp.read_text(encoding="utf-8")
    # Kommentare weg: das Programm prüfen, nicht die Erzählung (#1834/#1867).
    quelle = re.sub(r"/\*(?:.|\n)*?\*/", "", quelle)
    quelle = re.sub(r"(?m)^\s*//.*$", "", quelle)
    for verboten in ("new Function", "eval(", "Function("):
        assert verboten not in quelle, (
            f"kompilierer.ts enthält {verboten!r} — die CSP erlaubt kein "
            "unsafe-eval (#1816)")
    assert "alsFunktionen" in quelle, \
        "kompilierer.ts liefert `alsFunktionen` nicht mehr"


def test_csp_erlaubt_weiterhin_kein_unsafe_eval():
    """Die Härtung bleibt — der Fix war, den Verstoß zu beseitigen, nicht ihn zu erlauben."""
    conf = Path("docker/nginx.conf").read_text(encoding="utf-8")
    csp = re.search(r"Content-Security-Policy[^;]*;.*?(?=\"|\n)", conf, re.S)
    if csp:
        assert "unsafe-eval" not in csp.group(0), \
            "unsafe-eval wurde in die CSP aufgenommen — das war ausdrücklich nicht der Weg"


# ── #1817 · Meldung nennt die wahre Ursache ────────────────────────────────

def test_wiba_meldung_unterscheidet_projekt_und_katalog():
    """„Bitte ein Projekt auswählen", während eines gewählt ist — in Wahrheit
    fehlte der BSI-Katalog. Eine Wegbeschreibung, die ins Leere führt."""
    for datei in ("frontend/src/views/wiba/PrueffragenPanel.vue",
                  "frontend/src/views/wiba/DokumentationPanel.vue"):
        text = Path(datei).read_text(encoding="utf-8")
        assert "selectedProjekt" in text, f"{datei}: unterscheidet die Fälle nicht"
        assert "Katalog" in text, f"{datei}: nennt den Katalog nicht als Ursache"
        assert "Keine Prüffragen geladen — bitte zuerst ein Projekt auswählen." not in text
        assert "Keine Themen geladen — bitte zuerst ein Projekt auswählen." not in text


def test_wiba_verweis_nur_mit_berechtigung():
    """Ein Link auf den Katalog-Import, den das Konto nicht ausführen darf,
    wäre die nächste Sackgasse."""
    text = Path("frontend/src/views/wiba/PrueffragenPanel.vue").read_text(encoding="utf-8")
    assert "darfKatalog" in text
    assert "wiba:catalog" in text
