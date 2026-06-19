"""S2 (#1151) — Rechts-Kanon der erzeugungspflichtigen Dokumente je Modul.

Single Source of Truth für die Soll-Ist-Anzeige im Register (S5) und das
Assistant-Wiring (S8–S13). Erweiterbar — neue Pflichtdokumente hier ergänzen.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class ChecklistItem:
    """Ein Pflichtinhalt (Soll) eines Dokuments (#1234).

    ``id`` ist stabil je Dokumenttyp (Persistenz-Schlüssel des Ist-Status),
    ``rechtsbezug`` nennt die konkrete Annex-/Artikelstelle, ``pflicht``
    unterscheidet Muss- von Kann-Inhalten.
    """
    id: str
    label: str
    rechtsbezug: str = ""
    pflicht: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DocSpec:
    doc_type: str
    titel: str
    rechtsgrundlage: str
    kategorie: str
    beschreibung: str = ""
    # #1253: Laienverständliche 2–3-Satz-Erklärung (was/wofür/Inhalt).
    erklaerung: str = ""
    suggested_assistant: str | None = None
    pflicht: bool = True
    # #1234: Soll-Inhalte (Konformitäts-Checkliste). Leer = kein Panel.
    checklist: tuple[ChecklistItem, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["checklist"] = [c.to_dict() for c in self.checklist]
        return d


# ── Konformitäts-Checklisten (#1234) ───────────────────────────────────────────
# Soll-Inhalte der inhaltskritischen Pflichtdokumente. Single Source of Truth.

# CRA Technische Dokumentation — Annex VII (Inhalt) i.V.m. Annex I (ess. Anf.).
_CL_CRA_TECH_DOKU = (
    ChecklistItem("beschreibung", "Allgemeine Beschreibung des Produkts mit digitalen Elementen "
                  "(Zweck, Versionen, Software/Hardware)", "Annex VII (1)"),
    ChecklistItem("design_entwicklung", "Beschreibung von Konzeption, Entwicklung und Produktion "
                  "inkl. Komponenten und Update-Mechanismen", "Annex VII (2)"),
    ChecklistItem("essentielle_anforderungen", "Bewertung der grundlegenden Cybersicherheits-"
                  "anforderungen (Annex I Teil I)", "Annex VII (3) / Annex I"),
    ChecklistItem("schwachstellenbehandlung", "Prozesse zur Schwachstellenbehandlung "
                  "(Annex I Teil II): Meldung, CVD, Sicherheitsupdates", "Annex VII (3) / Annex I Teil II"),
    ChecklistItem("risikobewertung", "Cybersicherheits-Risikobewertung des Produkts", "Annex VII (3)"),
    ChecklistItem("support_zeitraum", "Festgelegter Supportzeitraum für Sicherheitsupdates", "Art. 13(8) / Annex VII"),
    ChecklistItem("normen", "Angewandte harmonisierte Normen / Spezifikationen", "Annex VII (4)"),
    ChecklistItem("testberichte", "Berichte über durchgeführte Tests zur Verifikation der "
                  "Cybersicherheitsanforderungen", "Annex VII (4)"),
    ChecklistItem("konformitaetserklaerung_ref", "Kopie der EU-Konformitätserklärung", "Annex VII (5)"),
    ChecklistItem("sbom", "Software Bill of Materials (SBOM) der Top-Level-Abhängigkeiten",
                  "Annex I Teil II (1)", pflicht=False),
)

# CRA Benutzerinformationen/-anleitung — Annex II.
_CL_CRA_BENUTZERINFO = (
    ChecklistItem("hersteller", "Name, Handelsname und Kontaktanschrift des Herstellers", "Annex II (1)"),
    ChecklistItem("kontakt_schwachstellen", "Zentrale Anlaufstelle zur Meldung von Schwachstellen "
                  "(Single Point of Contact)", "Annex II (2)"),
    ChecklistItem("produkt_id", "Eindeutige Identifikation des Produkts (Typ/Charge/Version)", "Annex II (3)"),
    ChecklistItem("verwendungszweck", "Bestimmungsgemäße Verwendung inkl. Sicherheitsumgebung", "Annex II (4)"),
    ChecklistItem("sicherheits_features", "Cybersicherheitsrelevante Eigenschaften und Konfiguration", "Annex II (5)"),
    ChecklistItem("inbetriebnahme", "Hinweise zur sicheren Inbetriebnahme und Nutzung", "Annex II (6)"),
    ChecklistItem("update_handhabung", "Wie Sicherheitsupdates bezogen/installiert werden", "Annex II (7)"),
    ChecklistItem("ausserbetriebnahme", "Hinweise zur sicheren Außerbetriebnahme / Deinstallation "
                  "(inkl. Datenlöschung)", "Annex II (6)"),
    ChecklistItem("support_ende", "Ende des Supportzeitraums / End-of-Life-Hinweis", "Annex II (8)"),
)

# AI-Act Technische Dokumentation — Annex IV.
_CL_AIACT_TECH_DOKU = (
    ChecklistItem("systembeschreibung", "Allgemeine Beschreibung des KI-Systems (Zweck, Versionen, "
                  "Interaktion mit Hard-/Software)", "Annex IV (1)"),
    ChecklistItem("entwicklung", "Detaillierte Beschreibung der Elemente und der Entwicklung "
                  "des Systems", "Annex IV (2)"),
    ChecklistItem("ueberwachung", "Überwachung, Funktionsweise und Kontrolle des Systems", "Annex IV (3)"),
    ChecklistItem("risikomanagement", "Risikomanagementsystem (Art. 9)", "Annex IV (4) / Art. 9"),
    ChecklistItem("aenderungen", "Vorgenommene Änderungen über den Lebenszyklus", "Annex IV (5)"),
    ChecklistItem("normen", "Angewandte harmonisierte Normen / sonstige Lösungen", "Annex IV (6)"),
    ChecklistItem("konformitaetserklaerung_ref", "Kopie der EU-Konformitätserklärung", "Annex IV (7)"),
    ChecklistItem("post_market", "System zur Beobachtung nach Inverkehrbringen (Post-Market-Monitoring)",
                  "Annex IV (8) / Art. 72"),
)


DOCUMENT_CATALOG: dict[str, list[DocSpec]] = {
    "ai_act": [
        DocSpec("technische_doku_annex_iv", "Technische Dokumentation (Annex IV)",
                "Art. 11 EU AI Act", "Konformität",
                "Technische Dokumentation für Hochrisiko-KI-Systeme.",
                erklaerung="Die technische Dokumentation ist die umfassende Nachweisakte, mit der ein "
                "Anbieter belegt, dass sein Hochrisiko-KI-System alle Anforderungen des AI Act erfüllt. "
                "Art. 11 i.V.m. Annex IV verlangt sie als Voraussetzung für die Konformitätsbewertung und "
                "CE-Kennzeichnung. Hinein gehören u. a. Systembeschreibung und Zweck, Entwicklungs- und "
                "Trainingsdaten, Risikomanagement (Art. 9), Überwachungs- und Kontrollmechanismen, "
                "angewandte Normen sowie das Post-Market-Monitoring.",
                # #1245: Annex-IV-Struktur-Wizard (Reuse A16 High-Risk-DOC + Annex IV).
                suggested_assistant="high-risk-doc",
                checklist=_CL_AIACT_TECH_DOKU),
        DocSpec("konformitaetserklaerung", "EU-Konformitätserklärung (Annex V)",
                "Art. 47 EU AI Act", "Konformität",
                "EU-Konformitätserklärung.",
                erklaerung="Die EU-Konformitätserklärung ist die rechtsverbindliche Erklärung des Anbieters, "
                "dass sein Hochrisiko-KI-System die Anforderungen des AI Act einhält. Art. 47 i.V.m. Annex V "
                "macht sie zur formalen Grundlage für die CE-Kennzeichnung. Sie enthält Name/Anschrift des "
                "Anbieters, eindeutige Systembezeichnung, einen Verweis auf die angewandten Normen und "
                "Konformitätsbewertungsverfahren sowie Ort, Datum und Unterschrift.",
                suggested_assistant="a8"),
        DocSpec("transparenzhinweise", "Transparenzhinweise",
                "Art. 50 EU AI Act", "Transparenz",
                "Transparenzpflichten gegenüber Nutzern.",
                erklaerung="Transparenzhinweise informieren Menschen darüber, dass sie mit einem KI-System "
                "interagieren oder dass Inhalte KI-generiert bzw. -manipuliert sind. Art. 50 verlangt diese "
                "Offenlegung u. a. bei Chatbots, Emotionserkennung, biometrischer Kategorisierung und bei "
                "Deepfakes. Das Dokument legt fest, welche Hinweise wann, wo und in welcher Form (z. B. "
                "Kennzeichnung, maschinenlesbare Markierung) gegeben werden.",
                suggested_assistant="a9"),
        DocSpec("betriebsanleitung", "Betriebsanleitung / Instructions for Use",
                "Art. 13 EU AI Act", "Betrieb",
                "Anleitung für Betreiber.",
                erklaerung="Die Betriebsanleitung (Instructions for Use) versetzt den Betreiber in die Lage, "
                "ein Hochrisiko-KI-System sicher und vorschriftsgemäß zu nutzen. Art. 13 verlangt sie, damit "
                "die Funktionsweise des Systems hinreichend transparent und verständlich ist. Hinein gehören "
                "Zweck und Leistungsgrenzen, bekannte Risiken und Fehlerquellen, Anforderungen an die "
                "menschliche Aufsicht, Eingabedaten-Vorgaben sowie Wartungs- und Erwartungswerte zur Genauigkeit.",
                # #1245: Art-13-Instructions-for-Use-Wizard.
                suggested_assistant="betriebsanleitung"),
        DocSpec("fria", "Grundrechte-Folgenabschätzung (FRIA)",
                "Art. 27 EU AI Act", "Grundrechte",
                "Fundamental Rights Impact Assessment.",
                erklaerung="Die Grundrechte-Folgenabschätzung (FRIA) prüft vor dem Einsatz eines "
                "Hochrisiko-KI-Systems, wie es sich auf die Grundrechte betroffener Personen auswirkt. "
                "Art. 27 verpflichtet bestimmte Betreiber (u. a. öffentliche Stellen) dazu. Das Dokument "
                "beschreibt die Einsatzprozesse, die betroffenen Personengruppen, die spezifischen "
                "Grundrechtsrisiken (z. B. Diskriminierung) sowie Maßnahmen zur Risikominderung und zur "
                "menschlichen Aufsicht.",
                # #1245: FRIA-Dokument-Wizard (geführte Grundrechte-Fragen).
                suggested_assistant="fria-doc"),
        DocSpec("pmm_plan", "Post-Market-Monitoring-Plan",
                "Art. 72 EU AI Act", "Überwachung",
                "Plan zur Marktbeobachtung nach Inverkehrbringen.",
                erklaerung="Der Post-Market-Monitoring-Plan beschreibt, wie ein Anbieter sein KI-System "
                "nach dem Inverkehrbringen systematisch im realen Betrieb beobachtet. Art. 72 verlangt ihn, "
                "um Leistungseinbußen, neue Risiken oder Fehlfunktionen frühzeitig zu erkennen. Er legt fest, "
                "welche Daten erhoben und ausgewertet werden, in welchen Intervallen, wer verantwortlich ist "
                "und wie Erkenntnisse in Korrekturmaßnahmen und Meldepflichten einfließen.",
                suggested_assistant="a5"),
        DocSpec("serious_incident_report", "Serious-Incident-Report",
                "Art. 73 EU AI Act", "Vorfälle",
                "Meldung schwerwiegender Vorfälle.",
                erklaerung="Der Serious-Incident-Report ist die formale Meldung eines schwerwiegenden "
                "Vorfalls mit einem Hochrisiko-KI-System an die zuständige Marktüberwachungsbehörde. "
                "Art. 73 verpflichtet Anbieter dazu, etwa bei Tod, schweren Gesundheitsschäden, kritischen "
                "Infrastruktur-Störungen oder Grundrechtsverletzungen. Der Report enthält Beschreibung und "
                "Zeitpunkt des Vorfalls, das betroffene System, mutmaßliche Ursachen sowie ergriffene "
                "Sofort- und Korrekturmaßnahmen.",
                suggested_assistant="a23"),
        DocSpec("eu_db_registrierung", "EU-Datenbank-Registrierung",
                "Art. 49 EU AI Act", "Registrierung",
                "Registrierungsunterlagen für die EU-Datenbank.",
                erklaerung="Die EU-Datenbank-Registrierung trägt ein Hochrisiko-KI-System vor seinem "
                "Inverkehrbringen oder seiner Inbetriebnahme in die öffentliche EU-Datenbank ein. Art. 49 "
                "schafft damit Transparenz darüber, welche Hochrisiko-Systeme im EU-Markt im Einsatz sind. "
                "Die Unterlagen umfassen u. a. Angaben zum Anbieter, Systembezeichnung und Zweck, "
                "Risikoklasse, Konformitätsstatus sowie Mitgliedstaaten des Einsatzes.",
                suggested_assistant="a19"),
        # #1242: AI-Literacy-Plan (Art. 4) — Ergebnis des Ausfüll-Assistenten.
        DocSpec("ai_literacy_plan", "AI-Literacy-Plan (Art. 4)",
                "Art. 4 EU AI Act", "Kompetenz",
                "Rollenbasierter KI-Kompetenz-/Schulungsplan (gilt seit 02.02.2025, "
                "alle Risikoklassen).",
                erklaerung="Der AI-Literacy-Plan stellt sicher, dass Beschäftigte, die KI-Systeme "
                "entwickeln oder betreiben, über ausreichende KI-Kompetenz verfügen. Art. 4 verpflichtet "
                "Anbieter und Betreiber seit 02.02.2025 hierzu — unabhängig von der Risikoklasse. Der Plan "
                "ordnet je Rolle die erforderlichen Kenntnisse zu (z. B. Grenzen, Risiken, korrekte "
                "Nutzung) und legt Schulungsmaßnahmen, Zielgruppen und Nachweise fest.",
                suggested_assistant="literacy", pflicht=False),
        # #1244: GPAI-Pflichtdokumente (Art. 53) — Ergebnisse der GPAI-Assistenten.
        DocSpec("gpai_copyright_policy", "GPAI-Urheberrechts-/TDM-Policy",
                "Art. 53(1)c EU AI Act", "GPAI",
                "Urheberrechts-/TDM-Opt-out-Policy für GPAI-Modelle.",
                erklaerung="Die GPAI-Urheberrechts-/TDM-Policy dokumentiert, wie ein Anbieter von "
                "General-Purpose-AI-Modellen das Urheberrecht beim Training wahrt. Art. 53(1)c verlangt eine "
                "Strategie, die insbesondere die Opt-outs vom Text- und Data-Mining (TDM) nach der "
                "DSM-Richtlinie respektiert. Sie beschreibt, wie Rechtevorbehalte erkannt und beachtet "
                "werden, welche Datenquellen genutzt werden und welche internen Kontrollen es gibt.",
                suggested_assistant="gpai-copyright", pflicht=False),
        DocSpec("gpai_training_summary", "GPAI-Trainingsdaten-Zusammenfassung",
                "Art. 53(1)d EU AI Act", "GPAI",
                "Öffentliche Zusammenfassung der Trainingsinhalte (AI-Office-Template).",
                erklaerung="Die GPAI-Trainingsdaten-Zusammenfassung ist eine öffentlich zugängliche "
                "Übersicht über die zum Training eines General-Purpose-AI-Modells verwendeten Inhalte. "
                "Art. 53(1)d verlangt sie, um Rechteinhabern und der Öffentlichkeit ein Mindestmaß an "
                "Transparenz über die Datenbasis zu geben. Sie folgt dem Template des AI Office und nennt "
                "u. a. Art und Herkunft der Datenquellen (z. B. öffentliche Datensätze, Web-Crawls, lizenzierte Daten).",
                suggested_assistant="gpai-training-summary", pflicht=False),
    ],
    "cra": [
        DocSpec("technische_doku_annex_vii", "Technische Dokumentation (Annex VII)",
                "Art. 31 CRA", "Konformität",
                "Technische Dokumentation für Produkte mit digitalen Elementen.",
                erklaerung="Die technische Dokumentation ist die Nachweisakte, mit der ein Hersteller belegt, "
                "dass sein Produkt mit digitalen Elementen die Cybersicherheitsanforderungen des CRA erfüllt. "
                "Art. 31 i.V.m. Annex VII verlangt sie als Grundlage der Konformitätsbewertung und "
                "CE-Kennzeichnung. Hinein gehören Produktbeschreibung, Konzept und Entwicklung, Bewertung der "
                "essenziellen Anforderungen (Annex I), Prozesse zur Schwachstellenbehandlung, Risikobewertung, "
                "Supportzeitraum sowie Test- und Normennachweise.",
                suggested_assistant="version-changes",  # #1249 Änderungshistorie
                checklist=_CL_CRA_TECH_DOKU),
        DocSpec("konformitaetserklaerung", "EU-Konformitätserklärung (Annex V)",
                "Art. 28 CRA", "Konformität", "EU-Konformitätserklärung.",
                erklaerung="Die EU-Konformitätserklärung ist die rechtsverbindliche Erklärung des Herstellers, "
                "dass sein Produkt mit digitalen Elementen die Anforderungen des CRA einhält. Art. 28 i.V.m. "
                "Annex V macht sie zur formalen Voraussetzung der CE-Kennzeichnung. Sie nennt Hersteller, "
                "eindeutige Produktidentifikation, die zugrunde gelegten Normen und das "
                "Konformitätsbewertungsverfahren sowie Ausstellungsort, Datum und Unterschrift.",
                suggested_assistant="eu-doc"),
        DocSpec("benutzeranleitung_annex_ii", "Benutzerinformationen/-anleitung (Annex II)",
                "Art. 13 CRA", "Betrieb", "Benutzerinformationen und Anleitung.",
                erklaerung="Die Benutzerinformationen/-anleitung versetzen den Nutzer in die Lage, ein "
                "Produkt mit digitalen Elementen sicher in Betrieb zu nehmen, zu betreiben und außer Betrieb "
                "zu nehmen. Art. 13 i.V.m. Annex II verlangt sie als verpflichtende Begleitinformation. "
                "Hinein gehören Hersteller- und Kontaktangaben, eine Anlaufstelle für Schwachstellenmeldungen, "
                "der bestimmungsgemäße Gebrauch, sicherheitsrelevante Konfiguration, der Bezug von "
                "Sicherheitsupdates sowie das Ende des Supportzeitraums.",
                checklist=_CL_CRA_BENUTZERINFO),
        DocSpec("sbom_begleitdoc", "SBOM-Begleitdokument",
                "Annex I Teil II CRA", "Lieferkette",
                "Begleitdokument zur Software Bill of Materials.",
                erklaerung="Eine SBOM (Software Bill of Materials) ist ein maschinenlesbares Verzeichnis aller "
                "in einem Produkt enthaltenen Software-Komponenten und ihrer Abhängigkeiten samt "
                "Versionen/Lizenzen. Der CRA verlangt sie (Annex I Teil II) zur Nachverfolgung von "
                "Schwachstellen in Drittkomponenten. Das Begleitdokument beschreibt Format (z. B. "
                "CycloneDX/SPDX), Erstellungsweg, Aktualisierungsfrequenz und wo Nutzer die SBOM erhalten.",
                suggested_assistant="sbom-doc"),
        DocSpec("vuln_disclosure_policy", "Coordinated Vulnerability Disclosure Policy",
                "Art. 13(8) CRA", "Schwachstellen",
                "Richtlinie zur koordinierten Offenlegung.",
                erklaerung="Die Coordinated Vulnerability Disclosure (CVD) Policy regelt, wie Sicherheits"
                "forscher und Nutzer Schwachstellen melden können und wie der Hersteller damit umgeht. Der "
                "CRA (Art. 13(8) i.V.m. Annex I Teil II) verlangt einen solchen koordinierten Offenlegungs"
                "prozess. Die Richtlinie nennt die Meldewege und Anlaufstelle, Reaktions- und Behebungsfristen, "
                "den Umgang mit der Veröffentlichung sowie Zusagen gegenüber Meldenden (z. B. kein rechtliches Vorgehen).",
                suggested_assistant="c8"),
        DocSpec("update_policy", "Security-Update-/Support-Policy",
                "Art. 13 CRA", "Betrieb",
                "Update- und Support-Richtlinie.",
                erklaerung="Die Security-Update-/Support-Policy legt fest, wie lange und auf welche Weise ein "
                "Produkt mit Sicherheitsupdates versorgt wird. Der CRA (Art. 13) verpflichtet Hersteller, "
                "Schwachstellen über einen angemessenen Supportzeitraum kostenlos zu beheben. Die Richtlinie "
                "definiert den Supportzeitraum, Reaktionszeiten für kritische Patches, den Bereitstellungs- "
                "und Installationsweg von Updates sowie End-of-Life-Hinweise.",
                suggested_assistant="c9"),
    ],
    "nis2": [
        # #1240: Je Pflichtdokument ein Copy/Paste-Generator (Art. 21(2)).
        # Ergebnis → editier-/freigabe-/exportierbares managed_doc (#1235).
        DocSpec("is_leitlinie", "IS-Leitlinie + Risikoanalyse-Policy",
                "Art. 21(2)a NIS2", "Governance",
                "Informationssicherheits-Leitlinie und Risikoanalyse.",
                erklaerung="Die IS-Leitlinie ist das oberste Steuerungsdokument der Informationssicherheit "
                "und legt die von der Leitung verabschiedeten Grundsätze und Verantwortlichkeiten fest. "
                "Art. 21(2)a NIS2 verlangt Konzepte für Risikoanalyse und Informationssicherheit. Hinein "
                "gehören Ziele und Geltungsbereich, Rollen und Verantwortlichkeiten, der Risikomanagement-"
                "Ansatz (Methodik zur Risikoidentifikation und -bewertung) sowie verbindliche "
                "Sicherheitsvorgaben für die Organisation.",
                suggested_assistant="nis2-is-leitlinie"),
        DocSpec("incident_handling_konzept", "Incident-Handling-Konzept",
                "Art. 21(2)b NIS2", "Vorfälle",
                "Konzept zur Behandlung von Sicherheitsvorfällen.",
                erklaerung="Das Incident-Handling-Konzept beschreibt, wie die Organisation "
                "Sicherheitsvorfälle erkennt, bewertet, eindämmt und behebt. Art. 21(2)b NIS2 verlangt ein "
                "Konzept zur Behandlung von Sicherheitsvorfällen. Hinein gehören die Vorfall-Klassifizierung, "
                "Rollen und Eskalationswege, der Ablauf von der Erkennung bis zur Wiederherstellung, die "
                "Anbindung an die NIS2-Meldepflichten (24h/72h/1 Monat) sowie die Nachbereitung (Lessons Learned).",
                suggested_assistant="nis2-incident-handling-konzept"),
        DocSpec("bcm_dr_plan", "BCM-/DR-/Krisenmanagement-Plan",
                "Art. 21(2)c NIS2", "Kontinuität",
                "Business Continuity, Disaster Recovery, Krisenmanagement.",
                erklaerung="Der BCM-/DR-/Krisenmanagement-Plan stellt sicher, dass kritische Dienste auch "
                "während und nach einer Störung aufrechterhalten oder schnell wiederhergestellt werden. "
                "Art. 21(2)c NIS2 verlangt Maßnahmen für Geschäftskontinuität (inkl. Backup-Management) und "
                "Krisenmanagement. Hinein gehören Business-Impact-Analyse, Wiederanlaufziele (RTO/RPO), "
                "Backup- und Wiederherstellungsverfahren, Notfall- und Krisenorganisation sowie regelmäßige Tests.",
                suggested_assistant="nis2-bcm-dr-plan"),
        DocSpec("lieferketten_richtlinie", "Lieferketten-Sicherheitsrichtlinie",
                "Art. 21(2)d NIS2", "Lieferkette",
                "Sicherheit in der Lieferkette.",
                erklaerung="Die Lieferketten-Sicherheitsrichtlinie regelt die Sicherheit der Beziehungen zu "
                "Lieferanten und Dienstleistern. Art. 21(2)d NIS2 verlangt, Sicherheitsaspekte der "
                "Lieferkette und der Beziehungen zu unmittelbaren Anbietern zu berücksichtigen. Hinein "
                "gehören Anforderungen an die Lieferantenauswahl, vertragliche Sicherheitsvorgaben, die "
                "Bewertung von Lieferantenrisiken sowie die Behandlung von Schwachstellen und Vorfällen bei Dritten.",
                suggested_assistant="nis2-lieferketten-richtlinie"),
        DocSpec("krypto_richtlinie", "Krypto-/Verschlüsselungsrichtlinie",
                "Art. 21(2)h NIS2", "Technik",
                "Einsatz von Kryptografie und Verschlüsselung.",
                erklaerung="Die Krypto-/Verschlüsselungsrichtlinie legt fest, wie und wann Kryptografie zum "
                "Schutz von Daten eingesetzt wird. Art. 21(2)h NIS2 verlangt Konzepte und Verfahren für den "
                "Einsatz von Kryptografie und, wo angemessen, Verschlüsselung. Hinein gehören zugelassene "
                "Algorithmen und Schlüssellängen, Vorgaben zur Verschlüsselung von Daten bei der Übertragung "
                "und Speicherung sowie das Schlüsselmanagement (Erzeugung, Aufbewahrung, Rotation, Vernichtung).",
                suggested_assistant="nis2-krypto-richtlinie"),
        DocSpec("zugriffskontroll_policy", "Zugriffskontroll-/Asset-Management-Policy",
                "Art. 21(2)i NIS2", "Technik",
                "Zugriffskontrolle und Asset-Management.",
                erklaerung="Die Zugriffskontroll-/Asset-Management-Policy regelt, wer auf welche Systeme und "
                "Daten zugreifen darf und wie die Werte (Assets) der Organisation verwaltet werden. "
                "Art. 21(2)i NIS2 verlangt Konzepte für Zugriffskontrolle und Anlagenverwaltung. Hinein "
                "gehören ein Asset-Inventar, die Rollen-/Rechtevergabe nach dem Need-to-know- und "
                "Least-Privilege-Prinzip, Berechtigungsüberprüfungen sowie Vorgaben für privilegierte Zugänge.",
                suggested_assistant="nis2-zugriffskontroll-policy"),
        DocSpec("incident_meldung", "Incident-Meldung (24h/72h/1M)",
                "Art. 23 NIS2", "Vorfälle",
                "Meldungen an die zuständige Behörde.",
                erklaerung="Die Incident-Meldung ist die gesetzlich vorgeschriebene Benachrichtigung der "
                "zuständigen Behörde bzw. des CSIRT über einen erheblichen Sicherheitsvorfall. Art. 23 NIS2 "
                "schreibt ein mehrstufiges Verfahren vor: Frühwarnung binnen 24 Stunden, Vorfallmeldung "
                "binnen 72 Stunden und Abschlussbericht binnen eines Monats. Die Meldung enthält Art und "
                "Schwere des Vorfalls, betroffene Dienste, mutmaßliche Ursachen sowie ergriffene Gegen- und "
                "Abhilfemaßnahmen.",
                suggested_assistant="n8"),
    ],
    "dsgvo": [
        DocSpec("datenschutzhinweise", "Datenschutzhinweise",
                "Art. 13/14 DSGVO", "Transparenz",
                "Informationspflichten gegenüber Betroffenen.",
                erklaerung="Datenschutzhinweise informieren betroffene Personen darüber, wie ihre "
                "personenbezogenen Daten verarbeitet werden. Art. 13 und 14 DSGVO verpflichten den "
                "Verantwortlichen, diese Informationen transparent und verständlich bereitzustellen (z. B. "
                "als Datenschutzerklärung). Hinein gehören Identität des Verantwortlichen und ggf. des DSB, "
                "Zwecke und Rechtsgrundlagen der Verarbeitung, Empfänger, Speicherdauer, Drittlandtransfers "
                "sowie die Rechte der Betroffenen."),
        DocSpec("avv_mustervertrag", "AVV-Mustervertrag",
                "Art. 28 DSGVO", "Auftragsverarbeitung",
                "Vertrag zur Auftragsverarbeitung.",
                erklaerung="Der AVV-Mustervertrag (Auftragsverarbeitungsvertrag) regelt die "
                "Datenschutzpflichten, wenn ein Dienstleister personenbezogene Daten im Auftrag eines "
                "Verantwortlichen verarbeitet. Art. 28 DSGVO schreibt einen solchen Vertrag verpflichtend "
                "vor. Hinein gehören Gegenstand, Dauer, Art und Zweck der Verarbeitung, Kategorien "
                "betroffener Personen und Daten, Weisungsbindung, technisch-organisatorische Maßnahmen, der "
                "Einsatz von Sub-Auftragsverarbeitern sowie Kontroll- und Löschpflichten."),
        DocSpec("tom_dokument", "TOM-Dokument",
                "Art. 32 DSGVO", "Sicherheit",
                "Technisch-organisatorische Maßnahmen.",
                erklaerung="Das TOM-Dokument beschreibt die technischen und organisatorischen Maßnahmen, mit "
                "denen personenbezogene Daten geschützt werden. Art. 32 DSGVO verlangt ein dem Risiko "
                "angemessenes Schutzniveau und dessen Nachweis. Hinein gehören u. a. Zugangs-, Zutritts- und "
                "Zugriffskontrolle, Verschlüsselung und Pseudonymisierung, Verfügbarkeit und "
                "Belastbarkeit der Systeme sowie Verfahren zur regelmäßigen Überprüfung der Wirksamkeit."),
        DocSpec("vvt_auszug", "VVT-Auszug",
                "Art. 30 DSGVO", "Dokumentation",
                "Auszug aus dem Verzeichnis von Verarbeitungstätigkeiten.",
                erklaerung="Der VVT-Auszug ist ein Ausschnitt aus dem Verzeichnis von "
                "Verarbeitungstätigkeiten, das jeder Verantwortliche führen muss. Art. 30 DSGVO verlangt eine "
                "vollständige Übersicht aller Verarbeitungen personenbezogener Daten als zentralen "
                "Rechenschafts-Nachweis. Je Verarbeitung gehören hinein: Zwecke, Kategorien betroffener "
                "Personen und Daten, Empfänger, Drittlandtransfers, vorgesehene Löschfristen sowie die "
                "ergriffenen technisch-organisatorischen Maßnahmen."),
        DocSpec("loeschkonzept_doc", "Löschkonzept-Dokument",
                "Art. 17 DSGVO", "Löschung",
                "Dokumentiertes Löschkonzept.",
                erklaerung="Das Löschkonzept-Dokument legt fest, wann und wie personenbezogene Daten "
                "gelöscht werden, sobald der Zweck entfällt. Es setzt das Recht auf Löschung (Art. 17 DSGVO) "
                "sowie den Grundsatz der Speicherbegrenzung systematisch um, häufig methodisch nach "
                "DIN 66398. Hinein gehören Lösch- bzw. Aufbewahrungsfristen je Datenart, die auslösenden "
                "Ereignisse, Verantwortlichkeiten, Löschverfahren sowie die Dokumentation der durchgeführten Löschungen."),
    ],
    "wiba": [
        DocSpec("nachweis_dokument", "Nachweis-/Maßnahmendokument",
                "BSI WiBA (IT-Grundschutz)", "Nachweis",
                "Nachweis- bzw. Maßnahmendokument je WiBA-Themenblock.",
                erklaerung="Das Nachweis-/Maßnahmendokument belegt je WiBA-Themenblock, dass die BSI-"
                "Prüffragen des „Wegs in die Basis-Absicherung\" erfüllt sind. Es dient kleinen und "
                "mittleren Organisationen als Nachweis eines grundlegend sicheren IT-Betriebs (IT-Grundschutz, "
                "auch mit Blick auf Datenschutz). Hinein gehören die umgesetzten Maßnahmen je Prüffrage, "
                "Verweise auf vorhandene Nachweise (z. B. Konfigurationen, Richtlinien), Verantwortliche "
                "sowie offene Punkte und geplante Verbesserungen.",
                pflicht=False),
    ],
}


# ── Querverweis-Bausteine (#1236) ───────────────────────────────────────────────
# Hinweis auf bereits vorhandene Module-Daten, die ein Dokument als Bestandteil
# einbeziehen kann (keine Datendopplung — nur Verlinkung/Hinweis). Keyed je
# (modul, doc_type).
_BAUSTEINE: dict[tuple[str, str], tuple[dict[str, str], ...]] = {
    ("cra", "technische_doku_annex_vii"): (
        {"label": "C1 — SBOM-Verzeichnis", "ziel": "sbom",
         "hinweis": "Vorhandene SBOM-Stände als Annex-VII/Annex-I-Teil-II-Baustein einbinden."},
        {"label": "C5 — Threat-Model", "ziel": "threatmodel",
         "hinweis": "Bestehendes Bedrohungsmodell als Teil der Risikobewertung referenzieren."},
    ),
}


def get_bausteine(modul: str, doc_type: str) -> list[dict[str, str]]:
    """Querverweis-Bausteine eines Dokumenttyps (#1236). Leer = kein Hinweis."""
    return [dict(b) for b in _BAUSTEINE.get((modul, doc_type), ())]


def get_catalog(modul: str) -> list[dict[str, Any]]:
    return [d.to_dict() for d in DOCUMENT_CATALOG.get(modul, [])]


def get_doc_spec(modul: str, doc_type: str) -> dict[str, Any] | None:
    for d in DOCUMENT_CATALOG.get(modul, []):
        if d.doc_type == doc_type:
            return d.to_dict()
    return None


def get_checklist(modul: str, doc_type: str) -> list[dict[str, Any]]:
    """Soll-Inhalte (Konformitäts-Checkliste) eines Dokumenttyps (#1234).

    Leere Liste, wenn keine Checkliste gepflegt ist (Panel wird dann nicht
    angezeigt — kein Fehler).
    """
    for d in DOCUMENT_CATALOG.get(modul, []):
        if d.doc_type == doc_type:
            return [c.to_dict() for c in d.checklist]
    return []
