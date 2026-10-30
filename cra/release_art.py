"""Art eines Releases: Sicherheitsupdate, Funktionsupdate, wesentliche Änderung (#1793).

DIE FRAGE DAHINTER
„Muss ich für jedes Sicherheitsupdate denselben Aufwand betreiben wie für ein
Funktionsupdate?" Nein — und die Verordnung sagt es deutlicher, als man erwartet.
Erwägungsgrund 39 der Verordnung (EU) 2024/2847:

    „Wenn eine Sicherheitsaktualisierung, mit der das Cybersicherheitsrisiko
    eines Produkts mit digitalen Elementen verringert werden soll, die
    Zweckbestimmung eines Produkts mit digitalen Elementen nicht verändert, gilt
    sie nicht als wesentliche Änderung."

Und ausdrücklich auch dann nicht, wenn dabei Funktionen oder Leistung geändert
werden — „zu dem alleinigen Zweck, das Cybersicherheitsrisiko zu senken".
Umgekehrt ist eine Funktionsaktualisierung, die die beabsichtigten Funktionen
oder die Art oder Leistung verändert, in der Regel wesentlich, „da das
Hinzufügen neuer Funktionen in der Regel zu einer größeren Angriffsfläche führt".

Damit hängt der ganze teure Teil eines Release-Vorgangs an einer einzigen
Einstufung: Die vier Neubewertungs-Punkte (``release_checkliste._NEUBEWERTUNG``)
erscheinen nur bei „wesentliche Änderung = ja".

WARUM DIE ART TROTZDEM NICHT DIE ANTWORT ERSETZT
Die Art ist eine Erklärung des Herstellers, kein Rechenergebnis. Sie **schlägt**
die Antwort auf die Kernfrage vor und liefert eine Begründung, die sich am
Verordnungstext entlangschreibt — gespeichert wird erst, wenn ein Mensch sie
abschickt. Ein Schalter, der die Entscheidung ersetzt, wäre genau die Umgehung,
vor der der Dateikopf der Checkliste warnt: Eine Liste, die sich selbst abhaken
lässt, ist als Nachweis wertlos.

Für ``funktionsupdate`` gibt es **bewusst keinen Vorschlag**. Ob ein
Funktionsupdate wesentlich ist, hängt nach Erwägungsgrund 39 davon ab, ob es die
Funktionen, die Art oder die Leistung verändert — eine geringfügige
Verbesserung, eine neue Sprache oder ein neues Piktogramm sind es in der Regel
nicht. Das kann nur beurteilen, wer die Änderung kennt.

WAS DIE ABKÜRZUNG GEGEN MISSBRAUCH SICHERT
:func:`widersprueche` rechnet die Erklärung gegen die eigene Akte. Besonders der
dritte Fall ist eine Stelle, an der die Verordnung konkreter ist als die meisten
Prozesse: Anhang I Teil II Nr. 2 verlangt, dass neue Sicherheitsaktualisierungen
„soweit technisch machbar … getrennt von den Funktionsaktualisierungen
bereitgestellt werden", und Erwägungsgrund 39 schiebt der naheliegenden
Umgehung den Riegel vor — bei der Beurteilung einer Funktionsaktualisierung
„spielt es keine Rolle, ob sie als separate Aktualisierung oder in Kombination
mit einer Sicherheitsaktualisierung bereitgestellt wird". Ein Funktionsupdate
wird also nicht dadurch harmlos, dass ein Sicherheitsfix mitfährt.
"""
from __future__ import annotations

from typing import Any

#: Zulässige Werte. Leer heißt **unbestimmt** — so steht jeder Bestandsvorgang
#: da, und das ist kein Mangel: Vor #1793 wurde die Art nicht erhoben.
ARTEN: tuple[str, ...] = ("sicherheitsupdate", "funktionsupdate", "wesentliche_aenderung")

LABELS: dict[str, str] = {
    "": "unbestimmt",
    "sicherheitsupdate": "Sicherheitsupdate",
    "funktionsupdate": "Funktionsupdate",
    "wesentliche_aenderung": "Wesentliche Änderung",
}

ERKLAERUNG: dict[str, str] = {
    "sicherheitsupdate": (
        "Behebt Schwachstellen und senkt das Cybersicherheitsrisiko. Die "
        "Zweckbestimmung bleibt unverändert — auch dann, wenn dafür Funktionen "
        "oder Leistung angepasst werden."),
    "funktionsupdate": (
        "Ändert oder ergänzt Funktionen. Ob das eine wesentliche Änderung ist, "
        "hängt davon ab, ob sich die beabsichtigten Funktionen, die Art oder die "
        "Leistung des Produkts ändern."),
    "wesentliche_aenderung": (
        "Verändert die Zweckbestimmung oder das Cybersicherheitsrisiko in einer "
        "Weise, die in der ursprünglichen Risikobewertung nicht vorgesehen war."),
}

#: Begründungsentwurf für die Kernfrage. Er schreibt den Erwägungsgrund nach und
#: lässt die Lücke stehen, die nur der Hersteller füllen kann — was geändert
#: wurde. Ein Entwurf, der schon vollständig klingt, wird nicht gelesen.
BEGRUENDUNG_ENTWURF: dict[str, str] = {
    "sicherheitsupdate": (
        "Dieses Release behebt Schwachstellen und dient dem alleinigen Zweck, "
        "das Cybersicherheitsrisiko zu senken. Die Zweckbestimmung des Produkts "
        "bleibt unverändert; neue Funktionen kommen nicht hinzu. Nach "
        "Erwägungsgrund 39 der Verordnung (EU) 2024/2847 gilt eine solche "
        "Sicherheitsaktualisierung nicht als wesentliche Änderung. "
        "[Hier ergänzen: welche Schwachstellen behoben wurden.]"),
    "wesentliche_aenderung": (
        "Dieses Release verändert das Produkt in einer Weise, die sich auf die "
        "Konformität mit den grundlegenden Cybersicherheitsanforderungen in "
        "Anhang I Teil I auswirkt oder die Zweckbestimmung ändert (Art. 3 Nr. 30 "
        "der Verordnung (EU) 2024/2847). "
        "[Hier ergänzen: was geändert wurde und warum das wesentlich ist.]"),
}


def ist_gueltig(art: str) -> bool:
    return str(art or "") in ("",) + ARTEN


def label(art: str) -> str:
    return LABELS.get(str(art or ""), LABELS[""])


def vorschlag(art: str) -> dict[str, str]:
    """Vorschlag für die Kernfrage — ``{"wert": …, "grund": …}``.

    Leerer ``wert`` heißt: kein Vorschlag, die Frage ist eigenständig zu
    beantworten. Das ist bei ``funktionsupdate`` und bei unbestimmter Art der
    Fall und **keine** Lücke, sondern die ehrliche Auskunft.
    """
    art = str(art or "")
    if art == "sicherheitsupdate":
        return {"wert": "nein", "grund": BEGRUENDUNG_ENTWURF["sicherheitsupdate"]}
    if art == "wesentliche_aenderung":
        return {"wert": "ja", "grund": BEGRUENDUNG_ENTWURF["wesentliche_aenderung"]}
    return {"wert": "", "grund": ""}


def widersprueche(art: str, *, wesentliche_aenderung: str = "",
                  neue_komponenten: int | None = None,
                  behobene_schwachstellen: int | None = None) -> list[dict[str, Any]]:
    """Die Erklärung gegen die eigene Akte rechnen.

    Reine Funktion — die Zahlen holt der Aufrufer. ``None`` heißt „nicht
    geprüft" und erzeugt keinen Befund; das ist dieselbe Regel wie überall im
    Gate, und sie ist hier besonders wichtig: Ein Projekt ohne SBOM soll nicht
    deshalb einen Widerspruch gemeldet bekommen, weil nichts zu vergleichen war.

    Keiner dieser Befunde ist rot. Sie sagen „das sieht nicht zusammen aus",
    nicht „das Produkt ist nicht konform" — die Einstufung bleibt die Aussage
    eines Menschen, und rot ist der Nicht-Konformität vorbehalten.
    """
    art = str(art or "")
    wesentlich = str(wesentliche_aenderung or "")
    befunde: list[dict[str, Any]] = []
    if art not in ARTEN:
        return befunde

    if art == "sicherheitsupdate" and wesentlich == "ja":
        befunde.append({
            "id": "art_gegen_antwort",
            "text": "Als Sicherheitsupdate erklärt, die Kernfrage ist aber mit „ja“ "
                    "beantwortet",
            "hinweis": "Beides kann nicht stimmen. Entweder ist die Art zu "
                       "korrigieren oder die Antwort auf die Kernfrage.",
            "rechtsbezug": "Art. 3 Nr. 30, Erwägungsgrund 39",
        })
    if art == "wesentliche_aenderung" and wesentlich == "nein":
        befunde.append({
            "id": "art_gegen_antwort",
            "text": "Als wesentliche Änderung erklärt, die Kernfrage ist aber mit "
                    "„nein“ beantwortet",
            "hinweis": "Entweder ist die Art zu korrigieren oder die Antwort auf "
                       "die Kernfrage.",
            "rechtsbezug": "Art. 3 Nr. 30",
        })

    if art == "sicherheitsupdate" and (neue_komponenten or 0) > 0:
        befunde.append({
            "id": "art_neue_komponenten",
            "text": f"Als Sicherheitsupdate erklärt, die SBOM führt aber "
                    f"{neue_komponenten} neu aufgenommene Komponente(n)",
            "hinweis": "Eine angehobene Version gehört zum Sicherheitsupdate; eine "
                       "neu hinzugekommene Abhängigkeit deutet auf Funktion hin. "
                       "Wenn es dabei bleibt, gehört der Grund in die Begründung.",
            "rechtsbezug": "Erwägungsgrund 39, Art. 13 Abs. 5",
        })

    if art == "funktionsupdate" and (behobene_schwachstellen or 0) > 0:
        befunde.append({
            "id": "art_gebuendelt",
            "text": f"Funktionsupdate behebt zugleich {behobene_schwachstellen} "
                    f"Schwachstelle(n)",
            "hinweis": "Anhang I Teil II Nr. 2 verlangt, dass neue "
                       "Sicherheitsaktualisierungen soweit technisch machbar "
                       "getrennt von Funktionsaktualisierungen bereitgestellt "
                       "werden. Ist das hier nicht machbar, gehört der Grund in "
                       "die Akte — und die Bündelung ändert nichts an der "
                       "Einstufung des Funktionsanteils.",
            "rechtsbezug": "Anhang I Teil II Nr. 2, Erwägungsgrund 39",
        })

    return befunde
