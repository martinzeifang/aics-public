"""Checkliste je Release — Rechts-Kanon der CRA-Pflichten im Tagesgeschäft (#1744).

CRA zerfällt für den Anwender in zwei Phasen: Erst wird ein Produkt in den
konformen Zustand gebracht (einmalig), danach ist bei **jedem Release**
nachzuweisen, dass es dabei geblieben ist. Diese Datei beschreibt die zweite
Phase.

Der Kern ist die Unterscheidung in drei **Arten** von Prüfpunkten, und sie ist
keine Darstellungsfrage:

* ``gerechnet`` — aus Daten der Anwendung abgeleitet. Niemand kann sie setzen;
  wären sie von Hand abhakbar, wäre der Nachweis manipulierbar.
* ``entscheidung`` — jedes Mal neu zu beantworten, **mit Begründung**. Das sind
  die Punkte, die kein Rechenweg kennt: Ist diese Änderung eine wesentliche im
  Sinne von Art. 3 Nr. 31? Wurde das Advisory veröffentlicht?
* ``gleichbleibend`` — einmal gesetzte Angaben, die je Release nur bestätigt
  werden (Support-Zeitraum, Update-Kanal, PSIRT-Kontakt). Sie werden **nicht
  kopiert**, sondern aus ihrer Quelle gelesen; die Bestätigung hält nur fest,
  dass jemand hingesehen hat.

Ohne diese Trennung passiert eines von zwei Dingen: Entweder hakt jemand eine
Liste ab, die sich selbst abhaken ließe — dann ist sie als Nachweis wertlos —,
oder er tippt jedes Release dieselben Angaben neu, und dann wird die Liste
umgangen. Der Anwender hat es genau so beschrieben: „Vieles ist jedes Mal
gleich, anderes muss ich prüfen."

Single Source of Truth: Neue Pflichten kommen hierher, nicht in die REST-Schicht
und nicht ins Frontend.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Art = Literal["gerechnet", "entscheidung", "gleichbleibend", "neubewertung"]

#: Zulässige Ist-Werte eines Punktes. ``nicht_anwendbar`` braucht wie
#: ``erledigt`` bei einer Entscheidung eine Begründung — „gilt hier nicht" ist
#: eine Aussage über das Produkt und keine Formalie.
STATUS = ("offen", "erledigt", "nicht_anwendbar")


@dataclass(frozen=True)
class ReleaseCheckItem:
    """Ein Prüfpunkt je Release.

    ``quelle`` nennt bei ``gerechnet`` den Schlüssel, unter dem
    ``cra.konformitaet_gate.evaluate`` das Ergebnis liefert, und bei
    ``gleichbleibend`` die Tabelle, aus der der Wert kommt. Damit ist im Code
    nachvollziehbar, woher eine Zeile im Nachweis stammt — die Frage, die bei
    einem Audit als erste kommt.
    """

    id: str
    label: str
    art: Art
    rechtsbezug: str
    erklaerung: str = ""
    quelle: str = ""
    pflicht: bool = True
    #: Sprungziel in der Modul-UI (wie ``offene_punkte[].link`` im Gate).
    link: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Gerechnet ───────────────────────────────────────────────────────────────
# Diese Punkte spiegeln die Release-Prüfungen des Gates (#1745). Sie stehen hier,
# damit der Nachweis sie mit Rechtsbezug und Erklärung ausgeben kann — gerechnet
# werden sie dort, nicht hier. Zwei Rechenwege für dieselbe Aussage wären zwei
# Wahrheiten (die Lehre aus #1726/#1727).
_GERECHNET: tuple[ReleaseCheckItem, ...] = (
    ReleaseCheckItem(
        "keine_offenen_kritischen", "Keine offenen kritischen oder hohen Schwachstellen",
        "gerechnet", "Anhang I Teil II Nr. 1–2",
        "Offene kritische Befunde schließen ein Release aus; behandelt oder als "
        "Risiko akzeptiert muss jeder davon sein.",
        quelle="offene_kritische_schwachstellen", link="pflichtdoku"),
    ReleaseCheckItem(
        "advisory_zu_behobenen", "Behobene Schwachstellen dieses Releases sind veröffentlicht",
        "gerechnet", "Anhang I Teil II Nr. 8",
        "Wer eine Schwachstelle behebt, muss darüber informieren. Geprüft wird, "
        "ob jede in dieser Version behobene Schwachstelle eine Advisory-Adresse trägt.",
        quelle="behobene_ohne_advisory", link="pflichtdoku"),
    ReleaseCheckItem(
        "sbom_zur_version", "SBOM liegt für diese Version vor",
        "gerechnet", "Anhang I Teil II Nr. 1",
        "Die Stückliste gehört zur Version, nicht zum Produkt — sonst belegt sie "
        "einen anderen Stand als den ausgelieferten.",
        quelle="sbom_version_fehlt", link="pflichtdoku"),
    ReleaseCheckItem(
        "support_deckt_release", "Release liegt im zugesagten Support-Zeitraum",
        "gerechnet", "Art. 13 Abs. 8",
        "Nach dem zugesagten Ende darf kein Produkt mit digitalen Elementen mehr "
        "als unterstützt in Verkehr gebracht werden.",
        quelle="support_ueberschritten", link="konformitaet"),
    ReleaseCheckItem(
        "keine_ueberfaellige_meldung", "Keine überfällige Meldefrist",
        "gerechnet", "Art. 14",
        "Ein Release während einer laufenden 24-Stunden- oder 72-Stunden-Frist ist "
        "kein Formfehler, sondern ein offener Rechtsverstoß.",
        quelle="ueberfaellige_meldungen", link="meldungen"),
    ReleaseCheckItem(
        "bewertungsweg_zulaessig", "Bewertungsweg für die Produktklasse zulässig",
        "gerechnet", "Art. 32 Abs. 1–4, Anhang VIII",
        "Die Produktklasse bestimmt, welche Verfahren offenstehen: Anhang III "
        "Klasse II und Anhang IV lassen die Selbstbewertung nach Modul A nicht "
        "zu. Ein unzulässiger Weg ist keine Lücke in der Akte, sondern eine "
        "Nicht-Konformität — die darauf gestützte EU-Konformitätserklärung "
        "trägt nicht. Die Klassifizierung selbst bleibt eine Entscheidung des "
        "Anwenders (Anhang III/IV sind Produktlisten); gerechnet wird nur ihre "
        "Folge (#1759).",
        quelle="bewertungsweg_unzulaessig", link="konformitaet"),
    ReleaseCheckItem(
        "annex_vii_vollstaendig", "Technische Dokumentation (Anhang VII) vollständig",
        "gerechnet", "Anhang VII", quelle="annex_vollstaendig", link="traceability"),
    ReleaseCheckItem(
        "doc_zur_version", "EU-Konformitätserklärung für diese Version ausgestellt",
        "gerechnet", "Art. 28, Anhang V", quelle="doc_ausgestellt", link="konformitaet"),
)

# ── Entscheidung ────────────────────────────────────────────────────────────
_ENTSCHEIDUNG: tuple[ReleaseCheckItem, ...] = (
    ReleaseCheckItem(
        "wesentliche_aenderung", "Ist dieses Release eine wesentliche Änderung?",
        "entscheidung", "Art. 3 Nr. 31",
        "Die wichtigste Frage des ganzen Vorgangs: Eine wesentliche Änderung löst "
        "eine neue Konformitätsbewertung, eine neue Konformitätserklärung und eine "
        "aktualisierte technische Dokumentation aus. Sie lässt sich nicht rechnen — "
        "sie hängt davon ab, ob sich Funktion oder Sicherheitseigenschaften ändern.",
        link="releases"),
    ReleaseCheckItem(
        "neubewertung_umfang", "Welche grundlegenden Anforderungen wurden neu bewertet?",
        "entscheidung", "Anhang I Teil I",
        "Bei einer wesentlichen Änderung genügt es nicht, sie festzustellen — der "
        "Umfang der Neubewertung gehört in den Nachweis.",
        pflicht=False, link="requirements"),
    ReleaseCheckItem(
        "release_notes_veroeffentlicht", "Nutzerinformation zum Release veröffentlicht",
        "entscheidung", "Art. 13 Abs. 18, Anhang II",
        "Anwender müssen erfahren, was sich sicherheitsrelevant geändert hat und "
        "wie sie das Update erhalten.",
        link="dokumente"),
    ReleaseCheckItem(
        "advisory_veroeffentlicht", "Security Advisory veröffentlicht und erreichbar",
        "entscheidung", "Anhang I Teil II Nr. 8",
        "Dass eine Advisory-Adresse hinterlegt ist, prüft die Anwendung. Dass "
        "dahinter ein lesbarer Hinweis steht, muss ein Mensch bestätigen.",
        pflicht=False, link="pflichtdoku"),
    ReleaseCheckItem(
        "fremdkomponenten_bewertet", "Neue oder angehobene Fremdkomponenten bewertet",
        "entscheidung", "Anhang I Teil II Nr. 1, Art. 13 Abs. 5",
        "Sorgfaltspflicht bei Komponenten Dritter: Eine neue Abhängigkeit bringt "
        "ihre Schwachstellen mit.",
        link="pflichtdoku"),
)

# ── Gleichbleibend ──────────────────────────────────────────────────────────
_GLEICHBLEIBEND: tuple[ReleaseCheckItem, ...] = (
    ReleaseCheckItem(
        "support_zeitraum", "Support-Zeitraum unverändert",
        "gleichbleibend", "Art. 13 Abs. 8", quelle="cra_support_period", link="konformitaet"),
    ReleaseCheckItem(
        "update_kanal", "Update-Kanal unverändert",
        "gleichbleibend", "Anhang I Teil II Nr. 7", quelle="cra_support_period",
        link="konformitaet"),
    ReleaseCheckItem(
        "psirt_kontakt", "Meldestelle für Schwachstellen unverändert erreichbar",
        "gleichbleibend", "Anhang I Teil II Nr. 5", quelle="cra_psirt",
        link="pflichtdoku"),
    ReleaseCheckItem(
        "disclosure_policy", "Offenlegungs-Richtlinie unverändert",
        "gleichbleibend", "Anhang I Teil II Nr. 5", quelle="cra_psirt",
        link="pflichtdoku"),
)

# ── Neubewertung bei wesentlicher Änderung (#1755) ──────────────────────────
# Diese Punkte erscheinen **nur**, wenn die wesentliche Änderung mit „ja"
# beantwortet wurde. Sie sind der Grund, warum diese Frage überhaupt gestellt
# wird: Eine wesentliche Änderung (Art. 3 Nr. 31) löst die Konformitätsbewertung
# erneut aus, und die Risikoabschätzung ist fortzuschreiben — der eigene
# Anforderungskatalog sagt es bei ``ART13-01`` selbst: „Regelmäßige
# Aktualisierung bei wesentlichen Produktänderungen."
#
# Die vier Punkte entsprechen ``release_db.REASSESS_ITEMS``. Dort wurden sie
# seit #1609 geöffnet — und von niemandem je gelesen. Hier bekommen sie einen
# Ort, an dem sie sichtbar sind und abgeschlossen werden müssen.
#
# Sie wirken **rot**, nicht ``bedingt``: Eine wesentliche Änderung ohne neue
# Konformitätsbewertung ist eine Nicht-Konformität und keine Lücke in der Akte.
_NEUBEWERTUNG: tuple[ReleaseCheckItem, ...] = (
    ReleaseCheckItem(
        "neubewertung_risikobewertung", "Risikoabschätzung für die Änderung fortgeschrieben",
        "neubewertung", "Art. 13 Abs. 1–3, Anhang I Teil I Nr. 1",
        "Die Cybersicherheits-Risikoabschätzung ist die Grundlage des ganzen "
        "Nachweises. Was sich ändert, muss darin auftauchen — und wenn nichts "
        "Neues entsteht, gehört diese Aussage begründet in die Akte.",
        quelle="rb_neue_risiken", link="requirements"),
    ReleaseCheckItem(
        "neubewertung_konformitaetsbewertung", "Konformitätsbewertung für die Änderung wiederholt",
        "neubewertung", "Art. 32, Anhang VIII",
        "Die Änderung und ihre Auswirkungen auf das übrige Produkt sind erneut "
        "zu bewerten — im selben Verfahren wie beim ersten Mal.",
        link="konformitaet"),
    ReleaseCheckItem(
        "neubewertung_technische_doku", "Technische Dokumentation nachgezogen",
        "neubewertung", "Anhang VII",
        "Die technische Dokumentation beschreibt das Produkt, das in Verkehr "
        "gebracht wird — nach der Änderung also ein anderes.",
        link="traceability"),
    ReleaseCheckItem(
        "neubewertung_doc", "EU-Konformitätserklärung neu ausgestellt",
        "neubewertung", "Art. 28, Anhang V",
        "Die Erklärung bezieht sich auf einen bestimmten Stand des Produkts.",
        link="konformitaet"),
)

KATALOG: tuple[ReleaseCheckItem, ...] = (
    _GERECHNET + _ENTSCHEIDUNG + _GLEICHBLEIBEND + _NEUBEWERTUNG)

#: Punkte, die erst bei „wesentliche Änderung = ja" gelten.
NEUBEWERTUNG_IDS: frozenset[str] = frozenset(i.id for i in _NEUBEWERTUNG)

#: Punkte, die eine Begründung brauchen, sobald sie nicht ``offen`` sind.
BEGRUENDUNG_PFLICHT: frozenset[str] = frozenset(
    i.id for i in KATALOG if i.art in ("entscheidung", "neubewertung"))


def katalog() -> list[dict[str, Any]]:
    """Der Katalog als JSON-fähige Liste (für REST und Bericht)."""
    return [i.to_dict() for i in KATALOG]


def item(item_id: str) -> ReleaseCheckItem | None:
    return next((i for i in KATALOG if i.id == item_id), None)


def gerechnete_ids() -> frozenset[str]:
    """IDs, die über die API **nicht** gesetzt werden dürfen."""
    return frozenset(i.id for i in KATALOG if i.art == "gerechnet")


def leerer_stand() -> dict[str, dict[str, Any]]:
    """Ist-Stand eines frischen Vorgangs: alles offen, nichts vorbelegt.

    Bewusst ohne Übernahme aus dem Vorgänger-Release — außer den
    ``gleichbleibend``-Punkten, die ihren Wert ohnehin aus der Quelle lesen.
    Ein vorbelegtes „erledigt" wäre eine Aussage, die niemand getroffen hat.
    """
    return {i.id: {"status": "offen", "begruendung": "", "von": "", "am": ""}
            for i in KATALOG}
