"""Demo-Daten-Generator für BISG-Gerichtsgutachten + Privatgutachten.

Erzeugt 2 Beispiel-Fälle basierend auf der BISG-Übungsaufgabe (Beta-Core v1.0
ERP-Migration mit fehlendem Exception-Handling):

1. Gerichtsgutachten 'GG-2026-DEMO' (LG Musterstadt, X 0815/26)
2. Privatgutachten 'PG-2026-DEMO' (Mandant ACME GmbH, Tauglichkeitsprüfung)

Usage:
    python3 scripts/seed_gerichtsgutachten_demo.py [--db PATH]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Repo-Root in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gutachten import gerichts_db as gdb


def seed_gerichtsgutachten_demo(db_path: Path, name: str = "GG-2026-DEMO") -> str:
    """Erzeugt ein Demo-Gerichtsgutachten basierend auf BISG-Übungsaufgabe."""
    # Falls schon vorhanden, löschen
    gdb.delete_gerichts_projekt(db_path, name)

    gdb.save_gerichts_projekt(
        db_path,
        name=name,
        gutachten_art="gericht",
        gericht="Landgericht Musterstadt",
        kammer="3. Zivilkammer",
        aktenzeichen="X 0815/26",
        klaeger_name="Mittelständischer Großhändler GmbH",
        klaeger_anwalt="RA Dr. Musteranwalt",
        beklagter_name="Softwarehaus AG",
        beklagter_anwalt="RAin Beispielanwalt",
        beweisbeschluss_datum="03.03.2026",
        thema="Überprüfung des relevanten Datenbanksystems der ERP-Software 'Beta-Core v1.0' "
              "auf systematische Migrationsfehler und Datenverlust",
        vertraulichkeit="STRENG VERTRAULICH",
        sv_name="Martin Zeifang",
        sv_zertifizierung="Zertifizierter IT-Sachverständiger (BISG e.V.)",
        sv_anschrift="Finkenweg 42, 89150 Laichingen",
        sv_kontakt="01785412043; martin@zeifang-lai.de",
    )

    # Beweisfragen
    bf1 = gdb.save_beweisfrage(
        db_path, projekt_name=name, nr=1,
        frage_text="Weist das gelieferte Softwaresystem einen technischen Mangel auf?",
        antwort_kurz="ja",
        antwort_text="Ja. Aus informationstechnischer Sicht liegt eine Abweichung vom Stand der "
                     "Technik (ISO/IEC 25010) im Sub-Merkmal Fault Tolerance und Recoverability vor.",
    )
    bf2 = gdb.save_beweisfrage(
        db_path, projekt_name=name, nr=2,
        frage_text="Entspricht das Verhalten des Softwaresystems dem aktuellen Stand der Technik?",
        antwort_kurz="nein",
        antwort_text="Nein. Es fehlen Mechanismen zur Ausnahmebehandlung und transaktionalen "
                     "Isolation. Beide sind in ISO/IEC 25010, OWASP ASVS V7 und BSI CON.8.A21 normiert.",
    )

    # Verfahrensereignisse
    gdb.save_verfahrensereignis(
        db_path, projekt_name=name, ereignis_datum="2026-03-12",
        ereignis_typ="akteneinsicht",
        titel="Auftragsannahme + Akteneinsicht via beA-Portal",
        beschreibung="Befangenheits-Selbstcheck nach § 407a Abs. 1 ZPO: keine Vorbefassung, "
                     "keine Verflechtung. Auftrag angenommen.",
        empfaenger=["Gericht"],
    )
    gdb.save_verfahrensereignis(
        db_path, projekt_name=name, ereignis_datum="2026-03-30",
        ereignis_typ="parteikommunikation",
        titel="Ladung zum Ortstermin (symmetrisch)",
        beschreibung="Beide Parteien + Gericht erhielten gleichlautende Ladung zum 09.04.2026.",
        empfaenger=["Kläger", "Beklagter", "Gericht"],
    )
    gdb.save_verfahrensereignis(
        db_path, projekt_name=name, ereignis_datum="2026-04-09",
        ereignis_typ="ortstermin",
        titel="Ortstermin Hauptsitz Klägerin",
        beschreibung="Asservatsicherung des API-Quellcodes und PostgreSQL-Konfigurations-Dump "
                     "schreibgeschützt nach ISO/IEC 27037. SHA-256 mit Vertretern beider Parteien "
                     "gegengezeichnet. Am Produktivsystem keine Eingriffe.",
        empfaenger=["Kläger", "Beklagter", "Gericht"],
    )
    gdb.save_verfahrensereignis(
        db_path, projekt_name=name, ereignis_datum="2026-04-10",
        ereignis_typ="labor-analyse",
        titel="Beginn Laboruntersuchung (10.04. - 21.04.2026)",
        beschreibung="Werkzeuge: Visual Studio Code 1.95 (statische Analyse), isolierter "
                     "Replay-Test-Host, PostgreSQL-Client 16.2. Fortlaufendes Protokoll.",
        empfaenger=[],
    )

    # Asservaten mit SHA-256
    asset1 = gdb.save_asset(
        db_path, projekt_name=name,
        bezeichnung="API-Quellcode-Auszug (Beta-Core v1.0)",
        sha256="8f3c9a1e4f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c",
        akquisitions_utc="2026-04-09T11:30:00Z",
        akquisitions_ort="Hauptsitz Klägerin, Musterstadt",
        werkzeug_name="hashlib",
        werkzeug_version="3.11",
        parteien_anwesend=["Klägerin (System-Admin Müller)", "Beklagte (Architekt Schmidt)", "Gericht (Geschäftsstelle)"],
        gegengezeichnet_von="System-Admin Herr Müller (Klägerin)",
        bemerkungen="Code-Passage isoliert vor Ort kopiert, Hash vor und nach Übertragung verifiziert.",
        original_dateiname="api_module.py",
    )

    # Befunde (Kap. IV — NUR Tatsachen)
    befund1 = gdb.save_befund(
        db_path, projekt_name=name, nr="4.1",
        titel="Fehlende Mechanismen zur Ausnahmebehandlung im API-Modul",
        beschreibung_text=(
            "Bei künstlicher Unterbrechung der Netzwerkverbindung (3 Wiederholungen) "
            "stürzte die Anwendung jeweils unkontrolliert ab. Im Anschluss wurden in "
            "der Datenbank Teildatensätze ohne zugehörige Header-Records vorgefunden "
            "(orphaned records). Der Quellcode der untersuchten API-Schnittstelle "
            "enthält keine try-catch-Blöcke und keine vergleichbaren Fehlerbehandlungs-"
            "Mechanismen."
        ),
        methode="dynamisch",
        werkzeug_name="Visual Studio Code",
        werkzeug_version="1.95",
        asset_ids=[asset1],
        erhebung_datum="2026-04-12",
        erhebung_ort="Labor",
        zeugen_text="Protokolliert, reproduzierbar durch Drittgutachter",
    )

    befund2 = gdb.save_befund(
        db_path, projekt_name=name, nr="4.2",
        titel="Fehlende Transaktionsprotokolle für DB-Recovery",
        beschreibung_text=(
            "Im untersuchten Quellcode der Datenbank-Anbindung sind keine Mechanismen "
            "zur Generierung von Transaktionsprotokollen (WAL) vorhanden. Nach dem "
            "Crash war keine Wiederherstellung des konsistenten Datenzustands möglich."
        ),
        methode="statisch",
        werkzeug_name="PostgreSQL-Client",
        werkzeug_version="16.2",
        asset_ids=[asset1],
        erhebung_datum="2026-04-15",
        erhebung_ort="Labor",
    )

    # Beurteilungen (Kap. V — Soll/Ist/Kausalität/Würdigung)
    urt1 = gdb.save_beurteilung(
        db_path, projekt_name=name, nr="5.1",
        titel="Verstoß gegen Fault Tolerance (ISO/IEC 25010)",
        befund_ids=[befund1],
        norm_referenz="ISO/IEC 25010 — Reliability/Fault Tolerance + OWASP ASVS V7.4 + BSI CON.8.A21",
        soll_text=(
            "ISO/IEC 25010 verlangt unter Reliability/Fault Tolerance, dass Software "
            "erwartbare Fehler (z.B. transientes Netzwerk-Disconnect) abfängt und nicht "
            "zum Crash führt. OWASP ASVS V7.4 und BSI CON.8.A21 konkretisieren dies "
            "über Exception-Handling, Retries und Circuit-Breaker-Patterns."
        ),
        ist_text=(
            "Befund 4.1 belegt das vollständige Fehlen von try-catch-Blöcken und "
            "vergleichbaren Mechanismen in der API-Schnittstelle. Ein Netzwerk-Timeout "
            "führt systemisch zu einem nicht abgefangenen Laufzeitfehler."
        ),
        kausalitaet_text=(
            "Aus informationstechnischer Sicht ist der unkontrollierte Absturz die "
            "unmittelbare Folge des fehlenden Exception-Handlings. Bei Einhaltung des "
            "anerkannten Stands der Technik wäre der Vorfall vermeidbar gewesen."
        ),
        bewertung_text=(
            "Aus informationstechnischer Sicht liegt eine signifikante Abweichung vom "
            "geschuldeten Stand der Technik vor. Eine 'höhere Gewalt' liegt nicht vor; "
            "Netzwerk-Disconnects sind erwartbare Fehler."
        ),
    )

    urt2 = gdb.save_beurteilung(
        db_path, projekt_name=name, nr="5.2",
        titel="Verstoß gegen Recoverability (ISO/IEC 25010, ACID)",
        befund_ids=[befund2],
        norm_referenz="ISO/IEC 25010 — Reliability/Recoverability + ACID-Prinzip",
        soll_text=(
            "ISO/IEC 25010 verlangt Recoverability auf Funktionsebene. Das ACID-Prinzip "
            "(Atomicity + Durability) ist die technische Konkretisierung für transaktions-"
            "orientierte Systeme. Transaktionsprotokolle (WAL) sind Stand der Technik."
        ),
        ist_text="Befund 4.2 belegt das vollständige Fehlen jeglicher Transaktions-Protokollierung.",
        kausalitaet_text=(
            "Ohne Transaktionsprotokolle ist die Wiederherstellung eines konsistenten "
            "Datenbestands nach Crash technisch ausgeschlossen — daher die orphaned records."
        ),
        bewertung_text=(
            "Aus informationstechnischer Sicht stellt das Fehlen der Recoverability-"
            "Mechanismen einen weiteren Verstoß gegen den anerkannten Stand der Technik dar. "
            "Beide Symptome (Crash + Datenverlust) gehen kausal auf dieselbe Ursache zurück."
        ),
    )

    # Beweisfragen mit Beurteilungs-Verweisen aktualisieren
    gdb.save_beweisfrage(
        db_path, id=bf1, projekt_name=name, nr=1,
        frage_text="Weist das gelieferte Softwaresystem einen technischen Mangel auf?",
        antwort_kurz="ja",
        antwort_text="Ja. Aus informationstechnischer Sicht liegt eine Abweichung vom Stand "
                     "der Technik (ISO/IEC 25010) vor.",
        referenz_beurteilung_ids=[urt1, urt2],
    )
    gdb.save_beweisfrage(
        db_path, id=bf2, projekt_name=name, nr=2,
        frage_text="Entspricht das Verhalten des Softwaresystems dem aktuellen Stand der Technik?",
        antwort_kurz="nein",
        antwort_text="Nein. Es fehlen Mechanismen zur Ausnahmebehandlung und transaktionalen "
                     "Isolation.",
        referenz_beurteilung_ids=[urt1, urt2],
    )

    return name


def seed_privatgutachten_demo(db_path: Path, name: str = "PG-2026-DEMO") -> str:
    """Erzeugt ein Demo-Privatgutachten (Tauglichkeitsprüfung)."""
    gdb.delete_gerichts_projekt(db_path, name)
    gdb.save_gerichts_projekt(
        db_path,
        name=name,
        gutachten_art="privat",
        auftraggeber="ACME GmbH (Beispiel-Auftraggeber)",
        auftrags_art="Tauglichkeitsprüfung",
        auftrags_datum=datetime.now().strftime("%Y-%m-%d"),
        auftrags_nummer="2026-007",
        honorarvereinbarung="650 € pauschaler Tagessatz, max. 3 Tage",
        thema="Tauglichkeitsprüfung des Web-Backends 'AcmePortal v2.5' vor Inbetriebnahme",
        vertraulichkeit="VERTRAULICH",
        sv_name="Martin Zeifang",
        sv_zertifizierung="Zertifizierter IT-Sachverständiger (BISG e.V.)",
        sv_anschrift="Finkenweg 42, 89150 Laichingen",
        sv_kontakt="martin@zeifang-lai.de",
    )

    gdb.save_beweisfrage(
        db_path, projekt_name=name, nr=1,
        frage_text="Erfüllt das System 'AcmePortal v2.5' die Mindest-Sicherheitsanforderungen nach "
                   "OWASP ASVS Level 2?",
    )
    gdb.save_befund(
        db_path, projekt_name=name, nr="4.1",
        titel="Pen-Test-Ergebnis: 2 Mittel-Findings",
        beschreibung_text="Zwei Mittel-Findings nach OWASP ASVS V5 (Input Validation): "
                          "fehlende Input-Sanitization bei /api/search.",
        methode="dynamisch", werkzeug_name="OWASP ZAP", werkzeug_version="2.15",
    )

    return name


def seed_uebung_originalfall(db_path: Path, name: str = "UEB-2026-001") -> str:
    """1:1-Übernahme der BISG-Übungsaufgabe 'Beta-Core v1.0' aus der Schulung
    (siehe 20260522-Übung1_GutachtenMZeifang.odt).

    Inhalt mit allen konkreten Datumsangaben + Asservat-Hash + HTML-formatierten
    Befund/Beurteilungs-Texten (für Test des Rich-Editor + DOCX-Export).
    """
    gdb.delete_gerichts_projekt(db_path, name)

    gdb.save_gerichts_projekt(
        db_path,
        name=name,
        gutachten_art="gericht",
        gericht="Landgericht Musterstadt",
        kammer="3. Zivilkammer",
        aktenzeichen="X 0815/26",
        klaeger_name="Mittelständischer Großhändler",
        klaeger_anwalt="RA Dr. Musteranwalt",
        beklagter_name="Softwarehaus",
        beklagter_anwalt="RAin Beispielanwalt",
        beweisbeschluss_datum="03.03.2026",
        thema=("Überprüfung des relevanten Datenbanksystems der ERP-Software "
               "'Beta-Core v1.0' auf systematische Migrationsfehler und Datenverlust."),
        vertraulichkeit="STRENG VERTRAULICH",
        sv_name="Martin Zeifang",
        sv_zertifizierung="(fast) Zertifizierter IT-Sachverständiger (BISG e.V.)",
        sv_anschrift="Finkenweg 42, 89150 Laichingen",
        sv_kontakt="01785412043; martin@zeifang-lai.de",
    )

    # Beweisfragen
    bf1 = gdb.save_beweisfrage(
        db_path, projekt_name=name, nr=1,
        frage_text="Weist das gelieferte Softwaresystem einen technischen Mangel auf?",
        antwort_kurz="ja",
        antwort_text="Ja. Aus informationstechnischer Sicht weist das System technische Mängel "
                     "in den ISO/IEC 25010-Sub-Merkmalen Fault Tolerance und Recoverability auf.",
    )
    bf2 = gdb.save_beweisfrage(
        db_path, projekt_name=name, nr=2,
        frage_text="Entspricht das Verhalten des Softwaresystems dem aktuellen Stand der Technik?",
        antwort_kurz="nein",
        antwort_text="Nein. Die fehlende Ausnahmebehandlung und Transaktionsprotokollierung sind "
                     "Verstöße gegen ISO/IEC 25010, OWASP ASVS V7 und BSI CON.8.A21.",
    )

    # Verfahrensgang nach Übungsaufgabe (exakte Daten)
    gdb.save_verfahrensereignis(
        db_path, projekt_name=name, ereignis_datum="2026-03-12",
        ereignis_typ="parteikommunikation",
        titel="Auftragsannahme angezeigt nach unverzüglicher Prüfung (§ 407a Abs. 1 ZPO)",
        beschreibung="Vollständige fachliche Zuständigkeit, keine Befangenheitsgründe nach § 406 ZPO.",
        empfaenger=["Gericht"],
    )
    gdb.save_verfahrensereignis(
        db_path, projekt_name=name, ereignis_datum="2026-03-23",
        ereignis_typ="akteneinsicht",
        titel="Akteneinsicht via beA-Portal (23.03. - 27.03.2026)",
        beschreibung="Ausgewertet: Klageschrift, Klageerwiderung, Lastenheft, Pflichtenheft, "
                     "Abnahmeprotokoll vom 28.01.2026.",
        empfaenger=["Gericht"],
    )
    gdb.save_verfahrensereignis(
        db_path, projekt_name=name, ereignis_datum="2026-03-30",
        ereignis_typ="parteikommunikation",
        titel="Ladung zum Ortstermin (gleichlautend, Zwei-Wochen-Frist gewahrt)",
        beschreibung="Symmetrische Korrespondenz an beide Prozessbevollmächtigte und das Gericht.",
        empfaenger=["Kläger", "Beklagter", "Gericht"],
    )
    gdb.save_verfahrensereignis(
        db_path, projekt_name=name, ereignis_datum="2026-04-09",
        ereignis_typ="ortstermin",
        titel="Ortstermin am Hauptsitz der Klägerin",
        beschreibung="Anwesend: Sachverständiger, beide Prozessbevollmächtigte, "
                     "je 1 technischer Vertreter beider Parteien. Asservatsicherung "
                     "schreibgeschützt nach ISO/IEC 27037, SHA-256-Verifikation, "
                     "Gegenzeichnung durch beide Parteien. Keine Eingriffe am Produktivsystem.",
        empfaenger=["Kläger", "Beklagter", "Gericht"],
    )
    gdb.save_verfahrensereignis(
        db_path, projekt_name=name, ereignis_datum="2026-04-10",
        ereignis_typ="labor-analyse",
        titel="Laboruntersuchung 10.04. - 21.04.2026",
        beschreibung="Werkzeuge: Visual Studio Code (statische Codeanalyse), isolierter "
                     "Replay-Test-Host (dynamische Simulation des Netzwerkfehlers), "
                     "PostgreSQL-Client 16.2 (Datenbankstrukturanalyse). Fortlaufende "
                     "Protokollierung für Drittgutachter-Tauglichkeit.",
        empfaenger=[],
    )

    # Asservat mit Original-Hash aus Übungsaufgabe
    asset1 = gdb.save_asset(
        db_path, projekt_name=name,
        bezeichnung="API-Quellcode-Passage (Beta-Core v1.0)",
        sha256="8f3c9a1e4f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c",
        akquisitions_utc="2026-04-09T11:30:00Z",
        akquisitions_ort="Hauptsitz der Klägerin",
        werkzeug_name="hashlib (SHA-256)",
        werkzeug_version="Python 3.11",
        parteien_anwesend=["Klägerin (Sys-Admin Herr Müller)", "Beklagte (Architekt)", "Gericht"],
        gegengezeichnet_von="System-Admin Herr Müller (Klägerin) + Architekt (Beklagte)",
        bemerkungen="Asservat schreibgeschützt erfasst, Hash vor und nach Übertragung verifiziert. "
                    "Im Labor konnte die Code-Passage fehlerfrei extrahiert und analysiert werden.",
        original_dateiname="api_module.py",
    )

    # Befunde — HTML-formatierter Text (für Rich-Editor-Test)
    befund1 = gdb.save_befund(
        db_path, projekt_name=name, nr="4.1",
        titel="Reproduzierbarer Absturz bei transientem Netzwerk-Disconnect",
        beschreibung_text=(
            "<p>Das Verhalten der Datenbank wurde im Labor durch <strong>künstliche Unterbrechung "
            "der Netzwerkverbindung</strong> nachgestellt. Der Versuch wurde <strong>drei Mal "
            "wiederholt</strong>.</p>"
            "<ul>"
            "<li>In jedem Fall stürzte die Anwendung <strong>unkontrolliert</strong> ab.</li>"
            "<li>In jedem Durchlauf erstellte das System keine transaktionale Isolation.</li>"
            "<li>Es wurden ebenfalls <em>Teildatensätze</em> in die Tabellen geschrieben, ohne "
            "die logische Gesamttransaktion ordnungsgemäß zurückzurollen.</li>"
            "</ul>"
            "<p>Die isolierte Code-Passage wurde beim Vor-Ort-Termin in Zusammenarbeit mit dem "
            "Systemadministrator des beklagten Systemhauses, Herrn Müller, vor Ort kopiert und "
            "ein kryptografischer Nachweis (SHA-256-Hashwert: <u>8f3c9a…e4f1</u>) erstellt.</p>"
        ),
        methode="dynamisch",
        werkzeug_name="Visual Studio Code",
        werkzeug_version="1.95",
        asset_ids=[asset1],
        erhebung_datum="10.04.2026 - 12.04.2026",
        erhebung_ort="Labor (isolierter Replay-Test-Host)",
        zeugen_text="Protokolliert, reproduzierbar durch unabhängigen Drittgutachter (DIN EN 16775)",
    )

    befund2 = gdb.save_befund(
        db_path, projekt_name=name, nr="4.2",
        titel="Fehlende Mechanismen zur Ausnahmebehandlung in der API-Schnittstelle",
        beschreibung_text=(
            "<p>Im Zuge der forensischen Analyse konnte bei der Überprüfung des Quellcodes der "
            "API-Schnittstelle festgestellt werden, dass jegliche Mechanismen zur "
            "<strong>Ausnahmebehandlung (try-catch-Blöcke)</strong> fehlen.</p>"
            "<p>Es konnten auch <strong>keine anderen, vergleichbaren Mechanismen</strong> zur "
            "Fehlerkorrektur gefunden werden:</p>"
            "<ul>"
            "<li>keine Retries</li>"
            "<li>keine Circuit-Breaker-Patterns</li>"
            "<li>keine vergleichbaren Resilience-Patterns</li>"
            "</ul>"
        ),
        methode="statisch",
        werkzeug_name="Visual Studio Code",
        werkzeug_version="1.95",
        asset_ids=[asset1],
        erhebung_datum="13.04.2026 - 15.04.2026",
        erhebung_ort="Labor",
    )

    befund3 = gdb.save_befund(
        db_path, projekt_name=name, nr="4.3",
        titel="Fehlende Transaktionsprotokollierung (WAL)",
        beschreibung_text=(
            "<p>Im untersuchten Quellcode der Datenbank-Anbindung sind keine Mechanismen zur "
            "Generierung von Transaktionsprotokollen (Write-Ahead-Log / WAL) vorhanden.</p>"
            "<p>Nach dem Crash war keine Wiederherstellung des konsistenten Datenzustands möglich.</p>"
        ),
        methode="db",
        werkzeug_name="PostgreSQL-Client",
        werkzeug_version="16.2",
        asset_ids=[asset1],
        erhebung_datum="16.04.2026 - 18.04.2026",
        erhebung_ort="Labor",
    )

    # Beurteilungen mit HTML-Formatierung
    urt1 = gdb.save_beurteilung(
        db_path, projekt_name=name, nr="5.1",
        titel="Fault tolerance — Ursache für den Absturz",
        befund_ids=[befund1, befund2],
        norm_referenz="ISO/IEC 25010 — Reliability/Fault Tolerance | OWASP ASVS V7.4 | BSI CON.8.A21",
        soll_text=(
            "<p>Die <strong>ISO/IEC 25010</strong> beschreibt den Stand der Technik. Unter "
            "<u>Reliability/Fault Tolerance</u> wird verlangt, dass Software erwartbare Fehler "
            "(z.B. Netzwerk-Disconnect) abfängt.</p>"
            "<p>Konkretisierungen durch:</p>"
            "<ul>"
            "<li><strong>OWASP ASVS V7.4</strong> 'Error Handling and Logging' — direktes Pendant "
            "zum fehlenden try-catch:"
            "<ul>"
            "<li>V7.4.1: Anwendung wirft generische Fehlermeldungen</li>"
            "<li>V7.4.2: Fehlerbehandlungslogik in der Trust-Boundary</li>"
            "<li>V7.4.3: Kontextuelle und sichere Behandlung unerwarteter Fehler</li>"
            "</ul></li>"
            "<li><strong>BSI IT-Grundschutz CON.8.A21</strong>: Bewährte Programmierregeln anwenden</li>"
            "</ul>"
        ),
        ist_text=(
            "<p>Befund 4.1 und 4.2 belegen das <strong>vollständige Fehlen von try-catch-Blöcken</strong> "
            "und vergleichbaren Mechanismen in der API-Schnittstelle. Ein Netzwerk-Timeout führt "
            "systemisch zu einem nicht abgefangenen Laufzeitfehler.</p>"
        ),
        kausalitaet_text=(
            "<p>Aus informationstechnischer Sicht ist der Absturz die <em>unmittelbare Folge</em> "
            "des fehlenden Exception-Handlings. Ein Netzwerk-Disconnect ist ein <strong>erwartbarer "
            "Fehler</strong>; eine 'höhere Gewalt' liegt nicht vor.</p>"
            "<p>Bei Einhaltung des aktuellen Stands der Technik wäre der Fehler sicher vermeidbar gewesen "
            "(z.B. Pufferung der Daten, Wiederherstellung der Verbindung, Retry).</p>"
        ),
        bewertung_text=(
            "<p>Aus <em>informationstechnischer Sicht</em> liegt eine <strong>signifikante Abweichung "
            "vom geschuldeten Stand der Technik</strong> vor.</p>"
            "<p>Das Fehlen der Sicherheitsfunktionen führte zum Absturz der Software. "
            "Eine 'höhere Gewalt' liegt nicht vor.</p>"
        ),
    )

    urt2 = gdb.save_beurteilung(
        db_path, projekt_name=name, nr="5.2",
        titel="Recoverability — fehlende Wiederherstellbarkeit nach Crash",
        befund_ids=[befund3],
        norm_referenz="ISO/IEC 25010 — Reliability/Recoverability + ACID-Prinzip",
        soll_text=(
            "<p>Die <strong>ISO/IEC 25010-Norm</strong> verlangt <u>Recoverability</u> "
            "(Wiederherstellbarkeit) auf Funktionsebene.</p>"
            "<p>Das <strong>ACID-Prinzip</strong> (Atomicity + Durability) ist die technische "
            "Konkretisierung dieser Forderung für transaktionsorientierte Systeme. "
            "ACID ist Stand der Technik bei SQL-DB-Anbindungen.</p>"
            "<p>Mittels Transaktionsprotokollen müssen Daten, die noch nicht sicher in die Datenbank "
            "geschrieben sind, wiederhergestellt werden können. Erst nach erfolgreichem Backup "
            "der Datenbank dürfen die Transaktionsprotokolle abgeschnitten werden.</p>"
        ),
        ist_text=(
            "<p>Befund 4.3 belegt das <strong>vollständige Fehlen jeglicher Transaktions-"
            "Protokollierung</strong>. Der gesicherte Code hat keinerlei Funktionen zur "
            "Generierung von Transaktionsprotokollen.</p>"
        ),
        kausalitaet_text=(
            "<p>Ohne Transaktionsprotokolle ist die Wiederherstellung eines konsistenten "
            "Datenbestands nach einem Crash <strong>technisch ausgeschlossen</strong> — "
            "daher die in Befund 4.1 dokumentierten <em>orphaned records</em>.</p>"
        ),
        bewertung_text=(
            "<p>Beide Symptome — der unkontrollierte Absturz und die daraus folgenden "
            "Datenbankinkonsistenzen — sind auf eine <strong>einzige technische Ursache</strong> "
            "zurückzuführen: das vollständige Fehlen von Mechanismen zur Ausnahmebehandlung "
            "in der API-Schnittstelle und der fehlenden Recoverability auf DB-Ebene.</p>"
            "<p>Aus informationstechnischer Sicht stellt das Fehlen dieser Recoverability-"
            "Mechanismen einen <strong>Verstoß gegen den anerkannten Stand der Technik</strong> dar. "
            "Dieser Befund erklärt sowohl das Versagen auf der Applikationsschicht (Fault tolerance) "
            "als auch das Ausbleiben eines datenbankbezogenen Rollbacks (Recoverability).</p>"
        ),
    )

    # Beweisfragen mit Beurteilungs-Verweisen aktualisieren
    gdb.save_beweisfrage(
        db_path, id=bf1, projekt_name=name, nr=1,
        frage_text="Weist das gelieferte Softwaresystem einen technischen Mangel auf?",
        antwort_kurz="ja",
        antwort_text="Ja. Es liegt ein technischer Mangel im Sinne von ISO/IEC 25010 vor "
                     "(siehe Beurteilungen 5.1 und 5.2).",
        referenz_beurteilung_ids=[urt1, urt2],
    )
    gdb.save_beweisfrage(
        db_path, id=bf2, projekt_name=name, nr=2,
        frage_text="Entspricht das Verhalten des Softwaresystems dem aktuellen Stand der Technik?",
        antwort_kurz="nein",
        antwort_text="Nein. Beide untersuchten Aspekte (Fault Tolerance und Recoverability) entsprechen "
                     "nicht dem in ISO/IEC 25010, OWASP ASVS V7 und BSI CON.8.A21 normierten "
                     "Stand der Technik.",
        referenz_beurteilung_ids=[urt1, urt2],
    )

    return name


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=Path("data/db/gutachten.sqlite"),
                   help="DB-Pfad (default: data/db/gutachten.sqlite)")
    p.add_argument("--only", choices=["gericht", "privat", "uebung", "alle"], default="alle")
    args = p.parse_args()

    if args.only in ("gericht", "alle"):
        n = seed_gerichtsgutachten_demo(args.db)
        print(f"✓ Gerichtsgutachten angelegt: {n}")
    if args.only in ("privat", "alle"):
        n = seed_privatgutachten_demo(args.db)
        print(f"✓ Privatgutachten angelegt: {n}")
    if args.only in ("uebung", "alle"):
        n = seed_uebung_originalfall(args.db)
        print(f"✓ Übungs-Originalfall angelegt: {n} (mit HTML-formatierten Texten)")
    print(f"\nDB: {args.db.absolute()}")


if __name__ == "__main__":
    main()
