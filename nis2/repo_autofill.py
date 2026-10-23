"""Repo-Scan Auto-Fill für die NIS2-Pflicht-Doku (Sprint #21, #1072–#1076).

Spiegelt das AI-Act A1/A2-Muster (``ai_act/system_doku_autofill.py``): liest
typische Infrastruktur-/Manifest-Dateien eines GitHub-Repos und leitet daraus
**Vorschläge** für die NIS2-Pflicht-Doku-Tabellen ab. Es werden ausschließlich
deterministische, zitierbare Heuristiken genutzt — kein LLM, kein Schreiben.

Token-aware (#1064): alle GitHub-Zugriffe laufen über
``ai_act.repo_alignment.github_fetch_text`` bzw. ``_gh_api_json``, die intern an
``vcs.repo_reader._github_api`` (HTTP-API + Token, gh-CLI-Fallback) delegieren.
Der Token wird vom Endpoint aus der Projekt-VCS-Konfig
(``shared.vcs_repo_config.vcs_token``) aufgelöst und hier durchgereicht.

Abdeckung NIS2 Art. 21(2):
- N1 Asset-Inventar  (#1072): docker-compose, Helm Chart.yaml, k8s-Manifeste,
  Terraform ``*.tf``, GitHub-Topics  → Asset-Vorschläge.
- N3 Incident-Response (#1074): SECURITY.md → CSIRT-/Kontakt-Defaults.
- N4 Supply-Chain    (#1075): SBOM + package.json/requirements.txt → Vendors.
- N5 BCP             (#1076): docker-compose → Backup-/Volume-Hinweise.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from ai_act.repo_alignment import github_fetch_text, parse_github_repo

# ── Kandidaten-Dateien ──────────────────────────────────────────────────────
_COMPOSE_CANDIDATES = (
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "deploy/docker-compose.yml",
    "docker/docker-compose.yml",
)
_HELM_CHART_CANDIDATES = (
    "Chart.yaml",
    "helm/Chart.yaml",
    "chart/Chart.yaml",
    "charts/Chart.yaml",
    "deploy/helm/Chart.yaml",
)
_K8S_CANDIDATES = (
    "k8s/deployment.yaml",
    "k8s/deployment.yml",
    "deploy/k8s/deployment.yaml",
    "manifests/deployment.yaml",
    "kubernetes/deployment.yaml",
    "k8s/manifest.yaml",
)
_TERRAFORM_CANDIDATES = (
    "main.tf",
    "terraform/main.tf",
    "infra/main.tf",
    "deploy/terraform/main.tf",
    "infrastructure/main.tf",
)
_SECURITY_CANDIDATES = (
    "SECURITY.md",
    "Security.md",
    "security.md",
    ".github/SECURITY.md",
    "docs/SECURITY.md",
    ".well-known/security.txt",
)
_SBOM_CANDIDATES = (
    "sbom.json",
    "sbom.spdx.json",
    "sbom.cdx.json",
    "bom.json",
    ".sbom/bom.json",
    "artifacts/sbom.json",
)
_PACKAGE_JSON_CANDIDATES = ("package.json",)
_REQUIREMENTS_CANDIDATES = ("requirements.txt", "requirements/base.txt")

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Vendor-Erkennung: bekannte Pakete → Anbieter (lose Heuristik).
_VENDOR_KEYWORDS: dict[str, str] = {
    "aws": "Amazon Web Services",
    "boto3": "Amazon Web Services",
    "@aws-sdk": "Amazon Web Services",
    "azure": "Microsoft Azure",
    "@azure": "Microsoft Azure",
    "google-cloud": "Google Cloud",
    "@google-cloud": "Google Cloud",
    "stripe": "Stripe",
    "twilio": "Twilio",
    "sendgrid": "Twilio SendGrid",
    "sentry": "Sentry",
    "@sentry": "Sentry",
    "datadog": "Datadog",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "psycopg2": "PostgreSQL",
    "snowflake": "Snowflake",
    "salesforce": "Salesforce",
    "cloudflare": "Cloudflare",
}


# ── Vorschlags-Typen ────────────────────────────────────────────────────────

@dataclass
class AssetSuggestion:
    """Vorschlag für einen ``nis2_asset_inventory``-Eintrag."""
    asset_name: str
    asset_typ: str          # it | ot | daten | cloud-service | netzwerk
    kritikalitaet: str      # niedrig | mittel | hoch | kritisch
    beschreibung: str
    source_path: str
    confidence: float = 0.6

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VendorSuggestion:
    """Vorschlag für einen ``nis2_supply_chain``-Eintrag."""
    vendor_name: str
    leistung: str
    kritikalitaet: str
    source_path: str
    confidence: float = 0.6

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assets_to_dicts(items: list[AssetSuggestion]) -> list[dict[str, Any]]:
    return [a.to_dict() if isinstance(a, AssetSuggestion) else a for a in (items or [])]


def vendors_to_dicts(items: list[VendorSuggestion]) -> list[dict[str, Any]]:
    return [v.to_dict() if isinstance(v, VendorSuggestion) else v for v in (items or [])]


# ── Helfer ──────────────────────────────────────────────────────────────────

def _fetch_first(owner: str, name: str, candidates: tuple[str, ...],
                 branch: str, token: str | None) -> tuple[str, str] | None:
    """Erste existierende Datei aus ``candidates`` als (path, content)."""
    for path in candidates:
        content = github_fetch_text(owner, name, path, branch, token=token)
        if content and content.strip():
            return path, content
    return None


def _fetch_topics(owner: str, name: str, token: str | None) -> list[str]:
    """GitHub-Repo-Topics (#1072). Token-aware via _gh_api_json. Fehler → []."""
    from ai_act.repo_alignment import _gh_api_json
    try:
        data = _gh_api_json(f"repos/{owner}/{name}/topics", token=token)
    except Exception:
        return []
    if isinstance(data, dict):
        names = data.get("names") or []
        return [str(t) for t in names if str(t).strip()]
    return []


def _compose_services(content: str) -> list[str]:
    """Service-Namen aus einer docker-compose-Datei (ohne PyYAML, robust)."""
    services: list[str] = []
    lines = content.splitlines()
    in_services = False
    base_indent: int | None = None
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        if re.match(r"^services\s*:", stripped):
            in_services = True
            base_indent = None
            continue
        if not in_services:
            continue
        # Eine Top-Level-Sektion (kein Einzug) beendet den services-Block.
        if indent == 0 and stripped.endswith(":"):
            in_services = False
            continue
        m = re.match(r"^([A-Za-z0-9._\-]+)\s*:\s*$", stripped)
        if m:
            if base_indent is None:
                base_indent = indent
            if indent == base_indent:
                services.append(m.group(1))
    return services


def _compose_volumes(content: str) -> list[str]:
    """Top-Level-Volume-Namen aus einer docker-compose-Datei (Backup-Hinweis)."""
    volumes: list[str] = []
    lines = content.splitlines()
    in_volumes = False
    base_indent: int | None = None
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        if re.match(r"^volumes\s*:", stripped):
            in_volumes = True
            base_indent = None
            continue
        if not in_volumes:
            continue
        if indent == 0 and stripped.endswith(":"):
            in_volumes = False
            continue
        m = re.match(r"^([A-Za-z0-9._\-]+)\s*:?\s*$", stripped)
        if m:
            if base_indent is None:
                base_indent = indent
            if indent == base_indent:
                volumes.append(m.group(1))
    return volumes


_DATASTORE_HINTS = (
    "postgres", "mysql", "mariadb", "mongo", "redis", "elasticsearch",
    "cassandra", "db", "database", "minio", "rabbitmq", "kafka",
)


def _service_typ_kritikalitaet(service: str) -> tuple[str, str]:
    s = service.lower()
    if any(h in s for h in _DATASTORE_HINTS):
        return "daten", "hoch"
    return "it", "mittel"


# ── N1: Asset-Inventar (#1072) ──────────────────────────────────────────────

def suggest_assets(repo: str, branch: str = "",
                   token: str | None = None) -> list[AssetSuggestion]:
    """Asset-Vorschläge aus Infrastruktur-Manifesten + GitHub-Topics.

    Liest docker-compose (Services), Helm Chart.yaml (App-Name), k8s-Manifeste,
    Terraform ``main.tf`` (Provider/Ressourcen) und Repo-Topics.
    """
    parsed = parse_github_repo(repo)
    if not parsed:
        return []
    owner, name = parsed

    out: list[AssetSuggestion] = []
    seen: set[str] = set()

    def _add(asset: AssetSuggestion) -> None:
        key = asset.asset_name.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(asset)

    # docker-compose → Services als IT/Daten-Assets
    compose = _fetch_first(owner, name, _COMPOSE_CANDIDATES, branch, token)
    if compose:
        path, content = compose
        for svc in _compose_services(content):
            typ, krit = _service_typ_kritikalitaet(svc)
            _add(AssetSuggestion(
                asset_name=svc, asset_typ=typ, kritikalitaet=krit,
                beschreibung=f"Container-Service aus {path}",
                source_path=path, confidence=0.7,
            ))

    # Helm Chart.yaml → Anwendung als Asset
    helm = _fetch_first(owner, name, _HELM_CHART_CANDIDATES, branch, token)
    if helm:
        path, content = helm
        m = re.search(r"^name\s*:\s*(.+)$", content, re.MULTILINE)
        app = (m.group(1).strip().strip("'\"") if m else "").strip()
        if app:
            _add(AssetSuggestion(
                asset_name=app, asset_typ="it", kritikalitaet="hoch",
                beschreibung=f"Helm-Chart-Anwendung aus {path}",
                source_path=path, confidence=0.7,
            ))

    # Kubernetes-Manifest → benannte Workloads
    k8s = _fetch_first(owner, name, _K8S_CANDIDATES, branch, token)
    if k8s:
        path, content = k8s
        for m in re.finditer(r"^\s*name\s*:\s*(.+)$", content, re.MULTILINE):
            wl = m.group(1).strip().strip("'\"")
            if wl:
                _add(AssetSuggestion(
                    asset_name=wl, asset_typ="it", kritikalitaet="mittel",
                    beschreibung=f"Kubernetes-Workload aus {path}",
                    source_path=path, confidence=0.6,
                ))

    # Terraform → Provider/Ressourcen als Cloud-Service-Assets
    tf = _fetch_first(owner, name, _TERRAFORM_CANDIDATES, branch, token)
    if tf:
        path, content = tf
        providers = sorted(set(re.findall(
            r'provider\s+"([A-Za-z0-9_\-]+)"', content)))
        for prov in providers:
            _add(AssetSuggestion(
                asset_name=f"{prov} (Terraform-Provider)",
                asset_typ="cloud-service", kritikalitaet="hoch",
                beschreibung=f"Infrastruktur via Terraform-Provider '{prov}' ({path})",
                source_path=path, confidence=0.65,
            ))
        for rtype, rname in re.findall(
                r'resource\s+"([A-Za-z0-9_\-]+)"\s+"([A-Za-z0-9_\-]+)"', content):
            _add(AssetSuggestion(
                asset_name=f"{rtype}.{rname}",
                asset_typ="cloud-service", kritikalitaet="mittel",
                beschreibung=f"Terraform-Ressource aus {path}",
                source_path=path, confidence=0.6,
            ))

    # GitHub-Topics → grobe System-Klassifizierung
    for topic in _fetch_topics(owner, name, token):
        _add(AssetSuggestion(
            asset_name=f"Komponente: {topic}", asset_typ="it",
            kritikalitaet="niedrig",
            beschreibung=f"Abgeleitet aus GitHub-Topic '{topic}'",
            source_path="github:topics", confidence=0.4,
        ))

    return out


# ── N3: Incident-Response — CSIRT-Defaults aus SECURITY.md (#1074) ───────────

def suggest_incident_response(repo: str, branch: str = "",
                              token: str | None = None) -> dict[str, Any]:
    """Liest SECURITY.md und leitet CSIRT-Kontakt-Defaults ab.

    Liefert ein Dict mit den ``nis2_incident_response``-Feldern, für die etwas
    gefunden wurde, plus ``source_path``. Die NIS2-SLAs (24h/72h/1M) bleiben
    fest und werden nicht überschrieben (vom Wizard/Default vorgegeben).
    """
    parsed = parse_github_repo(repo)
    if not parsed:
        return {}
    owner, name = parsed

    sec = _fetch_first(owner, name, _SECURITY_CANDIDATES, branch, token)
    if not sec:
        return {}
    path, content = sec

    out: dict[str, Any] = {"source_path": path}
    emails = _EMAIL_RE.findall(content)
    if emails:
        out["csirt_email"] = emails[0]
        out["csirt_kontakt"] = (
            f"Security-Kontakt laut {path}: {emails[0]}"
        )
    # Mailto-/Contact-Zeile (security.txt) bevorzugt
    m = re.search(r"(?im)^\s*contact\s*:\s*(.+)$", content)
    if m:
        out["eskalation_pfad"] = m.group(1).strip()
    return out


# ── N4: Supply-Chain — Vendors aus SBOM/Manifest (#1075) ─────────────────────

def _sbom_vendors(content: str, path: str) -> list[VendorSuggestion]:
    """Liefert Vendor-Vorschläge aus einer CycloneDX/SPDX-SBOM (JSON)."""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return []
    out: list[VendorSuggestion] = []
    seen: set[str] = set()

    def _add(vendor: str, leistung: str) -> None:
        key = vendor.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(VendorSuggestion(
                vendor_name=vendor, leistung=leistung,
                kritikalitaet="mittel", source_path=path, confidence=0.6,
            ))

    # CycloneDX: components[].publisher / group / supplier.name
    for comp in (data.get("components") or []):
        if not isinstance(comp, dict):
            continue
        supplier = comp.get("supplier") or {}
        vendor = (
            (supplier.get("name") if isinstance(supplier, dict) else None)
            or comp.get("publisher") or comp.get("group")
        )
        if vendor:
            _add(str(vendor), f"SBOM-Komponente: {comp.get('name', '')}".strip())
    # SPDX: packages[].supplier ("Organization: Foo")
    for pkg in (data.get("packages") or []):
        if not isinstance(pkg, dict):
            continue
        sup = str(pkg.get("supplier") or "")
        m = re.match(r"^\s*(?:Organization|Person)\s*:\s*(.+)$", sup)
        if m:
            _add(m.group(1).strip(), f"SBOM-Paket: {pkg.get('name', '')}".strip())
    return out


def _manifest_vendors(content: str, path: str, *, is_json: bool) -> list[VendorSuggestion]:
    """Vendor-Vorschläge aus package.json bzw. requirements.txt via Keyword-Map."""
    names: list[str] = []
    if is_json:
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            data = {}
        for sec in ("dependencies", "devDependencies", "peerDependencies"):
            deps = data.get(sec)
            if isinstance(deps, dict):
                names.extend(deps.keys())
    else:
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            pkg = re.split(r"[<>=!~;\[ ]", line, 1)[0].strip()
            if pkg:
                names.append(pkg)

    out: list[VendorSuggestion] = []
    seen: set[str] = set()
    for pkg in names:
        low = pkg.lower()
        for kw, vendor in _VENDOR_KEYWORDS.items():
            if kw in low:
                if vendor.lower() in seen:
                    break
                seen.add(vendor.lower())
                out.append(VendorSuggestion(
                    vendor_name=vendor,
                    leistung=f"Abhängigkeit '{pkg}' aus {path}",
                    kritikalitaet="mittel", source_path=path, confidence=0.55,
                ))
                break
    return out


def suggest_vendors(repo: str, branch: str = "",
                    token: str | None = None) -> list[VendorSuggestion]:
    """Vendor-Vorschläge: bevorzugt SBOM, sonst package.json/requirements.txt."""
    parsed = parse_github_repo(repo)
    if not parsed:
        return []
    owner, name = parsed

    out: list[VendorSuggestion] = []
    seen: set[str] = set()

    def _merge(items: list[VendorSuggestion]) -> None:
        for it in items:
            key = it.vendor_name.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(it)

    sbom = _fetch_first(owner, name, _SBOM_CANDIDATES, branch, token)
    if sbom:
        path, content = sbom
        _merge(_sbom_vendors(content, path))

    pj = _fetch_first(owner, name, _PACKAGE_JSON_CANDIDATES, branch, token)
    if pj:
        path, content = pj
        _merge(_manifest_vendors(content, path, is_json=True))

    rq = _fetch_first(owner, name, _REQUIREMENTS_CANDIDATES, branch, token)
    if rq:
        path, content = rq
        _merge(_manifest_vendors(content, path, is_json=False))

    return out


# ── N5: BCP — Backup-Hinweise aus docker-compose (#1076) ─────────────────────

def suggest_bcp(repo: str, branch: str = "",
                token: str | None = None) -> dict[str, Any]:
    """Backup-Hinweise aus docker-compose (benannte Volumes + Datenbank-Services).

    Liefert ein Dict mit BCP-Feldern (``backup_strategie``, ``notizen``,
    ``source_path``) als Vorschlag — RPO/RTO-Defaults kommen aus dem
    Sektor-Wizard und werden hier nicht gesetzt.
    """
    parsed = parse_github_repo(repo)
    if not parsed:
        return {}
    owner, name = parsed

    compose = _fetch_first(owner, name, _COMPOSE_CANDIDATES, branch, token)
    if not compose:
        return {}
    path, content = compose

    volumes = _compose_volumes(content)
    services = _compose_services(content)
    datastores = [s for s in services if any(h in s.lower() for h in _DATASTORE_HINTS)]
    if not volumes and not datastores:
        return {}

    parts: list[str] = []
    if volumes:
        parts.append("Persistente Volumes (Backup-Kandidaten): " + ", ".join(volumes))
    if datastores:
        parts.append("Datenbank-/Stateful-Services: " + ", ".join(datastores))

    return {
        "source_path": path,
        "backup_strategie": (
            "Empfohlen: regelmäßige Sicherung der persistenten Volumes "
            + (", ".join(volumes) if volumes else "(keine benannten Volumes gefunden)")
            + " inkl. Wiederherstellungstests."
        ),
        "notizen": "Repo-Scan-Hinweis (" + path + "):\n- " + "\n- ".join(parts),
        "volumes": volumes,
        "datastores": datastores,
    }
