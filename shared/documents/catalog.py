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
    # #1954 — englische Fassung, additiv und **hinten**: Ein Feld zwischen den
    # vorhandenen würde jedes Positionsargument verschieben, und die Aufrufer
    # legen die Punkte positionsweise an (``ChecklistItem("id", "label", …)``).
    #
    # ``id`` bekommt **nie** eine Sprachfassung: Sie ist der Schlüssel des
    # Ist-Status (``checklist_status_updates``) — eine übersetzte Kennung
    # verwaist jeden gesetzten Haken. ``pflicht`` ist eine Rechtsaussage und
    # keine Sprache.
    label_en: str = ""
    #: Fundstelle in englischer Fassung. **Leer, wo die deutsche schon
    #: englisch ist** (``Annex II (1)``) — ein zweites Feld mit demselben
    #: Inhalt ist nur Pflegeaufwand und läuft beim nächsten Mal auseinander.
    rechtsbezug_en: str = ""

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
    # #1954 — englische Fassung, additiv und **hinten** (Positionsargumente).
    #
    # Ohne Sprachfassung bleiben bewusst: ``doc_type`` (Schlüssel in
    # ``<modul>_managed_docs`` — ein übersetzter Schlüssel verwaist jedes
    # gespeicherte Dokument), ``suggested_assistant`` (zeigt auf die
    # Assistenten-Registry) und ``pflicht`` (Rechtsaussage, keine Sprache).
    titel_en: str = ""
    beschreibung_en: str = ""
    erklaerung_en: str = ""
    #: Gruppierungs-**Überschrift**, kein Schlüssel: Gegen ``kategorie`` wird
    #: nirgends verglichen und nach ihr nirgends gruppiert (geprüft über den
    #: ganzen Baum). Wäre sie ein Schlüssel, zerlegte eine übersetzte Fassung
    #: die Liste in zwei Gruppen — dann gehörte hier nichts hin.
    kategorie_en: str = ""
    #: Fundstelle in englischer Fassung. **Leer, wo die deutsche schon
    #: englisch ist** (``Art. 11 EU AI Act``, ``Art. 31 CRA``) — gesetzt nur
    #: dort, wo sie deutsche Wörter trägt (``DSGVO`` → ``GDPR``,
    #: ``Anhang I Teil II`` → ``Annex I Part II``). Die **Ziffern bleiben
    #: unverändert**; eine verschobene Nummer sieht im Nachweis aus wie eine
    #: Feststellung (#1763/#1792).
    rechtsgrundlage_en: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["checklist"] = [c.to_dict() for c in self.checklist]
        return d


# ── Konformitäts-Checklisten (#1234) ───────────────────────────────────────────
# Soll-Inhalte der inhaltskritischen Pflichtdokumente. Single Source of Truth.

# CRA Technische Dokumentation — Annex VII (Inhalt) i.V.m. Annex I (ess. Anf.).
# #1763: Eine Quelle für den Inhalt der technischen Dokumentation. Die Liste
# stand hier und — anders — in `cra/traceability_db.py`; zwei
# Vollständigkeitsquoten für dasselbe Dokument. Jetzt leitet sich beides aus
# `cra/annex_vii.py` ab.
#
# Der Import ist bewusst gekapselt: `shared/` liegt unter den Modulen, und eine
# Installation ohne CRA-Paket darf daran nicht scheitern (Muster:
# `shared/templates/schema.py`). Fällt er aus, bleibt die Checkliste leer statt
# falsch — ein fehlender Soll-Punkt ist sichtbar, ein veralteter nicht.
#
# #1954 — englische Fassung dieser elf Punkte: Der **deutsche** Text gehört
# `cra/annex_vii.py` (eine Quelle, #1763), also steht er hier nicht. Die
# englische Fassung liegt übergangsweise hier, weil `annex_vii.py` noch keine
# trägt und `shared/` der Ort ist, an dem sie gebraucht wird.
#
# Die Brücke **überschreibt nie**: Trägt ein Punkt eines Tages sein eigenes
# ``label_en`` (richtiger Ort — dort steht der deutsche Text), gilt dieses, und
# die Brücke lässt sich ohne Verhaltensänderung löschen. Fehlt ein Schlüssel,
# bleibt ``label_en`` leer und fällt auf — eine Positivliste, die nicht
# mitwächst, ist die Fehlerklasse aus #1871/#1879.
_EN_CRA_ANNEX_VII: dict[str, tuple[str, str]] = {
    "beschreibung": (
        "General description of the product with digital elements "
        "(purpose, versions, software/hardware)", "Annex VII No. 1"),
    "design_entwicklung": (
        "Description of the design, development and production including "
        "components and update mechanisms", "Annex VII No. 2(a)"),
    "essentielle_anforderungen": (
        "Assessment of the essential cybersecurity requirements "
        "(Annex I Part I)", "Annex VII No. 3; Annex I Part I"),
    "schwachstellenbehandlung": (
        "Vulnerability handling processes (Annex I Part II): reporting, "
        "coordinated disclosure, security updates", "Annex VII No. 2(b)"),
    "risikobewertung": ("Cybersecurity risk assessment of the product",
                        "Annex VII No. 3"),
    "support_zeitraum": ("Support period determined for security updates",
                         "Annex VII No. 4; Art. 13(8)"),
    "normen": ("Harmonised standards or specifications applied",
               "Annex VII No. 5"),
    "testberichte": (
        "Reports of the tests carried out to verify the cybersecurity "
        "requirements", "Annex VII No. 6"),
    "konformitaetserklaerung_ref": ("Copy of the EU declaration of conformity",
                                    "Annex VII No. 7"),
    "sbom": ("Software bill of materials (SBOM) of the top-level dependencies",
             "Annex VII No. 8; Annex I Part II No. 1"),
    "anleitung": (
        "Information and instructions to the user pursuant to Annex II — "
        "included or referenced", "Annex VII No. 1(d); Annex II"),
}


def _mit_en(punkte: tuple[ChecklistItem, ...]) -> tuple[ChecklistItem, ...]:
    """Die englische Fassung aus :data:`_EN_CRA_ANNEX_VII` nachtragen."""
    from dataclasses import replace
    out = []
    for p in punkte:
        en = _EN_CRA_ANNEX_VII.get(p.id)
        if en and not p.label_en:
            p = replace(p, label_en=en[0],
                        rechtsbezug_en=p.rechtsbezug_en or en[1])
        out.append(p)
    return tuple(out)


try:                                  # pragma: no cover - Verdrahtung
    from cra.annex_vii import checkliste as _cra_annex_vii_checkliste
    _CL_CRA_TECH_DOKU = _mit_en(tuple(_cra_annex_vii_checkliste()))
except Exception:                     # noqa: BLE001
    _CL_CRA_TECH_DOKU = ()

# CRA Benutzerinformationen/-anleitung — Annex II.
#
# #1954: ``rechtsbezug_en`` bleibt hier durchweg leer — ``Annex II (1)`` ist
# schon englisch.
#
# Fundstellen gegen das Amtsblatt geprüft (32024R2847, S. 70). Fünf waren
# falsch — die Nummerierung des Anhangs II war um eine Stelle verrutscht und
# die Unternummern von Nr. 8 fehlten ganz:
#   Nr. 4 nennt die Zweckbestimmung *und* „Informationen über die
#   Sicherheitseigenschaften“ (nicht Nr. 5) · Nr. 6 ist die Internetadresse
#   der EU-Konformitätserklärung und trifft weder Inbetriebnahme noch
#   Außerbetriebnahme — die stehen in Nr. 8 Buchst. a bzw. d · Nr. 7 ist das
#   Enddatum des Unterstützungszeitraums (nicht Nr. 8) · die Installation von
#   Sicherheitsaktualisierungen ist Nr. 8 Buchst. c.
# **Mit #1957 ergänzt** (05.11.2026), nachdem die Wortlaute entschieden waren:
# Nr. 5 (``vorhersehbare_risiken``), Nr. 9 (``sbom_zugang``) und die zweite
# Hälfte von Nr. 2 im Label von ``kontakt_schwachstellen``. Damit führt die
# Liste alle neun Nummern des Anhangs II.
#
# ``sbom_zugang`` ist der einzige Punkt hier mit ``pflicht=False``, und das ist
# der Rechtstext: Nr. 9 gilt „für den Fall, dass der Hersteller dem Nutzer die
# Software-Stückliste zur Verfügung stellt“. Als Mussfeld stünde in jeder Akte
# eine Pflicht, die für viele Produkte nicht besteht — dieselbe Erfindung wie
# eine falsche Nummer, nur in die andere Richtung.
_CL_CRA_BENUTZERINFO = (
    ChecklistItem("hersteller", "Name, Handelsname und Kontaktanschrift des Herstellers", "Annex II (1)",
                  label_en="Name, trade name and contact address of the manufacturer"),
    # Nr. 2 hat **zwei** Bestandteile, nicht zwei Nummern (#1957): die
    # Anlaufstelle *und* wo das Konzept für die koordinierte Offenlegung zu
    # finden ist. Deshalb ein geweitetes Label und kein zweiter Punkt.
    ChecklistItem("kontakt_schwachstellen", "Zentrale Anlaufstelle zur Meldung von Schwachstellen "
                  "(Single Point of Contact) und Fundort des Konzepts für die koordinierte "
                  "Offenlegung von Schwachstellen", "Annex II (2)",
                  label_en="Single point of contact for reporting vulnerabilities and where the "
                           "coordinated vulnerability disclosure policy can be found"),
    ChecklistItem("produkt_id", "Eindeutige Identifikation des Produkts (Typ/Charge/Version)", "Annex II (3)",
                  label_en="Unambiguous identification of the product (type/batch/version)"),
    ChecklistItem("verwendungszweck", "Bestimmungsgemäße Verwendung inkl. Sicherheitsumgebung", "Annex II (4)",
                  label_en="Intended purpose including the security environment"),
    ChecklistItem("vorhersehbare_risiken", "Bekannte oder vorhersehbare Umstände — auch "
                  "vernünftigerweise vorhersehbare Fehlanwendung —, die zu erheblichen "
                  "Cybersicherheitsrisiken führen können", "Annex II (5)",
                  label_en="Known or foreseeable circumstances, including reasonably foreseeable "
                           "misuse, that may lead to significant cybersecurity risks"),
    ChecklistItem("sicherheits_features", "Cybersicherheitsrelevante Eigenschaften und Konfiguration",
                  "Annex II (4), (8)(a), (8)(e)",
                  label_en="Cybersecurity-relevant properties and configuration"),
    ChecklistItem("inbetriebnahme", "Hinweise zur sicheren Inbetriebnahme und Nutzung", "Annex II (8)(a)",
                  label_en="Guidance on secure commissioning and use"),
    ChecklistItem("update_handhabung", "Wie Sicherheitsupdates bezogen/installiert werden", "Annex II (8)(c)",
                  label_en="How security updates are obtained and installed"),
    ChecklistItem("ausserbetriebnahme", "Hinweise zur sicheren Außerbetriebnahme / Deinstallation "
                  "(inkl. Datenlöschung)", "Annex II (8)(d)",
                  label_en="Guidance on secure decommissioning / uninstallation "
                           "(including erasure of data)"),
    ChecklistItem("support_ende", "Ende des Supportzeitraums / End-of-Life-Hinweis", "Annex II (7)",
                  label_en="End of the support period / end-of-life notice"),
    ChecklistItem("sbom_zugang", "Falls dem Nutzer eine Software-Stückliste bereitgestellt wird: "
                  "wo darauf zugegriffen werden kann", "Annex II (9)", pflicht=False,
                  label_en="Where the software bill of materials can be accessed, if the "
                           "manufacturer makes it available to the user"),
)

# AI-Act Technische Dokumentation — Annex IV.
#
# #1954: ``rechtsbezug_en`` bleibt hier durchweg leer — ``Annex IV (1)`` bzw.
# ``Annex IV (9) / Art. 72`` sind schon englisch.
#
# Fundstellen gegen das Amtsblatt geprüft (32024R1689, S. 130 f.). Anhang IV
# hat **neun** Nummern; Nr. 4 („Darlegungen zur Eignung der Leistungskennzahlen
# für das spezifische KI-System“) trug hier keinen Punkt, und deshalb waren
# alle fünf Fundstellen dahinter um eins zu klein: Risikomanagement ist Nr. 5,
# Änderungen Nr. 6, Normen Nr. 7, die Kopie der EU-Konformitätserklärung Nr. 8,
# die Beobachtung nach dem Inverkehrbringen Nr. 9.
#
# **Nr. 4 ist mit #1957 angelegt** (``kennzahlen_eignung``, 05.11.2026), damit
# die Liste alle neun Nummern führt. Sie fragt etwas anderes als Nr. 3: nicht
# *wie genau* das System ist, sondern ob die gewählten **Kennzahlen** für
# dieses System geeignet sind. Ihr Fehlen war die Ursache der fünf
# verschobenen Nummern — eine Liste, die acht von neun führt, sieht
# vollständig aus.
_CL_AIACT_TECH_DOKU = (
    ChecklistItem("systembeschreibung", "Allgemeine Beschreibung des KI-Systems (Zweck, Versionen, "
                  "Interaktion mit Hard-/Software)", "Annex IV (1)",
                  label_en="General description of the AI system (purpose, versions, "
                           "interaction with hardware and software)"),
    ChecklistItem("entwicklung", "Detaillierte Beschreibung der Elemente und der Entwicklung "
                  "des Systems", "Annex IV (2)",
                  label_en="Detailed description of the elements of the system and of its development"),
    ChecklistItem("ueberwachung", "Überwachung, Funktionsweise und Kontrolle des Systems", "Annex IV (3)",
                  label_en="Monitoring, functioning and control of the system"),
    ChecklistItem("kennzahlen_eignung", "Darlegung, warum die gewählten Leistungskennzahlen für "
                  "dieses KI-System geeignet sind", "Annex IV (4)",
                  label_en="Explanation of the appropriateness of the performance metrics for "
                           "this specific AI system"),
    ChecklistItem("risikomanagement", "Risikomanagementsystem (Art. 9)", "Annex IV (5) / Art. 9",
                  label_en="Risk management system (Art. 9)"),
    ChecklistItem("aenderungen", "Vorgenommene Änderungen über den Lebenszyklus", "Annex IV (6)",
                  label_en="Changes made over the lifecycle"),
    ChecklistItem("normen", "Angewandte harmonisierte Normen / sonstige Lösungen", "Annex IV (7)",
                  label_en="Harmonised standards applied / other solutions"),
    ChecklistItem("konformitaetserklaerung_ref", "Kopie der EU-Konformitätserklärung", "Annex IV (8)",
                  label_en="Copy of the EU declaration of conformity"),
    ChecklistItem("post_market", "System zur Beobachtung nach Inverkehrbringen (Post-Market-Monitoring)",
                  "Annex IV (9) / Art. 72",
                  label_en="System for post-market monitoring"),
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
                checklist=_CL_AIACT_TECH_DOKU,
                titel_en="Technical documentation (Annex IV)",
                beschreibung_en="Technical documentation for high-risk AI systems.",
                erklaerung_en="The technical documentation is the comprehensive evidence file with which "
                "a provider demonstrates that its high-risk AI system meets all requirements of the AI Act. "
                "Art. 11 read together with Annex IV requires it as a precondition for the conformity "
                "assessment and the CE marking. It covers, among other things, the system description and "
                "intended purpose, development and training data, risk management (Art. 9), oversight and "
                "control mechanisms, the standards applied as well as post-market monitoring.",
                kategorie_en="Conformity"),
        DocSpec("konformitaetserklaerung", "EU-Konformitätserklärung (Annex V)",
                "Art. 47 EU AI Act", "Konformität",
                "EU-Konformitätserklärung.",
                erklaerung="Die EU-Konformitätserklärung ist die rechtsverbindliche Erklärung des Anbieters, "
                "dass sein Hochrisiko-KI-System die Anforderungen des AI Act einhält. Art. 47 i.V.m. Annex V "
                "macht sie zur formalen Grundlage für die CE-Kennzeichnung. Sie enthält Name/Anschrift des "
                "Anbieters, eindeutige Systembezeichnung, einen Verweis auf die angewandten Normen und "
                "Konformitätsbewertungsverfahren sowie Ort, Datum und Unterschrift.",
                suggested_assistant="a8",
                titel_en="EU declaration of conformity (Annex V)",
                beschreibung_en="EU declaration of conformity.",
                erklaerung_en="The EU declaration of conformity is the provider's legally binding "
                "declaration that its high-risk AI system complies with the requirements of the AI Act. "
                "Art. 47 read together with Annex V makes it the formal basis for the CE marking. It states "
                "the name and address of the provider, the unambiguous designation of the system, a "
                "reference to the standards applied and to the conformity assessment procedure as well as "
                "the place, date and signature.",
                kategorie_en="Conformity"),
        DocSpec("transparenzhinweise", "Transparenzhinweise",
                "Art. 50 EU AI Act", "Transparenz",
                "Transparenzpflichten gegenüber Nutzern.",
                erklaerung="Transparenzhinweise informieren Menschen darüber, dass sie mit einem KI-System "
                "interagieren oder dass Inhalte KI-generiert bzw. -manipuliert sind. Art. 50 verlangt diese "
                "Offenlegung u. a. bei Chatbots, Emotionserkennung, biometrischer Kategorisierung und bei "
                "Deepfakes. Das Dokument legt fest, welche Hinweise wann, wo und in welcher Form (z. B. "
                "Kennzeichnung, maschinenlesbare Markierung) gegeben werden.",
                suggested_assistant="a9",
                titel_en="Transparency notices",
                beschreibung_en="Transparency obligations towards users.",
                erklaerung_en="Transparency notices inform people that they are interacting with an AI "
                "system or that content has been generated or manipulated by AI. Art. 50 requires this "
                "disclosure for, among other things, chatbots, emotion recognition, biometric "
                "categorisation and deep fakes. The document sets out which notices are given when, where "
                "and in what form (for example labelling or machine-readable marking).",
                kategorie_en="Transparency"),
        DocSpec("betriebsanleitung", "Betriebsanleitung / Instructions for Use",
                "Art. 13 EU AI Act", "Betrieb",
                "Anleitung für Betreiber.",
                erklaerung="Die Betriebsanleitung (Instructions for Use) versetzt den Betreiber in die Lage, "
                "ein Hochrisiko-KI-System sicher und vorschriftsgemäß zu nutzen. Art. 13 verlangt sie, damit "
                "die Funktionsweise des Systems hinreichend transparent und verständlich ist. Hinein gehören "
                "Zweck und Leistungsgrenzen, bekannte Risiken und Fehlerquellen, Anforderungen an die "
                "menschliche Aufsicht, Eingabedaten-Vorgaben sowie Wartungs- und Erwartungswerte zur Genauigkeit.",
                # #1245: Art-13-Instructions-for-Use-Wizard.
                suggested_assistant="betriebsanleitung",
                titel_en="Instructions for use",
                beschreibung_en="Instructions for the deployer.",
                erklaerung_en="The instructions for use enable the deployer to operate a high-risk AI "
                "system safely and in accordance with the rules. Art. 13 requires them so that the way the "
                "system works is sufficiently transparent and comprehensible. They cover the intended "
                "purpose and the limits of performance, known risks and sources of error, the requirements "
                "for human oversight, the specifications for input data as well as maintenance and the "
                "expected level of accuracy.",
                kategorie_en="Operation"),
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
                suggested_assistant="fria-doc",
                titel_en="Fundamental rights impact assessment (FRIA)",
                beschreibung_en="Fundamental rights impact assessment.",
                erklaerung_en="The fundamental rights impact assessment (FRIA) examines, before a "
                "high-risk AI system is put into use, how it affects the fundamental rights of the persons "
                "concerned. Art. 27 obliges certain deployers (public bodies among them) to carry it out. "
                "The document describes the processes of use, the groups of persons affected, the specific "
                "fundamental rights risks (for example discrimination) as well as measures for risk "
                "mitigation and for human oversight.",
                kategorie_en="Fundamental rights"),
        DocSpec("pmm_plan", "Post-Market-Monitoring-Plan",
                "Art. 72 EU AI Act", "Überwachung",
                "Plan zur Marktbeobachtung nach Inverkehrbringen.",
                erklaerung="Der Post-Market-Monitoring-Plan beschreibt, wie ein Anbieter sein KI-System "
                "nach dem Inverkehrbringen systematisch im realen Betrieb beobachtet. Art. 72 verlangt ihn, "
                "um Leistungseinbußen, neue Risiken oder Fehlfunktionen frühzeitig zu erkennen. Er legt fest, "
                "welche Daten erhoben und ausgewertet werden, in welchen Intervallen, wer verantwortlich ist "
                "und wie Erkenntnisse in Korrekturmaßnahmen und Meldepflichten einfließen.",
                suggested_assistant="a5",
                titel_en="Post-market monitoring plan",
                beschreibung_en="Plan for market monitoring after placing on the market.",
                erklaerung_en="The post-market monitoring plan describes how a provider systematically "
                "monitors its AI system in real operation after placing it on the market. Art. 72 requires "
                "it so that losses of performance, new risks or malfunctions are detected early. It sets "
                "out which data is collected and evaluated, at what intervals, who is responsible and how "
                "findings feed into corrective measures and reporting obligations.",
                kategorie_en="Monitoring"),
        DocSpec("serious_incident_report", "Serious-Incident-Report",
                "Art. 73 EU AI Act", "Vorfälle",
                "Meldung schwerwiegender Vorfälle.",
                erklaerung="Der Serious-Incident-Report ist die formale Meldung eines schwerwiegenden "
                "Vorfalls mit einem Hochrisiko-KI-System an die zuständige Marktüberwachungsbehörde. "
                "Art. 73 verpflichtet Anbieter dazu, etwa bei Tod, schweren Gesundheitsschäden, kritischen "
                "Infrastruktur-Störungen oder Grundrechtsverletzungen. Der Report enthält Beschreibung und "
                "Zeitpunkt des Vorfalls, das betroffene System, mutmaßliche Ursachen sowie ergriffene "
                "Sofort- und Korrekturmaßnahmen.",
                suggested_assistant="a23",
                titel_en="Serious incident report",
                beschreibung_en="Report of serious incidents.",
                erklaerung_en="The serious incident report is the formal notification of a serious "
                "incident involving a high-risk AI system to the competent market surveillance authority. "
                "Art. 73 obliges providers to submit it, for example in the event of death, serious damage "
                "to health, disruption of critical infrastructure or infringements of fundamental rights. "
                "The report contains a description of the incident and when it occurred, the system "
                "affected, the suspected causes as well as the immediate and corrective measures taken.",
                kategorie_en="Incidents"),
        DocSpec("eu_db_registrierung", "EU-Datenbank-Registrierung",
                "Art. 49 EU AI Act", "Registrierung",
                "Registrierungsunterlagen für die EU-Datenbank.",
                erklaerung="Die EU-Datenbank-Registrierung trägt ein Hochrisiko-KI-System vor seinem "
                "Inverkehrbringen oder seiner Inbetriebnahme in die öffentliche EU-Datenbank ein. Art. 49 "
                "schafft damit Transparenz darüber, welche Hochrisiko-Systeme im EU-Markt im Einsatz sind. "
                "Die Unterlagen umfassen u. a. Angaben zum Anbieter, Systembezeichnung und Zweck, "
                "Risikoklasse, Konformitätsstatus sowie Mitgliedstaaten des Einsatzes.",
                suggested_assistant="a19",
                titel_en="EU database registration",
                beschreibung_en="Registration documents for the EU database.",
                erklaerung_en="The EU database registration enters a high-risk AI system into the public "
                "EU database before it is placed on the market or put into service. Art. 49 thereby "
                "creates transparency about which high-risk systems are in use on the EU market. The "
                "documents cover, among other things, details of the provider, the designation and "
                "intended purpose of the system, the risk class, the conformity status as well as the "
                "Member States in which it is used.",
                kategorie_en="Registration"),
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
                suggested_assistant="literacy", pflicht=False,
                titel_en="AI literacy plan (Art. 4)",
                beschreibung_en="Role-based AI literacy and training plan (applicable since "
                "2 February 2025, all risk classes).",
                erklaerung_en="The AI literacy plan ensures that staff who develop or operate AI systems "
                "have a sufficient level of AI literacy. Art. 4 has obliged providers and deployers to do "
                "so since 2 February 2025 — irrespective of the risk class. The plan assigns the "
                "necessary knowledge to each role (for example limitations, risks, correct use) and "
                "defines training measures, target groups and records.",
                kategorie_en="Literacy"),
        # #1244: GPAI-Pflichtdokumente (Art. 53) — Ergebnisse der GPAI-Assistenten.
        DocSpec("gpai_copyright_policy", "GPAI-Urheberrechts-/TDM-Policy",
                "Art. 53(1)c EU AI Act", "GPAI",
                "Urheberrechts-/TDM-Opt-out-Policy für GPAI-Modelle.",
                erklaerung="Die GPAI-Urheberrechts-/TDM-Policy dokumentiert, wie ein Anbieter von "
                "General-Purpose-AI-Modellen das Urheberrecht beim Training wahrt. Art. 53(1)c verlangt eine "
                "Strategie, die insbesondere die Opt-outs vom Text- und Data-Mining (TDM) nach der "
                "DSM-Richtlinie respektiert. Sie beschreibt, wie Rechtevorbehalte erkannt und beachtet "
                "werden, welche Datenquellen genutzt werden und welche internen Kontrollen es gibt.",
                suggested_assistant="gpai-copyright", pflicht=False,
                titel_en="GPAI copyright / TDM policy",
                beschreibung_en="Copyright and TDM opt-out policy for GPAI models.",
                erklaerung_en="The GPAI copyright / TDM policy documents how a provider of "
                "general-purpose AI models respects copyright when training. Art. 53(1)(c) requires a "
                "policy that in particular respects the opt-outs from text and data mining (TDM) under "
                "the DSM Directive. It describes how reservations of rights are identified and observed, "
                "which data sources are used and which internal controls exist.",
                kategorie_en="GPAI"),
        DocSpec("gpai_training_summary", "GPAI-Trainingsdaten-Zusammenfassung",
                "Art. 53(1)d EU AI Act", "GPAI",
                "Öffentliche Zusammenfassung der Trainingsinhalte (AI-Office-Template).",
                erklaerung="Die GPAI-Trainingsdaten-Zusammenfassung ist eine öffentlich zugängliche "
                "Übersicht über die zum Training eines General-Purpose-AI-Modells verwendeten Inhalte. "
                "Art. 53(1)d verlangt sie, um Rechteinhabern und der Öffentlichkeit ein Mindestmaß an "
                "Transparenz über die Datenbasis zu geben. Sie folgt dem Template des AI Office und nennt "
                "u. a. Art und Herkunft der Datenquellen (z. B. öffentliche Datensätze, Web-Crawls, lizenzierte Daten).",
                suggested_assistant="gpai-training-summary", pflicht=False,
                titel_en="GPAI training data summary",
                beschreibung_en="Public summary of the training content (AI Office template).",
                erklaerung_en="The GPAI training data summary is a publicly available overview of the "
                "content used to train a general-purpose AI model. Art. 53(1)(d) requires it in order to "
                "give rightsholders and the public a minimum degree of transparency about the data basis. "
                "It follows the template of the AI Office and names, among other things, the type and "
                "origin of the data sources (for example public datasets, web crawls, licensed data).",
                kategorie_en="GPAI"),
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
                checklist=_CL_CRA_TECH_DOKU,
                titel_en="Technical documentation (Annex VII)",
                beschreibung_en="Technical documentation for products with digital elements.",
                erklaerung_en="The technical documentation is the evidence file with which a manufacturer "
                "demonstrates that its product with digital elements meets the cybersecurity requirements "
                "of the CRA. Art. 31 read together with Annex VII requires it as the basis of the "
                "conformity assessment and the CE marking. It covers the product description, design and "
                "development, the assessment of the essential requirements (Annex I), the vulnerability "
                "handling processes, the risk assessment, the support period as well as test reports and "
                "records of the standards applied.",
                kategorie_en="Conformity"),
        DocSpec("konformitaetserklaerung", "EU-Konformitätserklärung (Annex V)",
                "Art. 28 CRA", "Konformität", "EU-Konformitätserklärung.",
                erklaerung="Die EU-Konformitätserklärung ist die rechtsverbindliche Erklärung des Herstellers, "
                "dass sein Produkt mit digitalen Elementen die Anforderungen des CRA einhält. Art. 28 i.V.m. "
                "Annex V macht sie zur formalen Voraussetzung der CE-Kennzeichnung. Sie nennt Hersteller, "
                "eindeutige Produktidentifikation, die zugrunde gelegten Normen und das "
                "Konformitätsbewertungsverfahren sowie Ausstellungsort, Datum und Unterschrift.",
                suggested_assistant="eu-doc",
                titel_en="EU declaration of conformity (Annex V)",
                beschreibung_en="EU declaration of conformity.",
                erklaerung_en="The EU declaration of conformity is the manufacturer's legally binding "
                "declaration that its product with digital elements complies with the requirements of the "
                "CRA. Art. 28 read together with Annex V makes it the formal precondition for the CE "
                "marking. It names the manufacturer, the unambiguous identification of the product, the "
                "standards relied upon and the conformity assessment procedure as well as the place and "
                "date of issue and the signature.",
                kategorie_en="Conformity"),
        DocSpec("benutzeranleitung_annex_ii", "Benutzerinformationen/-anleitung (Annex II)",
                "Art. 13 CRA", "Betrieb", "Benutzerinformationen und Anleitung.",
                erklaerung="Die Benutzerinformationen/-anleitung versetzen den Nutzer in die Lage, ein "
                "Produkt mit digitalen Elementen sicher in Betrieb zu nehmen, zu betreiben und außer Betrieb "
                "zu nehmen. Art. 13 i.V.m. Annex II verlangt sie als verpflichtende Begleitinformation. "
                "Hinein gehören Hersteller- und Kontaktangaben, eine Anlaufstelle für Schwachstellenmeldungen, "
                "der bestimmungsgemäße Gebrauch, sicherheitsrelevante Konfiguration, der Bezug von "
                "Sicherheitsupdates sowie das Ende des Supportzeitraums.",
                checklist=_CL_CRA_BENUTZERINFO,
                titel_en="Information and instructions to the user (Annex II)",
                beschreibung_en="Information and instructions for the user.",
                erklaerung_en="The information and instructions to the user enable the user to put a "
                "product with digital elements into service, operate it and decommission it securely. "
                "Art. 13 read together with Annex II requires them as mandatory accompanying "
                "information. They cover the manufacturer's details and contact data, a point of contact "
                "for reporting vulnerabilities, the intended use, security-relevant configuration, how "
                "security updates are obtained as well as the end of the support period.",
                kategorie_en="Operation"),
        # Die Software-Stückliste ist **Nr. 1** des Anhangs I Teil II
        # (32024R2847, S. 68): „Schwachstellen und Komponenten … ermitteln und
        # dokumentieren, u. a. durch Erstellung einer Software-Stückliste in
        # einem gängigen maschinenlesbaren Format“. „Anhang I Teil II“ ohne
        # Nummer zeigt auf acht Anforderungen, von denen sieben nichts mit der
        # SBOM zu tun haben.
        DocSpec("sbom_begleitdoc", "SBOM-Begleitdokument",
                "Annex I Teil II Nr. 1 CRA", "Lieferkette",
                "Begleitdokument zur Software Bill of Materials.",
                erklaerung="Eine SBOM (Software Bill of Materials) ist ein maschinenlesbares Verzeichnis aller "
                "in einem Produkt enthaltenen Software-Komponenten und ihrer Abhängigkeiten samt "
                "Versionen/Lizenzen. Der CRA verlangt sie (Annex I Teil II Nr. 1) zur Nachverfolgung von "
                "Schwachstellen in Drittkomponenten. Das Begleitdokument beschreibt Format (z. B. "
                "CycloneDX/SPDX), Erstellungsweg, Aktualisierungsfrequenz und wo Nutzer die SBOM erhalten.",
                suggested_assistant="sbom-doc",
                titel_en="SBOM accompanying document",
                beschreibung_en="Accompanying document for the software bill of materials.",
                erklaerung_en="An SBOM (software bill of materials) is a machine-readable inventory of all "
                "software components contained in a product and of their dependencies, together with "
                "versions and licences. The CRA requires it (Annex I Part II No. 1) in order to track "
                "vulnerabilities in third-party components. The accompanying document describes the format "
                "(for example CycloneDX/SPDX), how it is produced, how often it is updated and where users "
                "obtain the SBOM.",
                kategorie_en="Supply chain",
                rechtsgrundlage_en="Annex I Part II No. 1 CRA"),
        # Die Strategie für die koordinierte Offenlegung steht in **Anhang I
        # Teil II Nr. 5** (32024R2847, S. 69): „eine Strategie für die
        # koordinierte Offenlegung von Schwachstellen aufstellen und
        # umsetzen“. Art. 13 Abs. 8 regelt die Behandlung von Schwachstellen
        # nach Anhang I Teil II und den Unterstützungszeitraum; sein letzter
        # Unterabsatz verweist auf Nr. 5 zurück, ist also der
        # Pflichtenanker — die Sachnorm aber nicht. Deshalb steht hier die
        # Sachnorm vorn. Die Kontaktadresse ist Nr. 6 (#1792).
        DocSpec("vuln_disclosure_policy", "Coordinated Vulnerability Disclosure Policy",
                "Annex I Teil II Nr. 5 CRA", "Schwachstellen",
                "Richtlinie zur koordinierten Offenlegung.",
                erklaerung="Die Coordinated Vulnerability Disclosure (CVD) Policy regelt, wie Sicherheits"
                "forscher und Nutzer Schwachstellen melden können und wie der Hersteller damit umgeht. Der "
                "CRA (Annex I Teil II Nr. 5 i.V.m. Art. 13 Abs. 8) verlangt einen solchen koordinierten "
                "Offenlegungsprozess. "
                "Die Richtlinie nennt die Meldewege und Anlaufstelle, Reaktions- und Behebungsfristen, "
                "den Umgang mit der Veröffentlichung sowie Zusagen gegenüber Meldenden (z. B. kein rechtliches Vorgehen).",
                suggested_assistant="c8",
                titel_en="Coordinated vulnerability disclosure policy",
                beschreibung_en="Policy on coordinated disclosure.",
                erklaerung_en="The coordinated vulnerability disclosure (CVD) policy governs how security "
                "researchers and users can report vulnerabilities and how the manufacturer deals with "
                "them. The CRA (Annex I Part II No. 5 read together with Art. 13(8)) requires such a "
                "coordinated disclosure process. The policy names the reporting channels and the point of "
                "contact, response and remediation deadlines, the handling of publication as well as "
                "commitments towards those reporting (for example no legal action).",
                kategorie_en="Vulnerabilities",
                rechtsgrundlage_en="Annex I Part II No. 5 CRA"),
        # „Art. 13 CRA“ zeigte auf einen Artikel mit 25 Absätzen. Gemeint sind
        # Art. 13 Abs. 8 (Unterstützungszeitraum, mindestens fünf Jahre) sowie
        # Anhang I Teil II Nr. 2 (unverzüglich behandeln und beheben, soweit
        # technisch machbar getrennt von Funktionsaktualisierungen) und Nr. 8
        # (unverzüglich und kostenlos verbreiten, mit Hinweisen) —
        # 32024R2847, S. 36 bzw. S. 68 f.
        DocSpec("update_policy", "Security-Update-/Support-Policy",
                "Art. 13(8) CRA; Annex I Teil II Nr. 2 und 8", "Betrieb",
                "Update- und Support-Richtlinie.",
                erklaerung="Die Security-Update-/Support-Policy legt fest, wie lange und auf welche Weise ein "
                "Produkt mit Sicherheitsupdates versorgt wird. Der CRA (Art. 13 Abs. 8 i.V.m. Annex I "
                "Teil II Nr. 2 und 8) verpflichtet Hersteller, "
                "Schwachstellen über einen angemessenen Supportzeitraum kostenlos zu beheben. Die Richtlinie "
                "definiert den Supportzeitraum, Reaktionszeiten für kritische Patches, den Bereitstellungs- "
                "und Installationsweg von Updates sowie End-of-Life-Hinweise.",
                suggested_assistant="c9",
                titel_en="Security update and support policy",
                beschreibung_en="Update and support policy.",
                erklaerung_en="The security update and support policy sets out for how long and in what "
                "way a product is supplied with security updates. The CRA (Art. 13(8) read together with "
                "Annex I Part II No. 2 and 8) obliges manufacturers "
                "to remedy vulnerabilities free of charge over an appropriate support period. The policy "
                "defines the support period, response times for critical patches, how updates are made "
                "available and installed as well as end-of-life notices.",
                kategorie_en="Operation",
                rechtsgrundlage_en="Art. 13(8) CRA; Annex I Part II No. 2 and 8"),
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
                suggested_assistant="nis2-is-leitlinie",
                titel_en="Information security policy + risk analysis policy",
                beschreibung_en="Information security policy and risk analysis.",
                erklaerung_en="The information security policy is the top-level steering document for "
                "information security and lays down the principles and responsibilities adopted by the "
                "management body. Art. 21(2) point (a) NIS 2 Directive requires policies on risk analysis "
                "and information system security. It covers the objectives and scope, roles and "
                "responsibilities, the risk management approach (methodology for identifying and "
                "assessing risks) as well as binding security requirements for the organisation.",
                kategorie_en="Governance"),
        DocSpec("incident_handling_konzept", "Incident-Handling-Konzept",
                "Art. 21(2)b NIS2", "Vorfälle",
                "Konzept zur Behandlung von Sicherheitsvorfällen.",
                erklaerung="Das Incident-Handling-Konzept beschreibt, wie die Organisation "
                "Sicherheitsvorfälle erkennt, bewertet, eindämmt und behebt. Art. 21(2)b NIS2 verlangt ein "
                "Konzept zur Behandlung von Sicherheitsvorfällen. Hinein gehören die Vorfall-Klassifizierung, "
                "Rollen und Eskalationswege, der Ablauf von der Erkennung bis zur Wiederherstellung, die "
                "Anbindung an die NIS2-Meldepflichten (24h/72h/1 Monat) sowie die Nachbereitung (Lessons Learned).",
                suggested_assistant="nis2-incident-handling-konzept",
                titel_en="Incident handling policy",
                beschreibung_en="Policy on the handling of security incidents.",
                erklaerung_en="The incident handling policy describes how the entity detects, assesses, "
                "contains and remedies security incidents. Art. 21(2) point (b) NIS 2 Directive requires "
                "a policy on incident handling. It covers the classification of incidents, roles and "
                "escalation paths, the course of events from detection through to recovery, the link to "
                "the NIS 2 reporting obligations (24 h / 72 h / one month) as well as the follow-up "
                "(lessons learned).",
                kategorie_en="Incidents"),
        DocSpec("bcm_dr_plan", "BCM-/DR-/Krisenmanagement-Plan",
                "Art. 21(2)c NIS2", "Kontinuität",
                "Business Continuity, Disaster Recovery, Krisenmanagement.",
                erklaerung="Der BCM-/DR-/Krisenmanagement-Plan stellt sicher, dass kritische Dienste auch "
                "während und nach einer Störung aufrechterhalten oder schnell wiederhergestellt werden. "
                "Art. 21(2)c NIS2 verlangt Maßnahmen für Geschäftskontinuität (inkl. Backup-Management) und "
                "Krisenmanagement. Hinein gehören Business-Impact-Analyse, Wiederanlaufziele (RTO/RPO), "
                "Backup- und Wiederherstellungsverfahren, Notfall- und Krisenorganisation sowie regelmäßige Tests.",
                suggested_assistant="nis2-bcm-dr-plan",
                titel_en="BCM / DR / crisis management plan",
                beschreibung_en="Business continuity, disaster recovery, crisis management.",
                erklaerung_en="The BCM / DR / crisis management plan ensures that critical services are "
                "maintained during and after a disruption or restored quickly. Art. 21(2) point (c) NIS 2 "
                "Directive requires measures for business continuity (including backup management) and "
                "crisis management. It covers the business impact analysis, recovery objectives "
                "(RTO/RPO), backup and restore procedures, the emergency and crisis organisation as well "
                "as regular testing.",
                kategorie_en="Continuity"),
        DocSpec("lieferketten_richtlinie", "Lieferketten-Sicherheitsrichtlinie",
                "Art. 21(2)d NIS2", "Lieferkette",
                "Sicherheit in der Lieferkette.",
                erklaerung="Die Lieferketten-Sicherheitsrichtlinie regelt die Sicherheit der Beziehungen zu "
                "Lieferanten und Dienstleistern. Art. 21(2)d NIS2 verlangt, Sicherheitsaspekte der "
                "Lieferkette und der Beziehungen zu unmittelbaren Anbietern zu berücksichtigen. Hinein "
                "gehören Anforderungen an die Lieferantenauswahl, vertragliche Sicherheitsvorgaben, die "
                "Bewertung von Lieferantenrisiken sowie die Behandlung von Schwachstellen und Vorfällen bei Dritten.",
                suggested_assistant="nis2-lieferketten-richtlinie",
                titel_en="Supply chain security policy",
                beschreibung_en="Security in the supply chain.",
                erklaerung_en="The supply chain security policy governs the security of relationships "
                "with suppliers and service providers. Art. 21(2) point (d) NIS 2 Directive requires "
                "security-related aspects of the supply chain and of the relationships with direct "
                "suppliers to be taken into account. It covers requirements for supplier selection, "
                "contractual security provisions, the assessment of supplier risks as well as the "
                "handling of vulnerabilities and incidents at third parties.",
                kategorie_en="Supply chain"),
        DocSpec("krypto_richtlinie", "Krypto-/Verschlüsselungsrichtlinie",
                "Art. 21(2)h NIS2", "Technik",
                "Einsatz von Kryptografie und Verschlüsselung.",
                erklaerung="Die Krypto-/Verschlüsselungsrichtlinie legt fest, wie und wann Kryptografie zum "
                "Schutz von Daten eingesetzt wird. Art. 21(2)h NIS2 verlangt Konzepte und Verfahren für den "
                "Einsatz von Kryptografie und, wo angemessen, Verschlüsselung. Hinein gehören zugelassene "
                "Algorithmen und Schlüssellängen, Vorgaben zur Verschlüsselung von Daten bei der Übertragung "
                "und Speicherung sowie das Schlüsselmanagement (Erzeugung, Aufbewahrung, Rotation, Vernichtung).",
                suggested_assistant="nis2-krypto-richtlinie",
                titel_en="Cryptography and encryption policy",
                beschreibung_en="Use of cryptography and encryption.",
                erklaerung_en="The cryptography and encryption policy lays down how and when "
                "cryptography is used to protect data. Art. 21(2) point (h) NIS 2 Directive requires "
                "policies and procedures regarding the use of cryptography and, where appropriate, "
                "encryption. It covers approved algorithms and key lengths, requirements for encrypting "
                "data in transit and at rest as well as key management (generation, storage, rotation, "
                "destruction).",
                kategorie_en="Technology"),
        # #1957: Titel und Inhalt **geweitet**, nicht das Zitat verengt.
        # Art. 21 Abs. 2 Buchst. i nennt drei Dinge — „Sicherheit des
        # Personals, Konzepte für die Zugriffskontrolle und Management von
        # Anlagen“ —, der Titel nannte zwei. Kein anderes Dokument des
        # NIS2-Katalogs deckte die Personalsicherheit ab (über Titel,
        # Beschreibung und Erklärung geprüft), das Zitat reichte also weiter
        # als der Inhalt. Buchst. i ist ein unteilbarer Buchstabe; ein Zitat
        # „Buchst. i, zweiter und dritter Teil“ liest sich wie eine Ausrede.
        # Fachlich gehört es ohnehin zusammen: Eintritt, Austritt,
        # Rollenwechsel und Zuverlässigkeitsprüfung sind genau die Vorgänge,
        # an denen Zugriffsrechte entstehen und vergehen.
        #
        # **Kein Checklisten-Punkt**, obwohl #1957 einen empfahl: Im
        # NIS2-Katalog hat **kein** Dokument eine Checkliste. Ein einzelner
        # Punkt „Personalsicherheit“ wäre das erste Panel des Moduls und würde
        # genau einen von mehreren Pflichtinhalten dieses Konzepts ausweisen —
        # eine Liste, die einen von vielen führt, behauptet Vollständigkeit.
        # Das ist dieselbe Falle wie Anhang IV mit acht von neun Nummern
        # (#1953). Eine Checkliste für NIS2 ist ein eigener Vorgang: entweder
        # vollständig je Dokument oder nicht.
        DocSpec("zugriffskontroll_policy", "Personalsicherheits-, Zugriffskontroll- und "
                "Asset-Management-Policy",
                "Art. 21(2)i NIS2", "Technik",
                "Sicherheit des Personals, Zugriffskontrolle und Asset-Management.",
                erklaerung="Die Policy regelt, wer auf welche Systeme und "
                "Daten zugreifen darf, wie die Werte (Assets) der Organisation verwaltet werden und "
                "welche personalbezogenen Sicherheitsmaßnahmen dabei greifen. "
                "Art. 21(2)i NIS2 verlangt die Sicherheit des Personals sowie Konzepte für "
                "Zugriffskontrolle und Anlagenverwaltung. Hinein "
                "gehören ein Asset-Inventar, die Rollen-/Rechtevergabe nach dem Need-to-know- und "
                "Least-Privilege-Prinzip, Berechtigungsüberprüfungen, Vorgaben für privilegierte Zugänge "
                "sowie die personalbezogenen Vorgänge: Zuverlässigkeitsprüfung vor dem Zugang, "
                "Verpflichtung auf Vertraulichkeit, Rechteanpassung bei Rollenwechsel und der "
                "Entzug aller Zugänge beim Austritt.",
                suggested_assistant="nis2-zugriffskontroll-policy",
                titel_en="Human resources security, access control and asset management policy",
                beschreibung_en="Human resources security, access control and asset management.",
                erklaerung_en="The policy governs who may access "
                "which systems and data, how the assets of the entity are managed and which "
                "personnel-related security measures apply. Art. 21(2) "
                "point (i) NIS 2 Directive requires human resources security as well as policies on "
                "access control and asset management. It "
                "covers an asset inventory, the assignment of roles and permissions following the "
                "need-to-know and least-privilege principles, reviews of permissions, "
                "requirements for privileged access as well as the personnel-related steps: "
                "screening before access is granted, confidentiality undertakings, adjustment of "
                "permissions when roles change and the withdrawal of all access upon departure.",
                kategorie_en="Technology"),
        DocSpec("incident_meldung", "Incident-Meldung (24h/72h/1M)",
                "Art. 23 NIS2", "Vorfälle",
                "Meldungen an die zuständige Behörde.",
                erklaerung="Die Incident-Meldung ist die gesetzlich vorgeschriebene Benachrichtigung der "
                "zuständigen Behörde bzw. des CSIRT über einen erheblichen Sicherheitsvorfall. Art. 23 NIS2 "
                "schreibt ein mehrstufiges Verfahren vor: Frühwarnung binnen 24 Stunden, Vorfallmeldung "
                "binnen 72 Stunden und Abschlussbericht binnen eines Monats. Die Meldung enthält Art und "
                "Schwere des Vorfalls, betroffene Dienste, mutmaßliche Ursachen sowie ergriffene Gegen- und "
                "Abhilfemaßnahmen.",
                suggested_assistant="n8",
                titel_en="Incident notification (24 h / 72 h / 1 month)",
                beschreibung_en="Notifications to the competent authority.",
                erklaerung_en="The incident notification is the legally required notification of the "
                "competent authority or of the CSIRT about a significant incident. Art. 23 NIS 2 "
                "Directive prescribes a staged procedure: an early warning within 24 hours, an incident "
                "notification within 72 hours and a final report within one month. The notification "
                "contains the nature and severity of the incident, the services affected, the suspected "
                "causes as well as the countermeasures and mitigation measures taken.",
                kategorie_en="Incidents"),
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
                "sowie die Rechte der Betroffenen.",
                titel_en="Privacy notice",
                beschreibung_en="Information obligations towards data subjects.",
                erklaerung_en="A privacy notice informs data subjects how their personal data is "
                "processed. Art. 13 and 14 GDPR oblige the controller to provide this information in a "
                "transparent and comprehensible form (for example as a privacy policy). It covers the "
                "identity of the controller and, where applicable, of the data protection officer, the "
                "purposes and legal bases of the processing, the recipients, the storage period, "
                "transfers to third countries as well as the rights of the data subjects.",
                kategorie_en="Transparency",
                rechtsgrundlage_en="Art. 13/14 GDPR"),
        DocSpec("avv_mustervertrag", "AVV-Mustervertrag",
                "Art. 28 DSGVO", "Auftragsverarbeitung",
                "Vertrag zur Auftragsverarbeitung.",
                erklaerung="Der AVV-Mustervertrag (Auftragsverarbeitungsvertrag) regelt die "
                "Datenschutzpflichten, wenn ein Dienstleister personenbezogene Daten im Auftrag eines "
                "Verantwortlichen verarbeitet. Art. 28 DSGVO schreibt einen solchen Vertrag verpflichtend "
                "vor. Hinein gehören Gegenstand, Dauer, Art und Zweck der Verarbeitung, Kategorien "
                "betroffener Personen und Daten, Weisungsbindung, technisch-organisatorische Maßnahmen, der "
                "Einsatz von Sub-Auftragsverarbeitern sowie Kontroll- und Löschpflichten.",
                titel_en="Data processing agreement (model contract)",
                beschreibung_en="Contract for processing on behalf of a controller.",
                erklaerung_en="The model data processing agreement governs the data protection "
                "obligations where a service provider processes personal data on behalf of a controller. "
                "Art. 28 GDPR makes such a contract mandatory. It covers the subject matter, duration, "
                "nature and purpose of the processing, the categories of data subjects and of personal "
                "data, the obligation to act only on instructions, the technical and organisational "
                "measures, the engagement of sub-processors as well as audit and erasure obligations.",
                kategorie_en="Processing on behalf of a controller",
                rechtsgrundlage_en="Art. 28 GDPR"),
        DocSpec("tom_dokument", "TOM-Dokument",
                "Art. 32 DSGVO", "Sicherheit",
                "Technisch-organisatorische Maßnahmen.",
                erklaerung="Das TOM-Dokument beschreibt die technischen und organisatorischen Maßnahmen, mit "
                "denen personenbezogene Daten geschützt werden. Art. 32 DSGVO verlangt ein dem Risiko "
                "angemessenes Schutzniveau und dessen Nachweis. Hinein gehören u. a. Zugangs-, Zutritts- und "
                "Zugriffskontrolle, Verschlüsselung und Pseudonymisierung, Verfügbarkeit und "
                "Belastbarkeit der Systeme sowie Verfahren zur regelmäßigen Überprüfung der Wirksamkeit.",
                titel_en="TOM document (technical and organisational measures)",
                beschreibung_en="Technical and organisational measures.",
                erklaerung_en="The TOM document describes the technical and organisational measures by "
                "which personal data is protected. Art. 32 GDPR requires a level of protection "
                "appropriate to the risk, and evidence of it. It covers, among other things, physical "
                "access, system access and data access control, encryption and pseudonymisation, the "
                "availability and resilience of the systems as well as procedures for regularly testing "
                "their effectiveness.",
                kategorie_en="Security",
                rechtsgrundlage_en="Art. 32 GDPR"),
        DocSpec("vvt_auszug", "VVT-Auszug",
                "Art. 30 DSGVO", "Dokumentation",
                "Auszug aus dem Verzeichnis von Verarbeitungstätigkeiten.",
                erklaerung="Der VVT-Auszug ist ein Ausschnitt aus dem Verzeichnis von "
                "Verarbeitungstätigkeiten, das jeder Verantwortliche führen muss. Art. 30 DSGVO verlangt eine "
                "vollständige Übersicht aller Verarbeitungen personenbezogener Daten als zentralen "
                "Rechenschafts-Nachweis. Je Verarbeitung gehören hinein: Zwecke, Kategorien betroffener "
                "Personen und Daten, Empfänger, Drittlandtransfers, vorgesehene Löschfristen sowie die "
                "ergriffenen technisch-organisatorischen Maßnahmen.",
                titel_en="RoPA extract",
                beschreibung_en="Extract from the record of processing activities.",
                erklaerung_en="The RoPA extract is a section of the record of processing activities "
                "(RoPA) that every controller must maintain. Art. 30 GDPR requires a complete overview "
                "of all processing of personal data as the central accountability record. For each "
                "processing activity it covers the purposes, the categories of data subjects and of "
                "personal data, the recipients, transfers to third countries, the envisaged erasure "
                "periods as well as the technical and organisational measures taken.",
                kategorie_en="Documentation",
                rechtsgrundlage_en="Art. 30 GDPR"),
        DocSpec("loeschkonzept_doc", "Löschkonzept-Dokument",
                "Art. 17 DSGVO", "Löschung",
                "Dokumentiertes Löschkonzept.",
                erklaerung="Das Löschkonzept-Dokument legt fest, wann und wie personenbezogene Daten "
                "gelöscht werden, sobald der Zweck entfällt. Es setzt das Recht auf Löschung (Art. 17 DSGVO) "
                "sowie den Grundsatz der Speicherbegrenzung systematisch um, häufig methodisch nach "
                "DIN 66398. Hinein gehören Lösch- bzw. Aufbewahrungsfristen je Datenart, die auslösenden "
                "Ereignisse, Verantwortlichkeiten, Löschverfahren sowie die Dokumentation der durchgeführten Löschungen.",
                titel_en="Erasure concept document",
                beschreibung_en="Documented erasure concept.",
                erklaerung_en="The erasure concept document lays down when and how personal data is "
                "erased once the purpose ceases to apply. It systematically implements the right to "
                "erasure (Art. 17 GDPR) and the principle of storage limitation, frequently following the "
                "method of DIN 66398. It covers erasure and retention periods for each type of data, the "
                "triggering events, responsibilities, erasure procedures as well as the documentation of "
                "the erasures carried out.",
                kategorie_en="Erasure",
                rechtsgrundlage_en="Art. 17 GDPR"),
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
                pflicht=False,
                # #1954: Nur die **Rahmen**texte. Die BSI-Prüffragen selbst haben
                # keine amtliche englische Fassung und ihr Katalogtext ist
                # urheberrechtlich geschützt (BSI, #1118) — eine selbst
                # übersetzte Prüffrage wäre im Nachweis eine eigene Behauptung
                # über einen fremden Katalog. Der Eigenname bleibt deutsch.
                titel_en="Evidence and measures document",
                beschreibung_en="Evidence and measures document for each WiBA topic block.",
                erklaerung_en="The evidence and measures document demonstrates, for each WiBA topic "
                "block, that the BSI test questions of the „Weg in die Basis-Absicherung\" (the BSI path "
                "towards basic protection) are met. It serves small and medium-sized organisations as "
                "evidence of fundamentally secure IT operations (IT-Grundschutz, also with a view to data "
                "protection). It covers the measures implemented for each test question, references to "
                "existing evidence (for example configurations, policies), the persons responsible as "
                "well as open points and planned improvements.",
                kategorie_en="Evidence"),
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


def _uebersetzt(eintrag: dict[str, Any], sprache: str) -> dict[str, Any]:
    """Ein Eintrag in der gewünschten Sprache — über **eine** Stelle (#2089).

    ``shared/katalog_sprache`` kennt die Regeln schon: Positivliste der
    übersetzbaren Felder, Rückfall auf den deutschen Text (nicht auf leer —
    eine halb übersetzte Liste ist schlechter als eine deutsche), und
    ``doc_type``/``id`` bleiben unberührt, weil sie **Schlüssel** in
    ``<modul>_managed_docs`` sind. Eine eigene Umformung hier wäre die zweite
    Wahrheit darüber, was übersetzt werden darf.
    """
    if not sprache or sprache == "de":
        return eintrag
    from shared.katalog_sprache import uebersetze
    return uebersetze(eintrag, sprache)


def _uebersetzt_viele(eintraege: list[dict[str, Any]],
                      sprache: str) -> list[dict[str, Any]]:
    if not sprache or sprache == "de":
        return eintraege
    from shared.katalog_sprache import uebersetze_viele
    return uebersetze_viele(eintraege, sprache)


def get_bausteine(modul: str, doc_type: str) -> list[dict[str, str]]:
    """Querverweis-Bausteine eines Dokumenttyps (#1236). Leer = kein Hinweis."""
    return [dict(b) for b in _BAUSTEINE.get((modul, doc_type), ())]


def kennt_doc_type(modul: str, doc_type: str) -> bool:
    """Steht dieser Dokumenttyp im Rechts-Kanon? (#2089)

    Eine **Präsenz-Prüfung**, kein Textzugriff — deshalb ohne Sprache. Sie hat
    einen eigenen Namen, damit der Wächter keine Ausnahme braucht: Jeder
    ``get_*``-Aufruf muss eine Sprache tragen, und eine Ausnahmeliste wird zum
    Teppich (#1805/#1834).
    """
    return any(d.doc_type == doc_type for d in DOCUMENT_CATALOG.get(modul, []))


def get_catalog(modul: str, sprache: str = "") -> list[dict[str, Any]]:
    """Der Rechts-Kanon eines Moduls, auf Wunsch in der Sprache des Mandanten.

    **``sprache=""`` liefert den Katalog byte-identisch wie vor #2089** — damit
    bleibt jeder Bestandsaufrufer und jeder Bestandstest unverändert (dieselbe
    Zusage wie ``evidence_section`` und ``prompt_zusatz``).

    #2089: Dieser Katalog führt je ``DocSpec`` fünf und je ``ChecklistItem``
    zwei englische Felder, **170 von 212 gefüllt** — und keine Stelle hat sie
    gelesen. Die Übersetzungsschicht war ausdrücklich dafür erweitert worden
    (``shared/katalog_sprache.UEBERSETZBAR`` nennt ``erklaerung``,
    ``kategorie``, ``rechtsgrundlage``, ``rechtsbezug``), nur blieben die drei
    Zugriffsfunktionen ohne Parameter. Dieselbe Fehlerklasse wie #1735 und
    #1841: Die Arbeit war getan, sie kam nur nirgends an.
    """
    aus = [d.to_dict() for d in DOCUMENT_CATALOG.get(modul, [])]
    return _uebersetzt_viele(aus, sprache)


def get_doc_spec(modul: str, doc_type: str,
                 sprache: str = "") -> dict[str, Any] | None:
    for d in DOCUMENT_CATALOG.get(modul, []):
        if d.doc_type == doc_type:
            return _uebersetzt(d.to_dict(), sprache)
    return None


def get_checklist(modul: str, doc_type: str,
                  sprache: str = "") -> list[dict[str, Any]]:
    """Soll-Inhalte (Konformitäts-Checkliste) eines Dokumenttyps (#1234).

    Leere Liste, wenn keine Checkliste gepflegt ist (Panel wird dann nicht
    angezeigt — kein Fehler).
    """
    for d in DOCUMENT_CATALOG.get(modul, []):
        if d.doc_type == doc_type:
            return _uebersetzt_viele([c.to_dict() for c in d.checklist],
                                     sprache)
    return []
