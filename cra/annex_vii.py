"""Inhalt der technischen Dokumentation (Anhang VII) — **eine** Liste (#1763).

Bis v8.0.0 gab es zwei, und sie waren verschieden:

* ``cra/traceability_db.ANNEX_VII_BAUSTEINE`` — acht Bausteine, als
  Beleg-Matrix im Traceability-Reiter. Ihr fehlten „angewandte Normen", die
  „Bewertung der grundlegenden Anforderungen" und der „Support-Zeitraum".
* ``shared/documents/catalog._CL_CRA_TECH_DOKU`` — zehn Inhaltspunkte, als
  Soll-Ist-Checkliste des verwalteten Dokuments.

Beide beanspruchten, Anhang VII abzubilden, und **beide zeigten eine
Vollständigkeitsquote**. Welche galt, hing davon ab, welchen Reiter man
öffnete. Für ein Werkzeug, das Nachweisführung verkauft, ist eine zweite Zahl
schlimmer als keine.

Die beiden Zwecke bleiben verschieden — *welcher Inhalt gehört hinein* gegen
*welcher Beleg liegt dafür vor* —, aber sie haben dieselbe Grundlage. Die
steht jetzt hier; beide Seiten leiten sich daraus ab.

**Zur Nummerierung:** Die Angaben stammen aus der bisherigen Checkliste des
Repos und sind nicht juristisch geprüft. Die Lückenanalyse vor der
8.0.0-Freigabe hat widersprüchliche Artikelzitate an mehreren Stellen gefunden
(#1763); eine falsche Nummer kostet mehr Glaubwürdigkeit als eine fehlende.
Geändert wurde hier deshalb **keine** Nummer — nur zusammengeführt, was
auseinanderlief.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnnexPunkt:
    """Ein Inhalt der technischen Dokumentation.

    ``doc_types`` ist die Heuristik der Beleg-Erkennung: Welche Dokumentarten
    zählen für diesen Punkt als Nachweis (``cra/annex_evidence.py``). Punkte
    ohne ``doc_types`` erscheinen in der Inhalts-Checkliste, haben aber keine
    eigene Beleg-Zeile — ihr Nachweis steckt woanders (z. B. im
    Anforderungsregister oder im Support-Zeitraum).
    """

    #: Schlüssel der **Inhalts-Checkliste** (``shared/documents/catalog.py``).
    #: Er ist der Persistenz-Schlüssel des Ist-Status je Dokument — wird er
    #: geändert, verwaisen in jeder laufenden Installation die gesetzten Haken.
    key: str
    label: str
    rechtsbezug: str
    pflicht: bool = True
    doc_types: tuple[str, ...] = ()
    #: Schlüssel der **Beleg-Matrix** (``cra_dokumente.annex_baustein``).
    #: Ebenfalls persistiert, historisch anders benannt. Die beiden
    #: Schlüsselräume zusammenzuführen wäre eine Migration über den Bestand —
    #: die Zuordnung steht deshalb hier, statt dass einer von beiden umbenannt
    #: wird. Leer = derselbe wie ``key``.
    baustein_key: str = ""
    #: Kurzform für die Beleg-Matrix; fehlt sie, wird ``label`` genommen.
    baustein_label: str = ""

    def als_baustein(self) -> dict[str, Any]:
        return {"key": self.baustein_key or self.key,
                "label": self.baustein_label or self.label,
                "doc_types": list(self.doc_types)}


PUNKTE: tuple[AnnexPunkt, ...] = (
    AnnexPunkt(
        "beschreibung",
        "Allgemeine Beschreibung des Produkts mit digitalen Elementen "
        "(Zweck, Versionen, Software/Hardware)",
        "Anhang VII (1)",
        doc_types=("produktbeschreibung", "description"),
        baustein_key="produktbeschreibung",
        baustein_label="Allgemeine Produktbeschreibung & Zweckbestimmung"),
    AnnexPunkt(
        "design_entwicklung",
        "Beschreibung von Konzeption, Entwicklung und Produktion inkl. "
        "Komponenten und Update-Mechanismen",
        "Anhang VII (2)",
        doc_types=("design", "architektur"),
        baustein_key="design",
        baustein_label="Konzeption, Entwicklung & Architektur"),
    AnnexPunkt(
        "essentielle_anforderungen",
        "Bewertung der grundlegenden Cybersicherheitsanforderungen "
        "(Anhang I Teil I)",
        "Anhang VII (3) / Anhang I",
        baustein_label="Bewertung der grundlegenden Anforderungen"),
    AnnexPunkt(
        "schwachstellenbehandlung",
        "Prozesse zur Schwachstellenbehandlung (Anhang I Teil II): Meldung, "
        "koordinierte Offenlegung, Sicherheitsupdates",
        "Anhang VII (3) / Anhang I Teil II",
        doc_types=("psirt", "vuln", "advisory"),
        baustein_key="vuln_handling",
        baustein_label="Vulnerability-Handling-Prozess"),
    AnnexPunkt(
        "risikobewertung",
        "Cybersicherheits-Risikobewertung des Produkts",
        "Anhang VII (3)",
        doc_types=("risikobewertung", "risk"),
        baustein_label="Cybersicherheits-Risikobewertung"),
    AnnexPunkt(
        "support_zeitraum",
        "Festgelegter Unterstützungszeitraum für Sicherheitsupdates",
        "Art. 13 Abs. 8 / Anhang VII",
        baustein_label="Unterstützungszeitraum"),
    AnnexPunkt(
        "normen",
        "Angewandte harmonisierte Normen bzw. Spezifikationen",
        "Anhang VII (4)",
        baustein_label="Angewandte Normen"),
    AnnexPunkt(
        "testberichte",
        "Berichte über durchgeführte Tests zur Verifikation der "
        "Cybersicherheitsanforderungen",
        "Anhang VII (4)",
        doc_types=("testbericht", "test", "pentest"),
        baustein_label="Testberichte & Security-Testing"),
    AnnexPunkt(
        "konformitaetserklaerung_ref",
        "Kopie der EU-Konformitätserklärung",
        "Anhang VII (5)",
        doc_types=("doc", "konformitaetserklaerung"),
        baustein_key="doc",
        baustein_label="EU-Konformitätserklärung (DoC)"),
    AnnexPunkt(
        "sbom",
        "Software-Bill-of-Materials (SBOM) der Top-Level-Abhängigkeiten",
        "Anhang I Teil II (1)",
        pflicht=False,
        doc_types=("sbom",),
        baustein_label="Software-Bill-of-Materials (SBOM)"),
    AnnexPunkt(
        # Die Nutzerinformationen sind ein eigenes Dokument (Anhang II), gehören
        # aber zu den Unterlagen, die bei einer Prüfung vorzulegen sind. Sie
        # standen bisher nur in der Beleg-Matrix; dort bleiben sie, in der
        # Inhalts-Checkliste des technischen Dokuments sind sie **kein**
        # Pflichtinhalt — sonst verlangte die Checkliste den Inhalt eines
        # anderen Dokuments.
        "anleitung",
        "Benutzeranleitung und Sicherheitsinformationen (eigenes Dokument "
        "nach Anhang II)",
        "Anhang II",
        pflicht=False,
        doc_types=("anleitung", "manual"),
        baustein_label="Benutzeranleitung & Sicherheitsinformationen"),
)


def bausteine() -> list[dict[str, Any]]:
    """Beleg-Matrix — **alle** Punkte, auch die ohne eigene Dokumentart.

    Punkte wie „angewandte Normen" oder „Unterstützungszeitraum" haben kein
    hochgeladenes Dokument; ihr Nachweis steckt in den Registern der Anwendung
    und wird dort abgeholt (``cra/annex_evidence.py``). Sie hier wegzulassen
    war der Grund für zwei verschiedene Vollständigkeitsquoten.
    """
    return [p.als_baustein() for p in PUNKTE]


def inhalts_punkte() -> tuple[AnnexPunkt, ...]:
    """Inhalts-Checkliste des technischen Dokuments — ohne das Fremddokument."""
    return tuple(p for p in PUNKTE if p.key != "anleitung")


def checkliste() -> list[Any]:
    """Als ``ChecklistItem`` für ``shared/documents/catalog.py``."""
    from shared.documents.catalog import ChecklistItem

    return [ChecklistItem(p.key, p.label, p.rechtsbezug, p.pflicht)
            for p in inhalts_punkte()]
