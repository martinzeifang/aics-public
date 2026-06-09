"""S2 (#1151) — Rechts-Kanon der erzeugungspflichtigen Dokumente je Modul.

Single Source of Truth für die Soll-Ist-Anzeige im Register (S5) und das
Assistant-Wiring (S8–S13). Erweiterbar — neue Pflichtdokumente hier ergänzen.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class DocSpec:
    doc_type: str
    titel: str
    rechtsgrundlage: str
    kategorie: str
    beschreibung: str = ""
    suggested_assistant: str | None = None
    pflicht: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DOCUMENT_CATALOG: dict[str, list[DocSpec]] = {
    "ai_act": [
        DocSpec("technische_doku_annex_iv", "Technische Dokumentation (Annex IV)",
                "Art. 11 EU AI Act", "Konformität",
                "Technische Dokumentation für Hochrisiko-KI-Systeme."),
        DocSpec("konformitaetserklaerung", "EU-Konformitätserklärung (Annex V)",
                "Art. 47 EU AI Act", "Konformität",
                "EU-Konformitätserklärung.", suggested_assistant="a8"),
        DocSpec("transparenzhinweise", "Transparenzhinweise",
                "Art. 50 EU AI Act", "Transparenz",
                "Transparenzpflichten gegenüber Nutzern.", suggested_assistant="a9"),
        DocSpec("betriebsanleitung", "Betriebsanleitung / Instructions for Use",
                "Art. 13 EU AI Act", "Betrieb",
                "Anleitung für Betreiber."),
        DocSpec("fria", "Grundrechte-Folgenabschätzung (FRIA)",
                "Art. 27 EU AI Act", "Grundrechte",
                "Fundamental Rights Impact Assessment."),
        DocSpec("pmm_plan", "Post-Market-Monitoring-Plan",
                "Art. 72 EU AI Act", "Überwachung",
                "Plan zur Marktbeobachtung nach Inverkehrbringen.", suggested_assistant="a5"),
        DocSpec("serious_incident_report", "Serious-Incident-Report",
                "Art. 73 EU AI Act", "Vorfälle",
                "Meldung schwerwiegender Vorfälle.", suggested_assistant="a23"),
        DocSpec("eu_db_registrierung", "EU-Datenbank-Registrierung",
                "Art. 49 EU AI Act", "Registrierung",
                "Registrierungsunterlagen für die EU-Datenbank.", suggested_assistant="a19"),
    ],
    "cra": [
        DocSpec("technische_doku_annex_vii", "Technische Dokumentation (Annex VII)",
                "Art. 31 CRA", "Konformität",
                "Technische Dokumentation für Produkte mit digitalen Elementen."),
        DocSpec("konformitaetserklaerung", "EU-Konformitätserklärung (Annex V)",
                "Art. 28 CRA", "Konformität", "EU-Konformitätserklärung."),
        DocSpec("benutzeranleitung_annex_ii", "Benutzerinformationen/-anleitung (Annex II)",
                "Art. 13 CRA", "Betrieb", "Benutzerinformationen und Anleitung."),
        DocSpec("sbom_begleitdoc", "SBOM-Begleitdokument",
                "Annex I Teil II CRA", "Lieferkette",
                "Begleitdokument zur Software Bill of Materials."),
        DocSpec("vuln_disclosure_policy", "Coordinated Vulnerability Disclosure Policy",
                "Art. 13(8) CRA", "Schwachstellen",
                "Richtlinie zur koordinierten Offenlegung.", suggested_assistant="c8"),
        DocSpec("update_policy", "Security-Update-/Support-Policy",
                "Art. 13 CRA", "Betrieb",
                "Update- und Support-Richtlinie.", suggested_assistant="c9"),
    ],
    "nis2": [
        DocSpec("is_leitlinie", "IS-Leitlinie + Risikoanalyse-Policy",
                "Art. 21(2)a NIS2", "Governance",
                "Informationssicherheits-Leitlinie und Risikoanalyse."),
        DocSpec("incident_handling_konzept", "Incident-Handling-Konzept",
                "Art. 21(2)b NIS2", "Vorfälle",
                "Konzept zur Behandlung von Sicherheitsvorfällen."),
        DocSpec("bcm_dr_plan", "BCM-/DR-/Krisenmanagement-Plan",
                "Art. 21(2)c NIS2", "Kontinuität",
                "Business Continuity, Disaster Recovery, Krisenmanagement."),
        DocSpec("lieferketten_richtlinie", "Lieferketten-Sicherheitsrichtlinie",
                "Art. 21(2)d NIS2", "Lieferkette",
                "Sicherheit in der Lieferkette."),
        DocSpec("krypto_richtlinie", "Krypto-/Verschlüsselungsrichtlinie",
                "Art. 21(2)h NIS2", "Technik",
                "Einsatz von Kryptografie und Verschlüsselung."),
        DocSpec("zugriffskontroll_policy", "Zugriffskontroll-/Asset-Management-Policy",
                "Art. 21(2)i NIS2", "Technik",
                "Zugriffskontrolle und Asset-Management."),
        DocSpec("incident_meldung", "Incident-Meldung (24h/72h/1M)",
                "Art. 23 NIS2", "Vorfälle",
                "Meldungen an die zuständige Behörde.", suggested_assistant="n8"),
    ],
    "dsgvo": [
        DocSpec("datenschutzhinweise", "Datenschutzhinweise",
                "Art. 13/14 DSGVO", "Transparenz",
                "Informationspflichten gegenüber Betroffenen."),
        DocSpec("avv_mustervertrag", "AVV-Mustervertrag",
                "Art. 28 DSGVO", "Auftragsverarbeitung",
                "Vertrag zur Auftragsverarbeitung."),
        DocSpec("tom_dokument", "TOM-Dokument",
                "Art. 32 DSGVO", "Sicherheit",
                "Technisch-organisatorische Maßnahmen."),
        DocSpec("vvt_auszug", "VVT-Auszug",
                "Art. 30 DSGVO", "Dokumentation",
                "Auszug aus dem Verzeichnis von Verarbeitungstätigkeiten."),
        DocSpec("loeschkonzept_doc", "Löschkonzept-Dokument",
                "Art. 17 DSGVO", "Löschung",
                "Dokumentiertes Löschkonzept."),
    ],
    "wiba": [
        DocSpec("nachweis_dokument", "Nachweis-/Maßnahmendokument",
                "BSI WiBA (IT-Grundschutz)", "Nachweis",
                "Nachweis- bzw. Maßnahmendokument je WiBA-Themenblock.",
                pflicht=False),
    ],
}


def get_catalog(modul: str) -> list[dict[str, Any]]:
    return [d.to_dict() for d in DOCUMENT_CATALOG.get(modul, [])]


def get_doc_spec(modul: str, doc_type: str) -> dict[str, Any] | None:
    for d in DOCUMENT_CATALOG.get(modul, []):
        if d.doc_type == doc_type:
            return d.to_dict()
    return None
