#!/usr/bin/env python3
"""Demo-Daten-Seeder für eine Demoinstanz.

Legt eine zentrale Beispielfirma („Demo AG") an und füllt JEDES web-bediente Modul
(außer Gutachten) mit repräsentativen Demodaten — über die PG-sicheren
``save_*``-DB-Layer-Funktionen (kein direktes sqlite3). Idempotent + je Schritt
fehlertolerant (ein Modul-Fehler stoppt den Rest nicht).

Voraussetzung: ``DATABASE_URL`` zeigt auf das Ziel-Postgres (lokal via
``shared.dev_postgres``; im Container gesetzt). Aufruf:
    PYTHONPATH=/app python scripts/seed_demo.py
"""
from __future__ import annotations

import json
import traceback
from pathlib import Path

DB = lambda stem: Path(f"data/db/{stem}.sqlite")  # noqa: E731
FIRMA = "Demo AG"
BERATER = "Demo Consulting GmbH"

_ok: list[str] = []
_fail: list[str] = []


def step(label: str, fn) -> None:
    try:
        fn()
        _ok.append(label)
        print(f"  ✓ {label}")
    except Exception as exc:  # noqa: BLE001
        _fail.append(f"{label}: {exc!r}")
        print(f"  ✗ {label}: {exc!r}")
        if __import__("os").environ.get("SEED_DEBUG"):
            traceback.print_exc()


# ── CRA / NIS2 / DSGVO Bewertungs-Inhalte (echte Anforderungs-IDs) ───────────
CRA_RATINGS = {
    "AI1-01": (4, "Secure-by-design im SDLC verankert (Reviews/Threat Modeling).", "SDLC-Nachweise verbindlich machen."),
    "AI1-02": (3, "Release-Checks vorhanden, Vuln-Freiheit nicht für alle Komponenten belegbar.", "Vuln-Management inkl. SLA etablieren."),
    "AI1-03": (4, "Sichere Defaults umgesetzt; einzelne Legacy-Ausnahmen.", "Hardening-Guides ergänzen."),
    "AI1-04": (4, "TLS/Encryption weitgehend umgesetzt.", "Key-Management-Standards konsolidieren."),
    "AI1-05": (3, "Integrität teils über Signaturen abgesichert.", "Release-Signierung vereinheitlichen."),
    "AI1-06": (3, "Angriffsoberfläche reduziert; API-Inventar nicht aktuell.", "Schnittstelleninventar + Review."),
    "AI1-08": (4, "Zentrales Logging/Alerting für Kernsysteme.", "Use-Case-Katalog + Tuning."),
    "AI1-09": (4, "Patch-/Updateprozesse vorhanden.", "Abhängigkeitsupdates automatisieren."),
    "AI2-01": (3, "Schwachstellen über Scans/Tickets verfolgt.", "Severity/SLA-Regeln einführen."),
    "AI2-02": (2, "SBOM nur punktuell erzeugt.", "SBOM automatisiert pro Release."),
    "AI2-05": (2, "CVD-Prozess intern bekannt, keine öffentliche Policy.", "CVD-Policy + security.txt veröffentlichen."),
    "ART13-02": (2, "Technische Doku vorhanden; CRA-Doku-Paket unstrukturiert.", "CRA-Artefaktliste aufbauen."),
    "ART14-01": (2, "ENISA-Meldung nicht als Prozess etabliert.", "Meldekriterien + Runbook definieren."),
    "IMPL-01": (4, "Security-Verantwortlichkeiten definiert.", "Mandate dokumentieren."),
    "IMPL-02": (3, "Secure SDLC teilweise umgesetzt.", "Gates festschreiben."),
}
NIS2_RATINGS = {
    "NIS1-01": (4, "Leitung eingebunden (Quartalsreport, Budgetfreigaben).", "Management-Review protokollieren."),
    "NIS1-04": (3, "Strategie als Security-Roadmap, nicht als NIS2-Dokument.", "NIS2-Strategie-Dokument erstellen."),
    "NIS2-01": (3, "Risikoanalyse für Kernsysteme; Lieferkette weniger integriert.", "Scope erweitern."),
    "NIS2-03": (3, "Incident Response definiert; Übungen unregelmäßig.", "IR-Übungsplan verbindlich."),
    "NIS2-04": (3, "Backups/Notfallkontakte vorhanden; BCM nicht getestet.", "BCM-Tests einführen."),
    "NIS2-07": (4, "Cyberhygiene-Schulungen jährlich.", "Phishing-KPIs aufnehmen."),
    "NIS2-10": (4, "MFA für Kernsysteme ausgerollt.", "Legacy-Ausnahmen abbauen."),
    "NIS3-02": (2, "24h-Frühwarnung nicht trainiert.", "Runbook für 24h-Meldung."),
    "NIS3-03": (2, "72h-Meldung konzeptionell, Rollen unvollständig.", "Templates + Verantwortliche."),
    "NIS4-01": (3, "Lieferantensicherheit initial geprüft.", "Kontinuierliches Monitoring."),
    "NIS4-02": (2, "Lieferketten-Schwachstellen nicht überwacht.", "SBOM/OSV-Monitoring."),
    "NIS5-02": (3, "Normen teilweise angewendet.", "Controls-Mapping dokumentieren."),
}
DSGVO_RATINGS = {
    "GDS1-01": (4, "Grundsätze in Policies verankert.", "Stichprobenkontrollen vereinheitlichen."),
    "GDS1-03": (3, "Datenminimierung beachtet, nicht systematisch geprüft.", "Checkliste als Gate."),
    "GDS1-05": (2, "Löschkonzept nur für Kernsysteme.", "Lösch-/Aufbewahrungsplan zentral."),
    "GDS1-06": (4, "Zugriffsschutz, MFA, Verschlüsselung umgesetzt.", "Wirksamkeitsnachweise sammeln."),
    "GDS2-01": (4, "Datenschutzhinweise veröffentlicht und aktuell.", "Review bei Tool-Änderungen."),
    "GDS2-02": (3, "DSAR-Prozess über Ticketing.", "Systematische Suchprozesse."),
    "GDS3-04": (4, "AVVs vorhanden, Dienstleister initial geprüft.", "Re-Evaluierung standardisieren."),
    "GDS4-01": (4, "Verschlüsselung für Transport/Endgeräte.", "Standards dokumentieren."),
    "GDS4-02": (4, "Zugriffskontrolle/MFA/Logging umgesetzt.", "Legacy rezertifizieren."),
    "GDS4-03": (4, "Backups + Restore-Tests vorhanden.", "Restore-Tests dokumentieren."),
    "GDS5-01": (3, "Meldeprozess vorhanden, 72h-Routine ausbaufähig.", "Playbooks/Übungen."),
    "GDS5-04": (2, "DSFA nur vereinzelt.", "DSFA-Pflichtprozess implementieren."),
    "GDS6-01": (4, "DSB benannt und erreichbar.", "Vertretungsregelung prüfen."),
    "GDS6-04": (3, "SCC genutzt, TIAs fallweise.", "TIA-Standardprozess einführen."),
}
AIACT_RATINGS = {
    "AIA-GOV-01": (3, "KI-Governance-Rollen definiert.", "Steuerkreis etablieren."),
    "AIA-GOV-02": (3, "Risikomanagement für KI begonnen.", "Art.-9-Prozess formalisieren."),
    "AIA-DATA-01": (3, "Trainingsdaten dokumentiert.", "Bias-Assessment vertiefen."),
    "AIA-HR-01": (4, "Hochrisiko-Einstufung geprüft.", "Klassifizierung versionieren."),
    "AIA-HR-03": (3, "Technische Doku (Anhang IV) begonnen.", "Doku-Paket vervollständigen."),
    "AIA-HR-05": (3, "Menschliche Aufsicht definiert.", "Interventionsmechanismen testen."),
}
DORA_RATINGS = {
    "ICT-RM-01": (3, "ICT-Risikomanagement-Rahmen etabliert.", "Jährliches Review festlegen."),
    "ICT-IM-01": (3, "Incident-Management-Prozess vorhanden.", "Klassifizierung schärfen."),
    "ICT-IM-02": (2, "Schwerwiegende Vorfälle: Meldewege unklar.", "Meldeprozess an Behörde definieren."),
    "ICT-IS-01": (3, "Resilienz-Tests punktuell.", "Testprogramm aufbauen."),
}


def seed_users() -> None:
    """Optionalen Admin-Account anlegen — NUR aus Env (KEINE Test-User hardcoden).

    Diese Instanz wird extern veröffentlicht und läuft produktiv-ähnlich
    (FLASK_ENV=production). Es werden bewusst KEINE Demo-/Test-Logins erzeugt.
    Ist ``SEED_ADMIN_EMAIL`` + ``SEED_ADMIN_PASSWORD`` gesetzt, wird daraus ein
    Admin angelegt/aktualisiert; sonst übernimmt das Account-Anlegen der Betreiber.
    """
    import os as _os
    email = _os.environ.get("SEED_ADMIN_EMAIL", "").strip()
    pw = _os.environ.get("SEED_ADMIN_PASSWORD", "").strip()
    if not (email and pw):
        print("    (kein SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD → Admin manuell anlegen)")
        return
    from server.auth import users_db as u
    u.ensure_db()
    existing = u.get_user_by_email(email)
    if existing and existing.get("id"):
        u.update_user(existing["id"], password=pw, roles=["admin"])
    else:
        u.create_user(email=email, password=pw, roles=["admin"], display_name="Administrator")


def seed_firmen() -> None:
    from firmen import db as m
    m.ensure_db(DB("firmen"))
    m.save_firma(DB("firmen"), name=FIRMA, unternehmen=FIRMA,
                 beschreibung="Beispielfirma der Demoinstanz — Cross-Modul-Compliance.",
                 berater=BERATER)


def _bewertungen(modul, save_projekt_kw, ratings, proj_name):
    from importlib import import_module
    m = import_module(f"{modul}.db")
    m.ensure_db(DB(modul))
    m.save_projekt(DB(modul), **save_projekt_kw)
    for rid, (b, kom, ms) in ratings.items():
        m.save_bewertung(DB(modul), projekt_name=proj_name,
                         anforderung_id=rid, bewertung=int(b), kommentar=kom, massnahme=ms)


def seed_cra() -> None:
    from cra import db as m
    _bewertungen("cra", dict(name="Demo CRA", unternehmen=FIRMA, produkt="Demo-Gateway",
                             produktklasse="default", beschreibung="CRA-Konformitätsbewertung",
                             berater=BERATER), CRA_RATINGS, "Demo CRA")
    step("cra: Schwachstelle", lambda: m.save_vuln(DB("cra"), projekt_name="Demo CRA", data={
        "cve_id": "CVE-2024-31337", "titel": "Demo OpenSSL-Schwachstelle", "schwere": "high",
        "cvss_score": 7.5, "affected_component": "openssl 3.0.1", "status": "open"}))
    step("cra: Schwachstelle 2", lambda: m.save_vuln(DB("cra"), projekt_name="Demo CRA", data={
        "cve_id": "CVE-2025-0420", "titel": "Demo libcurl Use-after-free", "schwere": "medium",
        "cvss_score": 5.9, "affected_component": "libcurl 8.5.0", "status": "triaging"}))
    step("cra: SBOM", lambda: m.save_sbom(DB("cra"), projekt_name="Demo CRA", data={
        "release_version": "1.0.0", "sbom_format": "CycloneDX", "komponenten_count": 128,
        "lizenzen": ["MIT", "Apache-2.0", "BSD-3-Clause"], "quelle": "CI-Pipeline"}))


def seed_nis2() -> None:
    from nis2 import db as m
    _bewertungen("nis2", dict(name="Demo NIS2", unternehmen=FIRMA, einrichtungsklasse="wesentlich",
                              beschreibung="NIS2-Reifegradbewertung", berater=BERATER),
                 NIS2_RATINGS, "Demo NIS2")
    step("nis2: Asset", lambda: m.save_asset(DB("nis2"), "Demo NIS2", {
        "asset_name": "Kern-Datenbankserver", "asset_typ": "it", "kritikalitaet": "kritisch",
        "schutzbedarf_v": 3, "schutzbedarf_i": 3, "schutzbedarf_a": 3}))
    step("nis2: Lieferant", lambda: m.save_vendor(DB("nis2"), "Demo NIS2", {
        "vendor_name": "Cloud-Hoster Demo", "leistung": "IaaS", "kritikalitaet": "hoch"}))


def seed_ai_act() -> None:
    from ai_act import db as m
    m.ensure_db(DB("ai_act"))
    m.save_projekt(DB("ai_act"), name="Demo AI Act", organisation=FIRMA, produkt="Demo-Scoring-KI",
                   beschreibung="EU-AI-Act-Konformität (Hochrisiko)")
    for rid, (b, kom, ms) in AIACT_RATINGS.items():
        m.save_bewertung(DB("ai_act"), projekt_name="Demo AI Act", anforderung_id=rid,
                         bewertung=int(b), kommentar=kom, massnahme=ms)
    step("ai_act: System-Doku", lambda: m.save_system_doku(DB("ai_act"), "Demo AI Act", {
        "system_name": "Demo-Scoring-KI", "version": "1.2", "provider": FIRMA,
        "intended_purpose": "Bonitätsbewertung", "architecture": "Gradient-Boosting + Feature-Store"}))


def seed_dsgvo() -> None:
    from dsgvo import db as m
    _bewertungen("dsgvo", dict(name="Demo DSGVO", unternehmen=FIRMA,
                               beschreibung="DSMS-Reifegrad", berater=BERATER),
                 DSGVO_RATINGS, "Demo DSGVO")
    step("dsgvo: VVT", lambda: m.save_vvt(DB("dsgvo"), "Demo DSGVO", {
        "vvt_id": "VVT-001", "name": "Kundenverwaltung", "zweck": "Vertragsabwicklung",
        "rechtsgrundlage": "Art. 6 Abs. 1 lit. b", "betroffene_kategorien": "Kunden",
        "datenkategorien": "Name, E-Mail, Adresse", "rolle": "verantwortlicher"}))
    step("dsgvo: TOM", lambda: m.save_tom(DB("dsgvo"), "Demo DSGVO", {
        "kategorie": "zutrittskontrolle", "massnahme": "Badge-Zutritt Rechenzentrum",
        "beschreibung": "Physischer Zugang nur mit Badge + Protokollierung", "umsetzungsstatus": "umgesetzt"}))


def seed_risikobewertung() -> None:
    from risikobewertung import db as m
    m.save_projekt(DB("risikobewertung"), name="Demo Risikobewertung", framework="STRIDE",
                   beschreibung="Bedrohungsanalyse Demo-Gateway", unternehmen=FIRMA, berater=BERATER)
    for i, (nm, lab, wert) in enumerate([
        ("Spoofing der Admin-Schnittstelle", "hoch", 12),
        ("Tampering an Update-Paketen", "mittel", 8),
        ("Denial of Service am API-Gateway", "mittel", 9)], start=1):
        m.save_risiko(DB("risikobewertung"), {
            "projekt_name": "Demo Risikobewertung", "nr": i, "risk_name": nm,
            "beschreibung": f"Demo-Risiko: {nm}", "framework": "STRIDE",
            "risikowert": wert, "risiko_label": lab})


def seed_dora() -> None:
    from dora import db as m
    m.ensure_db(DB("dora"))
    m.save_projekt(DB("dora"), name="Demo DORA", unternehmen=FIRMA,
                   finanzeinrichtung_klasse="bank", beschreibung="DORA-Resilienz", berater=BERATER)
    for rid, (b, kom, ms) in DORA_RATINGS.items():
        m.save_bewertung(DB("dora"), projekt_name="Demo DORA", anforderung_id=rid,
                         bewertung=int(b), kommentar=kom, massnahme=ms)
    step("dora: TPP", lambda: m.save_tpp(DB("dora"), projekt_name="Demo DORA", tpp={
        "name": "Cloud-Hoster Demo", "kategorie": "cloud", "kritisch": 1, "status": "aktiv"}))


def seed_wiba() -> None:
    from wiba import db as m
    m.ensure_db(DB("wiba"))
    m.save_projekt(DB("wiba"), name="Demo WiBA", unternehmen=FIRMA,
                   beschreibung="BSI WiBA — Weg in die Basis-Absicherung", berater=BERATER)
    # Demo-Katalog NUR wenn leer (echten BSI-Katalog niemals überschreiben).
    # Generische Platzhalter-Prüffragen (kein BSI-Originaltext, Copyright).
    if m.catalog_meta(DB("wiba")).get("anzahl_prueffragen", 0) == 0:
        themen = [
            {"theme_key": "orga", "titel": "Organisation & Verantwortung", "reihenfolge": 1,
             "ziel": "Demo-Thema: Rollen und Verantwortlichkeiten für IT-Sicherheit."},
            {"theme_key": "datensicherung", "titel": "Datensicherung", "reihenfolge": 2,
             "ziel": "Demo-Thema: regelmäßige Backups und Wiederherstellung."},
        ]
        prueffragen = [
            {"control_id": "orga-1", "theme_key": "orga", "nr": 1,
             "frage": "Demo: Sind Verantwortlichkeiten für IT-Sicherheit benannt?"},
            {"control_id": "orga-2", "theme_key": "orga", "nr": 2,
             "frage": "Demo: Gibt es eine Leitlinie zur Informationssicherheit?"},
            {"control_id": "datensicherung-1", "theme_key": "datensicherung", "nr": 1,
             "frage": "Demo: Werden regelmäßig Datensicherungen erstellt?"},
            {"control_id": "datensicherung-2", "theme_key": "datensicherung", "nr": 2,
             "frage": "Demo: Wird die Wiederherstellung der Backups getestet?"},
        ]
        m.replace_catalog(DB("wiba"), themen, prueffragen, version="demo", quelle="Demo-Seed")
        for cid, status in [("orga-1", "ja"), ("orga-2", "nein"), ("datensicherung-1", "ja")]:
            try:
                m.save_antwort(DB("wiba"), "Demo WiBA", cid, status=status,
                               notiz="Demo-Antwort")
            except Exception:
                pass


def seed_soc() -> None:
    from soc import db as m
    m.ensure_db(DB("soc"))
    step("soc: Verbindung", lambda: m.save_connection(
        DB("soc"), name="default", modus="pull", url="https://wazuh-indexer.demo.local:9200",
        username="demo-reader"))
    step("soc: Asset", lambda: m.upsert_asset(DB("soc"), {
        "agent_id": "001", "agent_name": "web-01", "hostname": "web-01.demo.local",
        "organisation": FIRMA, "kritikalitaet": 4, "umgebung": "prod"}))
    step("soc: Incident", lambda: m.create_incident(
        DB("soc"), titel="Demo: Verdächtige Anmeldung", severity="medium",
        agent_name="web-01", beschreibung="Mehrfache fehlgeschlagene Logins (Demo)."))


def main() -> int:
    print(f"== Demo-Seed fuer Firma {FIRMA} ==")
    # Module mit eigenem step()-internem Logging rufen ihre Sub-steps selbst;
    # die Projekt-/Firmen-Anlage wird hier je Modul gekapselt.
    step("users: Demo-Logins", seed_users)
    step("firmen: Firma", seed_firmen)
    step("cra: Projekt + Bewertungen", seed_cra)
    step("nis2: Projekt + Bewertungen", seed_nis2)
    step("ai_act: Projekt + Bewertungen", seed_ai_act)
    step("dsgvo: Projekt + Bewertungen", seed_dsgvo)
    step("risikobewertung: Projekt + Risiken", seed_risikobewertung)
    step("dora: Projekt + Bewertungen", seed_dora)
    step("wiba: Projekt", seed_wiba)
    step("soc: Verbindung/Asset/Incident", seed_soc)

    # firmen_id-Verknüpfung über alle Module
    def link():
        from shared.firmen_link import backfill_firmen_ids
        for stem, table, col in [
            ("cra", "cra_projekte", "unternehmen"), ("nis2", "nis2_projekte", "unternehmen"),
            ("ai_act", "ai_act_projekte", "organisation"), ("dsgvo", "dsgvo_projekte", "unternehmen"),
            ("risikobewertung", "rb_projekte", "unternehmen"), ("dora", "dora_projekte", "unternehmen"),
            ("wiba", "wiba_projekte", "unternehmen")]:
            try:
                backfill_firmen_ids(DB(stem), table=table, name_col=col, firmen_db=DB("firmen"))
            except Exception as exc:  # noqa: BLE001
                print(f"    (firmen-link {stem}: {exc!r})")
    step("firmen-link: backfill", link)

    print(f"\n== Fertig: {len(_ok)} ok, {len(_fail)} Fehler ==")
    for f in _fail:
        print("  ! " + f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
