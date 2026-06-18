"""Standard-Response-Playbooks (#1314) — Seed-Katalog nach NIST SP 800-61 / BSI DER.2.1.

Jede Vorlage gliedert die Reaktion in die Phasen Analyse → Eindämmung → Beseitigung →
Wiederherstellung → Nachbereitung. Pflicht-Schritte (`mandatory`) müssen vor dem
Statuswechsel auf „resolved" abgehakt sein.
"""
from __future__ import annotations

from pathlib import Path

# kategorie, name, beschreibung, steps[(text, mandatory)]
DEFAULT_PLAYBOOKS: list[dict] = [
    {
        "name": "Phishing-Vorfall", "kategorie": "phishing",
        "beschreibung": "Reaktion auf gemeldete/erkannte Phishing-E-Mails.",
        "steps": [
            ("Verdächtige E-Mail + Header sichern, Indikatoren (Absender, URLs, Anhänge) erfassen", True),
            ("Betroffene Empfänger und mögliche Klicks/Eingaben ermitteln", True),
            ("Schadhafte URLs/Domains sperren, E-Mail aus Postfächern entfernen", True),
            ("Kompromittierte Konten zurücksetzen (Passwort + Sessions), MFA prüfen", True),
            ("Awareness-Hinweis an Betroffene/Organisation", False),
            ("IoCs in Sperrlisten/Threat-Intel übernehmen", False),
            ("Nachbereitung: Ursache + Lessons Learned dokumentieren", True),
        ],
    },
    {
        "name": "Malware / Ransomware", "kategorie": "malware",
        "beschreibung": "Reaktion auf Malware-/Ransomware-Befall eines Hosts.",
        "steps": [
            ("Betroffene Hosts identifizieren + Art der Malware bestimmen", True),
            ("Host(s) vom Netz isolieren (Containment)", True),
            ("Beweissicherung: Speicher-/Datenträger-Image bzw. Logs sichern", True),
            ("Ausbreitung prüfen (laterale Bewegung, weitere Hosts)", True),
            ("Malware entfernen / Host neu aufsetzen (Eradication)", True),
            ("Aus sauberem Backup wiederherstellen, Integrität prüfen", True),
            ("Bei Ransomware: keine Lösegeldzahlung ohne Leitungsentscheid; Meldepflichten prüfen", True),
            ("Nachbereitung + Härtung (Patch, EDR-Regeln)", True),
        ],
    },
    {
        "name": "Unbefugter Zugriff / Kompromittiertes Konto", "kategorie": "unauthorized_access",
        "beschreibung": "Reaktion auf kompromittierte Konten oder unbefugten Zugriff.",
        "steps": [
            ("Betroffenes Konto/Asset + Zugriffspfad bestimmen", True),
            ("Konto sperren / Sessions invalidieren, Passwort zurücksetzen", True),
            ("Umfang prüfen: was wurde abgerufen/geändert (Audit-Logs)", True),
            ("Persistenz entfernen (angelegte Konten, Schlüssel, Regeln)", True),
            ("Rechte/Privilegien überprüfen und bereinigen", True),
            ("Personenbezug? → DSGVO-Meldepflicht prüfen (Router)", False),
            ("Nachbereitung: Ursache, Maßnahmen, Lessons Learned", True),
        ],
    },
    {
        "name": "DoS / DDoS", "kategorie": "dos",
        "beschreibung": "Reaktion auf (Distributed-)Denial-of-Service.",
        "steps": [
            ("Angriff bestätigen + Zieldienst/Vektor identifizieren", True),
            ("Verkehr analysieren (Quellen, Muster, Volumen)", True),
            ("Gegenmaßnahmen: Rate-Limiting/Filter/Upstream-/CDN-Schutz aktivieren", True),
            ("Betroffene Dienste + Nutzerauswirkung dokumentieren", True),
            ("Provider/Upstream einbeziehen falls nötig", False),
            ("Nach Abklingen: Schutz dauerhaft härten", True),
            ("Nachbereitung + ggf. NIS2-Meldepflicht prüfen", False),
        ],
    },
    {
        "name": "Datenabfluss / Datenpanne", "kategorie": "data_exfiltration",
        "beschreibung": "Reaktion bei Verdacht auf Abfluss (personenbezogener) Daten.",
        "steps": [
            ("Abfluss bestätigen: welche Daten, Umfang, Zeitpunkt", True),
            ("Exfiltrationskanal schließen (Containment)", True),
            ("Betroffene Datenkategorien + Personenzahl abschätzen", True),
            ("Awareness-Zeitpunkt festhalten (startet 72h-Frist)", True),
            ("Meldepflicht-Router ausführen (DSGVO Art. 33/34 / NIS2 / CRA)", True),
            ("Beweise sichern (Chain of Custody)", True),
            ("Nachbereitung: Root Cause + Maßnahmen", True),
        ],
    },
]


def seed_default_playbooks(db_path: Path) -> int:
    """Legt die Standard-Playbooks an, falls der Katalog leer ist (idempotent)."""
    from soc import db as sdb
    if sdb.list_playbooks(db_path):
        return 0
    n = 0
    for pb in DEFAULT_PLAYBOOKS:
        steps = [{"id": i + 1, "text": t, "mandatory": m} for i, (t, m) in enumerate(pb["steps"])]
        sdb.save_playbook(db_path, name=pb["name"], kategorie=pb["kategorie"],
                          beschreibung=pb["beschreibung"], steps=steps)
        n += 1
    return n
