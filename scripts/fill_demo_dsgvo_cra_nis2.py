from __future__ import annotations

import sqlite3


DEMO_NAMES = ["Demokunde", "Demoprojekt"]


def _customer_row(name: str):
    con = sqlite3.connect("data/db/firmen.sqlite")
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM firmen WHERE name=?", (name,)).fetchone()
    con.close()
    return row


def _company_defaults(name: str) -> tuple[str, str]:
    row = _customer_row(name)
    if row is None:
        return ("Demo GmbH", "")
    keys = set(row.keys())
    unternehmen = row["unternehmen"] if "unternehmen" in keys else ""
    berater = row["berater"] if "berater" in keys else ""
    return ((unternehmen or "Demo GmbH"), (berater or ""))


def fill_dsgvo() -> None:
    ratings: dict[str, tuple[int, str, str]] = {
        "GDS1-01": (4, "Grundsaetze sind in Policies und Prozessen verankert; Umsetzung weitgehend konsistent.", "Stichprobenkontrollen und Nachweise vereinheitlichen."),
        "GDS1-02": (4, "Zwecke sind je Prozess dokumentiert, Aenderungen werden meist im Ticketing nachgezogen.", "Regelmaessiger Review-Zyklus fuer Zweckbindung."),
        "GDS1-03": (3, "Datenminimierung wird beachtet, aber nicht in allen Fachprozessen systematisch geprueft.", "Checkliste als Pflicht-Gate in Projekten etablieren."),
        "GDS1-04": (3, "Korrekturen sind moeglich, Datenqualitaet wird teils manuell abgesichert.", "Datenqualitaetsregeln und Verantwortliche pro System definieren."),
        "GDS1-05": (2, "Loeschkonzept existiert nur fuer Kernsysteme, Rand-/SaaS-Systeme uneinheitlich.", "Loesch- und Aufbewahrungsplan zentral erstellen und umsetzen."),
        "GDS1-06": (4, "Zugriffsschutz, MFA, Verschluesselung und Logging sind weitgehend umgesetzt.", "Wirksamkeitsnachweise (KPI/Reports) regelmaessig sammeln."),
        "GDS1-07": (3, "Accountability ist grundsaetzlich bekannt, Nachweisfuehrung nicht durchgaengig.", "Evidenzablage und Verantwortlichkeiten (RACI) schaerfen."),
        "GDS1-08": (4, "Rechtsgrundlagen werden im VVT erfasst und bei neuen Prozessen geprueft.", "Turnusmaessige Revalidierung einplanen."),
        "GDS1-09": (3, "Web-Consent ist technisch abgedeckt; Offline/Vertrieb teils manuell.", "Einheitliches Einwilligungsregister fuer alle Kanaele."),
        "GDS1-10": (3, "Besondere Kategorien kommen selten vor; Schutzmassnahmen vorhanden, Kennzeichnung lueckenhaft.", "Klassifizierung/Markierung in Systemen nachziehen."),
        "GDS2-01": (4, "Datenschutzhinweise sind veroeffentlicht und meist aktuell.", "Review-Prozess bei Tool-Aenderungen strenger anwenden."),
        "GDS2-02": (3, "DSAR-Prozess ueber Ticketing vorhanden; Systemabfragen teils manuell.", "Systematische Suchprozesse und Vorlagen/QA einfuehren."),
        "GDS2-03": (3, "Loeschung/Berichtigung in Kernsystemen etabliert; Nachweise nicht vollstaendig.", "Loeschprotokolle und Nachweis je System standardisieren."),
        "GDS2-04": (3, "Einschraenkung wird organisatorisch umgesetzt, technische Sperren nicht ueberall.", "Workflow und Systemflags fuer Einschraenkung etablieren."),
        "GDS2-05": (2, "Datenuebertragbarkeit ist bisher nur ad-hoc/teilweise moeglich.", "Exportformate und Prozess fuer relevante Systeme definieren."),
        "GDS2-06": (3, "Widerspruchsprozess existiert; automatisierte Entscheidungen werden selten genutzt.", "Dokumentation und Kommunikation bei Profiling/Automatisierung vervollstaendigen."),
        "GDS3-01": (3, "Datenschutzrollen sind definiert, Governance ist aber nicht komplett formalisiert.", "Regelmaessige Datenschutz-Reviews/Steuerkreis etablieren."),
        "GDS3-02": (3, "Privacy by Design Checklisten existieren, werden aber nicht immer als Gate genutzt.", "Freigabe-Checkpoint im Projektprozess verpflichtend machen."),
        "GDS3-03": (2, "Gemeinsame Verantwortlichkeit wird selten behandelt; Vereinbarungen fehlen teilweise.", "Prozess zur Identifikation und Vereinbarung (Art. 26) einfuehren."),
        "GDS3-04": (4, "AVVs sind vorhanden und Dienstleister werden initial geprueft.", "Regelmaessige Re-Evaluierung/Monitoring standardisieren."),
        "GDS3-05": (3, "VVT wird gepflegt, Vollstaendigkeitspruefung nicht streng terminiert.", "Jahresreview und Owner pro Verarbeitung festlegen."),
        "GDS4-01": (4, "Verschluesselung ist fuer Transport und Endgeraete umgesetzt.", "Standards fuer alle Systeme dokumentieren."),
        "GDS4-02": (4, "Zugriffskontrolle/MFA/Logging sind weitgehend umgesetzt.", "Legacy-Ausnahmen reduzieren und rezertifizieren."),
        "GDS4-03": (4, "Backups und Wiederherstellung sind vorhanden; Restore-Tests erfolgen.", "Restore-Tests dokumentiert und regelmaessig planen."),
        "GDS4-04": (3, "Wirksamkeitspruefung durch Scans/Pentests punktuell.", "Kontrollplan und KPIs fuer TOM-Wirksamkeit einfuehren."),
        "GDS4-05": (4, "Mitarbeiterzugriffe sind rollenbasiert, On/Offboarding definiert.", "Rezertifizierung der Rechte konsistent dokumentieren."),
        "GDS5-01": (3, "Meldeprozess existiert, aber 72h-Routine und Uebungen sind ausbaufähig.", "Playbooks/Uebungen und Fristtracking etablieren."),
        "GDS5-02": (3, "Vorlagen existieren, Entscheidungskriterien sind definiert.", "Abstimmung DS/Legal/PR und Nachweise standardisieren."),
        "GDS5-03": (2, "Vorfaelle werden erfasst, aber Dokumentation nicht durchgaengig konsistent.", "Zentrales Incident-Register fuer Datenschutzvorfaelle einfuehren."),
        "GDS5-04": (2, "DSFA wird vereinzelt gemacht, aber nicht systematisch fuer alle Hochrisiko-Prozesse.", "DSFA-Kriterienkatalog und Pflichtprozess implementieren."),
        "GDS5-05": (1, "Vorherige Konsultation wurde bisher nicht durchgefuehrt; Prozess nicht ausgearbeitet.", "Verfahren fuer Konsultation (Art. 36) definieren."),
        "GDS6-01": (4, "DSB ist benannt und erreichbar.", "Vertretungsregelung und Aktualitaet pruefen."),
        "GDS6-02": (3, "Aufgaben sind bekannt, Einbindung fruehzeitig nicht immer nachweisbar.", "Einbindungs- und Reportingprozess formal dokumentieren."),
        "GDS6-03": (3, "Angemessenheitsentscheidungen werden beruecksichtigt.", "Dokumentation im VVT/Transferliste staerken."),
        "GDS6-04": (3, "SCC werden genutzt, TIAs nur fallweise.", "TIA-Standardprozess und Update-Zyklus einfuehren."),
        "GDS6-05": (2, "Compliance Monitoring ist punktuell; Bussgeldrisiken werden nicht regelmaessig bewertet.", "Regelmaessiges Compliance-/Risk-Review mit KPIs etablieren."),
    }

    con = sqlite3.connect("data/db/dsgvo.sqlite")
    q = (
        "INSERT INTO dsgvo_bewertungen (projekt_name, anforderung_id, bewertung, kommentar, massnahme) "
        "VALUES (?,?,?,?,?) "
        "ON CONFLICT(projekt_name, anforderung_id) DO UPDATE SET "
        "bewertung=excluded.bewertung, kommentar=excluded.kommentar, massnahme=excluded.massnahme, updated_at=datetime('now')"
    )
    for proj in DEMO_NAMES:
        unternehmen, berater = _company_defaults(proj)
        con.execute(
            "INSERT OR IGNORE INTO dsgvo_projekte (name, unternehmen, berater) VALUES (?,?,?)",
            (proj, unternehmen, berater),
        )
        for rid, (b, kom, ms) in ratings.items():
            con.execute(q, (proj, rid, int(b), kom, ms))
    con.commit()
    for proj in DEMO_NAMES:
        c = con.execute("SELECT COUNT(*) FROM dsgvo_bewertungen WHERE projekt_name=?", (proj,)).fetchone()[0]
        print("DSGVO", proj, c)
    con.close()


def fill_cra() -> None:
    cra: dict[str, tuple[int, str, str]] = {
        "AI1-01": (4, "Secure-by-design ist im SDLC verankert (Reviews/Threat Modeling), aber nicht durchgaengig formal nachgewiesen.", "SDLC-Nachweise/Checklisten verbindlich machen."),
        "AI1-02": (3, "Release-Checks existieren, aber 'keine bekannten ausnutzbaren Schwachstellen' ist nicht fuer alle Komponenten belegbar.", "Vuln-Management inkl. SLA und Ausnahmeprozess etablieren."),
        "AI1-03": (4, "Sichere Defaults sind umgesetzt; einzelne Legacy-Ausnahmen bestehen.", "Legacy-Defaults reduzieren und Hardening-Guides ergaenzen."),
        "AI1-04": (4, "TLS/Encryption ist weitgehend umgesetzt; Key-Management ist nicht ueberall gleich dokumentiert.", "Key-Management Standards konsolidieren."),
        "AI1-05": (4, "Integritaet wird teilweise ueber Checks/Signaturen abgesichert; nicht fuer alle Artefakte standardisiert.", "Signierung fuer Releases und Updatepakete vereinheitlichen."),
        "AI1-06": (3, "Angriffsoberflaeche wird reduziert; API-/Schnittstelleninventar ist nicht immer aktuell.", "Schnittstelleninventar + regelmaessiger Review."),
        "AI1-07": (3, "Monitoring/Backups existieren; HA/DR fuer alle kritischen Teile ist nicht vollstaendig.", "BCM/DR fuer kritische Komponenten ausbauen."),
        "AI1-08": (4, "Zentrales Logging/Alerting fuer Kernsysteme ist vorhanden; Use-Case Abdeckung nicht vollstaendig.", "Use-Case Katalog + Tuning-Routine einfuehren."),
        "AI1-09": (4, "Patch/Updateprozesse existieren; Third-party Updates sind teils manuell.", "Abhaengigkeitsupdates weiter automatisieren."),
        "AI1-10": (3, "Privacy-by-design wird beachtet, aber nicht als verpflichtendes Release-Gate.", "Privacy Impact Check pro Release einfuehren."),
        "AI2-01": (3, "Schwachstellen werden ueber Scans/Tickets verfolgt; Priorisierung/SLA sind nicht durchgaengig.", "Severity/SLA Regeln + KPI Reporting einfuehren."),
        "AI2-02": (2, "SBOM wird derzeit nur punktuell erzeugt.", "SBOM automatisiert pro Build/Release erzeugen und versionieren."),
        "AI2-03": (3, "Kritische Patches werden zeitnah eingespielt; bei niedrigeren Severities gibt es Rueckstaende.", "Patch-Zyklen definieren und nachhalten."),
        "AI2-04": (3, "Security Tests finden statt, aber nicht strikt release-basiert.", "Release-orientierten Testplan etablieren."),
        "AI2-05": (2, "CVD Prozess ist intern bekannt, aber keine oeffentliche Policy.", "CVD-Policy und security.txt veroeffentlichen."),
        "AI2-06": (2, "Fixes werden kommuniziert, aber keine konsistente oeffentliche Advisories.", "Advisory Template + Prozess definieren."),
        "AI2-07": (3, "Updatemechanismen sind vorhanden; Verifikation/Signierung nicht durchgaengig automatisiert.", "Secure Update Pipeline ausbauen."),
        "AI2-08": (2, "Third-party Komponenten sind bekannt, aber Monitoring/Infoaustausch nicht systematisch.", "Supplier Monitoring/Prozess etablieren."),
        "ART13-01": (3, "Risikobewertungen existieren fuer Kernreleases; nicht fuer alle Produktlinien konsistent.", "Risikobewertung standardisieren und versionieren."),
        "ART13-02": (2, "Technische Doku ist vorhanden; CRA-spezifisches Doku-Paket ist noch nicht strukturiert.", "CRA Doku-Paket/Artefaktliste aufbauen."),
        "ART13-03": (2, "Supportzeitraeume werden kommuniziert, aber nicht formal je Version nachweisbar.", "Support-Policy + EOL Prozess definieren."),
        "ART13-04": (3, "Sicherheitshinweise existieren, aber nicht konsistent je Release.", "Security Notes in Releaseprozess integrieren."),
        "ART13-05": (2, "Marktueberwachungs-Kooperation ist nicht geuebt.", "Kontakt-/Meldeprozess und Rollen definieren."),
        "ART14-01": (2, "ENISA Meldung fuer aktiv ausgenutzte Schwachstellen ist nicht als Prozess etabliert.", "Meldekriterien + Runbook definieren."),
        "ART14-02": (2, "Vorfallsprozess existiert; CRA-spezifische Schwellenwerte/Wege fehlen.", "CRA Incident Klassifizierung + Templates einfuehren."),
        "ART14-03": (2, "Kooperation mit CSIRT/Behoerden wurde nicht regelmaessig getestet.", "Uebungen + Kontaktliste pflegen."),
        "IMPL-01": (4, "Security Verantwortlichkeiten sind definiert.", "Stellvertretungen und formale Mandate dokumentieren."),
        "IMPL-02": (3, "Secure SDLC ist teilweise umgesetzt (Code Review, Scans), aber nicht durchgaengig als Standard nachweisbar.", "Secure SDLC Policies + Gates festschreiben."),
        "IMPL-03": (3, "Lieferkettenpruefungen erfolgen initial, kontinuierliches Monitoring fehlt.", "Supplier Risk Reviews + SBOM/OSV Monitoring etablieren."),
        "IMPL-04": (2, "Produktklassifizierung/Conformity Path ist noch nicht formal dokumentiert.", "Klassifizierungslogik + Konformitaetsweg dokumentieren."),
        "IMPL-05": (2, "Archivierung/Versionierung ist vorhanden, aber CRA Artefakte sind nicht vollstaendig definiert.", "Artefaktliste + Aufbewahrungsfristen festlegen."),
        "IMPL-06": (3, "Awareness Schulungen existieren; CRA-spezifische Inhalte fehlen.", "CRA Schulungsmodul in Jahresunterweisung integrieren."),
    }

    con = sqlite3.connect("data/db/cra.sqlite")
    q = (
        "INSERT INTO cra_bewertungen (projekt_name, anforderung_id, bewertung, kommentar, massnahme) "
        "VALUES (?,?,?,?,?) "
        "ON CONFLICT(projekt_name, anforderung_id) DO UPDATE SET "
        "bewertung=excluded.bewertung, kommentar=excluded.kommentar, massnahme=excluded.massnahme, updated_at=datetime('now')"
    )
    for proj in DEMO_NAMES:
        unternehmen, berater = _company_defaults(proj)
        con.execute(
            "INSERT OR IGNORE INTO cra_projekte (name, unternehmen, produkt, produktklasse, berater) VALUES (?,?,?,?,?)",
            (proj, unternehmen, "Demo-Produkt", "default", berater),
        )
        for rid, (b, kom, ms) in cra.items():
            con.execute(q, (proj, rid, int(b), kom, ms))
    con.commit()
    for proj in DEMO_NAMES:
        c = con.execute("SELECT COUNT(*) FROM cra_bewertungen WHERE projekt_name=?", (proj,)).fetchone()[0]
        print("CRA", proj, c)
    con.close()


def fill_nis2() -> None:
    nis2: dict[str, tuple[int, str, str]] = {
        "NIS1-01": (4, "Leitung ist eingebunden (Quartalsreport, Budgetfreigaben), aber nicht alle Entscheidungen sind formal protokolliert.", "Management-Review Protokolle standardisieren."),
        "NIS1-02": (3, "Schulung der Leitung erfolgte punktuell; kein jaehrlicher Nachweis.", "Jahresschulung + Nachweis fuer Leitung einfuehren."),
        "NIS1-03": (3, "Haftungs-/Rollenbewusstsein ist vorhanden, aber Dokumentation/Briefings sind lueckenhaft.", "Briefing-Deck + Nachweis etablieren."),
        "NIS1-04": (3, "Strategie existiert als Security-Roadmap; nicht als formales NIS2 Dokument.", "NIS2 Strategie-Dokument erstellen und versionieren."),
        "NIS1-05": (4, "Rollen/Verantwortlichkeiten sind definiert; Stellvertretungen nicht ueberall.", "Stellvertretungen + Eskalationsmatrix pflegen."),
        "NIS2-01": (3, "Risikoanalyseprozess existiert fuer Kernsysteme; Schatten-IT/Lieferkette weniger integriert.", "Scope erweitern + Review-Zyklus festlegen."),
        "NIS2-02": (3, "Richtlinien sind vorhanden; Versions-/Aenderungsnachweise nicht durchgaengig.", "Policy Lifecycle (Review/Sign-off) standardisieren."),
        "NIS2-03": (3, "Incident Response definiert; Uebungen und Lessons Learned nicht regelmaessig.", "IR Uebungsplan + Postmortems verbindlich machen."),
        "NIS2-04": (3, "Backups/Notfallkontakte vorhanden; BCM/Krisenplan nicht vollstaendig getestet.", "BCM Plan + regelmaessige Tests einfuehren."),
        "NIS2-05": (3, "Security Anforderungen in Beschaffung/Dev vorhanden; Secure SDLC Nachweise nicht komplett.", "Secure SDLC Artefakte (SAST/DAST/SBOM) verpflichten."),
        "NIS2-06": (3, "Wirksamkeit wird punktuell geprueft; kein vollstaendiger Kontrollplan.", "Kontrollplan + KPIs je Control definieren."),
        "NIS2-07": (4, "Cyberhygiene Schulungen jaehrlich; Wirksamkeitsmessung ausbaufähig.", "Quiz/Phishing KPIs in Bericht aufnehmen."),
        "NIS2-08": (4, "Kryptografie ist umgesetzt; Standards nicht fuer alle Systeme dokumentiert.", "Crypto-Standards/Key Mgmt Dokumentation konsolidieren."),
        "NIS2-09": (3, "Personalsicherheit/Access ist definiert; Rezertifizierung nicht konsistent.", "Rezertifizierungsprozess einfuehren."),
        "NIS2-10": (4, "MFA ist fuer Kernsysteme ausgerollt; einzelne Legacy-Ausnahmen.", "Legacy-Ausnahmen abbauen + Nachweise pflegen."),
        "NIS3-01": (3, "Meldepflichten sind bekannt; Prozess selten geuebt.", "Meldeprozess testen und dokumentieren."),
        "NIS3-02": (2, "24h Fruehwarnung ist nicht als fester Ablauf trainiert.", "Runbook + Checkliste fuer 24h Meldung."),
        "NIS3-03": (2, "72h Meldung ist konzeptionell vorhanden, aber Rollen/Artefakte nicht vollstaendig.", "Templates + Verantwortlichkeiten fuer 72h Meldung definieren."),
        "NIS3-04": (2, "Abschlussbericht Prozess ist nicht formalisiert.", "Abschlussbericht Vorlage + Prozess definieren."),
        "NIS3-05": (3, "Benachrichtigung von Empfaengern wird fallweise gemacht.", "Kommunikationsplan + Kriterien standardisieren."),
        "NIS3-06": (3, "Erkennung/Klassifizierung ueber SIEM; Regeln nicht vollstaendig.", "Severity Matrix + Regeln konsolidieren."),
        "NIS4-01": (3, "Lieferantensicherheit initial geprueft; kontinuierliches Monitoring fehlt.", "Supplier Reviews + kritische Lieferantenliste pflegen."),
        "NIS4-02": (2, "Schwachstellen in Lieferkette werden nicht systematisch ueberwacht.", "SBOM/OSV Monitoring fuer Drittkomponenten einfuehren."),
        "NIS4-03": (2, "Koordinierte Lieferkettenbewertung ist nicht etabliert.", "Bewertungsmethodik + Review-Zyklus definieren."),
        "NIS4-04": (3, "Vertragliche Anforderungen existieren fuer Kernlieferanten; nicht fuer alle SaaS.", "Standard-Security-Anhang fuer alle Dienstleister verwenden."),
        "NIS5-01": (2, "Zertifizierungen werden beobachtet, aber nicht genutzt.", "Bewertung ob EU-Zertifizierung sinnvoll ist."),
        "NIS5-02": (3, "Normen werden teilweise angewendet, aber nicht formal nachgewiesen.", "Normen/Controls Mapping dokumentieren."),
        "NIS5-03": (3, "Nachweise koennen punktuell geliefert werden; Sammelpaket fehlt.", "Evidence Pack Prozess aufbauen."),
        "NIS5-04": (2, "Registrierungsvorbereitung vorhanden, aber kein formaler Prozess.", "Registrierungsprozess + Owner definieren."),
        "NIS5-05": (3, "Kooperation mit Behoerden ist konzeptionell; Uebungen fehlen.", "Kontaktliste + Uebung planen."),
    }

    con = sqlite3.connect("data/db/nis2.sqlite")
    q = (
        "INSERT INTO nis2_bewertungen (projekt_name, anforderung_id, bewertung, kommentar, massnahme) "
        "VALUES (?,?,?,?,?) "
        "ON CONFLICT(projekt_name, anforderung_id) DO UPDATE SET "
        "bewertung=excluded.bewertung, kommentar=excluded.kommentar, massnahme=excluded.massnahme, updated_at=datetime('now')"
    )
    for proj in DEMO_NAMES:
        unternehmen, berater = _company_defaults(proj)
        con.execute(
            "INSERT OR IGNORE INTO nis2_projekte (name, unternehmen, einrichtungsklasse, berater) VALUES (?,?,?,?)",
            (proj, unternehmen, "wesentlich", berater),
        )
        for rid, (b, kom, ms) in nis2.items():
            con.execute(q, (proj, rid, int(b), kom, ms))
    con.commit()
    for proj in DEMO_NAMES:
        c = con.execute("SELECT COUNT(*) FROM nis2_bewertungen WHERE projekt_name=?", (proj,)).fetchone()[0]
        print("NIS2", proj, c)
    con.close()


if __name__ == "__main__":
    fill_dsgvo()
    fill_cra()
    fill_nis2()
