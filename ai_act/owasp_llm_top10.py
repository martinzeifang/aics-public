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
