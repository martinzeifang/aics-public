"""Hardware-Fingerprint: sha256(hostname + volume-id) — oder persistenter Seed.

Tolerantes Fingerprinting — bewusst ohne MAC (ändert sich bei Docker-Recreate)
und CPU-ID (in VMs nicht stabil).

Reihenfolge (#412):
1. ENV ``AICS_FINGERPRINT_SEED`` — Operator-Override
2. ``<data_dir>/.fingerprint-seed`` — beim ersten Start auto-generiert,
   im persistenten Volume → überlebt Container-Recreates
3. Klassisch: sha256(hostname + machine-id) — Fallback für lokale Installs

Plattform-Strategien für Fallback 3:
- Linux / Docker: /etc/machine-id (vom systemd verwaltet, stabil)
- macOS: IOPlatformUUID via `ioreg`
- Windows: GetVolumeInformation (C: Volume Serial)
- Fallback: hostname allein (besser als nichts)
"""

from __future__ import annotations

import hashlib
import os
import platform
import secrets
import socket
import subprocess
from pathlib import Path
from typing import Final

_FP_LEN: Final[int] = 64  # sha256-hexdigest


def _data_dir() -> Path:
    """Persistentes Datenverzeichnis — /app/data im Container, sonst data/."""
    return Path('/app/data') if Path('/app/data').exists() else Path('data')


def _load_or_create_seed() -> str:
    """Persistenter Fingerprint-Seed im Volume.

    Returnt ein 64-Zeichen-Hex. Reihenfolge:
      1. existing seed-File → return
      2. existing license.token → extrahiere fp-Claim → migrate (Backward-Kompat
         für vor #412 aktivierte Tokens, die mit Hostname-FP signiert wurden)
      3. neu generieren mit secrets.token_hex(32)
    """
    seed_path = _data_dir() / '.fingerprint-seed'
    try:
        if seed_path.exists():
            existing = seed_path.read_text('ascii').strip()
            if len(existing) == _FP_LEN and all(c in '0123456789abcdef' for c in existing):
                return existing

        seed_path.parent.mkdir(parents=True, exist_ok=True)

        # Backward-Compat: existing Token → fp daraus übernehmen
        seed_from_token = _extract_fp_from_cached_token()
        new_seed = seed_from_token or secrets.token_hex(32)

        seed_path.write_text(new_seed, encoding='ascii')
        try:
            os.chmod(seed_path, 0o600)
        except OSError:
            pass
        return new_seed
    except OSError:
        return ''


def _extract_fp_from_cached_token() -> str:
    """Liest den fp-Claim aus dem (Base64-codierten) license.token im
    persistenten Volume. Returnt '' wenn nicht vorhanden oder kaputt.
    """
    import base64
    import json

    p = _data_dir() / 'license.token'
    if not p.exists():
        return ''
    try:
        raw = p.read_bytes()
        # Cache-Format: 'AICS-LIC-CACHE-v1\n' + b64(token)
        if raw.startswith(b'AICS-LIC-CACHE-v1\n'):
            raw = raw[len(b'AICS-LIC-CACHE-v1\n'):]
            token = base64.b64decode(raw).decode('utf-8').strip()
        else:
            token = raw.decode('utf-8', errors='replace').strip()
        # Token-Format: header.payload.sig (Base64-URL)
        parts = token.split('.')
        if len(parts) != 3:
            return ''
        pad = '=' * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad))
        fp = str(payload.get('fp') or '').strip().lower()
        if len(fp) == _FP_LEN and all(c in '0123456789abcdef' for c in fp):
            return fp
    except Exception:  # noqa: BLE001
        pass
    return ''


def _volume_id_linux() -> str:
    """/etc/machine-id ist die kanonische Linux-Maschine-Identität (systemd)."""
    for p in ('/etc/machine-id', '/var/lib/dbus/machine-id'):
        try:
            with open(p, 'r', encoding='ascii') as f:
                v = f.read().strip()
            if len(v) >= 16:
                return v
        except OSError:
            continue
    return ''


def _volume_id_macos() -> str:
    try:
        out = subprocess.check_output(
            ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
            timeout=5, text=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return ''
    for line in out.splitlines():
        if 'IOPlatformUUID' in line:
            parts = line.split('=')
            if len(parts) > 1:
                return parts[1].strip().strip('"')
    return ''


def _volume_id_windows() -> str:
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        volume_serial = ctypes.c_ulong()
        max_component = ctypes.c_ulong()
        fs_flags = ctypes.c_ulong()
        ok = kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p('C:\\'),
            None, 0,
            ctypes.byref(volume_serial),
            ctypes.byref(max_component),
            ctypes.byref(fs_flags),
            None, 0,
        )
        if ok:
            return f'{volume_serial.value:08X}'
    except Exception:  # noqa: BLE001
        pass
    return ''


def _volume_id() -> str:
    system = platform.system().lower()
    if system == 'linux':
        return _volume_id_linux()
    if system == 'darwin':
        return _volume_id_macos()
    if system == 'windows':
        return _volume_id_windows()
    return ''


def _hostname() -> str:
    return socket.gethostname() or os.environ.get('HOSTNAME', '') or 'unknown'


def compute_fingerprint() -> str:
    """Stabiler 64-stelliger Hex-Fingerprint (#412).

    Reihenfolge:
      1. ENV AICS_FINGERPRINT_SEED (vom Operator gesetzt)
      2. <data_dir>/.fingerprint-seed (persistent, beim ersten Start angelegt)
      3. sha256(hostname + machine-id) — Fallback für lokale Installs
    """
    env_seed = os.environ.get('AICS_FINGERPRINT_SEED', '').strip().lower()
    if len(env_seed) == _FP_LEN and all(c in '0123456789abcdef' for c in env_seed):
        return env_seed

    persisted = _load_or_create_seed()
    if persisted:
        return persisted

    raw = f'{_hostname()}|{_volume_id()}'.encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def machine_label() -> str:
    """Menschen-lesbares Label fürs Reporting — Hostname + Platform."""
    return f'{_hostname()} ({platform.system()})'
