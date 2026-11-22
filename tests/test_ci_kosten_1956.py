"""Die CI bleibt billig, ohne an Qualität zu verlieren (#1956).

WAS GEMESSEN WURDE
Ein CI-Lauf kostete **73 abrechenbare Minuten**, davon 70 in den vier
Test-Shards. Die Schritt-Zeiten eines Shards:

    0,4 min  Initialize containers
    0,1 min  Set up Python
    0,3 min  Install dependencies
   15,8 min  Run test suite (shard 0/4)      <-- hier liegt alles

Der Overhead je Shard ist also eine Minute; **weniger Shards sparen nichts**,
sie machen den Lauf nur langsamer. Die Testzeit selbst war der Hebel.

DER BEFUND
Dieselbe Testdatei, lokal, je zweimal gemessen:

    mit  --cov=server --cov=shared --cov-append :  3,49 s · 3,35 s
    ohne                                        :  0,24 s · 0,24 s

**Faktor 14.** Die Instrumentierung kostet ~3,2 s **je Prozess**, und die
Suite startet 327 Prozesse — einen je Testdatei, weil ein Gesamtlauf in
einem Prozess den DB-Pool erschöpft und State verschleppt (#1546/#1530).
Das sind **~17 Minuten je Lauf** für eine Zahl, die **kein Gate** ist: Es
gab kein ``--cov-fail-under``, keinen Schwellwert, und die vier
``coverage.xml``-Fragmente führte niemand zusammen und las niemand.

WAS AUSDRÜCKLICH NICHT ANGETASTET WURDE
* **Die Isolation je Testdatei.** Sie ist der Grund, warum die Suite
  überhaupt verlässlich läuft (#1546/#1530/#1704). Dateien zu gruppieren
  würde Prozess-Startzeit sparen und genau die Flakiness zurückbringen, die
  diese Bauform behoben hat.
* **Pfad-Filter.** Naheliegend — und hier falsch: Die Wächter dieses Repos
  lesen absichtlich quer durch den Baum (``frontend/src``, ``docs/``,
  ``.sync-exclude``, ``docker-compose.yml``, ``Dockerfile``). Ein Filter
  „nur Frontend geändert, Python-Tests überspringen" würde
  ``test_i18n_katalog_1954`` stilllegen, und zwar lautlos. Ein übersprungener
  Wächter ist ein Qualitätsverlust, kein Sparen.
* **Die Testmenge.** Keine Datei wurde entfernt, keine Prüfung abgeschaltet.
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
CI = WURZEL / ".github" / "workflows" / "ci.yml"
WORKFLOWS = WURZEL / ".github" / "workflows"


def _ci() -> str:
    return CI.read_text(encoding="utf-8")


def test_coverage_laeuft_nicht_bei_jedem_push():
    """``--cov`` darf nur hinter dem Schalter stehen.

    Ein hart eingetragenes ``--cov`` kostet 3,2 s je Testdatei, also ~17 min
    je Lauf — für eine Kennzahl, die niemand abfragt.
    """
    s = _ci()
    assert "MIT_COVERAGE" in s, (
        "Der Schalter MIT_COVERAGE fehlt — Coverage läuft wieder bei jedem "
        "Push (~17 min je Lauf).")
    # Die Flags dürfen nur in der bedingten Zuweisung vorkommen, nicht im
    # pytest-Aufruf selbst.
    for zeile in s.split("\n"):
        if "--cov" not in zeile or zeile.lstrip().startswith("#"):
            continue
        assert "COV=" in zeile, (
            f"`--cov` steht wieder fest im Aufruf: {zeile.strip()[:80]}")


def test_die_isolation_je_testdatei_bleibt():
    """Die Schleife über einzelne Dateien ist load-bearing (#1546/#1530).

    Sie zu ersetzen wäre der naheliegendste Spar-Griff und der teuerste:
    Ein Gesamtlauf in einem Prozess erschöpft den DB-Pool und verschleppt
    App-State — genau die Flakiness, die diese Bauform behoben hat.
    """
    s = _ci()
    assert "for f in" in s and 'pytest' in s, \
        "Die Datei-Schleife ist weg — läuft die Suite wieder in einem Prozess?"
    assert "--timeout=180" in s, "Der Per-Test-Timeout aus #1530 ist weg."
    assert "timeout -k 20 600" in s, \
        "Der harte Wanduhr-Deckel je Datei aus #1704 ist weg."


def test_keine_pfadfilter_auf_der_testsuite():
    """Ein übersprungener Wächter ist Qualitätsverlust, kein Sparen.

    Die Wächter lesen absichtlich quer durch den Baum: ``test_i18n_katalog``
    liest ``frontend/src/i18n``, ``test_hilfe_fragen`` liest ``docs/`` und
    ``.sync-exclude``, ``test_pdf_fehler`` liest ``docker-compose.yml``,
    ``test_public_publisher`` liest den ``Dockerfile``. Ein ``paths``-Filter
    auf dem Test-Job legt sie bei einer Frontend-Änderung lautlos still.
    """
    s = _ci()
    # `paths`/`paths-ignore` im `on:`-Block des Test-Workflows.
    kopf = s.split("jobs:", 1)[0]
    treffer = [z.strip() for z in kopf.split("\n")
               if re.match(r"^\s*paths(-ignore)?\s*:", z)]
    assert not treffer, (
        "Pfad-Filter auf der Testsuite: " + "; ".join(treffer)
        + " — siehe Modul-Docstring, die Wächter lesen quer durch den Baum.")


def test_keine_workflows_auf_nicht_existierende_branches():
    """Ein Workflow an einem toten Branch ist irreführende Automation.

    Sieben Workflows hingen an ``ai-act/ai-main`` und ``cra/ai-main`` —
    Feature-Branches alter Sprints, die es auf ``origin`` nicht mehr gibt.
    Vier liefen zuletzt im Mai 2026, einer **nie**; zwei liefen nur noch
    über ihren Wochen-Cron und doppelten dabei ``deps-audit`` (derselbe
    OSV-Scanner, dieselbe ``requirements.txt``). In einem Repo, das
    releasefähig werden soll, sieht so etwas nach aktiver Prüfung aus und
    ist keine.
    """
    tot = ("ai-act/ai-main", "cra/ai-main")
    verstoesse: list[str] = []
    for p in sorted(WORKFLOWS.glob("*.yml")):
        s = p.read_text(encoding="utf-8")
        kopf = s.split("jobs:", 1)[0]
        for branch in tot:
            if branch in kopf:
                verstoesse.append(f"{p.name}: an {branch} gebunden")
    assert not verstoesse, (
        "Workflow an einem Branch, den es nicht gibt:\n  "
        + "\n  ".join(verstoesse))


def test_der_osv_scan_gibt_es_genau_einmal():
    """Drei Workflows installierten denselben OSV-Scanner.

    ``deps-audit`` scannt ``requirements.txt`` **und** die Doku-Abhängigkeiten
    **und** läuft ``pip-audit`` — bei Push, PR und wöchentlich. Die beiden
    Modul-Scans taten weniger und liefen nur wöchentlich; sie waren Kopien
    aus der Zeit der Feature-Branches. Eine Prüfung dreimal zu fahren macht
    sie nicht besser.
    """
    mit_osv = [p.name for p in sorted(WORKFLOWS.glob("*.yml"))
               if "osv-scanner" in p.read_text(encoding="utf-8")]
    assert mit_osv == ["deps-audit.yml"], (
        f"Mehr als ein OSV-Scan: {mit_osv} — siehe Docstring.")


# ── Der main-Lauf entfällt nur bei baumgleichem Merge ────────────────────────

def test_die_vorpruefung_vergleicht_baum_hashes():
    """Nicht „ist es ein Merge?", sondern „ist der Inhalt derselbe?".

    DIE PRÄMISSE, DIE NICHT GANZ STIMMTE
    „Jeder PR wurde doch schon geprüft" — ja, aber **nicht jede Änderung an
    main kommt aus einem PR**. Von den letzten 14 main-Commits waren **6
    Direktpushes**, und zwar genau die ``chore(release): vX.Y.Z``-Commits
    plus Doku-Korrekturen; ``main`` hat **keine Branch-Protection**. Ein
    pauschales Weglassen hätte ausgerechnet die Release-Commits ungeprüft
    gelassen — die, die getaggt und ausgeliefert werden.

    Deshalb der Baum-Hash: Ist ``HEAD^{tree}`` gleich ``HEAD^2^{tree}``, hat
    der Merge **keinen neuen Inhalt** gebracht und der PR-Lauf genau diesen
    Baum geprüft. Eine Identitätsprüfung, keine Heuristik. Lief main während
    des PR weiter, weichen die Hashes ab und es wird geprüft — der Fall, für
    den der main-Lauf da ist, bleibt abgedeckt.
    """
    s = _ci()
    assert "vorpruefung" in s, "Der Vorprüfungs-Job fehlt."
    assert 'HEAD^{tree}' in s and 'HEAD^2^{tree}' in s, (
        "Die Vorprüfung vergleicht keine Baum-Hashes mehr — prüft sie nur "
        "noch, *ob* es ein Merge ist? Dann bleibt ein Merge, bei dem main "
        "weitergelaufen ist, ungeprüft.")
    # Ein Direktpush darf nie übersprungen werden.
    assert "eltern" in s and "-lt 3" in s, (
        "Die Unterscheidung Direktpush/Merge fehlt — Release-Commits werden "
        "direkt auf main gepusht und hat kein PR geprüft.")


def test_die_teuren_jobs_haengen_an_der_vorpruefung():
    """Sonst spart die Entscheidung nichts."""
    import yaml

    d = yaml.safe_load(_ci())
    for job in ("test-shard", "frontend-build"):
        jd = d["jobs"][job]
        assert jd.get("needs") == "vorpruefung" or \
            "vorpruefung" in (jd.get("needs") or []), \
            f"{job} hängt nicht an der Vorprüfung"
        assert "vorpruefung.outputs.testen" in str(jd.get("if", "")), \
            f"{job} fragt die Entscheidung nicht ab"


def test_der_pflicht_check_bleibt_gruen_wenn_uebersprungen():
    """``test`` muss einen Status haben, auch ohne Shards.

    Ohne ``always()`` wäre der aggregierte Check „skipped", und eine
    Branch-Protection, die auf ihn wartet, wartet ewig — der Merge-Knopf
    bliebe grau. Das ist die Art Folgefehler, die erst auffällt, wenn man
    die Protection einschaltet.
    """
    import yaml

    d = yaml.safe_load(_ci())
    jd = d["jobs"]["test"]
    assert "always()" in str(jd.get("if", "")), \
        "Der Sammel-Job `test` laeuft nicht mit always() — er waere skipped."
    # Und er darf nicht grün sein, wenn die Shards rot waren.
    assert "needs.test-shard.result" in _ci(), (
        "Der Sammel-Job sieht das Ergebnis der Shards nicht an — mit "
        "always() wäre er dann immer grün, also wertlos.")
