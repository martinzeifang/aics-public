"""OWASP-LLM-Top-10-Register — Auto-Detect + KI-Wizard (Issue #1087, Sprint #21 S17).

Liefert die Status-Verwaltung für die OWASP-LLM-Top-10 mit FULL parity zum
CRA-OWASP-Panel:

- ``OWASP_LLM_TOP10`` (+ ``maps_to`` → AI-Act-Anforderungen) wird unverändert aus
  :mod:`ai_act.owasp_llm_top10` übernommen (Compliance: A1-A5/Mapping bleiben).
- **Auto-Detect** ``autodetect_owasp_llm`` scannt das Repo token-aware über
  :func:`ai_act.repo_alignment.github_path_exists` /
  :func:`ai_act.repo_alignment.github_fetch_text` (#1064-Pattern). 10
  LLM-spezifische Heuristiken (Prompt-Injection-Guards, Output-Encoding,
  Rate-Limiting, Content-Filter, PII-Redaction, Model-Pinning, Eval/Test-Harness,
  Dependency-Pinning, Secrets-Handling, Logging).
- **KI-Wizard** ``build_owasp_llm_prompt`` / ``parse_owasp_llm_response`` analog zu
  :mod:`ai_act.ai_wizards` (Prompt-Builder + Parse).

Die Heuristiken sind bewusst konservativ und liefern nur dann einen positiven
Status, wenn ein konkretes Repo-Artefakt zitierbar ist (Datei/Ordner/Treffer).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from ai_act.owasp_llm_top10 import OWASP_LLM_TOP10, OWASP_LLM_TOP10_REF
from ai_act.repo_alignment import (
    github_fetch_text,
    github_path_exists,
    parse_github_repo,
)


# ── Register-Metadaten (parity zum CRA-OWASP-Katalog: id/title/ref/maps_to) ──

def register_items() -> list[dict[str, Any]]:
    """Vollständige Item-Liste für das Frontend/Issue-Defaults.

    Enthält ``id``/``title``/``ref``/``maps_to`` (1:1 aus owasp_llm_top10) plus
    einen kurzen ``hint``, was im Repo geprüft wird (analog evidence_hint im CRA)."""
    out: list[dict[str, Any]] = []
    for it in OWASP_LLM_TOP10:
        out.append({
            "id": it["id"],
            "title": it["title"],
            "ref": it["ref"],
            "maps_to": list(it.get("maps_to") or []),
            "hint": _DETECT_HINTS.get(it["id"], ""),
        })
    return out


def find_item(llm_id: str) -> dict[str, Any] | None:
    return next((it for it in register_items() if it["id"] == llm_id), None)


# ── 10 LLM-spezifische Auto-Detect-Heuristiken ──────────────────────────────
#
# Jede Heuristik gibt (matched: bool, status: int, evidence: list[dict]) zurück.
# status nur dann > 0, wenn ein konkretes Artefakt gefunden wurde.

_DETECT_HINTS: dict[str, str] = {
    "LLM01": "Prompt-Injection-Guards: Untrusted-Block-Wrapping, Input-Sanitizing, Guardrails.",
    "LLM02": "Output-Encoding/Escaping vor Anzeige/Weiterverarbeitung der Modell-Ausgabe.",
    "LLM03": "Rate-Limiting/Throttling/Quota gegen Model-DoS.",
    "LLM04": "Content-Filter / Moderation / Toxicity-Checks auf Ein-/Ausgaben.",
    "LLM05": "PII-Redaction / DLP / Anonymisierung sensibler Daten.",
    "LLM06": "Model-Pinning: feste Modell-Version/Revision/Digest statt 'latest'.",
    "LLM07": "Eval/Test-Harness für das LLM (Eval-Suite, Red-Team-/Prompt-Tests).",
    "LLM08": "Dependency-Pinning: Lockfiles + Dependabot/Renovate für die KI-Lib-Supply-Chain.",
    "LLM09": "Secrets-Handling: keine Klartext-Keys, .env-Ignore, Secret-Scanning.",
    "LLM10": "Logging/Monitoring von Prompts/Responses für Audit + Anomalie-Erkennung.",
}


@dataclass(frozen=True)
class LlmDetectResult:
    llm_id: str
    matched: bool
    status: int          # 0-5
    kommentar: str
    evidence: list[dict[str, Any]] = field(default_factory=list)


def _ev(owner: str, name: str, path: str, branch: str) -> dict[str, Any]:
    ok, info = github_path_exists(owner, name, path, branch)
    if ok and info:
        return {"url": info.get("url", ""), "path": path}
    return {}


def _scan_files_for(owner: str, name: str, branch: str,
                    paths: list[str], patterns: list[str]) -> tuple[bool, dict[str, Any]]:
    """Lädt jede vorhandene Datei und sucht (case-insensitive) nach Patterns.

    Gibt (True, evidence) beim ersten Treffer zurück, sonst (False, {})."""
    rx = [re.compile(p, re.IGNORECASE) for p in patterns]
    for path in paths:
        text = github_fetch_text(owner, name, path, branch)
        if not text:
            continue
        for r in rx:
            if r.search(text):
                ok, info = github_path_exists(owner, name, path, branch)
                url = info.get("url", "") if (ok and info) else ""
                return True, {"url": url, "path": path}
    return False, {}


# Kandidaten-Pfade für Source-Scans (klein gehalten — token-aware Contents-API).
_CODE_PATHS = [
    "security_utils.py",
    "prefill/engine.py",
    "ai_act/ai_wizards.py",
    "cra/repo_autoanswer.py",
    "shared/encoding.py",
    "shared/redaction.py",
    "shared/audit.py",
]


def _detect_llm01(owner: str, name: str, branch: str) -> LlmDetectResult:
    # Prompt-Injection-Guards: Untrusted-Block-Wrapping / Sanitizing / Guardrails.
    ok, ev = _scan_files_for(
        owner, name, branch,
        ["security_utils.py", "prefill/engine.py"],
        [r"add_untrusted_block", r"prompt[_-]?injection", r"sanitiz", r"guardrail", r"untrusted"],
    )
    if ok:
        return LlmDetectResult("LLM01", True, 4,
                               "Prompt-Injection-Schutz im Code gefunden (Untrusted-Block/Sanitizing).",
                               [ev])
    return LlmDetectResult("LLM01", False, 0,
                           "Kein Prompt-Injection-Guard im Repo gefunden.", [])


def _detect_llm02(owner: str, name: str, branch: str) -> LlmDetectResult:
    # Output-Encoding / Escaping.
    ev = _ev(owner, name, "shared/encoding.py", branch)
    if ev:
        return LlmDetectResult("LLM02", True, 4,
                               "Output-Encoding-Modul (shared/encoding.py) vorhanden.", [ev])
    ok, ev2 = _scan_files_for(
        owner, name, branch, _CODE_PATHS,
        [r"html\.escape", r"escape\(", r"sanitize_output", r"bleach"],
    )
    if ok:
        return LlmDetectResult("LLM02", True, 3,
                               "Output-Escaping im Code gefunden.", [ev2])
    return LlmDetectResult("LLM02", False, 0,
                           "Kein Output-Encoding/Escaping gefunden.", [])


def _detect_llm03(owner: str, name: str, branch: str) -> LlmDetectResult:
    # Rate-Limiting / Throttling / Quota.
    ok, ev = _scan_files_for(
        owner, name, branch,
        ["server/__init__.py", "server/app.py", "requirements.txt"],
        [r"rate.?limit", r"flask.?limiter", r"throttl", r"slowapi"],
    )
    if ok:
        return LlmDetectResult("LLM03", True, 3,
                               "Rate-Limiting/Throttling-Hinweis gefunden.", [ev])
    return LlmDetectResult("LLM03", False, 0,
                           "Kein Rate-Limiting gegen Model-DoS gefunden.", [])


def _detect_llm04(owner: str, name: str, branch: str) -> LlmDetectResult:
    # Content-Filter / Moderation.
    ok, ev = _scan_files_for(
        owner, name, branch, _CODE_PATHS + ["requirements.txt"],
        [r"content.?filter", r"moderation", r"toxicity", r"profanity", r"safety.?check"],
    )
    if ok:
        return LlmDetectResult("LLM04", True, 3,
                               "Content-Filter/Moderation-Hinweis gefunden.", [ev])
    return LlmDetectResult("LLM04", False, 0,
                           "Kein Content-Filter/Moderation gefunden.", [])


def _detect_llm05(owner: str, name: str, branch: str) -> LlmDetectResult:
    # PII-Redaction / DLP / Anonymisierung.
    ev = _ev(owner, name, "shared/redaction.py", branch)
    if ev:
        return LlmDetectResult("LLM05", True, 4,
                               "Secret-/PII-Redaktion (shared/redaction.py) vorhanden.", [ev])
    ok, ev2 = _scan_files_for(
        owner, name, branch, _CODE_PATHS,
        [r"redact", r"\bpii\b", r"anonymi", r"\bdlp\b", r"mask_"],
    )
    if ok:
        return LlmDetectResult("LLM05", True, 3,
                               "PII-Redaction/Anonymisierung im Code gefunden.", [ev2])
    return LlmDetectResult("LLM05", False, 0,
                           "Keine PII-Redaction/DLP gefunden.", [])


def _detect_llm06(owner: str, name: str, branch: str) -> LlmDetectResult:
    # Model-Pinning: feste Modell-Version statt 'latest'.
    ok, ev = _scan_files_for(
        owner, name, branch,
        ["requirements.txt", "ai_act/ai_wizards.py", "compliance_db/config.py",
         "ollama.config.json", "docker-compose.yml"],
        [r"model[_-]?version", r"model[_-]?revision", r"@sha256:", r"model_pin",
         r"gpt-4[\w.\-]*", r"claude-[\w.\-]+", r"\bllama[\w.\-]*:\d"],
    )
    if ok:
        return LlmDetectResult("LLM06", True, 3,
                               "Gepinnte Modell-Version/Revision gefunden.", [ev])
    return LlmDetectResult("LLM06", False, 0,
                           "Kein Model-Pinning (feste Modell-Version) gefunden.", [])


def _detect_llm07(owner: str, name: str, branch: str) -> LlmDetectResult:
    # Eval / Test-Harness für das LLM.
    for path in ("tests", "evals", "eval", ".github/workflows"):
        ev = _ev(owner, name, path, branch)
        if ev:
            return LlmDetectResult("LLM07", True, 3,
                                   f"Test-/Eval-Harness vorhanden ({path}).", [ev])
    ok, ev2 = _scan_files_for(
        owner, name, branch, _CODE_PATHS,
        [r"red.?team", r"eval.?suite", r"prompt.?test"],
    )
    if ok:
        return LlmDetectResult("LLM07", True, 3,
                               "Eval/Red-Team-Test-Hinweis gefunden.", [ev2])
    return LlmDetectResult("LLM07", False, 0,
                           "Kein Eval/Test-Harness gefunden.", [])


def _detect_llm08(owner: str, name: str, branch: str) -> LlmDetectResult:
    # Dependency-Pinning: Lockfiles + Dependabot/Renovate.
    for path in (".github/dependabot.yml", "renovate.json",
                 "poetry.lock", "requirements.txt", "package-lock.json"):
        ev = _ev(owner, name, path, branch)
        if ev:
            return LlmDetectResult("LLM08", True, 4,
                                   f"Dependency-Pinning/Update-Automation gefunden ({path}).",
                                   [ev])
    return LlmDetectResult("LLM08", False, 0,
                           "Kein Dependency-Pinning (Lockfile/Dependabot) gefunden.", [])


def _detect_llm09(owner: str, name: str, branch: str) -> LlmDetectResult:
    # Secrets-Handling: .gitignore für .env + Secret-Scanning.
    text = github_fetch_text(owner, name, ".gitignore", branch)
    if text and re.search(r"\.env", text, re.IGNORECASE):
        ok, info = github_path_exists(owner, name, ".gitignore", branch)
        url = info.get("url", "") if (ok and info) else ""
        return LlmDetectResult("LLM09", True, 4,
                               "Secrets aus VCS ausgeschlossen (.env in .gitignore).",
                               [{"url": url, "path": ".gitignore"}])
    for path in (".github/workflows", ".pre-commit-config.yaml"):
        ev = _ev(owner, name, path, branch)
        if ev:
            return LlmDetectResult("LLM09", True, 3,
                                   f"Secret-Scanning/Hooks-Hinweis gefunden ({path}).", [ev])
    return LlmDetectResult("LLM09", False, 0,
                           "Kein Secrets-Handling (env-ignore/Secret-Scan) gefunden.", [])


def _detect_llm10(owner: str, name: str, branch: str) -> LlmDetectResult:
    # Logging / Monitoring von Prompts/Responses.
    ev = _ev(owner, name, "shared/audit.py", branch)
    if ev:
        return LlmDetectResult("LLM10", True, 4,
                               "Strukturiertes Audit-Logging (shared/audit.py) vorhanden.", [ev])
    ok, ev2 = _scan_files_for(
        owner, name, branch, _CODE_PATHS,
        [r"audit_event", r"logging\.", r"logger\."],
    )
    if ok:
        return LlmDetectResult("LLM10", True, 3,
                               "Logging im Code gefunden.", [ev2])
    return LlmDetectResult("LLM10", False, 0,
                           "Kein Logging/Monitoring für LLM-Interaktionen gefunden.", [])


_DETECTORS: dict[str, Callable[[str, str, str], LlmDetectResult]] = {
    "LLM01": _detect_llm01,
    "LLM02": _detect_llm02,
    "LLM03": _detect_llm03,
    "LLM04": _detect_llm04,
    "LLM05": _detect_llm05,
    "LLM06": _detect_llm06,
    "LLM07": _detect_llm07,
    "LLM08": _detect_llm08,
    "LLM09": _detect_llm09,
    "LLM10": _detect_llm10,
}


def autodetect_owasp_llm(*, repo: str, branch: str = "",
                         token: str | None = None) -> list[LlmDetectResult]:
    """Token-aware Repo-Scan über alle 10 LLM-Heuristiken (#1064-Pattern).

    ``token`` wird über :func:`ai_act.repo_alignment.github_path_exists` /
    ``github_fetch_text`` an die HTTP-API durchgereicht (gh-CLI-Fallback ohne
    Token). Schlägt eine einzelne Heuristik fehl, gilt sie als 'nicht gefunden'
    (defensiv — der Scan darf nie crashen)."""
    parsed = parse_github_repo(repo)
    if not parsed:
        raise ValueError("Repo-URL ungültig. Erwartet z.B. https://github.com/org/repo oder org/repo")
    owner, name = parsed

    # Die Detektoren rufen die Modul-Helfer (github_path_exists/github_fetch_text)
    # direkt ohne token-Param auf. _run_detector reicht den token #1064-konform
    # durch (lokaler Wrapper der Modul-Funktionen für die Dauer des Detektors).
    results: list[LlmDetectResult] = []
    for it in OWASP_LLM_TOP10:
        lid = it["id"]
        detector = _DETECTORS.get(lid)
        if not detector:
            continue
        try:
            results.append(_run_detector(detector, owner, name, branch, token))
        except Exception:
            results.append(LlmDetectResult(lid, False, 0, "Auto-Detect fehlgeschlagen.", []))
    return results


def _run_detector(detector: Callable[[str, str, str], LlmDetectResult],
                  owner: str, name: str, branch: str,
                  token: str | None) -> LlmDetectResult:
    """Führt einen Detector mit token-aware Helfern aus.

    Da die Detektoren ``github_path_exists``/``github_fetch_text`` ohne token
    aufrufen, injizieren wir den token über temporäre Monkey-Patches der
    Modul-Funktionen — lokal und thread-sicher genug für den synchronen Scan.
    Wird kein token übergeben, fällt alles auf das #1064-Default zurück."""
    if token is None:
        return detector(owner, name, branch)

    import ai_act.owasp_llm_register as _self
    orig_exists = _self.github_path_exists
    orig_fetch = _self.github_fetch_text

    def _exists(o, n, p, b="", **kw):
        return orig_exists(o, n, p, b, token=token)

    def _fetch(o, n, p, b="", **kw):
        return orig_fetch(o, n, p, b, token=token)

    _self.github_path_exists = _exists  # type: ignore[assignment]
    _self.github_fetch_text = _fetch    # type: ignore[assignment]
    try:
        return detector(owner, name, branch)
    finally:
        _self.github_path_exists = orig_exists  # type: ignore[assignment]
        _self.github_fetch_text = orig_fetch    # type: ignore[assignment]


# ── KI-Wizard (Prompt-Builder + Parse) — analog ai_act/ai_wizards.py ─────────

def build_owasp_llm_prompt(projekt: dict[str, Any],
                           system_doku: dict[str, Any] | None = None,
                           checks: dict[str, dict[str, Any]] | None = None) -> str:
    """KI-Prompt für die Bewertung aller OWASP-LLM-Top-10-Items (Skala 0-5)."""
    sd = system_doku or {}
    saved = checks or {}
    item_lines = []
    for it in OWASP_LLM_TOP10:
        cur = saved.get(it["id"], {})
        st = int(cur.get("status", 0) or 0)
        item_lines.append(
            f"- {it['id']} {it['title']} "
            f"(AI-Act-Mapping: {', '.join(it.get('maps_to') or []) or '—'}; aktuell {st}/5)"
        )
    items_block = "\n".join(item_lines)
    return f"""🔒 SECURITY: Verwende AUSSCHLIESSLICH die bereitgestellten Informationen.

Du bist ein Experte für LLM-Anwendungssicherheit (OWASP Top 10 for LLM Applications)
und EU-AI-Act-Compliance (Verordnung (EU) 2024/1689, Art. 9 + Art. 15).

Bewerte für das folgende KI-System den Umsetzungsgrad jedes der OWASP-LLM-Top-10-Risiken
auf einer Skala 0-5 (0 = nicht umgesetzt, 5 = vollständig umgesetzt).

# System-Kontext
- System: {projekt.get('name', '')} ({projekt.get('organisation', '')})
- Produkt: {projekt.get('produkt', '')}
- Architektur: {sd.get('architecture', '(nicht gesetzt)')}
- Intended Purpose: {sd.get('intended_purpose', '(nicht gesetzt)')}
- Cybersecurity-Maßnahmen: {sd.get('cybersecurity_measures', '(nicht gesetzt)')}

# OWASP-LLM-Top-10
{items_block}

Hinweis: Diese Risiken stärken die Nachweise zu **AI-Act Art. 9 (Risikomanagement)**
und **Art. 15 (Genauigkeit/Robustheit/Cybersicherheit)** — additiv, ohne sie zu ersetzen.

Antworte **ausschließlich** als JSON-Objekt der Form:
```json
{{
  "items": [
    {{"id": "LLM01", "status": 0, "kommentar": "Begründung in 1-2 Sätzen"}},
    {{"id": "LLM02", "status": 0, "kommentar": "..."}}
  ]
}}
```
Liste ALLE 10 Items (LLM01-LLM10). Referenz: {OWASP_LLM_TOP10_REF}
"""


def parse_owasp_llm_response(raw: str) -> list[dict[str, Any]]:
    """Parst die KI-Antwort zu einer Liste von {id, status, kommentar}.

    Akzeptiert sowohl ``{"items": [...]}`` als auch eine reine Liste. Unbekannte
    IDs werden verworfen, status auf 0-5 geklemmt. Leere Liste, wenn nichts
    Brauchbares erkannt wurde (Endpoint antwortet dann mit 400)."""
    data: Any = _extract_json_loose(raw)
    if isinstance(data, dict):
        items = data.get("items")
    elif isinstance(data, list):
        items = data
    else:
        items = None
    if not isinstance(items, list):
        return []

    valid_ids = {it["id"] for it in OWASP_LLM_TOP10}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in items:
        if not isinstance(entry, dict):
            continue
        lid = str(entry.get("id", "")).strip().upper()
        if lid not in valid_ids or lid in seen:
            continue
        try:
            st = int(entry.get("status", 0) or 0)
        except (TypeError, ValueError):
            st = 0
        st = max(0, min(5, st))
        out.append({
            "id": lid,
            "status": st,
            "kommentar": str(entry.get("kommentar", "") or ""),
        })
        seen.add(lid)
    return out


def _extract_json_loose(raw: str) -> Any:
    """Tolerantes JSON-Extrakt: Code-Fence entfernen, erstes {...} oder [...]."""
    if not raw:
        return None
    text = raw.strip()
    for marker in ("```json", "```"):
        if marker in text:
            parts = text.split(marker)
            if len(parts) >= 2:
                text = parts[1].split("```")[0] if marker == "```json" else parts[1]
                break
    # Versuche zuerst Objekt, dann Array.
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start >= 0 and end > start:
            snippet = text[start:end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
