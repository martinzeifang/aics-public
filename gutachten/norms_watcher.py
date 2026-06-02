"""G0-5 — Living-Norms-Watcher.

Bietet:
- Versions-Tracking je Norm (gutachten_norm_versions)
- Subscriptions: welche Gutachten (audit|gerichts) zitieren welche Norm
- check_updates(): vergleicht aktuelle Version aus normen.json mit DB-Stand
- Notifications-Helper

Hinweis: KEINE externen HTTP-Calls — die Norm-Versionen kommen aus der lokal
gepflegten normen.json. Der Watcher informiert nur über manuelle/scripted Updates.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from gutachten import normen as _normen

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gutachten_norm_versions (
    norm_id     TEXT PRIMARY KEY,
    version     TEXT NOT NULL DEFAULT '',
    checked_at  TEXT NOT NULL DEFAULT (datetime('now')),
    source_url  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS gutachten_norm_subscriptions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    norm_id       TEXT NOT NULL,
    projekt_typ   TEXT NOT NULL,    -- audit|gerichts
    projekt_name  TEXT NOT NULL,
    subscribed_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(norm_id, projekt_typ, projekt_name)
);

CREATE INDEX IF NOT EXISTS idx_norm_sub_norm ON gutachten_norm_subscriptions(norm_id);
CREATE INDEX IF NOT EXISTS idx_norm_sub_projekt ON gutachten_norm_subscriptions(projekt_typ, projekt_name);

CREATE TABLE IF NOT EXISTS gutachten_norm_notifications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    norm_id       TEXT NOT NULL,
    old_version   TEXT NOT NULL DEFAULT '',
    new_version   TEXT NOT NULL DEFAULT '',
    projekt_typ   TEXT NOT NULL,
    projekt_name  TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    acknowledged  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_norm_notif_open ON gutachten_norm_notifications(acknowledged, created_at);
"""


def _ensure(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(_SCHEMA)
        con.commit()
    finally:
        con.close()


def subscribe(db_path: Path, norm_id: str, projekt_typ: str, projekt_name: str) -> None:
    if projekt_typ not in ("audit", "gerichts"):
        raise ValueError("projekt_typ muss 'audit' oder 'gerichts' sein")
    _ensure(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            """INSERT OR IGNORE INTO gutachten_norm_subscriptions
                 (norm_id, projekt_typ, projekt_name) VALUES (?, ?, ?)""",
            (norm_id, projekt_typ, projekt_name),
        )
        con.commit()
    finally:
        con.close()


def unsubscribe(db_path: Path, norm_id: str, projekt_typ: str, projekt_name: str) -> None:
    _ensure(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            """DELETE FROM gutachten_norm_subscriptions
               WHERE norm_id=? AND projekt_typ=? AND projekt_name=?""",
            (norm_id, projekt_typ, projekt_name),
        )
        con.commit()
    finally:
        con.close()


def list_subscriptions(
    db_path: Path,
    norm_id: str | None = None,
    projekt_typ: str | None = None,
    projekt_name: str | None = None,
) -> list[dict[str, Any]]:
    _ensure(db_path)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        where = []
        params: list[Any] = []
        if norm_id:
            where.append("norm_id = ?")
            params.append(norm_id)
        if projekt_typ:
            where.append("projekt_typ = ?")
            params.append(projekt_typ)
        if projekt_name:
            where.append("projekt_name = ?")
            params.append(projekt_name)
        sql = "SELECT * FROM gutachten_norm_subscriptions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY norm_id, projekt_typ, projekt_name"
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def check_updates(db_path: Path) -> list[dict[str, Any]]:
    """Vergleicht aktuelle Norm-Versionen (normen.json) mit DB-Stand.
    Bei Mismatch → Notification-Eintrag pro Subscription, returniert Liste der Updates.
    """
    _ensure(db_path)
    current = {n["id"]: n.get("version", "") for n in _normen.list_normen()}
    updates: list[dict[str, Any]] = []

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        # Vorhandene Versions-Tracker laden
        known = {r["norm_id"]: r["version"] for r in con.execute(
            "SELECT norm_id, version FROM gutachten_norm_versions"
        ).fetchall()}

        for norm_id, new_version in current.items():
            old_version = known.get(norm_id)
            if old_version is None:
                # Erst-Erfassung — kein Update, nur eintragen
                con.execute(
                    """INSERT INTO gutachten_norm_versions (norm_id, version)
                       VALUES (?, ?)
                       ON CONFLICT(norm_id) DO UPDATE SET version=excluded.version,
                                                          checked_at=datetime('now')""",
                    (norm_id, new_version),
                )
                continue
            if old_version != new_version:
                # Update — alle Subscriptions benachrichtigen
                subs = con.execute(
                    "SELECT projekt_typ, projekt_name FROM gutachten_norm_subscriptions WHERE norm_id=?",
                    (norm_id,),
                ).fetchall()
                for sub in subs:
                    con.execute(
                        """INSERT INTO gutachten_norm_notifications
                             (norm_id, old_version, new_version, projekt_typ, projekt_name)
                           VALUES (?, ?, ?, ?, ?)""",
                        (norm_id, old_version, new_version, sub["projekt_typ"], sub["projekt_name"]),
                    )
                con.execute(
                    """UPDATE gutachten_norm_versions
                       SET version=?, checked_at=datetime('now')
                       WHERE norm_id=?""",
                    (new_version, norm_id),
                )
                updates.append({
                    "norm_id": norm_id,
                    "old_version": old_version,
                    "new_version": new_version,
                    "notifications_created": len(subs),
                })
        con.commit()
    finally:
        con.close()
    return updates


def list_notifications(db_path: Path, only_open: bool = True) -> list[dict[str, Any]]:
    _ensure(db_path)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        sql = "SELECT * FROM gutachten_norm_notifications"
        if only_open:
            sql += " WHERE acknowledged = 0"
        sql += " ORDER BY created_at DESC"
        return [dict(r) for r in con.execute(sql).fetchall()]
    finally:
        con.close()


def acknowledge_notification(db_path: Path, notif_id: int) -> None:
    _ensure(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "UPDATE gutachten_norm_notifications SET acknowledged=1 WHERE id=?",
            (notif_id,),
        )
        con.commit()
    finally:
        con.close()
