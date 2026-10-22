"""Deterministic CRA/OWASP auto-answer rules from repository evidence.

Entry points:
  suggest_from_repo_evidence()  — focused subset (legacy/quick)
  full_repo_scan()              — comprehensive signal catalog (~60+ checks)
                                   returns OWASP + CRA prefill suggestions
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CRARepoSuggestion:
    field_id: str
    score: int
    kommentar: str
    confidence: float
    rationale: str
    citations: list[dict[str, Any]]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _ev(ev_dict: dict[str, Any] | None) -> dict[str, Any]:
    if not ev_dict:
        return {}
    return {"doc_id": "", "chunk_idx": 0, "url": ev_dict.get("url"), "path": ev_dict.get("path")}


def _suggest(field_id: str, score: int, kommentar: str, confidence: float,
             rationale: str, evs: list[dict | None]) -> CRARepoSuggestion:
    citations = [_ev(e) for e in evs if e]
    return CRARepoSuggestion(
        field_id=field_id,
        score=score,
        kommentar=kommentar,
        confidence=confidence,
        rationale=rationale,
        citations=citations,
    )


# ── Signal catalog (universal CI/policy checks) ───────────────────────

def _collect_signals(owner: str, name: str, branch: str = "") -> dict[str, tuple[bool, dict | None]]:
    """Run universal CI/policy file-existence checks.

    These are universal paths that any repo might have (SECURITY.md,
    dependabot.yml, CI workflows, etc.). Security module detection
    uses pattern-based _discover_security_files() instead.
    """
    from cra.repo_alignment import _github_path_exists

    paths = [
        # ── Documentation & policy ──────────────────────────────────────────
        "SECURITY.md",
        ".well-known/security.txt",
        "docs/development/security-tooling.md",
        # ── Dependency management ───────────────────────────────────────────
        ".github/dependabot.yml",
        ".github/dependabot.yaml",
        "renovate.json",
        "renovate.json5",
        # ── SBOM ────────────────────────────────────────────────────────────
        ".github/workflows/cra-sbom.yml",
        ".github/workflows/sbom.yml",
        # ── Vulnerability / SAST scanning ───────────────────────────────────
        ".github/workflows/codeql.yml",
        ".github/workflows/codeql-analysis.yml",
        ".github/workflows/trivy.yml",
        ".github/workflows/osv-scanner.yml",
        ".trivy.yml",
        ".snyk",
        # ── Secret scanning ─────────────────────────────────────────────────
        ".gitleaks.toml",
        ".gitleaks.yml",
        ".github/secret_scanning.yml",
        # ── Build / CI ──────────────────────────────────────────────────────
        ".github/workflows",
        ".gitlab-ci.yml",
        # ── Code review / ownership ─────────────────────────────────────────
        ".github/CODEOWNERS",
        # ── Documentation ───────────────────────────────────────────────────
        "README.md",
        "README.rst",
        "docs",
        "CHANGELOG.md",
        "CHANGELOG",
        "CHANGES.md",
        # ── License ─────────────────────────────────────────────────────────
        "LICENSE",
        "LICENSE.md",
        "LICENSE.txt",
        # ── Tests ───────────────────────────────────────────────────────────
        "tests",
        "test",
        "__tests__",
        "spec",
        # ── Dependency files (evidence of managed dependencies) ─────────────
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "go.mod",
        "Cargo.toml",
        "pom.xml",
        # ── Container / infrastructure ──────────────────────────────────────
        "Dockerfile",
        ".hadolint.yml",
        ".dockerignore",
        # ── Contribution / disclosure process ───────────────────────────────
        "CONTRIBUTING.md",
        ".github/ISSUE_TEMPLATE",
        # ── Release process ─────────────────────────────────────────────────
        ".github/workflows/release.yml",
        ".github/workflows/publish.yml",
    ]

    signals: dict[str, tuple[bool, dict | None]] = {}
    for path in paths:
        ok, ev = _github_path_exists(owner, name, path, branch)
        signals[path] = (ok, ev)
    return signals


def _build_suggestions(owner: str, name: str,
                        signals: dict[str, tuple[bool, dict | None]]) -> list[CRARepoSuggestion]:
    results: list[CRARepoSuggestion] = []
    base_url = f"https://github.com/{owner}/{name}"

    def has(path: str) -> bool:
        return signals.get(path, (False, None))[0]

    def ev(path: str) -> dict | None:
        return signals.get(path, (False, None))[1]

    # ── AI1 controls (Software development lifecycle / secure coding) ─────────

    has_sast = has(".github/workflows/codeql.yml") or has(".github/workflows/codeql-analysis.yml")
    if has_sast:
        sast_evs = [ev(".github/workflows/codeql.yml"), ev(".github/workflows/codeql-analysis.yml")]
        results.append(_suggest(
            "AI1-02", 4,
            "Statische Code-Analyse (CodeQL) im CI konfiguriert.",
            0.9, "GitHub Actions CodeQL-Workflow gefunden.", sast_evs,
        ))

    has_vuln_scan = (has(".github/workflows/trivy.yml") or has(".github/workflows/osv-scanner.yml")
                     or has(".trivy.yml") or has(".snyk"))
    if has_vuln_scan:
        vscan_evs = [ev(".github/workflows/trivy.yml"), ev(".github/workflows/osv-scanner.yml"),
                     ev(".trivy.yml"), ev(".snyk")]
        results.append(_suggest(
            "AI1-03", 4,
            "Vulnerability-Scanning im CI konfiguriert (Trivy/OSV-Scanner/Snyk).",
            0.9, "Vulnerability-Scan-Konfigurationsdatei gefunden.", vscan_evs,
        ))
    else:
        results.append(_suggest(
            "AI1-03", 0,
            "Kein Vulnerability-Scan-Workflow gefunden (.github/workflows/trivy.yml o. ä.).",
            0.8, "Kein Scan-Signal im Repo.", [],
        ))

    has_tests = has("tests") or has("test") or has("__tests__") or has("spec")
    if has_tests:
        test_evs = [ev("tests"), ev("test"), ev("__tests__"), ev("spec")]
        results.append(_suggest(
            "AI1-04", 3,
            "Test-Verzeichnis im Repo vorhanden.",
            0.7, "Hinweis auf automatisierte Tests gefunden.", test_evs,
        ))

    # ── AI2 controls (Vulnerability handling / SBOM) ─────────────────────────

    has_security_md = has("SECURITY.md")
    has_security_txt = has(".well-known/security.txt")
    if has_security_md or has_security_txt:
        pol_evs = [ev("SECURITY.md"), ev(".well-known/security.txt")]
        results.append(_suggest(
            "AI2-01", 4,
            "CVD-Policy / Security-Disclosure-Kontakt vorhanden (SECURITY.md / security.txt).",
            0.9, "Policy-Datei(en) im Repo gefunden.", pol_evs,
        ))
        results.append(_suggest(
            "AI2-05", 4,
            "CVD-Policy vorhanden – Nutzer können Schwachstellen melden.",
            0.9, "SECURITY.md / security.txt als Nachweis.", pol_evs,
        ))
    else:
        results.append(_suggest(
            "AI2-01", 0,
            "Keine CVD-Policy gefunden (SECURITY.md oder .well-known/security.txt fehlen).",
            0.85, "Kein Policy-Signal.", [],
        ))

    has_sbom_wf = has(".github/workflows/cra-sbom.yml") or has(".github/workflows/sbom.yml")
    has_dep_files = (has("requirements.txt") or has("pyproject.toml") or has("package.json")
                     or has("go.mod") or has("Cargo.toml") or has("pom.xml"))
    if has_sbom_wf:
        sbom_evs = [ev(".github/workflows/cra-sbom.yml"), ev(".github/workflows/sbom.yml")]
        results.append(_suggest(
            "AI2-02", 4,
            "SBOM-Erzeugung als GitHub Actions Workflow konfiguriert.",
            0.9, "SBOM-Workflow-Datei gefunden.", sbom_evs,
        ))
    elif has_dep_files:
        dep_evs = [ev("requirements.txt"), ev("pyproject.toml"), ev("package.json"),
                   ev("go.mod"), ev("Cargo.toml"), ev("pom.xml")]
        results.append(_suggest(
            "AI2-02", 2,
            "Dependency-Dateien gefunden (SBOM-Erzeugung möglicherweise ableitbar); "
            "kein dedizierter SBOM-Workflow vorhanden.",
            0.6, "Dependency-Manifest als Teilnachweis.", dep_evs,
        ))

    has_dep_bot = has(".github/dependabot.yml") or has(".github/dependabot.yaml")
    has_renovate = has("renovate.json") or has("renovate.json5")
    if has_dep_bot or has_renovate:
        dep_evs2 = [ev(".github/dependabot.yml"), ev(".github/dependabot.yaml"),
                    ev("renovate.json"), ev("renovate.json5")]
        results.append(_suggest(
            "AI2-03", 3,
            "Automatisiertes Dependency-Update konfiguriert (Dependabot/Renovate).",
            0.85, "Update-Konfigurationsdatei gefunden.", dep_evs2,
        ))
    else:
        results.append(_suggest(
            "AI2-03", 0,
            "Kein automatisiertes Dependency-Update-Tool gefunden (Dependabot/Renovate fehlen).",
            0.8, "Kein Update-Tool-Signal.", [],
        ))

    has_disclosure_template = has(".github/ISSUE_TEMPLATE")
    if has_disclosure_template:
        results.append(_suggest(
            "AI2-05", 3,
            "Issue-Templates vorhanden – strukturierte Schwachstellen-Meldung möglich.",
            0.7, ".github/ISSUE_TEMPLATE gefunden.", [ev(".github/ISSUE_TEMPLATE")],
        ))

    has_release_wf = has(".github/workflows/release.yml") or has(".github/workflows/publish.yml")
    if has_release_wf:
        rel_evs = [ev(".github/workflows/release.yml"), ev(".github/workflows/publish.yml")]
        results.append(_suggest(
            "AI2-06", 3,
            "Automatisierter Release-Prozess als Workflow konfiguriert.",
            0.8, "Release/Publish-Workflow gefunden.", rel_evs,
        ))

    has_changelog = has("CHANGELOG.md") or has("CHANGELOG") or has("CHANGES.md")
    if has_changelog:
        cl_evs = [ev("CHANGELOG.md"), ev("CHANGELOG"), ev("CHANGES.md")]
        results.append(_suggest(
            "AI2-07", 3,
            "CHANGELOG vorhanden – Dokumentation von Änderungen und Patches.",
            0.8, "CHANGELOG-Datei gefunden.", cl_evs,
        ))

    has_secret_scan = (has(".gitleaks.toml") or has(".gitleaks.yml")
                       or has(".github/secret_scanning.yml"))
    if has_secret_scan:
        ss_evs = [ev(".gitleaks.toml"), ev(".gitleaks.yml"), ev(".github/secret_scanning.yml")]
        results.append(_suggest(
            "AI2-08", 3,
            "Secret-Scanning konfiguriert (Gitleaks / GitHub Secret Scanning).",
            0.85, "Secret-Scan-Konfiguration gefunden.", ss_evs,
        ))

    # ── ART13 controls (Technical documentation) ─────────────────────────────

    has_readme = has("README.md") or has("README.rst")
    if has_readme:
        rm_evs = [ev("README.md"), ev("README.rst")]
        results.append(_suggest(
            "ART13-01", 3,
            "README vorhanden – Basisinformation zum Produkt.",
            0.7, "README-Datei gefunden.", rm_evs,
        ))

    has_docs_dir = has("docs")
    if has_docs_dir:
        results.append(_suggest(
            "ART13-03", 3,
            "Technische Dokumentation im Repo abgelegt (docs/).",
            0.7, "docs/ Ordner gefunden.", [ev("docs")],
        ))

    has_license = has("LICENSE") or has("LICENSE.md") or has("LICENSE.txt")
    if has_license:
        lic_evs = [ev("LICENSE"), ev("LICENSE.md"), ev("LICENSE.txt")]
        results.append(_suggest(
            "ART13-05", 4,
            "Lizenzinformation vorhanden.",
            0.95, "LICENSE-Datei gefunden.", lic_evs,
        ))

    has_contributing = has("CONTRIBUTING.md")
    if has_contributing:
        results.append(_suggest(
            "ART13-04", 3,
            "CONTRIBUTING.md vorhanden – Entwicklungs- und Beitragsprozess dokumentiert.",
            0.7, "CONTRIBUTING.md gefunden.", [ev("CONTRIBUTING.md")],
        ))

    # ── IMPL (Build / CI) ─────────────────────────────────────────────────────

    has_ci = has(".github/workflows") or has(".gitlab-ci.yml")
    if has_ci:
        ci_evs = [ev(".github/workflows"), ev(".gitlab-ci.yml")]
        results.append(_suggest(
            "AI1-01", 3,
            "CI/CD-Pipeline konfiguriert (GitHub Actions / GitLab CI).",
            0.8, "CI-Konfiguration gefunden.", ci_evs,
        ))

    has_container = has("Dockerfile")
    has_hadolint = has(".hadolint.yml")
    if has_container and has_hadolint:
        results.append(_suggest(
            "AI1-05", 3,
            "Container (Dockerfile) mit Hadolint-Konfiguration – sichere Container-Builds.",
            0.75, "Dockerfile + .hadolint.yml gefunden.",
            [ev("Dockerfile"), ev(".hadolint.yml")],
        ))
    elif has_container:
        results.append(_suggest(
            "AI1-05", 2,
            "Dockerfile gefunden; kein Hadolint-Linting konfiguriert.",
            0.6, "Dockerfile ohne Sicherheits-Linting.", [ev("Dockerfile")],
        ))

    return results


# ── Universal security file discovery (works for ANY repo) ─────────────
#
# Instead of hardcoded paths, we:
#   1. List the repo root directory via GitHub Contents API
#   2. Also list common source directories (src/, app/, lib/, shared/, utils/ etc.) if they exist
#   3. Match discovered file names against universal patterns
#   4. Map matched files to OWASP and/or CRA controls
#
# This works for any project, not just AI Compliance Suite.

# Universal file name patterns → (owasp|cra) mappings.
# Each entry: (pattern_glob, [(field_id, score, comment, confidence, rationale), ...])
# pattern_glob is fnmatch-style (* matches anything, ? matches one char).
# The category key is a short description for evidence attribution.

_UNIVERSAL_NAME_PATTERNS: dict[str, dict[str, list[tuple[str, int, str, float, str]]]] = {
    # ── Config / Settings Management → PC-C2 + PC-C8 → AI2-04 ──────────
    "*config*.*": {
        "owasp": [
            ("OWASP-PC-C2", 4, "Konfigurationsverwaltung mit sicherer I/O (atomisches Schreiben, restriktive Rechte).",
             0.8, "Config-Datei(en) gefunden: typischerweise mit Zugriffsschutz und/oder Integritätssicherung."),
            ("OWASP-PC-C8", 3, "Konfigurationsdateien mit restriktiven Berechtigungen/deployment-spezifischen Secrets.",
             0.7, "Config-Datei gefunden: Hinweis auf Schutz von Konfigurationsdaten."),
        ],
        "cra": [
            ("AI2-04", 4, "Sichere Konfigurationsverwaltung (Config-Dateien mit Zugriffssteuerung und Integrität).",
             0.8, "CRA AI2-04 (Cybersecurity): Config-Management deutet auf systematische Sicherheitskontrollen hin."),
        ],
    },
    # ── Audit / Logging → PC-C2 + PC-C9 → AI2-04 ──────────────────────
    "*audit*.*": {
        "owasp": [
            ("OWASP-PC-C2", 3, "Audit-Modul für sicherheitsrelevante Aktionen.",
             0.8, "Audit-Datei gefunden: Framework für nachvollziehbare Sicherheitsereignisse."),
            ("OWASP-PC-C9", 4, "Audit-Logging für sicherheitsrelevante Ereignisse strukturiert erfasst.",
             0.85, "Audit-Datei gefunden: systematische Protokollierung von Sicherheitsereignissen."),
        ],
        "cra": [
            ("AI2-04", 4, "Audit-/Logging-System für Sicherheitsereignisse implementiert.",
             0.85, "CRA AI2-04 (Cybersecurity): Nachvollziehbare Protokollierung sicherheitsrelevanter Aktionen."),
        ],
    },
    # ── Logging Setup → PC-C9 (no CRA usually, but useful) ────────────
    "*log*.*": {
        "owasp": [
            ("OWASP-PC-C9", 3, "Logging-Konfiguration für technische Laufzeit-Logs.",
             0.75, "Logging-Datei gefunden: ergänzt Audit um technische Laufzeitinformationen."),
        ],
    },
    # ── Encryption / Crypto → PC-C2 + PC-C8 → AI2-04 ──────────────────
    "*crypto*.*": {
        "owasp": [
            ("OWASP-PC-C2", 4, "Kryptografische Bibliothek für sicheres Framework.",
             0.85, "Crypto-Datei gefunden: Security-Framework mit Verschlüsselungsfunktionen."),
            ("OWASP-PC-C8", 4, "Datenverschlüsselung im Ruhezustand implementiert.",
             0.85, "Crypto-Datei gefunden: Schutz sensibler Daten durch Verschlüsselung."),
        ],
        "cra": [
            ("AI2-04", 4, "Kryptografische Funktionen für Datenschutz und Integrität.",
             0.85, "CRA AI2-04 (Cybersecurity): Verschlüsselung als Schutzmaßnahme für sensible Daten."),
        ],
    },
    # ── Database / DB Security → PC-C3 + PC-C7 + PC-C8 → AI2-04 ───────
    "*db*.*": {
        "owasp": [
            ("OWASP-PC-C3", 4, "Datenbankzugriff mit Sicherheitskontrollen (Path-Containment, restriktive Rechte).",
             0.8, "DB-Datei gefunden: Hinweis auf gesicherten Datenbankzugriff."),
            ("OWASP-PC-C7", 3, "Datenbank-Zugriffskontrolle implementiert.",
             0.75, "DB-Datei gefunden: Zugriffssteuerung auf Datenbankebene."),
            ("OWASP-PC-C8", 3, "Datenbank-Dateien mit Zugriffsschutz (Owner-only-Berechtigungen).",
             0.75, "DB-Datei gefunden: Schutz von Datenbankdateien vor unbefugtem Zugriff."),
        ],
        "cra": [
            ("AI2-04", 4, "Datenbankzugriff mit Sicherheitskontrollen (Zugriffssteuerung, Path-Containment).",
             0.8, "CRA AI2-04 (Cybersecurity): DB-Sicherheit durch Zugriffskontrollen."),
        ],
    },
    # ── Input Validation → PC-C5 → AI1-02 ─────────────────────────────
    "*valid*.*": {
        "owasp": [
            ("OWASP-PC-C5", 4, "Eingabevalidierung für Benutzereingaben und externe Daten.",
             0.85, "Validierungs-Datei gefunden: systematische Prüfung von Eingabedaten."),
        ],
        "cra": [
            ("AI1-02", 3, "Eingabevalidierung für externe Daten implementiert.",
             0.8, "CRA AI1-02 (Data Governance): Validierung reduziert Risiken durch fehlerhafte/missbräuchliche Eingaben."),
        ],
    },
    # ── Error Handling → PC-C10 → AI2-07 ──────────────────────────────
    "*error*.*": {
        "owasp": [
            ("OWASP-PC-C10", 4, "Strukturiertes Exception-Handling und Fehlerbehandlung.",
             0.85, "Error-Handling-Datei gefunden: systematische Behandlung von Ausnahmen."),
        ],
        "cra": [
            ("AI2-07", 3, "Strukturierte Fehlerbehandlung für Benutzeroberfläche/API.",
             0.8, "CRA AI2-07 (Logging/Fehlerbehandlung): Strukturierte Fehlerbehandlung."),
        ],
    },
    # ── Secrets / Tokens → PC-C8 → AI1-02 ─────────────────────────────
    "*secret*.*": {
        "owasp": [
            ("OWASP-PC-C8", 4, "Secret-Management für API-Keys, Tokens und sensible Zugangsdaten.",
             0.85, "Secret-Datei gefunden: Schutz sensibler Authentifizierungsdaten."),
        ],
        "cra": [
            ("AI1-02", 4, "Sensitive Zugangsdaten werden geschützt verwaltet (Secrets-Management).",
             0.85, "CRA AI1-02 (Data Governance): Schutz sensibler Daten durch Secrets-Management."),
        ],
    },
    # ── Encoding / Escaping → PC-C4 → AI2-06 ──────────────────────────
    "*encod*.*": {
        "owasp": [
            ("OWASP-PC-C4", 4, "Output-Encoding/-Escaping zum Schutz vor Injection-Angriffen.",
             0.85, "Encoding-Datei gefunden: kontextabhängiges Escaping für sichere Ausgaben."),
        ],
        "cra": [
            ("AI2-06", 3, "Output-Encoding für sichere Datenausgabe (z. B. CSV, HTML, JSON).",
             0.8, "CRA AI2-06 (Output-Handling): Schutz vor Injection in generierten Ausgaben."),
        ],
    },
    # ── Escaping → PC-C4 ──────────────────────────────────────────────
    "*escap*.*": {
        "owasp": [
            ("OWASP-PC-C4", 3, "Output-Escaping für kontextspezifische Ausgaben.",
             0.8, "Escaping-Datei gefunden: Schutz vor Injection durch Escape-Mechanismen."),
        ],
    },
    # ── Issue / Sync → AI1-05 (Human Oversight) ───────────────────────
    "*issue*.*": {
        "cra": [
            ("AI1-05", 3, "Issue-/Task-Management für Nachverfolgung und Review-Prozesse.",
             0.75, "Issue-Datei gefunden: ermöglicht menschliche Überprüfung und Nachverfolgung."),
        ],
    },
    # ── SBOM / Lieferkette → IMPL-03 (Supply Chain Security) ──────────
    # #1488: Das frühere "*engine*"-Mapping war semantisch falsch (IMPL-03 ist
    # Lieferkettensicherheit, nicht „Engine-Tooling"). Jetzt echte Supply-Chain-
    # Signale: SBOM-Artefakte (SPDX/CycloneDX). Dependabot/Renovate decken
    # _collect_signals bereits ab (kontinuierliches Drittkomponenten-Monitoring).
    "*sbom*": {
        "cra": [
            ("IMPL-03", 3, "SBOM-Artefakt vorhanden → Transparenz über Drittkomponenten.",
             0.8, "SBOM-Datei gefunden: Basis für Lieferketten-/Komponenten-Überwachung."),
        ],
    },
    "*.spdx.json": {
        "cra": [
            ("IMPL-03", 3, "SPDX-SBOM vorhanden → Lieferketten-Transparenz.",
             0.8, "SPDX-SBOM gefunden."),
        ],
    },
    "*.cdx.json": {
        "cra": [
            ("IMPL-03", 3, "CycloneDX-SBOM vorhanden → Lieferketten-Transparenz.",
             0.8, "CycloneDX-SBOM gefunden."),
        ],
    },
    # ── Security documentation → PC-C1 → AI1-03 ───────────────────────
    "*security*.*": {
        "owasp": [
            ("OWASP-PC-C1", 3, "Sicherheitsdokumentation mit Architektur- und Bedrohungsanalyse.",
             0.8, "Security-Datei gefunden: dokumentierte Sicherheitsarchitektur."),
        ],
        "cra": [
            ("AI1-03", 3, "Technische Sicherheitsdokumentation verfügbar.",
             0.8, "CRA AI1-03 (Technical Documentation): Sicherheitsaspekte dokumentiert."),
        ],
    },
    # ── Sanitization / Cleaning → PC-C4 + PC-C5 → AI1-02 ──────────────
    "*sanit*.*": {
        "owasp": [
            ("OWASP-PC-C4", 3, "Output-Bereinigung für sichere Datenausgabe.",
             0.75, "Sanitize-Datei gefunden: Bereinigung von Ausgabedaten."),
            ("OWASP-PC-C5", 3, "Eingabebereinigung für externe/ungeprüfte Datenquellen.",
             0.75, "Sanitize-Datei gefunden: Validierung und Bereinigung von Eingaben."),
        ],
        "cra": [
            ("AI1-02", 3, "Datenbereinigung (Sanitization) für Eingabe- und Ausgabedaten.",
             0.75, "CRA AI1-02 (Data Governance): Sanitisierung reduziert Kontamination durch schadhafte Daten."),
        ],
    },
    # ── Authentication / Access → PC-C6 + PC-C7 → AI2-04 (#576) ───────
    "*auth*.*": {
        "owasp": [
            ("OWASP-PC-C6", 4, "Digital-Identity-Verwaltung (Authentifizierung, Session, Passwort-Speicher).",
             0.85, "Auth-Datei gefunden: Identitätsverwaltung und Authentifizierungsflows."),
            ("OWASP-PC-C7", 4, "Authentifizierungs-/Autorisierungsmodul für Zugriffskontrolle.",
             0.85, "Auth-Datei gefunden: Zugriffssteuerung auf Benutzerebene."),
        ],
        "cra": [
            ("AI2-04", 4, "Authentifizierung und Zugriffskontrolle implementiert.",
             0.85, "CRA AI2-04 (Cybersecurity): Zugriffskontrolle durch Authentifizierung."),
        ],
    },
    # ── Login/Session/MFA/Token → PC-C6 (Digital Identity) (#576) ─────
    "*login*.*": {
        "owasp": [
            ("OWASP-PC-C6", 4, "Login-Flow für Digital-Identity-Verifikation.",
             0.85, "Login-Datei gefunden: Authentifizierungs-Endpoint vorhanden."),
        ],
        "cra": [
            ("AI2-04", 4, "Login-Flow als zentrale Zugangskontrolle implementiert.",
             0.8, "CRA AI2-04: gesicherter Login schützt vor unbefugtem Zugriff."),
        ],
    },
    "*session*.*": {
        "owasp": [
            ("OWASP-PC-C6", 4, "Session-Management (Tokens, Cookies, Lifetime, Renewal).",
             0.85, "Session-Datei gefunden: Lifecycle-Management für Identity."),
        ],
        "cra": [
            ("AI2-04", 3, "Session-Management implementiert.", 0.8, "CRA AI2-04: Sitzungsverwaltung als Cybersecurity-Komponente."),
        ],
    },
    "*token*.*": {
        "owasp": [
            ("OWASP-PC-C6", 4, "Token-basierte Authentifizierung (JWT/Bearer/Refresh).",
             0.8, "Token-Datei gefunden: tokengestützte Identity-Flows."),
        ],
        "cra": [
            ("AI2-04", 3, "Token-Mechanismus für Zugriffskontrolle.", 0.75, "CRA AI2-04: Tokens als kurzlebige Zugriffsnachweise."),
        ],
    },
    "*totp*.*": {
        "owasp": [
            ("OWASP-PC-C6", 5, "Multi-Faktor-Authentifizierung (TOTP/2FA).",
             0.9, "TOTP-Datei gefunden: starke Authentifizierung implementiert."),
        ],
        "cra": [
            ("AI2-04", 5, "Mehrstufige Authentifizierung (MFA) implementiert.",
             0.9, "CRA AI2-04: MFA als hoher Schutz vor Account-Übernahme."),
        ],
    },
    "*2fa*.*": {
        "owasp": [
            ("OWASP-PC-C6", 5, "2-Faktor-Authentifizierung implementiert.",
             0.9, "2FA-Datei gefunden: starke Authentifizierung."),
        ],
        "cra": [
            ("AI2-04", 5, "2FA-Verfahren erhöht Authentifizierungsstärke.",
             0.9, "CRA AI2-04: 2FA-Schutz."),
        ],
    },
    "*password*.*": {
        "owasp": [
            ("OWASP-PC-C6", 4, "Passwort-Management (Hashing, Reset, Policy).",
             0.8, "Password-Datei gefunden: Identity-Credentials-Management."),
        ],
        "cra": [
            ("AI2-04", 3, "Passwort-Handling als Identity-Baustein.", 0.75, "CRA AI2-04: Passwort-Hygiene."),
        ],
    },
    # ── Permissions → PC-C7 + PC-C8 → AI2-04 ──────────────────────────
    "*perm*.*": {
        "owasp": [
            ("OWASP-PC-C7", 4, "Berechtigungsverwaltung für Dateisystem-/Ressourcenzugriff.",
             0.85, "Permission-Datei gefunden: systematische Zugriffssteuerung."),
            ("OWASP-PC-C8", 3, "Restriktive Berechtigungen für Daten und Ressourcen.",
             0.8, "Permission-Datei gefunden: Schutz von Daten durch minimale Berechtigungen."),
        ],
        "cra": [
            ("AI2-04", 4, "Berechtigungs- und Zugriffssteuerung implementiert.",
             0.85, "CRA AI2-04 (Cybersecurity): Zugriffskontrolle durch gestaffelte Berechtigungen."),
        ],
    },
    # ── Integrity / Checksum → PC-C2 → AI2-04 ─────────────────────────
    "*integrity*.*": {
        "owasp": [
            ("OWASP-PC-C2", 3, "Integritätsprüfung (SHA-256/Hash-Manifest) für Dateien.",
             0.8, "Integritäts-Datei gefunden: Sicherheits-Framework für Dateiintegrität."),
        ],
        "cra": [
            ("AI2-04", 4, "Runtime-Integritätsprüfung für Software-Module implementiert.",
             0.85, "CRA AI2-04 (Integrität): stellt sicher, dass nur unveränderte Module ausgeführt werden."),
        ],
    },
    # ── Network / Communication → PC-C5 + PC-C8 → AI2-04 ──────────────
    "*net*.*": {
        "owasp": [
            ("OWASP-PC-C5", 3, "Netzwerkvalidierung/-absicherung (Egress-Kontrolle, Host-Validierung).",
             0.75, "Netzwerk-Datei gefunden: Validierung ausgehender Verbindungen."),
            ("OWASP-PC-C8", 3, "Netzwerkdatenfluss geschützt (HTTPS-only, expliziter Consent).",
             0.75, "Netzwerk-Datei gefunden: Schutz von Daten in der Kommunikation."),
        ],
        "cra": [
            ("AI2-04", 4, "Netzwerkzugriff gehärtet (Egress-Kontrolle, verschlüsselte Kommunikation).",
             0.8, "CRA AI2-04 (Cybersecurity): mehrstufige Netzwerkkontrolle."),
        ],
    },
    # ── Redaction / Masking → PC-C8 → AI1-02 ──────────────────────────
    "*redact*.*": {
        "owasp": [
            ("OWASP-PC-C8", 4, "Daten-Redaktion für sensible Informationen (API-Keys, Tokens, PII).",
             0.85, "Redact-Datei gefunden: automatische Schwärzung sensibler Daten."),
        ],
        "cra": [
            ("AI1-02", 4, "Sensitive Daten werden vor Persistierung/Versand redigiert.",
             0.85, "CRA AI1-02 (Data Governance): Reduktion personenbezogener/sensibler Daten."),
        ],
    },
    # ── Security policy / Documentation → PC-C1 → AI1-01 + AI1-03 ─────
    "SECURITY.md": {
        "owasp": [
            ("OWASP-PC-C1", 4, "Sicherheitsrichtlinie mit Meldeweg für Schwachstellen (SECURITY.md).",
             0.9, "Definiert Security-Requirements und verantwortlichen Meldeweg."),
        ],
        "cra": [
            ("AI1-01", 3, "Security-Richtlinie dokumentiert in SECURITY.md.",
             0.8, "CRA AI1-01 (Risk Management): Dokumentierte Sicherheitsprozesse."),
        ],
    },
    # ── Dependabot → PC-C2 → AI2-01 + AI2-02 ──────────────────────────
    ".github/dependabot.yml": {
        "owasp": [
            ("OWASP-PC-C2", 4, "Dependabot für automatische Dependency-Updates.",
             0.9, "GitHub-natives Security-Framework für Abhängigkeitsmanagement."),
        ],
        "cra": [
            ("AI2-01", 4, "Automatisiertes Dependency-Update-Management über Dependabot.",
             0.9, "CRA AI2-01 (Vulnerability Management): Regelmäßige Aktualisierung von Abhängigkeiten."),
            ("AI2-02", 3, "Dependabot erzeugt SBOM-relevante Dependency-Updates.",
             0.8, "CRA AI2-02 (SBOM): Nachvollziehbarkeit von Abhängigkeiten."),
        ],
    },
    # ── Renovate → PC-C2 → AI2-03 ─────────────────────────────────────
    "renovate.json": {
        "owasp": [
            ("OWASP-PC-C2", 3, "Renovate Bot für automatische Dependency-Updates.",
             0.85, "Alternatives Security-Framework für Dependency-Management."),
        ],
    },
    # ── CODEOWNERS → PC-C7 ────────────────────────────────────────────
    ".github/CODEOWNERS": {
        "owasp": [
            ("OWASP-PC-C7", 3, "CODEOWNERS für Ownership/Review-Struktur.",
             0.85, "Definiert Verantwortlichkeiten für Code-Reviews und Zugriffskontrolle."),
        ],
    },
    # ── CI/CD Workflows → PC-C9 → IMPL-01 + IMPL-02 ───────────────────
    ".github/workflows": {
        "owasp": [
            ("OWASP-PC-C9", 3, "CI/CD-Workflows mit automatisierten Sicherheitsprüfungen.",
             0.85, "Workflows für SBOM, OSV-Scan, Evidence Pack, Docs-Deployment."),
        ],
        "cra": [
            ("IMPL-01", 4, "CI/CD-Pipeline mit Sicherheits-Scans (OSV, Dependabot) und SBOM-Generierung.",
             0.9, "CRA IMPL-01 (Prozesse): Entwicklungsprozess mit integrierten Sicherheitsprüfungen."),
            ("IMPL-02", 3, "CI-Artefakte als Compliance-Nachweise speicherbar.",
             0.8, "CRA IMPL-02 (Dokumentation): Automatisch generierte Nachweise aus CI-Pipeline."),
        ],
    },
}


def _discover_security_files(
    owner: str, name: str, branch: str = "",
) -> dict[str, dict | None]:
    """Discover security-relevant files via directory listing + name pattern matching.

    Lists the repo root (and common source directories) via GitHub Contents API,
    then matches file names against _UNIVERSAL_NAME_PATTERNS. Works for ANY repo,
    not just AI Compliance Suite.

    Returns dict of {matched_path: evidence_metadata}.
    """
    import fnmatch
    from cra.repo_alignment import _github_path_exists, _gh_api_json

    discovered: dict[str, dict | None] = {}

    # Step 1: always check universal exact paths first (fast, no listing needed)
    exact_paths = [
        "SECURITY.md",
        ".github/dependabot.yml",
        ".github/CODEOWNERS",
        ".github/workflows",
    ]
    for path in exact_paths:
        ok, ev = _github_path_exists(owner, name, path, branch)
        if ok and ev:
            discovered[path] = ev

    # Step 2: list repo root directory
    try:
        root_api = f"repos/{owner}/{name}/contents/"
        if branch:
            import urllib.parse
            root_api += f"?ref={urllib.parse.quote(branch, safe='')}"
        root_items = _gh_api_json(root_api)
    except Exception:
        root_items = []

    # Collect all file entries from root
    all_paths: list[tuple[str, dict]] = []
    if isinstance(root_items, list):
        for item in root_items:
            p = item.get("path", "")
            tp = item.get("type")
            url = item.get("html_url", "")
            if tp == "file":
                all_paths.append((p, {"provider": "github", "owner": owner, "repo": name, "path": p, "url": url}))
            elif tp == "dir":
                # Check if directory name matches patterns
                all_paths.append((p, {"provider": "github", "owner": owner, "repo": name, "path": p, "url": url}))

    # Step 3: also list common source directories if they exist
    source_dirs = ["src", "app", "lib", "shared", "utils", "helpers", "core"]
    for sd in source_dirs:
        try:
            sd_api = f"repos/{owner}/{name}/contents/{sd}"
            if branch:
                import urllib.parse
                sd_api += f"?ref={urllib.parse.quote(branch, safe='')}"
            sd_items = _gh_api_json(sd_api)
            if isinstance(sd_items, list):
                for item in sd_items:
                    if item.get("type") == "file":
                        p = item.get("path", "")
                        url = item.get("html_url", "")
                        all_paths.append((p, {"provider": "github", "owner": owner, "repo": name, "path": p, "url": url}))
        except Exception:
            pass

    # Step 4: also check well-known deeper paths
    deep_paths = [
        "evidence", "vcs", "prefill", "risikobewertung",
        "docs/development", "docs/security",
    ]
    for dp in deep_paths:
        try:
            import urllib.parse
            dp_api = f"repos/{owner}/{name}/contents/{dp}"
            if branch:
                dp_api += f"?ref={urllib.parse.quote(branch, safe='')}"
            dp_items = _gh_api_json(dp_api)
            if isinstance(dp_items, list):
                for item in dp_items:
                    p = item.get("path", "")
                    url = item.get("html_url", "")
                    all_paths.append((p, {"provider": "github", "owner": owner, "repo": name, "path": p, "url": url}))
        except Exception:
            pass

    # Step 5: match all discovered paths against universal patterns
    pattern_keys = list(_UNIVERSAL_NAME_PATTERNS.keys())
    for path, ev in all_paths:
        fname = path.split("/")[-1]
        for pattern in pattern_keys:
            if fnmatch.fnmatch(fname, pattern) or fnmatch.fnmatch(path, pattern):
                if path not in discovered:
                    discovered[path] = ev
                break  # first matching pattern wins

    return discovered


# #576: Identity-Libraries die OWASP-PC-C6 belegen
_IDENTITY_LIBS = {
    # Password hashing
    'bcrypt': 'Password-Hashing (bcrypt)',
    'argon2': 'Password-Hashing (argon2)',
    'argon2-cffi': 'Password-Hashing (argon2-cffi)',
    'passlib': 'Password-Hashing (passlib)',
    'scrypt': 'Password-Hashing (scrypt)',
    # JWT
    'pyjwt': 'JWT-Token (PyJWT)',
    'jsonwebtoken': 'JWT-Token (jsonwebtoken)',
    'flask-jwt-extended': 'JWT-Token (flask-jwt-extended)',
    'jose': 'JWT/JWE (python-jose)',
    'python-jose': 'JWT/JWE (python-jose)',
    # OAuth/OIDC
    'authlib': 'OAuth/OIDC (Authlib)',
    'oauthlib': 'OAuth (oauthlib)',
    'requests-oauthlib': 'OAuth (requests-oauthlib)',
    'python-social-auth': 'Social Login',
    'passport': 'OAuth/Social Login (Passport)',
    'next-auth': 'OAuth/Social Login (NextAuth)',
    # MFA / TOTP
    'pyotp': 'TOTP/2FA (pyotp)',
    'otplib': 'TOTP/2FA (otplib)',
    'speakeasy': 'TOTP/2FA (speakeasy)',
    # SAML
    'python3-saml': 'SAML (python3-saml)',
    'passport-saml': 'SAML (passport-saml)',
}


def _detect_identity_libs(owner: str, name: str, branch: str = "") -> list[str]:
    """Lädt requirements.txt + package.json + pyproject.toml und matched Identity-Libs.

    #576: erkennt OWASP-PC-C6 (Digital Identity) auch wenn keine Datei
    "auth"/"login" o.ä. heißt.
    """
    import base64
    from cra.repo_alignment import _gh_api_json

    matches: set[str] = set()
    for path in ("requirements.txt", "pyproject.toml", "package.json", "package-lock.json", "Pipfile"):
        try:
            data = _gh_api_json(f"repos/{owner}/{name}/contents/{path}" + (f"?ref={branch}" if branch else ""))
        except Exception:
            continue
        try:
            content = base64.b64decode((data or {}).get("content", "")).decode("utf-8", errors="replace").lower()
        except Exception:
            continue
        for lib, label in _IDENTITY_LIBS.items():
            # Substring match — robust für requirements + package.json
            if lib.lower() in content:
                matches.add(label)
    return sorted(matches)


def _build_from_discovered(
    discovered: dict[str, dict | None],
    kind: str,  # "owasp" or "cra"
) -> list[CRARepoSuggestion]:
    """Build suggestions from discovered security files for a given kind (owasp/cra).

    For each discovered file, matches its name against _UNIVERSAL_NAME_PATTERNS
    and generates suggestions of the specified kind. Best score per field_id wins.
    """
    import fnmatch

    best: dict[str, CRARepoSuggestion] = {}
    pattern_keys = list(_UNIVERSAL_NAME_PATTERNS.keys())

    for path, evidence in discovered.items():
        if not evidence:
            continue
        fname = path.split("/")[-1]
        # Find matching pattern
        for pattern in pattern_keys:
            if fnmatch.fnmatch(fname, pattern) or fnmatch.fnmatch(path, pattern):
                mappings = _UNIVERSAL_NAME_PATTERNS[pattern].get(kind, [])
                for field_id, score, kommentar, confidence, rationale in mappings:
                    curr = best.get(field_id)
                    if curr is None or score > curr.score:
                        best[field_id] = _suggest(field_id, score, kommentar, confidence, rationale, [evidence])
                break  # first matching pattern only (avoid double-matching)

    return list(best.values())


# ── Public API ────────────────────────────────────────────────────────────────

def suggest_from_repo_evidence(
    *, provider: str, repo: str, branch: str = "", base_url: str = "", token_env: str = ""
) -> list[CRARepoSuggestion]:
    """Focused subset of signals (legacy/quick). GitHub only."""
    provider = (provider or "").strip() or "github"
    if provider != "github":
        return []

    from cra.repo_alignment import _parse_github_repo, _github_path_exists

    parsed = _parse_github_repo(repo)
    if not parsed:
        raise ValueError("Repo-URL ungültig. Erwartet org/repo oder https://github.com/org/repo")
    owner, name = parsed

    def chk(path: str) -> tuple[bool, dict | None]:
        return _github_path_exists(owner, name, path, branch)

    results: list[CRARepoSuggestion] = []

    has_sbom_wf, ev_sbom_wf = chk(".github/workflows/cra-sbom.yml")
    if has_sbom_wf and ev_sbom_wf:
        results.append(CRARepoSuggestion(
            field_id="AI2-02", score=3,
            kommentar="SBOM-Erzeugung ist im Repo als GitHub Actions Workflow konfiguriert.",
            confidence=0.9, rationale="Workflow-Datei für SBOM-Generierung gefunden.",
            citations=[{"doc_id": "", "chunk_idx": 0, "url": ev_sbom_wf.get("url"),
                        "path": ev_sbom_wf.get("path")}],
        ))

    has_security_md, ev_security_md = chk("SECURITY.md")
    has_security_txt, ev_security_txt = chk(".well-known/security.txt")
    if (has_security_md and ev_security_md) or (has_security_txt and ev_security_txt):
        evs = [e for e in [ev_security_md, ev_security_txt] if e]
        results.append(CRARepoSuggestion(
            field_id="AI2-05", score=4,
            kommentar="CVD-Policy/Disclosure Kontakt ist dokumentiert (SECURITY.md/security.txt).",
            confidence=0.9, rationale="Policy-Datei(en) im Repo gefunden.",
            citations=[{"doc_id": "", "chunk_idx": 0, "url": e.get("url"), "path": e.get("path")}
                       for e in evs],
        ))

    has_codeowners, ev_codeowners = chk(".github/CODEOWNERS")
    if has_codeowners and ev_codeowners:
        results.append(CRARepoSuggestion(
            field_id="AI2-01", score=2,
            kommentar="CODEOWNERS ist vorhanden (Ownership/Review-Struktur).",
            confidence=0.7, rationale="Repo-Signal; Schwachstellenprozess muss separat nachgewiesen werden.",
            citations=[{"doc_id": "", "chunk_idx": 0, "url": ev_codeowners.get("url"),
                        "path": ev_codeowners.get("path")}],
        ))

    has_docs, ev_docs = chk("docs")
    if has_docs and ev_docs:
        results.append(CRARepoSuggestion(
            field_id="ART13-03", score=2,
            kommentar="Technische Dokumentation ist im Repo abgelegt (docs/).",
            confidence=0.6, rationale="Repo-Signal: docs/ Ordner vorhanden.",
            citations=[{"doc_id": "", "chunk_idx": 0, "url": ev_docs.get("url"),
                        "path": ev_docs.get("path")}],
        ))

    return results


def full_repo_scan(
    *, provider: str, repo: str, branch: str = "", base_url: str = "", token_env: str = ""
) -> list[CRARepoSuggestion]:
    """Full-Repo-Scan: discovers OWASP + CRA evidence in ANY GitHub repo.

    Uses UNIVERSAL file name pattern matching (not hardcoded paths):
      1. Exact path checks for universal CI/policy files (SECURITY.md,
         dependabot, CODEOWNERS, workflows, etc.)
      2. Directory listing + fnmatch pattern matching for security modules
         (*config*, *audit*, *crypto*, *valid*, *error*, *secret*, etc.)
      3. Source directory scanning (src/, app/, lib/, shared/, utils/)

    branch: specific git ref to scan (e.g. 'cra/ai-main'). Empty = repo default branch.
    Returns one suggestion per field_id — duplicates merged by highest score.
    """
    provider = (provider or "").strip() or "github"
    if provider != "github":
        raise NotImplementedError("Full-Repo-Scan ist aktuell nur für GitHub implementiert.")

    from cra.repo_alignment import _parse_github_repo

    parsed = _parse_github_repo(repo)
    if not parsed:
        raise ValueError("Repo-URL ungültig. Erwartet org/repo oder https://github.com/org/repo")
    owner, name = parsed

    # Source 1: CI/policy signals via exact path checks (universal)
    signals = _collect_signals(owner, name, branch)
    ci_cra = _build_suggestions(owner, name, signals)

    # Source 2: Universal security file discovery via name patterns
    discovered = _discover_security_files(owner, name, branch)
    sec_owasp = _build_from_discovered(discovered, "owasp")
    sec_cra = _build_from_discovered(discovered, "cra")

    # Source 3 (#576): Identity-Lib-Detection in Dependency-Manifesten → PC-C6
    identity_libs = _detect_identity_libs(owner, name, branch)
    identity_suggestions: list[CRARepoSuggestion] = []
    if identity_libs:
        rationale = (
            f"Identity-Libraries in Dependencies erkannt: {', '.join(identity_libs[:6])}"
            + (f" (+{len(identity_libs)-6} weitere)" if len(identity_libs) > 6 else "")
        )
        identity_suggestions.append(_suggest(
            "OWASP-PC-C6", 5,
            "Digital-Identity-Bibliotheken im Einsatz (Password-Hashing, JWT, OAuth, MFA, SAML).",
            0.9, rationale, [{"provider": "github", "owner": owner, "repo": name,
                              "path": "requirements.txt|package.json", "url": f"https://github.com/{owner}/{name}"}],
        ))
        identity_suggestions.append(_suggest(
            "AI2-04", 4,
            "Authentifizierungs-/Identity-Stack via etablierte Libraries (Defense-in-Depth).",
            0.85, rationale, [],
        ))

    # Merge all by field_id: keep highest score, on tie keep first
    best: dict[str, CRARepoSuggestion] = {}
    for s in ci_cra + sec_owasp + sec_cra + identity_suggestions:
        curr = best.get(s.field_id)
        if curr is None or s.score > curr.score:
            best[s.field_id] = s

    return list(best.values())
