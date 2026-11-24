"""Die Desktop-Variante ist entfernt — und bleibt es (#1955).

Ausgeliefert wird nur noch das Webprodukt. Entfernt sind die vier reinen
Desktop-Module (``baso``, ``ict``, ``compliance``, ``compliance_db``), die
Tkinter-Oberflächen der Web-Module (``*/gui_module.py`` und die Panels und
Dialoge darunter), die Suite-Oberfläche samt ihrer eigenen
Authentifizierung/Lizenz/Backup, der Weiß-Etikett-Starter, die
Tk-Viewer in ``shared/``, ``vcs/issue_assistant.py``,
``prefill/review_dialog.py`` sowie die Starter und die Desktop-Integration.

**Dieser Test prüft beide Richtungen, und die zweite ist die wichtigere.** Ein
Rückbau, der nur „ist es weg?" prüft, hinterlässt genau die Art Schaden, die
niemand bemerkt, bis ein Kunde sie findet (die Lehre aus #1905):

* Die **Flask-App** muss weiter alle Blueprints registrieren, und jedes
  Web-Modul muss importierbar bleiben.
* Die **Lizenz-Modulliste** und die ``module_*``-Spalten in ``firmen`` dürfen
  sich nicht verändert haben — eine Firma, die CRA gebucht hat, muss CRA
  behalten.
* **``python -m cra sync-vulns``** muss weiter laufen: Das ist der Aufruf aus
  ``.github/workflows/cra-vuln-sync.yml`` (#937), und er steckte in einer
  Datei, die ohne Argumente die GUI startete.
* **``gutachten/file_download.py``** muss bleiben: Es kennt den Weg um die
  eur-lex-WAF, und ``shared/verordnungen.py`` (#1894) sowie
  ``server/api/compliance_audit.py`` rufen es auf. Nur der Tk-Dialog darüber
  ist weg.
* Die **OWASP-PC-C10-Fundstelle** der CRA-Eigenbewertung darf nicht verloren
  sein. Sie stand auf ``shared/errors.py``, und
  ``cra.local_code_analysis.analyze_local_codebase`` überspringt fehlende
  Dateien **stillschweigend** (``if not exists: continue``) — die Akte hätte
  den Nachweis lautlos verloren.

**Die #1779-Falle greift hier nicht**, und das ist belegt statt angenommen:
Die Desktop-Module hatten **nie** Rechte, Rollen oder Lizenz-Einträge in der
Webanwendung (siehe ``test_keine_rolle_musste_bereinigt_werden``). Beim SOC war
das anders — dort brauchte es ``ENTFERNTE_ROLLEN``, weil die
Benutzerverwaltung seit #1779 unbekannte Rollen beim **Schreiben** ablehnt und
betroffene Konten sonst nicht mehr speicherbar gewesen wären.

Was **nicht** entfernt ist und warum, steht in CLAUDE.md unter „Die
Desktop-Variante ist entfernt" — allen voran die Postgres-Schemata ``baso``,
``ict`` und ``compliance``: Ein ``DROP SCHEMA`` ist nicht umkehrbar, und was
dort liegt, sind Bestandsdaten einer Installation.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Die vier Desktop-Module.
DESKTOP_MODULE = ("baso", "ict", "compliance", "compliance_db")

#: Dateien und Verzeichnisse, die es nicht mehr geben darf.
WEG = (
    # Die vier Desktop-Module …
    "baso",
    "ict",
    "compliance",
    "compliance_db",
    # … samt ihrer toten Web-Oberfläche (nicht gegated, kein Frontend-Aufruf).
    "server/api/baso.py",
    "server/api/ict.py",
    # Die Tkinter-Oberflächen der Web-Module.
    "ai_act/gui_module.py",
    "cra/gui_module.py",
    "dsgvo/gui_module.py",
    "firmen/gui_module.py",
    "gutachten/gui_module.py",
    "nis2/gui_module.py",
    "risikobewertung/gui_module.py",
    "cra/_panel_anforderungen.py",
    "cra/_panel_dashboard.py",
    "cra/_panel_owasp.py",
    "gutachten/_download_dialog.py",
    "gutachten/_panel_gerichts.py",
    "gutachten/_panel_gutachten.py",
    "risikobewertung/_massen_dialog.py",
    # Die Suite-Oberfläche und ihre Desktop-eigenen Bausteine.
    "ai_compliance_suite/gui.py",
    "ai_compliance_suite/auth.py",
    "ai_compliance_suite/cli.py",
    "ai_compliance_suite/__main__.py",
    "ai_compliance_suite/backup.py",
    "ai_compliance_suite/license_state.py",
    "ai_compliance_suite/license_dialog.py",
    "ai_compliance_suite/_backup_dialog.py",
    # Tk-Werkzeuge.
    "shared/db_viewer.py",
    "shared/audit_viewer.py",
    "shared/errors.py",
    "vcs/issue_assistant.py",
    "prefill/review_dialog.py",
    "prefill/tk_ui",
    # Starter und Desktop-Integration.
    "start-suite.sh",
    "start-suite.bat",
    "install-desktop-entry.sh",
    "install-ollama.sh",
    "install-ollama.bat",
    "linux/ai-compliance-suite.desktop.in",
    # Doku und Konfiguration der entfernten Module.
    "docs/modules/baso.md",
    "docs/modules/ict.md",
    "docs/modules/compliance.md",
    "docs/modules/compliance-db.md",
    "docs/workflows/baso-workflow.md",
    "docs/workflows/ict-workflow.md",
    "docs/cli/index.md",
    "baso.config.json",
    "ict.config.json",
    "compliance.config.json",
    "compliance_db.config.json",
)


def _git(*argv: str) -> str:
    return subprocess.run(["git", *argv], cwd=REPO,
                          capture_output=True, text=True).stdout


# ── Es ist weg ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pfad", WEG)
def test_die_dateien_sind_weg(pfad):
    """Geprüft wird **git**, nicht das Dateisystem.

    Ein Arbeitsbaum trägt unversionierten Müll — nach einem Branch-Wechsel
    bleiben etwa ``__pycache__``-Verzeichnisse stehen, und ``Path.exists()``
    wird davon rot, obwohl im Repository nichts mehr liegt. „Entfernt" heißt:
    nicht mehr versioniert; das ist es, was ausgeliefert wird. (Die Lehre
    steht so schon in ``test_soc_entfernt_1905``.)
    """
    roh = _git("ls-files", "--", pfad).strip()
    assert not roh, f"{pfad} ist noch versioniert:\n  " + roh.replace("\n", "\n  ")


def _weiss_etikett_starter() -> str:
    """Das Verzeichnis des Weiß-Etikett-Starters, gelesen aus ``.sync-exclude``.

    **Warum nicht als Literal hier.** Sein Verzeichnisname ist der Name eines
    echten Kunden, und der Final-Guard von ``sync-to-public`` bricht ab, wenn
    der Begriff im öffentlichen Baum auftaucht — ``tests/`` wird gespiegelt.
    Genau daran ist die Veröffentlichung von **v8.6.0 im ersten Anlauf
    gescheitert** (und v8.0.9 schon einmal). Die Hausregel lautet: keine echten
    Kundennamen in Code oder Tests.

    Den Test deshalb aus der Spiegelung auszunehmen wäre der falsche Ausweg —
    er prüft dann im Produkt nichts. ``.sync-exclude`` nennt das Verzeichnis
    ohnehin (es ist die Liste dessen, was nicht hinaus darf) und wird selbst
    nicht veröffentlicht. Damit steht der Name an **einer** internen Stelle,
    und die Prüfung bleibt echt.
    """
    for zeile in (REPO / ".sync-exclude").read_text(encoding="utf-8").splitlines():
        eintrag = zeile.strip().rstrip("/")
        if eintrag.endswith("_suite") and not eintrag.startswith("ai_compliance"):
            return eintrag
    raise AssertionError(
        "Der Weiß-Etikett-Starter steht nicht mehr in `.sync-exclude`. Steht er "
        "dort nicht, wird er bei einem Versehen mit veröffentlicht — der "
        "Eintrag gehört zurück, bevor dieser Test wieder grün wird.")


def test_der_weiss_etikett_starter_ist_weg():
    """Eigener Test, weil sein Name nicht in die Liste oben darf.

    Geprüft wird **git**, aus demselben Grund wie oben: Im Arbeitsbaum stand
    hier beim Schreiben dieses Tests noch ein ``__pycache__`` mit zwei
    ``.pyc`` von April — unversioniert, also längst entfernt. Ein
    ``Path.exists()`` wäre daran rot geworden und hätte eine Entfernung
    bestritten, die stattgefunden hat.
    """
    name = _weiss_etikett_starter()
    roh = _git("ls-files", "--", name).strip()
    assert not roh, f"{name} ist noch versioniert:\n  " + roh.replace("\n", "\n  ")


def test_kein_tkinter_import_mehr():
    """Das Produkt hat keine Tkinter-Oberfläche — also auch keinen Import.

    Vorher trugen **37** Dateien einen. Geprüft wird der Produktionsbaum;
    ``tests/`` darf das Wort nennen (diese Datei tut es selbst — die Lehre aus
    #1834/#1867/#1878: das Programm prüfen, nicht die Erzählung).
    """
    roh = _git("grep", "-nE", r"^\s*(import tkinter|from tkinter)", "--", "*.py")
    treffer = [z for z in roh.splitlines() if z and not z.startswith("tests/")]
    assert not treffer, "Tkinter-Importe übrig:\n  " + "\n  ".join(treffer)


def test_kein_produktionscode_importiert_die_desktop_module():
    """Genau diese Reste hinterlässt ein Rückbau.

    Ein ``from baso import …`` in einem ``try`` tut von da an stillschweigend
    nichts. ``pyflakes`` (#1896) findet undefinierte Namen, aber keinen Import,
    der ins Leere zeigt — ein ``ImportError`` in einem ``except Exception``
    fällt nirgends auf.
    """
    muster = "|".join(DESKTOP_MODULE)
    roh = _git("grep", "-nE",
               rf"^\s*(from ({muster})[. ]|import ({muster})($|[.,]))", "--", "*.py")
    treffer = [z for z in roh.splitlines() if z and not z.startswith("tests/")]
    assert not treffer, "Desktop-Importe übrig:\n  " + "\n  ".join(treffer)


def test_keine_gui_dateien_mehr():
    """Die Gegenrichtung zur Positivliste oben: **nirgends** mehr eine.

    ``WEG`` nennt die Dateien, die es gab. Dieser Test findet eine neue
    ``gui_module.py`` auch dort, wo sie in der Liste fehlt — sonst wäre die
    Liste die einzige Wahrheit, und Positivlisten wachsen nicht von selbst mit
    (#1871/#1879).
    """
    roh = _git("ls-files", "*gui_module.py", "*/gui.py", "gui.py")
    assert not roh.strip(), f"Tkinter-Oberfläche wieder da:\n  {roh}"


def test_kein_baso_oder_ict_blueprint_im_quelltext():
    """``server/app.py`` registriert die beiden toten Blueprints nicht mehr.

    Ohne Datenbank lässt sich ``create_app()`` hier nicht aufrufen; geprüft
    wird deshalb der Quelltext. ``test_die_app_registriert_alle_blueprints``
    deckt die Laufzeit ab.
    """
    quelle = (REPO / "server/app.py").read_text(encoding="utf-8")
    programm = "\n".join(z for z in quelle.splitlines()
                         if not z.lstrip().startswith("#"))
    for verboten in ("server.api.baso", "server.api.ict",
                     "'/api/baso'", "'/api/ict'"):
        assert verboten not in programm, f"{verboten} wird noch registriert"


def test_die_register_nennen_kein_desktop_modul():
    """Die Web-Register haben sie nie gekannt — und dürfen es nicht anfangen."""
    from shared.firmen_link import MODULE_PROJECT_TABLES
    from shared.hilfe import MODUL_DATEI
    from shared.licensing import modules as m
    from shared.templates import schema

    for modul in DESKTOP_MODULE:
        assert modul not in m.ALL_MODULES
        assert modul not in m.GATED_MODULES
        assert modul not in m.MODULE_LABELS
        assert modul not in m.FIRMEN_MODULE_COLUMNS
        assert modul not in MODULE_PROJECT_TABLES
        assert modul not in MODUL_DATEI
        assert modul not in schema.MODULE_DB
        assert m.module_for_path(f"/api/{modul}/x") is None


def test_keine_rolle_musste_bereinigt_werden():
    """**Die #1779-Falle greift hier nicht — belegt, nicht angenommen.**

    Beim SOC brauchte es ``ENTFERNTE_ROLLEN``: Seit #1779 lehnt die
    Benutzerverwaltung unbekannte Rollen beim **Schreiben** ab (400), und ein
    Konto mit der Rolle eines entfernten Moduls wäre nicht mehr speicherbar
    gewesen — der Administrator käme nicht daran und wüsste nicht, warum.

    Die Desktop-Module hatten nie Rechte oder Rollen in der Webanwendung; es
    gibt also kein Bestandskonto, das etwas Unbekanntes trüge. Dieser Test
    hält genau das fest, damit die Behauptung nachprüfbar bleibt.
    """
    from server.models.permission import (MODULE_PERMISSIONS, Permission,
                                          ROLE_PERMISSIONS, RoleEnum)

    # **Exakt vergleichen, nicht als Teilwort.** `compliance` steckt in
    # `compliance_audit` und in der Rolle `compliance_auditor` — ein
    # Teilstring-Test wäre hier rot geworden und hätte ein Web-Modul
    # angeschwärzt. Dieselbe Regel wie bei der Zuordnung Befund→Komponente
    # (#1774: `requests-oauthlib` ist nicht `requests`).
    rollen = {str(r.value) for r in RoleEnum}
    for modul in DESKTOP_MODULE:
        assert [p for p in Permission
                if str(p.value).split(":")[0] == modul] == []
        assert modul not in rollen
        assert f"{modul}_editor" not in rollen
        assert modul not in MODULE_PERMISSIONS
        assert not any(str(r.value) == modul for r in ROLE_PERMISSIONS)


def test_die_doku_navigation_zeigt_nicht_ins_leere():
    """``mkdocs build --strict`` ist ein Build-Gate — ein toter Link bricht es."""
    nav = (REPO / "mkdocs.yml").read_text(encoding="utf-8")
    for datei in ("modules/baso.md", "modules/ict.md", "modules/compliance.md",
                  "modules/compliance-db.md", "workflows/baso-workflow.md",
                  "workflows/ict-workflow.md", "cli/index.md"):
        assert datei not in nav, f"mkdocs.yml verweist noch auf {datei}"


def test_das_dockerfile_kopiert_die_module_nicht_mehr():
    """Die ``COPY``-Positivliste hat schon einmal alle Instanzen lahmgelegt.

    #1713: Ein **fehlender** Eintrag ließ die Container nicht mehr starten.
    Die Gegenrichtung ist harmloser, aber genauso unaufrichtig — das Image
    würde ein Paket tragen, das es nicht gibt.
    """
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    for modul in DESKTOP_MODULE:
        assert f" {modul}/ /app/{modul}/" not in dockerfile, \
            f"Dockerfile kopiert noch {modul}/"


# ── Und es nimmt nichts mit ─────────────────────────────────────────────────

#: Die Web-Module, wie die Lizenz sie kennt. Unverändert zu v8.3.x.
WEB_MODULE = ("cra", "nis2", "aiact", "dsgvo", "wiba", "risikobewertung",
              "pentest", "firmen", "gutachten", "compliance_audit")


def test_die_lizenz_modulliste_ist_unveraendert():
    """Der wichtigste Test dieser Datei.

    Eine Firma, die CRA gebucht hat, muss CRA behalten; eine gültige Lizenz
    muss dieselben Module freigeben wie vorher. Der Rückbau hat an den
    Kategorien nichts zu suchen.
    """
    from shared.licensing import modules as m

    assert m.BASE_MODULES == ("risikobewertung", "wiba", "pentest",
                              "compliance_audit")
    assert m.SELLABLE_MODULES == ("cra", "nis2", "aiact", "dsgvo")
    assert m.EXPLICIT_MODULES == ("gutachten",)
    assert m.UNGATED_MODULES == ("firmen",)
    for modul in WEB_MODULE:
        assert modul in m.ALL_MODULES, modul
    # Und das Gate entscheidet weiter wie vorher.
    assert m.is_allowed("cra", {"cra", "dsgvo"}) is True
    assert m.is_allowed("wiba", {"cra"}) is True          # Grundpreis (#1703/S1)
    assert m.is_allowed("gutachten", {"*"}) is False      # nur explizit


def test_die_firmen_modulspalten_sind_unberuehrt():
    """Es gab **nie** eine ``module_baso``-Spalte — und die anderen bleiben.

    Das ist der Bestandsdaten-Test: Hätte eine Firma eine Desktop-Spalte
    getragen, hätte der Rückbau sie entfernen müssen, und jede Abfrage mit
    ``SELECT *``-Erwartung wäre darüber gestolpert.
    """
    from shared.licensing.modules import FIRMEN_MODULE_COLUMNS

    import firmen.db as fdb

    spalten = set(FIRMEN_MODULE_COLUMNS.values())
    assert spalten == {
        "module_cra", "module_nis2", "module_ai_act", "module_dsgvo",
        "module_wiba", "module_risikobewertung", "module_gutachten",
        "module_compliance_audit",
    }
    schema = fdb.SCHEMA
    assert isinstance(schema, str) and "module_cra" in schema

    # Wieder exakt: `module_compliance` ist ein **Präfix** von
    # `module_compliance_audit`. Ein `in`-Test wäre rot geworden, obwohl die
    # Spalte, die er meint, nie existiert hat.
    spalten_im_schema = set(re.findall(r"\bmodule_[a-z_]+", schema))
    for modul in DESKTOP_MODULE:
        assert f"module_{modul}" not in spalten_im_schema, \
            f"module_{modul} steht im firmen-Schema"
    # Die Spalten der Web-Module stehen weiter im Schema.
    for spalte in spalten:
        assert spalte in schema, f"{spalte} fehlt im firmen-Schema"


def test_jedes_web_modul_ist_importierbar():
    """Ein Rückbau, der ein Web-Modul mitnimmt, fällt hier auf.

    Importiert werden die Bausteine, die der Webserver beim Start zieht —
    ohne Datenbankzugriff.
    """
    import importlib

    for modul in ("cra", "nis2", "dsgvo", "ai_act", "wiba", "risikobewertung",
                  "pentest", "firmen", "gutachten", "compliance_audit"):
        importlib.import_module(modul)
        importlib.import_module(f"{modul}.db")


def test_die_geteilte_konfiguration_und_die_ki_provider_bleiben():
    """``ai_compliance_suite`` ist kein Launcher mehr, aber kein leeres Paket.

    Die Webanwendung liest ``config`` und ``ai`` an über 30 Stellen — von
    ``server/api/admin.py`` bis ``shared/backup/paket.py``. Wer das Paket mit
    der Oberfläche weggeräumt hätte, hätte die halbe Anwendung mitgenommen.
    """
    from ai_compliance_suite.ai.provider import AITextRequest
    from ai_compliance_suite.config import DEFAULT_CONFIG_PATH, load_config

    assert callable(load_config)
    assert str(DEFAULT_CONFIG_PATH).endswith("ai_compliance_suite.config.json")
    # Das Ausgabebudget muss ankommen (#1841/E2) — die Felder sind der Grund,
    # warum dieses Paket nicht mit der Oberfläche verschwinden durfte.
    assert "max_output_tokens" in AITextRequest.__dataclass_fields__


def test_cra_sync_vulns_laeuft_weiter():
    """``python -m cra sync-vulns`` ist der Aufruf aus einem Zeitplan (#937).

    Er steckte in ``cra/__main__.py`` — einer Datei, die ohne Argumente die
    Tkinter-GUI startete und deshalb nach Desktop aussah. Wer sie mit den
    Oberflächen weggeräumt hätte, hätte den Schwachstellen-Abgleich
    stillgelegt, und gemerkt hätte man es erst am nächsten fehlenden Lauf.
    """
    workflow = (REPO / ".github/workflows/cra-vuln-sync.yml").read_text(
        encoding="utf-8")
    assert "python -m cra sync-vulns" in workflow

    erg = subprocess.run(["python3", "-m", "cra", "sync-vulns", "--help"],
                         cwd=REPO, capture_output=True, text=True)
    assert erg.returncode == 0, erg.stderr[-800:]
    for flag in ("--projekt", "--repo", "--source", "--dry-run", "--promote"):
        assert flag in erg.stdout, flag

    # Ohne Subcommand: Hilfe und Exit 2. Vorher startete hier die GUI; **0**
    # wäre jetzt gefährlich — ein vertippter Zeitplan sähe wie Erfolg aus.
    leer = subprocess.run(["python3", "-m", "cra"],
                          cwd=REPO, capture_output=True, text=True)
    assert leer.returncode == 2, leer.returncode


def test_der_verordnungs_download_bleibt_erreichbar():
    """Nur der Tk-Dialog ist weg, nicht der Weg um die eur-lex-WAF.

    ``gutachten/file_download.py`` ist tkinter-frei und wird von
    ``shared/verordnungen.py`` (#1894) und ``server/api/compliance_audit.py``
    aufgerufen. Die amtlichen Fassungen sind die Grundlage für Fundstellen, die
    in unterschriebene Dokumente gedruckt werden (#1763/#1792).
    """
    from gutachten.file_download import Doc, build_requests_session
    from shared import verordnungen as vo

    assert callable(build_requests_session)
    assert "celex" in Doc.__dataclass_fields__
    # **Teilmenge, keine Gleichheit.** Gegenstand dieses Tests ist, dass der
    # Weg um die WAF den Desktop-Rückbau überlebt hat — nicht, wie viele
    # Rechtsakte die Liste führt. Die Liste selbst ist in
    # ``test_verordnungstexte_1894`` festgenagelt, mit Begründung; sie hier ein
    # zweites Mal auf Gleichheit zu prüfen ist die Spiegel-Liste aus
    # #1731/#1735 — und sie hat prompt zugeschlagen: #2061 ergänzte sechs
    # nationale Gesetze, und dieser Test wurde rot, ohne dass etwas kaputt war.
    assert {"cra", "ki-vo", "dsgvo", "nis2"} <= {v.schluessel
                                                 for v in vo.VERORDNUNGEN}
    assert vo.nach_schluessel("cra").celex == "32024R2847"
    assert vo.nach_schluessel("ki-vo").celex == "32024R1689"


def test_die_pc_c10_fundstelle_ist_nicht_verloren():
    """**Die Falle, die dieser Rückbau fast gestellt hätte.**

    ``shared/errors.py`` war die einzige OWASP-PC-C10-Fundstelle der
    CRA-Eigenbewertung, und ``analyze_local_codebase`` überspringt fehlende
    Dateien stillschweigend (``if not exists: continue``). Die Akte hätte den
    Nachweis **lautlos** verloren — nichts wäre fehlgeschlagen, es hätte nur
    eine Zeile weniger in der Nachweisliste gestanden.

    Umgekehrt wäre der alte Text nach dem Rückbau **falsch**: Er nannte die
    Fehlerbehandlung einer Oberfläche, die das Produkt nicht mehr ausliefert,
    und eine Nachweiszeile über eine entfernte Funktion ist in einer
    Konformitätsakte schlechter als keine (#1799).
    """
    from cra.local_code_analysis import _SECURITY_CHECKS, analyze_local_codebase
    from cra.repo_alignment import _FILE_CHECKS

    # Keine der beiden Listen zeigt noch auf die gelöschte Datei …
    assert "shared/errors.py" not in _SECURITY_CHECKS
    assert not [s for s in _FILE_CHECKS if s[0] == "shared/errors.py"]

    # … und die Fundstelle selbst ist noch da, mit einer Datei, die existiert.
    pc_c10 = {pfad for pfad, checks in _SECURITY_CHECKS.items()
              if "PC-C10" in (checks.get("owasp") or {})}
    assert pc_c10, "OWASP-PC-C10 hat keine Fundstelle mehr"
    for pfad in pc_c10:
        assert (REPO / pfad).exists(), f"{pfad} gibt es nicht"
    assert any(s[1] == "OWASP-PC-C10" and (REPO / s[0]).exists()
               for s in _FILE_CHECKS), "repo_alignment nennt PC-C10 nicht mehr"

    # Und der Lauf über den echten Baum liefert den Befund wirklich — das ist
    # die Probe, die ein Vergleich der Listen allein nicht leistet.
    ids = {f.field_id for f in analyze_local_codebase(REPO)}
    assert "OWASP-PC-C10" in ids, sorted(ids)


def test_die_warteliste_des_ki_waechters_nennt_nur_echte_dateien():
    """Drei ihrer vier Einträge sind mit dem Rückbau gegenstandslos geworden.

    ``test_die_warteliste_nennt_nur_echte_dateien_mit_grund`` in
    ``test_ki_engine_1841`` hätte die beiden ``compliance_db``-Einträge sonst
    angemahnt. Hier steht die Probe nochmals, weil eine Warteliste mit
    Geister-Einträgen zum Teppich wird (#1851).
    """
    from tests.test_ki_engine_1841 import WARTET

    for rel in WARTET:
        assert (REPO / rel).exists(), f"{rel} gibt es nicht mehr"
    for modul in DESKTOP_MODULE:
        assert not [r for r in WARTET if r.startswith(f"{modul}/")]


# ── Laufzeit: braucht die Datenbank ─────────────────────────────────────────

def test_die_app_registriert_alle_blueprints():
    """Die App startet, und unter ``/api/baso`` bzw. ``/api/ict`` liegt nichts.

    Die Gegenprobe ist die wichtigere: Die Blueprints der Web-Module müssen
    **alle** noch da sein.
    """
    from server.app import create_app

    app = create_app()
    regeln = [str(r) for r in app.url_map.iter_rules()]

    tot = [r for r in regeln if r.startswith(("/api/baso", "/api/ict"))]
    assert not tot, tot

    for prefix in ("/api/cra", "/api/nis2", "/api/aiact", "/api/dsgvo",
                   "/api/wiba", "/api/risikobewertung", "/api/pentest",
                   "/api/firmen", "/api/gutachten", "/api/compliance-audit",
                   "/api/admin", "/api/auth", "/api/ai", "/api/templates",
                   "/api/hilfe", "/api/risk-cockpit"):
        assert any(r.startswith(prefix) for r in regeln), \
            f"Kein Endpunkt unter {prefix} — ein Blueprint fehlt"
