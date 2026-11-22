"""Die Zweisprachigkeit der Oberfläche hat einen Prüfer (#1954).

WARUM ES DIESEN TEST BRAUCHT
`frontend/tsconfig.json` schaltet `strictTemplates` ausdrücklich **aus** — ein
Aufruf `$t('cra.releases.titel')` im Template wird von `vue-tsc` also nicht
gegen irgendetwas geprüft. Damit sehen drei verschiedene Fehler gleich aus,
und zwar alle gleich harmlos:

  * ein Tippfehler im Schlüssel,
  * ein Schlüssel, den es in **keiner** Sprache gibt,
  * ein Schlüssel, der auf Deutsch da ist und auf Englisch fehlt.

In allen drei Fällen baut das Frontend grün, startet, und zeigt dem Anwender
den **Rohschlüssel** an. Kein bestehender Prüfer fängt das: `vue-tsc` sieht
Template-Ausdrücke nicht an, `tests/test_knopf_ohne_wirkung_1805.py` prüft
Ereignisse und Zuhörer, und der Browser meldet höchstens eine Warnung in einer
Konsole, die im Betrieb niemand liest. Das ist dieselbe Fehlerklasse wie #1805,
#1820 und #1870: Es schlägt nichts fehl, es steht nur das Falsche da.

DER GEFÄHRLICHERE TEIL: MARKER SIND KEINE TEXTE
`test_kein_datenformat_im_katalog` ist der eigentliche Grund, warum dieser Test
mehr ist als Buchhaltung. Mehrere deutsche Zeichenketten dieser Anwendung
werden **in die Datenbank geschrieben und per Präfix wieder gelesen** — etwa
„⚠️ Neubewertung erforderlich" (`shared/issue_abgleich.py`) oder „🤖
KI-generiert" (`shared/ki_herkunft.py`). An letzterem entscheidet
`ki_herkunft.ist_druckbar()`, ob ein ungeprüfter KI-Entwurf in eine
**freigegebene** EU-Konformitätserklärung darf. Wanderte so ein Marker in
einen Sprachkatalog und würde übersetzt, wäre die Folge nicht ein hässlicher
Text, sondern: Bestandsdaten verlieren lautlos ihre Markierung, und
ungeprüfte Entwürfe gelten plötzlich als geprüft.

Die Regel dahinter ist die Regel des ganzen Vorhabens: **Gespeichert wird nie
etwas anderes.** Jede Übersetzung ist eine Anzeigeschicht. Der deutsche
Markerstring ist ein Schlüssel, der zufällig deutsch aussieht — wie
`anforderung_id`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
I18N = WURZEL / "frontend" / "src" / "i18n"
QUELLE = WURZEL / "frontend" / "src"

SPRACHEN = ("de", "en")

# Zeichenketten, die Datenformat sind und niemals übersetzt werden dürfen.
# Die Fundstellen stehen daneben, damit beim nächsten Mal niemand sucht.
DATENFORMAT = (
    "Neubewertung erforderlich",   # shared/issue_abgleich.py, 6 Kopien
    "Neubewertung bestätigt",      # shared/issue_abgleich.py (#1868)
    "Vollständig bearbeitet",      # shared/issue_completion.py (Altbestand)
    "KI-generiert",                # shared/ki_herkunft.py -> ist_druckbar()
    "Akzeptanz zurückgenommen",    # risikobewertung/db.py
    "Eigene Hinweise des Bearbeiters",  # shared/prompt_zusatz.py (Idempotenz)
    "Verbindlich bleibt",          # shared/prompt_zusatz.py (Vorrang-Block)
    "BEGIN_EIGENE_HINWEISE",
    "END_EIGENE_HINWEISE",
)

PLATZHALTER = re.compile(r"\{(\w+)\}")


def _lade(sprache: str) -> dict[str, object]:
    """Liest alle Gruppen einer Sprache so ein, wie `index.ts` es tut."""
    verzeichnis = I18N / sprache
    assert verzeichnis.is_dir(), f"{verzeichnis} fehlt"
    baum: dict[str, object] = {}
    for datei in sorted(verzeichnis.glob("*.json")):
        baum[datei.stem] = json.loads(datei.read_text(encoding="utf-8"))
    return baum


def _flach(baum: object, pfad: str = "") -> dict[str, object]:
    """Macht aus dem verschachtelten Baum `{'a.b': wert}`."""
    raus: dict[str, object] = {}
    if isinstance(baum, dict):
        for schluessel, wert in baum.items():
            raus.update(_flach(wert, f"{pfad}.{schluessel}" if pfad else schluessel))
    else:
        raus[pfad] = baum
    return raus


@pytest.fixture(scope="module")
def kataloge() -> dict[str, dict[str, object]]:
    return {sprache: _flach(_lade(sprache)) for sprache in SPRACHEN}


def test_jede_sprache_hat_einen_katalog():
    for sprache in SPRACHEN:
        dateien = list((I18N / sprache).glob("*.json"))
        assert dateien, f"Kein Katalog für '{sprache}'"


def test_beide_sprachen_haben_dieselben_schluessel(kataloge):
    """Der eigentliche Fund: ein fehlender englischer Text ist unsichtbar.

    vue-i18n fällt auf die Ausweichsprache zurück und zeigt den deutschen
    Text — in einer englischen Oberfläche. Das sieht nach einem
    Übersetzungsrest aus und ist keiner, sondern ein fehlender Schlüssel.
    """
    de = set(kataloge["de"])
    en = set(kataloge["en"])
    nur_de = sorted(de - en)
    nur_en = sorted(en - de)
    assert not nur_de, (
        f"{len(nur_de)} Schlüssel gibt es nur auf Deutsch — in der englischen "
        f"Oberfläche erscheint dort der deutsche Text: {nur_de[:15]}"
    )
    assert not nur_en, (
        f"{len(nur_en)} Schlüssel gibt es nur auf Englisch — toter Ballast "
        f"oder ein vergessener deutscher Text: {nur_en[:15]}"
    )


def test_platzhalter_stimmen_zwischen_den_sprachen(kataloge):
    """`{v}` auf Deutsch und `{version}` auf Englisch druckt `{version}`.

    Der Kompilierer lässt einen nicht gelieferten Platzhalter ausdrücklich
    stehen (statt „undefined" zu schreiben) — damit ein Tippfehler auffällt.
    Auffallen kann er aber nur, wenn ihn jemand sucht. Das ist hier.
    """
    fehler: list[str] = []
    for schluessel, wert_de in kataloge["de"].items():
        wert_en = kataloge["en"].get(schluessel)
        if wert_en is None:
            continue  # der Paritätstest meldet das schon
        namen_de = {n for t in _texte(wert_de) for n in PLATZHALTER.findall(t)}
        namen_en = {n for t in _texte(wert_en) for n in PLATZHALTER.findall(t)}
        if namen_de != namen_en:
            fehler.append(f"{schluessel}: de={sorted(namen_de)} en={sorted(namen_en)}")
    assert not fehler, "Platzhalter weichen ab:\n  " + "\n  ".join(fehler)


def test_pluralformen_haben_gleich_viele_zweige(kataloge):
    """Eine Liste ist eine Pluralform; verschieden lange Listen greifen daneben.

    vue-i18n wählt den Zweig über den Plural-Index. Hat Deutsch drei Zweige
    und Englisch zwei, zeigt Englisch bei n=5 den falschen.
    """
    fehler: list[str] = []
    for schluessel, wert_de in kataloge["de"].items():
        wert_en = kataloge["en"].get(schluessel)
        if isinstance(wert_de, list) or isinstance(wert_en, list):
            if not (isinstance(wert_de, list) and isinstance(wert_en, list)):
                fehler.append(f"{schluessel}: nur eine Sprache ist eine Pluralform")
            elif len(wert_de) != len(wert_en):
                fehler.append(f"{schluessel}: de={len(wert_de)} Zweige, en={len(wert_en)}")
    assert not fehler, "Pluralformen passen nicht:\n  " + "\n  ".join(fehler)


def _texte(wert: object) -> list[str]:
    if isinstance(wert, list):
        return [str(x) for x in wert]
    return [str(wert)]


def test_keine_leeren_texte(kataloge):
    for sprache, katalog in kataloge.items():
        leer = sorted(k for k, v in katalog.items() if not any(_texte(v)) or not all(t.strip() for t in _texte(v)))
        assert not leer, f"{sprache}: leere Texte — besser den Schlüssel weglassen: {leer[:15]}"


#: Oberflächentexte, die einen Marker **nennen** dürfen — je mit Grund.
#: Der Marker steht in der Bemerkung des Objekts; eine Filter-Beschriftung
#: oder ein Abzeichen, das ihn nicht wörtlich nennt, schickt den Anwender
#: nach einem Text suchen, der nicht in seiner Akte steht. Deshalb sind diese
#: Stellen erlaubt — und müssen den Marker in **jeder** Sprache deutsch
#: zitieren (siehe den Test darunter).
MARKER_ZITAT_ERLAUBT = {
    "geteilt.autoMassBewertungModal.nurNeubewertungErforderlichV0":
        "Filter-Beschriftung: nennt die Markierung, nach der gefiltert wird.",
    "geteilt.issueNeubewertungModal.v0ObjektEMitVerknupftenIssuesV1Berei":
        "Zähler-Zeile: sagt, wie viele Objekte die Markierung tragen.",
    "geteilt.massAssessmentModal.nurNeubewertungErforderlichV0":
        "Filter-Beschriftung, wie im Auto-Massenlauf.",
    "geteilt.projektWerkzeugleiste.rueckfrageAbgleichen":
        "Rückfrage vor dem Status-Abgleich: Sie sagt dem Anwender wörtlich, "
        "was der Abgleich in die Bemerkung schreibt — und muss den Marker "
        "deshalb zitieren. (#2041: war in drei Bruchstücke geteilt, von denen "
        "nur zwei im Katalog standen; die Rückfrage begann deutsch und endete "
        "englisch.)",
    "risikobewertung.risikobewertungView.neubewertungErforderlich":
        "Erklärtext: zitiert wörtlich, was der Abgleich in die Bemerkung "
        "schreibt.",
    "sidebars.risikobewertungSidebar.neubewertungErforderlich":
        "Tooltip des ⚠️-Abzeichens — benennt die Markierung des Risikos.",
    "sidebars.risikobewertungSidebar.nurBewertungenMitMindestensEinemRisi":
        "Filter-Tooltip der Seitenleiste: nennt die Markierung, nach der "
        "gefiltert wird.",
    "complianceAudit.complianceAuditView.kIGeneriertFachlichNochNichtGepruftU":
        "Hinweis am KI-Entwurf: zitiert die Kennzeichnung aus ki_herkunft.",
    "geteilt.autoBewertungErgebnis.kIGeneriert":
        "Abzeichen am Ergebnis der automatischen Bewertung — es benennt die "
        "Kennzeichnung, die ki_herkunft am Objekt führt.",
    "risikobewertung.risikoEditor.kIGeneriert":
        "Dasselbe Abzeichen im Risiko-Editor — es benennt denselben "
        "Registereintrag aus ki_herkunft.",
    "firmen.pentestExtraktModal.kIGeneriertBitteGegenDenBerichtPrufe":
        "Hinweis am KI-Entwurf der Pentest-Extraktion, dieselbe "
        "Kennzeichnung.",
}

#: Dekorations-Abweichungen, die eine **richtige** Übersetzung erzwingt —
#: je mit Grund. Ohne Begründung wäre die Liste ein Teppich (#1851).
DEKORATION_ERLAUBT: dict[str, str] = {
    "cra.konformitaetPanel.anhangNbspITeilNbspIINrNbspIstDannNi":
        "Satzbruchstück: Das Deutsche beginnt mit dem Doppelpunkt, der den "
        "Satz an der Hervorhebung fortsetzt (… verzichten: Anhang I …). "
        "Englisch trägt die Hervorhebung das Verb (… you may close this "
        "point: Annex I …), der Doppelpunkt wandert mit. Ein Prüfer, der das "
        "beanstandet, erzwingt die schlechtere Übersetzung.",
}


def test_kein_datenformat_im_katalog(kataloge):
    """Marker gehören nicht in einen Sprachkatalog — sie sind Datenformat.

    Siehe den Modul-Docstring. Der schlimmste Fall ist „KI-generiert":
    `shared/ki_herkunft.ist_druckbar()` entscheidet daran, ob ein ungeprüfter
    KI-Entwurf in ein ausgehendes Dokument darf.
    """
    fehler: list[str] = []
    for sprache, katalog in kataloge.items():
        for schluessel, wert in katalog.items():
            if schluessel in MARKER_ZITAT_ERLAUBT:
                continue
            for text in _texte(wert):
                for marker in DATENFORMAT:
                    if marker in text:
                        fehler.append(f"{sprache}:{schluessel} enthält den Marker {marker!r}")
    assert not fehler, (
        "Datenformat im Sprachkatalog — diese Zeichenketten werden in die "
        "Datenbank geschrieben und per Präfix zurückgelesen:\n  "
        + "\n  ".join(fehler)
    )


# --- Benutzte Schlüssel gegen den Katalog -----------------------------------

# `$t('a.b')`, `t('a.b')`, `i18n.t('a.b')`. Ein Punkt im Schlüssel ist Pflicht
# (alle Schlüssel sind `gruppe.name`) — das hält zufällige `t('...')`-Treffer
# aus fremdem Code heraus.
BENUTZT = re.compile(r"(?<![\w.])\$?t\(\s*['\"]([a-zA-Z][\w]*(?:\.[\w]+)+)['\"]")


def _ohne_kommentare(text: str) -> str:
    """Kommentare weg — das Programm prüfen, nicht die Erzählung.

    Die Lehre aus #1834/#1867/#1878/#1903: Ein Prüfer, der auf einen Kommentar
    anspringt, der den alten Zustand zitiert, meldet Fehlalarme — und ein
    Prüfer, dessen Ausgabe man nicht mehr liest, prüft nichts.
    """
    text = re.sub(r"/\*(?:.|\n)*?\*/", "", text)
    text = re.sub(r"(?m)^\s*//.*$", "", text)
    text = re.sub(r"(?m)<!--(?:.|\n)*?-->", "", text)
    return text


def _benutzte_schluessel() -> dict[str, list[str]]:
    treffer: dict[str, list[str]] = {}
    for datei in list(QUELLE.rglob("*.vue")) + list(QUELLE.rglob("*.ts")):
        if I18N in datei.parents or datei.parent == I18N:
            continue
        inhalt = _ohne_kommentare(datei.read_text(encoding="utf-8", errors="replace"))
        for schluessel in BENUTZT.findall(inhalt):
            treffer.setdefault(schluessel, []).append(str(datei.relative_to(WURZEL)))
    return treffer


def test_jeder_benutzte_schluessel_steht_im_katalog(kataloge):
    benutzt = _benutzte_schluessel()
    de = kataloge["de"]
    fehlend = {k: v for k, v in benutzt.items() if k not in de}
    assert not fehlend, (
        "Diese Schlüssel werden benutzt, stehen aber in keinem Katalog — in der "
        "Oberfläche erscheint der Rohschlüssel:\n  "
        + "\n  ".join(f"{k}  ({', '.join(sorted(set(v))[:3])})" for k, v in sorted(fehlend.items()))
    )


# --- Die CSP-Zusicherung aus #1816 bleibt ----------------------------------


def test_der_kompilierer_erzeugt_keinen_code():
    """Platzhalter ohne `eval` — das war die Bedingung der ganzen Lösung.

    #1816 hat `new Function()` aus dem Bundle genommen, weil die CSP
    `script-src 'self'` ohne `unsafe-eval` ist. Der Kompilierer setzt
    Textstücke zusammen; er erzeugt keinen Code. Wer das ändert, bringt den
    Konsolenfehler auf jeder Seite zurück — und zwar erst im Betrieb.
    """
    for datei in sorted(I18N.glob("*.ts")):
        quelle = _ohne_kommentare(datei.read_text(encoding="utf-8"))
        for verboten in ("new Function", "eval(", "Function("):
            assert verboten not in quelle, (
                f"{datei.name} enthält {verboten!r} — die CSP erlaubt kein "
                "unsafe-eval (#1816)"
            )


def test_die_ci_prueft_das_gebaute_bundle():
    """Der Quelltext-Prüfer oben ist ein Indiz, das Bundle ist der Beweis.

    `test_der_kompilierer_erzeugt_keinen_code` liest unseren eigenen Code.
    Der Laufzeit-Compiler käme aber über einen geänderten Vite-Alias, eine
    neue Abhängigkeit oder ein Plugin zurück — alles Wege, die an dieser
    Datei vorbeiführen. Deshalb greift der Schritt in `frontend-build` nach
    `npm run build` ins `dist/`; dieser Test hält bloß fest, dass es ihn
    gibt und dass er Folgen hat (das Muster aus #1858).
    """
    roh = (WURZEL / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    # Ganze Kommentarzeilen weg, sonst prüft der Wächter die Erzählung.
    #
    # Beim ersten Anlauf wurde dieser Test rot — nicht wegen der CI, sondern
    # weil der Kommentar aus #1858 ein paar Zeilen darüber „Kein
    # `continue-on-error` — ein Prüfer, dessen Ausgabe nichts bedeutet, prüft
    # nichts" **wörtlich** enthält. Genau die Falle aus #1834/#1867/#1878/#1903,
    # hier zum fünften Mal: Wer einen Prüfer schreibt, der auf Prosa anspringt,
    # bekommt Fehlalarme — und ein Prüfer, dessen Ausgabe man nicht mehr liest,
    # prüft nichts.
    ci = re.sub(r"(?m)^\s*#.*$", "", roh)
    assert "dist/assets/" in ci and "new Function(" in ci, (
        "Der Bundle-Prüfer fehlt in .github/workflows/ci.yml — die "
        "CSP-Zusicherung aus #1816 hängt dann wieder nur an einem Indiz"
    )
    # Der Schritt muss im Job `frontend-build` stehen: Der ist verbindlich.
    # Ein eigener Job bräuchte erst einen Eintrag in der Branch-Protection
    # und wäre bis dahin folgenlos.
    nach_job = ci.split("frontend-build:", 1)
    assert len(nach_job) == 2, "Job `frontend-build` nicht gefunden"
    bis_naechster_job = re.split(r"\n  \w[\w-]*:", nach_job[1], maxsplit=1)[0]
    assert "new Function(" in bis_naechster_job, (
        "Der Bundle-Prüfer steht nicht im Job `frontend-build` — dort wirkt "
        "er sofort, weil der Job schon Pflicht ist"
    )
    assert "continue-on-error" not in bis_naechster_job, (
        "`continue-on-error` im Job `frontend-build` — ein Prüfer, dessen "
        "Ausgabe nichts bedeutet, prüft nichts"
    )


def test_zitierte_marker_bleiben_in_jeder_sprache_deutsch(kataloge):
    """Ein zitierter Marker wird **nicht** übersetzt (#1954).

    DER BEFUND, DER DAS NÖTIG MACHT
    Ein Übersetzer-Agent hat ``🤖 KI-generiert`` zu ``🤖 AI-generated``
    gemacht — eine saubere Übersetzung und genau der Fehler. Der Marker steht
    deutsch in der Bemerkung des Objekts (``shared/issue_completion.
    NEEDS_REASSESS_MARKER``, ``shared/ki_herkunft.ALTER_MARKER``). Wer die
    englische Oberfläche liest und danach in seiner Akte sucht, findet
    nichts — die Anwendung hätte ihm einen Text genannt, den es dort nicht
    gibt. Dieselbe Klasse wie die Wegbeschreibung aus #1805.

    Die Stellen, die einen Marker nennen dürfen, stehen in
    :data:`MARKER_ZITAT_ERLAUBT`. Dort muss er **wörtlich** stehen, in jeder
    Sprache; der Satz drumherum wird übersetzt.
    """
    verstoesse: list[str] = []
    de = kataloge["de"]
    for schluessel in MARKER_ZITAT_ERLAUBT:
        wert_de = de.get(schluessel)
        if wert_de is None:
            continue
        zitiert = [m for m in DATENFORMAT
                   if any(m in t for t in _texte(wert_de))]
        for code, andere in kataloge.items():
            if code == "de" or schluessel not in andere:
                continue
            texte = _texte(andere[schluessel])
            for marker in zitiert:
                if not any(marker in t for t in texte):
                    verstoesse.append(
                        f"{code}:{schluessel}: Marker {marker!r} wurde "
                        f"übersetzt")
    assert not verstoesse, "\n  ".join(["Zitierte Marker:"] + verstoesse)


def test_dekoration_ist_in_jeder_sprache_dieselbe(kataloge):
    """Sinnbilder und Layout-Zeichen stehen in jeder Sprache gleich (#1954).

    DER BEFUND, DER DAS NÖTIG MACHT
    Vier Werte in ``en/common.json`` hatten ihr Sinnbild verloren
    (``📋 Kopieren`` → ``Copy``), weil die englischen Werte älter waren als
    die deutschen. Aufgefallen ist es beim Übersetzen, nicht beim Prüfen:
    Der Sinnbild-Wächter aus #1851 deckte nur ``aktionen.json`` ab.

    Ein Knopf, der deutsch 📋 trägt und englisch nicht, ist für denselben
    Anwender zwei Knöpfe; ein fehlendes ``*`` behauptet, das Feld sei
    freiwillig.
    """
    import unicodedata as _u

    #: Nur **Layout**-Zeichen, nicht jede Satzzeichen-Abweichung. Der
    #: Gedankenstrich gehört zur Prosa: „Bestätigungs-Code aus der App
    #: eingeben:" wurde englisch zu „Confirmation code — enter it from the
    #: app:", weil der Imperativ sonst verloren geht. Das ist eine richtige
    #: Übersetzung, und ein Prüfer, der sie beanstandet, erzwingt eine
    #: schlechtere.
    LAYOUT = set("*→⟶←↑↓:…")

    def dekoration(text: str) -> tuple[str, str]:
        """Sinnbild davor, Layout-Zeichen danach."""
        def rand(s: str) -> str:
            return "".join(c for c in s
                           if c in LAYOUT or _u.category(c) == "So")

        vorne = re.match(r"^[^\w(]*", text)
        hinten = re.search(r"[^\w).]*$", text)
        return (rand(vorne.group(0) if vorne else ""),
                rand(hinten.group(0) if hinten else ""))

    abweichung: list[str] = []
    de = kataloge["de"]
    for schluessel, wert in de.items():
        if schluessel in DEKORATION_ERLAUBT:
            continue
        for code, andere in kataloge.items():
            if code == "de" or schluessel not in andere:
                continue
            for a, b in zip(_texte(wert), _texte(andere[schluessel])):
                if dekoration(a) != dekoration(b):
                    abweichung.append(
                        f"{code}:{schluessel}: {dekoration(a)} vs "
                        f"{dekoration(b)}  ({a[:34]!r} / {b[:34]!r})")
    assert not abweichung, (
        "Dekoration weicht zwischen den Sprachen ab:\n  "
        + "\n  ".join(sorted(abweichung)[:30])
        + (f"\n  … und {len(abweichung) - 30} weitere"
           if len(abweichung) > 30 else ""))


def test_die_ausnahmen_tragen_eine_begruendung():
    """Eine Ausnahme ohne Grund ist ein Teppich, kein Befund (#1851)."""
    for liste, name in ((MARKER_ZITAT_ERLAUBT, "MARKER_ZITAT_ERLAUBT"),
                        (DEKORATION_ERLAUBT, "DEKORATION_ERLAUBT")):
        for schluessel, grund in liste.items():
            assert len(grund) >= 40, \
                f"{name}[{schluessel}]: Grund zu knapp — {grund!r}"
