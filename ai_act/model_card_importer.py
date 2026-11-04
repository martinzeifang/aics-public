"""AI Act Phase E A20 — Model-Card-Importer (#546).

Parst Model-Card-Metadaten von externen Providern (HuggingFace, OpenAI, Anthropic)
in das interne AI-System-Doku-Schema. Backfill ohne ChatGPT-Roundtrip.

Unterstützte Formate:
- huggingface : YAML-Frontmatter + Markdown (README.md im Model-Repo)
- openai      : OpenAI-Model-Card JSON (system-card.json)
- anthropic   : Anthropic-Model-Card JSON (model-card.json)
- generic     : best-effort Markdown-Parsing (Headlines)
"""
from __future__ import annotations

import json
import re
from typing import Any


SUPPORTED_FORMATS = ("huggingface", "openai", "anthropic", "generic")


def import_model_card(text: str, fmt: str = "huggingface") -> dict[str, Any]:
    """Liefert ein Dict mit Feldern fürs `aiact_system_doku`-Schema.

    Felder im Output (Subset von `aiact_system_doku`):
      system_name, version, provider, intended_purpose, architecture,
      training_methodology, accuracy_robustness, cybersecurity_measures,
      notizen (= rohe Card als Markdown)
    """
    fmt = (fmt or "").strip().lower() or "generic"
    if fmt not in SUPPORTED_FORMATS:
        fmt = "generic"

    if fmt == "huggingface":
        parsed = _parse_hf_card(text)
    elif fmt == "openai":
        parsed = _parse_openai_card(text)
    elif fmt == "anthropic":
        parsed = _parse_anthropic_card(text)
    else:
        parsed = _parse_generic(text)

    parsed.setdefault("notizen", text.strip())
    parsed["_source_format"] = fmt
    return parsed


# ─────────────────────────────────────────────────────────────────────
# HuggingFace
# ─────────────────────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def _parse_hf_card(text: str) -> dict[str, Any]:
    """HF model cards = YAML frontmatter + Markdown body.

    Wir parsen nur die für AI Act relevanten Felder; keine YAML-Lib-Pflicht.
    """
    fm: dict[str, str] = {}
    body = text
    m = _FRONTMATTER_RE.match(text.strip())
    if m:
        fm = _parse_simple_yaml(m.group(1))
        body = m.group(2)

    sections = _markdown_sections(body)
    return {
        "system_name": fm.get("model-index_name") or fm.get("model_name") or fm.get("name") or _first_heading(body),
        "version": fm.get("version") or fm.get("model_version") or "",
        "provider": fm.get("organization") or fm.get("provider") or fm.get("author") or "",
        "intended_purpose": _pick_section(sections, ["intended use", "intended uses", "model use", "uses"]),
        "architecture": fm.get("base_model") or fm.get("library_name") or _pick_section(sections, ["model architecture", "architecture", "model details"]),
        "training_methodology": _pick_section(sections, ["training data", "training procedure", "training"]),
        "accuracy_robustness": _pick_section(sections, ["evaluation", "performance", "metrics", "results"]),
        "cybersecurity_measures": _pick_section(sections, ["safety", "security", "risks"]),
    }


def _parse_simple_yaml(yaml_text: str) -> dict[str, str]:
    """Best-effort YAML-Parser (kein PyYAML-Zwang)."""
    out: dict[str, str] = {}
    for line in yaml_text.splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            v = v.strip().strip('"').strip("'")
            if v:
                out[k.strip().lower().replace(" ", "_")] = v
    return out


# ─────────────────────────────────────────────────────────────────────
# OpenAI / Anthropic JSON
# ─────────────────────────────────────────────────────────────────────

def _parse_openai_card(text: str) -> dict[str, Any]:
    data = _extract_json(text)
    return {
        "system_name": data.get("model") or data.get("model_id") or data.get("name", ""),
        "version": data.get("version") or data.get("release_date", ""),
        "provider": "OpenAI",
        "intended_purpose": _stringify(data.get("intended_use") or data.get("use_cases", "")),
        "architecture": _stringify(data.get("model_architecture") or data.get("architecture", "")),
        "training_methodology": _stringify(data.get("training_data") or data.get("training", "")),
        "accuracy_robustness": _stringify(data.get("evaluation") or data.get("performance", "")),
        "cybersecurity_measures": _stringify(data.get("safety_evaluations") or data.get("safety", "")),
    }


def _parse_anthropic_card(text: str) -> dict[str, Any]:
    data = _extract_json(text)
    return {
        "system_name": data.get("model") or data.get("name", ""),
        "version": data.get("version", ""),
        "provider": "Anthropic",
        "intended_purpose": _stringify(data.get("intended_uses") or data.get("intended_use", "")),
        "architecture": _stringify(data.get("model_details") or data.get("architecture", "")),
        "training_methodology": _stringify(data.get("training") or data.get("training_data", "")),
        "accuracy_robustness": _stringify(data.get("evaluations") or data.get("evaluation", "")),
        "cybersecurity_measures": _stringify(data.get("safety") or data.get("acceptable_use_policy", "")),
    }


# ─────────────────────────────────────────────────────────────────────
# Generic Markdown
# ─────────────────────────────────────────────────────────────────────

def _parse_generic(text: str) -> dict[str, Any]:
    sections = _markdown_sections(text)
    return {
        "system_name": _first_heading(text),
        "version": "",
        "provider": "",
        "intended_purpose": _pick_section(sections, ["intended", "uses", "use cases"]),
        "architecture": _pick_section(sections, ["architecture", "model"]),
        "training_methodology": _pick_section(sections, ["training"]),
        "accuracy_robustness": _pick_section(sections, ["evaluation", "performance"]),
        "cybersecurity_measures": _pick_section(sections, ["safety", "risk"]),
    }


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)


def _markdown_sections(text: str) -> dict[str, str]:
    """Returns {heading_lowercase: body_until_next_heading}."""
    sections: dict[str, str] = {}
    matches = list(_HEADING_RE.finditer(text))
    for i, m in enumerate(matches):
        title = m.group(2).strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections[title] = body[:2000]
    return sections


def _pick_section(sections: dict[str, str], keywords: list[str]) -> str:
    """Find first section whose title contains any keyword (substring match)."""
    for title, body in sections.items():
        for kw in keywords:
            if kw in title:
                return body
    return ""


def _first_heading(text: str) -> str:
    m = _HEADING_RE.search(text)
    return m.group(2).strip() if m else ""


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    for marker in ("```json", "```"):
        if marker in text:
            parts = text.split(marker)
            if len(parts) >= 2:
                text = parts[1].split("```")[0]
                break
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _stringify(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return "\n".join(_stringify(x) for x in v if x)
    if isinstance(v, dict):
        return "\n".join(f"{k}: {_stringify(val)}" for k, val in v.items() if val)
    return str(v)
