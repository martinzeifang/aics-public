"""C3 Vulnerability-Auto-Sync — Orchestrierung (#937).

Sammelt Schwachstellen aus GitHub (Security-Advisories + Dependabot-Alerts) und
GitLab (Vulnerability-Findings), schreibt sie idempotent in ``cra_vuln`` und
liefert einen Sync-Report. Optional werden offene Funde in die verknüpfte
Risikobewertung übernommen (Auto-Promotion, ``sync.auto_promote_to_risk``).

Wird sowohl vom CLI (``python -m cra sync-vulns``) als auch vom geplanten
GitHub-Action-Agenten genutzt.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def _split_repo(repo: str) -> tuple[str, str]:
    repo = (repo or '').replace('https://github.com/', '').strip().rstrip('/')
    if '/' not in repo:
        raise ValueError(f"Repo muss Format 'owner/name' haben, war: {repo!r}")
    owner, name = repo.split('/', 1)
    return owner, name.split('/')[0]


def resolve_repo_from_project(db_path: Path, projekt_name: str) -> str:
    """Liest das verknüpfte GitHub-Repo aus dem CRA-Projekt-Meta (``linked_app.repo``)."""
    from cra.db import load_projekt
    p = load_projekt(db_path, projekt_name)
    if not p:
        return ''
    meta = p.get('meta') if isinstance(p.get('meta'), dict) else {}
    return ((meta.get('linked_app') or {}).get('repo') or '').strip()


def collect_findings(
    *,
    repo: str = '',
    sources: tuple[str, ...] = ('github', 'gitlab'),
    gitlab_base_url: str = '',
    gitlab_project: str = '',
    gitlab_token_env: str = 'GITLAB_TOKEN',
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Sammelt Funde aus allen aktivierten Quellen (ohne Persistenz)."""
    from cra.pflicht_doku_autodetect import (
        detect_vulns, detect_dependabot_vulns, detect_vulns_gitlab,
    )
    findings: list[dict[str, Any]] = []
    if 'github' in sources and repo:
        owner, name = _split_repo(repo)
        findings += detect_dependabot_vulns(owner, name, limit=limit)
        findings += detect_vulns(owner, name, limit=limit)
    if 'gitlab' in sources and gitlab_project:
        findings += detect_vulns_gitlab(
            gitlab_base_url, gitlab_project, gitlab_token_env, limit=limit,
        )
    return findings


_HIGH = ('high', 'critical')


def sync_vulns(
    db_path: Path,
    projekt_name: str,
    *,
    repo: str = '',
    sources: tuple[str, ...] = ('github', 'gitlab'),
    gitlab_base_url: str = '',
    gitlab_project: str = '',
    gitlab_token_env: str = 'GITLAB_TOKEN',
    dry_run: bool = False,
    limit: int = 100,
) -> dict[str, Any]:
    """Synchronisiert Schwachstellen in ``cra_vuln`` und liefert einen Report.

    Report: ``{inserted, updated, unchanged, new_high_critical, total, dry_run,
    findings}``. Idempotent über :func:`cra.db.upsert_vuln`.
    """
    from cra.db import upsert_vuln

    if not repo and 'github' in sources:
        repo = resolve_repo_from_project(db_path, projekt_name)

    findings = collect_findings(
        repo=repo, sources=sources, gitlab_base_url=gitlab_base_url,
        gitlab_project=gitlab_project, gitlab_token_env=gitlab_token_env, limit=limit,
    )

    report = {
        'projekt': projekt_name, 'repo': repo, 'dry_run': dry_run,
        'inserted': 0, 'updated': 0, 'unchanged': 0,
        'new_high_critical': 0, 'total': len(findings), 'findings': [],
    }
    for f in findings:
        entry = {'cve_id': f.get('cve_id'), 'schwere': f.get('schwere'),
                 'source': f.get('source'), 'action': 'dry_run'}
        if not dry_run:
            res = upsert_vuln(db_path, projekt_name, f)
            entry['action'] = res['action']
            report[res['action']] = report.get(res['action'], 0) + 1
            if res['action'] == 'inserted' and (f.get('schwere') in _HIGH):
                report['new_high_critical'] += 1
        report['findings'].append(entry)
    return report


def promote_to_risk(cra_db: Path, rb_db: Path, cra_projekt: str, rb_name: str) -> dict[str, Any]:
    """Übernimmt offene/triagierte CVEs idempotent als RB-Risiken (#937 Phase 6).

    Spiegelt die Logik des Server-Endpunkts (PR #887/#916), aber app-context-frei
    für den CLI/Agent-Pfad.
    """
    from cra.db import list_vuln
    from cra.risk_import import cve_to_risk, provenance_key
    from risikobewertung.db import load_risiken, save_risiko
    from risikobewertung.frameworks import berechne_risiko

    open_cves = [v for v in list_vuln(cra_db, cra_projekt)
                 if v.get('status') in ('open', 'triaging')]
    candidates = [cve_to_risk(v, cra_projekt) for v in open_cves]

    existing = load_risiken(rb_db, rb_name)
    by_prov: dict[tuple, dict] = {}
    max_nr = 0
    for r in existing:
        max_nr = max(max_nr, int(r.get('nr') or 0))
        key = provenance_key(r.get('felder') or {})
        if key:
            by_prov[key] = r

    created = updated = 0
    for cand in candidates:
        score, label, detail = berechne_risiko('STRIDE', cand['felder'])
        cand_key = provenance_key(cand['felder'])
        row = {
            'projekt_name': rb_name, 'risk_name': cand['risk_name'],
            'beschreibung': cand['beschreibung'], 'framework': 'STRIDE',
            'felder': cand['felder'], 'risikowert': score,
            'risiko_label': label, 'detail_text': detail,
            'bewertung_text': cand.get('bewertung_text', ''),
        }
        prev = by_prov.get(cand_key) if cand_key else None
        if prev:
            row['id'] = prev.get('id')
            row['nr'] = prev.get('nr')
            save_risiko(rb_db, row)
            updated += 1
        else:
            max_nr += 1
            row['nr'] = max_nr
            save_risiko(rb_db, row)
            created += 1
    return {'created': created, 'updated': updated, 'total': created + updated}
