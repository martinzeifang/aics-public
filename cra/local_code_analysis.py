"""Local code analysis for CRA/OWASP requirement fulfillment detection.

Scans the local project directory for security-relevant files and patterns,
then maps findings to OWASP Proactive Controls and CRA requirements.
Works fully offline (no GitHub API needed).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CodeFinding:
    """A single finding from local code analysis."""

    field_id: str               # OWASP-PC-C1 or AI1-01 etc.
    object_kind: str            # 'owasp' | 'cra'
    score: int                  # 0-5 (BEWERTUNG_SKALA)
    kommentar: str
    confidence: float           # 0.0 - 1.0
    rationale: str
    citations: list[dict[str, str]] = field(default_factory=list)


# Security-relevant files to check (relative to project root)
_SECURITY_CHECKS: dict[str, dict[str, Any]] = {
    # ── Config I/O ──────────────────────────────────────────────────────────
    "shared/config_io.py": {
        "owasp": {
            "C2": {
                "score": 4,
                "kommentar": "Sichere Config-I/O mit atomischem Schreiben, SHA-256-Sidecar und Audit-Events (shared/config_io.py).",
                "confidence": 0.9,
                "rationale": "Nutzt etablierte Sicherheitsbibliothek (atomisches Schreiben, umask, SHA-256) für Konfigurationsdateien.",
            },
            "C8": {
                "score": 3,
                "kommentar": "Config-Dateien werden mit restriktiven Berechtigungen (0600) und umask(077) geschützt.",
                "confidence": 0.85,
                "rationale": "Verhindert unbefugten Lesezugriff auf Konfigurationsdateien durch restriktive Dateirechte.",
            },
        },
        "cra": {
            "AI2-04": {
                "score": 4,
                "kommentar": "Sichere Konfigurationsverwaltung mit Integritätsschutz (SHA-256-Sidecar) und Audit-Logging implementiert.",
                "confidence": 0.85,
                "rationale": "CRA AI2-04 fordert Integrität und Vertraulichkeit von Konfigurationen; SHA-256 + restriktive Permissions adressieren dies.",
            },
        },
    },
    # ── DB Security ─────────────────────────────────────────────────────────
    "shared/db_security.py": {
        "owasp": {
            "PC-C3": {
                "score": 4,
                "kommentar": "Sicherer DB-Zugriff mit Path-Containment, POSIX-Permissions (0700/0600) und Audit (shared/db_security.py).",
                "confidence": 0.9,
                "rationale": "SQLite-Datenbanken werden mit restriktiven Rechten geöffnet; Path-Traversal wird verhindert.",
            },
            "PC-C8": {
                "score": 3,
                "kommentar": "DB-Dateien werden mit Owner-only-Berechtigungen (0600) und umask(077) geschützt.",
                "confidence": 0.85,
                "rationale": "Schützt Datenbankdateien vor unbefugtem Lesezugriff.",
            },
        },
        "cra": {
            "AI2-04": {
                "score": 4,
                "kommentar": "Datenbankzugriff mit Path-Containment, restriktiven Dateirechten und Audit-Logging geschützt.",
                "confidence": 0.85,
                "rationale": "CRA AI2-04 (Cybersecurity): DB-Sicherheit durch Zugriffskontrollen auf Dateisystemebene.",
            },
        },
    },
    # ── Filesystem Permissions ──────────────────────────────────────────────
    "shared/fs_perms.py": {
        "owasp": {
            "PC-C7": {
                "score": 3,
                "kommentar": "Restriktive Dateisystem-Permissions mit ensure_private_dir/file (0700/0600) implementiert (shared/fs_perms.py).",
                "confidence": 0.85,
                "rationale": "Durchgesetzte Owner-only-Berechtigungen für data/, db/, evidence/, out/, logs/.",
            },
            "PC-C8": {
                "score": 4,
                "kommentar": "Zentrale Dateisystem-Permission-Verwaltung: alle data-Verzeichnisse auf 0700, Dateien auf 0600.",
                "confidence": 0.9,
                "rationale": "Schützt Daten im Ruhezustand durch restriktive POSIX-Permissions beim Suite-Start.",
            },
        },
        "cra": {
            "AI2-04": {
                "score": 3,
                "kommentar": "Dateisystemberechtigungen werden zentral verwaltet und beim Suite-Start erzwungen.",
                "confidence": 0.8,
                "rationale": "CRA AI2-04: Zugriffskontrolle auf Dateisystemebene für alle relevanten Verzeichnisse.",
            },
        },
    },
    # ── Integrity Check ─────────────────────────────────────────────────────
    "shared/integrity.py": {
        "owasp": {
            "PC-C2": {
                "score": 3,
                "kommentar": "Runtime-Integritätsprüfung mit SHA-256-Manifest beim Suite-Start (shared/integrity.py).",
                "confidence": 0.85,
                "rationale": "Erkennt Manipulation von Modul-Dateien durch Hash-Vergleich gegen ein Manifest.",
            },
        },
        "cra": {
            "AI2-04": {
                "score": 4,
                "kommentar": "Runtime-Integritätsprüfung der Software-Module mittels SHA-256-Manifest; optional fail-closed.",
                "confidence": 0.85,
                "rationale": "CRA AI2-04 (Integrität): stellt sicher, dass nur unveränderte Module ausgeführt werden.",
            },
        },
    },
    # ── JSON I/O ────────────────────────────────────────────────────────────
    "shared/json_io.py": {
        "owasp": {
            "PC-C5": {
                "score": 4,
                "kommentar": "Sichere JSON-Importe mit Größenbegrenzung (10 MB), Fence-Stripping und Audit (shared/json_io.py).",
                "confidence": 0.9,
                "rationale": "Verhindert Overload-Angriffe durch große JSON-Payloads; entfernt Markdown-Fence-Artifakte.",
            },
        },
        "cra": {
            "AI1-02": {
                "score": 3,
                "kommentar": "Importierte Daten (JSON aus ChatGPT) werden auf Größe und Struktur validiert.",
                "confidence": 0.8,
                "rationale": "CRA AI1-02 (Data Governance): validierte Dateneingänge reduzieren Risiken durch fehlerhafte/missbräuchliche JSON-Importe.",
            },
        },
    },
    # ── Network Validation ──────────────────────────────────────────────────
    "shared/net_validation.py": {
        "owasp": {
            "PC-C5": {
                "score": 3,
                "kommentar": "Netzwerkzugriff wird validiert: Loopback-Guard für lokale LLM, Cloud-Egress-Gate (shared/net_validation.py).",
                "confidence": 0.85,
                "rationale": "Verhindert unautorisierte Netzwerkverbindungen durch Host-Validierung und expliziten Consent.",
            },
            "PC-C8": {
                "score": 3,
                "kommentar": "Datenübertragung an externe Dienste nur mit explizitem Consent und HTTPS-only.",
                "confidence": 0.85,
                "rationale": "Schützt Daten vor unbeabsichtigtem Abfluss an externe KI-Dienste.",
            },
        },
        "cra": {
            "AI2-04": {
                "score": 4,
                "kommentar": "Netzwerkzugriff gehärtet: Loopback-Guard, Cloud-Egress-Gate mit Consent, HTTPS-only, Audit.",
                "confidence": 0.85,
                "rationale": "CRA AI2-04 (Cybersecurity): mehrstufige Netzwerkkontrolle für KI-Kommunikation.",
            },
        },
    },
    # ── Redaction ───────────────────────────────────────────────────────────
    "shared/redaction.py": {
        "owasp": {
            "PC-C8": {
                "score": 4,
                "kommentar": "Secret-Redaktion für API-Keys, Tokens und sensible Muster (shared/redaction.py).",
                "confidence": 0.9,
                "rationale": "Verhindert versehentliches Leaken von Secrets in Logs, Issues und KI-Anfragen.",
            },
        },
        "cra": {
            "AI1-02": {
                "score": 4,
                "kommentar": "Sensitive Daten (API-Keys, Tokens) werden vor Persistierung/Versand automatisch redigiert.",
                "confidence": 0.9,
                "rationale": "CRA AI1-02 (Data Governance): Reduktion personenbezogener/sensibler Daten durch automatische Redaktion.",
            },
        },
    },
    # ── Crypto At-Rest ─────────────────────────────────────────────────────
    "shared/crypto_at_rest.py": {
        "owasp": {
            "PC-C8": {
                "score": 4,
                "kommentar": "Optionale AES-128-Verschlüsselung für Backups und Evidence-Dateien (Fernet, shared/crypto_at_rest.py).",
                "confidence": 0.9,
                "rationale": "Schützt Daten im Ruhezustand durch Dateiverschlüsselung mit Salt pro Datei; Schlüssel extern via Env-Var.",
            },
        },
        "cra": {
            "AI2-04": {
                "score": 4,
                "kommentar": "Optionale At-Rest-Verschlüsselung für Backups und Evidence-Dateien implementiert.",
                "confidence": 0.85,
                "rationale": "CRA AI2-04 (Cybersecurity): Verschlüsselung sensibler Daten im Ruhezustand.",
            },
        },
    },
    # ── Audit Logging ───────────────────────────────────────────────────────
    "shared/audit.py": {
        "owasp": {
            "PC-C9": {
                "score": 4,
                "kommentar": "Strukturiertes Audit-Logging für sicherheitsrelevante Aktionen (shared/audit.py).",
                "confidence": 0.9,
                "rationale": "Erfasst Config-Änderungen, DB-Zugriffe, Exporte, KI-Anfragen und Integritätsprüfungen als Audit-Events.",
            },
        },
        "cra": {
            "AI2-04": {
                "score": 4,
                "kommentar": "Umfassendes Audit-Logging mit 9 Event-Kategorien; Audit-Log-Viewer in der Suite-GUI.",
                "confidence": 0.9,
                "rationale": "CRA AI2-04 (Cybersecurity): Nachvollziehbare Protokollierung aller sicherheitsrelevanten Aktionen.",
            },
        },
    },
    # ── Logging Setup ───────────────────────────────────────────────────────
    "shared/logging_setup.py": {
        "owasp": {
            "PC-C9": {
                "score": 3,
                "kommentar": "Zentrales Infra-Logging mit Logger-Konfiguration (shared/logging_setup.py).",
                "confidence": 0.8,
                "rationale": "Ergänzt Audit-Logging durch technische Laufzeit-Logs für Fehlerdiagnose.",
            },
        },
    },
    # ── Security Utils (Office) ─────────────────────────────────────────────
    "security_utils.py": {
        "owasp": {
            "PC-C5": {
                "score": 4,
                "kommentar": "Office-Dokumenten-Validierung: Zip-Bomb-Schutz, Magic-Bytes, Path-Containment (security_utils.py).",
                "confidence": 0.9,
                "rationale": "Validiert XLSX/DOCX vor dem Einlesen auf schadhafte Inhalte (Zip-Bomben, fehlende Content-Types).",
            },
            "PC-C4": {
                "score": 3,
                "kommentar": "Output-Encoding für CSV (Formula-Injection-Schutz) und Markdown (Fence-Escaping) in security_utils / shared/encoding.",
                "confidence": 0.85,
                "rationale": "schützt vor Injection-Angriffen über generierte Dateien durch kontextabhängiges Escaping.",
            },
        },
        "cra": {
            "AI1-02": {
                "score": 3,
                "kommentar": "Eingabedaten aus Office-Dokumenten werden auf schadhafte Inhalte validiert und bereinigt.",
                "confidence": 0.85,
                "rationale": "CRA AI1-02 (Data Governance): Validierung und Sanitisierung von Eingabedaten aus externen Quellen.",
            },
            "AI2-04": {
                "score": 3,
                "kommentar": "Office-Dateien werden vor dem Einlesen auf Integrität und Sicherheit geprüft.",
                "confidence": 0.8,
                "rationale": "CRA AI2-04: Schutz vor schadhaften Anhängen/Import-Dokumenten.",
            },
        },
    },
    # ── Error Handling ──────────────────────────────────────────────────────
    "shared/errors.py": {
        "owasp": {
            "PC-C10": {
                "score": 4,
                "kommentar": "Zentrales Exception-Handling für Tkinter-GUI (shared/errors.py).",
                "confidence": 0.9,
                "rationale": "Fängt unbehandelte Exceptions in der GUI und zeigt benutzerfreundliche Fehlermeldungen.",
            },
        },
        "cra": {
            "AI2-07": {
                "score": 3,
                "kommentar": "Globales Fehlerbehandlung für die GUI-Komponente implementiert.",
                "confidence": 0.8,
                "rationale": "CRA AI2-07 (Logging/Fehlerbehandlung): Strukturierte Fehlerbehandlung für Benutzeroberfläche.",
            },
        },
    },
    # ── Output Encoding ─────────────────────────────────────────────────────
    "shared/encoding.py": {
        "owasp": {
            "PC-C4": {
                "score": 4,
                "kommentar": "CSV Formula-Injection-Schutz und Markdown-Escaping (shared/encoding.py).",
                "confidence": 0.9,
                "rationale": "Verhindert CSV-Injection und Markdown-Struktur-Manipulation in generierten Export-Dateien.",
            },
        },
        "cra": {
            "AI2-06": {
                "score": 3,
                "kommentar": "Output-Encoding für CSV und Markdown-Exporte implementiert.",
                "confidence": 0.8,
                "rationale": "CRA AI2-06 (Output-Handling): Schutz vor Injection in generierten Export-Dokumenten.",
            },
        },
    },
    # ── Input Validation ────────────────────────────────────────────────────
    "shared/validation.py": {
        "owasp": {
            "PC-C5": {
                "score": 3,
                "kommentar": "Eingabevalidierung für Repo/Branch/URL/Env-Namen in GUI-Dialogen (shared/validation.py).",
                "confidence": 0.85,
                "rationale": "Stellt sicher, dass Benutzereingaben in Konfigurationsfeldern valide Formate haben.",
            },
        },
    },
    # ── CI/CD Workflows ─────────────────────────────────────────────────────
    ".github/workflows": {
        "owasp": {
            "PC-C9": {
                "score": 3,
                "kommentar": "CI/CD-Workflows für SBOM, OSV-Scan, Evidence Pack und Docs-Deployment vorhanden.",
                "confidence": 0.85,
                "rationale": "Automatisierte Sicherheitsprüfungen in der CI-Pipeline (Dependency-Scans, SBOM-Generierung).",
            },
        },
        "cra": {
            "IMPL-01": {
                "score": 4,
                "kommentar": "CI/CD-Pipeline mit automatisierten Sicherheits-Scans (OSV, Dependabot) und SBOM-Generierung.",
                "confidence": 0.9,
                "rationale": "CRA IMPL-01 (Prozesse): Entwicklungsprozess mit integrierten Sicherheitsprüfungen.",
            },
            "IMPL-02": {
                "score": 3,
                "kommentar": "CI-Artefakte (SBOM, Scan-Ergebnisse) werden als Evidence in der Nachweisbibliothek gespeichert.",
                "confidence": 0.8,
                "rationale": "CRA IMPL-02 (Dokumentation): Automatisch generierte Nachweise aus CI-Pipeline.",
            },
        },
    },
    # ── SECURITY.md ─────────────────────────────────────────────────────────
    "SECURITY.md": {
        "owasp": {
            "PC-C1": {
                "score": 4,
                "kommentar": "Sicherheitsrichtlinie (SECURITY.md) mit Koordinationsprozess für Schwachstellenmeldungen.",
                "confidence": 0.9,
                "rationale": "Definiert Security-Requirements und verantwortlichen Meldeweg für Sicherheitslücken.",
            },
        },
        "cra": {
            "AI1-01": {
                "score": 3,
                "kommentar": "Security-Richtlinie dokumentiert in SECURITY.md; definiert Prozess für Schwachstellenmanagement.",
                "confidence": 0.8,
                "rationale": "CRA AI1-01 (Risk Management): Dokumentierte Sicherheitsprozesse als Teil des Risikomanagements.",
            },
        },
    },
    # ── Dependabot ──────────────────────────────────────────────────────────
    ".github/dependabot.yml": {
        "owasp": {
            "PC-C2": {
                "score": 4,
                "kommentar": "Dependabot für automatische Dependency-Updates konfiguriert (.github/dependabot.yml).",
                "confidence": 0.9,
                "rationale": "Nutzung von GitHub Dependabot als Security-Framework für Abhängigkeitsmanagement.",
            },
        },
        "cra": {
            "AI2-01": {
                "score": 4,
                "kommentar": "Automatisiertes Dependency-Update-Management über Dependabot (wöchentlich).",
                "confidence": 0.9,
                "rationale": "CRA AI2-01 (Vulnerability Management): Regelmäßige Aktualisierung von Abhängigkeiten mit Sicherheits-Fixes.",
            },
            "AI2-02": {
                "score": 3,
                "kommentar": "Dependabot erzeugt SBOM-relevante Dependency-Updates; SBOM wird via CI (CycloneDX) erstellt.",
                "confidence": 0.8,
                "rationale": "CRA AI2-02 (SBOM): Nachvollziehbarkeit von Abhängigkeiten durch Dependency-Management.",
            },
        },
    },
    # ── Docs / Documentation ────────────────────────────────────────────────
    "docs/development/security-tooling.md": {
        "cra": {
            "AI1-03": {
                "score": 4,
                "kommentar": "Umfassende Sicherheitsdokumentation: Architektur, Module, Limits, Sicherheitslimits dokumentiert.",
                "confidence": 0.9,
                "rationale": "CRA AI1-03 (Technical Documentation): Sicherheitsarchitektur, Bedrohungsanalyse und Gegenmaßnahmen dokumentiert.",
            },
        },
    },
    # ── Risk Assessment ─────────────────────────────────────────────────────
    "risikobewertung": {
        "cra": {
            "AI1-01": {
                "score": 4,
                "kommentar": "Strukturiertes Risikobewertungs-Modul (FI, STRIDE, CVSS, OCTAVE) mit Change-Log und Issue-Sync.",
                "confidence": 0.9,
                "rationale": "CRA AI1-01 (Risk Management): Systematische Risikobewertung mit etablierten Methodiken, Audit-Trail und Issue-Integration.",
            },
        },
    },
    # ── VCS Issue Sync ──────────────────────────────────────────────────────
    "vcs/issue_sync.py": {
        "cra": {
            "AI1-05": {
                "score": 3,
                "kommentar": "Issue-Synchronisation ermöglicht menschliche Überprüfung und Nachverfolgung von Sicherheitslücken.",
                "confidence": 0.8,
                "rationale": "CRA AI1-05 (Human Oversight): Issues ermöglichen review-basierten Entscheidungsprozess für Sicherheitsmaßnahmen.",
            },
        },
    },
    # ── Evidence Library ────────────────────────────────────────────────────
    "evidence/db.py": {
        "cra": {
            "IMPL-02": {
                "score": 4,
                "kommentar": "Zentrale Nachweisbibliothek (Evidence Store) für Compliance-Dokumente mit Mandantentrennung.",
                "confidence": 0.9,
                "rationale": "CRA IMPL-02 (Dokumentation): Strukturierte Speicherung und Verwaltung von Compliance-Nachweisen.",
            },
        },
    },
    # ── Prefill Engine ──────────────────────────────────────────────────────
    "prefill/engine.py": {
        "cra": {
            "IMPL-03": {
                "score": 3,
                "kommentar": "KI-gestützte Vorschlags-Engine für automatische Bewertung von Nachweisen.",
                "confidence": 0.8,
                "rationale": "CRA IMPL-03 (Tools): Automatisierte Unterstützung bei der Compliance-Bewertung durch KI.",
            },
        },
    },
}


def _file_exists(rel_path: str, root: Path) -> bool:
    """Check if a file or directory exists relative to root."""
    full = root / rel_path
    return full.exists()


def _dir_has_py_files(rel_dir: str, root: Path) -> bool:
    """Check if a directory contains any .py files."""
    d = root / rel_dir
    if not d.is_dir():
        return False
    return any(d.glob("*.py"))


def analyze_local_codebase(project_root: str | Path) -> list[CodeFinding]:
    """Scan local project directory and return OWASP/CRA suggestions.

    Args:
        project_root: Path to the project root directory.

    Returns:
        List of CodeFinding with scores for OWASP and CRA requirements.
    """
    root = Path(project_root).resolve()
    findings: list[CodeFinding] = []
    seen_owasp: set[str] = set()
    seen_cra: set[str] = set()

    for rel_path, checks in _SECURITY_CHECKS.items():
        # Determine what to check: file or directory
        if rel_path.endswith("/"):
            exists = _dir_has_py_files(rel_path.rstrip("/"), root)
        else:
            exists = _file_exists(rel_path, root)

        if not exists:
            continue

        # Build citation
        citation: dict[str, str] = {
            "path": rel_path,
        }
        full_path = root / rel_path
        if full_path.is_file():
            try:
                citation["url"] = full_path.resolve().as_uri()
            except Exception:
                pass

        # OWASP mappings
        for oid, mapping in checks.get("owasp", {}).items():
            oid_clean = oid[3:] if oid.startswith("PC-") else oid
            key = f"OWASP-PC-{oid_clean}"
            if key in seen_owasp:
                continue
            seen_owasp.add(key)
            findings.append(CodeFinding(
                field_id=key,
                object_kind="owasp",
                score=mapping["score"],
                kommentar=mapping["kommentar"],
                confidence=mapping["confidence"],
                rationale=mapping["rationale"],
                citations=[citation],
            ))

        # CRA mappings
        for cra_id, mapping in checks.get("cra", {}).items():
            if cra_id in seen_cra:
                continue
            seen_cra.add(cra_id)
            findings.append(CodeFinding(
                field_id=cra_id,
                object_kind="cra",
                score=mapping["score"],
                kommentar=mapping["kommentar"],
                confidence=mapping["confidence"],
                rationale=mapping["rationale"],
                citations=[citation],
            ))

    return findings


# Default checks: used for controls without automatic detection
_DEFAULT_OWASP_NEEDS_REVIEW = [
    "OWASP-PC-C6",  # Digital Identity
]


def get_pending_controls(project_root: str | Path) -> list[str]:
    """Return OWASP control IDs that still need manual review."""
    root = Path(project_root).resolve()
    pending: list[str] = []
    for oid in _DEFAULT_OWASP_NEEDS_REVIEW:
        pending.append(oid)
    return pending
