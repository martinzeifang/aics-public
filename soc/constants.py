"""SOC-Konstanten: Alarm-/Incident-Status, Severity-Mapping, Meldepflicht-Regime.

Single Source of Truth für die Status-Maschinen und das Regime-Mapping des
Meldepflicht-Routers (#1281). Severity leitet sich generisch aus dem Wazuh
``rule.level`` (0–15) ab — funktioniert mit jeder Wazuh-4.x-Instanz.
"""
from __future__ import annotations

# ── Severity aus Wazuh rule.level (0–15) ────────────────────────────────────
SEVERITIES = ["low", "medium", "high", "critical"]


def severity_from_level(level: int | None) -> str:
    try:
        lvl = int(level)
    except (TypeError, ValueError):
        return "low"
    if lvl >= 12:
        return "critical"
    if lvl >= 8:
        return "high"
    if lvl >= 4:
        return "medium"
    return "low"


SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}


# ── Alarm-Art: Schwachstelle vs. sonstiger Alarm (#1294) ────────────────────
ALERT_KINDS = ["alert", "vulnerability"]
# Wazuh-rule.groups-Marker des Vulnerability-Detectors
_VULN_GROUP_MARKERS = ("vulnerability-detector", "vulnerability", "vuln")


def classify_kind(groups: list[str] | None) -> str:
    for g in (groups or []):
        gl = str(g).lower()
        if any(m in gl for m in _VULN_GROUP_MARKERS):
            return "vulnerability"
    return "alert"


# ── Alarm-Triage-Status ─────────────────────────────────────────────────────
ALERT_STATES = ["new", "in_review", "false_positive", "confirmed", "suppressed"]

ALERT_TRANSITIONS: dict[str, list[str]] = {
    "new": ["in_review", "false_positive", "confirmed", "suppressed"],
    "in_review": ["false_positive", "confirmed", "new"],
    "false_positive": ["new", "in_review"],
    "confirmed": ["in_review"],  # bestätigt → wird i.d.R. zum Incident eskaliert
    "suppressed": ["new"],
}


# ── Incident-Status-Maschine (NIST SP 800-61 / ISO 27035) ───────────────────
INCIDENT_STATES = [
    "new", "in_review", "false_positive", "confirmed",
    "contained", "eradicated", "resolved", "closed", "reopened",
]

INCIDENT_TRANSITIONS: dict[str, list[str]] = {
    "new": ["in_review", "false_positive"],
    "in_review": ["false_positive", "confirmed"],
    "false_positive": ["closed", "reopened"],
    "confirmed": ["contained"],
    "contained": ["eradicated", "resolved"],
    "eradicated": ["resolved"],
    "resolved": ["closed", "reopened"],
    "closed": ["reopened"],
    "reopened": ["in_review", "confirmed"],
}

# Status, ab denen ein Incident als „offen/aktiv" gilt (für KPIs/Cockpit)
INCIDENT_OPEN_STATES = {
    "new", "in_review", "confirmed", "contained", "eradicated", "reopened",
}

# Post-Incident-Review-Maßnahmen (#1316)
PIR_ACTION_STATES = ["offen", "in_arbeit", "erledigt"]

# Detection-Use-Cases (#1321)
DETECTION_STATES = ["aktiv", "tuning", "geplant", "ausser_betrieb"]

# SOC-Übungen (#1319)
UEBUNG_TYPES = ["tabletop", "detection_test"]
UEBUNG_STATES = ["geplant", "durchgefuehrt", "ausgewertet"]
UEBUNG_ERGEBNIS = ["offen", "bestanden", "teilweise", "nicht_bestanden"]
# ISO-22398-Lebenszyklus + Performance-Objective-Typen + Bewertungen (#1351)
UEBUNG_LIFECYCLE = ["design", "develop", "conduct", "evaluate", "improve"]
UEBUNG_ZIEL_TYPES = ["orientation", "learning", "cooperation", "experimenting", "testing"]
UEBUNG_ZIEL_BEWERTUNG = ["offen", "erfuellt", "teilweise", "nicht_erfuellt"]
UEBUNG_INJECT_STATES = ["geplant", "injiziert", "bewaeltigt", "verpasst"]
UEBUNG_MASS_STATES = ["offen", "in_arbeit", "erledigt"]
# Vor dem endgültigen 'closed' muss bei echten (eskalierten) Incidents ein PIR mit
# Root-Cause vorliegen. False-Positives (Pfad new→false_positive→closed) sind ausgenommen.
PIR_REQUIRED_BEFORE_CLOSE_FROM = {"resolved", "contained", "eradicated"}


def can_transition(current: str, target: str, *, incident: bool = False) -> bool:
    table = INCIDENT_TRANSITIONS if incident else ALERT_TRANSITIONS
    return target in table.get(current, [])


# ── Meldepflicht-Regime (Router #1281) ──────────────────────────────────────
# Jedes Regime: durch welches Asset-Flag ausgelöst, Rechtsgrundlage, Fristen
# (in Stunden ab Awareness, None = kein fixes Limit), Zielmodul.
REGIMES: dict[str, dict] = {
    "dsgvo": {
        "label": "DSGVO Datenpanne",
        "trigger_flag": "personenbezogen",
        "legal": "Art. 33/34 DSGVO",
        "deadlines": [
            {"key": "art33_meldung", "label": "Meldung an Aufsichtsbehörde", "hours": 72},
            {"key": "art34_betroffene", "label": "Benachrichtigung Betroffener (bei hohem Risiko)", "hours": None},
        ],
        "target_module": "dsgvo",
    },
    "nis2": {
        "label": "NIS2 Sicherheitsvorfall",
        "trigger_flag": "nis2_scope",
        "legal": "Art. 23 NIS2",
        "deadlines": [
            {"key": "fruehwarnung", "label": "Frühwarnung", "hours": 24},
            {"key": "meldung", "label": "Meldung", "hours": 72},
            {"key": "abschluss", "label": "Abschlussbericht", "hours": 24 * 30},
        ],
        "target_module": "nis2",
    },
    "cra": {
        "label": "CRA-Vorfall / aktiv ausgenutzte Schwachstelle",
        "trigger_flag": "cra_produkt",
        "legal": "Art. 14 CRA",
        "deadlines": [
            {"key": "fruehwarnung", "label": "Frühwarnung an ENISA", "hours": 24},
            {"key": "meldung", "label": "Meldung", "hours": 72},
            {"key": "abschluss", "label": "Abschlussbericht", "hours": 24 * 14},
        ],
        "target_module": "cra",
    },
    "aiact": {
        "label": "AI-Act schwerer Vorfall (Hochrisiko-KI)",
        "trigger_flag": "ki_hochrisiko",
        "legal": "Art. 73 AI-Act",
        "deadlines": [
            {"key": "meldung", "label": "Meldung an Marktüberwachung", "hours": 24 * 15},
        ],
        "target_module": "aiact",
    },
    "dora": {
        "label": "DORA schwerwiegender ICT-Vorfall (Stub)",
        "trigger_flag": "dora_scope",
        "legal": "Art. 19 DORA",
        "deadlines": [
            {"key": "erstmeldung", "label": "Erstmeldung", "hours": 24},
        ],
        "target_module": "dora",
        "stub": True,
    },
}

# Asset-Flags, die der Router auswertet
ASSET_FLAGS = ["personenbezogen", "nis2_scope", "cra_produkt", "ki_hochrisiko", "dora_scope"]

# ── Verbindungsmodi ─────────────────────────────────────────────────────────
CONNECTION_MODES = ["pull", "push"]
DEFAULT_INDEX_PATTERN = "wazuh-alerts-*"
DEFAULT_MIN_LEVEL = 7
DEFAULT_INDEXER_PORT = 9200


# ── Schwachstellen-Register (#1343) ─────────────────────────────────────────
# Eigener States-Index (Ist-Zustand der Vulnerability-Detection, nicht Alarme).
DEFAULT_VULN_INDEX_PATTERN = "wazuh-states-vulnerabilities-*"

# Suite-seitige, leichte Triage. Default 'new' = nur erfasst/informativ.
VULN_TRIAGE_STATES = ["new", "acknowledged", "risk_accepted", "false_positive", "promoted"]

# Wazuh-States-Status (vulnerability.under_evaluation / state):
#   "Active"  → CVE auf dem Host aktiv vorhanden
#   "Solved"  → in Wazuh als behoben markiert (oder beim Reconcile verschwunden)
VULN_WAZUH_ACTIVE = "Active"
VULN_WAZUH_SOLVED = "Solved"

# Wazuh-Severity-Strings (vulnerability.severity) → Suite-Severity (SEVERITIES).
_VULN_SEVERITY_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "moderate": "medium",
    "low": "low",
    "none": "low",
    "untriaged": "low",
    "unknown": "low",
}


def severity_from_vuln(value: str | None, cvss_score: float | None = None) -> str:
    """Normalisiert die Wazuh-States-Severity (Wort) bzw. den CVSS-Score → SEVERITIES."""
    s = str(value or "").strip().lower()
    if s in _VULN_SEVERITY_MAP:
        return _VULN_SEVERITY_MAP[s]
    # Fallback über CVSS-Base-Score (CVSS v3.x-Schwellen)
    try:
        c = float(cvss_score)
    except (TypeError, ValueError):
        return "low"
    if c >= 9.0:
        return "critical"
    if c >= 7.0:
        return "high"
    if c >= 4.0:
        return "medium"
    return "low"
