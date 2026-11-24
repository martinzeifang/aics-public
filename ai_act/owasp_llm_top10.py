"""Minimal OWASP Top 10 for LLM Applications overlay dataset.

We store only short titles + reference links (no long text).
"""

from __future__ import annotations

from typing import Any


OWASP_LLM_TOP10_REF = "https://owasp.org/www-project-top-10-for-large-language-model-applications/"


OWASP_LLM_TOP10: list[dict[str, Any]] = [
    {"id": "LLM01", "title": "Prompt Injection", "ref": OWASP_LLM_TOP10_REF, "maps_to": ["AIA-HR-07", "AIA-HR-05"]},
    {"id": "LLM02", "title": "Insecure Output Handling", "ref": OWASP_LLM_TOP10_REF, "maps_to": ["AIA-HR-07"]},
    {"id": "LLM03", "title": "Training Data Poisoning", "ref": OWASP_LLM_TOP10_REF, "maps_to": ["AIA-HR-02", "AIA-DATA-01"]},
    {"id": "LLM04", "title": "Model Denial of Service", "ref": OWASP_LLM_TOP10_REF, "maps_to": ["AIA-HR-07", "AIA-HR-08"]},
    {"id": "LLM05", "title": "Supply Chain Vulnerabilities", "ref": OWASP_LLM_TOP10_REF, "maps_to": ["AIA-HR-07"]},
    {"id": "LLM06", "title": "Sensitive Information Disclosure", "ref": OWASP_LLM_TOP10_REF, "maps_to": ["AIA-HR-05", "AIA-HR-04"]},
    {"id": "LLM07", "title": "Insecure Plugin Design", "ref": OWASP_LLM_TOP10_REF, "maps_to": ["AIA-HR-07"]},
    {"id": "LLM08", "title": "Excessive Agency", "ref": OWASP_LLM_TOP10_REF, "maps_to": ["AIA-HR-06", "AIA-HR-05"]},
    {"id": "LLM09", "title": "Overreliance", "ref": OWASP_LLM_TOP10_REF, "maps_to": ["AIA-HR-05", "AIA-HR-06"]},
    {"id": "LLM10", "title": "Model Theft", "ref": OWASP_LLM_TOP10_REF, "maps_to": ["AIA-HR-07"]},
]


# Phase E A21 — OWASP-LLM-Top-10-Watch (#547)
# Heuristik-Signale aus Pflicht-Doku, die eine Kategorie "mitigiert"/"offen" markieren

WATCH_STATUS_RULES: dict[str, dict[str, Any]] = {
    "LLM01": {  # Prompt Injection
        "system_doku_keywords": ["prompt", "injection", "sanitiz", "input-filter", "guardrail"],
        "field": "cybersecurity_measures",
    },
    "LLM02": {  # Insecure Output Handling
        "system_doku_keywords": ["output", "sanitiz", "encod", "escape"],
        "field": "cybersecurity_measures",
    },
    "LLM03": {  # Training Data Poisoning
        "data_gov_keywords": ["bias", "data-quality", "provenance", "vetting", "filter"],
        "field": "bias_mitigation",
    },
    "LLM04": {  # Model DoS
        "system_doku_keywords": ["rate-limit", "throttl", "quota", "circuit-breaker"],
        "field": "cybersecurity_measures",
    },
    "LLM05": {  # Supply Chain
        "system_doku_keywords": ["sbom", "supply-chain", "vendor", "dependency-scan"],
        "field": "cybersecurity_measures",
    },
    "LLM06": {  # Sensitive Info Disclosure
        "system_doku_keywords": ["pii", "redact", "sensitive", "dlp", "anonym"],
        "field": "cybersecurity_measures",
    },
    "LLM07": {  # Insecure Plugin Design
        "system_doku_keywords": ["plugin", "tool", "sandbox", "allow-list", "scope"],
        "field": "cybersecurity_measures",
    },
    "LLM08": {  # Excessive Agency
        "oversight_keywords": ["human-in-the-loop", "approval", "consent", "veto"],
        "field": "intervention_mechanisms",
    },
    "LLM09": {  # Overreliance
        "oversight_keywords": ["disclaimer", "transparenz", "transparency", "user-warning"],
        "field": "intervention_mechanisms",
    },
    "LLM10": {  # Model Theft
        "system_doku_keywords": ["rate-limit", "watermark", "extraction", "fingerprint"],
        "field": "cybersecurity_measures",
    },
}


def compute_watch_status(system_doku: dict[str, Any] | None,
                         data_governance: dict[str, Any] | None,
                         oversight: dict[str, Any] | None) -> list[dict[str, Any]]:
    """OWASP-LLM-Top-10-Watch — pro Kategorie ein Status-Eintrag.

    Heuristik: wenn ein Mitigation-Keyword in den jeweiligen Pflicht-Doku-Feldern
    auftaucht, gilt die Kategorie als "mitigiert". Sonst "offen". `n.a.` wenn das
    System nicht LLM-basiert ist (architecture enthält 'LLM'/'GPT'/'transformer').
    """
    sd = system_doku or {}
    dg = data_governance or {}
    ho = oversight or {}

    arch = (sd.get("architecture") or "").lower()
    is_llm = any(t in arch for t in ("llm", "gpt", "transformer", "language model", "language-model"))

    rows: list[dict[str, Any]] = []
    for cat in OWASP_LLM_TOP10:
        cat_id = cat["id"]
        rule = WATCH_STATUS_RULES.get(cat_id, {})
        if not is_llm:
            status, hint = "n.a.", "System ist nicht als LLM-Architektur dokumentiert"
        else:
            mitigated = False
            matched_keyword = ""
            for src, src_keys in (
                (sd, "system_doku_keywords"),
                (dg, "data_gov_keywords"),
                (ho, "oversight_keywords"),
            ):
                kws = rule.get(src_keys) or []
                if not kws:
                    continue
                blob = " ".join(str(v) for v in src.values() if isinstance(v, str)).lower()
                for kw in kws:
                    if kw in blob:
                        mitigated = True
                        matched_keyword = kw
                        break
                if mitigated:
                    break
            status = "mitigiert" if mitigated else "offen"
            hint = f"Hinweis im Feld gefunden: '{matched_keyword}'" if mitigated else \
                   f"Kein Mitigation-Beleg gefunden im Feld {rule.get('field', 'n.a.')}"
        rows.append({
            "owasp_id": cat_id,
            "title": cat["title"],
            "ref": cat["ref"],
            "maps_to": cat["maps_to"],
            "status": status,
            "hint": hint,
        })
    return rows
