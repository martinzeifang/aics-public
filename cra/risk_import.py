"""#887: CRA-Risikoquellen (Threat-Model/STRIDE & CVEs) → RB-Risiken.

Reine Mapping-Funktionen ohne DB/HTTP (testbar). Sie übersetzen CRA-Threats
und CVEs in RB-Risiko-Dicts für das STRIDE-Framework. Die eigentliche,
idempotente Persistierung erfolgt im API-Layer (Provenienz in ``felder``).

Fachlicher Bezug: greift die Vorarbeiten #562 (Threat-Model ↔ Risikobewertung)
und #482 (CVEs als Risiko-Quelle) auf; dient der Nachweisbarkeit (AI1-01).
Optional/abschaltbar — kein Pflichtpfad für Stufe 1/2.
"""
from __future__ import annotations

from typing import Any

from risikobewertung.frameworks import STRIDE_KATEGORIEN

# Provenienz-Schlüssel im felder_json eines importierten RB-Risikos.
SOURCE_THREAT = "cra-threat"
SOURCE_CVE = "cra-cve"

# ── CVSS/Schwere → STRIDE-Felder (dokumentierte Heuristik) ──────────────────
# Eintrittswahrscheinlichkeit nach CVSS-Base-Score: bekannte/disclosed CVEs
# gelten als real ausnutzbar, daher tendenziell höhere Wahrscheinlichkeit.
def cve_likelihood(cvss: float) -> str:
    if cvss >= 9.0:
        return "Sehr wahrscheinlich"
    if cvss >= 7.0:
        return "Wahrscheinlich"
    if cvss >= 4.0:
        return "Möglich"
    if cvss > 0.0:
        return "Unwahrscheinlich"
    return "Möglich"


# Auswirkung (Impact) aus der CVE-Schwere (STRIDE-Impact-Skala).
_SCHWERE_IMPACT = {
    "critical": "Kritisch",
    "high": "Hoch",
    "medium": "Mittel",
    "low": "Gering",
    "unknown": "Mittel",
}


def _match_stride_kategorie(raw: str) -> str:
    """Ordnet eine freie Kategorie-Angabe einer STRIDE_KATEGORIEN-Konstante zu.

    Leerstring, wenn keine Zuordnung möglich (Score hängt nur von
    Wahrscheinlichkeit × Auswirkung ab, die Kategorie ist Klassifikation)."""
    s = str(raw or "").strip().lower()
    if not s:
        return ""
    for kat in STRIDE_KATEGORIEN:
        if kat.lower() == s:
            return kat
    # Anfangsbuchstabe (S/T/R/I/D/E) oder Schlagwort-Treffer
    for kat in STRIDE_KATEGORIEN:
        head = kat.split(" ", 1)[0].lower()  # z.B. "spoofing"
        if s == head or s in kat.lower() or head in s:
            return kat
    return ""


def cve_to_risk(cve: dict, cra_projekt: str = "") -> dict:
    """Übersetzt einen ``cra_vuln``-Eintrag in ein RB-Risiko-Dict (STRIDE)."""
    cvss = float(cve.get("cvss_score") or 0.0)
    schwere = str(cve.get("schwere") or "unknown").lower()
    impact = _SCHWERE_IMPACT.get(schwere, "Mittel")
    cve_id = str(cve.get("cve_id") or "").strip()
    felder: dict[str, Any] = {
        "stride_kategorie": "",
        "eintrittswahrscheinlichkeit": cve_likelihood(cvss),
        "auswirkung": impact,
        "_source": SOURCE_CVE,
        "_source_id": cve_id,
        "_source_projekt": cra_projekt,
    }
    titel = (cve.get("titel") or "").strip()
    name = f"{cve_id}: {titel}".strip(": ").strip() or cve_id or "CVE"
    herkunft = f"Importierte CVE aus CRA-Projekt „{cra_projekt}“." if cra_projekt else ""
    parts = [
        herkunft,
        f"CVSS {cvss} ({schwere}).",
        f"Betroffene Komponente: {cve.get('affected_component')}." if cve.get("affected_component") else "",
        f"Advisory: {cve.get('advisory_url')}" if cve.get("advisory_url") else "",
    ]
    return {
        "risk_name": name,
        "beschreibung": " ".join(p for p in parts if p).strip(),
        "framework": "STRIDE",
        "felder": felder,
        "bewertung_text": (cve.get("triage_kommentar") or "").strip(),
    }


def threat_to_risk(threat: dict, idx: int, cra_projekt: str = "") -> dict:
    """Übersetzt einen (freiformigen) Threat-Model-Eintrag in ein RB-Risiko-Dict."""
    tid = str(threat.get("id") or threat.get("threat_id") or threat.get("ref") or idx)
    kat_raw = threat.get("kategorie") or threat.get("category") or threat.get("stride") or ""
    titel = (threat.get("titel") or threat.get("title") or threat.get("name")
             or f"Threat {tid}").strip()
    beschr = (threat.get("beschreibung") or threat.get("description") or "").strip()
    mitigation = (threat.get("mitigation") or threat.get("massnahme")
                  or threat.get("gegenmassnahme") or "").strip()
    felder: dict[str, Any] = {
        "stride_kategorie": _match_stride_kategorie(kat_raw),
        "eintrittswahrscheinlichkeit": "Möglich",
        "auswirkung": "Hoch",
        "_source": SOURCE_THREAT,
        "_source_id": tid,
        "_source_projekt": cra_projekt,
    }
    bewertung_text = mitigation
    if cra_projekt:
        beschr = (beschr + f"\n\n(Importiert aus CRA-Threat-Model „{cra_projekt}“.)").strip()
    return {
        "risk_name": titel,
        "beschreibung": beschr,
        "framework": "STRIDE",
        "felder": felder,
        "bewertung_text": bewertung_text,
    }


def provenance_key(felder: dict) -> tuple[str, str] | None:
    """Provenienz-Schlüssel (source, source_id) eines importierten Risikos
    oder ``None`` für manuell angelegte Risiken."""
    if not isinstance(felder, dict):
        return None
    src = felder.get("_source")
    if src not in (SOURCE_THREAT, SOURCE_CVE):
        return None
    return (str(src), str(felder.get("_source_id") or ""))
