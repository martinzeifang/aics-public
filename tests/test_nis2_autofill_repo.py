"""Sprint #21 (#1072/#1074/#1075/#1076) — NIS2 Repo-Scan-Autofill.

Reine Heuristik-Tests ohne Netzwerk; ``github_fetch_text`` /
``_gh_api_json`` werden gemonkeypatcht. Prüft außerdem die #1064-Token-
Durchreichung (HTTP-API statt gh-CLI).
"""

from __future__ import annotations

from nis2 import repo_autofill as ra
from nis2.repo_autofill import AssetSuggestion, VendorSuggestion

COMPOSE = """version: "3.9"
services:
  web:
    image: nginx
  api:
    build: .
  postgres:
    image: postgres:16
    volumes:
      - dbdata:/var/lib/postgresql/data

volumes:
  dbdata:
  uploads:
"""

CHART = """apiVersion: v2
name: my-platform
version: 1.0.0
"""

K8S = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: billing-service
spec:
  template:
    metadata:
      name: billing-pod
"""

TERRAFORM = '''provider "aws" {
  region = "eu-central-1"
}
resource "aws_s3_bucket" "data" {
  bucket = "my-data"
}
'''

SECURITY = """# Security Policy

Please report vulnerabilities to security@example.com.
Our CSIRT will respond within 24h.
"""

SBOM = """{
  "bomFormat": "CycloneDX",
  "components": [
    {"name": "boto3", "supplier": {"name": "Amazon Web Services"}},
    {"name": "leftpad", "publisher": "Community"}
  ]
}"""

PACKAGE_JSON = """{
  "name": "frontend",
  "dependencies": {
    "@aws-sdk/client-s3": "^3.0.0",
    "stripe": "^14.0.0",
    "lodash": "^4.0.0"
  }
}"""

REQUIREMENTS = """boto3==1.34.0
sentry-sdk>=1.0
flask
"""


def _make_fetch(files: dict[str, str]):
    def _fetch(owner, name, path, branch="", token=None):
        return files.get(path)
    return _fetch


# ── N1: Assets ───────────────────────────────────────────────────────────

def test_suggest_assets_from_compose(monkeypatch):
    monkeypatch.setattr(ra, "parse_github_repo", lambda r: ("o", "r"))
    monkeypatch.setattr(ra, "github_fetch_text",
                        _make_fetch({"docker-compose.yml": COMPOSE}))
    monkeypatch.setattr(ra, "_fetch_topics", lambda o, n, t: [])

    out = ra.suggest_assets("o/r")
    names = {a.asset_name for a in out}
    assert {"web", "api", "postgres"} <= names
    # postgres → Datastore → 'daten'/'hoch'
    pg = next(a for a in out if a.asset_name == "postgres")
    assert pg.asset_typ == "daten"
    assert pg.kritikalitaet == "hoch"
    assert all(isinstance(a, AssetSuggestion) for a in out)
    assert all(a.source_path for a in out)


def test_suggest_assets_helm_k8s_terraform_topics(monkeypatch):
    monkeypatch.setattr(ra, "parse_github_repo", lambda r: ("o", "r"))
    monkeypatch.setattr(ra, "github_fetch_text", _make_fetch({
        "Chart.yaml": CHART,
        "k8s/deployment.yaml": K8S,
        "main.tf": TERRAFORM,
    }))
    monkeypatch.setattr(ra, "_fetch_topics", lambda o, n, t: ["nis2", "kritis"])

    out = ra.suggest_assets("o/r")
    names = {a.asset_name for a in out}
    assert "my-platform" in names                        # Helm
    assert "billing-service" in names                    # k8s
    assert any("aws" in n and "Provider" in n for n in names)   # terraform provider
    assert "aws_s3_bucket.data" in names                 # terraform resource
    assert any(n.startswith("Komponente:") for n in names)      # topics


def test_suggest_assets_invalid_repo(monkeypatch):
    monkeypatch.setattr(ra, "parse_github_repo", lambda r: None)
    assert ra.suggest_assets("nope") == []


# ── N3: Incident-Response CSIRT ──────────────────────────────────────────

def test_suggest_incident_response_csirt(monkeypatch):
    monkeypatch.setattr(ra, "parse_github_repo", lambda r: ("o", "r"))
    monkeypatch.setattr(ra, "github_fetch_text",
                        _make_fetch({"SECURITY.md": SECURITY}))
    out = ra.suggest_incident_response("o/r")
    assert out["csirt_email"] == "security@example.com"
    assert "security@example.com" in out["csirt_kontakt"]
    assert out["source_path"] == "SECURITY.md"


def test_suggest_incident_response_no_file(monkeypatch):
    monkeypatch.setattr(ra, "parse_github_repo", lambda r: ("o", "r"))
    monkeypatch.setattr(ra, "github_fetch_text", _make_fetch({}))
    assert ra.suggest_incident_response("o/r") == {}


# ── N4: Vendors ──────────────────────────────────────────────────────────

def test_suggest_vendors_from_sbom(monkeypatch):
    monkeypatch.setattr(ra, "parse_github_repo", lambda r: ("o", "r"))
    monkeypatch.setattr(ra, "github_fetch_text",
                        _make_fetch({"sbom.json": SBOM}))
    out = ra.suggest_vendors("o/r")
    vendors = {v.vendor_name for v in out}
    assert "Amazon Web Services" in vendors
    assert all(isinstance(v, VendorSuggestion) for v in out)


def test_suggest_vendors_from_manifests(monkeypatch):
    monkeypatch.setattr(ra, "parse_github_repo", lambda r: ("o", "r"))
    monkeypatch.setattr(ra, "github_fetch_text", _make_fetch({
        "package.json": PACKAGE_JSON,
        "requirements.txt": REQUIREMENTS,
    }))
    out = ra.suggest_vendors("o/r")
    vendors = {v.vendor_name for v in out}
    assert "Amazon Web Services" in vendors   # @aws-sdk + boto3 (dedupe)
    assert "Stripe" in vendors
    assert "Sentry" in vendors


# ── N5: BCP ──────────────────────────────────────────────────────────────

def test_suggest_bcp_from_compose(monkeypatch):
    monkeypatch.setattr(ra, "parse_github_repo", lambda r: ("o", "r"))
    monkeypatch.setattr(ra, "github_fetch_text",
                        _make_fetch({"docker-compose.yml": COMPOSE}))
    out = ra.suggest_bcp("o/r")
    assert out["source_path"] == "docker-compose.yml"
    assert "dbdata" in out["volumes"]
    assert "uploads" in out["volumes"]
    assert "postgres" in out["datastores"]
    assert "dbdata" in out["backup_strategie"]


def test_suggest_bcp_no_compose(monkeypatch):
    monkeypatch.setattr(ra, "parse_github_repo", lambda r: ("o", "r"))
    monkeypatch.setattr(ra, "github_fetch_text", _make_fetch({}))
    assert ra.suggest_bcp("o/r") == {}


# ── #1064: Token-Durchreichung ───────────────────────────────────────────

def test_assets_thread_token(monkeypatch):
    seen = {}
    monkeypatch.setattr(ra, "parse_github_repo", lambda r: ("o", "r"))

    def _fetch(owner, name, path, branch="", token=None):
        seen["token"] = token
        return None
    monkeypatch.setattr(ra, "github_fetch_text", _fetch)
    monkeypatch.setattr(ra, "_fetch_topics",
                        lambda o, n, t: seen.update(topics_token=t) or [])
    ra.suggest_assets("o/r", token="N1-TOK")
    assert seen["token"] == "N1-TOK"
    assert seen["topics_token"] == "N1-TOK"


def test_vendors_thread_token(monkeypatch):
    seen = {}
    monkeypatch.setattr(ra, "parse_github_repo", lambda r: ("o", "r"))

    def _fetch(owner, name, path, branch="", token=None):
        seen["token"] = token
        return None
    monkeypatch.setattr(ra, "github_fetch_text", _fetch)
    ra.suggest_vendors("o/r", token="N4-TOK")
    assert seen["token"] == "N4-TOK"


def test_fetch_topics_uses_token(monkeypatch):
    seen = {}

    def fake_api(path, token=None):
        seen["path"] = path
        seen["token"] = token
        return {"names": ["a", "b"]}
    monkeypatch.setattr("ai_act.repo_alignment._gh_api_json", fake_api)
    out = ra._fetch_topics("o", "r", "T-TOPICS")
    assert out == ["a", "b"]
    assert seen["token"] == "T-TOPICS"
    assert "o/r/topics" in seen["path"]
