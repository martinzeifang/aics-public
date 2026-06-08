"""Auto-Fill-Vorschläge für die A2-Tabelle ``aiact_data_governance`` (#1021).

Liest deterministische Signale aus typischen Repo-Dateien (DATASET.md,
datasheet.md, MODEL_CARD.md, bias-report.md, dvc.yaml, README) bzw. aus einer
frei angegebenen URL und schlägt Werte für die Daten-Governance-Felder vor.

Nur Lib — keine Endpoints/kein Frontend. Analog zu Story 2 (#1020).
"""
from __future__ import annotations

import re

from ai_act.autofill_common import FieldSuggestion
from ai_act.repo_alignment import github_fetch_text, parse_github_repo
from evidence.web_fetch import WebFetchError, fetch_page

# Confidence-Stufen laut Story
_C_DIRECT = 0.7   # direkter Treffer (passende Sektion gefunden)
_C_HEURISTIC = 0.4  # abgeleitet / Heuristik

# Dateien, die wir nacheinander probieren (erste, die existiert, gewinnt).
_DATASET_FILES = ("DATASET.md", "datasheet.md", "docs/DATASET.md", "data/DATASET.md")
_MODELCARD_FILES = ("MODEL_CARD.md", "MODELCARD.md", "model_card.md", "docs/MODEL_CARD.md")
_BIAS_FILES = ("bias-report.md", "bias_report.md", "docs/bias-report.md", "BIAS.md")
_README_FILES = ("README.md", "README.rst", "readme.md")
_DVC_FILES = ("dvc.yaml", "dvc.lock")

# Max. Länge eines vorgeschlagenen Textblocks (Felder sind Kurztexte).
_MAX_VALUE = 1200


# ─── Markdown-Helfer ───────────────────────────────────────────────────────

def _fetch_first(owner: str, name: str, branch: str,
                 candidates: tuple[str, ...]) -> tuple[str, str] | None:
    """Erste existierende Datei aus ``candidates`` als (path, text) zurückgeben."""
    for path in candidates:
        text = github_fetch_text(owner, name, path, branch)
        if text and text.strip():
            return path, text
    return None


def _split_sections(md: str) -> list[tuple[str, str]]:
    """Markdown grob in (Überschrift, Body) zerlegen (ATX-Header ``#``…)."""
    sections: list[tuple[str, str]] = []
    current_head = ""
    current_body: list[str] = []
    for line in (md or "").splitlines():
        m = re.match(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$", line)
        if m:
            if current_head or current_body:
                sections.append((current_head, "\n".join(current_body).strip()))
            current_head = m.group(1).strip()
            current_body = []
        else:
            current_body.append(line)
    if current_head or current_body:
        sections.append((current_head, "\n".join(current_body).strip()))
    return sections


def _find_section(md: str, keywords: tuple[str, ...]) -> str | None:
    """Body der ersten Sektion zurückgeben, deren Überschrift ein Keyword enthält."""
    for head, body in _split_sections(md):
        h = head.lower()
        if any(kw in h for kw in keywords) and body.strip():
            return _clip(body)
    return None


def _first_section_body(md: str) -> str | None:
    """Body der ersten nicht-leeren Sektion (Intro nach dem Titel)."""
    for head, body in _split_sections(md):
        if body.strip():
            return _clip(body)
    return None


def _clip(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    if len(text) > _MAX_VALUE:
        text = text[:_MAX_VALUE].rstrip() + " …"
    return text


# ─── Repo-basierte Vorschläge ──────────────────────────────────────────────

def suggest_data_governance(repo: str, branch: str = "") -> dict[str, FieldSuggestion]:
    """Vorschläge für ``aiact_data_governance`` aus GitHub-Repo-Dateien.

    Nur Felder mit gefundenem Inhalt werden zurückgegeben. ``repo`` darf eine
    GitHub-URL oder ``owner/name`` sein; bei unparsbarem Wert: leeres Dict.
    """
    parsed = parse_github_repo(repo)
    if not parsed:
        return {}
    owner, name = parsed

    out: dict[str, FieldSuggestion] = {}

    def add(field: str, value: str | None, source: str, conf: float) -> None:
        if value and value.strip() and field not in out:
            out[field] = FieldSuggestion(field=field, value=value.strip(),
                                         source_path=source, confidence=conf)

    dataset = _fetch_first(owner, name, branch, _DATASET_FILES)
    modelcard = _fetch_first(owner, name, branch, _MODELCARD_FILES)
    bias_doc = _fetch_first(owner, name, branch, _BIAS_FILES)
    readme = _fetch_first(owner, name, branch, _README_FILES)

    # training_data_source / training_data_size ← DATASET.md erste Sektionen
    if dataset:
        ds_path, ds_text = dataset
        src = _find_section(ds_text, ("source", "quelle", "origin", "provenance"))
        if not src:
            src = _first_section_body(ds_text)
        add("training_data_source", src, ds_path, _C_DIRECT if src else _C_HEURISTIC)

        size = _find_section(ds_text, ("size", "größe", "umfang", "statistics",
                                       "statistik", "samples", "instances"))
        add("training_data_size", size, ds_path, _C_DIRECT)

        collection = _find_section(ds_text, ("collection", "erhebung", "sammlung",
                                             "acquisition"))
        add("data_collection_method", collection, ds_path, _C_DIRECT)

        labelling = _find_section(ds_text, ("labeling", "labelling", "annotation",
                                            "labeling process", "annotat",
                                            "kennzeichnung"))
        add("data_labelling_method", labelling, ds_path, _C_DIRECT)

        repr_ = _find_section(ds_text, ("coverage", "representativeness",
                                        "representative", "repräsentativ",
                                        "abdeckung"))
        add("representativeness", repr_, ds_path, _C_DIRECT)

    # data_collection_method (Heuristik): dvc.yaml-Existenz signalisiert Pipeline
    if "data_collection_method" not in out:
        dvc = _fetch_first(owner, name, branch, _DVC_FILES)
        if dvc:
            dvc_path, _ = dvc
            add("data_collection_method",
                "Datenpipeline mit DVC versioniert (dvc.yaml vorhanden) — "
                "Erhebungsschritte bitte ergänzen.",
                dvc_path, _C_HEURISTIC)

    # bias_assessment / bias_mitigation ← bias-report.md bzw. MODEL_CARD Limitations
    if bias_doc:
        b_path, b_text = bias_doc
        assess = _find_section(b_text, ("assessment", "bewertung", "analysis",
                                        "analyse", "bias", "fairness")) \
            or _first_section_body(b_text)
        add("bias_assessment", assess, b_path, _C_DIRECT if assess else _C_HEURISTIC)
        mitig = _find_section(b_text, ("mitigation", "minderung", "maßnahmen",
                                       "remediation", "mitigat"))
        add("bias_mitigation", mitig, b_path, _C_DIRECT)

    if modelcard:
        mc_path, mc_text = modelcard
        assess = _find_section(mc_text, ("limitation", "bias", "fairness",
                                         "einschränkung", "verzerrung"))
        add("bias_assessment", assess, mc_path, _C_DIRECT)
        mitig = _find_section(mc_text, ("mitigation", "minderung", "maßnahmen"))
        add("bias_mitigation", mitig, mc_path, _C_DIRECT)

    # personal_data_used (Heuristik) ← README/DATASET erwähnt PII/personenbezogen
    pii_pattern = re.compile(r"personal data|personenbezog|\bpii\b|personally identifiable",
                             re.IGNORECASE)
    pii_source = None
    for doc in (dataset, readme):
        if doc and pii_pattern.search(doc[1]):
            pii_source = doc[0]
            break
    if pii_source:
        add("personal_data_used", "ja (bitte prüfen)", pii_source, _C_HEURISTIC)
        add("legal_basis_gdpr",
            "Bitte Rechtsgrundlage nach Art. 6 DSGVO prüfen.",
            pii_source, _C_HEURISTIC)

    return out


# ─── URL-basierte Vorschläge ───────────────────────────────────────────────

def suggest_from_url(url: str) -> dict[str, FieldSuggestion]:
    """Vorschläge aus dem Klartext einer beliebigen Webseite.

    Grobe Ableitung von ``training_data_source`` / ``data_collection_method``
    über Keyword-Absätze. Bei ``WebFetchError`` wird ein leeres Dict geliefert.
    """
    try:
        result = fetch_page(url)
    except WebFetchError:
        return {}
    except Exception:
        return {}

    text = result.text or ""
    if not text.strip():
        return {}

    out: dict[str, FieldSuggestion] = {}
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    def first_match(keywords: tuple[str, ...]) -> str | None:
        for para in paragraphs:
            low = para.lower()
            if any(kw in low for kw in keywords):
                return _clip(para)
        return None

    src = first_match(("data source", "dataset", "datenquelle", "data set",
                       "training data", "trainingsdaten"))
    if src:
        out["training_data_source"] = FieldSuggestion(
            field="training_data_source", value=src,
            source_path=result.url or url, confidence=_C_HEURISTIC)

    collection = first_match(("data collection", "collected", "erhebung",
                              "gesammelt", "acquisition", "crawl"))
    if collection:
        out["data_collection_method"] = FieldSuggestion(
            field="data_collection_method", value=collection,
            source_path=result.url or url, confidence=_C_HEURISTIC)

    return out
