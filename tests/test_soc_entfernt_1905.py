"""Das SOC ist entfernt — und bleibt es (#1905).

Das SOC-Modul ist abgekündigt und mit v8.3.0 vollständig aus der Suite
entfernt: Backend-Paket, REST, Frontend, der **Portal-Modus**
(``AICS_PORTAL=soc``), Lizenzierung, Rechte und Rolle.

**Dieser Test prüft beide Richtungen**, und die zweite ist die wichtigere.
Ein Rückbau, der nur „ist es weg?" prüft, hinterlässt genau die Art Schaden,
die niemand bemerkt, bis ein Kunde sie findet:

* Ein **Bestandstoken**, in dessen Modulliste ``soc`` steht, muss weiterhin
  gültig sein und die übrigen Module freigeben.
* Ein **Konto mit der Rolle** ``soc_operator`` muss speicherbar bleiben. Seit
  #1779 lehnt die Benutzerverwaltung unbekannte Rollen beim **Schreiben** ab
  (400) — ohne Bereinigung käme der Administrator an diese Konten nicht mehr
  heran und wüsste nicht, warum.
* Eine **Stack-Umgebung mit ``AICS_PORTAL=soc``** muss unverändert starten.
  Die Variable steht dort noch, bis die SOC-Stacks gelöscht sind; einen
  Container an einer Angabe scheitern zu lassen, die nichts mehr bedeutet,
  wäre der leichtfertigste Teil dieses Rückbaus.

Was **nicht** entfernt ist und warum, steht in #1905: das ``soc``-Schema in
PostgreSQL. Ein ``DROP SCHEMA`` ist nicht umkehrbar, und das Schema führt
Vorfälle und Meldetracks. Dafür gibt es ``scripts/ops/soc_daten_entfernen.py``
— ein eigener Aufruf, von Hand, mit ``--confirm``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Dateien und Verzeichnisse, die es nicht mehr geben darf.
WEG = (
    "soc",
    "server/api/soc",
    "frontend/src/views/soc",
    "frontend/src/components/soc",
    "frontend/src/stores/soc.ts",
    "frontend/src/stores/portal.ts",
    "frontend/src/help/soc.ts",
    "frontend/src/components/sidebars/SOCSidebar.vue",
    "docs/modules/soc.md",
    "scripts/create_soc_stack.py",
)


# ── Es ist weg ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pfad", WEG)
def test_die_dateien_sind_weg(pfad):
    """Geprüft wird **git**, nicht das Dateisystem.

    Ein Arbeitsbaum trägt unversionierten Müll — nach einem Branch-Wechsel
    bleiben etwa `__pycache__`-Verzeichnisse stehen, und `Path.exists()` wird
    davon rot, obwohl im Repository nichts mehr liegt. „Entfernt" heißt: nicht
    mehr versioniert; das ist es, was ausgeliefert wird.
    """
    import subprocess

    roh = subprocess.run(["git", "ls-files", "--", pfad],
                         cwd=REPO, capture_output=True, text=True).stdout.strip()
    assert not roh, f"{pfad} ist noch versioniert:\n  " + roh.replace("\n", "\n  ")


def test_kein_modul_in_der_registry():
    from shared.licensing import modules as m

    assert "soc" not in m.ALL_MODULES
    assert "soc" not in m.GATED_MODULES
    assert "soc" not in m.MODULE_LABELS
    assert m.WEITERE_MODULE == (), m.WEITERE_MODULE
    assert m.module_for_path("/api/soc/alerts") is None


def test_keine_rechte_und_keine_rolle():
    from server.models.permission import (MODULE_PERMISSIONS, Permission,
                                          ROLE_PERMISSIONS, RoleEnum)

    assert [p for p in Permission if str(p.value).startswith("soc:")] == []
    assert [r for r in RoleEnum if "soc" in str(r.value)] == []
    assert "soc" not in MODULE_PERMISSIONS
    assert not any("soc" in str(r.value) for r in ROLE_PERMISSIONS)


def test_kein_blueprint_und_keine_route():
    """Die App startet, und unter ``/api/soc`` liegt nichts mehr."""
    from server.app import create_app

    app = create_app()
    regeln = [str(r) for r in app.url_map.iter_rules()]
    assert not [r for r in regeln if r.startswith("/api/soc")], \
        [r for r in regeln if r.startswith("/api/soc")]
    # Der Wazuh-Webhook hing unter /api/ingest — auch der ist weg.
    assert not [r for r in regeln if r.startswith("/api/ingest")]


def test_der_webserver_importiert_kein_soc():
    """Kein Produktionsmodul darf ``soc`` noch importieren.

    Genau diese Reste hinterlässt ein Rückbau: ein ``from soc import …`` in
    einem ``try``, das von da an stillschweigend nichts tut. ``pyflakes``
    (#1896) findet undefinierte Namen, aber nicht einen Import, der ins Leere
    zeigt — ein ``ImportError`` in einem ``except Exception`` fällt nirgends
    auf.
    """
    import subprocess

    roh = subprocess.run(
        ["git", "grep", "-nE", r"(from soc[. ]|import soc$|import soc[.,])",
         "--", "*.py"],
        cwd=REPO, capture_output=True, text=True).stdout.strip()
    treffer = [z for z in roh.splitlines() if z and not z.startswith("tests/")]
    assert not treffer, "SOC-Importe übrig:\n  " + "\n  ".join(treffer)


def test_kein_portal_modus_mehr():
    """Der Portal-Modus existierte nur für das SOC."""
    import subprocess

    # Geprüft wird das **Lesen**, nicht das Wort: Kommentare und
    # `.env.example` dürfen erklären, dass die Variable entfallen ist (die
    # Lehre aus #1834/#1867/#1878 — das Programm prüfen, nicht die Erzählung).
    roh = subprocess.run(
        ["git", "grep", "-nE", r"(getenv|environ)[^\n]*AICS_PORTAL"],
        cwd=REPO, capture_output=True, text=True).stdout.strip()
    treffer = [z for z in roh.splitlines() if z and not z.startswith("tests/")]
    assert not treffer, "AICS_PORTAL wird noch gelesen:\n  " + "\n  ".join(treffer)
    # Und der Portal-Store des Frontends ist weg.
    assert not (REPO / "frontend/src/stores/portal.ts").exists()


def test_die_hilfe_kennt_kein_soc():
    """``MODUL_DATEI`` ist eine Positivliste, die #1878 beidseitig prüft."""
    from shared.hilfe import MODUL_DATEI

    assert "soc" not in MODUL_DATEI


def test_das_routen_inventar_nennt_kein_soc():
    """#1846: verschwundene Issue-Routen sind dort sonst ein Fehler."""
    routen = json.loads(
        (REPO / "tests/data/issue_routen_vor_1846.json").read_text(encoding="utf-8"))
    assert not [r for r in routen if "/api/soc" in r]


# ── Und es nimmt nichts mit ─────────────────────────────────────────────────

def test_ein_bestandstoken_mit_soc_bleibt_gueltig():
    """Der wichtigste Test dieser Datei.

    Ein Token, dessen ``mod``-Liste ``soc`` nennt, darf nicht plötzlich
    weniger freigeben. Die Gate-Entscheidung geht immer von einem **Pfad**
    aus, und auf ``soc`` zeigt keiner mehr — ein unbekannter Name in der
    Liste bedeutet damit nichts, nicht alles und nicht nichts.
    """
    from shared.licensing.modules import (billable_modules, effective_modules,
                                          is_allowed)

    mit = effective_modules({"cra", "dsgvo", "soc"})
    ohne = effective_modules({"cra", "dsgvo"})
    assert mit == ohne, (mit, ohne)
    assert "soc" not in mit
    assert is_allowed("cra", {"cra", "dsgvo", "soc"}) is True
    assert billable_modules({"cra", "soc"}) == ["cra"]


def test_die_rolle_wird_aus_bestandskonten_genommen():
    """Sonst wäre jedes betroffene Konto nicht mehr speicherbar (#1779)."""
    from server.auth.users_db import ENTFERNTE_ROLLEN

    assert "soc_operator" in ENTFERNTE_ROLLEN


def test_aics_portal_in_der_umgebung_startet_die_suite(monkeypatch):
    """Eine Stack-Umgebung mit der alten Variable läuft unverändert."""
    monkeypatch.setenv("AICS_PORTAL", "soc")
    from server.app import create_app

    app = create_app()
    with app.test_client() as c:
        antwort = c.get("/api/auth/public-config")
    assert antwort.status_code == 200
    daten = antwort.get_json()
    # Die Portal-Schlüssel sind weg; was bleibt, ist die Suite.
    assert "portal" not in daten and "portal_enabled" not in daten
    assert "demo_users_enabled" in daten


def test_alte_archive_werden_nicht_stillschweigend_eingespielt():
    """Der Ausschluss bleibt — mit dem Grund, den der Bericht ausgibt."""
    from shared.backup.uebernehmen import NICHT_UEBERNOMMEN

    assert "soc" in NICHT_UEBERNOMMEN
    assert "entfernt" in NICHT_UEBERNOMMEN["soc"].lower()


def test_das_schema_wird_nicht_vom_code_geloescht():
    """Daten verschwinden nur auf ausdrücklichen Zuruf, nicht beim Deploy.

    Ein ``DROP SCHEMA soc`` im Anwendungscode wäre ein Löschen, das im
    Rahmen eines Releases passiert — ohne Entscheider und ohne Rückweg.
    """
    import subprocess

    roh = subprocess.run(["git", "grep", "-niE", r"drop schema", "--", "*.py"],
                         cwd=REPO, capture_output=True, text=True).stdout
    # Ohne `tests/` findet dieser Test **sich selbst** — seinen Docstring und
    # sein eigenes Suchmuster. Lokal fiel das nicht auf, weil `git grep` nur
    # **versionierte** Dateien durchsucht und die Datei noch neu war; rot wurde
    # er erst in der CI. Das ist die Falle aus #1834/#1867 in ihrer dritten
    # Gestalt: Der Wächter liest die Erzählung — hier die eigene.
    treffer = [z for z in roh.splitlines()
               if "soc" in z.lower()
               and not z.startswith(("scripts/ops/", "tests/"))]
    assert not treffer, treffer
