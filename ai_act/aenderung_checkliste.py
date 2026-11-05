"""Checkliste je Änderung — Rechts-Kanon des AI Act (#1756).

Die **Form** ist die des CRA-Release-Katalogs (#1744): drei Arten von
Prüfpunkten, je Punkt ein Rechtsbezug, eine Erklärung und — bei ``gerechnet`` —
die Quelle, unter der das Gate das Ergebnis liefert. Diese Trennung ist keine
Darstellungsfrage:

* ``gerechnet`` — aus Daten der Anwendung abgeleitet. Niemand kann sie setzen;
  wären sie von Hand abhakbar, wäre der Nachweis manipulierbar.
* ``entscheidung`` — jedes Mal neu zu beantworten, **mit Begründung**.
* ``gleichbleibend`` — einmal gesetzte Angaben, die je Änderung nur bestätigt
  werden.

Der **Inhalt** ist ein anderer, und nichts davon ist aus dem CRA übertragbar:
Dort geht es um ein Produkt mit digitalen Elementen und seine Schwachstellen,
hier um ein Hochrisiko-KI-System und seine Modell-, Daten- und
Zweckänderungen. Die Pflichten, die eine Änderung auslöst, stehen in Art. 9–15,
Art. 43 Abs. 4, Art. 47/48, Art. 49/71, Art. 72 und Art. 73 der Verordnung
(EU) 2024/1689.

**Zwei Relevanz-Achsen, die der CRA-Katalog nicht hat.** Welche Pflicht eine
Änderung auslöst, hängt hier von zwei Dingen ab, und beide gehören in den
Katalog statt in die Oberfläche:

1. ``gilt_bei`` — die Antwort auf die Kernfrage. Eine erneute
   Konformitätsbewertung samt neuer Konformitätserklärung und CE-Kennzeichnung
   fordert Art. 43 Abs. 4 **nur** bei einer wesentlichen Änderung. Für
   ``vorab_bewertet`` (vorab festgelegt und mitbewertet) greift die Ausnahme —
   diese Punkte entfallen, die Dokumentations-, Protokollierungs- und
   Beobachtungspflichten bleiben. Ohne diese Unterscheidung meldete das
   Werkzeug bei jedem fortlernenden System Daueralarm.
2. ``gilt_bei_grund`` — der Anlass. Daten-Governance nach Art. 10 ist bei
   neuen Trainingsdaten Pflicht und bei einer reinen Zweckänderung nicht;
   umgekehrt bei der menschlichen Aufsicht nach Art. 14.

Single Source of Truth: Neue Pflichten kommen hierher, nicht in die REST-Schicht
und nicht ins Frontend.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Art = Literal["gerechnet", "entscheidung", "gleichbleibend"]

#: Zulässige Ist-Werte eines Punktes.
STATUS = ("offen", "erledigt", "nicht_anwendbar")

#: Alle Antworten auf die Kernfrage (vgl. ``aenderungen_db.WESENTLICH_WERTE``).
_ALLE = ("ja", "nein", "vorab_bewertet")

#: Alle Anlässe (vgl. ``aenderungen_db.GRUND_ARTEN``).
_ALLE_GRUENDE = ("nachtraining", "daten", "zweck", "leistung", "sonstiges")

#: Die Kernfrage. Sie steht im Katalog, damit Bericht und Oberfläche sie mit
#: Rechtsbezug ausgeben können — gesetzt wird sie aber über die eigenen Felder
#: des Vorgangs (drei Antworten, Person, Zeit, Fundstelle).
KERNFRAGE_ID = "wesentliche_aenderung"


@dataclass(frozen=True)
class AenderungCheckItem:
    """Ein Prüfpunkt je Änderung am KI-System.

    ``quelle`` nennt bei ``gerechnet`` den Schlüssel, unter dem
    :func:`ai_act.aenderung_gate.evaluate` das Ergebnis liefert, und bei
    ``gleichbleibend`` die Tabelle, aus der der Wert kommt. Damit ist im Code
    nachvollziehbar, woher eine Zeile im Nachweis stammt.
    """

    id: str
    label: str
    art: Art
    rechtsbezug: str
    erklaerung: str = ""
    quelle: str = ""
    pflicht: bool = True
    #: Sprungziel in der Modul-UI (Tab-ID).
    link: str = ""
    #: Antworten auf die Kernfrage, bei denen der Punkt überhaupt gilt.
    gilt_bei: tuple[str, ...] = field(default=_ALLE)
    #: Änderungsgründe, bei denen der Punkt gilt.
    gilt_bei_grund: tuple[str, ...] = field(default=_ALLE_GRUENDE)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["gilt_bei"] = list(self.gilt_bei)
        d["gilt_bei_grund"] = list(self.gilt_bei_grund)
        return d


# ── Gerechnet ───────────────────────────────────────────────────────────────
# Diese Punkte spiegeln die Prüfungen des Gates. Sie stehen hier, damit der
# Nachweis sie mit Rechtsbezug und Erklärung ausgeben kann — gerechnet werden
# sie dort, nicht hier. Zwei Rechenwege für dieselbe Aussage wären zwei
# Wahrheiten.
_GERECHNET: tuple[AenderungCheckItem, ...] = (
    AenderungCheckItem(
        "annex_iv_aktuell", "Technische Dokumentation (Anhang IV) nachgezogen",
        "gerechnet", "Art. 11 i.V.m. Anhang IV",
        "Die technische Dokumentation ist während der gesamten Lebensdauer "
        "aktuell zu halten. Geprüft wird, ob sie nach dieser Änderung "
        "fortgeschrieben wurde — eine Dokumentation, die einen früheren "
        "Modellstand beschreibt, belegt das System nicht, das in Betrieb ist.",
        quelle="annex_iv", link="pflichtdoku"),
    AenderungCheckItem(
        "doc_ce_aktuell", "Konformitätserklärung und CE-Kennzeichnung erneuert",
        "gerechnet", "Art. 43 Abs. 4, Art. 47, Art. 48",
        "Eine wesentliche Änderung erfordert eine erneute Konformitätsbewertung "
        "und damit eine neue EU-Konformitätserklärung. Bei vorab festgelegten "
        "und mitbewerteten Änderungen entfällt das (Ausnahme des Art. 43 Abs. 4).",
        quelle="doc_ce", link="conformity", gilt_bei=("ja",)),
    AenderungCheckItem(
        "eu_registrierung_aktuell", "Registrierung in der EU-Datenbank aktualisiert",
        "gerechnet", "Art. 49, Art. 71",
        "Die Angaben in der EU-Datenbank müssen den tatsächlichen Stand des "
        "Systems abbilden; Änderungen sind nachzutragen.",
        quelle="eu_registrierung", link="dokumente"),
    AenderungCheckItem(
        "pmm_plan_angepasst", "Beobachtungsplan nach dem Inverkehrbringen angepasst",
        "gerechnet", "Art. 72",
        "Der Beobachtungsplan muss zu dem System passen, das beobachtet wird. "
        "Nach einem Nachtraining sind Kennzahlen und Drift-Erkennung in der "
        "Regel nicht mehr dieselben.",
        quelle="pmm", link="pflichtdoku"),
    AenderungCheckItem(
        "keine_offene_vorfallmeldung", "Keine offene oder überfällige Vorfallmeldung",
        "gerechnet", "Art. 73",
        "Eine Änderung während einer laufenden Meldefrist ist ein Signal; eine "
        "versäumte Frist ist eine Pflichtverletzung gegenüber der Marktaufsicht "
        "und kein Nachweismangel.",
        quelle="vorfaelle", link="incidents"),
)

# ── Entscheidung ────────────────────────────────────────────────────────────
_ENTSCHEIDUNG: tuple[AenderungCheckItem, ...] = (
    AenderungCheckItem(
        KERNFRAGE_ID, "Ist dies eine wesentliche Änderung?",
        "entscheidung", "Art. 3 Nr. 23, Art. 43 Abs. 4",
        "Die Frage, um die der ganze Vorgang gebaut ist — und sie hat drei "
        "Antworten, nicht zwei: ja, nein, oder vorab festgelegt und bei der "
        "Konformitätsbewertung bereits mitbewertet. Die dritte ist der "
        "Ausnahmetatbestand des Art. 43 Abs. 4 und bei fortlernenden Systemen "
        "der Normalfall; sie löst keine erneute Konformitätsbewertung aus, "
        "verlangt aber eine Fundstelle in der technischen Dokumentation.",
        link="aenderungen"),
    AenderungCheckItem(
        "risikomanagement_aktualisiert", "Risikomanagementsystem aktualisiert",
        "entscheidung", "Art. 9",
        "Das Risikomanagement ist ein fortlaufender Prozess über den gesamten "
        "Lebenszyklus. Eine Änderung am System kann neue Risiken schaffen und "
        "bekannte verschieben — beides gehört in die verknüpfte "
        "Risikobewertung, nicht in ein Freitextfeld.",
        link="anforderungen"),
    AenderungCheckItem(
        "daten_governance_geprueft", "Daten-Governance der neuen Daten geprüft",
        "entscheidung", "Art. 10",
        "Neue Trainings-, Validierungs- oder Testdaten sind auf Relevanz, "
        "Repräsentativität, Fehlerfreiheit und Verzerrungen zu prüfen. Bei einer "
        "Änderung ohne neue Daten entfällt der Punkt.",
        link="pflichtdoku", gilt_bei_grund=("nachtraining", "daten")),
    AenderungCheckItem(
        "protokollierung_geprueft", "Protokollierung deckt den neuen Stand ab",
        "entscheidung", "Art. 12",
        "Die automatische Aufzeichnung von Ereignissen muss den geänderten Stand "
        "erfassen — sonst fehlt genau für den Zeitraum nach der Änderung die "
        "Nachvollziehbarkeit.",
        link="pflichtdoku"),
    AenderungCheckItem(
        "nutzerinformation_aktualisiert", "Betriebsanleitung / Nutzerinformation aktualisiert",
        "entscheidung", "Art. 13",
        "Betreiber müssen erfahren, was sich an Zweckbestimmung, Leistung und "
        "Grenzen geändert hat. Bei geänderter Zweckbestimmung ist das Pflicht.",
        link="dokumente", gilt_bei_grund=("zweck", "leistung")),
    AenderungCheckItem(
        "menschliche_aufsicht_geprueft", "Menschliche Aufsicht auf den neuen Zweck geprüft",
        "entscheidung", "Art. 14",
        "Die Aufsichtsmaßnahmen sind auf die Zweckbestimmung zugeschnitten. "
        "Ändert sich der Zweck, passt die bisherige Aufsicht in der Regel nicht "
        "mehr — bis zu der Frage, wer überhaupt eingreifen darf.",
        link="pflichtdoku", gilt_bei_grund=("zweck", "leistung")),
    AenderungCheckItem(
        "genauigkeit_robustheit_geprueft", "Genauigkeit, Robustheit und Cybersicherheit erneut geprüft",
        "entscheidung", "Art. 15",
        "Nach einem Nachtraining oder bei im Betrieb abweichender Leistung sind "
        "die zugesagten Kennzahlen neu zu belegen.",
        link="anforderungen",
        gilt_bei_grund=("nachtraining", "daten", "leistung")),
    AenderungCheckItem(
        "konformitaetsbewertung_durchlaufen",
        "Erneute Konformitätsbewertung durchgeführt",
        "entscheidung", "Art. 43 Abs. 4",
        "Bei einer wesentlichen Änderung ist das Konformitätsbewertungsverfahren "
        "erneut zu durchlaufen — bei Anhang-III-Nr.-1-Systemen unter Beteiligung "
        "der notifizierten Stelle.",
        link="conformity", gilt_bei=("ja",)),
)

# ── Gleichbleibend ──────────────────────────────────────────────────────────
_GLEICHBLEIBEND: tuple[AenderungCheckItem, ...] = (
    AenderungCheckItem(
        "qms_unveraendert", "Qualitätsmanagementsystem unverändert wirksam",
        "gleichbleibend", "Art. 17", quelle="aiact_conformity", link="conformity"),
    AenderungCheckItem(
        "aufbewahrung_unveraendert",
        "Aufbewahrung der Dokumentation unverändert geregelt (10 Jahre)",
        "gleichbleibend", "Art. 18", quelle="aiact_system_doku", link="dokumente"),
    AenderungCheckItem(
        "marktaufsicht_kontakt", "Kontakt zur Marktaufsichtsbehörde unverändert",
        "gleichbleibend", "Art. 73 Abs. 1",
        quelle="aiact_post_market_monitoring", link="pflichtdoku"),
)

KATALOG: tuple[AenderungCheckItem, ...] = _GERECHNET + _ENTSCHEIDUNG + _GLEICHBLEIBEND

#: Punkte, die eine Begründung brauchen, sobald sie nicht ``offen`` sind.
BEGRUENDUNG_PFLICHT: frozenset[str] = frozenset(
    i.id for i in KATALOG if i.art == "entscheidung")


def katalog() -> list[dict[str, Any]]:
    """Der Katalog als JSON-fähige Liste (für REST, Oberfläche und Bericht)."""
    return [i.to_dict() for i in KATALOG]


def item(item_id: str) -> AenderungCheckItem | None:
    return next((i for i in KATALOG if i.id == item_id), None)


def gerechnete_ids() -> frozenset[str]:
    """IDs, die über die API **nicht** gesetzt werden dürfen."""
    return frozenset(i.id for i in KATALOG if i.art == "gerechnet")


def gilt(item_: AenderungCheckItem, wesentlich: str = "", grund_art: str = "") -> bool:
    """Gilt der Punkt für diese Antwort und diesen Anlass?

    Solange die Kernfrage unbeantwortet ist (``wesentlich == ''``), gilt **jeder**
    Punkt: Vorher ist nicht entschieden, ob die Ausnahme des Art. 43 Abs. 4
    greift, und ein ausgeblendeter Punkt sähe aus wie ein erledigter.
    """
    if wesentlich and wesentlich not in item_.gilt_bei:
        return False
    if grund_art and grund_art not in item_.gilt_bei_grund:
        return False
    return True


def relevanter_katalog(wesentlich: str = "", grund_art: str = "") -> list[dict[str, Any]]:
    """Katalog mit der abgeleiteten Relevanz je Punkt.

    Punkte, die nach Antwort oder Anlass nicht gelten, bleiben **sichtbar** und
    werden als ``relevant: False`` markiert — mit dem Grund. Sie stillschweigend
    zu entfernen wäre die bequeme Lösung und die falsche: Im Nachweis soll
    stehen, *dass* eine Pflicht geprüft und *warum* sie nicht einschlägig war.
    """
    out: list[dict[str, Any]] = []
    for i in KATALOG:
        d = i.to_dict()
        rel = gilt(i, wesentlich, grund_art)
        d["relevant"] = rel
        if not rel:
            if wesentlich and wesentlich not in i.gilt_bei:
                d["nicht_relevant_grund"] = (
                    "entfällt, weil die Änderung nicht als wesentlich eingeordnet "
                    "wurde" if wesentlich == "nein" else
                    "entfällt nach der Ausnahme des Art. 43 Abs. 4 (vorab "
                    "festgelegt und mitbewertet)")
            else:
                d["nicht_relevant_grund"] = (
                    f"entfällt beim Änderungsgrund „{grund_art}“")
        out.append(d)
    return out


def leerer_stand() -> dict[str, dict[str, Any]]:
    """Ist-Stand eines frischen Vorgangs: alles offen, nichts vorbelegt.

    Bewusst ohne Übernahme aus der Vorgänger-Änderung: Ein vorbelegtes
    „erledigt" wäre eine Aussage, die niemand getroffen hat.
    """
    return {i.id: {"status": "offen", "begruendung": "", "von": "", "am": ""}
            for i in KATALOG}
