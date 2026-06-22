"""Prefill-Service: Gemeinsame Repo-Scan-Helfer und KI-Provider-Auswahl.

Generic Repo-File-Existence-Checks die alle Module nutzen können:
- CRA mappt SECURITY.md → AI1-01
- NIS2 mappt .github/workflows/security.yml → NIS-IM-01

Pro Modul wird ein modulspezifisches FILE_TO_REQ-Mapping definiert.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# ============================================================
# Datenmodell
# ============================================================

@dataclass
class RepoSignal:
    """Eine Datei/Pattern + Bewertung als Repo-Signal."""
    pattern: str  # z.B. 'SECURITY.md' oder '.github/workflows/*'
    description: str
    score_if_present: int = 4  # 0-5
    confidence: float = 0.85
    citations: list[str] = field(default_factory=list)


@dataclass
class PrefillSuggestion:
    """Vorgeschlagene Bewertung für eine Anforderung."""
    field_id: str
    score: int
    kommentar: str
    confidence: float
    rationale: str
    citations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================
# Generische Repo-Scan-Funktionen
# ============================================================

def parse_github_repo(repo_url: str) -> tuple[str, str] | None:
    """'https://github.com/owner/repo' oder 'owner/repo' → (owner, repo)."""
    if not repo_url:
        return None
    m = re.match(r'(?:https?://github\.com/)?([^/]+)/([^/]+?)(?:\.git)?/?$', repo_url.strip())
    if not m:
        return None
    return m.group(1), m.group(2)


def gh_path_exists(repo_url: str, path: str, branch: str = '') -> bool:
    """Prüft ob ein Pfad in einem GitHub-Repo existiert (via gh CLI oder API)."""
    parsed = parse_github_repo(repo_url)
    if not parsed:
        return False
    owner, repo = parsed

    branch_part = f'?ref={branch}' if branch else ''
    api_path = f'/repos/{owner}/{repo}/contents/{path}{branch_part}'

    try:
        import subprocess
        result = subprocess.run(
            ['gh', 'api', api_path],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def scan_files(repo_url: str, signals: list[RepoSignal], branch: str = '') -> list[dict[str, Any]]:
    """Prüft Datei-Existenz für eine Liste von Signalen.

    Returns: Liste der gefundenen Signale mit Score + Citation-URL.
    """
    parsed = parse_github_repo(repo_url)
    if not parsed:
        return []
    owner, repo = parsed
    base = f'https://github.com/{owner}/{repo}'

    found = []
    for sig in signals:
        if gh_path_exists(repo_url, sig.pattern, branch=branch):
            citation = f"{base}/blob/{branch or 'main'}/{sig.pattern}"
            found.append({
                'pattern': sig.pattern,
                'description': sig.description,
                'score': sig.score_if_present,
                'confidence': sig.confidence,
                'citations': [citation],
            })
    return found


# ============================================================
# Standard-Signale (modul-übergreifend nützlich)
# ============================================================

COMMON_SECURITY_SIGNALS: list[RepoSignal] = [
    RepoSignal('SECURITY.md', 'Vulnerability-Disclosure-Policy', score_if_present=4),
    RepoSignal('CODE_OF_CONDUCT.md', 'Code of Conduct', score_if_present=3),
    RepoSignal('CONTRIBUTING.md', 'Contribution Guidelines', score_if_present=3),
    RepoSignal('LICENSE', 'License', score_if_present=4),
    RepoSignal('README.md', 'README mit Projekt-Beschreibung', score_if_present=3),
    RepoSignal('.github/CODEOWNERS', 'Code-Ownership-Definition', score_if_present=4),
    RepoSignal('.github/dependabot.yml', 'Automatisches Dependency-Management', score_if_present=4),
    RepoSignal('.github/workflows', 'CI/CD-Workflows', score_if_present=4),
    RepoSignal('docs/', 'Dokumentations-Verzeichnis', score_if_present=3),
    RepoSignal('tests/', 'Test-Suite', score_if_present=4),
    RepoSignal('Dockerfile', 'Containerization', score_if_present=3),
    RepoSignal('docker-compose.yml', 'Container-Orchestrierung', score_if_present=3),
    RepoSignal('THREAT_MODEL.md', 'Threat-Modeling-Dokument', score_if_present=5),
    RepoSignal('sbom.json', 'Software Bill of Materials', score_if_present=5),
    RepoSignal('sbom.spdx.json', 'SPDX SBOM', score_if_present=5),
    RepoSignal('cyclonedx.json', 'CycloneDX SBOM', score_if_present=5),
]


# ============================================================
# KI-Provider-Auswahl (Wrapper für Settings)
# ============================================================

def get_ai_provider_config() -> dict[str, Any]:
    """Liest die KI-Provider-Konfiguration aus den globalen Settings.

    Returns: dict mit provider, base_url, model, timeout_s, allow_data_egress
    """
    try:
        from ai_compliance_suite.config import load_config
        cfg = load_config()
        ai = cfg.get('ai', {})
        provider = ai.get('provider', 'on_prem')
        if provider == 'on_prem':
            on_prem = ai.get('on_prem', {})
            return {
                'provider': 'on_prem',
                'base_url': on_prem.get('base_url', 'http://127.0.0.1:11434'),
                'model': on_prem.get('model', ''),
                'timeout_s': int(on_prem.get('timeout_s', 60)),
                'allow_data_egress': True,  # lokal
            }
        elif provider == 'cloud':
            cloud = ai.get('cloud', {})
            return {
                'provider': 'cloud',
                'base_url': cloud.get('base_url', 'https://api.openai.com/v1'),
                'model': cloud.get('model', ''),
                'timeout_s': int(cloud.get('timeout_s', 60)),
                'allow_data_egress': bool(cloud.get('allow_data_egress', False)),
                'api_key_env': cloud.get('api_key_env', ''),
                'api_key': cloud.get('api_key', ''),  # direkter Key (Vorrang vor Env-Var)
            }
    except Exception:
        pass

    return {
        'provider': 'on_prem',
        'base_url': 'http://127.0.0.1:11434',
        'model': '',
        'timeout_s': 60,
        'allow_data_egress': True,
    }


def is_ai_available() -> tuple[bool, str]:
    """Prüft ob KI-Bewertung verfügbar ist.

    Returns: (available, reason_if_not)
    """
    cfg = get_ai_provider_config()
    if cfg['provider'] == 'on_prem':
        if not cfg.get('model'):
            return False, 'Kein on-prem-Model konfiguriert. Bitte Einstellungen prüfen.'
        return True, ''
    elif cfg['provider'] == 'cloud':
        if not cfg.get('allow_data_egress'):
            return False, 'Cloud-Provider benötigt allow_data_egress=true in den Einstellungen.'
        # Direkter Key (in den Einstellungen hinterlegt) hat Vorrang vor der Env-Variable.
        direct_key = str(cfg.get('api_key', '') or '').strip()
        if not direct_key:
            api_key_env = str(cfg.get('api_key_env', '') or '').strip()
            import re as _re
            if api_key_env and _re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', api_key_env):
                # Gültiger Variablen-NAME → muss gesetzt sein.
                if not os.environ.get(api_key_env):
                    return False, (f'API-Key Umgebungsvariable „{api_key_env}" ist nicht gesetzt.')
            elif not api_key_env:
                return False, ('Kein Cloud-API-Key hinterlegt — bitte in den Einstellungen '
                               'einen API-Key eintragen.')
            # api_key_env ist kein gültiger Name, aber nicht leer → wird tolerant als
            # direkter Key verwendet (siehe CloudProvider._resolve_api_key).
        if not cfg.get('model'):
            return False, 'Kein cloud-Model konfiguriert. Bitte Einstellungen prüfen.'
        return True, ''
    return False, 'Unbekannter AI-Provider'
