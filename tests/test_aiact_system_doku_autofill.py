"""Unit-Tests für die A1-Auto-Fill-Vorschläge (#1020). Keine Netzwerkzugriffe."""

from __future__ import annotations

from evidence.web_fetch import FetchResult, WebFetchError

from ai_act import system_doku_autofill as mod
from ai_act.autofill_common import FieldSuggestion

README = """# Awesome Vision Model

Awesome Vision Model is an image classification system intended for
quality inspection on production lines. It detects surface defects in
real time.

## Installation

Run `pip install awesome`.
"""

ARCHITECTURE = """# Architecture

The system is a convolutional neural network (ResNet-50 backbone) with a
custom classification head, served via a gRPC microservice.

## Components
- Inference server
- Preprocessing pipeline
"""

MODEL_CARD = """# Model Card

## Intended Use
Industrial defect detection.

## Training
Trained on 1.2M labelled images using SGD with momentum over 90 epochs on
8x A100 GPUs. Data augmentation included random crops and flips.

## Performance
Top-1 accuracy 97.3%, F1 0.96 on the held-out test set.
"""

SECURITY = """# Security Policy

We follow secure SDLC practices: dependencies are scanned with Dependabot,
all releases are signed, and access is restricted via least privilege.

## Reporting
Email security@example.com.
"""


def _fake_fetch_text(owner, name, path, branch=""):
    p = path.lower()
    if p in ("readme.md",):
        return README
    if p == "architecture.md":
        return ARCHITECTURE
    if p == "model_card.md":
        return MODEL_CARD
    if p == "security.md":
        return SECURITY
    return None


def test_suggest_system_doku_fields(monkeypatch):
    monkeypatch.setattr(mod, "github_fetch_text", _fake_fetch_text)
    monkeypatch.setattr(mod, "parse_github_repo", lambda repo: ("o", "r"))

    out = mod.suggest_system_doku("o/r")

    # Mindestens 4 Felder bekommen Vorschläge
    assert len(out) >= 4, out.keys()

    # Erwartete Schlüssel (echte Spalten von aiact_system_doku)
    for key in (
        "system_name",
        "intended_purpose",
        "architecture",
        "training_methodology",
        "performance_metrics_json",
        "cybersecurity_measures",
    ):
        assert key in out, f"{key} fehlt: {list(out)}"

    # Typ + grundlegende Invarianten
    for key, sug in out.items():
        assert isinstance(sug, FieldSuggestion)
        assert sug.field == key
        assert sug.value.strip()
        assert sug.source_path
        assert 0.0 < sug.confidence <= 1.0

    assert out["system_name"].value == "Awesome Vision Model"
    assert "quality inspection" in out["intended_purpose"].value
    assert "convolutional" in out["architecture"].value.lower()
    assert "90 epochs" in out["training_methodology"].value
    assert "97.3%" in out["performance_metrics_json"].value
    assert "secure sdlc" in out["cybersecurity_measures"].value.lower()


def test_suggest_system_doku_truncates_purpose(monkeypatch):
    long_readme = "# Title\n\n" + ("word " * 400)
    monkeypatch.setattr(
        mod, "github_fetch_text",
        lambda o, n, path, branch="": long_readme if path.lower() == "readme.md" else None,
    )
    monkeypatch.setattr(mod, "parse_github_repo", lambda repo: ("o", "r"))

    out = mod.suggest_system_doku("o/r")
    assert "intended_purpose" in out
    assert len(out["intended_purpose"].value) <= mod._MAX_PURPOSE_LEN + 1


def test_suggest_system_doku_invalid_repo(monkeypatch):
    monkeypatch.setattr(mod, "parse_github_repo", lambda repo: None)
    assert mod.suggest_system_doku("not a repo") == {}


def test_suggest_from_url(monkeypatch):
    def fake_fetch(url, **kwargs):
        return FetchResult(
            url=url,
            title="ACME AI Platform",
            text="ACME AI Platform helps companies automate document review "
                 "and compliance checks.\n\nMore details follow.",
        )

    monkeypatch.setattr(mod, "fetch_page", fake_fetch)

    out = mod.suggest_from_url("https://example.com/product")
    assert "intended_purpose" in out
    sug = out["intended_purpose"]
    assert isinstance(sug, FieldSuggestion)
    assert "automate document review" in sug.value
    assert sug.source_path == "https://example.com/product"

    assert "system_name" in out
    assert out["system_name"].value == "ACME AI Platform"


def test_suggest_from_url_error_returns_empty(monkeypatch):
    def boom(url, **kwargs):
        raise WebFetchError("nope")

    monkeypatch.setattr(mod, "fetch_page", boom)
    assert mod.suggest_from_url("https://example.com") == {}
