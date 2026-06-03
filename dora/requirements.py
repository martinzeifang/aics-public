"""DORA-Anforderungskatalog basierend auf EU 2022/2554 (Digital Operational Resilience Act).

5 Pfeiler:
- ICT-RM (ICT Risk Management, Art. 5-16)
- ICT-IM (ICT-Incident Management, Art. 17-23)
- ICT-RT (Resilience Testing, Art. 24-27)
- ICT-TP (Third-Party Risk Management, Art. 28-44)
- ICT-IS (Information Sharing, Art. 45)

Quellen:
- EU 2022/2554 (DORA-Verordnung)
- BaFin-Leitfaden DORA-Umsetzung
- EBA-Leitlinien zu DORA
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

PFEILER = {
    'ICT-RM': 'ICT Risk Management',
    'ICT-IM': 'ICT Incident Management',
    'ICT-RT': 'Resilience Testing',
    'ICT-TP': 'Third-Party Risk Management',
    'ICT-IS': 'Information Sharing',
}


# Anforderungs-Katalog: ~32 Items
DORA_ANFORDERUNGEN: list[dict[str, Any]] = [

    # ========== Pfeiler 1: ICT Risk Management (Art. 5-16) ==========
    {
        'id': 'ICT-RM-01',
        'pfeiler': 'ICT-RM',
        'ref': 'Art. 5',
        'titel': 'Governance und ICT-Risikomanagement-Verantwortung',
        'beschreibung': 'Das Leitungsorgan trägt die Letztverantwortung für das ICT-Risikomanagement. Klare Rollen und Aufsichtspflichten sind festgelegt.',
        'hinweise': 'Vorstand/Geschäftsführung beschließt ICT-Strategie. Aufsichtsrat überwacht. Mindestens jährliche Berichterstattung.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-RM-02',
        'pfeiler': 'ICT-RM',
        'ref': 'Art. 6',
        'titel': 'ICT-Risikomanagement-Rahmenwerk',
        'beschreibung': 'Dokumentiertes ICT-Risikomanagement-Rahmenwerk inkl. Strategien, Policies, Verfahren und Tools.',
        'hinweise': 'Mindestens jährliche Überprüfung. Anpassung an neue Bedrohungen.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-RM-03',
        'pfeiler': 'ICT-RM',
        'ref': 'Art. 7',
        'titel': 'ICT-Systeme, Protokolle und Werkzeuge',
        'beschreibung': 'Aktuelle, robuste, technisch resiliente ICT-Systeme; Verschlüsselung, MFA, Patching.',
        'hinweise': 'Lifecycle-Management. Regelmäßige Vulnerability-Scans. Asset-Inventar.',
        'gewichtung': 2,
    },
    {
        'id': 'ICT-RM-04',
        'pfeiler': 'ICT-RM',
        'ref': 'Art. 8',
        'titel': 'Identifikation aller ICT-Assets',
        'beschreibung': 'Vollständiges Inventar aller ICT-Assets, Datenflüsse, Konfigurationen und Abhängigkeiten.',
        'hinweise': 'Mindestens jährliche Aktualisierung. Klassifizierung nach Kritikalität.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-RM-05',
        'pfeiler': 'ICT-RM',
        'ref': 'Art. 9',
        'titel': 'Schutz und Prävention',
        'beschreibung': 'Vertraulichkeits-, Integritäts- und Verfügbarkeitsschutz: Zugriffsmanagement, Verschlüsselung, Netzwerksegmentierung.',
        'hinweise': 'Datenklassifizierung. Privileged-Access-Management. Verschlüsselung in Transit und at-rest.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-RM-06',
        'pfeiler': 'ICT-RM',
        'ref': 'Art. 10',
        'titel': 'Erkennung von Anomalien und Vorfällen',
        'beschreibung': 'Mechanismen zur Erkennung anomaler Aktivitäten, einschließlich SIEM, EDR und 24/7-Monitoring.',
        'hinweise': 'Logs zentralisiert. Alert-Schwellen definiert. Cyber-Threat-Intelligence-Quellen abonniert.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-RM-07',
        'pfeiler': 'ICT-RM',
        'ref': 'Art. 11',
        'titel': 'Reaktions- und Wiederherstellungsmaßnahmen',
        'beschreibung': 'Business Continuity Plan und Disaster Recovery Plan; regelmäßige Tests.',
        'hinweise': 'RTO/RPO-Definitionen. Mindestens jährliche BCM-Tests. Crisis-Communication-Plan.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-RM-08',
        'pfeiler': 'ICT-RM',
        'ref': 'Art. 12',
        'titel': 'Backup-Richtlinien und -Verfahren',
        'beschreibung': 'Backup-Strategie inkl. Wiederherstellungsverfahren, Tests und Aufbewahrungsfristen.',
        'hinweise': '3-2-1-Regel. Offline/Air-Gapped-Backups. Wiederherstellungstests dokumentiert.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-RM-09',
        'pfeiler': 'ICT-RM',
        'ref': 'Art. 13',
        'titel': 'Lessons Learned und Weiterentwicklung',
        'beschreibung': 'Strukturierter Prozess zur Auswertung von Vorfällen und kontinuierlichen Verbesserung.',
        'hinweise': 'Post-Mortem-Reviews. Aktualisierung der Pläne. Schulungen ableiten.',
        'gewichtung': 2,
    },
    {
        'id': 'ICT-RM-10',
        'pfeiler': 'ICT-RM',
        'ref': 'Art. 14',
        'titel': 'Krisenkommunikation und Offenlegung',
        'beschreibung': 'Pläne für interne und externe Krisenkommunikation, einschließlich Aufsichtsbehörden, Firmen, Öffentlichkeit.',
        'hinweise': 'Vorlage-Templates. Sprecher festgelegt. Regelmäßige Übungen.',
        'gewichtung': 2,
    },
    {
        'id': 'ICT-RM-11',
        'pfeiler': 'ICT-RM',
        'ref': 'Art. 16',
        'titel': 'Vereinfachtes ICT-Risikomanagement-Rahmenwerk',
        'beschreibung': 'Für kleinere Einrichtungen: vereinfachtes Rahmenwerk gemäß Verhältnismäßigkeitsprinzip.',
        'hinweise': 'Nur relevant für KMU/Mikrofinanz. Selbstdeklaration.',
        'gewichtung': 1,
    },

    # ========== Pfeiler 2: ICT Incident Management (Art. 17-23) ==========
    {
        'id': 'ICT-IM-01',
        'pfeiler': 'ICT-IM',
        'ref': 'Art. 17',
        'titel': 'Incident-Management-Prozess',
        'beschreibung': 'Definierter Prozess zur Erkennung, Bearbeitung und Nachverfolgung von ICT-Vorfällen.',
        'hinweise': 'CSIRT-Team. Eskalationsmatrix. Ticketsystem. Time-to-Detect/Respond gemessen.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-IM-02',
        'pfeiler': 'ICT-IM',
        'ref': 'Art. 18',
        'titel': 'Klassifizierung schwerwiegender ICT-Vorfälle',
        'beschreibung': 'Kriterien zur Klassifizierung schwerwiegender Vorfälle anhand von Schweregrad, Dauer, betroffenen Firmen, Reputation.',
        'hinweise': 'Schwellenwerte definiert. Klassifizierung dokumentiert.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-IM-03',
        'pfeiler': 'ICT-IM',
        'ref': 'Art. 19',
        'titel': 'Reporting an zuständige Behörde',
        'beschreibung': 'Meldung schwerwiegender ICT-Vorfälle an BaFin/Aufsichtsbehörde innerhalb der gesetzlichen Fristen.',
        'hinweise': 'Initial-Meldung 4h, Zwischen-Bericht 72h, Final-Bericht 1 Monat.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-IM-04',
        'pfeiler': 'ICT-IM',
        'ref': 'Art. 19',
        'titel': 'Cyber-Bedrohungs-Notifizierung (freiwillig)',
        'beschreibung': 'Freiwillige Meldung erheblicher Cyber-Bedrohungen, auch ohne tatsächlichen Vorfall.',
        'hinweise': 'Empfohlen für Sektor-übergreifenden Threat-Intelligence.',
        'gewichtung': 1,
    },
    {
        'id': 'ICT-IM-05',
        'pfeiler': 'ICT-IM',
        'ref': 'Art. 20',
        'titel': 'Standardisierung der Reporting-Inhalte',
        'beschreibung': 'Verwendung der durch ESAs vorgegebenen Templates und Klassifizierungs-Schemata.',
        'hinweise': 'EBA-Reporting-Tool. XBRL-Format wo verlangt.',
        'gewichtung': 2,
    },
    {
        'id': 'ICT-IM-06',
        'pfeiler': 'ICT-IM',
        'ref': 'Art. 21',
        'titel': 'Reporting an Firmen und Geschäftspartner',
        'beschreibung': 'Information betroffener Firmen bei Vorfällen, die ihre Interessen tangieren.',
        'hinweise': 'Templates. Datenschutz-konform. DSGVO-Meldung parallel.',
        'gewichtung': 2,
    },

    # ========== Pfeiler 3: Resilience Testing (Art. 24-27) ==========
    {
        'id': 'ICT-RT-01',
        'pfeiler': 'ICT-RT',
        'ref': 'Art. 24',
        'titel': 'Digital Operational Resilience Testing-Programm',
        'beschreibung': 'Strukturiertes Test-Programm mit risikobasiertem Ansatz.',
        'hinweise': 'Mindestens jährlich. Tests aller kritischer ICT-Systeme.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-RT-02',
        'pfeiler': 'ICT-RT',
        'ref': 'Art. 25',
        'titel': 'Vulnerability Assessments und Sicherheitstests',
        'beschreibung': 'Regelmäßige Vulnerability-Scans, Network Security Assessments, Source-Code-Reviews.',
        'hinweise': 'OWASP-Methodik. Quartalsweise Scans. Pen-Tests jährlich.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-RT-03',
        'pfeiler': 'ICT-RT',
        'ref': 'Art. 26-27',
        'titel': 'TLPT (Threat-Led Penetration Testing)',
        'beschreibung': 'Bedrohungsorientierte Penetrationstests gemäß TIBER-EU-Framework für signifikante Anbieter.',
        'hinweise': 'Mindestens alle 3 Jahre. Externe Tester. Aufsichtsbehörde-überwacht.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-RT-04',
        'pfeiler': 'ICT-RT',
        'ref': 'Art. 24',
        'titel': 'Test-Berichte und Lessons Learned',
        'beschreibung': 'Dokumentation aller Tests, Findings, Remediation-Pläne und Re-Tests.',
        'hinweise': 'Findings-Tracking. Closure-Reports. Aufbewahrung 5 Jahre.',
        'gewichtung': 2,
    },

    # ========== Pfeiler 4: Third-Party Risk Management (Art. 28-44) ==========
    {
        'id': 'ICT-TP-01',
        'pfeiler': 'ICT-TP',
        'ref': 'Art. 28',
        'titel': 'TPP-Strategie und Governance',
        'beschreibung': 'Dokumentierte Strategie für ICT-Drittanbieter-Beziehungen, einschließlich Auslagerung.',
        'hinweise': 'Vorstandsfreigabe. Mindestens jährliche Review. Ausstiegsstrategien definiert.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-TP-02',
        'pfeiler': 'ICT-TP',
        'ref': 'Art. 29',
        'titel': 'Konzentrationsrisiko-Bewertung',
        'beschreibung': 'Vor-Vertrags-Bewertung von Konzentrationsrisiken bei TPP-Beziehungen.',
        'hinweise': 'Sektor-weite Anbieter-Übersicht. Mehrere kritische TPP gleicher Kategorie = Risiko.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-TP-03',
        'pfeiler': 'ICT-TP',
        'ref': 'Art. 30',
        'titel': 'Vertragsbedingungen für ICT-TPP',
        'beschreibung': 'Pflicht-Vertragsbedingungen: SLAs, Audit-Rechte, Datenschutz, Exit-Klauseln, Sub-Auslagerung.',
        'hinweise': 'EBA-Mindestanforderungen. Aufsichtszugang. Kündigungsfrist mind. 90 Tage.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-TP-04',
        'pfeiler': 'ICT-TP',
        'ref': 'Art. 28',
        'titel': 'Auslagerungsregister (Register of Information)',
        'beschreibung': 'Aktuelles, vollständiges Register aller ICT-Drittanbieter-Verträge gemäß ESAs-Template.',
        'hinweise': 'XBRL-Format. Quartalsweise Aktualisierung. ESAs-Submission jährlich.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-TP-05',
        'pfeiler': 'ICT-TP',
        'ref': 'Art. 28',
        'titel': 'Pre-Contract Due Diligence',
        'beschreibung': 'Sorgfaltsprüfung vor Vertragsabschluss: Sicherheit, Compliance, Reputation, Geo-Risiken.',
        'hinweise': 'Standardisierte Fragebögen. SOC2-Reports. ISO27001-Zertifikate.',
        'gewichtung': 2,
    },
    {
        'id': 'ICT-TP-06',
        'pfeiler': 'ICT-TP',
        'ref': 'Art. 28',
        'titel': 'Exit-Strategie und Transitionsplanung',
        'beschreibung': 'Dokumentierte Exit-Strategien für jede kritische TPP-Beziehung.',
        'hinweise': 'Daten-Migration. Service-Übergabe. Notfall-Insourcing-Optionen.',
        'gewichtung': 2,
    },
    {
        'id': 'ICT-TP-07',
        'pfeiler': 'ICT-TP',
        'ref': 'Art. 31',
        'titel': 'Identifikation kritischer ICT-TPP',
        'beschreibung': 'Klassifizierung von TPP nach Kritikalität gemäß Aufsichts-Kriterien.',
        'hinweise': 'ESAs-Liste kritischer TPP. Sub-Outsourcing-Ketten.',
        'gewichtung': 3,
    },
    {
        'id': 'ICT-TP-08',
        'pfeiler': 'ICT-TP',
        'ref': 'Art. 32-44',
        'titel': 'Aufsichtsrahmen für kritische TPP',
        'beschreibung': 'Beachtung der direkten ESAs-Aufsicht über kritische TPP. Kooperation mit Lead Overseer.',
        'hinweise': 'Information bei Audits. Empfehlungen umsetzen.',
        'gewichtung': 2,
    },

    # ========== Pfeiler 5: Information Sharing (Art. 45) ==========
    {
        'id': 'ICT-IS-01',
        'pfeiler': 'ICT-IS',
        'ref': 'Art. 45',
        'titel': 'Cyber-Threat-Intelligence-Sharing',
        'beschreibung': 'Teilnahme an Threat-Intelligence-Sharing-Initiativen (z.B. FS-ISAC, BSI-CERT-Bund).',
        'hinweise': 'Memberships. STIX/TAXII-Feeds. Quartalsweise Beiträge.',
        'gewichtung': 1,
    },
    {
        'id': 'ICT-IS-02',
        'pfeiler': 'ICT-IS',
        'ref': 'Art. 45',
        'titel': 'Vertraulichkeitsvereinbarungen für Information-Sharing',
        'beschreibung': 'NDAs und Vertraulichkeitsvereinbarungen für sensitive Bedrohungsinformationen.',
        'hinweise': 'Traffic-Light-Protocol. Personenbezogene Daten ausgeschlossen.',
        'gewichtung': 1,
    },
    {
        'id': 'ICT-IS-03',
        'pfeiler': 'ICT-IS',
        'ref': 'Art. 45',
        'titel': 'Information an Aufsichtsbehörde über Sharing-Aktivitäten',
        'beschreibung': 'Dokumentation und Information der Aufsichtsbehörde über Teilnahme an Sharing-Initiativen.',
        'hinweise': 'Jahres-Bericht. Anlass-bezogene Meldungen.',
        'gewichtung': 1,
    },
]


def anforderungen_by_pfeiler() -> dict[str, list[dict[str, Any]]]:
    """Anforderungen nach Pfeiler gruppiert."""
    result: dict[str, list[dict[str, Any]]] = {p: [] for p in PFEILER}
    for req in DORA_ANFORDERUNGEN:
        result.setdefault(req['pfeiler'], []).append(req)
    return result


def load_merged_anforderungen(db_path: 'Path | None' = None) -> list[dict[str, Any]]:
    """Standard + Custom-Anforderungen merged."""
    if db_path is None:
        db_path = Path('data/db/dora.sqlite')

    from dora.db import load_custom_anforderungen
    custom = load_custom_anforderungen(db_path)
    custom_overrides = {c['id']: c for c in custom if c.get('ist_override')}

    merged = []
    for req in DORA_ANFORDERUNGEN:
        rid = req['id']
        if rid in custom_overrides:
            ov = dict(custom_overrides[rid])
            ov['_quelle'] = 'override'
            merged.append(ov)
        else:
            r = dict(req)
            r['_quelle'] = 'standard'
            merged.append(r)

    # Reine Custom-Anforderungen (kein Override)
    for c in custom:
        if not c.get('ist_override'):
            r = dict(c)
            r['_quelle'] = 'custom'
            merged.append(r)

    return merged


def berechne_reifegrad(
    bewertungen: dict[str, dict[str, Any]],
    anforderungen: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Reifegrad pro Pfeiler + gesamt mit Gewichtung.

    Returns: {gesamt_punkte, max_punkte, prozent, pfeiler_scores, luecken}
    """
    if anforderungen is None:
        anforderungen = DORA_ANFORDERUNGEN

    gesamt_punkte = 0
    max_punkte = 0
    pfeiler_scores: dict[str, dict[str, Any]] = {
        p: {'punkte': 0, 'max': 0, 'anzahl': 0, 'bewertet': 0}
        for p in PFEILER
    }

    for req in anforderungen:
        pfeiler_id = req.get('pfeiler', '')
        gew = int(req.get('gewichtung', 1))
        bew = bewertungen.get(req['id'], {})
        wert = int(bew.get('bewertung', 0))

        max_punkte += 5 * gew
        gesamt_punkte += wert * gew

        if pfeiler_id in pfeiler_scores:
            pfeiler_scores[pfeiler_id]['max'] += 5 * gew
            pfeiler_scores[pfeiler_id]['punkte'] += wert * gew
            pfeiler_scores[pfeiler_id]['anzahl'] += 1
            if wert > 0:
                pfeiler_scores[pfeiler_id]['bewertet'] += 1

    prozent = round(gesamt_punkte / max_punkte * 100, 1) if max_punkte > 0 else 0.0

    for ps in pfeiler_scores.values():
        ps['prozent'] = round(ps['punkte'] / ps['max'] * 100, 1) if ps['max'] > 0 else 0.0

    luecken = [
        req for req in anforderungen
        if int(bewertungen.get(req['id'], {}).get('bewertung', 0)) <= 2
    ]
    luecken.sort(
        key=lambda r: (int(bewertungen.get(r['id'], {}).get('bewertung', 0)),
                       -int(r.get('gewichtung', 1)))
    )

    return {
        'gesamt_punkte': gesamt_punkte,
        'max_punkte': max_punkte,
        'prozent': prozent,
        'pfeiler_scores': pfeiler_scores,
        'luecken': luecken,
    }
