"""Framework definitions: scales, scoring logic, and explanatory texts.

Each framework exposes:
  framework_felder(fw)   -> list[dict]   – input field descriptors
  berechne_risiko(fw, d) -> (score, label, detail_str)
  FRAMEWORK_ERKLAERUNG   – dict of explanation texts (for info panel)
"""
from __future__ import annotations

# ── Scale tables ──────────────────────────────────────────────────────────────

_FI_LIKELIHOOD = [
    ("Unwahrscheinlich", 1),
    ("Möglich", 2),
    ("Wahrscheinlich", 3),
    ("Sehr wahrscheinlich", 4),
]
_FI_IMPACT = [
    ("Niedrig", 1),
    ("Mittel", 2),
    ("Hoch", 3),
    ("Sehr hoch", 4),
]

_STRIDE_LIKELIHOOD = [
    ("Sehr unwahrscheinlich", 1),
    ("Unwahrscheinlich", 2),
    ("Möglich", 3),
    ("Wahrscheinlich", 4),
    ("Sehr wahrscheinlich", 5),
]
_STRIDE_IMPACT = [
    ("Vernachlässigbar", 1),
    ("Gering", 2),
    ("Mittel", 3),
    ("Hoch", 4),
    ("Kritisch", 5),
]
STRIDE_KATEGORIEN = [
    "Spoofing (S) – Identitätsfälschung",
    "Tampering (T) – Manipulation von Daten",
    "Repudiation (R) – Abstreitbarkeit von Aktionen",
    "Information Disclosure (I) – Informationsoffenbarung",
    "Denial of Service (D) – Dienstverweigerung",
    "Elevation of Privilege (E) – Rechteerweiterung",
]

# EU AI Act (Art. 9) — Risikomanagement für Hochrisiko-KI-Systeme (#1044).
EU_AI_ACT_LIFECYCLE = ["design", "development", "deployment", "monitoring"]
EU_AI_ACT_RISK_KATEGORIEN = [
    "safety – Gesundheit & Sicherheit",
    "fundamental-rights – Grundrechte",
    "bias – Diskriminierung/Verzerrung",
    "security – Cybersicherheit",
    "other – Sonstiges",
]

# STRIDE-LLM: LLM-spezifische Bedrohungs-Kategorien nach OWASP LLM Top 10 + AI Act #540
STRIDE_LLM_KATEGORIEN = [
    "Prompt-Injection (LLM01) – direkte/indirekte Manipulation des Modells via Eingabe",
    "Insecure-Output-Handling (LLM02) – Output ungeprüft in Downstream-System ausgeführt",
    "Training-Data-Poisoning (LLM03) – Manipulation der Trainingsdaten",
    "Model-DoS (LLM04) – ressourcenintensive Anfragen, Token-Flooding",
    "Supply-Chain (LLM05) – kompromittierte Modelle/Plugins/Datasets",
    "Sensitive-Information-Disclosure (LLM06) – PII-Leakage über Output",
    "Insecure-Plugin-Design (LLM07) – Plugins ohne Input-Validation/Auth",
    "Excessive-Agency (LLM08) – LLM hat zu weitreichende Aktions-Rechte",
    "Overreliance (LLM09) – User vertraut LLM-Output blind",
    "Model-Theft (LLM10) – Modell-Extraktion via Query-Probing",
    "Bias & Discrimination – diskriminierende Outputs auf geschützte Merkmale",
    "Hallucination – plausibel klingende falsche Fakten",
]

_AP_EXPERTISE = [
    ("Laie", 0),
    ("Fachkenntnis", 2),
    ("Experte", 4),
    ("Mehrere Experten", 6),
]
_AP_KNOWLEDGE = [
    ("Öffentlich", 0),
    ("Eingeschränkt", 2),
    ("Sensibel", 5),
    ("Kritisch", 7),
]
_AP_WINDOW = [
    ("Unbegrenzt", 0),
    ("Leicht erreichbar", 1),
    ("Moderat", 4),
    ("Schwierig", 10),
]
_AP_EQUIPMENT = [
    ("Standard", 0),
    ("Spezialisiert", 2),
    ("Maßgeschneidert", 5),
    ("Mehrfach maßgefertigt", 8),
]
_AP_ELAPSED = [
    ("≤ 1 Woche", 0),
    ("≤ 1 Monat", 1),
    ("≤ 6 Monate", 4),
    ("> 6 Monate", 17),
]
_IMPACT_5 = [
    ("Kein Schaden", 0),
    ("Gering", 1),
    ("Mittel", 2),
    ("Schwerwiegend", 3),
    ("Kritisch", 4),
]
_IMPACT_4 = [
    ("Vernachlässigbar", 1),
    ("Moderat", 2),
    ("Schwerwiegend", 3),
    ("Kritisch", 4),
]

# DSGVO-DSFA (Art. 35 Abs. 7 lit. c + d) — Risiken für Rechte und Freiheiten
# natürlicher Personen + Abhilfemaßnahmen (#1084/#1085). Likelihood × Severity,
# beides 4-stufig (an die Vorgaben des EDSA WP248 angelehnt).
_DSFA_LIKELIHOOD = [
    ("Vernachlässigbar", 1),
    ("Begrenzt", 2),
    ("Erheblich", 3),
    ("Maximal", 4),
]
_DSFA_SEVERITY = [
    ("Vernachlässigbar", 1),
    ("Begrenzt", 2),
    ("Erheblich", 3),
    ("Maximal", 4),
]

_OCTAVE_ACTOR = ["Extern", "Intern", "Technisch / Unfall"]
_OCTAVE_MOTIVE = ["Absichtlich", "Unbeabsichtigt / Versehen"]
_OCTAVE_ACCESS = ["Physisch", "Netzwerk", "System", "Anwendungsebene"]
_OCTAVE_PROB = [
    ("Niedrig", 1),
    ("Mittel", 2),
    ("Hoch", 3),
]
_OCTAVE_IMPACT = [
    ("Kein Einfluss", 0),
    ("Niedrig", 1),
    ("Mittel", 3),
    ("Hoch", 5),
]

# ── Framework metadata ────────────────────────────────────────────────────────

FRAMEWORK_IDS = ["Finanzinstitute", "STRIDE", "STRIDE-LLM", "HEAVENS", "OCTAVE", "TARA", "EU-AI-Act", "DSGVO-DSFA"]

FRAMEWORK_LABELS = {
    "Finanzinstitute": "Risikobewertung Finanzinstitute",
    "STRIDE":          "STRIDE (Microsoft)",
    "STRIDE-LLM":      "STRIDE-LLM (OWASP LLM Top 10)",
    "HEAVENS":         "HEAVENS (Automotive/Embedded)",
    "OCTAVE":          "OCTAVE Allegro (CERT/CMU)",
    "TARA":            "TARA (ISO/SAE 21434)",
    "EU-AI-Act":       "EU AI Act (Art. 9 Risikomanagement)",
    "DSGVO-DSFA":      "DSGVO-DSFA (Art. 35 Abs. 7 c+d)",
}

# ── Field descriptors ─────────────────────────────────────────────────────────

def framework_felder(framework: str) -> list[dict]:
    """Return field descriptors for a framework.
    Each dict: {key, label, typ ('combo'|'text_info'), optionen, gruppe}
    """
    if framework == "Finanzinstitute":
        return [
            {"key": "eintrittswahrscheinlichkeit", "label": "Eintrittswahrscheinlichkeit",
             "typ": "combo", "optionen": _labels(_FI_LIKELIHOOD), "gruppe": "Bewertung"},
            {"key": "schadenspotenzial",            "label": "Schadenspotenzial",
             "typ": "combo", "optionen": _labels(_FI_IMPACT),     "gruppe": "Bewertung"},
        ]

    if framework == "STRIDE":
        return [
            {"key": "stride_kategorie",             "label": "STRIDE-Kategorie",
             "typ": "combo", "optionen": STRIDE_KATEGORIEN,               "gruppe": "Klassifikation"},
            {"key": "eintrittswahrscheinlichkeit",  "label": "Eintrittswahrscheinlichkeit",
             "typ": "combo", "optionen": _labels(_STRIDE_LIKELIHOOD),     "gruppe": "Bewertung"},
            {"key": "auswirkung",                   "label": "Auswirkung (Impact)",
             "typ": "combo", "optionen": _labels(_STRIDE_IMPACT),         "gruppe": "Bewertung"},
        ]

    if framework == "EU-AI-Act":
        return [
            {"key": "lifecycle_phase",              "label": "Lebenszyklus-Phase (Art. 9)",
             "typ": "combo", "optionen": EU_AI_ACT_LIFECYCLE,            "gruppe": "Klassifikation"},
            {"key": "risk_category",                "label": "Risiko-Kategorie",
             "typ": "combo", "optionen": EU_AI_ACT_RISK_KATEGORIEN,      "gruppe": "Klassifikation"},
            {"key": "eintrittswahrscheinlichkeit",  "label": "Eintrittswahrscheinlichkeit",
             "typ": "combo", "optionen": _labels(_STRIDE_LIKELIHOOD),     "gruppe": "Bewertung"},
            {"key": "auswirkung",                   "label": "Auswirkung (Impact)",
             "typ": "combo", "optionen": _labels(_STRIDE_IMPACT),         "gruppe": "Bewertung"},
        ]

    if framework == "DSGVO-DSFA":
        return [
            {"key": "bedrohung_rechte_freiheiten",  "label": "Bedrohung für Rechte/Freiheiten der Betroffenen (Art. 35 Abs. 7 lit. c)",
             "typ": "text_info",                                          "gruppe": "Risiko (Art. 35 Abs. 7 c)"},
            {"key": "eintrittswahrscheinlichkeit",  "label": "Eintrittswahrscheinlichkeit",
             "typ": "combo", "optionen": _labels(_DSFA_LIKELIHOOD),        "gruppe": "Risiko (Art. 35 Abs. 7 c)"},
            {"key": "schwere",                      "label": "Schwere des Schadens",
             "typ": "combo", "optionen": _labels(_DSFA_SEVERITY),          "gruppe": "Risiko (Art. 35 Abs. 7 c)"},
            {"key": "massnahme",                    "label": "Technische/organisatorische Abhilfemaßnahme (Art. 35 Abs. 7 lit. d)",
             "typ": "text_info",                                          "gruppe": "Maßnahme (Art. 35 Abs. 7 d)"},
            {"key": "restrisiko",                   "label": "Verbleibendes Restrisiko nach Maßnahme (Art. 35 Abs. 7 lit. d / Art. 36)",
             "typ": "combo", "optionen": ["niedrig", "mittel", "hoch"],   "gruppe": "Maßnahme (Art. 35 Abs. 7 d)"},
        ]

    if framework == "STRIDE-LLM":
        return [
            {"key": "stride_llm_kategorie",         "label": "STRIDE-LLM-Kategorie",
             "typ": "combo", "optionen": STRIDE_LLM_KATEGORIEN,           "gruppe": "Klassifikation"},
            {"key": "eintrittswahrscheinlichkeit",  "label": "Eintrittswahrscheinlichkeit",
             "typ": "combo", "optionen": _labels(_STRIDE_LIKELIHOOD),     "gruppe": "Bewertung"},
            {"key": "auswirkung",                   "label": "Auswirkung (Impact)",
             "typ": "combo", "optionen": _labels(_STRIDE_IMPACT),         "gruppe": "Bewertung"},
            {"key": "ai_system_ref",                "label": "Bezogenes AI-System (optional)",
             "typ": "text_info",                                          "gruppe": "Klassifikation"},
        ]

    if framework == "HEAVENS":
        return [
            {"key": "ap_expertise",    "label": "Expertise des Angreifers",
             "typ": "combo", "optionen": _labels(_AP_EXPERTISE), "gruppe": "Angriffspotenzial"},
            {"key": "ap_knowledge",    "label": "Kenntnisstand über System",
             "typ": "combo", "optionen": _labels(_AP_KNOWLEDGE), "gruppe": "Angriffspotenzial"},
            {"key": "ap_window",       "label": "Zeitfenster für Angriff",
             "typ": "combo", "optionen": _labels(_AP_WINDOW),    "gruppe": "Angriffspotenzial"},
            {"key": "ap_equipment",    "label": "Erforderliche Ausrüstung",
             "typ": "combo", "optionen": _labels(_AP_EQUIPMENT), "gruppe": "Angriffspotenzial"},
            {"key": "impact_safety",   "label": "Impact: Sicherheit (Safety)",
             "typ": "combo", "optionen": _labels(_IMPACT_5),     "gruppe": "Impact (SFOP)"},
            {"key": "impact_financial","label": "Impact: Finanzen",
             "typ": "combo", "optionen": _labels(_IMPACT_5),     "gruppe": "Impact (SFOP)"},
            {"key": "impact_operational","label": "Impact: Betrieb (Operational)",
             "typ": "combo", "optionen": _labels(_IMPACT_5),     "gruppe": "Impact (SFOP)"},
            {"key": "impact_privacy",  "label": "Impact: Datenschutz (Privacy)",
             "typ": "combo", "optionen": _labels(_IMPACT_5),     "gruppe": "Impact (SFOP)"},
        ]

    if framework == "OCTAVE":
        return [
            {"key": "octave_actor",    "label": "Bedrohungsakteur",
             "typ": "combo", "optionen": _OCTAVE_ACTOR,           "gruppe": "Bedrohungsprofil"},
            {"key": "octave_motive",   "label": "Motivation",
             "typ": "combo", "optionen": _OCTAVE_MOTIVE,          "gruppe": "Bedrohungsprofil"},
            {"key": "octave_access",   "label": "Angriffsweg",
             "typ": "combo", "optionen": _OCTAVE_ACCESS,          "gruppe": "Bedrohungsprofil"},
            {"key": "octave_prob",     "label": "Eintrittswahrscheinlichkeit",
             "typ": "combo", "optionen": _labels(_OCTAVE_PROB),   "gruppe": "Wahrscheinlichkeit"},
            {"key": "impact_rep",      "label": "Impact: Reputation",
             "typ": "combo", "optionen": _labels(_OCTAVE_IMPACT), "gruppe": "Impact-Bereiche"},
            {"key": "impact_fin",      "label": "Impact: Finanzen",
             "typ": "combo", "optionen": _labels(_OCTAVE_IMPACT), "gruppe": "Impact-Bereiche"},
            {"key": "impact_prod",     "label": "Impact: Produktivität",
             "typ": "combo", "optionen": _labels(_OCTAVE_IMPACT), "gruppe": "Impact-Bereiche"},
            {"key": "impact_safety",   "label": "Impact: Sicherheit / Gesundheit",
             "typ": "combo", "optionen": _labels(_OCTAVE_IMPACT), "gruppe": "Impact-Bereiche"},
            {"key": "impact_fines",    "label": "Impact: Bußgelder / Strafen",
             "typ": "combo", "optionen": _labels(_OCTAVE_IMPACT), "gruppe": "Impact-Bereiche"},
        ]

    if framework == "TARA":
        return [
            {"key": "ap_elapsed",      "label": "Zeitaufwand für Angriff",
             "typ": "combo", "optionen": _labels(_AP_ELAPSED),   "gruppe": "Angriffsrealisierbarkeit"},
            {"key": "ap_expertise",    "label": "Expertise des Angreifers",
             "typ": "combo", "optionen": _labels(_AP_EXPERTISE), "gruppe": "Angriffsrealisierbarkeit"},
            {"key": "ap_knowledge",    "label": "Kenntnisstand über System",
             "typ": "combo", "optionen": _labels(_AP_KNOWLEDGE), "gruppe": "Angriffsrealisierbarkeit"},
            {"key": "ap_window",       "label": "Zeitfenster für Angriff",
             "typ": "combo", "optionen": _labels(_AP_WINDOW),    "gruppe": "Angriffsrealisierbarkeit"},
            {"key": "ap_equipment",    "label": "Erforderliche Ausrüstung",
             "typ": "combo", "optionen": _labels(_AP_EQUIPMENT), "gruppe": "Angriffsrealisierbarkeit"},
            {"key": "impact_safety",   "label": "Impact: Sicherheit (Safety)",
             "typ": "combo", "optionen": _labels(_IMPACT_4),     "gruppe": "Impact (SFOP)"},
            {"key": "impact_financial","label": "Impact: Finanzen (Financial)",
             "typ": "combo", "optionen": _labels(_IMPACT_4),     "gruppe": "Impact (SFOP)"},
            {"key": "impact_operational","label": "Impact: Betrieb (Operational)",
             "typ": "combo", "optionen": _labels(_IMPACT_4),     "gruppe": "Impact (SFOP)"},
            {"key": "impact_privacy",  "label": "Impact: Datenschutz (Privacy)",
             "typ": "combo", "optionen": _labels(_IMPACT_4),     "gruppe": "Impact (SFOP)"},
        ]

    return []


# ── Scoring ───────────────────────────────────────────────────────────────────

def berechne_risiko(framework: str, felder: dict) -> tuple[int | None, str, str]:
    """Return (score, label, detail_text). score=None if inputs incomplete."""
    if framework == "Finanzinstitute":
        lw = _wert(_FI_LIKELIHOOD, felder.get("eintrittswahrscheinlichkeit", ""))
        iw = _wert(_FI_IMPACT,     felder.get("schadenspotenzial", ""))
        if lw is None or iw is None:
            return None, "", ""
        score = lw + iw - 1
        labels = {1: "Nicht relevant", 2: "Nicht relevant", 3: "Vernachlässigbar",
                  4: "Gering", 5: "Relevant", 6: "Äußerst relevant", 7: "Existenzbedrohend"}
        detail = f"EW={lw} + SP={iw} − 1 = {score}"
        return score, labels.get(score, ""), detail

    if framework == "STRIDE":
        lw = _wert(_STRIDE_LIKELIHOOD, felder.get("eintrittswahrscheinlichkeit", ""))
        iw = _wert(_STRIDE_IMPACT,     felder.get("auswirkung", ""))
        if lw is None or iw is None:
            return None, "", ""
        score = lw * iw
        if score <= 4:   label = "Sehr niedrig"
        elif score <= 9: label = "Niedrig"
        elif score <= 14: label = "Mittel"
        elif score <= 19: label = "Hoch"
        else:             label = "Kritisch"
        detail = f"Wahrscheinlichkeit={lw} × Impact={iw} = {score}"
        return score, label, detail

    if framework == "EU-AI-Act":
        # 5x5-Skala (Likelihood × Impact) analog STRIDE, AI-Act-Labels.
        lw = _wert(_STRIDE_LIKELIHOOD, felder.get("eintrittswahrscheinlichkeit", ""))
        iw = _wert(_STRIDE_IMPACT,     felder.get("auswirkung", ""))
        if lw is None or iw is None:
            return None, "", ""
        score = lw * iw
        if score <= 4:   label = "Sehr niedrig"
        elif score <= 9: label = "Niedrig"
        elif score <= 14: label = "Mittel"
        elif score <= 19: label = "Hoch"
        else:             label = "Kritisch"
        phase = felder.get("lifecycle_phase", "")
        cat = felder.get("risk_category", "")
        detail = f"Wahrscheinlichkeit={lw} × Impact={iw} = {score}"
        extra = " · ".join(x for x in (phase, cat.split('–')[0].strip() if cat else "") if x)
        if extra:
            detail += f" · {extra}"
        return score, label, detail

    if framework == "DSGVO-DSFA":
        # Art. 35 Abs. 7 lit. c: Eintrittswahrscheinlichkeit × Schwere (4×4).
        lw = _wert(_DSFA_LIKELIHOOD, felder.get("eintrittswahrscheinlichkeit", ""))
        sw = _wert(_DSFA_SEVERITY,   felder.get("schwere", ""))
        if lw is None or sw is None:
            return None, "", ""
        score = lw * sw
        if score <= 2:    label = "Niedrig"
        elif score <= 6:  label = "Mittel"
        elif score <= 9:  label = "Hoch"
        else:             label = "Sehr hoch"
        detail = f"Wahrscheinlichkeit={lw} × Schwere={sw} = {score}"
        return score, label, detail

    if framework == "STRIDE-LLM":
        # Gleiche 5x5-Skala wie STRIDE
        lw = _wert(_STRIDE_LIKELIHOOD, felder.get("eintrittswahrscheinlichkeit", ""))
        iw = _wert(_STRIDE_IMPACT,     felder.get("auswirkung", ""))
        if lw is None or iw is None:
            return None, "", ""
        score = lw * iw
        if score <= 4:   label = "Sehr niedrig"
        elif score <= 9: label = "Niedrig"
        elif score <= 14: label = "Mittel"
        elif score <= 19: label = "Hoch"
        else:             label = "Kritisch"
        cat = felder.get("stride_llm_kategorie", "")
        detail = f"Wahrscheinlichkeit={lw} × Impact={iw} = {score}"
        if cat:
            detail += f" · {cat.split('–')[0].strip()}"
        return score, label, detail

    if framework == "HEAVENS":
        ap = _ap_sum_4(felder)
        if ap is None:
            return None, "", ""
        sl = _ap_zu_level(ap)
        impacts = [_wert(_IMPACT_5, felder.get(k, ""))
                   for k in ("impact_safety","impact_financial","impact_operational","impact_privacy")]
        if any(v is None for v in impacts):
            return None, "", ""
        max_i = max(impacts)  # type: ignore[arg-type]
        score = sl * max_i
        if score <= 2:   label = "Vernachlässigbar"
        elif score <= 6: label = "Niedrig"
        elif score <= 10: label = "Mittel"
        elif score <= 14: label = "Hoch"
        else:             label = "Sehr hoch"
        sl_label = {4:"SL 4 (Hoch)", 3:"SL 3 (Mittel-Hoch)", 2:"SL 2 (Mittel)", 1:"SL 1 (Niedrig)"}[sl]
        detail = f"AP={ap} → {sl_label} | max Impact={max_i} | SL×Impact={score}"
        return score, label, detail

    if framework == "OCTAVE":
        prob = _wert(_OCTAVE_PROB, felder.get("octave_prob", ""))
        if prob is None:
            return None, "", ""
        imp_keys = ("impact_rep","impact_fin","impact_prod","impact_safety","impact_fines")
        imps = [_wert(_OCTAVE_IMPACT, felder.get(k, "")) for k in imp_keys]
        if any(v is None for v in imps):
            return None, "", ""
        imp_sum = sum(imps)  # type: ignore[arg-type]
        score = prob * imp_sum
        if score <= 14:  label = "Niedrig"
        elif score <= 29: label = "Mittel"
        elif score <= 49: label = "Hoch"
        else:             label = "Kritisch"
        detail = f"Prob={prob} × Σ Impact={imp_sum} = {score}"
        return score, label, detail

    if framework == "TARA":
        elapsed = _wert(_AP_ELAPSED,    felder.get("ap_elapsed", ""))
        exp_    = _wert(_AP_EXPERTISE,  felder.get("ap_expertise", ""))
        know    = _wert(_AP_KNOWLEDGE,  felder.get("ap_knowledge", ""))
        win     = _wert(_AP_WINDOW,     felder.get("ap_window", ""))
        equip   = _wert(_AP_EQUIPMENT,  felder.get("ap_equipment", ""))
        if any(v is None for v in (elapsed, exp_, know, win, equip)):
            return None, "", ""
        ap = elapsed + exp_ + know + win + equip  # type: ignore[operator]
        afr = _ap_zu_level(ap)
        afr_label = {4:"Hoch (4)", 3:"Mittel (3)", 2:"Niedrig (2)", 1:"Sehr niedrig (1)"}[afr]
        imps = [_wert(_IMPACT_4, felder.get(k, ""))
                for k in ("impact_safety","impact_financial","impact_operational","impact_privacy")]
        if any(v is None for v in imps):
            return None, "", ""
        ir = max(imps)  # type: ignore[arg-type]
        ir_label = {4:"Kritisch (4)", 3:"Schwerwiegend (3)", 2:"Moderat (2)", 1:"Vernachlässigbar (1)"}[ir]
        matrix = {
            (1,1):1,(1,2):1,(1,3):2,(1,4):2,
            (2,1):1,(2,2):2,(2,3):3,(2,4):3,
            (3,1):2,(3,2):3,(3,3):3,(3,4):4,
            (4,1):2,(4,2):3,(4,3):4,(4,4):4,
        }
        score = matrix.get((afr, ir), 1)
        rv_labels = {1:"Akzeptabel", 2:"Niedrig", 3:"Mittel", 4:"Kritisch"}
        detail = f"AP={ap} → AFR={afr_label} | max IR={ir_label} | RV={score}"
        return score, rv_labels.get(score, ""), detail

    return None, "", ""


def risiko_farbe(label: str) -> str:
    """Return a hex color for the risk label badge."""
    l = label.lower()
    if any(w in l for w in ("nicht relevant", "vernachlässig", "akzeptabel", "sehr niedrig")):
        return "#2e7d32"
    if any(w in l for w in ("gering", "niedrig")):
        return "#f9a825"
    if any(w in l for w in ("mittel", "moderat")):
        return "#e65100"
    if any(w in l for w in ("hoch", "relevant", "kritisch", "existenz", "sehr hoch")):
        return "#b71c1c"
    return "#546e7a"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _labels(scale: list[tuple[str, int]]) -> list[str]:
    return [l for l, _ in scale]


def _wert(scale: list[tuple[str, int]], label: str) -> int | None:
    for l, v in scale:
        if l == label:
            return v
    return None


def _ap_sum_4(felder: dict) -> int | None:
    vals = [
        _wert(_AP_EXPERTISE, felder.get("ap_expertise", "")),
        _wert(_AP_KNOWLEDGE, felder.get("ap_knowledge", "")),
        _wert(_AP_WINDOW,    felder.get("ap_window", "")),
        _wert(_AP_EQUIPMENT, felder.get("ap_equipment", "")),
    ]
    if any(v is None for v in vals):
        return None
    return sum(vals)  # type: ignore[arg-type]


def _ap_zu_level(ap: int) -> int:
    """Map attack potential sum to security level 1–4 (4 = most feasible attack)."""
    if ap <= 13: return 4
    if ap <= 19: return 3
    if ap <= 24: return 2
    return 1


# ── Explanation texts ─────────────────────────────────────────────────────────

FRAMEWORK_ERKLAERUNG: dict[str, str] = {

"Finanzinstitute": """\
RISIKOBEWERTUNG FINANZINSTITUTE
================================
Ursprung & Fokus
  Branchenstandard für Finanzdienstleister; orientiert sich an BAIT, VAIT, MaRisk
  sowie den EBA-Leitlinien zur IT-Sicherheit. Wird auch als Basis für
  die Bewertung CVE eingesetzt (Modul „Bewertung CVE").

Bewertungsparameter
  ┌─────────────────────────────────────────┬──────┐
  │ Eintrittswahrscheinlichkeit             │ Wert │
  ├─────────────────────────────────────────┼──────┤
  │ Unwahrscheinlich                        │  1   │
  │ Möglich                                 │  2   │
  │ Wahrscheinlich                          │  3   │
  │ Sehr wahrscheinlich                     │  4   │
  └─────────────────────────────────────────┴──────┘
  ┌──────────────────────────────────────────┬──────┐
  │ Schadenspotenzial                        │ Wert │
  ├──────────────────────────────────────────┼──────┤
  │ Niedrig                                  │  1   │
  │ Mittel                                   │  2   │
  │ Hoch                                     │  3   │
  │ Sehr hoch                                │  4   │
  └──────────────────────────────────────────┴──────┘

Formel
  Risikowert = Eintrittswahrscheinlichkeit + Schadenspotenzial − 1
  Bereich: 1 … 7

Risikolevel
  1–2  Nicht relevant
  3    Vernachlässigbar
  4    Gering
  5    Relevant
  6    Äußerst relevant
  7    Existenzbedrohend

CRA-Relevanz
  Geeignet für Produkte und Dienstleistungen im Finanzbereich; wird durch die
  DORA-Verordnung (Digital Operational Resilience Act) ergänzt.
""",

"STRIDE": """\
STRIDE (MICROSOFT)
==================
Ursprung & Fokus
  Entwickelt von Microsoft (Kohnfelder & Garg, 1999); integraler Bestandteil des
  Microsoft Security Development Lifecycle (SDL). Klassifiziert Bedrohungen in
  sechs Kategorien, ohne eine eigene Risikoquantifizierung zu definieren.
  Dieses Modul erweitert STRIDE um eine 5×5-Matrix für die Quantifizierung.

STRIDE-Kategorien
  S – Spoofing:              Angreifer gibt sich als andere Entität aus
  T – Tampering:             Unberechtigte Änderung von Daten oder Code
  R – Repudiation:           Aktionen können nicht nachverfolgt werden
  I – Information Disclosure: Vertrauliche Daten werden offenbart
  D – Denial of Service:     Verfügbarkeit wird beeinträchtigt
  E – Elevation of Privilege: Erlangung unberechtigter Rechte

Bewertungsparameter (Erweiterung für Quantifizierung)
  Eintrittswahrscheinlichkeit: 1–5 (Sehr unwahrscheinlich … Sehr wahrscheinlich)
  Auswirkung (Impact):         1–5 (Vernachlässigbar … Kritisch)

Formel
  Risikowert = Eintrittswahrscheinlichkeit × Auswirkung
  Bereich: 1 … 25

Risikolevel
  1–4    Sehr niedrig
  5–9    Niedrig
  10–14  Mittel
  15–19  Hoch
  20–25  Kritisch

CRA-Relevanz
  STRIDE ist besonders geeignet für Bedrohungsmodellierung in der
  Softwareentwicklungsphase (Art. 13 CRA – Security by Design).
  Die Kategorisierung hilft, Gegenmaßnahmen gezielt abzuleiten.
""",

"HEAVENS": """\
HEAVENS (AUTOMOTIVE / EMBEDDED)
================================
Ursprung & Fokus
  Entwickelt von Volvo Cars Research & Technology (Wrige, 2014) auf Basis von
  ISO/SAE 21434 und Common Criteria (CC). Ursprünglich für Automotive-Systeme,
  geeignet für alle eingebetteten und cyber-physischen Systeme.

Angriffspotenzial-Bewertung (Common Criteria Methodik)
  Das Angriffspotenzial (AP) summiert vier Faktoren:
  ┌──────────────────────────────┬─────┬─────────┬────────┬──────────────────┐
  │ Faktor                       │ Wert│         │        │                  │
  ├──────────────────────────────┼─────┼─────────┼────────┼──────────────────┤
  │ Expertise                    │ L:0 │ Fach: 2 │ Exp: 4 │ Mehrere Exp.: 6  │
  │ Kenntnisstand System         │ Öff:0│ Einschr:2│ Sens:5│ Kritisch: 7     │
  │ Zeitfenster                  │ Unb:0│ Leicht:1│ Mod: 4│ Schwierig: 10   │
  │ Ausrüstung                   │ Std:0│ Spez: 2 │ Maßg:5│ Mehrfach-M: 8   │
  └──────────────────────────────┴─────┴─────────┴────────┴──────────────────┘
  AP-Summe → Security Level (SL):
    0–13  → SL 4 (Hoch – leicht angreifbar)
    14–19 → SL 3 (Mittel-Hoch)
    20–24 → SL 2 (Mittel)
    ≥ 25  → SL 1 (Niedrig – schwer angreifbar)

Impact-Bewertung (SFOP)
  Jede Dimension: Kein Schaden(0) / Gering(1) / Mittel(2) / Schwerwiegend(3) / Kritisch(4)
  S = Safety  |  F = Financial  |  O = Operational  |  P = Privacy

Formel
  Risikowert = SL × max(S, F, O, P)
  Bereich: 0 … 16

Risikolevel
  0–2    Vernachlässigbar
  3–6    Niedrig
  7–10   Mittel
  11–14  Hoch
  15–16  Sehr hoch

CRA-Relevanz
  Ideal für IoT-Geräte und Embedded-Systeme unter CRA Art. 13, 24.
  Berücksichtigt explizit Angriffspfade und SFOP-Dimensionen, die im CRA
  für wesentliche und kritische Produkte (Annex I, II) gefordert werden.
""",

"OCTAVE": """\
OCTAVE ALLEGRO (CERT / CARNEGIE MELLON)
========================================
Ursprung & Fokus
  Operationally Critical Threat, Asset, and Vulnerability Evaluation – entwickelt
  vom CERT Coordination Center der Carnegie Mellon University. OCTAVE Allegro
  (2007) ist die schlanke Variante für kleinere Teams und ist eng mit ISO 27001
  und ISMS-Implementierungen verwandt.

Bedrohungsprofil (qualitativ, dient als Kontext)
  Bedrohungsakteur: Extern / Intern / Technisch (Unfall)
  Motivation:       Absichtlich / Unbeabsichtigt
  Angriffsweg:      Physisch / Netzwerk / System / Anwendungsebene

Eintrittswahrscheinlichkeit
  Niedrig(1) / Mittel(2) / Hoch(3)

Impact-Bereiche (je: Kein(0) / Niedrig(1) / Mittel(3) / Hoch(5))
  1. Reputation / Firmenvertrauen
  2. Finanzieller Schaden
  3. Produktivitätsverlust
  4. Sicherheit / Gesundheit
  5. Bußgelder / Strafen (regulatorisch)

Formel
  Gesamt-Impact = Summe aller 5 Impact-Bereiche  (Bereich: 0–25)
  Risikowert    = Eintrittswahrscheinlichkeit × Gesamt-Impact
  Bereich: 0 … 75

Risikolevel
  0–14   Niedrig
  15–29  Mittel
  30–49  Hoch
  50–75  Kritisch

CRA-Relevanz
  OCTAVE Allegro adressiert organisatorische und technische Risiken und eignet
  sich besonders für die Betreiberperspektive. Relevant für CRA Art. 13 Abs. 2
  (Risikobewertung über den gesamten Lebenszyklus) sowie für NIS2-Pflichten.
""",

"DSGVO-DSFA": """\
DSGVO-DSFA (ART. 35 ABS. 7 LIT. c + d)
======================================
Ursprung & Fokus
  Datenschutz-Folgenabschätzung nach Art. 35 DSGVO. Dieses Framework deckt die
  beiden bewertungsrelevanten Pflichtinhalte des Art. 35 Abs. 7 ab:
    lit. c – Bewertung der Risiken für die Rechte und Freiheiten der betroffenen
             Personen,
    lit. d – die zur Bewältigung der Risiken geplanten Abhilfemaßnahmen
             (technische und organisatorische Maßnahmen).
  Die übrigen DSFA-Pflichtinhalte (lit. a Beschreibung der Verarbeitung, lit. b
  Notwendigkeit/Verhältnismäßigkeit, Art. 36 Konsultation, Art. 35 Abs. 11
  Review) verbleiben im DSGVO-Modul (dsgvo_dpia) und werden NICHT hier geführt.

Pflichtfelder
  - Bedrohung für Rechte/Freiheiten der Betroffenen (Art. 35 Abs. 7 lit. c)
  - Technische/organisatorische Abhilfemaßnahme (Art. 35 Abs. 7 lit. d)

Bewertungsparameter (EDSA WP248 angelehnt)
  Eintrittswahrscheinlichkeit: Vernachlässigbar(1) / Begrenzt(2) / Erheblich(3) / Maximal(4)
  Schwere des Schadens:        Vernachlässigbar(1) / Begrenzt(2) / Erheblich(3) / Maximal(4)

Formel
  Risikowert = Eintrittswahrscheinlichkeit × Schwere
  Bereich: 1 … 16

Risikolevel
  1–2    Niedrig
  3–6    Mittel
  7–9    Hoch
  10–16  Sehr hoch

DSGVO-Relevanz
  Bei verbleibendem hohem Risiko trotz Maßnahmen ist die Aufsichtsbehörde zu
  konsultieren (Art. 36). Die Konsultations- und Review-Verwaltung erfolgt im
  DSGVO-Modul, das auf diese Risikobewertung verweist.
""",

"TARA": """\
TARA – THREAT ANALYSIS AND RISK ASSESSMENT (ISO/SAE 21434)
============================================================
Ursprung & Fokus
  Kernmethodik der ISO/SAE 21434 „Road Vehicles – Cybersecurity Engineering"
  (2021); auch verwendet in UNECE WP.29 und für alle sicherheitskritischen
  Embedded-Systeme. Besonders geeignet für CRA-Konformitätsnachweise bei
  vernetzten Produkten (Annex I Klasse I und II).

Angriffsrealisierbarkeit (Attack Feasibility Rating, AFR)
  Fünf Faktoren nach Common Criteria:
  ┌──────────────────────┬─────────┬─────────┬────────┬──────────────────┐
  │ Zeitaufwand          │ ≤1 Woche│ ≤1 Mon. │≤6 Mon. │ > 6 Monate       │
  │ Punkte               │    0    │    1    │    4   │      17           │
  ├──────────────────────┼─────────┼─────────┼────────┼──────────────────┤
  │ Expertise            │  Laie:0 │ Fach: 2 │ Exp: 4 │ Mehr. Exp.: 6    │
  │ Kenntnisstand        │ Öff.: 0 │ Einschr:2│Sens:5 │ Kritisch: 7      │
  │ Zeitfenster          │ Unb.: 0 │ Leicht:1 │ Mod:4 │ Schwierig: 10    │
  │ Ausrüstung           │ Std.: 0 │ Spez.: 2 │Maßg:5 │ Mehrfach-M: 8    │
  └──────────────────────┴─────────┴─────────┴────────┴──────────────────┘
  AP-Summe → AFR:
    0–13  → AFR 4 = Hoch        (leicht realisierbar)
    14–19 → AFR 3 = Mittel
    20–24 → AFR 2 = Niedrig
    ≥ 25  → AFR 1 = Sehr niedrig

Impact Rating (IR)
  Dimensionen S/F/O/P je: Vernachlässigbar(1) / Moderat(2) / Schwerwiegend(3) / Kritisch(4)
  IR = max(Safety, Financial, Operational, Privacy)

Risikowert-Matrix (AFR × IR)
         │ Vernachl.(1)│ Moderat(2) │ Schwerw.(3)│ Kritisch(4)│
  ───────┼────────────┼────────────┼────────────┼────────────┤
  AFR 1  │      1     │      1     │      2     │      2     │
  AFR 2  │      1     │      2     │      3     │      3     │
  AFR 3  │      2     │      3     │      3     │      4     │
  AFR 4  │      2     │      3     │      4     │      4     │

Risikolevel
  1 – Akzeptabel    (Behandlung: Akzeptieren)
  2 – Niedrig       (Behandlung: Überwachen)
  3 – Mittel        (Behandlung: Maßnahmen erforderlich)
  4 – Kritisch      (Behandlung: Sofortige Maßnahmen / Vermeiden)

CRA-Relevanz
  TARA ist die empfohlene Methode für CRA-konforme Risikoanalysen bei
  vernetzten Produkten. Entspricht direkt Art. 13 Abs. 2 und Art. 24 CRA
  sowie ISO/IEC 27005 für die Informationssicherheitsrisikoanalyse.
""",
}
