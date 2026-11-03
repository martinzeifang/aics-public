"""Runtime-Integritätsprüfung (best-effort) über Hash-Manifest.

Threat model (Risk #202):
- Detect (not prevent) local tampering of Python modules/scripts.

Design:
- A JSON manifest stores sha256 for a set of files (typically *.py).
- At runtime we can verify current hashes against the manifest.
- Enforcement is optional via env var to avoid breaking dev workflows.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from shared.audit import audit_event


DEFAULT_MANIFEST_PATH = Path(".integrity.manifest.json")


def _repo_root() -> Path:
    # shared/ is located directly under repo root in this project layout.
    return Path(__file__).resolve().parents[1]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_files(base: Path) -> Iterable[Path]:
    # Focus on executable/source artifacts.
    include_suffixes = {".py", ".yml", ".yaml", ".json", ".txt", ".md"}
    exclude_dirs = {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        "out",
        "data",
        "logs",
        ".opencode",
        ".pytest_cache",
        ".mypy_cache",
    }

    for p in base.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(base).parts
        if any(part in exclude_dirs for part in rel_parts):
            continue
        if p.suffix.lower() not in include_suffixes:
            continue

        # Exclude user-editable runtime config to avoid false positives.
        name = p.name.lower()
        if name.endswith(".config.json"):
            continue
        if name in {DEFAULT_MANIFEST_PATH.name.lower()}:
            continue

        yield p


def generate_manifest(*, base_dir: Path | None = None) -> dict:
    base = base_dir or _repo_root()
    items: dict[str, str] = {}
    for p in _iter_files(base):
        rel = str(p.relative_to(base)).replace("\\", "/")
        items[rel] = _sha256_file(p)

    return {
        "format": "aics.integrity.manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base": ".",
        "count": len(items),
        "sha256": items,
    }


def write_manifest(path: Path | None = None, *, base_dir: Path | None = None) -> Path:
    base = base_dir or _repo_root()
    out_path = (base / (path or DEFAULT_MANIFEST_PATH)).resolve()
    manifest = generate_manifest(base_dir=base)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit_event(
        "integrity.manifest.write",
        module="integrity",
        outcome="success",
        details={"path": str(out_path), "count": manifest.get("count")},
    )
    return out_path


@dataclass(frozen=True)
class IntegrityResult:
    ok: bool
    missing: list[str]
    mismatched: list[str]


def verify_manifest(path: Path | None = None, *, base_dir: Path | None = None) -> IntegrityResult:
    base = base_dir or _repo_root()
    manifest_path = (base / (path or DEFAULT_MANIFEST_PATH)).resolve()
    if not manifest_path.exists():
        return IntegrityResult(ok=True, missing=[], mismatched=[])

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected: dict[str, str] = dict(manifest.get("sha256") or {})

    missing: list[str] = []
    mismatched: list[str] = []
    for rel, exp in expected.items():
        p = (base / rel).resolve()
        if not p.exists() or not p.is_file():
            missing.append(rel)
            continue
        cur = _sha256_file(p)
        if cur != exp:
            mismatched.append(rel)

    ok = (not missing) and (not mismatched)
    audit_event(
        "integrity.check",
        module="integrity",
        outcome="success" if ok else "fail",
        details={
            "manifest": str(manifest_path),
            "missing": missing[:50],
            "mismatched": mismatched[:50],
        },
    )
    return IntegrityResult(ok=ok, missing=missing, mismatched=mismatched)


def enforce_if_configured(result: IntegrityResult) -> None:
    """Fail closed if AICS_INTEGRITY_ENFORCE=1."""
    if result.ok:
        return
    if os.environ.get("AICS_INTEGRITY_ENFORCE", "").strip() in {"1", "true", "yes", "on"}:
        raise RuntimeError(
            "Integrity check failed (set AICS_INTEGRITY_ENFORCE=0 to bypass for dev). "
            f"Missing={len(result.missing)} mismatched={len(result.mismatched)}"
        )


def _main(argv: list[str]) -> int:
    # Minimal CLI: python -m shared.integrity [--write] [--verify]
    if "--write" in argv:
        write_manifest()
        return 0
    if "--verify" in argv:
        res = verify_manifest()
        if not res.ok:
            return 2
        return 0
    print("Usage: python -m shared.integrity --write|--verify")
    return 1


if __name__ == "__main__":
    raise SystemExit(_main(list(os.sys.argv[1:])))
