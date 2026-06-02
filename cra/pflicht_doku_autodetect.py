"""CRA Pflicht-Doku Auto-Detection aus GitHub-Repo (#558).

Scannt ein GitHub-Repo und extrahiert Daten für die 5 Pflicht-Doku-Bereiche
direkt aus echten Artefakten (Releases, SECURITY.md, Security-Advisories,
Repo-Historie, Threat-Model-Dateien).

Pattern: Dry-Run gibt nur Funde zurück, Apply-Modus schreibt in die Pflicht-Doku-DB
(aber nur in leere Felder — bestehende Daten bleiben unangetastet).
"""
from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from cra.repo_alignment import (
    _gh_api_json,
    _github_path_exists,
    reset_permission_counter,
    get_permission_denied_count,
)
from cra.db import (
    list_sbom, save_sbom,
    load_psirt, save_psirt,
    list_vuln, save_vuln,
    load_support_period, save_support_period,
    load_threatmodel, save_threatmodel,
)

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# C1: SBOM-Erkennung aus Releases + Workflows
# ─────────────────────────────────────────────────────────────────────────

SBOM_ASSET_PATTERNS = [
    r'\.spdx\.json$',
    r'\.spdx$',
    r'.*cyclonedx.*\.json$',
    r'.*sbom.*\.json$',
    r'.*sbom.*\.xml$',
]

SBOM_WORKFLOW_PATTERNS = [
    '.github/workflows/sbom.yml',
    '.github/workflows/sbom.yaml',
    '.github/workflows/cra-sbom.yml',
    '.github/workflows/cyclonedx.yml',
    '.github/workflows/spdx.yml',
]


def detect_sboms(owner: str, repo: str) -> list[dict[str, Any]]:
    """Liefert Liste aufgefundener SBOM-Hinweise (Releases + Workflows)."""
    findings: list[dict[str, Any]] = []

    # Variante A: Releases mit SBOM-Assets
    try:
        releases = _gh_api_json(f"repos/{owner}/{repo}/releases?per_page=20") or []
    except Exception as e:
        log.debug("releases fetch failed: %s", e)
        releases = []

    for rel in releases:
        tag = rel.get('tag_name', '')
        published = (rel.get('published_at') or rel.get('created_at') or '')[:10]
        for asset in rel.get('assets', []) or []:
            name = asset.get('name', '')
            for pat in SBOM_ASSET_PATTERNS:
                if re.search(pat, name, re.IGNORECASE):
                    fmt = 'cyclonedx' if 'cyclonedx' in name.lower() else 'spdx'
                    findings.append({
                        'release_version': tag,
                        'sbom_format': fmt,
                        'sbom_datum': published,
                        'quelle': f"auto:github:release:{tag}",
                        'blob_path': asset.get('browser_download_url', ''),
                        'komponenten_count': 0,  # erfordert Download zum Parsen
                        'lizenzen': [],
                        'notizen': f"Auto-erkannt aus Release-Asset '{name}'",
                    })
                    break

    # Variante B: SBOM-Workflow vorhanden (deutet auf CI-Generierung)
    for wf in SBOM_WORKFLOW_PATTERNS:
        ok, _ev = _github_path_exists(owner, repo, wf)
        if ok and not any(f['quelle'].startswith('auto:github:workflow') for f in findings):
            findings.append({
                'release_version': 'workflow-detected',
                'sbom_format': 'spdx',
                'sbom_datum': datetime.utcnow().strftime('%Y-%m-%d'),
                'quelle': f"auto:github:workflow:{wf}",
                'blob_path': f"https://github.com/{owner}/{repo}/blob/HEAD/{wf}",
                'komponenten_count': 0,
                'lizenzen': [],
                'notizen': f"SBOM-Workflow erkannt: {wf} — generiert SBOM in CI.",
            })
            break

    return findings


# ─────────────────────────────────────────────────────────────────────────
# C2: PSIRT-Erkennung aus SECURITY.md
# ─────────────────────────────────────────────────────────────────────────

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
SLA_RE = re.compile(r'(\d+)\s*(stunden?|hours?|tage?|days?|h\b|d\b)', re.IGNORECASE)


def _fetch_file_content(owner: str, repo: str, path: str) -> str | None:
    try:
        data = _gh_api_json(f"repos/{owner}/{repo}/contents/{path}")
        if isinstance(data, dict) and data.get('content'):
            return base64.b64decode(data['content']).decode('utf-8', errors='replace')
    except Exception as e:
        log.debug("file fetch %s failed: %s", path, e)
    return None


def detect_psirt(owner: str, repo: str) -> dict[str, Any]:
    """Extrahiert PSIRT-Konfiguration aus SECURITY.md / security.txt."""
    found: dict[str, Any] = {}

    # SECURITY.md hat Vorrang
    for path in ('SECURITY.md', '.github/SECURITY.md', 'docs/SECURITY.md', '.well-known/security.txt'):
        content = _fetch_file_content(owner, repo, path)
        if not content:
            continue

        # Intake-Kanal: erste E-Mail-Adresse
        if not found.get('intake_kanal'):
            emails = EMAIL_RE.findall(content)
            # bevorzuge security@/psirt@ Adressen
            preferred = [e for e in emails if any(k in e.lower() for k in ('security', 'psirt', 'cert', 'soc'))]
            if preferred:
                found['intake_kanal'] = preferred[0]
            elif emails:
                found['intake_kanal'] = emails[0]

        # URLs
        if 'SECURITY.md' in path or path == 'docs/SECURITY.md':
            found['security_md_url'] = f"https://github.com/{owner}/{repo}/blob/HEAD/{path}"

        # SLA-Heuristik aus Text
        if not found.get('triage_sla'):
            # Suche "triage" + Nummer
            m = re.search(r'triage[^\n]{0,80}?(\d+\s*(?:stunden?|hours?|tage?|days?|h\b|d\b))', content, re.IGNORECASE | re.DOTALL)
            if m:
                found['triage_sla'] = m.group(1).strip()

        if not found.get('fix_sla_critical'):
            m = re.search(r'(critical|kritisch)[^\n]{0,80}?(\d+\s*(?:stunden?|hours?|tage?|days?|h\b|d\b))', content, re.IGNORECASE | re.DOTALL)
            if m:
                found['fix_sla_critical'] = m.group(2).strip()

        # Hinweis: gefunden via
        found.setdefault('notizen', f"Auto-erkannt aus {path}")
        break

    # Disclosure-Policy-URL aus .well-known
    ok_sectxt, _ = _github_path_exists(owner, repo, '.well-known/security.txt')
    if ok_sectxt and not found.get('disclosure_policy_url'):
        found['disclosure_policy_url'] = f"https://github.com/{owner}/{repo}/blob/HEAD/.well-known/security.txt"

    return found


# ─────────────────────────────────────────────────────────────────────────
# C3: Vuln-Tracker aus GitHub Security Advisories
# ─────────────────────────────────────────────────────────────────────────

SEVERITY_MAP = {
    'critical': 'critical',
    'high': 'high',
    'medium': 'medium',
    'moderate': 'medium',
    'low': 'low',
}


def detect_vulns(owner: str, repo: str, limit: int = 20) -> list[dict[str, Any]]:
    """Lädt öffentliche Security-Advisories des Repos."""
    findings: list[dict[str, Any]] = []
    try:
        advs = _gh_api_json(f"repos/{owner}/{repo}/security-advisories?per_page={limit}") or []
    except Exception as e:
        log.debug("advisories fetch failed: %s", e)
        return findings

    for adv in advs[:limit]:
        cve = adv.get('cve_id') or adv.get('ghsa_id') or ''
        if not cve:
            continue
        sev = SEVERITY_MAP.get((adv.get('severity') or '').lower(), 'unknown')
        cvss = (adv.get('cvss') or {}).get('score') or 0
        state = (adv.get('state') or '').lower()
        status = 'fixed' if state == 'published' and adv.get('closed_at') else ('disclosed' if state == 'published' else 'triaging')

        # Affected components
        components = []
        for v in adv.get('vulnerabilities') or []:
            pkg = (v.get('package') or {}).get('name', '')
            if pkg:
                components.append(pkg)

        findings.append({
            'cve_id': cve,
            'titel': adv.get('summary', '')[:200],
            'schwere': sev,
            'cvss_score': float(cvss) if cvss else 0.0,
            'affected_component': ', '.join(components[:3]),
            'advisory_url': adv.get('html_url', ''),
            'status': status,
            'fixed_at': (adv.get('closed_at') or '')[:10] or None,
            'disclosed_at': (adv.get('published_at') or '')[:10] or None,
        })
    return findings


# ─────────────────────────────────────────────────────────────────────────
# C4: Support-Period aus Repo-Historie
# ─────────────────────────────────────────────────────────────────────────

def detect_support_period(owner: str, repo: str) -> dict[str, Any]:
    """Bestimmt Markteintritts-Datum aus erstem Release / ältestem Commit."""
    markteintritt = None

    # Variante A: ältester Release-Tag
    try:
        releases = _gh_api_json(f"repos/{owner}/{repo}/releases?per_page=100") or []
        if releases:
            dates = [r.get('published_at') or r.get('created_at') for r in releases if r.get('published_at') or r.get('created_at')]
            if dates:
                markteintritt = min(dates)[:10]
    except Exception:
        pass

    # Variante B: Repo-Erstellungs-Datum als Fallback
    if not markteintritt:
        try:
            repo_data = _gh_api_json(f"repos/{owner}/{repo}")
            markteintritt = (repo_data.get('created_at') or '')[:10] or None
        except Exception:
            pass

    if not markteintritt:
        return {}

    support_jahre = 5  # CRA-Default
    try:
        mt = datetime.fromisoformat(markteintritt)
        eol = (mt + timedelta(days=support_jahre * 365)).date().isoformat()
    except Exception:
        eol = None

    return {
        'markteintritt_datum': markteintritt,
        'support_jahre': support_jahre,
        'eol_datum': eol,
        'rationale': f"Auto-erkannt: ältester Release/Repo-Erstellung am {markteintritt}, CRA-Default 5 Jahre",
        'update_kanal': 'GitHub Releases',
    }


# ─────────────────────────────────────────────────────────────────────────
# C5: Threat-Model aus Repo-Dateien
# ─────────────────────────────────────────────────────────────────────────

THREATMODEL_PATHS = [
    'THREATMODEL.md',
    'threatmodel.md',
    'docs/threat-model.md',
    'docs/threatmodel.md',
    'docs/security/threat-model.md',
    'docs/security/threatmodel.md',
    '.security/threat-model.md',
]

FRAMEWORK_KEYWORDS = {
    'STRIDE': ['stride', 'spoofing', 'tampering', 'repudiation', 'information disclosure', 'denial of service', 'elevation of privilege'],
    'PASTA': ['pasta', 'process for attack simulation'],
    'LINDDUN': ['linddun', 'linkability', 'identifiability'],
}


def detect_threatmodel(owner: str, repo: str) -> dict[str, Any]:
    """Findet Threat-Model-Doku + erkennt verwendetes Framework."""
    for path in THREATMODEL_PATHS:
        content = _fetch_file_content(owner, repo, path)
        if not content:
            continue
        lower = content.lower()
        # Framework erkennen
        framework = 'STRIDE'  # Default
        scores = {fw: sum(1 for kw in kws if kw in lower) for fw, kws in FRAMEWORK_KEYWORDS.items()}
        if scores:
            framework = max(scores.items(), key=lambda x: x[1])[0]

        # Erste Überschrift als Scope
        scope_match = re.search(r'^#\s*(.+)$', content, re.MULTILINE)
        scope = scope_match.group(1).strip() if scope_match else 'Threat-Model (auto-detected)'

        return {
            'framework': framework,
            'scope': scope,
            'diagram_url': f"https://github.com/{owner}/{repo}/blob/HEAD/{path}",
            'notizen': f"Auto-erkannt aus {path}",
            'assets': [],
            'threats': [],
            'mitigations': [],
        }
    return {}


# ─────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────

def _check_repo_access(owner: str, repo: str) -> dict[str, Any]:
    """Prüft ob das Repo überhaupt erreichbar ist und gibt Diagnose zurück."""
    from shared.github_config import get_github_token
    try:
        data = _gh_api_json(f"repos/{owner}/{repo}")
        return {
            'accessible': True,
            'private': data.get('private', False),
            'auth_used': 'token' if get_github_token() else 'unauthenticated',
            'rate_limit_hint': '5000/h' if get_github_token() else '60/h',
        }
    except Exception as e:
        msg = str(e)
        hints: list[str] = []
        if '404' in msg:
            hints.append("Repo nicht gefunden ODER privat ohne Token-Zugriff.")
        if 'rate limit' in msg.lower():
            hints.append("Rate-Limit erreicht — GH_TOKEN setzen.")
        if not get_github_token():
            hints.append("Kein GH_TOKEN konfiguriert. Admin → Einstellungen → GitHub.")
        return {'accessible': False, 'error': msg, 'hints': hints}


def autodetect_all(owner: str, repo: str) -> dict[str, Any]:
    """Führt alle 5 Detektoren aus und liefert konsolidierten Bericht inkl. Diagnose."""
    access = _check_repo_access(owner, repo)
    if not access.get('accessible'):
        return {
            'sbom': [], 'psirt': {}, 'vuln': [], 'support_period': {}, 'threatmodel': {},
            'warnings': [f"Repo nicht erreichbar: {access.get('error')}"] + access.get('hints', []),
            'access': access,
        }

    warnings: list[str] = []
    if access.get('private') and access.get('auth_used') == 'unauthenticated':
        warnings.append("Privates Repo aber unauthentifiziert — wahrscheinlich liefert die API überall 404.")

    # #563: Counter resetten BEVOR Detektoren laufen
    reset_permission_counter()

    result = {
        'sbom': detect_sboms(owner, repo),
        'psirt': detect_psirt(owner, repo),
        'vuln': detect_vulns(owner, repo),
        'support_period': detect_support_period(owner, repo),
        'threatmodel': detect_threatmodel(owner, repo),
        'access': access,
        'warnings': warnings,
    }

    # #563: Wenn Permission-Denied beim Contents-Endpoint → klare Anleitung
    perm_denied, last_path = get_permission_denied_count()
    if perm_denied > 0:
        result['warnings'].append(
            f"⚠️ Token hat KEINE 'Contents:Read'-Permission ({perm_denied} 403-Antworten). "
            f"Letzter Pfad: {last_path}. "
            "Fix: GitHub → Settings → Developer settings → Personal access tokens → "
            "Token editieren → Repository permissions → Contents: Read-only aktivieren."
        )
        result['permission_denied_count'] = perm_denied

    # Falls trotz Erreichbarkeit nichts gefunden wurde → Hinweis
    total = (len(result['sbom']) + len(result['psirt']) + len(result['vuln'])
             + (1 if result['support_period'] else 0) + (1 if result['threatmodel'] else 0))
    if total == 0 and perm_denied == 0:
        result['warnings'].append(
            "Repo erreichbar, aber keine Pflicht-Doku-Artefakte erkannt. "
            "Erwartet werden z.B. SECURITY.md, Releases, .github/workflows/sbom.yml, docs/threat-model.md."
        )
    return result


def apply_findings(db_path: Path, projekt_name: str, findings: dict[str, Any]) -> dict[str, int]:
    """Schreibt Funde in die Pflicht-Doku-DB.

    Regel: bestehende 1:1-Einträge (PSIRT/SP/TM) werden nur ergänzt wo Felder leer sind.
    Listen-Einträge (SBOM/Vuln) werden hinzugefügt, sofern noch nicht vorhanden.
    """
    counts = {'sbom': 0, 'psirt': 0, 'vuln': 0, 'support_period': 0, 'threatmodel': 0}

    # SBOM: Add-if-not-exists per (release_version, sbom_format)
    existing_sboms = {(s['release_version'], s['sbom_format']) for s in list_sbom(db_path, projekt_name)}
    for s in findings.get('sbom') or []:
        key = (s.get('release_version'), s.get('sbom_format'))
        if key not in existing_sboms:
            try:
                save_sbom(db_path, projekt_name, s)
                counts['sbom'] += 1
            except Exception as e:
                log.warning("save_sbom failed: %s", e)

    # PSIRT: merge in leere Felder
    psirt = findings.get('psirt') or {}
    if psirt:
        current = load_psirt(db_path, projekt_name) or {}
        merged = dict(current)
        changed = False
        for k, v in psirt.items():
            if v and not current.get(k):
                merged[k] = v
                changed = True
        if changed:
            save_psirt(db_path, projekt_name, merged)
            counts['psirt'] = 1

    # Vuln: Add-if-not-exists per cve_id
    existing_cves = {v['cve_id'] for v in list_vuln(db_path, projekt_name)}
    for v in findings.get('vuln') or []:
        if v.get('cve_id') and v['cve_id'] not in existing_cves:
            try:
                save_vuln(db_path, projekt_name, v)
                counts['vuln'] += 1
            except Exception as e:
                log.warning("save_vuln failed: %s", e)

    # Support-Period: nur setzen wenn leer
    sp = findings.get('support_period') or {}
    if sp:
        current = load_support_period(db_path, projekt_name) or {}
        if not current.get('markteintritt_datum'):
            save_support_period(db_path, projekt_name, sp)
            counts['support_period'] = 1

    # Threat-Model: nur setzen wenn leer
    tm = findings.get('threatmodel') or {}
    if tm:
        current = load_threatmodel(db_path, projekt_name) or {}
        if not current.get('framework') or current.get('framework') == 'STRIDE' and not current.get('scope'):
            save_threatmodel(db_path, projekt_name, tm)
            counts['threatmodel'] = 1

    return counts
