"""Unit-Tests für die Daten-Governance-Auto-Fill-Vorschläge (#1021).

Keine Netzzugriffe: ``github_fetch_text`` / ``parse_github_repo`` /
``fetch_page`` werden gemockt.
"""
from __future__ import annotations

import pytest

from ai_act import data_governance_autofill as dga
from ai_act.autofill_common import FieldSuggestion
from evidence.web_fetch import FetchResult, WebFetchError


DATASET_MD = """# Example Dataset

A short intro describing the corpus.

## Source
Collected from public crawl of de.example.org and partner archives.

## Size
1,250,000 labelled samples across 12 categories.

## Collection
Data was gathered via automated crawling and curated review.

## Labeling
Three annotators per item, majority vote, Cohen's kappa 0.81.

## Coverage
Covers all 16 German federal states; mention of personal data was removed.
"""

MODELCARD_MD = """# Model Card

## Intended Use
Classification.

## Limitations
The model shows reduced accuracy on dialectal inputs and may reflect
historical bias present in the training corpus.

## Mitigation
We reweighted under-represented groups and added fairness regression tests.
"""


def _fake_fetch(mapping: dict[str, str]):
    def _inner(owner, name, path, branch=""):
        return mapping.get(path)
    return _inner


def test_suggest_data_governance_returns_fields(monkeypatch):
    monkeypatch.setattr(dga, "parse_github_repo", lambda repo: ("o", "r"))
    monkeypatch.setattr(
        dga, "github_fetch_text",
        _fake_fetch({"DATASET.md": DATASET_MD, "MODEL_CARD.md": MODELCARD_MD}),
    )

    out = dga.suggest_data_governance("o/r")

    # Mindestens drei Felder vorgeschlagen
    assert len(out) >= 3
    # Alle Werte sind FieldSuggestion-Instanzen
    for key, sug in out.items():
        assert isinstance(sug, FieldSuggestion)
        assert sug.field == key
        assert sug.value.strip()
        assert 0.0 <= sug.confidence <= 1.0

    # Direkte Sektions-Treffer aus DATASET.md
    assert "training_data_source" in out
    assert "public crawl" in out["training_data_source"].value
    assert out["training_data_source"].confidence == 0.7
    assert "training_data_size" in out
    assert "1,250,000" in out["training_data_size"].value
    assert "data_collection_method" in out
    assert "data_labelling_method" in out
    assert "representativeness" in out

    # Bias aus MODEL_CARD.md (Limitations/Mitigation)
    assert "bias_assessment" in out
    assert "bias_mitigation" in out

    # personal_data-Heuristik (DATASET erwähnt "personal data")
    assert out["personal_data_used"].value == "ja (bitte prüfen)"
    assert out["personal_data_used"].confidence == 0.4
    assert "Art. 6 DSGVO" in out["legal_basis_gdpr"].value


def test_unparsable_repo_returns_empty(monkeypatch):
    monkeypatch.setattr(dga, "parse_github_repo", lambda repo: None)
    assert dga.suggest_data_governance("not a repo") == {}


def test_no_files_returns_empty(monkeypatch):
    monkeypatch.setattr(dga, "parse_github_repo", lambda repo: ("o", "r"))
    monkeypatch.setattr(dga, "github_fetch_text", _fake_fetch({}))
    assert dga.suggest_data_governance("o/r") == {}


def test_dvc_heuristic_for_collection(monkeypatch):
    monkeypatch.setattr(dga, "parse_github_repo", lambda repo: ("o", "r"))
    monkeypatch.setattr(dga, "github_fetch_text", _fake_fetch({"dvc.yaml": "stages:\n  prep:\n"}))
    out = dga.suggest_data_governance("o/r")
    assert "data_collection_method" in out
    assert out["data_collection_method"].confidence == 0.4
    assert out["data_collection_method"].source_path == "dvc.yaml"


def test_suggest_from_url(monkeypatch):
    page_text = (
        "Welcome to our project.\n\n"
        "The training data was collected from a public web crawl in 2024.\n\n"
        "Our dataset source is the open de.example.org archive.\n\n"
        "Contact us for more.\n"
    )

    def fake_fetch_page(url, *, timeout=15):
        return FetchResult(url=url, title="T", text=page_text)

    monkeypatch.setattr(dga, "fetch_page", fake_fetch_page)
    out = dga.suggest_from_url("https://example.org/about")

    assert out
    assert "training_data_source" in out or "data_collection_method" in out
    for sug in out.values():
        assert isinstance(sug, FieldSuggestion)
        assert sug.confidence == 0.4
        assert sug.source_path == "https://example.org/about"


def test_suggest_from_url_fetch_error(monkeypatch):
    def boom(url, *, timeout=15):
        raise WebFetchError("nope")

    monkeypatch.setattr(dga, "fetch_page", boom)
    assert dga.suggest_from_url("https://bad.example") == {}
