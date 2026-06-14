"""OWASP-LLM-Erkennung aus SOC-Alarmen (#1286, nice-to-have).

Heuristik: Wazuh-Alarme, deren Regel/Gruppen/Log auf KI-spezifische Angriffe
hindeuten, werden einer OWASP-LLM-Top-10-Kategorie zugeordnet. Treffer können in
das AI-Act-OWASP-LLM-Register (`aiact_owasp_llm_checks`) als Evidenz gepusht werden,
um Art. 9/Art. 15 additiv zu stützen.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from soc import db as sdb

# Stichwort → OWASP-LLM-ID (Schlüsselwörter klein, Substring-Match)
LLM_KEYWORDS: list[tuple[str, str]] = [
    ("prompt injection", "LLM01"), ("prompt-injection", "LLM01"),
    ("jailbreak", "LLM01"), ("ignore previous instructions", "LLM01"),
    ("insecure output", "LLM02"),
    ("training data poison", "LLM03"), ("data poisoning", "LLM03"),
    ("model dos", "LLM04"), ("llm dos", "LLM04"), ("token flood", "LLM04"),
    ("sensitive disclosure", "LLM06"), ("prompt leak", "LLM06"), ("system prompt leak", "LLM06"),
    ("insecure plugin", "LLM07"),
    ("excessive agency", "LLM08"),
    ("model theft", "LLM10"), ("model extraction", "LLM10"),
]

LLM_TITLES = {
    "LLM01": "Prompt Injection", "LLM02": "Insecure Output Handling",
    "LLM03": "Training Data Poisoning", "LLM04": "Model Denial of Service",
    "LLM05": "Supply Chain Vulnerabilities", "LLM06": "Sensitive Information Disclosure",
    "LLM07": "Insecure Plugin Design", "LLM08": "Excessive Agency",
    "LLM09": "Overreliance", "LLM10": "Model Theft",
}


def _match_llm(alert: dict[str, Any]) -> str | None:
    hay = " ".join([
        str(alert.get("description", "")),
        " ".join(alert.get("groups", []) or []),
        str(alert.get("full_log", "")),
    ]).lower()
    # Nur betrachten, wenn überhaupt ein KI/LLM-Bezug erkennbar ist
    if not any(k in hay for k in ("llm", "prompt", "model", "ai ", "genai", "chatbot")):
        return None
    for kw, llm_id in LLM_KEYWORDS:
        if kw in hay:
            return llm_id
    return None


def detect_llm_alerts(db_path: Path) -> list[dict[str, Any]]:
    """Gruppiert KI-relevante Alarme nach OWASP-LLM-Kategorie."""
    sdb.ensure_db(db_path)
    by_id: dict[str, dict[str, Any]] = {}
    for a in sdb.list_alerts(db_path, limit=5000):
        llm_id = _match_llm(a)
        if not llm_id:
            continue
        entry = by_id.setdefault(llm_id, {"llm_id": llm_id, "title": LLM_TITLES.get(llm_id, llm_id),
                                          "count": 0, "samples": []})
        entry["count"] += 1
        if len(entry["samples"]) < 3:
            entry["samples"].append({"alert_uid": a.get("alert_uid"), "description": a.get("description"),
                                     "agent": a.get("agent_name"), "ts": a.get("event_ts")})
    return sorted(by_id.values(), key=lambda e: e["llm_id"])


def push_to_aiact(db_path: Path, aiact_db: Path, projekt_name: str) -> dict[str, Any]:
    """Schreibt die SOC-Treffer als Evidenz in das AI-Act-OWASP-LLM-Register."""
    from ai_act import db as adb
    detections = detect_llm_alerts(db_path)
    if not detections:
        return {"ok": True, "pushed": 0, "hinweis": "Keine KI-spezifischen Alarme erkannt."}
    pushed = 0
    for det in detections:
        evidence = [{"quelle": "soc", "alert_uid": s.get("alert_uid"), "beschreibung": s.get("description")}
                    for s in det["samples"]]
        try:
            adb.upsert_owasp_llm_check(
                aiact_db, projekt_name=projekt_name, llm_id=det["llm_id"], status=1,
                kommentar=f"SOC erkannte {det['count']} Alarm(e) zu {det['title']} (Detektion vorhanden).",
                evidence=evidence)
            pushed += 1
        except Exception:  # noqa: BLE001
            continue
    return {"ok": True, "pushed": pushed, "detections": detections}
