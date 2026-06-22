"""Auto-Fill-Vorschläge für die A1-Tabelle ``aiact_system_doku`` (#1020).

Liest typische Repo-Dateien (README, ARCHITECTURE, MODEL_CARD, SECURITY) bzw.
eine beliebige Web-URL und leitet daraus Vorschläge für die Pflicht-Doku-Felder
ab. Es werden ausschließlich Felder zurückgegeben, für die Inhalt gefunden wurde.

Die field-Keys entsprechen exakt den Spalten von ``aiact_system_doku`` (siehe
``ai_act/db.py``): ``system_name``, ``intended_purpose``, ``architecture``,
``training_methodology``, ``performance_metrics_json``, ``cybersecurity_measures``.
"""

from __future__ import annotations

import re

from ai_act.autofill_common import FieldSuggestion
from ai_act.repo_alignment import github_fetch_text, parse_github_repo
from evidence.web_fetch import WebFetchError, fetch_page

# Kandidaten-Dateinamen ------------------------------------------------------
_README_CANDIDATES = ("README.md", "Readme.md", "readme.md")
_ARCHITECTURE_CANDIDATES = (
    "ARCHITECTURE.md",
    "Architecture.md",
    "architecture.md",
    "docs/architecture.md",
    "docs/ARCHITECTURE.md",
    "docs/architecture/README.md",
    "docs/architecture/index.md",
)
_MODEL_CARD_CANDIDATES = (
    "MODEL_CARD.md",
    "model_card.md",
    "Model_Card.md",
    "ModelCard.md",
    "docs/MODEL_CARD.md",
    "docs/model_card.md",
)
_SECURITY_CANDIDATES = (
    "SECURITY.md",
    "Security.md",
    "security.md",
    ".github/SECURITY.md",
    "docs/SECURITY.md",
)

_MAX_PURPOSE_LEN = 500

# Konfidenz-Stufen
_CONF_DIRECT = 0.7   # direkter Treffer (eigene Datei / klare Sektion)
_CONF_DERIVED = 0.5  # abgeleitet (z.B. erster Absatz nach Heading)


# ── Markdown-Helfer ─────────────────────────────────────────────────────────

def _strip_markdown(text: str) -> str:
    """Entfernt grob Markdown-Auszeichnung aus einem Textstück."""
    s = text
    # Bilder/Links → nur Linktext
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    # Inline-Code / Betonung / Überschriften-Marker
    s = s.replace("`", "")
    s = re.sub(r"[*_]{1,3}", "", s)
    s = re.sub(r"^\s{0,3}#{1,6}\s*", "", s, flags=re.MULTILINE)
    s = re.sub(r"^\s{0,3}>\s?", "", s, flags=re.MULTILINE)
    return s.strip()


def _first_heading(md: str) -> str:
    """Liefert den Text der ersten Markdown-H1/H2-Überschrift (``# …``)."""
    for line in md.splitlines():
        m = re.match(r"^\s{0,3}#{1,6}\s+(.*\S)\s*$", line)
        if m:
            return _strip_markdown(m.group(1)).strip()
    return ""


def _first_paragraph(md: str, *, after_heading: bool = False) -> str:
    """Erster nicht-leerer Fließtext-Absatz.

    ``after_heading=True``: überspringt alles bis nach der ersten Überschrift.
    Code-Blöcke, Listen, Badges und Tabellen werden übersprungen.
    """
    lines = md.splitlines()
    started = not after_heading
    in_code = False
    para: list[str] = []
    seen_heading = False

    for raw in lines:
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        is_heading = bool(re.match(r"^\s{0,3}#{1,6}\s+", line))
        if after_heading and not started:
            if is_heading:
                started = True
                seen_heading = True
            continue
        if not line.strip():
            if para:
                break
            continue
        if is_heading:
            if para:
                break
            continue
        # Listen/Tabellen/HR überspringen, solange noch kein Absatz begonnen hat
        stripped = line.strip()
        if not para and re.match(r"^([-*+]\s|\d+\.\s|\||---|===)", stripped):
            continue
        para.append(stripped)

    _ = seen_heading
    return _strip_markdown(" ".join(para)).strip()


_SECTION_KEYWORDS = {
    "training": ("training", "trainings", "training data", "training procedure",
                 "training methodology"),
    "performance": ("performance", "metrics", "evaluation", "results",
                     "benchmark", "benchmarks", "accuracy"),
}


def _extract_section(md: str, keywords: tuple[str, ...]) -> str:
    """Extrahiert den Textkörper der ersten Sektion, deren Überschrift eines der
    Keywords enthält. Stoppt an der nächsten Überschrift gleicher/höherer Ebene.
    """
    lines = md.splitlines()
    n = len(lines)
    for i, line in enumerate(lines):
        m = re.match(r"^\s{0,3}(#{1,6})\s+(.*\S)\s*$", line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).lower()
        if not any(k in title for k in keywords):
            continue
        body: list[str] = []
        in_code = False
        for j in range(i + 1, n):
            cur = lines[j]
            if cur.strip().startswith("```"):
                in_code = not in_code
                body.append(cur)
                continue
            if not in_code:
                hm = re.match(r"^\s{0,3}(#{1,6})\s+", cur)
                if hm and len(hm.group(1)) <= level:
                    break
            body.append(cur)
        return "\n".join(body).strip()
    return ""


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _fetch_first(owner: str, name: str, candidates: tuple[str, ...],
                 branch: str, token: str | None = None) -> tuple[str, str] | None:
    """Erste existierende Datei aus ``candidates`` als (path, content)."""
    for path in candidates:
        content = github_fetch_text(owner, name, path, branch, token=token)
        if content and content.strip():
            return path, content
    return None


# ── Öffentliche API ─────────────────────────────────────────────────────────

def suggest_system_doku(repo: str, branch: str = "",
                        token: str | None = None) -> dict[str, FieldSuggestion]:
    """Vorschläge für ``aiact_system_doku`` aus den Dateien eines GitHub-Repos.

    Gibt nur Felder mit gefundenem Inhalt zurück. ``token`` (#1064) für private
    Repos im Container.
    """
    parsed = parse_github_repo(repo)
    if not parsed:
        return {}
    owner, name = parsed

    out: dict[str, FieldSuggestion] = {}

    # README → system_name + intended_purpose
    readme = _fetch_first(owner, name, _README_CANDIDATES, branch, token)
    if readme:
        path, content = readme
        heading = _first_heading(content)
        if heading:
            out["system_name"] = FieldSuggestion(
                field="system_name", value=heading,
                source_path=path, confidence=_CONF_DIRECT,
            )
        purpose = _first_paragraph(content, after_heading=True)
        if not purpose:
            purpose = _first_paragraph(content, after_heading=False)
        if purpose:
            out["intended_purpose"] = FieldSuggestion(
                field="intended_purpose",
                value=_truncate(purpose, _MAX_PURPOSE_LEN),
                source_path=path, confidence=_CONF_DERIVED,
            )

    # ARCHITECTURE → architecture
    arch = _fetch_first(owner, name, _ARCHITECTURE_CANDIDATES, branch, token)
    if arch:
        path, content = arch
        body = _first_paragraph(content, after_heading=True)
        if not body:
            body = _first_paragraph(content, after_heading=False)
        if body:
            out["architecture"] = FieldSuggestion(
                field="architecture",
                value=_truncate(body, _MAX_PURPOSE_LEN),
                source_path=path, confidence=_CONF_DIRECT,
            )

    # MODEL_CARD → training_methodology + performance_metrics_json
    card = _fetch_first(owner, name, _MODEL_CARD_CANDIDATES, branch, token)
    if card:
        path, content = card
        training = _extract_section(content, _SECTION_KEYWORDS["training"])
        if training:
            out["training_methodology"] = FieldSuggestion(
                field="training_methodology",
                value=_truncate(_strip_markdown(training), _MAX_PURPOSE_LEN),
                source_path=path, confidence=_CONF_DIRECT,
            )
        perf = _extract_section(content, _SECTION_KEYWORDS["performance"])
        if perf:
            out["performance_metrics_json"] = FieldSuggestion(
                field="performance_metrics_json",
                value=_truncate(_strip_markdown(perf), _MAX_PURPOSE_LEN),
                source_path=path, confidence=_CONF_DERIVED,
            )

    # SECURITY → cybersecurity_measures
    sec = _fetch_first(owner, name, _SECURITY_CANDIDATES, branch, token)
    if sec:
        path, content = sec
        body = _first_paragraph(content, after_heading=True)
        if not body:
            body = _first_paragraph(content, after_heading=False)
        if body:
            out["cybersecurity_measures"] = FieldSuggestion(
                field="cybersecurity_measures",
                value=_truncate(body, _MAX_PURPOSE_LEN),
                source_path=path, confidence=_CONF_DIRECT,
            )

    return out


def suggest_from_url(url: str) -> dict[str, FieldSuggestion]:
    """Vorschläge aus einer beliebigen Web-URL.

    Setzt ``intended_purpose`` aus dem Klartext und – falls vorhanden – einen
    ``system_name`` aus dem Seitentitel. Bei Abruf-Fehlern wird ein leeres Dict
    zurückgegeben (kein Crash).
    """
    try:
        res = fetch_page(url)
    except WebFetchError:
        return {}

    out: dict[str, FieldSuggestion] = {}

    title = (res.title or "").strip()
    if title:
        out["system_name"] = FieldSuggestion(
            field="system_name", value=title,
            source_path=res.url or url, confidence=_CONF_DERIVED,
        )

    text = (res.text or "").strip()
    if text:
        # Ersten sinnvollen Absatz nehmen
        para = ""
        for block in re.split(r"\n\s*\n", text):
            cand = " ".join(block.split())
            if len(cand) >= 20:
                para = cand
                break
        if not para:
            para = " ".join(text.split())
        if para:
            out["intended_purpose"] = FieldSuggestion(
                field="intended_purpose",
                value=_truncate(para, _MAX_PURPOSE_LEN),
                source_path=res.url or url, confidence=_CONF_DERIVED,
            )

    return out
