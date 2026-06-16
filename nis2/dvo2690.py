"""N-DVO (#1220 Teil B) — NIS2 DVO (EU) 2024/2690 Sektor-Anforderungsset + Triage.

Die Durchführungsverordnung (EU) 2024/2690 konkretisiert für digitale
Infrastrukturen/Dienste die technischen und methodischen Mindestanforderungen
(Anhang, Abschnitte 1–13) sowie die **Erheblichkeits-Schwellenwerte** für die
Vorfall-Triage je Diensttyp.

Dieser Layer liefert:
- ``DVO_SECTIONS``: die 13 Abschnitte als bewertbare Controls (Seed für
  ``nis2_anforderungen_custom``, Kapitel ``DVO2690``).
- ``SCHWELLENWERTE``: strukturierter Erheblichkeits-Schwellenwert-Katalog je
  Diensttyp (Entscheidungshilfe in der NIS2-Incident-Triage).
- Aktivierungs-/Deaktivierungs-Helfer, gebunden an den N6-Klassifikator-Sektor.

Kein neues DB-Schema: die Controls werden in die bestehende
``nis2_anforderungen_custom``-Tabelle geschrieben (global, Kapitel ``DVO2690``).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from nis2 import db as ndb

DB_PATH = Path("data/db/nis2.sqlite")

KAPITEL = "DVO2690"

# Sektoren, für die die DVO 2024/2690 gilt (digitale Infrastrukturen/Dienste).
# Wird gegen den N6-Klassifikator-Sektor (lower, substring) geprüft.
DVO_SEKTOREN_KEYWORDS = (
    "digital", "dns", "tld", "cloud", "rechenzentrum", "data center",
    "content delivery", "cdn", "vertrauensdienst", "trust service",
    "kommunikation", "ict", "managed service", "online", "plattform",
    "marktplatz", "suchmaschine", "social",
)

# Die 13 Abschnitte des DVO-Anhangs als bewertbare Controls.
DVO_SECTIONS: list[dict[str, str]] = [
    {"ref": "DVO-1", "titel": "Risikomanagement-Konzept für die Sicherheit von Netz-/Informationssystemen",
     "beschreibung": "Etablierung, Pflege und Anwendung eines dokumentierten Risikomanagement-Rahmens."},
    {"ref": "DVO-2", "titel": "Politik für die Sicherheit von Netz- und Informationssystemen",
     "beschreibung": "Übergeordnete, von der Leitung gebilligte Sicherheitspolitik mit Rollen/Verantwortlichkeiten."},
    {"ref": "DVO-3", "titel": "Bewältigung von Sicherheitsvorfällen",
     "beschreibung": "Erkennung, Behandlung, Eskalation und Nachbereitung von Vorfällen (inkl. Meldewege)."},
    {"ref": "DVO-4", "titel": "Betriebskontinuität und Krisenmanagement",
     "beschreibung": "Business-Continuity-, Backup- und Disaster-Recovery-Management inkl. Tests."},
    {"ref": "DVO-5", "titel": "Sicherheit der Lieferkette",
     "beschreibung": "Sicherheitsanforderungen an Lieferanten/Dienstleister und deren Überwachung."},
    {"ref": "DVO-6", "titel": "Sicherheit bei Erwerb, Entwicklung und Wartung",
     "beschreibung": "Sichere Beschaffung, Entwicklung, Wartung und Schwachstellenoffenlegung."},
    {"ref": "DVO-7", "titel": "Bewertung der Wirksamkeit der Maßnahmen",
     "beschreibung": "Regelmäßige Wirksamkeitsprüfung der Risikomanagement-Maßnahmen."},
    {"ref": "DVO-8", "titel": "Cyberhygiene und Schulung",
     "beschreibung": "Grundlegende Cyberhygiene-Praktiken und Sensibilisierungs-/Schulungsprogramme."},
    {"ref": "DVO-9", "titel": "Kryptografie und Verschlüsselung",
     "beschreibung": "Konzept und Einsatz von Kryptografie nach Stand der Technik."},
    {"ref": "DVO-10", "titel": "Personalsicherheit, Zugriffskontrolle und Asset-Management",
     "beschreibung": "Personelle Sicherheit, Identitäts-/Zugriffsmanagement und Asset-Inventar."},
    {"ref": "DVO-11", "titel": "Multi-Faktor-Authentifizierung und gesicherte Kommunikation",
     "beschreibung": "MFA, gesicherte Sprach-/Video-/Textkommunikation und Notfallkommunikation."},
    {"ref": "DVO-12", "titel": "Sicherheit des Personals und der physischen Umgebung",
     "beschreibung": "Physische Sicherheit, Zutrittskontrolle und Schutz der Einrichtungen."},
    {"ref": "DVO-13", "titel": "Überwachung, Protokollierung und Audit",
     "beschreibung": "Monitoring, Logging, Audit-Trails und Auswertung sicherheitsrelevanter Ereignisse."},
]

# Erheblichkeits-Schwellenwert-Katalog je Diensttyp (Triage-Entscheidungshilfe).
# Werte sind Richtgrößen aus der DVO 2024/2690 (vereinfacht, Single Source of Truth).
SCHWELLENWERTE: list[dict[str, Any]] = [
    {"diensttyp": "DNS-Diensteanbieter",
     "kriterien": [
         "Vollständige Nichtverfügbarkeit der DNS-Auflösung > 30 Minuten",
         "Manipulation von DNS-Antworten (Integritätsverlust)",
     ]},
    {"diensttyp": "TLD-Namenregister",
     "kriterien": [
         "Nichtverfügbarkeit der Registry-Dienste > 30 Minuten",
         "Unbefugte Änderung von Registrierungsdaten",
     ]},
    {"diensttyp": "Cloud-Computing-Dienst",
     "kriterien": [
         "Nichtverfügbarkeit > 5 % der Nutzer oder > 1 Stunde für kritische Kunden",
         "Verlust der Vertraulichkeit/Integrität gespeicherter Kundendaten",
     ]},
    {"diensttyp": "Rechenzentrumsdienst",
     "kriterien": [
         "Ausfall der Stromversorgung/Kühlung mit Dienstunterbrechung",
         "Physischer/logischer Sicherheitsvorfall mit Auswirkung auf Kunden",
     ]},
    {"diensttyp": "Content-Delivery-Network",
     "kriterien": [
         "Nichtverfügbarkeit der Auslieferung für > 5 % der Endnutzer",
         "Manipulation ausgelieferter Inhalte",
     ]},
    {"diensttyp": "Vertrauensdiensteanbieter",
     "kriterien": [
         "Kompromittierung von Signatur-/Siegel-Schlüsseln",
         "Ausstellung falscher/qualifizierter Zertifikate",
     ]},
    {"diensttyp": "Anbieter öffentlicher elektronischer Kommunikation",
     "kriterien": [
         "Ausfall mit > 1.000.000 betroffenen Nutzerstunden",
         "Abhören/Manipulation von Kommunikationsinhalten",
     ]},
]


def is_dvo_relevant(sektor: str | None) -> bool:
    s = (sektor or "").strip().lower()
    return any(kw in s for kw in DVO_SEKTOREN_KEYWORDS)


def list_active(db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    """Liefert die aktuell aktivierten DVO-Controls (Kapitel ``DVO2690``)."""
    ndb.ensure_db(db_path)
    return [c for c in ndb.load_custom_anforderungen(db_path)
            if c.get("kapitel") == KAPITEL]


def activate(db_path: Path = DB_PATH) -> int:
    """Aktiviert das DVO-2690-Set: schreibt die 13 Abschnitte als Controls.

    Idempotent (Upsert je id ``DVO2690-DVO-n``). Returns Anzahl Controls.
    """
    ndb.ensure_db(db_path)
    for sec in DVO_SECTIONS:
        ndb.save_custom_anforderung(db_path, {
            "id": f"{KAPITEL}-{sec['ref']}",
            "kapitel": KAPITEL,
            "ref": sec["ref"],
            "titel": sec["titel"],
            "beschreibung": sec["beschreibung"],
            "hinweise": "DVO (EU) 2024/2690 — sektorspezifische Mindestanforderung.",
            "gewichtung": 1,
            "ist_override": 0,
        })
    return len(DVO_SECTIONS)


def deactivate(db_path: Path = DB_PATH) -> int:
    """Entfernt alle DVO-2690-Controls. Returns Anzahl entfernter Controls."""
    active = list_active(db_path)
    for c in active:
        ndb.delete_custom_anforderung(db_path, c["id"])
    return len(active)
