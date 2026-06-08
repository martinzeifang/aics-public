"""G-Hilfe — Kontextuelle Hilfetexte basierend auf BISG-Schulungsunterlagen.

Quelle: BISG_Zusammenfassung Tag 1 (Folien 1-80) + Tag 2 (Folien 81-122) +
Übungsaufgabe Software-Qualität.

Jeder Key liefert ein Dict mit:
- title: Kurzer Titel
- norm: Norm-/ZPO-Bezug
- was: Was die Norm verlangt
- fallstrick: Typischer Fallstrick
- beispiel: Beispiel-Formulierung oder -Verfahren
"""
from __future__ import annotations

from typing import Any


HELP: dict[str, dict[str, str]] = {
    # ───────────────────── Selbstcheck (G2-1, § 406 ZPO) ─────────────────────
    "selbstcheck.wirtschaftlich": {
        "title": "Wirtschaftliche Verflechtung",
        "norm": "§ 406 ZPO — Befangenheitsgründe",
        "was": "Beteiligungen, Aufträge oder finanzielle Beziehungen zu einer "
               "Verfahrenspartei begründen die Besorgnis der Befangenheit.",
        "fallstrick": "Auch indirekte Verflechtungen (Konzernverbindung, "
                      "Tochtergesellschaften) zählen. Bei Zweifel offenlegen.",
        "beispiel": "Sie waren in den letzten 24 Monaten als Berater für die "
                    "Klägerin tätig → ablehnen nach § 407 Abs. 2 ZPO.",
    },
    "selbstcheck.familiaer": {
        "title": "Persönliche/familiäre Nähe",
        "norm": "§ 406 i.V.m. § 41 ZPO",
        "was": "Verwandtschaft bis 3. Grades, Ehe, Partnerschaft, enge "
               "Freundschaft zu Parteien, Anwälten oder Zeugen begründen Befangenheit.",
        "fallstrick": "Auch nicht-juristische Nähebeziehungen (Vereinskollege, "
                      "Geschäftspartner) können relevant sein.",
        "beispiel": "Der Geschäftsführer der Beklagten ist Ihr Cousin → ablehnen.",
    },
    "selbstcheck.vorbefassung": {
        "title": "Vorbefassung im selben Sachverhalt",
        "norm": "§ 406 ZPO + DIN EN 16775",
        "was": "Wer den Sachverhalt vorher als Berater, Entwickler oder Projektleiter "
               "bearbeitet hat, darf nicht als SV agieren.",
        "fallstrick": "Auch Audit-Berichte zum gleichen System aus der Vergangenheit "
                      "können Vorbefassung begründen (vgl. G0-9 Befangenheits-Check).",
        "beispiel": "Sie haben vor 2 Jahren ein Compliance-Audit für die Klägerin "
                    "über genau dieses ERP-System erstellt → ablehnen.",
    },
    "selbstcheck.social_media": {
        "title": "Social Media + Befangenheit",
        "norm": "§ 406 ZPO (aktuelle Rechtsprechung 2026)",
        "was": "Pointierte oder einseitige Äußerungen auf LinkedIn, X oder anderen "
               "Netzwerken zu Beteiligten oder zum Sachverhalt können Befangenheits-"
               "anträge auslösen.",
        "fallstrick": "Folge: Ablehnung + Verlust des Honoraranspruchs nach JVEG.",
        "beispiel": "LinkedIn-Post 'Solche Softwarehäuser gehören abgestraft' bei "
                    "anhängigem Verfahren → Befangenheitsantrag erfolgreich.",
    },
    "selbstcheck.kompetenz": {
        "title": "Eigene fachliche Kompetenz",
        "norm": "§ 407 Abs. 2 ZPO — Persönliche Leistungserbringung",
        "was": "Der SV muss die 'besondere Sachkunde' für die Beweisfragen besitzen. "
               "Mangelnde Kompetenz → unverzügliche Anzeige an Gericht.",
        "fallstrick": "Persönliche Leistungserbringung ist nicht delegierbar — "
                      "auch nicht an KI (§ 407a + § 839a BGB Haftungsdurchgriff).",
        "beispiel": "Sie sind IT-SV, aber das Verfahren benötigt Embedded-Hardware-"
                    "Reverse-Engineering → ablehnen, ggf. Unter-SV vorschlagen.",
    },

    # ───────────────────── Deckblatt ─────────────────────
    "deckblatt.gericht": {
        "title": "Gericht + Kammer",
        "norm": "DIN EN 16775 — Berichtsstruktur",
        "was": "Exakte Bezeichnung der gerichtlichen Stelle (z.B. 'Landgericht "
               "Musterstadt, 3. Zivilkammer').",
        "fallstrick": "Kammer NICHT abkürzen ('3. ZK' statt '3. Zivilkammer').",
        "beispiel": "Landgericht Stuttgart, 17. Zivilkammer (Handelssachen)",
    },
    "deckblatt.aktenzeichen": {
        "title": "Aktenzeichen",
        "norm": "ZPO formell",
        "was": "Vollständiges AZ wie im Beweisbeschluss benannt (Kammer-Buchstabe + "
               "fortlaufende Nr / Jahr).",
        "fallstrick": "Im Footer jedes Berichts wiederholen → Verwechslungsschutz.",
        "beispiel": "X 0815/26 oder 17 O 4711/26",
    },
    "deckblatt.beweisbeschluss_datum": {
        "title": "Beweisbeschluss vom",
        "norm": "ZPO § 404",
        "was": "Datum, an dem das Gericht den SV bestellt hat (NICHT das Datum der "
               "Auftragsannahme durch den SV).",
        "fallstrick": "Tagesgenau, im deutschen Format DD.MM.YYYY.",
        "beispiel": "03.03.2026",
    },
    "deckblatt.auftraggeber": {
        "title": "Auftraggeber (Privatgutachten)",
        "norm": "Werkvertragsrecht + Standesrecht BISG",
        "was": "Vollständige Bezeichnung des Auftraggebers (Privatperson, Firma, "
               "RA-Kanzlei).",
        "fallstrick": "Bei RA-Kanzlei als Auftraggeber → Mandanten-Bezeichnung "
                      "im Thema nennen.",
        "beispiel": "ACME GmbH, vertreten durch Geschäftsführer Herr Müller",
    },
    "deckblatt.auftrags_art": {
        "title": "Auftragsart (Privatgutachten)",
        "norm": "Standesrecht BISG",
        "was": "Klare Bezeichnung der Auftragsart — definiert Umfang und Bewertungs-"
               "tiefe.",
        "fallstrick": "Privatgutachten ist KEIN gerichtliches Beweismittel — der "
                      "SV muss die eingeschränkte Unparteiischheit dokumentieren.",
        "beispiel": "Beweissicherung / Tauglichkeitsprüfung / Schaden-Gutachten / "
                    "Wertgutachten / Kaufberatung",
    },

    # ───────────────────── Beweisfragen (Kap. II) ─────────────────────
    "beweisfragen.intro": {
        "title": "II. Untersuchungsauftrag",
        "norm": "ZPO § 404 (Beweisbeschluss)",
        "was": "Die Beweisfragen sind WÖRTLICH aus dem Beweisbeschluss zu übernehmen. "
               "Niemals eigenmächtig abändern, präzisieren oder weglassen.",
        "fallstrick": "Bei technisch unklarer Frage: beim Gericht um Konkretisierung "
                      "bitten (§ 407a ZPO Mitteilungspflicht).",
        "beispiel": "'Weist das gelieferte Softwaresystem einen technischen Mangel auf?'",
    },

    # ───────────────────── Verfahrensgang (Kap. III) ─────────────────────
    "verfahren.intro": {
        "title": "III. Verfahrensgang",
        "norm": "DIN EN 16775 — Transparenter Verfahrensgang",
        "was": "Chronologische, lückenlose Dokumentation aller Verfahrensschritte. "
               "Untersuchungsumgebung, Werkzeuge inkl. Versionen, Labor-Setup nachvollziehbar.",
        "fallstrick": "JEDE Parteikommunikation muss symmetrisch sein — gleicher "
                      "Inhalt, gleiches Datum, an Kläger UND Beklagter UND Gericht.",
        "beispiel": "30.03.2026 — Ladung Ortstermin (gleichlautend an alle Parteien)",
    },
    "verfahren.symmetrie": {
        "title": "Symmetrie der Parteikommunikation",
        "norm": "DIN EN 16775 + ZPO § 357 (rechtliches Gehör)",
        "was": "Sämtliche Korrespondenz hat inhaltsgleich und zeitgleich an beide "
               "Parteien zu erfolgen. Verstöße begründen Befangenheitsanträge.",
        "fallstrick": "Auch informelle E-Mails an nur eine Partei zählen.",
        "beispiel": "BCC ist zulässig, aber Empfänger-Liste sichtbar dokumentieren.",
    },

    # ───────────────────── Befunde (Kap. IV) ─────────────────────
    "befund.intro": {
        "title": "IV. Befunderhebung — Tatsachen-only",
        "norm": "DIN EN 16775 — Disjunkter Befundbericht",
        "was": "OBJEKTIVE, wertungsfreie Darstellung der Messfakten. Keine Bewertung, "
               "keine Würdigung, keine Schlussfolgerung.",
        "fallstrick": "Wörter wie 'mangelhaft', 'fehlerhaft', 'unzureichend' "
                      "gehören NACH Kap. V. Der Linter markiert diese gelb.",
        "beispiel": "'Bei künstlicher Netzwerk-Unterbrechung stürzte die Anwendung "
                    "3 Mal unkontrolliert ab' (Fakt) — NICHT: 'Die Software ist mangelhaft' (Wertung).",
    },
    "befund.methode": {
        "title": "Methode",
        "norm": "ISO/IEC 27037 + IT-Forensik-Grundsätze",
        "was": "Klassifikation der Untersuchungsmethode für Drittgutachter-Tauglichkeit.",
        "fallstrick": "Live-Forensik verlangt Beachtung der 'Order of Volatility' "
                      "(RAM → Netzwerk → FS → Persistent).",
        "beispiel": "statisch (White-Box-Code-Analyse) / dynamisch (Replay-Test) / "
                    "db (DB-Strukturanalyse) / netzwerk / interview / live-forensik",
    },
    "befund.werkzeug": {
        "title": "Werkzeug + Version",
        "norm": "DIN EN 16775 — Reproduzierbarkeit",
        "was": "Werkzeug + EXAKTE Version, damit ein Drittgutachter zum gleichen "
               "Ergebnis kommt.",
        "fallstrick": "Werkzeug muss im SV-Register (G0-3) stehen — siehe G4-2 "
                      "Werkzeug-Validator.",
        "beispiel": "Visual Studio Code 1.95.2 / PostgreSQL-Client 16.2 / Wireshark 4.2",
    },
    "befund.non_liquet": {
        "title": "Non-liquet (Nicht-Feststellbar)",
        "norm": "BISG-Lehre + DIN EN 16775",
        "was": "Wenn Daten fehlen (Log-Rotation, Anti-Forensik, fehlende Backups) "
               "und ein Befund nicht abschließend feststellbar ist — SACHLICH "
               "deklarieren, NICHT durch Spekulation ersetzen.",
        "fallstrick": "Non-liquet ist kein Eingeständnis von Schwäche, sondern "
                      "professionelle Ehrlichkeit.",
        "beispiel": "'Die Ursache des Datenbankzustands ist mangels vorhandener "
                    "WAL-Logs nicht zweifelsfrei rekonstruierbar (non-liquet).'",
    },

    # ───────────────────── Beurteilungen (Kap. V) ─────────────────────
    "beurteilung.intro": {
        "title": "V. Technische Beurteilung",
        "norm": "DIN EN 16775 — Gutachterliche Würdigung",
        "was": "Soll-Ist-Abgleich gegen Normen (ISO/IEC 25010, OWASP ASVS, BSI-"
               "Grundschutz). Trennscharfe wissenschaftliche Begründung.",
        "fallstrick": "Jura-Sperre beachten: NIE 'Vertragsbruch', 'schuldhaft', "
                      "'fahrlässig'. Statt dessen: 'Aus informationstechnischer Sicht...'",
        "beispiel": "'Aus informationstechnischer Sicht liegt eine signifikante "
                    "Abweichung vom geschuldeten Stand der Technik vor.'",
    },
    "beurteilung.norm_referenz": {
        "title": "Norm-Referenz",
        "norm": "ISO/IEC 25010 + 27037 + DIN EN 16775 + OWASP + BSI",
        "was": "EXAKTE Norm + Sub-Merkmal angeben. Sub-Merkmal ist wichtiger als "
               "die übergeordnete Kategorie.",
        "fallstrick": "Pflichtfeld — Beurteilung ohne Norm-Referenz wird vom "
                      "Validator als Error markiert.",
        "beispiel": "ISO/IEC 25010 — Reliability/Fault Tolerance",
    },
    "beurteilung.soll": {
        "title": "Soll (was die Norm verlangt)",
        "norm": "Anerkannte Regeln der Technik",
        "was": "Textueller Auszug oder Paraphrase der Norm-Forderung.",
        "fallstrick": "Bei mehreren passenden Normen alle auflisten — stärkt die "
                      "Belastbarkeit.",
        "beispiel": "ISO/IEC 25010 verlangt unter Reliability/Fault Tolerance, "
                    "dass Software erwartbare Fehler (z.B. Netzwerk-Disconnect) abfängt.",
    },
    "beurteilung.ist": {
        "title": "Ist (Befund-Vergleich)",
        "norm": "BISG-Lehre",
        "was": "Was beim Befund (Kap. IV) tatsächlich vorgefunden wurde — mit "
               "expliziter Befund-Nummer-Verweis.",
        "fallstrick": "Befunde dürfen nicht neu formuliert werden — referenzieren "
                      "und kurz wiedergeben.",
        "beispiel": "Befund 4.1 belegt das vollständige Fehlen von try-catch-Blöcken "
                    "in der API-Schnittstelle.",
    },
    "beurteilung.kausalitaet": {
        "title": "Kausalität",
        "norm": "DIN EN 16775 — wissenschaftliche Begründung",
        "was": "WARUM der Befund einen Verstoß darstellt. Logische Verkettung "
               "Ursache → Wirkung.",
        "fallstrick": "Korrelation ≠ Kausalität. Bei stochastischen Systemen "
                      "(KI) sind 100%-Aussagen oft unzulässig.",
        "beispiel": "Aus informationstechnischer Sicht ist der Absturz die unmittelbare "
                    "Folge des fehlenden Exception-Handlings.",
    },
    "beurteilung.wuerdigung": {
        "title": "Würdigung (Jura-Sperre!)",
        "norm": "ZPO § 407a — Überlassung der Rechtsbewertung",
        "was": "Gutachterliche Bewertung mit 'Aus informationstechnischer Sicht'-Formel. "
               "Niemals rechtliche Begriffe verwenden.",
        "fallstrick": "Bewertung des Gerichts überlassen. Der SV liefert FAKTEN.",
        "beispiel": "'Aus informationstechnischer Sicht liegt eine signifikante "
                    "Abweichung vom Stand der Technik vor.' NIE: 'Die Software ist "
                    "mangelhaft im Rechtssinne.'",
    },

    # ───────────────────── Asservaten (Chain of Custody) ─────────────────────
    "asset.sha256": {
        "title": "SHA-256-Hashwert",
        "norm": "ISO/IEC 27037 — Mathematische Integritätssicherung",
        "was": "Kryptografischer Einweg-Hash, unmittelbar bei Akquisition gebildet, "
               "vor und nach Analyse verifiziert.",
        "fallstrick": "Hash MUSS bei der Sicherung gegengezeichnet werden — "
                      "beste Praxis: durch Vertreter beider Parteien.",
        "beispiel": "SHA-256: 8f3c9a1e4f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c",
    },
    "asset.coc": {
        "title": "Chain of Custody (CoC)",
        "norm": "ISO/IEC 27037 — 4 Phasen-Lebenszyklus",
        "was": "Lückenlose Dokumentation aller Personen, Zeiten und Maßnahmen, "
               "die mit dem Beweismittel interagiert haben.",
        "fallstrick": "Jede Lücke kann zum Beweisverwertungsverbot führen.",
        "beispiel": "(1) Identifikation/Erfassung → (2) Sicherung/Verpackung → "
                    "(3) Transport/Lagerung → (4) Labor-Analyse",
    },
    "asset.parteien": {
        "title": "Parteien anwesend / Gegengezeichnet",
        "norm": "ZPO § 357 + ISO/IEC 27037",
        "was": "Bei Asservatensicherung im Ortstermin sollten Vertreter beider "
               "Parteien anwesend sein und den Hashwert gegenzeichnen.",
        "fallstrick": "Wenn nicht möglich: schriftliche Begründung in den "
                      "Bemerkungen + sofortige Anzeige an Gericht.",
        "beispiel": "Klägerin: System-Admin Müller / Beklagte: Architekt Schmidt",
    },

    # ───────────────────── Honorar ─────────────────────
    "honorar.jveg": {
        "title": "JVEG-Honorargruppe",
        "norm": "JVEG (Justizvergütungs- und -entschädigungsgesetz)",
        "was": "Striktes Gesetz ohne Verhandlungsspielraum für Gerichtsgutachten. "
               "IT-Spezialgebiete: HG-11/12/13.",
        "fallstrick": "Bei Privatgutachten gilt freie Vereinbarung — Verbot von "
                      "Erfolgshonoraren (Standesrecht).",
        "beispiel": "HG-11 (Standard-IT) = 105€/h · HG-12 (komplexe IT) = 115€/h · "
                    "HG-13 (IT-Forensik/Spezial) = 130€/h",
    },

    # ───────────────────── Validator + Export ─────────────────────
    "validator.intro": {
        "title": "Pre-Export-Validator",
        "norm": "Eigene Quality-Gate-Logik (G5-1)",
        "was": "Prüft Pflichtfelder + Sprach-Linter + Cross-Reference. Nur "
               "release_ready=true sollte exportiert werden.",
        "fallstrick": "Sprach-Warnungen sind nur Hinweise — Pflichtfeld-Errors "
                      "blockieren den Export.",
        "beispiel": "Aus 'release_ready: false' folgt: erst Errors beheben, dann DOCX.",
    },
    "validator.qes": {
        "title": "QES — Elektronische Einreichung",
        "norm": "§ 130a ZPO — Qualifizierte Elektronische Signatur",
        "was": "Elektronisch eingereichte Gutachten brauchen QES via beA / beN / beBPo. "
               "Ein Scan der Unterschrift genügt NICHT.",
        "fallstrick": "PDF + Hash-Sidecar speichern — die App generiert beides.",
        "beispiel": "PDF im Adobe Reader mit beA-Karte signieren → versenden.",
    },

    # ───────────────────── Allgemein ─────────────────────
    "general.407a": {
        "title": "§ 407a — Persönliche Leistungserbringung",
        "norm": "ZPO § 407a + BGB § 839a",
        "was": "Der SV muss seine Beurteilungen PERSÖNLICH erstellen. KI darf "
               "nur als Hilfsmittel (Recherche, Strukturierung, sprachliche "
               "Optimierung) verwendet werden.",
        "fallstrick": "Bei Halluzinationen: Durchgriffshaftung wegen grober "
                      "Fahrlässigkeit (§ 839a BGB).",
        "beispiel": "KI-Vorschlag akzeptieren → § 407a-Akzeptanz-Log wird "
                    "automatisch geschrieben (G3-4).",
    },
    "general.aufbewahrung": {
        "title": "10-Jahre-Aufbewahrungspflicht",
        "norm": "Standesrecht BISG + GoBD analog",
        "was": "Sämtliche Gutachten + Asservaten + CoC-Protokolle müssen "
               "mindestens 10 Jahre archiviert werden.",
        "fallstrick": "Archiv-ZIP mit Hash-Manifest schützt vor Manipulationsvorwürfen.",
        "beispiel": "Sprint G5-5 setzt das Archiv-Datum automatisch auf "
                    "Erstellungsdatum + 10 Jahre.",
    },
}


def get_help(key: str) -> dict[str, Any] | None:
    """Liefert Hilfetext zu einem Key oder None."""
    return HELP.get(key)


def list_keys() -> list[str]:
    """Alle verfügbaren Hilfe-Keys."""
    return sorted(HELP.keys())


def search_help(query: str) -> list[dict[str, Any]]:
    """Volltextsuche über alle Hilfetexte."""
    q = (query or "").strip().lower()
    if not q:
        return []
    out = []
    for k, v in HELP.items():
        hay = " ".join(filter(None, [v.get("title"), v.get("norm"), v.get("was"),
                                     v.get("fallstrick"), v.get("beispiel")])).lower()
        if q in hay or q in k.lower():
            out.append({"key": k, **v})
    return out
