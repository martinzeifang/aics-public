"""#1908 — Release-Kanal, und der Update-Knopf nimmt den dokumentierten Weg.

AUS DEM BETRIEB
---------------
„Ich will in den Einstellungen sagen, ob ich meine Releases von Public bekomme
… oder von privat, dann will ich auch unreleased Versionen. Hintergrund: Vor
der CRA-Veröffentlichung muss ein Beta-Test möglich sein."

Der Wunsch ist richtig, der Hebel „public gegen privat" nicht — er koppelt die
**Reife** eines Stands an die **Nachweisbarkeit** seiner Herkunft. Daraus wurden
drei Kanäle: ``stable`` und ``beta`` **beide** aus ``aics-public`` (signiert,
mit Provenance, Beta als Prerelease), ``dev`` nur intern und ohne Prüfung.

WAS DIESER WÄCHTER FESTHÄLT
---------------------------
1. ``pullImage: True`` kommt nicht zurück. Der Endpunkt schickte es bis v8.2.3
   — der Weg, den #1733 untersagt: 3,2 GB Ollama, und er hebt Postgres,
   Gotenberg und Redis **ungefragt** an.
2. Der Endpunkt und das Ops-Skript nutzen **dieselbe** Logik.
3. Jeder Kundenkanal erzwingt die Herkunftsprüfung; nur ``dev`` nicht, und
   ``dev`` ist nicht wählbar ohne ausdrückliche Freigabe.
4. Vorabfassungen sortieren richtig (``8.3.0-beta.1 < 8.3.0``) und landen
   **nicht** auf ``latest``/``<major.minor>``.
5. Die Anwendung kennt ihre Herkunft **ohne** Docker-API.

Geprüft wird das Programm, nicht die Erzählung — die Docstrings zitieren den
alten Zustand als Begründung (die Lehre aus #1834/#1867/#1878 und aus #1903,
wo mir genau das passiert ist).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]


def _ohne_kommentare_py(text: str) -> str:
    """``#``-Zeilen und Docstrings entfernen — nur das Programm bleibt."""
    text = re.sub(r'"""(?:.|\n)*?"""', '""', text)
    text = re.sub(r"'''(?:.|\n)*?'''", "''", text)
    return "\n".join(z for z in text.splitlines()
                     if not z.lstrip().startswith("#"))


# ── 1. Der verbotene Weg kommt nicht zurück ─────────────────────────────

def test_kein_produktionscode_schickt_pullimage_true():
    """#1733: Der Endpunkt umging den dokumentierten Weg.

    ``{'pullImage': True}`` zieht **jedes** Image des Stacks neu — gemessen 35
    Minuten wegen 3,2 GB Ollama — und hebt dabei ``postgres:16-alpine``,
    ``gotenberg:8`` und ``redis:7-alpine`` an. Ein App-Update konnte so die
    Datenbank auf einen neuen 16.x-Stand heben, ohne dass das irgendwo als
    Datenbank-Update auftauchte.
    """
    funde = []
    for muster in ("server/**/*.py", "shared/**/*.py", "scripts/**/*.py"):
        for datei in WURZEL.glob(muster):
            programm = _ohne_kommentare_py(datei.read_text(encoding="utf-8"))
            if re.search(r"pullImage['\"]?\s*[:=]\s*True", programm):
                funde.append(datei.relative_to(WURZEL).as_posix())
    assert not funde, (
        f"Diese Stellen deployen mit pullImage:true: {funde}. "
        "Der Weg ist shared/deploy/portainer.redeploy.")


def test_der_endpunkt_nutzt_die_geteilte_logik():
    quelle = (WURZEL / "server/api/admin.py").read_text(encoding="utf-8")
    programm = _ohne_kommentare_py(quelle)
    assert "from shared.deploy.portainer import" in programm
    assert "redeploy(" in programm, (
        "Der Endpunkt muss die geteilte redeploy-Funktion rufen, nicht selbst "
        "mit Portainer sprechen")


def test_skript_und_endpunkt_teilen_die_logik():
    """Eine Kopie hätte den Unterschied dauerhaft gemacht (#1731/#1735)."""
    skript = _ohne_kommentare_py(
        (WURZEL / "scripts/ops/portainer_redeploy.py").read_text(encoding="utf-8"))
    assert "from shared.deploy.portainer import" in skript
    # Das Skript darf die Mechanik nicht selbst mitbringen.
    assert "requests.put" not in skript and "def redeploy(" not in skript


def test_die_logik_liegt_im_image():
    """``scripts/`` wird nicht ins Image kopiert — deshalb ``shared/``."""
    dockerfile = (WURZEL / "Dockerfile").read_text(encoding="utf-8")
    kopiert = [z for z in dockerfile.splitlines()
               if z.startswith("COPY") and " shared/" in z]
    assert kopiert, "shared/ muss ins Image kopiert werden"
    assert not any(" scripts/" in z for z in dockerfile.splitlines()
                   if z.startswith("COPY")), (
        "Wenn scripts/ ins Image käme, wäre die Verschiebung nach shared/ "
        "unnötig — dann diesen Test und die Begründung anpassen")


# ── 2. Die Kanäle ───────────────────────────────────────────────────────

def test_jeder_kundenkanal_erzwingt_die_herkunftspruefung():
    """Der Kern der Entkopplung: Beta kostet keine Nachweisbarkeit."""
    from shared.deploy.kanal import KANAELE, OEFFENTLICHE_QUELLE

    assert KANAELE["stable"].quelle == OEFFENTLICHE_QUELLE
    assert KANAELE["beta"].quelle == OEFFENTLICHE_QUELLE, (
        "Eine Beta wird aus aics-public gebaut — sonst verbindet der Kanal "
        "„ich will beta testen\" mit „ich gebe die Herkunftsprüfung auf\"")
    assert KANAELE["dev"].quelle is None


def test_dev_ist_nicht_waehlbar_ohne_freigabe(monkeypatch):
    from shared.deploy import kanal as k

    monkeypatch.delenv(k.DEV_FREIGABE_ENV, raising=False)
    assert [c.name for c in k.waehlbare_kanaele()] == ["stable", "beta"]
    assert k.kanal("dev").name == "stable", (
        "Ohne Freigabe fällt dev auf stable — der Nothilfe-Weg bleibt einer")

    monkeypatch.setenv(k.DEV_FREIGABE_ENV, "1")
    assert "dev" in [c.name for c in k.waehlbare_kanaele()]
    assert k.kanal("dev").name == "dev"


def test_ein_unbekannter_kanal_faellt_auf_den_strengsten():
    """Ein Tippfehler darf nicht ohne Herkunftsprüfung aktualisieren."""
    from shared.deploy.kanal import kanal

    for roh in ("", None, "stabel", "PRODUCTION", "privat"):
        assert kanal(roh).name == "stable", roh


def test_die_eingabe_wird_beanstandet_und_nicht_nur_zurueckgesetzt():
    """Stiller Rückfall allein wäre die Fehlerklasse aus #1805.

    Wer „stabel" speichert, bekäme eine Installation, die aussieht wie
    eingestellt und sich verhält wie nicht eingestellt.
    """
    from server.api.admin import _pruefe_update_kanal

    assert _pruefe_update_kanal({"update": {"channel": "stable"}}) is None
    assert _pruefe_update_kanal({"update": {}}) is None
    assert _pruefe_update_kanal({}) is None
    fehler = _pruefe_update_kanal({"update": {"channel": "stabel"}})
    assert fehler and fehler["code"] == "unbekannter-kanal"
    assert fehler["feld"] == "update.channel"


def test_dev_laesst_sich_nicht_ueber_die_einstellungen_erschleichen(monkeypatch):
    from server.api.admin import _pruefe_update_kanal
    from shared.deploy import kanal as k

    monkeypatch.delenv(k.DEV_FREIGABE_ENV, raising=False)
    fehler = _pruefe_update_kanal({"update": {"channel": "dev"}})
    assert fehler and fehler["code"] == "dev-kanal-nicht-freigegeben"

    monkeypatch.setenv(k.DEV_FREIGABE_ENV, "1")
    assert _pruefe_update_kanal({"update": {"channel": "dev"}}) is None


# ── 3. Versionen ────────────────────────────────────────────────────────

@pytest.mark.parametrize("neuer,aelter", [
    ("8.3.0", "8.3.0-beta.1"),
    ("8.3.0-beta.2", "8.3.0-beta.1"),
    ("8.3.0-rc.1", "8.3.0-beta.9"),
    ("8.10.0", "8.9.0"),
    ("9.0.0", "8.99.99"),
    ("8.3.1", "8.3.0"),
])
def test_versionen_sortieren_richtig(neuer, aelter):
    """``8.3.0-beta.1 < 8.3.0`` — das konnte ``_parse_semver`` nicht.

    Es schnitt alles nach dem ``-`` weg; eine Beta galt damit als **gleich**
    ihrem Release und bekam die Freigabe nie als Update angeboten.
    """
    from shared.deploy.kanal import ist_neuer

    assert ist_neuer(neuer, aelter) is True, f"{neuer} > {aelter}"
    assert ist_neuer(aelter, neuer) is False


def test_der_alte_parser_konnte_das_nachweislich_nicht():
    """Belegt, dass die Erweiterung nötig war — und nicht nur behauptet."""
    from server.api.admin import _parse_semver

    assert _parse_semver("8.3.0-beta.1") == _parse_semver("8.3.0"), (
        "Wenn das hier auseinanderfällt, ist _parse_semver verändert worden — "
        "dann prüft dieser Test nichts mehr und gehört angepasst")


def test_stable_nimmt_keine_vorabfassung():
    from shared.deploy.kanal import kanal, passt_in_kanal

    assert passt_in_kanal("8.3.0", kanal("stable")) is True
    assert passt_in_kanal("8.3.0-beta.1", kanal("stable")) is False, (
        "Sonst gilt ein Prerelease als Update für eine freigegebene "
        "Installation")
    assert passt_in_kanal("8.3.0-beta.1", kanal("beta")) is True
    assert passt_in_kanal("8.3.0", kanal("beta")) is True, (
        "Wer Beta testet, soll nicht auf einer alten Vorabfassung sitzen "
        "bleiben, wenn die Freigabe erscheint")


def test_unsinn_wird_nicht_zur_version():
    from shared.deploy.kanal import ist_neuer, parse_version

    assert parse_version("main") is None
    assert parse_version("sha-89bff28") is None
    assert parse_version("") is None
    assert ist_neuer("main", "8.3.0") is None


# ── 4. Die Tag-Strategie im öffentlichen Workflow ───────────────────────

def test_eine_vorabfassung_landet_nicht_auf_dem_beweglichen_tag():
    """Sonst zieht sie jede Installation mit, die auf ``8.3`` zeigt."""
    wf = (WURZEL / ".public-templates/.github-workflows-public/docker-publish.yml"
          ).read_text(encoding="utf-8")
    zeile = next((z for z in wf.splitlines()
                  if "pattern={{major}}.{{minor}}" in z), "")
    assert zeile, "Das major.minor-Muster fehlt"
    assert "enable=" in zeile and "contains(github.ref_name, '-')" in zeile, (
        "Das bewegliche Tag muss für Vorabfassungen abgeschaltet sein")


def test_latest_haengt_am_default_branch_und_nicht_am_release():
    """Beinahe falsch gemacht — deshalb festgehalten.

    Der öffentliche Workflow läuft auf ``push`` (branches main + tags), nicht
    auf ``release``. ``latest`` an ``github.event.release`` zu hängen hätte es
    **nie** mehr gesetzt und den Release-Prozess gebrochen.
    """
    wf = (WURZEL / ".public-templates/.github-workflows-public/docker-publish.yml"
          ).read_text(encoding="utf-8")
    zeile = next((z for z in wf.splitlines() if "value=latest" in z), "")
    assert "enable={{is_default_branch}}" in zeile, (
        "latest folgt main, nicht dem Tag")


def test_der_sync_laesst_main_bei_einer_vorabfassung_unberuehrt():
    """Die Tag-Regel allein genügt nicht.

    Der Sync pusht ``main`` mit ``--force``; ein Beta-Stand auf dem
    öffentlichen ``main`` löst dort einen Build aus, bei dem
    ``is_default_branch`` wahr ist — also ein ``latest``-Image **aus der Beta**.
    """
    wf = (WURZEL / ".github/workflows/sync-to-public.yml").read_text(encoding="utf-8")
    assert "is_prerelease" in wf, "Der Sync muss Vorabfassungen erkennen"
    assert re.search(r'if \[ "\$\{\{ steps\.tag\.outputs\.is_prerelease \}\}" = "true" \]',
                     wf), "Der Push-Schritt muss den Fall unterscheiden"
    assert "--prerelease" in wf, (
        "Das gespiegelte Release muss ebenfalls als Vorabfassung erscheinen — "
        "sonst ist die Beta im öffentlichen Repo „Latest release\"")


# ── 5. Herkunft ohne Docker-API ─────────────────────────────────────────

def test_die_build_metadaten_stehen_im_image():
    dockerfile = (WURZEL / "Dockerfile").read_text(encoding="utf-8")
    for name in ("APP_IMAGE_SOURCE", "APP_IMAGE_TAG", "APP_IMAGE_DIGEST"):
        assert f"ARG {name}" in dockerfile, name
        assert name in dockerfile.split("ENV APP_IMAGE_SOURCE")[1][:200], (
            f"{name} muss auch als ENV gesetzt sein — ein ARG allein ist zur "
            "Laufzeit nicht lesbar")


def test_beide_workflows_geben_die_metadaten_mit():
    for pfad in (".github/workflows/docker-publish.yml",
                 ".public-templates/.github-workflows-public/docker-publish.yml"):
        wf = (WURZEL / pfad).read_text(encoding="utf-8")
        assert "APP_IMAGE_SOURCE=" in wf, pfad
        assert "APP_IMAGE_TAG=" in wf, pfad


def test_die_anwendung_liest_ihre_herkunft_ohne_docker(monkeypatch):
    from server.api.admin import _image_herkunft

    monkeypatch.setenv("APP_IMAGE_SOURCE", "https://github.com/martinzeifang/aics-public")
    monkeypatch.setenv("APP_IMAGE_TAG", "8.3.0")
    h = _image_herkunft()
    assert h["oeffentlich"] is True
    assert h["unveroeffentlicht"] is False

    monkeypatch.setenv("APP_IMAGE_SOURCE",
                       "https://github.com/martinzeifang/AI_Compliance_Suite")
    monkeypatch.setenv("APP_IMAGE_TAG", "sha-89bff28")
    h = _image_herkunft()
    assert h["oeffentlich"] is False
    assert h["unveroeffentlicht"] is True, (
        "Ein Dev-Tag muss als solcher erkennbar sein — bei v8.2.1 fuhren Prod "
        "und Demo eines, während die Oberfläche eine Release-Nummer zeigte")


def test_ohne_metadaten_wird_nichts_behauptet(monkeypatch):
    from server.api.admin import _image_herkunft

    monkeypatch.delenv("APP_IMAGE_SOURCE", raising=False)
    monkeypatch.delenv("APP_IMAGE_TAG", raising=False)
    h = _image_herkunft()
    assert h["metadaten_vorhanden"] is False
    assert h["oeffentlich"] is False, (
        "Ohne Label ist die Herkunft unbekannt und nicht „öffentlich\"")


def test_der_stand_steht_im_profil():
    """Die Fußzeile las ``package.json`` — den Build-Wert des Frontends."""
    quelle = (WURZEL / "server/api/auth.py").read_text(encoding="utf-8")
    assert "'app_stand': _app_stand()" in quelle
    bar = (WURZEL / "frontend/src/components/StatusBar.vue").read_text(encoding="utf-8")
    assert "app_stand" in bar, (
        "Die Fußzeile muss den Stand vom Server nehmen")


# ── 6. Der Rückweg ──────────────────────────────────────────────────────

def test_ein_rueckschritt_verlangt_eine_bestaetigung():
    """Älterer Code auf einer Datenbank mit neuerem Schema (#1785)."""
    quelle = _ohne_kommentare_py(
        (WURZEL / "server/api/admin.py").read_text(encoding="utf-8"))
    assert "downgrade-bestaetigen" in quelle
    assert "confirm_downgrade" in quelle
    assert "428" in quelle


def test_der_rueckschritt_wird_nicht_verboten():
    """Ein Rückweg, den die Anwendung verbietet, endet im Eingriff von Hand."""
    quelle = (WURZEL / "server/api/admin.py").read_text(encoding="utf-8")
    stelle = quelle[quelle.index("def trigger_update"):]
    stelle = stelle[:stelle.index("@admin_bp.post('/update/test-connection')")]
    assert "confirm_downgrade" in stelle
    assert "403" not in stelle.split("confirm_downgrade")[1][:400], (
        "Der Rückschritt ist bestätigungspflichtig, nicht gesperrt")
