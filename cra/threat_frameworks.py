"""Einheitliche Threat-Model-Framework-Liste für CRA C5 (#938).

Single Source of Truth für die im CRA-Threat-Model (C5) zulässigen Frameworks.
Der CRA ist methodenneutral (Art. 13(2), Annex I Teil I) — anerkannt sind u. a.
STRIDE, PASTA, LINDDUN, OCTAVE, HEAVENS und TARA (ISO/SAE 21434, in EN 18031 /
BSI TR-03161 referenziert).

Die Risikobewertung (``risikobewertung/frameworks.py``) kennt eine Teilmenge
(Finanzinstitute, STRIDE, STRIDE-LLM, HEAVENS, OCTAVE, TARA). Diese Liste ist
das Superset und garantiert, dass ein aus der verknüpften Risikobewertung
übernommenes Framework hier immer als gültige Option existiert.
"""
from __future__ import annotations

# (id, label) — id wird in cra_threatmodel.framework persistiert.
THREAT_FRAMEWORKS: list[tuple[str, str]] = [
    ("STRIDE",          "STRIDE (Microsoft SDL)"),
    ("STRIDE-LLM",      "STRIDE-LLM (OWASP LLM Top 10)"),
    ("PASTA",           "PASTA (risiko-/business-zentriert)"),
    ("LINDDUN",         "LINDDUN (Privacy)"),
    ("HEAVENS",         "HEAVENS (Embedded/Automotive)"),
    ("OCTAVE",          "OCTAVE Allegro (CERT/CMU)"),
    ("TARA",            "TARA (ISO/SAE 21434)"),
    ("Finanzinstitute", "Risikobewertung Finanzinstitute"),
    ("EU-AI-Act",       "EU AI Act (Art. 9 Risikomanagement)"),
    ("DSGVO-DSFA",      "DSGVO-DSFA (Art. 35 Datenschutz-Folgenabschätzung)"),
]

THREAT_FRAMEWORK_IDS: list[str] = [fid for fid, _ in THREAT_FRAMEWORKS]
THREAT_FRAMEWORK_LABELS: dict[str, str] = {fid: label for fid, label in THREAT_FRAMEWORKS}


def is_valid_framework(framework: str) -> bool:
    """True, wenn ``framework`` eine bekannte C5-Framework-ID ist."""
    return framework in THREAT_FRAMEWORK_LABELS


def framework_label(framework: str) -> str:
    """Anzeigename zu einer Framework-ID (Fallback: die ID selbst)."""
    return THREAT_FRAMEWORK_LABELS.get(framework, framework)
