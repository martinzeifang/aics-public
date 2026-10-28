"""Ein Name je Handlung — und er kommt aus dem Katalog (#1851).

Dieselbe Handlung trug bis v8.2.0 bis zu **vier** Beschriftungen. Der
Status-Abgleich hieß „🔄 Issues synchronisieren", „🔄 Issue-Status abgleichen",
„🔄 Synchronisieren", „🔄 Sync" und „🔄 Status synchronisieren"; der
Ladezustand dazu „⏳ Sync…", „⏳ Abgleich…", „⏳…" und in einem Fall gar nichts.

WARUM DAS EIN TEST IST UND KEINE FRAGE DER SORGFALT
Beschriftungen als Zeichenketten in 30 Templates sind die Spiegel-Liste aus
#1731/#1735: Beim nächsten Modul schreibt jemand die naheliegende Variante hin,
und es fällt niemandem auf, weil **nichts fehlschlägt** — die Oberfläche sieht
nur an zwei Stellen anders aus. Dieser Test lässt rot werden, wer eine
Beschriftung des Katalogs wieder ins Template schreibt.
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "frontend" / "src"
KATALOG = FRONTEND / "utils" / "aktionen.ts"

#: Die sechs Modul-Views, die die gemeinsame Werkzeugleiste tragen müssen.
MODUL_VIEWS = {
    "cra": "views/cra/CRAView.vue",
    "nis2": "views/nis2/NIS2View.vue",
    "aiact": "views/aiact/AIActView.vue",
    "dsgvo": "views/dsgvo/DSGVOView.vue",
    "wiba": "views/wiba/WiBAView.vue",
    "risikobewertung": "views/risikobewertung/RisikobewertungView.vue",
}

#: Wo „Sync" in der Oberfläche stehen **darf** — je mit Grund.
#:
#: Die Regel aus #1851 gilt den **sieben Handlungen** der Werkzeugleiste. Was
#: hier steht, ist etwas anderes als „Issue-Status abgleichen" und würde durch
#: eine Umbenennung nicht klarer, sondern falsch.
SYNC_ERLAUBT = {
    "views/cra/PflichtDokuPanel.vue":
        "Der CRA-Schwachstellen-Sync (#937) ist eine andere Handlung: Er zieht "
        "Advisories aus GitHub/GitLab in `cra_vuln`. „Abgleichen“ wäre dort "
        "irreführend, weil nichts gegenübergestellt wird.",
    "views/admin/IssueOverviewView.vue":
        "Administrationsansicht über **alle** Module; keine der sieben "
        "projektweiten Handlungen, sondern ein Wartungslauf.",
    "views/soc/SOCView.vue":
        "SOC ist ein eigenes Portal mit eigener Sprache (Wazuh-Telemetrie); "
        "es trägt die Werkzeugleiste nicht.",
    "views/dsgvo/TomKatalogPanel.vue":
        "Der WiBA-Abgleich der TOM (#1575) ist eine fachliche Ableitung, keine "
        "Issue-Handlung — die Beschriftung heißt dort ohnehin „Abgleich“.",
    "components/RepoConfigPanel.vue":
        "Fließtext, der den Zweck des Repositorys erklärt, keine Beschriftung.",
    "components/SettingsDialog.vue":
        "Fließtext zur Nachweis-Einbeziehung, keine Beschriftung.",
    "views/account/SecurityView.vue":
        "Zustands-Abzeichen eines Passkeys („synchronisiert“), keine Handlung.",
    "views/firmen/FirmenView.vue":
        "Projekte anlegen aus dem Firmenbestand; die Beschriftung sagt bereits "
        "„Projekte anlegen“, nur ein Fehlertext nennt „Synchronisieren“.",
}


def _lies(rel: str) -> str:
    return (FRONTEND / rel).read_text(encoding="utf-8")


def _ohne_kommentare(text: str) -> str:
    """HTML- und JS-Kommentare entfernen (Lehre aus #1833, umgekehrt)."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return "\n".join(z for z in text.split("\n")
                     if not z.lstrip().startswith(("//", "*", "/*")))


def _katalog_texte() -> dict[str, str]:
    """Alle ``text:``-Werte des Katalogs → Schlüsselname."""
    quelle = KATALOG.read_text(encoding="utf-8")
    treffer: dict[str, str] = {}
    for block in re.finditer(
            r"(\w+):\s*\{\s*\n\s*text:\s*'([^']+)'", quelle):
        treffer[block.group(2)] = block.group(1)
    return treffer


def _vue_dateien() -> list[Path]:
    return sorted(p for p in FRONTEND.rglob("*.vue"))


def test_katalog_ist_vollstaendig():
    """Die sieben projektweiten und die acht Objekt-Handlungen stehen drin."""
    quelle = KATALOG.read_text(encoding="utf-8")
    for name in ("massenAuto", "massenPrompt", "issuesAnlegen",
                 "statusAbgleichen", "feedbackUebernehmen", "neubewertung",
                 "auditLog"):
        assert f"{name}:" in quelle, f"PROJEKT_AKTIONEN.{name} fehlt"
    for name in ("issueAnlegen", "issueVerknuepfen", "issueAbgleichen",
                 "issueEntknuepfen", "kiPrompt", "kiAuto", "issueImportieren",
                 "kiNeubewertung"):
        assert f"{name}:" in quelle, f"OBJEKT_AKTIONEN.{name} fehlt"


def test_jede_handlung_hat_genau_eine_beschriftung():
    """Keine Katalog-Beschriftung steht als Literal in einem Template.

    Die Beschriftung aus dem Katalog gehört in **einen** Ausdruck
    (``{{ A.statusAbgleichen.text }}``). Steht sie als Zeichenkette im
    Template, gibt es sie zweimal — und die zweite Stelle wandert beim nächsten
    Mal auseinander.
    """
    texte = _katalog_texte()
    assert len(texte) >= 15, f"Katalog unerwartet klein: {texte}"
    verstoesse: list[str] = []
    for pfad in _vue_dateien():
        # **Ohne Kommentare.** Ein Kommentar, der die Beschriftung zitiert, um
        # eine Entscheidung zu erklären („dieser Knopf heißt jetzt …“), ist
        # genau das, was hier erwünscht ist — und er kann nicht auseinander-
        # laufen, weil ihn niemand anzeigt.
        inhalt = _ohne_kommentare(pfad.read_text(encoding="utf-8"))
        for text, name in texte.items():
            # ✕ ist ein Symbol und steht überall (Schließen-Knöpfe); es ist
            # keine Beschriftung, die auseinanderlaufen kann.
            if text == "✕":
                continue
            if text in inhalt:
                verstoesse.append(
                    f"{pfad.relative_to(FRONTEND)}: „{text}“ "
                    f"(gehört als {name} aus utils/aktionen.ts)")
    assert not verstoesse, (
        "Beschriftungen aus dem Katalog stehen als Literal im Template:\n  "
        + "\n  ".join(verstoesse))


def test_sync_steht_nicht_mehr_in_der_oberflaeche():
    """„Sync“ ist Fachjargon für „abgleichen“ und sagt nichts.

    Im Code darf ``sync`` stehen — so heißen die Endpunkte. In der Oberfläche
    nicht. Ausnahmen stehen in :data:`SYNC_ERLAUBT`, **je mit Grund**; ohne
    Begründungspflicht wird die Liste zum Teppich, unter den alles wandert.
    """
    verstoesse: list[str] = []
    for pfad in _vue_dateien():
        rel = str(pfad.relative_to(FRONTEND))
        if rel in SYNC_ERLAUBT:
            continue
        inhalt = pfad.read_text(encoding="utf-8")
        vorlage = inhalt.split("<script", 1)[0]
        # Nur sichtbarer Text: Beschriftungen und Attributwerte von `title`.
        for zeile in vorlage.splitlines():
            if re.search(r"\bSync\b|synchronisier", zeile):
                # Kommentarzeilen im Template erklären, sie beschriften nicht.
                if zeile.strip().startswith(("<!--", "-->")) or "#" in zeile:
                    continue
                verstoesse.append(f"{rel}: {zeile.strip()[:90]}")
    assert not verstoesse, (
        "„Sync“/„synchronisieren“ steht noch in der Oberfläche:\n  "
        + "\n  ".join(verstoesse))


def test_ausnahmen_tragen_eine_begruendung():
    """Eine Ausnahme ohne Grund ist ein Teppich, kein Befund."""
    for rel, grund in SYNC_ERLAUBT.items():
        assert (FRONTEND / rel).exists(), f"{rel} gibt es nicht (mehr)"
        assert len(grund) >= 40, f"{rel}: Grund zu knapp — „{grund}“"


def test_alle_sechs_module_tragen_die_werkzeugleiste():
    """Die sieben Handlungen gibt es in **allen** sechs Modulen.

    Vorher fehlten „🧪 Neubewertung aus Issues“ und „📜 Audit-Log“ in fünf von
    sechs, und WiBA hatte „🐙 Issues anlegen“ nicht.
    """
    fehlt = [m for m, rel in MODUL_VIEWS.items()
             if "ProjektWerkzeugleiste" not in _lies(rel)]
    assert not fehlt, f"Diese Module tragen die Werkzeugleiste nicht: {fehlt}"


def test_werkzeugleiste_bedient_alle_sieben_handlungen():
    """Die Komponente ruft jede der sieben Handlungen auch auf."""
    quelle = _lies("components/shared/ProjektWerkzeugleiste.vue")
    for name in ("massenAuto", "massenPrompt", "issuesAnlegen",
                 "statusAbgleichen", "feedbackUebernehmen", "neubewertung",
                 "auditLog"):
        assert f"A.{name}." in quelle, f"{name} wird nicht angezeigt"
    for pfad in ("issues/bulk", "issues/sync", "issues/import"):
        assert pfad in quelle, f"{pfad} wird nicht aufgerufen"
    for komponente in ("AuditLogModal", "IssueNeubewertungModal",
                       "MassAssessmentModal", "AutoMassBewertungModal"):
        assert komponente in quelle, f"{komponente} fehlt"


def test_kein_modul_baut_die_projektweiten_aufrufe_selbst():
    """Die projektweiten Endpunkte ruft nur die Werkzeugleiste auf.

    Sonst entstehen wieder sechs Fassungen derselben Handlung — mit sechs
    Meldungstexten und sechs Nachlade-Entscheidungen, von denen vier gar nicht
    nachgeladen haben.
    """
    erlaubt = {"components/shared/ProjektWerkzeugleiste.vue"}
    verstoesse: list[str] = []
    for pfad in _vue_dateien():
        rel = str(pfad.relative_to(FRONTEND))
        if rel in erlaubt:
            continue
        inhalt = pfad.read_text(encoding="utf-8")
        for endpunkt in ("/issues/bulk", "/issues/sync'", "/issues/import"):
            if endpunkt in inhalt:
                verstoesse.append(f"{rel}: ruft {endpunkt} selbst auf")
    assert not verstoesse, (
        "Projektweite Issue-Endpunkte außerhalb der Werkzeugleiste:\n  "
        + "\n  ".join(verstoesse))


def test_alle_sechs_module_haben_die_projektweiten_routen(app):
    """Backend-Gegenstück: Ohne Route ist der Knopf ein Defekt (#1846)."""
    regeln = {f"{sorted(r.methods - {'HEAD', 'OPTIONS'})[0]} {r.rule}"
              for r in app.url_map.iter_rules()}
    for modul in ("cra", "nis2", "aiact", "dsgvo", "wiba", "risikobewertung"):
        basis = f"/api/{modul}/projekte/<projekt_name>"
        erwartet = [
            f"POST {basis}/issues/bulk",
            f"POST {basis}/issues/sync",
            f"POST {basis}/issues/import",
            f"GET {basis}/issues/neubewertung",
            f"GET {basis}/audit",
        ]
        fehlt = [e for e in erwartet if e not in regeln]
        assert not fehlt, f"{modul}: diese Routen fehlen: {fehlt}"
