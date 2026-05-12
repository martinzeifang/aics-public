"""Deterministic repo alignment for CRA OWASP checklist.

Scans GitHub repositories via `gh api` for security-relevant files and maps
findings to OWASP Proactive Controls (PC-C1 through PC-C10).
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.parse
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RepoEvidence:
    owasp_id: str
    status: int
    kommentar: str
    evidence: list[dict[str, Any]]


# ── File-to-control mapping ─────────────────────────────────────────────
# Each entry: (repo_path, target_control, score_if_found, description)
_FILE_CHECKS: list[tuple[str, str, int, str]] = [
    # PC-C1: Define Security Requirements
    ("SECURITY.md",                 "OWASP-PC-C1", 4, "Sicherheitsrichtlinie (SECURITY.md) mit Meldeweg für Schwachstellen."),
    (".well-known/security.txt",    "OWASP-PC-C1", 3, "Security Contact (security.txt) für verantwortliche Offenlegung."),
    ("docs/development/security-tooling.md", "OWASP-PC-C1", 3, "Sicherheitsarchitektur dokumentiert (Security-Tooling-Dokumentation)."),

    # PC-C2: Leverage Security Frameworks and Libraries
    (".github/dependabot.yml",      "OWASP-PC-C2", 4, "Dependabot für automatische Dependency-Updates (GitHub-native Sicherheitsintegration)."),
    ("renovate.json",               "OWASP-PC-C2", 3, "Renovate Bot für automatische Dependency-Updates."),
    ("shared/config_io.py",         "OWASP-PC-C2", 4, "Sichere Config-I/O (shared/config_io.py): atomisches Schreiben, SHA-256-Sidecar."),
    ("shared/crypto_at_rest.py",    "OWASP-PC-C2", 4, "At-Rest-Verschlüsselung (shared/crypto_at_rest.py): Fernet-basiert (AES-128)."),
    ("shared/audit.py",             "OWASP-PC-C2", 3, "Strukturiertes Audit-Logging (shared/audit.py)."),
    ("shared/integrity.py",         "OWASP-PC-C2", 3, "Runtime-Integritätsprüfung (shared/integrity.py): SHA-256-Manifest."),
    ("shared/fs_perms.py",          "OWASP-PC-C2", 3, "Zentrale Dateirechte-Verwaltung (shared/fs_perms.py)."),

    # PC-C3: Secure Database Access
    ("shared/db_security.py",       "OWASP-PC-C3", 4, "Sicherer DB-Zugriff (shared/db_security.py): Path-Containment, POSIX-Permissions, umask(077)."),

    # PC-C4: Encode and Escape Data
    ("shared/encoding.py",          "OWASP-PC-C4", 4, "Output-Encoding (shared/encoding.py): CSV-Formula-Injection-Schutz, Markdown-Escaping."),
    ("security_utils.py",           "OWASP-PC-C4", 3, "add_untrusted_block() mit Markdown-Codefence-Escaping in Prompts."),

    # PC-C5: Validate All Inputs
    ("shared/json_io.py",           "OWASP-PC-C5", 4, "Sichere JSON-Importe (shared/json_io.py): 10 MB Größenlimit, Fence-Stripping, Audit."),
    ("shared/validation.py",        "OWASP-PC-C5", 3, "Eingabevalidierung (shared/validation.py): Repo/Branch/URL/Env-Prüfung."),
    ("shared/net_validation.py",    "OWASP-PC-C5", 3, "Netzwerkvalidierung (shared/net_validation.py): Loopback-Guard, Cloud-Egress-Gate."),
    ("security_utils.py",           "OWASP-PC-C5", 4, "Office-Dokumenten-Validierung (security_utils.py): Zip-Bomb-Schutz, Magic-Bytes, Path-Containment."),

    # PC-C6: Digital Identity – schwer automatisiert prüfbar, kein Mapping

    # PC-C7: Enforce Access Controls
    (".github/CODEOWNERS",          "OWASP-PC-C7", 3, "CODEOWNERS für Ownership/Review-Struktur."),
    ("shared/fs_perms.py",          "OWASP-PC-C7", 4, "Restriktive Dateisystem-Permissions (shared/fs_perms.py): 0700/0600, ensure_private_dir/file."),
    ("shared/db_security.py",       "OWASP-PC-C7", 3, "DB-Zugriffskontrolle (shared/db_security.py): Path-Containment."),

    # PC-C8: Protect Data Everywhere
    ("shared/fs_perms.py",          "OWASP-PC-C8", 4, "Dateisystem-Permissions (shared/fs_perms.py): data/db/evidence/out/logs auf 0700/0600."),
    ("shared/crypto_at_rest.py",    "OWASP-PC-C8", 4, "At-Rest-Verschlüsselung (shared/crypto_at_rest.py): AES-128-CBC + HMAC für Backups/Evidence."),
    ("shared/redaction.py",         "OWASP-PC-C8", 4, "Secret-Redaktion (shared/redaction.py): API-Keys, Tokens, Bearer-Header."),
    ("shared/db_security.py",       "OWASP-PC-C8", 3, "DB-Dateien mit 0600-Berechtigungen (shared/db_security.py)."),
    ("shared/config_io.py",         "OWASP-PC-C8", 3, "Config-Dateien mit 0600 und umask(077) (shared/config_io.py)."),
    ("shared/net_validation.py",    "OWASP-PC-C8", 3, "Cloud-Egress-Gate (shared/net_validation.py): Datenabfluss nur mit explizitem Consent."),

    # PC-C9: Implement Security Logging and Monitoring
    ("shared/audit.py",             "OWASP-PC-C9", 4, "Audit-Logging (shared/audit.py): 9 Event-Kategorien, persistierte Events, GUI-Viewer."),
    ("shared/logging_setup.py",     "OWASP-PC-C9", 3, "Infra-Logging (shared/logging_setup.py): Technische Laufzeit-Logs."),
    (".github/workflows",           "OWASP-PC-C9", 3, "CI/CD-Workflows (SBOM, OSV-Scan, Evidence Pack, Docs-Deployment)."),

    # PC-C10: Handle All Errors and Exceptions
    ("shared/errors.py",            "OWASP-PC-C10", 4, "Globales Exception-Handling (shared/errors.py): Tkinter-Fehlerbehandlung."),
]


def _parse_github_repo(repo_url: str) -> tuple[str, str] | None:
    s = (repo_url or "").strip()
    if not s:
        return None

    # Accept https://github.com/owner/repo(.git) or owner/repo
    m = re.match(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", s, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)

    m = re.match(r"^([^/]+)/([^/]+)$", s)
    if m:
        return m.group(1), m.group(2)

    return None


def _gh_api_json(path: str) -> Any:
    """GitHub-API-Aufruf. Bevorzugt REST mit Token (Docker-tauglich),
    Fallback auf `gh` CLI für lokale Dev-Umgebungen ohne Token (Issue #391).
    """
    import shutil
    from shared.github_config import get_github_token, github_headers

    if get_github_token():
        import requests

        url = f"https://api.github.com/{path.lstrip('/')}"
        r = requests.get(url, headers=github_headers(), timeout=30)
        if r.status_code == 404:
            raise RuntimeError("404 Not Found")
        if r.status_code >= 300:
            raise RuntimeError(f"GitHub API {r.status_code}: {r.text[:200]}")
        return r.json()

    if shutil.which("gh"):
        p = subprocess.run(
            ["gh", "api", path],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if p.returncode != 0:
            raise RuntimeError((p.stderr or p.stdout or "gh api failed").strip())
        return json.loads(p.stdout)

    raise RuntimeError(
        "Kein GitHub-Backend verfügbar: weder GH_TOKEN/GITHUB_TOKEN gesetzt "
        "noch `gh` CLI installiert. Für Repo-Scan ist GH_TOKEN als ENV "
        "im Container erforderlich."
    )


def _github_path_exists(
    owner: str, repo: str, path: str, branch: str = ""
) -> tuple[bool, dict[str, Any] | None]:
    """Check whether a path exists in a GitHub repo.

    branch is URL-encoded automatically so names like 'cra/ai-main' work correctly.
    When branch is empty, the repo's default branch is used.
    """
    api = f"repos/{owner}/{repo}/contents/{path.lstrip('/')}"
    if branch:
        api += f"?ref={urllib.parse.quote(branch, safe='')}"
    try:
        data = _gh_api_json(api)
    except Exception:
        return False, None

    ref_slug = urllib.parse.quote(branch, safe="") if branch else "HEAD"

    if isinstance(data, dict) and data.get("type") in ("file", "dir"):
        url = data.get("html_url") or (
            f"https://github.com/{owner}/{repo}/blob/{ref_slug}/{path.lstrip('/')}"
        )
        return True, {"provider": "github", "owner": owner, "repo": repo,
                      "path": path, "url": url}
    if isinstance(data, list):
        return True, {
            "provider": "github", "owner": owner, "repo": repo, "path": path,
            "url": f"https://github.com/{owner}/{repo}/tree/{ref_slug}/{path.lstrip('/')}",
        }
    return False, None


def align_owasp_proactive_controls(repo_url: str, branch: str = "") -> list[RepoEvidence]:
    """Return deterministic alignment results for OWASP Proactive Controls.

    Scans the GitHub repository for security-relevant files and maps findings
    to OWASP Proactive Controls (PC-C1 through PC-C10). Multiple files can
    contribute to the same control; the highest score is used.

    Args:
        repo_url: GitHub repo URL or 'owner/repo' string.
        branch: Git branch/ref to check (e.g. 'cra/ai-main'). Empty = default branch.

    Returns:
        List of RepoEvidence, one per OWASP control with aggregated evidence.

    Raises:
        ValueError: If repo_url cannot be parsed or gh CLI fails.
    """
    parsed = _parse_github_repo(repo_url)
    if not parsed:
        raise ValueError(
            "Repo-URL ungültig. Erwartet z.B. https://github.com/org/repo oder org/repo"
        )
    owner, repo_short = parsed

    def chk(path: str) -> tuple[bool, dict | None]:
        return _github_path_exists(owner, repo_short, path, branch)

    # ── Run all checks ──────────────────────────────────────────────────
    # Collect evidence per OWASP control ID
    control_evidence: dict[str, list[dict[str, Any]]] = {}
    control_scores: dict[str, list[int]] = {}
    control_comments: dict[str, list[str]] = {}

    for file_path, ctrl_id, score, desc in _FILE_CHECKS:
        found, ev = chk(file_path)

        if ctrl_id not in control_evidence:
            control_evidence[ctrl_id] = []
            control_scores[ctrl_id] = []
            control_comments[ctrl_id] = []

        if found:
            control_evidence[ctrl_id].append(ev or {"path": file_path, "url": ""})
            control_scores[ctrl_id].append(score)
            control_comments[ctrl_id].append(desc)

    # ── Build results ───────────────────────────────────────────────────
    ALL_CONTROLS = [
        "OWASP-PC-C1", "OWASP-PC-C2", "OWASP-PC-C3", "OWASP-PC-C4",
        "OWASP-PC-C5", "OWASP-PC-C6", "OWASP-PC-C7", "OWASP-PC-C8",
        "OWASP-PC-C9", "OWASP-PC-C10",
    ]

    CONTROL_LABELS: dict[str, str] = {
        "OWASP-PC-C1":  "Define Security Requirements",
        "OWASP-PC-C2":  "Leverage Security Frameworks and Libraries",
        "OWASP-PC-C3":  "Secure Database Access",
        "OWASP-PC-C4":  "Encode and Escape Data",
        "OWASP-PC-C5":  "Validate All Inputs",
        "OWASP-PC-C6":  "Digital Identity",
        "OWASP-PC-C7":  "Enforce Access Controls",
        "OWASP-PC-C8":  "Protect Data Everywhere",
        "OWASP-PC-C9":  "Implement Security Logging and Monitoring",
        "OWASP-PC-C10": "Handle All Errors and Exceptions",
    }

    results: list[RepoEvidence] = []

    for ctrl_id in ALL_CONTROLS:
        ev_list = control_evidence.get(ctrl_id, [])
        scores = control_scores.get(ctrl_id, [])

        if not ev_list:
            # No evidence found – check if it's PC-C6 (always manual)
            if ctrl_id == "OWASP-PC-C6":
                results.append(RepoEvidence(
                    owasp_id=ctrl_id,
                    status=0,
                    kommentar=(
                        "Nicht deterministisch aus Repo-Dateien ableitbar "
                        "(manuelle Bewertung erforderlich)."
                    ),
                    evidence=[],
                ))
            else:
                results.append(RepoEvidence(
                    owasp_id=ctrl_id,
                    status=0,
                    kommentar=f"Kein Repo-Nachweis für {ctrl_id} gefunden.",
                    evidence=[],
                ))
            continue

        # Use the highest score found
        max_score = max(scores)
        # Combine comments into a single string
        combined_comment = "; ".join(control_comments.get(ctrl_id, []))
        kommentar = (
            f"{len(ev_list)} Nachweis(e) gefunden: {combined_comment}"
        )

        results.append(RepoEvidence(
            owasp_id=ctrl_id,
            status=max_score,
            kommentar=kommentar,
            evidence=ev_list,
        ))

    return results
