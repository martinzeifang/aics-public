"""Gemeinsame Helfer für die pro-Projekt-Repository-Konfiguration (#862).

Jedes Modul (CRA, NIS2, AI-Act, DSGVO, Risikobewertung) speichert sein
GitHub-/GitLab-Repository pro Projekt im Projekt-``meta`` unter ``vcs_publish``.
Das vermeidet eine globale Einstellung und hält Repo + (optionalen) Token
projektgebunden.

Sicherheit:
- Ein eingegebener Token wird at-rest verschlüsselt (``crypto_at_rest``) als
  ``token_enc`` abgelegt und NIE an die API ausgeliefert (nur ein ``has_token``-
  Flag). Fehlt ein Token, wird auf ``token_env`` (Umgebungsvariable) zurück-
  gegriffen — typischerweise ``GH_TOKEN`` / ``GITLAB_TOKEN``.

Diese Funktionen sind bewusst frei von Flask/DB-Abhängigkeiten, damit sie
modulübergreifend und in Tests einfach nutzbar sind. Sie spiegeln das in
``server/api/risikobewertung.py`` etablierte Muster wider.
"""

from __future__ import annotations

import os
from typing import Any

from shared.crypto_at_rest import decrypt_field, encrypt_field

# Erlaubte (unverschlüsselte) Felder der vcs_publish-Struktur.
VCS_FIELDS = ('provider', 'repo', 'base_url', 'branch', 'token_env', 'path')


def vcs_token(vcs: dict[str, Any] | None) -> str | None:
    """Token auflösen: erst entschlüsselter ``token_enc``, sonst ``token_env``→ENV."""
    vcs = vcs or {}
    enc = vcs.get('token_enc')
    if enc:
        try:
            return decrypt_field(str(enc))
        except Exception:
            return None
    env_name = str(vcs.get('token_env') or '').strip()
    if env_name:
        return os.environ.get(env_name)
    return None


def public_vcs(vcs: dict[str, Any] | None) -> dict[str, Any]:
    """vcs_publish ohne Geheimnis: ``token_enc`` raus, ``has_token``-Flag rein."""
    if not isinstance(vcs, dict):
        return {}
    out = {k: v for k, v in vcs.items() if k != 'token_enc'}
    out['has_token'] = bool(vcs.get('token_enc'))
    return out


def sanitize_vcs(raw: Any, existing_vcs: dict[str, Any] | None = None) -> dict[str, Any]:
    """Nur erlaubte vcs_publish-Felder übernehmen; eingehenden Klartext-Token
    verschlüsseln. Bei Partial-Update (kein neuer Token) wird ein bestehender
    ``token_enc`` bewahrt.
    """
    out: dict[str, Any] = {}
    if isinstance(raw, dict):
        for k in VCS_FIELDS:
            if raw.get(k) is not None:
                out[k] = str(raw[k]).strip()
        tok = str(raw.get('token') or '').strip()
        if tok:
            out['token_enc'] = encrypt_field(tok)
        elif existing_vcs and existing_vcs.get('token_enc'):
            out['token_enc'] = existing_vcs['token_enc']
    return out


def resolve_repo(vcs: dict[str, Any] | None, override: str | None = None) -> str:
    """Repo bestimmen: expliziter Override (z.B. aus dem Request) gewinnt,
    sonst das pro Projekt gespeicherte ``vcs_publish.repo``. Leerer String,
    wenn nichts konfiguriert ist."""
    ov = (override or '').strip()
    if ov:
        return ov
    return str((vcs or {}).get('repo') or '').strip()


def vcs_fuer_projekt(module_db: Any, projekt_name: str) -> dict[str, Any]:
    """Die ``vcs_publish``-Konfiguration eines Modulprojekts über seinen Namen.

    #1871: Der projektgebundene Token (#862) wirkte nur beim **Anlegen** von
    Issues — ``token_umgebung`` hatte im ganzen Baum genau einen Aufrufer.
    Jeder lesende Weg (Übernahme, Abgleich, Neubewertung mit Issue-Feedback)
    fiel auf ``GH_TOKEN`` aus dem Prozess-Umfeld zurück. Ein globaler Token ist
    genau **ein** Zugang; eine Installation mit Mandanten in verschiedenen
    GitHub-Organisationen kann ihn nicht setzen.

    Den Token an die acht lesenden Aufrufstellen durchzureichen wäre die
    Spiegel-Liste aus #1731/#1735 — bei der neunten fehlt er wieder. Darum löst
    die Abholung ihn selbst auf: Modul und Projektname liegen dort ohnehin vor.

    Die Zuordnung Modul → Projekt-Tabelle wird **nicht** ein zweites Mal
    geführt, sondern aus ``shared.firmen_link.MODULE_PROJECT_TABLES`` geholt —
    dieselbe Begründung, die dort schon steht.

    Fail-open wie ``projekt_firmen_id``: Ist nichts bestimmbar (Projekt
    unbekannt, Tabelle ohne ``meta_json``, Modul nicht in der Zuordnung),
    kommt ``{}`` zurück und der Aufrufer bleibt beim bisherigen Verhalten.
    """
    import json
    from pathlib import Path

    from shared import db as _sdb
    from shared.firmen_link import MODULE_PROJECT_TABLES

    table, _name_col = MODULE_PROJECT_TABLES.get(Path(module_db).name, (None, None))
    if not table or not str(projekt_name or '').strip():
        return {}
    try:
        con = _sdb.connect(module_db)
        try:
            row = con.execute(
                f"SELECT meta_json FROM {table} WHERE name=? LIMIT 1",  # nosec B608
                (str(projekt_name),)).fetchone()
        finally:
            con.close()
    except Exception:  # noqa: BLE001 — Tabelle ohne meta_json, Modul unbekannt
        return {}
    if not row or not row[0]:
        return {}
    try:
        meta = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
    except Exception:  # noqa: BLE001
        return {}
    vcs = (meta or {}).get('vcs_publish') if isinstance(meta, dict) else None
    return dict(vcs) if isinstance(vcs, dict) else {}
