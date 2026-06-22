"""Deterministic AI Act suggestions from repository signals.

This is intentionally heuristic and conservative. We only produce suggestions
when we can cite a concrete repo artifact (file/folder existence).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_act.repo_alignment import github_path_exists, parse_github_repo


@dataclass(frozen=True)
class AIActRepoSuggestion:
    field_id: str
    score: int
    kommentar: str
    confidence: float
    rationale: str
    citations: list[dict[str, Any]]


def _ev(ev_dict: dict[str, Any] | None) -> dict[str, Any]:
    if not ev_dict:
        return {}
    return {"doc_id": "", "chunk_idx": 0, "url": ev_dict.get("url"), "path": ev_dict.get("path")}


def _suggest(field_id: str, score: int, kommentar: str, confidence: float, rationale: str, evs: list[dict | None]) -> AIActRepoSuggestion:
    citations = [_ev(e) for e in evs if e]
    return AIActRepoSuggestion(
        field_id=field_id,
        score=score,
        kommentar=kommentar,
        confidence=confidence,
        rationale=rationale,
        citations=citations,
    )


def suggest_from_linked_risk(rb_name: str | None) -> AIActRepoSuggestion | None:
    """AIA-HR-01 (Risikomanagement-System, Art. 9) als erfüllt erkennen, wenn dem
    AI-Act-Projekt eine Risikobewertung verknüpft ist (#1452).

    Das verknüpfte Risikobewertungs-Projekt IST das geforderte, dokumentierte
    Risikomanagement-System über den Lebenszyklus. Ohne Verknüpfung → None
    (AIA-HR-01 bleibt offen, Verhalten unverändert)."""
    name = (rb_name or "").strip()
    if not name:
        return None
    return _suggest(
        "AIA-HR-01",
        5,
        f"Verknüpftes Risikomanagement-System: Risikobewertungs-Projekt „{name}“. "
        "Risiken, Maßnahmen und Reviews werden dort dokumentiert geführt.",
        0.95,
        "Verknüpfte Risikobewertung als Nachweis fuer das Risiko-Management (Art. 9).",
        [],
    )


def suggest_from_repo_signals(*, repo: str, branch: str = "",
                              token: str | None = None) -> list[AIActRepoSuggestion]:
    parsed = parse_github_repo(repo)
    if not parsed:
        raise ValueError("Repo-URL ungültig. Erwartet z.B. https://github.com/org/repo oder org/repo")
    owner, name = parsed

    def has(path: str) -> tuple[bool, dict | None]:
        return github_path_exists(owner, name, path, branch, token=token)  # #1064/#1065

    # Collect evidence paths
    paths = {
        # Documentation
        "README.md": has("README.md"),
        "docs": has("docs"),
        "ARCHITECTURE.md": has("ARCHITECTURE.md"),
        "docs/architecture": has("docs/architecture"),
        "MODEL_CARD.md": has("MODEL_CARD.md"),
        "model_card.md": has("model_card.md"),
        # Risk / threat modeling
        "THREAT_MODEL.md": has("THREAT_MODEL.md"),
        "threat_model.md": has("threat_model.md"),
        "RISK_REGISTER.md": has("RISK_REGISTER.md"),
        "risk_register.md": has("risk_register.md"),
        # Security / vuln mgmt
        "SECURITY.md": has("SECURITY.md"),
        ".well-known/security.txt": has(".well-known/security.txt"),
        ".github/workflows": has(".github/workflows"),
        ".github/workflows/codeql.yml": has(".github/workflows/codeql.yml"),
        ".github/workflows/codeql-analysis.yml": has(".github/workflows/codeql-analysis.yml"),
        ".github/workflows/trivy.yml": has(".github/workflows/trivy.yml"),
        ".github/workflows/osv-scanner.yml": has(".github/workflows/osv-scanner.yml"),
        ".github/workflows/cra-osv-scan.yml": has(".github/workflows/cra-osv-scan.yml"),
        ".github/workflows/cra-sbom.yml": has(".github/workflows/cra-sbom.yml"),
        ".github/workflows/sbom.yml": has(".github/workflows/sbom.yml"),
        ".github/dependabot.yml": has(".github/dependabot.yml"),
        "renovate.json": has("renovate.json"),
        "requirements.txt": has("requirements.txt"),
        "pyproject.toml": has("pyproject.toml"),
        "package.json": has("package.json"),
        # Data governance signals
        "DATASET.md": has("DATASET.md"),
        "datasheet.md": has("datasheet.md"),
        "dvc.yaml": has("dvc.yaml"),
        ".dvc": has(".dvc"),
        # Ops
        "RUNBOOK.md": has("RUNBOOK.md"),
        "INCIDENT_RESPONSE.md": has("INCIDENT_RESPONSE.md"),
    }

    def ok(p: str) -> bool:
        return bool(paths.get(p, (False, None))[0])

    def ev(p: str) -> dict | None:
        return paths.get(p, (False, None))[1]

    out: list[AIActRepoSuggestion] = []

    # AIA-HR-03 Technical documentation
    has_docs = ok("docs") or ok("ARCHITECTURE.md") or ok("docs/architecture")
    if has_docs:
        out.append(
            _suggest(
                "AIA-HR-03",
                3,
                "Technische Dokumentation im Repo vorhanden (docs/ oder ARCHITECTURE.md).",
                0.85,
                "Dokumentationsartefakte im Repo gefunden.",
                [ev("docs"), ev("ARCHITECTURE.md"), ev("docs/architecture")],
            )
        )
    elif ok("README.md"):
        out.append(
            _suggest(
                "AIA-HR-03",
                2,
                "README vorhanden; detaillierte technische Doku ist ggf. separat nachzuweisen.",
                0.6,
                "Nur README als schwacher Proxy fuer technische Doku.",
                [ev("README.md")],
            )
        )

    # AIA-HR-01 Risk management system
    has_risk = ok("THREAT_MODEL.md") or ok("threat_model.md") or ok("RISK_REGISTER.md") or ok("risk_register.md")
    if has_risk:
        out.append(
            _suggest(
                "AIA-HR-01",
                3,
                "Risk-/Threat-Model Dokumentation im Repo gefunden.",
                0.8,
                "Threat model / risk register als Nachweis fuer Risiko-Management.",
                [ev("THREAT_MODEL.md"), ev("threat_model.md"), ev("RISK_REGISTER.md"), ev("risk_register.md")],
            )
        )

    # AIA-HR-02 Data governance / data quality
    has_data_gov = ok("DATASET.md") or ok("datasheet.md") or ok("dvc.yaml") or ok(".dvc")
    if has_data_gov:
        out.append(
            _suggest(
                "AIA-HR-02",
                2,
                "Hinweise auf Data Governance (Datasheet/Dataset-Doku oder DVC) gefunden.",
                0.7,
                "Dataset/Datasheet/DVC als Proxy fuer Daten-Governance.",
                [ev("DATASET.md"), ev("datasheet.md"), ev("dvc.yaml"), ev(".dvc")],
            )
        )

    # AIA-HR-05 Transparency / user info
    has_model_card = ok("MODEL_CARD.md") or ok("model_card.md")
    if has_model_card:
        out.append(
            _suggest(
                "AIA-HR-05",
                3,
                "Model card im Repo vorhanden (Transparenz-/Nutzerinformationen).",
                0.85,
                "Model card als konkreter Nachweis fuer Nutzerinformation/Transparenz.",
                [ev("MODEL_CARD.md"), ev("model_card.md")],
            )
        )
    elif ok("README.md"):
        out.append(
            _suggest(
                "AIA-HR-05",
                2,
                "README vorhanden (Basis-Nutzerinformationen).",
                0.55,
                "README als Teilnachweis; spezifische AI-Transparenz ggf. ergänzen.",
                [ev("README.md")],
            )
        )

    # AIA-HR-07 Accuracy/robustness/cybersecurity
    has_sbom = ok(".github/workflows/cra-sbom.yml") or ok(".github/workflows/sbom.yml")
    has_osv = ok(".github/workflows/cra-osv-scan.yml") or ok(".github/workflows/osv-scanner.yml")
    has_codeql = ok(".github/workflows/codeql.yml") or ok(".github/workflows/codeql-analysis.yml")
    has_dep_update = ok(".github/dependabot.yml") or ok("renovate.json")
    any_sec = has_sbom or has_osv or has_codeql or has_dep_update
    if any_sec:
        score = 4 if (has_sbom and (has_osv or has_codeql)) else 3
        out.append(
            _suggest(
                "AIA-HR-07",
                score,
                "Security-by-design Signale im Repo gefunden (SBOM/Vuln-Scan/SAST/Dependency Updates).",
                0.9,
                "CI/Repo Security Artefakte als Nachweis fuer Cybersecurity-Massnahmen.",
                [
                    ev(".github/workflows/cra-sbom.yml"),
                    ev(".github/workflows/sbom.yml"),
                    ev(".github/workflows/cra-osv-scan.yml"),
                    ev(".github/workflows/osv-scanner.yml"),
                    ev(".github/workflows/codeql.yml"),
                    ev(".github/workflows/codeql-analysis.yml"),
                    ev(".github/dependabot.yml"),
                    ev("renovate.json"),
                ],
            )
        )

    # OPS / incidents
    has_incident = ok("INCIDENT_RESPONSE.md") or ok("RUNBOOK.md") or ok("SECURITY.md") or ok(".well-known/security.txt")
    if has_incident:
        out.append(
            _suggest(
                "AIA-HR-09",
                2,
                "Incident-/Disclosure Artefakte im Repo gefunden (Runbook/IR/SECURITY).",
                0.7,
                "Repo-Dokumente als Hinweis auf Incident Handling/Meldungsprozesse.",
                [ev("INCIDENT_RESPONSE.md"), ev("RUNBOOK.md"), ev("SECURITY.md"), ev(".well-known/security.txt")],
            )
        )

    return out
