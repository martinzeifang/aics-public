"""Helper für API-Endpoints, die in Workspace-internen Tempverzeichnissen arbeiten.

Hintergrund: viele io_xlsx/report_export-Funktionen nutzen security_utils.safe_generated_file,
das nur Pfade unterhalb des Repo-Roots erlaubt. /tmp ist außerhalb → ValueError.

Im Docker-Container ist `/app/var` root-owned und nicht beschreibbar. Daher
liegt der Tempspace per Default unter `/app/data/tmp/` (= aics_data Volume,
vom aics-User schreibbar). Überschreibbar via ENV `AICS_TMP_DIR`.
"""

from __future__ import annotations
import os
import tempfile
from pathlib import Path

from security_utils import workspace_root_from


def _workspace_root() -> Path:
    return workspace_root_from(Path(__file__))


def _tmp_base() -> Path:
    """Bestimmt das temp-Basisverzeichnis (überschreibbar via AICS_TMP_DIR)."""
    env = os.environ.get('AICS_TMP_DIR', '').strip()
    if env:
        return Path(env)
    # Default: data/tmp/ unter dem Workspace-Root.
    # data/ ist im Docker ein gemountetes Volume (schreibbar), lokal ein
    # ganz normales Verzeichnis im Repo.
    return _workspace_root() / 'data' / 'tmp'


def workspace_tmpdir(prefix: str = 'aics_') -> Path:
    """Legt ein temporäres Verzeichnis im Workspace-temp-Pfad an."""
    base = _tmp_base()
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=str(base)))
