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

SEIT #1954 FOLGT DER WÄCHTER DEM TEXT IN DEN SPRACHKATALOG
Die Wörter liegen nicht mehr in `utils/aktionen.ts`, sondern in
`i18n/{de,en}/aktionen.json`; die `.ts` führt nur noch die **Struktur** (welche
Handlungen es gibt und wie ihr Schlüssel heißt). Der alte Leser suchte
`text: '…'` in der `.ts` — er hätte nach dem Umzug **nichts** mehr gefunden und
wäre grün geblieben, also hätte ausgerechnet die Vereinheitlichung den Wächter
abgeschaltet. Genau diese Klasse ist #1870.

Geprüft wird deshalb in beide Richtungen: dass die `.ts` jede Handlung an den
Sprachkatalog bindet, dass der Katalog keine Handlung führt, die niemand
benutzt, und dass die Beschriftungen **beider** Sprachen in keinem Template als
Literal stehen.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "frontend" / "src"
KATALOG = FRONTEND / "utils" / "aktionen.ts"
SPRACHEN = ("de", "en")

#: Die Gruppen des Sprachkatalogs ↔ die beiden Exporte der `.ts`.
GRUPPEN = {"projekt": "PROJEKT_AKTIONEN", "objekt": "OBJEKT_AKTIONEN"}

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


def _sprachkatalog(code: str) -> dict:
    return json.loads((FRONTEND / "i18n" / code / "aktionen.json")
                      .read_text(encoding="utf-8"))


def _handlungen(code: str) -> dict[str, dict[str, str]]:
    """``"projekt.massenAuto"`` → ``{text, titel, laufend}``."""
    katalog = _sprachkatalog(code)
    return {f"{gruppe}.{id_}": werte
            for gruppe in GRUPPEN
            for id_, werte in (katalog.get(gruppe) or {}).items()}


def _katalog_texte() -> dict[str, str]:
    """Jede sichtbare Beschriftung → wo sie herkommt, über **alle** Sprachen.

    Beide Sprachen, weil ein Template auch den englischen Text als Literal
    tragen könnte — und dann liefe er beim nächsten Mal auseinander, ohne dass
    die deutsche Prüfung etwas merkt.
    """
    treffer: dict[str, str] = {}
    for code in SPRACHEN:
        for name, werte in _handlungen(code).items():
            treffer[werte["text"]] = f"{name} ({code})"
        for name, wert in (_sprachkatalog(code).get("abschnitte") or {}).items():
            treffer[wert] = f"abschnitte.{name} ({code})"
        treffer[_sprachkatalog(code)["kiVorbehalt"]] = f"kiVorbehalt ({code})"
    return treffer


def _vue_dateien() -> list[Path]:
    return sorted(p for p in FRONTEND.rglob("*.vue"))


PROJEKT_IDS = ("massenAuto", "massenPrompt", "issuesAnlegen",
               "statusAbgleichen", "feedbackUebernehmen", "neubewertung",
               "auditLog", "ueberholt")
OBJEKT_IDS = ("issueAnlegen", "issueVerknuepfen", "issueAbgleichen",
              "issueEntknuepfen", "kiPrompt", "kiAuto", "issueImportieren",
              "kiNeubewertung")


def test_katalog_ist_vollstaendig():
    """Die acht projektweiten und die acht Objekt-Handlungen stehen drin."""
    quelle = KATALOG.read_text(encoding="utf-8")
    for name in PROJEKT_IDS:
        assert f"{name}:" in quelle, f"PROJEKT_AKTIONEN.{name} fehlt"
    for name in OBJEKT_IDS:
        assert f"{name}:" in quelle, f"OBJEKT_AKTIONEN.{name} fehlt"


def test_jede_handlung_steht_in_jedem_sprachkatalog():
    """Fehlt ein Schlüssel, zeigt der Knopf seinen eigenen Pfad an.

    `strictTemplates` ist aus (#1858) — ein unbekannter Schlüssel ist also kein
    Fehler, sondern ein Knopf mit der Aufschrift
    `aktionen.projekt.massenAuto.text`. Auffallen würde das erst dem Anwender.
    """
    for code in SPRACHEN:
        katalog = _sprachkatalog(code)
        for gruppe, ids in (("projekt", PROJEKT_IDS), ("objekt", OBJEKT_IDS)):
            vorhanden = set(katalog.get(gruppe) or {})
            assert vorhanden == set(ids), (
                f"{code}/{gruppe}: {vorhanden ^ set(ids)}")
            for id_ in ids:
                for feld in ("text", "titel", "laufend"):
                    wert = (katalog[gruppe][id_] or {}).get(feld, "")
                    assert wert.strip(), f"{code}/{gruppe}.{id_}.{feld} ist leer"
        assert (katalog.get("abschnitte") or {}).keys() == {"issues", "kiBewertung"}
        assert katalog.get("kiVorbehalt", "").strip()


def test_die_ts_bindet_jede_handlung_an_den_sprachkatalog():
    """Beide Richtungen — die Lehre aus #1878.

    Eine Handlung, die die `.ts` führt und der Katalog nicht, zeigt ihren Pfad
    an. Eine, die der Katalog führt und die `.ts` nicht, ist totes Gewicht mit
    falscher Zusicherung.
    """
    quelle = _ohne_kommentare(KATALOG.read_text(encoding="utf-8"))
    gebunden = {f"{g}.{i}" for g, i in
                re.findall(r"aktion\(\s*'(projekt|objekt)'\s*,\s*'(\w+)'\s*\)", quelle)}
    erwartet = ({f"projekt.{i}" for i in PROJEKT_IDS}
                | {f"objekt.{i}" for i in OBJEKT_IDS})
    assert gebunden == erwartet, f"Abweichung: {gebunden ^ erwartet}"
    assert set(_handlungen("de")) == erwartet, "Katalog und .ts weichen ab"


def test_die_ts_fuehrt_keine_woerter_mehr():
    """Sonst gäbe es die Beschriftung zweimal — und das war der Ausgangsmangel.

    Geprüft wird der **kommentarfreie** Text: Der Dateikopf zitiert die alten
    Beschriftungen, um zu erklären, warum es diesen Katalog gibt. Das ist die
    Falle, die in #1834/#1867/#1878/#1903 viermal zugeschlagen hat — ein Wächter
    prüft das Programm, nicht die Erzählung.
    """
    quelle = _ohne_kommentare(KATALOG.read_text(encoding="utf-8"))
    for feld in ("text", "titel", "laufend"):
        treffer = re.findall(rf"\b{feld}:\s*['\"`]", quelle)
        assert not treffer, (
            f"`{feld}:` mit einem Literal in aktionen.ts — die Wörter gehören "
            f"nach i18n/<sprache>/aktionen.json")


def test_die_beschriftung_wird_beim_lesen_aufgeloest():
    """Getter, nicht Auflösung beim Laden des Moduls.

    Würde `aktion()` die drei Werte beim Import auflösen, stünde die Sprache
    fest, die beim ersten Import galt — der Umschalter wirkte erst nach dem
    Neuladen. Das wäre ein Knopf, der sich halb umstellt, und genau so etwas
    fällt niemandem auf, der nur auf Deutsch arbeitet.
    """
    quelle = _ohne_kommentare(KATALOG.read_text(encoding="utf-8"))
    for feld in ("text", "titel", "laufend"):
        assert re.search(rf"get {feld}\(\)\s*\{{\s*return t\(", quelle), (
            f"`{feld}` wird nicht als Getter aufgelöst")
    assert "KI_VORBEHALT = computed(" in quelle, (
        "KI_VORBEHALT braucht einen Ref — ein konstanter String wechselt nicht")


def test_gleiche_sinnbilder_in_jeder_sprache():
    """Das Sinnbild gehört zur Handlung, nicht zur Sprache.

    Es steht im Text, weil die Templates genau eine Zeichenkette anzeigen.
    Damit kann es auseinanderlaufen — ein Knopf, der deutsch 🔄 und englisch 🔁
    trägt, ist für denselben Anwender zwei Knöpfe.
    """
    def sinnbild(wert: str) -> str:
        """Das führende Sinnbild — oder leer.

        Über ``unicodedata`` und nicht über „nicht ASCII": Der erste Anlauf
        prüfte den ersten *Wortteil* auf ASCII und hielt damit „Für" für ein
        Sinnbild. Ein Prüfer, dessen Ausgabe man nicht mehr liest, prüft nichts
        (#1805) — Emoji sind Kategorie ``So`` (Symbol, other), Buchstaben mit
        Umlaut sind es nicht.
        """
        import unicodedata

        if wert and unicodedata.category(wert[0]) == "So":
            return wert.split(" ", 1)[0]
        return ""

    for name in _handlungen("de"):
        bilder = {code: {feld: sinnbild(_handlungen(code)[name][feld])
                         for feld in ("text", "titel", "laufend")}
                  for code in SPRACHEN}
        erstes = bilder[SPRACHEN[0]]
        for code, menge in bilder.items():
            assert menge == erstes, f"{name}: {code} weicht ab — {menge} vs {erstes}"


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


#: Katalog-Schlüssel, in denen „Sync" stehen **darf** — je mit Grund.
#:
#: Es sind dieselben Sachverhalte wie in :data:`SYNC_ERLAUBT`: Mit #1954 sind
#: die Texte aus den Masken in den Katalog gewandert, und damit aus der
#: Reichweite der Datei-Ausnahme. Die Begründung wandert mit, sonst wäre die
#: Ausnahme plötzlich keine mehr — oder der Teppich größer.
SYNC_ERLAUBT_KATALOG = {
    "ansichten.cra.einSyncLauftBereitsFurDiesesProjekt":
        "409 des CRA-Schwachstellen-Sync (#937): „Ein Sync läuft bereits für "
        "dieses Projekt.\u201c — dieselbe Handlung wie der Knopf, der in "
        "SYNC_ERLAUBT begründet ist. Der Text benennt, was läuft.",
    "cra.pflichtDokuPanel.c3SchwachstellenSync":
        "Abschnitts-Überschrift C3 des Schwachstellen-Sync (#937), derselbe "
        "Sachverhalt wie der Knopf darunter.",
    "admin.issueOverviewView.alleGitHubIssuesSyncen":
        "Knopf des modulübergreifenden Wartungslaufs in der Administration — "
        "keine der sieben projektweiten Handlungen.",
    "cra.pflichtDokuPanel.letzterSync":
        "Zustandszeile des CRA-Schwachstellen-Sync (#937) — dieselbe Handlung "
        "wie der Knopf daneben, der in SYNC_ERLAUBT begründet ist.",
    "cra.pflichtDokuPanel.nochKeinSyncGelaufen":
        "Leerzustand derselben Zustandszeile des Schwachstellen-Sync (#937).",
    "cra.pflichtDokuPanel.syncJetzt":
        "Knopf des CRA-Schwachstellen-Sync (#937): Er zieht Advisories aus "
        "GitHub/GitLab; „Abgleichen\u201c wäre dort irreführend.",
    "cra.pflichtDokuPanel.syncLauft":
        "Ladezustand desselben Knopfes.",
    "admin.issueOverviewView.alleGitHubIssuesUberAlleModuleSynchr":
        "Administrationsansicht über alle Module — ein Wartungslauf, keine der "
        "sieben projektweiten Handlungen.",
    "admin.issueOverviewView.syncFehlgeschlagen":
        "Fehlermeldung desselben Wartungslaufs in der Administration.",
    "firmen.firmenView.fehlerBeimSynchronisieren":
        "Projekte aus dem Firmenbestand anlegen — die Beschriftung sagt "
        "„Projekte anlegen\u201c, nur der Fehlertext nennt „Synchronisieren\u201c.",
    "admin.adminWibaCatalogView.syncLauft":
        "Ladezustand des Katalog-Wartungslaufs in der Administration.",
    "admin.adminWibaCatalogView.syncAbgeschlossenV0AktualisiertV1Feh":
        "Administrationsansicht über alle Module; ein Wartungslauf, keine der "
        "sieben projektweiten Handlungen.",
    "geteilt.repoConfigPanel.diesesRepositoryWirdFurIssueErstellu":
        "Fließtext, der den Zweck des Repositorys erklärt, keine Beschriftung.",
    "geteilt.settingsDialog.beziehtDenOperativenZustandSchwachst":
        "Fließtext zur Nachweis-Einbeziehung, keine Beschriftung.",
}


def test_sync_ausnahmen_im_katalog_tragen_eine_begruendung():
    for schluessel, grund in SYNC_ERLAUBT_KATALOG.items():
        assert len(grund) >= 30, f"{schluessel}: Grund zu knapp — {grund!r}"


def test_sync_steht_auch_nicht_im_sprachkatalog():
    """Die Regel gilt dem **Wortlaut**, nicht der Datei, in der er steht.

    Mit dem Umzug nach #1954 wären die Beschriftungen aus der Reichweite des
    Prüfers oben gewandert — er liest `.vue`-Dateien. Für Englisch wäre „Sync"
    die naheliegende Wahl gewesen, und niemand hätte es beanstandet. Es heißt
    dort „Reconcile".
    """
    erlaubte_schluessel = {s.rsplit(".", 1)[-1] for s in SYNC_ERLAUBT_KATALOG}
    verstoesse: list[str] = []
    for datei in sorted((FRONTEND / "i18n").rglob("*.json")):
        inhalt = datei.read_text(encoding="utf-8")
        for zeile in inhalt.splitlines():
            if not re.search(r"\bSync\b|synchronis", zeile, re.I):
                continue
            # Der Schlüssel steht am Zeilenanfang: `"letzterSync": "…"`.
            m = re.match(r'\s*"([\w-]+)"\s*:', zeile)
            if m and m.group(1) in erlaubte_schluessel:
                continue
            verstoesse.append(
                f"{datei.relative_to(FRONTEND)}: {zeile.strip()[:90]}")
    assert not verstoesse, (
        "\u201eSync\u201c/\u201esynchronisieren\u201c steht im Sprachkatalog:\n  "
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
    # #1944: Die drei langen Handlungen laufen **schrittweise** über die
    # Einzel-Routen und nicht mehr über die Sammel-Endpunkte. Die Sammel-Route
    # antwortet erst am Ende; bei 312 s gemessener Laufzeit (#1940) sah der
    # Anwender fünf Minuten ausgegraute Knöpfe, hatte keinen Abbruch, und bei
    # einem Zeitüberlauf blieb ein halb geschriebener Stand, von dem niemand
    # wusste, wie weit er reicht. Die Endpunkte bleiben als Schnittstelle (und
    # `test_alle_sechs_module_haben_die_projektweiten_routen` prüft sie) —
    # geprüft wird hier, dass die Leiste den schrittweisen Weg bedient.
    assert "issues/objekte" in quelle, (
        "Die Objektliste holt der Server. Sie aus dem Massen-Adapter zu bauen "
        "hätte den Umfang verengt — der projektweite Lauf fasst in CRA vier "
        "Objektarten an, der Adapter kennt eine."
    )
    # Die Aufrufe stehen als Template-Literale (`${objektUrl(o)}/issues`),
    # deshalb endet der Pfad auf dem Backtick und nicht auf einem Hochkomma.
    for pfad in ("/issues`", "/issues/sync`", "/import-issue`"):
        assert pfad in quelle, f"Einzel-Route {pfad} wird nicht aufgerufen"
    assert "LaufFortschritt" in quelle, "die Fortschrittsanzeige fehlt"
    assert "AbortController" in quelle, (
        "Ohne Abbruch ist der einzige Ausweg Neuladen — und das hinterlässt "
        "einen Stand, von dem niemand weiß, wie weit er reicht."
    )
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
