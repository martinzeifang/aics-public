"""Seed-Katalog für das Gutachten-Glossar (#986, Story D).

Liefert fertige Erklärungen für gängige Normen, Standards und IT-Forensik-
Fachbegriffe. Die automatische Glossar-Erstellung (#984) matcht erkannte
Begriffe case-insensitiv gegen diesen Katalog und übernimmt die Erklärung.
Erweiterbar — siehe CLAUDE.md.
"""
from __future__ import annotations

# begriff (Anzeigeform) → {erklaerung, typ}
GLOSSAR_SEED: dict[str, dict[str, str]] = {
    "ISO/IEC 27001": {
        "typ": "norm",
        "erklaerung": "Internationale Norm für Informationssicherheits-Managementsysteme (ISMS); "
                      "definiert Anforderungen an Aufbau, Betrieb und kontinuierliche Verbesserung der Informationssicherheit.",
    },
    "ISO/IEC 27002": {
        "typ": "norm",
        "erklaerung": "Leitfaden mit Maßnahmenempfehlungen (Controls) zur Informationssicherheit, ergänzend zu ISO/IEC 27001.",
    },
    "ISO/IEC 27037": {
        "typ": "norm",
        "erklaerung": "Leitfaden zur Identifizierung, Sammlung, Erfassung und Sicherung digitaler Beweismittel "
                      "(Chain of Custody) — zentral für die IT-forensische Beweissicherung.",
    },
    "ISO/IEC 27042": {
        "typ": "norm",
        "erklaerung": "Leitfaden für die Analyse und Interpretation digitaler Beweismittel.",
    },
    "ISO/IEC 27043": {
        "typ": "norm",
        "erklaerung": "Rahmenwerk für Untersuchungsprinzipien und -prozesse bei Vorfällen (Incident Investigation).",
    },
    "ISO 9001": {
        "typ": "norm",
        "erklaerung": "Internationale Norm für Qualitätsmanagementsysteme.",
    },
    "DIN EN 16775": {
        "typ": "norm",
        "erklaerung": "Europäische Norm zu allgemeinen Anforderungen an Sachverständigenleistungen.",
    },
    "BSI IT-Grundschutz": {
        "typ": "norm",
        "erklaerung": "Methodik und Baustein-Kompendium des BSI zur Umsetzung angemessener Informationssicherheit.",
    },
    "BSI TR-03161": {
        "typ": "norm",
        "erklaerung": "Technische Richtlinie des BSI zu Sicherheitsanforderungen an Anwendungen im Gesundheitswesen.",
    },
    "EN 18031": {
        "typ": "norm",
        "erklaerung": "Europäische Norm zu Cybersicherheitsanforderungen an funkgestützte Geräte (RED).",
    },
    "ISO/SAE 21434": {
        "typ": "norm",
        "erklaerung": "Norm für Cybersicherheit im Straßenfahrzeug-Engineering (Automotive), Grundlage der TARA-Methode.",
    },
    "Chain of Custody": {
        "typ": "begriff",
        "erklaerung": "Lückenlose, dokumentierte Beweismittelkette von der Sicherstellung bis zur Auswertung; "
                      "sichert Authentizität und Integrität digitaler Beweismittel.",
    },
    "SHA-256": {
        "typ": "begriff",
        "erklaerung": "Kryptografische Hashfunktion (256 Bit) zur Integritätssicherung; identischer Inhalt ergibt "
                      "identischen Hashwert — Veränderungen werden nachweisbar.",
    },
    "Hashwert": {
        "typ": "begriff",
        "erklaerung": "Eindeutige Prüfsumme eines Datenbestands; dient dem Nachweis der Unverändertheit (Integrität).",
    },
    "MACB": {
        "typ": "begriff",
        "erklaerung": "Zeitstempel-Kategorien eines Dateisystems: Modified, Accessed, Changed, Birth — "
                      "wichtig für die forensische Zeitlinien-Analyse.",
    },
    "Non-liquet": {
        "typ": "begriff",
        "erklaerung": "Feststellung, dass sich eine Beweisfrage mit den vorliegenden Mitteln nicht eindeutig "
                      "klären lässt (lateinisch: es ist nicht klar).",
    },
    "STRIDE": {
        "typ": "methode",
        "erklaerung": "Bedrohungsmodellierungs-Methode (Spoofing, Tampering, Repudiation, Information Disclosure, "
                      "Denial of Service, Elevation of Privilege).",
    },
    "Write-Blocker": {
        "typ": "werkzeug",
        "erklaerung": "Hard- oder Software, die schreibenden Zugriff auf ein Asservat verhindert, um die "
                      "Beweismittelintegrität bei der Sicherung zu wahren.",
    },
    "Imaging": {
        "typ": "begriff",
        "erklaerung": "Bit-genaue forensische Kopie eines Datenträgers (z. B. als E01/RAW) als Grundlage der Analyse.",
    },
    "§ 406 ZPO": {
        "typ": "begriff",
        "erklaerung": "Regelung zur Ablehnung eines Sachverständigen wegen Besorgnis der Befangenheit.",
    },
    "§ 407a ZPO": {
        "typ": "begriff",
        "erklaerung": "Pflichten des Sachverständigen, u. a. persönliche Leistungserbringung und Hinzuziehung von Hilfspersonen.",
    },
}


def lookup(begriff: str) -> dict[str, str] | None:
    """Case-insensitiver Treffer im Seed-Katalog."""
    if not begriff:
        return None
    low = begriff.strip().lower()
    for k, v in GLOSSAR_SEED.items():
        if k.lower() == low:
            return {"begriff": k, **v}
    return None
