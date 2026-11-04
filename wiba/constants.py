"""WiBA-Konstanten: Antwort-/Status-Modell + Reifegrad-Mapping.

WiBA nutzt nativ das BSI-Antwortmodell *Ja / Nein / Nicht relevant*. Für die
suite-einheitliche Reifegrad-Logik (wie CRA) wird daraus ein Prozentwert
abgeleitet; ``nicht_relevant`` ist außerhalb des Scopes (zählt nicht zur Basis).
"""
from __future__ import annotations

# Antwort-/Status-Werte einer Prüffrage.
STATUS_OFFEN = "offen"
STATUS_JA = "ja"
STATUS_NEIN = "nein"
STATUS_NICHT_RELEVANT = "nicht_relevant"

STATUS_WERTE = (STATUS_OFFEN, STATUS_JA, STATUS_NEIN, STATUS_NICHT_RELEVANT)

# Anzeige-Metadaten (Label + Farbe) — analog CRA BEWERTUNG_SKALA.
STATUS_META: dict[str, dict[str, str]] = {
    STATUS_OFFEN: {"label": "Offen", "farbe": "#9e9e9e"},
    STATUS_JA: {"label": "Ja (umgesetzt)", "farbe": "#1b5e20"},
    STATUS_NEIN: {"label": "Nein (offen)", "farbe": "#c62828"},
    STATUS_NICHT_RELEVANT: {"label": "Nicht relevant", "farbe": "#607d8b"},
}


def normalize_status(value: str | None) -> str:
    """Mappt Eingaben robust auf einen gültigen Status (Default ``offen``)."""
    v = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if v in ("ja", "yes", "true", "umgesetzt"):
        return STATUS_JA
    if v in ("nein", "no", "false", "offen_nein"):
        return STATUS_NEIN
    if v in ("nicht_relevant", "n_a", "na", "n/a", "nichtrelevant", "irrelevant"):
        return STATUS_NICHT_RELEVANT
    if v == STATUS_NEIN:
        return STATUS_NEIN
    return v if v in STATUS_WERTE else STATUS_OFFEN


def reifegrad_pct(status: str) -> float | None:
    """Reifegrad-Beitrag einer Prüffrage in Prozent.

    ``ja`` = 100, ``nein``/``offen`` = 0, ``nicht_relevant`` = None (außer Scope).
    """
    s = normalize_status(status)
    if s == STATUS_NICHT_RELEVANT:
        return None
    return 100.0 if s == STATUS_JA else 0.0
