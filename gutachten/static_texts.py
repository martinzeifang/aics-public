"""Zentrale Fixtexte für Gutachten — gemeinsam von Standard- und Template-Renderer (#974).

Single Source of Truth für rechtlich relevante Standardformulierungen, damit
Standard-Export und Word-Vorlagen-Export identisch sind.
"""
from __future__ import annotations

# Eigenversicherung des Sachverständigen (Kap. VII Schlussformel).
EIGENVERSICHERUNG = (
    "Der Unterzeichnende versichert, das Gutachten unparteiisch, nach bestem "
    "Wissen und Gewissen, persönlich und nach dem aktuellen Stand der Technik "
    "erstellt zu haben."
)

# Pflicht-Klausel zur KI-Nutzung (§ 407a Abs. 2 ZPO).
KI_KLAUSEL = (
    "Hinweis: KI-Werkzeuge wurden ausschließlich zur Recherche, Strukturierung "
    "und sprachlichen Optimierung eingesetzt. Die finale Beurteilung und "
    "Kausalitätsbewertung erfolgte persönlich durch den Sachverständigen "
    "(§ 407a Abs. 2 ZPO)."
)
