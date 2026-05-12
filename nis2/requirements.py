"""NIS2-Modul – Anforderungskatalog (Richtlinie (EU) 2022/2555)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

EINRICHTUNGSKLASSEN: dict[str, dict[str, str]] = {
    "wesentlich": {
        "label": "Wesentliche Einrichtung",
        "beschreibung": "Einrichtungen der in Anhang I genannten Sektoren (z.B. Energie, Verkehr, Bankwesen, Gesundheit, Wasser, digitale Infrastruktur).",
    },
    "wichtig": {
        "label": "Wichtige Einrichtung",
        "beschreibung": "Einrichtungen der in Anhang II genannten Sektoren (z.B. Post, Abfallwirtschaft, Chemie, Lebensmittel, verarbeitendes Gewerbe, digitale Dienste).",
    },
    "beide": {
        "label": "Wesentliche und Wichtige Einrichtung",
        "beschreibung": "Einrichtung ist sowohl als wesentliche als auch als wichtige Einrichtung eingestuft.",
    },
}

KAPITEL: dict[str, dict[str, str]] = {
    "NIS1": {
        "titel": "Governance & Verantwortung",
        "referenz": "Art. 20 NIS2-RL",
        "beschreibung": "Anforderungen an das Management, die Unternehmensleitung und die organisatorische Verantwortung für Cybersicherheit.",
    },
    "NIS2": {
        "titel": "Risikomanagement & Technische Maßnahmen",
        "referenz": "Art. 21 NIS2-RL",
        "beschreibung": "Maßnahmen zur Bewältigung von Cybersicherheitsrisiken für Netz- und Informationssysteme.",
    },
    "NIS3": {
        "titel": "Meldepflichten & Incident Response",
        "referenz": "Art. 23 NIS2-RL",
        "beschreibung": "Pflichten zur Meldung erheblicher Sicherheitsvorfälle an die zuständigen Behörden.",
    },
    "NIS4": {
        "titel": "Lieferkettensicherheit",
        "referenz": "Art. 21 Abs. 2 lit. d NIS2-RL",
        "beschreibung": "Sicherheit in der Lieferkette einschließlich sicherheitsrelevanter Aspekte der Beziehungen zwischen Einrichtungen und ihren unmittelbaren Anbietern.",
    },
    "NIS5": {
        "titel": "Implementierung & Zertifizierung",
        "referenz": "Art. 24–25 NIS2-RL",
        "beschreibung": "Nutzung von europäischen Cybersicherheitszertifizierungsschemata und Standardisierungsvorgaben zur Umsetzung.",
    },
}

BEWERTUNG_SKALA: dict[int, dict[str, str]] = {
    0: {"label": "Nicht bewertet",       "farbe": "#9E9E9E"},
    1: {"label": "Nicht erfüllt",         "farbe": "#C62828"},
    2: {"label": "In Planung",            "farbe": "#E65100"},
    3: {"label": "Teilweise erfüllt",     "farbe": "#F57F17"},
    4: {"label": "Weitgehend erfüllt",    "farbe": "#2E7D32"},
    5: {"label": "Vollständig erfüllt",   "farbe": "#1B5E20"},
}

BEWERTUNG_LABELS: dict[int, str] = {k: v["label"] for k, v in BEWERTUNG_SKALA.items()}

NIS2_ANFORDERUNGEN: list[dict[str, Any]] = [
    # ── NIS1: Governance & Verantwortung ────────────────────────────────────
    {
        "id": "NIS1-01", "kapitel": "NIS1", "gewichtung": 3,
        "ref": "Art. 20 Abs. 1 NIS2-RL",
        "titel": "Verantwortung der Unternehmensleitung",
        "beschreibung": "Die Leitungsorgane der Einrichtung müssen die Maßnahmen zum Cybersicherheits-Risikomanagement genehmigen und deren Umsetzung überwachen.",
        "hinweise": "Nachweise: Beschlüsse des Leitungsorgans, Sitzungsprotokolle, Richtlinien mit Freigabevermerk der Geschäftsführung.",
    },
    {
        "id": "NIS1-02", "kapitel": "NIS1", "gewichtung": 3,
        "ref": "Art. 20 Abs. 1 NIS2-RL",
        "titel": "Schulung der Unternehmensleitung",
        "beschreibung": "Mitglieder der Leitungsorgane müssen an Schulungen zu Cybersicherheitsrisiken teilnehmen und ihren Mitarbeitenden vergleichbare Schulungen anbieten.",
        "hinweise": "Nachweise: Schulungsnachweise, Zertifikate, Schulungsplan für das Managementteam.",
    },
    {
        "id": "NIS1-03", "kapitel": "NIS1", "gewichtung": 2,
        "ref": "Art. 20 Abs. 2 NIS2-RL",
        "titel": "Haftung der Leitungsorgane",
        "beschreibung": "Leitungsorgane können für Verstöße gegen Cybersicherheitspflichten haftbar gemacht werden. Einrichtungen müssen sicherstellen, dass Leitungsorgane die Anforderungen kennen.",
        "hinweise": "Nachweise: Dokumentierte Kenntnis der Pflichten, interne Richtlinien zur Haftung.",
    },
    {
        "id": "NIS1-04", "kapitel": "NIS1", "gewichtung": 2,
        "ref": "Art. 20 NIS2-RL",
        "titel": "Cybersicherheitsstrategie",
        "beschreibung": "Die Einrichtung hat eine dokumentierte Cybersicherheitsstrategie mit klaren Zielen, Verantwortlichkeiten und Überprüfungsmechanismen.",
        "hinweise": "Nachweise: Strategie-Dokument, Governance-Framework, RACI-Matrix für Cybersicherheit.",
    },
    {
        "id": "NIS1-05", "kapitel": "NIS1", "gewichtung": 2,
        "ref": "Art. 20 NIS2-RL",
        "titel": "Rollen und Verantwortlichkeiten",
        "beschreibung": "Klare Definition von Cybersicherheitsrollen (CISO, IT-Sicherheitsbeauftragter o.ä.) mit dokumentierten Aufgaben und Befugnissen.",
        "hinweise": "Nachweise: Stellenbeschreibungen, Organigramm, Beauftragungsschreiben.",
    },

    # ── NIS2: Risikomanagement & Technische Maßnahmen ───────────────────────
    {
        "id": "NIS2-01", "kapitel": "NIS2", "gewichtung": 3,
        "ref": "Art. 21 Abs. 1 NIS2-RL",
        "titel": "Risikoanalyse und Sicherheitsrichtlinien",
        "beschreibung": "Geeignete und verhältnismäßige technische, betriebliche und organisatorische Maßnahmen auf Basis einer umfassenden Risikoanalyse für Netz- und Informationssysteme.",
        "hinweise": "Nachweise: Risikoregister, Risikoanalyse-Dokument, Sicherheitsrichtlinien (ISO 27001, BSI IT-Grundschutz).",
    },
    {
        "id": "NIS2-02", "kapitel": "NIS2", "gewichtung": 3,
        "ref": "Art. 21 Abs. 2 lit. a NIS2-RL",
        "titel": "Konzepte für Risikoanalyse und Informationssicherheit",
        "beschreibung": "Konzepte in Bezug auf die Risikoanalyse und Sicherheit von Informationssystemen müssen vorhanden und regelmäßig aktualisiert werden.",
        "hinweise": "Nachweise: ISMS-Dokumentation, Sicherheitskonzept, Informationssicherheits-Leitlinie.",
    },
    {
        "id": "NIS2-03", "kapitel": "NIS2", "gewichtung": 3,
        "ref": "Art. 21 Abs. 2 lit. b NIS2-RL",
        "titel": "Bewältigung von Sicherheitsvorfällen",
        "beschreibung": "Konzepte und Verfahren für die Bewältigung von Sicherheitsvorfällen (Incident Management) müssen etabliert sein.",
        "hinweise": "Nachweise: Incident-Response-Plan, Notfallhandbuch, Eskalationsverfahren, Playbooks.",
    },
    {
        "id": "NIS2-04", "kapitel": "NIS2", "gewichtung": 3,
        "ref": "Art. 21 Abs. 2 lit. c NIS2-RL",
        "titel": "Business Continuity und Krisenmanagement",
        "beschreibung": "Aufrechterhaltung des Betriebs (BCM) mit Backup-Management, Wiederherstellung im Notfall und Krisenmanagement.",
        "hinweise": "Nachweise: BCM-Plan, BCP-Tests, RTO/RPO-Definitionen, Backup-Konzept, Disaster-Recovery-Tests.",
    },
    {
        "id": "NIS2-05", "kapitel": "NIS2", "gewichtung": 2,
        "ref": "Art. 21 Abs. 2 lit. e NIS2-RL",
        "titel": "Sicherheit beim Erwerb, Entwicklung und Wartung",
        "beschreibung": "Sicherheit bei der Beschaffung, Entwicklung und Wartung von Netz- und Informationssystemen einschließlich Management und Offenlegung von Schwachstellen.",
        "hinweise": "Nachweise: Secure-SDLC-Prozesse, Patch-Management-Konzept, Vulnerability-Disclosure-Policy.",
    },
    {
        "id": "NIS2-06", "kapitel": "NIS2", "gewichtung": 2,
        "ref": "Art. 21 Abs. 2 lit. f NIS2-RL",
        "titel": "Wirksamkeit von Sicherheitsmaßnahmen",
        "beschreibung": "Konzepte und Verfahren zur Bewertung der Wirksamkeit von Risikomanagementmaßnahmen im Bereich Cybersicherheit.",
        "hinweise": "Nachweise: KPIs für Cybersicherheit, Audit-Berichte, Penetrationstests, Metriken-Dashboard.",
    },
    {
        "id": "NIS2-07", "kapitel": "NIS2", "gewichtung": 2,
        "ref": "Art. 21 Abs. 2 lit. g NIS2-RL",
        "titel": "Grundlegende Hygienemaßnahmen und Schulungen",
        "beschreibung": "Grundlegende Praktiken der Cyberhygiene und Schulungen im Bereich Cybersicherheit für alle Mitarbeitenden.",
        "hinweise": "Nachweise: Security-Awareness-Schulungen, Phishing-Tests, Patch-Zyklen, Passwortrichtlinie, MFA.",
    },
    {
        "id": "NIS2-08", "kapitel": "NIS2", "gewichtung": 2,
        "ref": "Art. 21 Abs. 2 lit. h NIS2-RL",
        "titel": "Kryptografie und Verschlüsselung",
        "beschreibung": "Konzepte und Verfahren für den Einsatz von Kryptografie und gegebenenfalls Verschlüsselung.",
        "hinweise": "Nachweise: Kryptografie-Richtlinie, Inventar kryptografischer Verfahren, Zertifikatsmanagement.",
    },
    {
        "id": "NIS2-09", "kapitel": "NIS2", "gewichtung": 3,
        "ref": "Art. 21 Abs. 2 lit. i NIS2-RL",
        "titel": "Sicherheit des Personals und Zugangskontrolle",
        "beschreibung": "Sicherheit des Personals, Konzepte für die Zugriffskontrolle und Management von Anlagen (Asset Management).",
        "hinweise": "Nachweise: IAM-Konzept, Zero-Trust-Architektur, privilegierte Zugangsverwaltung (PAM), HR-Sicherheitsrichtlinien.",
    },
    {
        "id": "NIS2-10", "kapitel": "NIS2", "gewichtung": 2,
        "ref": "Art. 21 Abs. 2 lit. j NIS2-RL",
        "titel": "Multi-Faktor-Authentifizierung",
        "beschreibung": "Verwendung von Multi-Faktor-Authentifizierung (MFA) oder kontinuierlicher Authentifizierungslösungen, gesicherte Sprach-, Video- und Textkommunikation.",
        "hinweise": "Nachweise: MFA-Implementierungsnachweis, Konfigurationsdokumentationen, Authentifizierungsrichtlinie.",
    },

    # ── NIS3: Meldepflichten & Incident Response ─────────────────────────────
    {
        "id": "NIS3-01", "kapitel": "NIS3", "gewichtung": 3,
        "ref": "Art. 23 Abs. 1 NIS2-RL",
        "titel": "Meldung erheblicher Sicherheitsvorfälle",
        "beschreibung": "Erhebliche Sicherheitsvorfälle sind unverzüglich der zuständigen nationalen Behörde (BSI in Deutschland) oder dem CSIRT zu melden.",
        "hinweise": "Nachweise: Meldehistorie, Meldeprozess-Dokumentation, Kontaktdaten der zuständigen Behörde.",
    },
    {
        "id": "NIS3-02", "kapitel": "NIS3", "gewichtung": 3,
        "ref": "Art. 23 Abs. 4 NIS2-RL",
        "titel": "Frühwarnung binnen 24 Stunden",
        "beschreibung": "Unverzügliche Frühwarnung an die zuständige Behörde oder das CSIRT binnen 24 Stunden nach Kenntnisnahme eines erheblichen Sicherheitsvorfalls.",
        "hinweise": "Nachweise: Dokumentierter Eskalationsprozess, Kontaktliste BSI/CSIRT, Bereitschaftsdienst (24/7).",
    },
    {
        "id": "NIS3-03", "kapitel": "NIS3", "gewichtung": 3,
        "ref": "Art. 23 Abs. 4 lit. b NIS2-RL",
        "titel": "Vorfallsmeldung binnen 72 Stunden",
        "beschreibung": "Vorfallsmeldung mit erster Bewertung des Sicherheitsvorfalls, Schweregrad und Kompromittierungsindikatoren binnen 72 Stunden nach Kenntnisnahme.",
        "hinweise": "Nachweise: Meldeformulare, Ticketsystem-Exports mit Zeitstempeln, Kommunikationsnachweis mit BSI.",
    },
    {
        "id": "NIS3-04", "kapitel": "NIS3", "gewichtung": 2,
        "ref": "Art. 23 Abs. 4 lit. c NIS2-RL",
        "titel": "Abschlussbericht binnen eines Monats",
        "beschreibung": "Abschlussbericht mit detaillierter Beschreibung des Vorfalls, Ursachenanalyse, ergriffenen Abhilfemaßnahmen und Auswirkungen spätestens einen Monat nach Meldung.",
        "hinweise": "Nachweise: Post-Incident-Review-Dokumente, Root-Cause-Analysis, Lessons-Learned-Protokolle.",
    },
    {
        "id": "NIS3-05", "kapitel": "NIS3", "gewichtung": 2,
        "ref": "Art. 23 Abs. 2 NIS2-RL",
        "titel": "Benachrichtigung betroffener Empfänger",
        "beschreibung": "Erhebliche Cybersicherheitsbedrohungen müssen den betroffenen Empfängern der Dienste mitgeteilt werden, wenn dies geboten ist.",
        "hinweise": "Nachweise: Kommunikationsplan, Benachrichtigungsvorlagen, Meldenachweis an Kunden/Nutzer.",
    },
    {
        "id": "NIS3-06", "kapitel": "NIS3", "gewichtung": 2,
        "ref": "Art. 23 Abs. 3 NIS2-RL",
        "titel": "Erkennung und Klassifizierung von Vorfällen",
        "beschreibung": "Prozesse zur Erkennung, Bewertung und Klassifizierung von Sicherheitsvorfällen nach Erheblichkeit (wesentliche vs. nicht-wesentliche Vorfälle).",
        "hinweise": "Nachweise: SIEM/SOC-Dokumentation, Klassifizierungsmatrix, Erkennungsverfahren.",
    },

    # ── NIS4: Lieferkettensicherheit ─────────────────────────────────────────
    {
        "id": "NIS4-01", "kapitel": "NIS4", "gewichtung": 3,
        "ref": "Art. 21 Abs. 2 lit. d NIS2-RL",
        "titel": "Sicherheit in der Lieferkette",
        "beschreibung": "Sicherheit in der Lieferkette einschließlich sicherheitsbezogener Aspekte der Beziehungen zwischen Einrichtungen und ihren unmittelbaren Anbietern und Diensteanbietern.",
        "hinweise": "Nachweise: Lieferantenverzeichnis mit Risikoklassifizierung, Vertragsklauseln, Lieferantenbewertungen.",
    },
    {
        "id": "NIS4-02", "kapitel": "NIS4", "gewichtung": 2,
        "ref": "Art. 21 Abs. 3 NIS2-RL",
        "titel": "Berücksichtigung von Schwachstellen in der Lieferkette",
        "beschreibung": "Berücksichtigung der Gesamtqualität der Produkte und Cybersicherheitspraktiken der Lieferanten und Diensteanbieter, einschließlich ihrer Entwicklungsverfahren.",
        "hinweise": "Nachweise: Lieferanten-Audits, SBOM-Anforderungen, Sicherheitsfragebögen für Lieferanten.",
    },
    {
        "id": "NIS4-03", "kapitel": "NIS4", "gewichtung": 2,
        "ref": "Art. 22 NIS2-RL",
        "titel": "Koordinierte Sicherheitsrisikobewertung der Lieferketten",
        "beschreibung": "Beteiligung an koordinierten Sicherheitsrisikobewertungen kritischer IKT-Lieferketten auf EU-Ebene (NIS-Kooperationsgruppe).",
        "hinweise": "Nachweise: Dokumentation der Beteiligung, Ergebnisberichte koordinierter Bewertungen.",
    },
    {
        "id": "NIS4-04", "kapitel": "NIS4", "gewichtung": 2,
        "ref": "Art. 21 Abs. 2 lit. d NIS2-RL",
        "titel": "Vertragliche Sicherheitsanforderungen",
        "beschreibung": "Vertragliche Sicherheitsanforderungen an Lieferanten und Diensteanbieter, einschließlich Mindest-Cybersicherheitsstandards und Auditrechte.",
        "hinweise": "Nachweise: Musterverträge mit Sicherheitsklauseln, SLAs mit Sicherheitsanforderungen, Auditberichte.",
    },

    # ── NIS5: Implementierung & Zertifizierung ───────────────────────────────
    {
        "id": "NIS5-01", "kapitel": "NIS5", "gewichtung": 2,
        "ref": "Art. 24 NIS2-RL",
        "titel": "Nutzung europäischer Cybersicherheitszertifizierung",
        "beschreibung": "Nutzung von Produkten, Diensten und Verfahren der IKT, die im Rahmen europäischer Cybersicherheitszertifizierungsschemata (gem. Cybersecurity Act) zertifiziert sind.",
        "hinweise": "Nachweise: Zertifizierungsnachweise, Inventar zertifizierter Produkte/Dienste, Beschaffungsrichtlinie.",
    },
    {
        "id": "NIS5-02", "kapitel": "NIS5", "gewichtung": 2,
        "ref": "Art. 25 NIS2-RL",
        "titel": "Normen und technische Spezifikationen",
        "beschreibung": "Berücksichtigung europäischer und internationaler Normen (ISO/IEC 27001, ETSI EN-Normen) sowie technischer Spezifikationen bei der Umsetzung der Sicherheitsmaßnahmen.",
        "hinweise": "Nachweise: ISO 27001-Zertifikat oder Zertifizierungsplanung, Normenmapping, Compliance-Berichte.",
    },
    {
        "id": "NIS5-03", "kapitel": "NIS5", "gewichtung": 2,
        "ref": "Art. 24 Abs. 2 NIS2-RL",
        "titel": "Nachweis der Einhaltung für wesentliche Einrichtungen",
        "beschreibung": "Wesentliche Einrichtungen müssen auf Anfrage der Behörden die Einhaltung der Sicherheitsanforderungen durch Zertifizierungen oder regelmäßige Audits nachweisen.",
        "hinweise": "Nachweise: Zertifizierungsberichte (ISO 27001, BSI IT-Grundschutz), externe Audit-Berichte, Self-Assessment.",
    },
    {
        "id": "NIS5-04", "kapitel": "NIS5", "gewichtung": 3,
        "ref": "Art. 26 NIS2-RL",
        "titel": "Registrierung bei der zuständigen Behörde",
        "beschreibung": "Einrichtungen müssen sich bei der zuständigen nationalen Behörde (Deutschland: BSI) registrieren und relevante Informationen übermitteln.",
        "hinweise": "Nachweise: Registrierungsnachweis beim BSI, aktuelle Registrierungsdaten, Ansprechpartner-Dokumentation.",
    },
    {
        "id": "NIS5-05", "kapitel": "NIS5", "gewichtung": 2,
        "ref": "Art. 32–33 NIS2-RL",
        "titel": "Zusammenarbeit mit Aufsichtsbehörden",
        "beschreibung": "Kooperation mit den zuständigen Behörden bei Aufsichtsmaßnahmen, Vor-Ort-Prüfungen und der Bereitstellung von Informationen.",
        "hinweise": "Nachweise: Kommunikationshistorie mit BSI, Reaktionsplan für Behördenanfragen, interne Ansprechpartner.",
    },
]

_STANDARD_IDS: frozenset[str] = frozenset(r["id"] for r in NIS2_ANFORDERUNGEN)


def anforderungen_by_kapitel() -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {k: [] for k in KAPITEL}
    for req in NIS2_ANFORDERUNGEN:
        result[req["kapitel"]].append(req)
    return result


def load_merged_anforderungen(db_path: "Path | None" = None) -> list[dict]:
    """Gibt den vollständigen Anforderungskatalog zurück, mit _quelle-Tag pro Eintrag."""
    base: dict[str, dict] = {
        r["id"]: dict(r, _quelle="standard") for r in NIS2_ANFORDERUNGEN
    }

    if db_path is not None:
        try:
            from nis2.db import load_custom_anforderungen
            for custom in load_custom_anforderungen(db_path):
                rid = custom["id"]
                quelle = "override" if custom.get("ist_override") else "custom"
                base[rid] = {
                    "id": rid,
                    "kapitel": custom["kapitel"],
                    "ref": custom["ref"],
                    "titel": custom["titel"],
                    "beschreibung": custom["beschreibung"],
                    "hinweise": custom["hinweise"],
                    "gewichtung": int(custom["gewichtung"]),
                    "_quelle": quelle,
                }
        except Exception:
            pass

    kap_order = {k: i for i, k in enumerate(KAPITEL)}
    return sorted(base.values(), key=lambda r: (kap_order.get(r.get("kapitel", "NIS5"), 99), r["id"]))


def berechne_reifegrad(
    bewertungen: dict[str, dict],
    anforderungen: list[dict],
) -> dict[str, Any]:
    gesamt_punkte = 0
    max_punkte = 0
    kapitel_scores: dict[str, dict[str, Any]] = {k: {"punkte": 0, "max": 0, "anzahl": 0, "bewertet": 0} for k in KAPITEL}

    for req in anforderungen:
        kid = req["kapitel"]
        gew = int(req.get("gewichtung", 1))
        bew = bewertungen.get(req["id"], {})
        wert = int(bew.get("bewertung", 0))

        max_punkte += 5 * gew
        gesamt_punkte += wert * gew
        if kid in kapitel_scores:
            kapitel_scores[kid]["max"] += 5 * gew
            kapitel_scores[kid]["punkte"] += wert * gew
            kapitel_scores[kid]["anzahl"] += 1
            if wert > 0:
                kapitel_scores[kid]["bewertet"] += 1

    prozent = round(gesamt_punkte / max_punkte * 100, 1) if max_punkte > 0 else 0.0

    for kid, ks in kapitel_scores.items():
        ks["prozent"] = round(ks["punkte"] / ks["max"] * 100, 1) if ks["max"] > 0 else 0.0

    luecken = [
        req for req in anforderungen
        if int(bewertungen.get(req["id"], {}).get("bewertung", 0)) <= 2
    ]
    luecken.sort(key=lambda r: (int(bewertungen.get(r["id"], {}).get("bewertung", 0)), -int(r.get("gewichtung", 1))))

    return {
        "gesamt_punkte": gesamt_punkte,
        "max_punkte": max_punkte,
        "prozent": prozent,
        "kapitel_scores": kapitel_scores,
        "luecken": luecken,
    }
