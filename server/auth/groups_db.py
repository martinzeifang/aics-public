"""Benutzergruppen mit Berechtigungen (#1779).

Rechte hingen bis v8.0.3 an jedem Konto einzeln: Rollen, ``extra_permissions``,
``allowed_modules`` und ``allowed_firmen`` stehen in ``users``. Bei mehr als
einer Handvoll Konten heißt das, dieselbe Rechte-Entscheidung mehrfach zu
treffen — und bei einer Änderung jedes Konto nachzuziehen. Was fehlte, ist die
Stelle, an der eine Rechte-Entscheidung **einmal** steht.

ADDITIV, NICHT EINSCHRÄNKEND
Eine Gruppe trägt **Rollen und Einzelberechtigungen**, aber keine
``allowed_modules``/``allowed_firmen``. Das ist eine Entscheidung, nicht ein
fehlendes Stück: Whitelists sind *Beschränkungen*, die sich schneiden müssten,
während Rollen sich vereinigen. Beides in einem Mechanismus zu mischen ist
genau die Stelle, an der RBAC-Fehler entstehen — eine Gruppe, die den Zugriff
auf zwei Mandanten begrenzen soll, würde ein Konto ohne Whitelist nicht
begrenzen, sondern alles offen lassen. ``resolve_permissions`` ist bereits rein
additiv; die Gruppen setzen davor an, nicht daneben.

RECHTEÄNDERUNG WIRKT SOFORT
Berechtigungen stehen im JWT (``build_login_response``), nicht in einer Abfrage
je Request. Eine Änderung an der Gruppe oder an der Mitgliedschaft muss deshalb
die ``token_version`` der betroffenen Konten erhöhen (#738) — die Mitglieder
melden sich neu an. Das ist die Absicht: Ein entzogenes Recht, das bis zum
Ablauf des Tokens weitergilt, ist in einem Nachweiswerkzeug schlechter als ein
Logout.

DIE GRUPPE SCHREIBT NICHTS IN DAS KONTO
``effektiv()`` liefert eine **Kopie**; die eigenen Rollen des Kontos bleiben
unberührt. Würde die Auflösung in den Datensatz zurückschreiben, blieben
Gruppen-Rollen beim Verlassen der Gruppe stehen — und niemand könnte später
sagen, woher ein Recht kam.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from shared import db as _sdb

from server.auth.users_db import DEFAULT_DB_PATH

log = logging.getLogger(__name__)

_ENSURED: set[str] = set()


def _connect(db_path: Path = DEFAULT_DB_PATH) -> Any:
    return _sdb.connect(db_path)


def ensure_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Tabellen anlegen (idempotent, je Pfad einmal).

    Gleicher Cache-Gedanke wie in ``users_db.ensure_db``: Die Auflösung läuft
    bei jeder Anmeldung und bei jeder Benutzerliste.
    """
    key = str(db_path)
    if key in _ENSURED:
        return
    con = _connect(db_path)
    try:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS user_groups (
            id                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name                   TEXT NOT NULL UNIQUE,
            beschreibung           TEXT NOT NULL DEFAULT '',
            roles_json             TEXT NOT NULL DEFAULT '[]',
            extra_permissions_json TEXT NOT NULL DEFAULT '[]',
            active                 INTEGER NOT NULL DEFAULT 1,
            created_at             TEXT DEFAULT aics_now(),
            updated_at             TEXT DEFAULT aics_now()
        );
        CREATE TABLE IF NOT EXISTS user_group_members (
            group_id   BIGINT NOT NULL,
            user_id    TEXT NOT NULL,
            created_at TEXT DEFAULT aics_now(),
            PRIMARY KEY (group_id, user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_group_members_user
            ON user_group_members(user_id);
        """)
        con.commit()
        _ENSURED.add(key)
    finally:
        con.close()


def _liste(roh: Any) -> list[str]:
    """JSON-Spalte zu einer Liste von Zeichenketten — nie ``None``."""
    if isinstance(roh, list):
        werte = roh
    else:
        try:
            werte = json.loads(roh or "[]")
        except (TypeError, ValueError):
            return []
    if not isinstance(werte, list):
        return []
    return [str(w).strip() for w in werte if str(w).strip()]


def _row_to_group(row: Any) -> dict[str, Any]:
    d = dict(row)
    return {
        "id": int(d["id"]),
        "name": str(d.get("name") or ""),
        "beschreibung": str(d.get("beschreibung") or ""),
        "roles": _liste(d.get("roles_json")),
        "extra_permissions": _liste(d.get("extra_permissions_json")),
        "active": bool(d.get("active", 1)),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }


# ── Lesen ───────────────────────────────────────────────────────────────────

def list_groups(db_path: Path = DEFAULT_DB_PATH, *,
                include_inactive: bool = True) -> list[dict[str, Any]]:
    """Alle Gruppen mit Mitgliederzahl — **eine** Abfrage je Teil (kein N+1)."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        q = "SELECT * FROM user_groups"
        if not include_inactive:
            q += " WHERE active=1"
        q += " ORDER BY name"
        gruppen = [_row_to_group(r) for r in con.execute(q).fetchall()]
        zaehler: dict[int, int] = {}
        for r in con.execute(
                "SELECT group_id, COUNT(*) AS n FROM user_group_members "
                "GROUP BY group_id").fetchall():
            zaehler[int(r[0])] = int(r[1])
        for g in gruppen:
            g["mitglieder_count"] = zaehler.get(g["id"], 0)
        return gruppen
    finally:
        con.close()


def get_group(group_id: int, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM user_groups WHERE id=?",
                          (int(group_id),)).fetchone()
        if row is None:
            return None
        g = _row_to_group(row)
        g["mitglieder"] = [str(r[0]) for r in con.execute(
            "SELECT user_id FROM user_group_members WHERE group_id=? ORDER BY user_id",
            (int(group_id),)).fetchall()]
        g["mitglieder_count"] = len(g["mitglieder"])
        return g
    finally:
        con.close()


def get_group_by_name(name: str, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        row = con.execute("SELECT * FROM user_groups WHERE name=?",
                          (str(name or "").strip(),)).fetchone()
        return _row_to_group(row) if row is not None else None
    finally:
        con.close()


def members(group_id: int, db_path: Path = DEFAULT_DB_PATH) -> list[str]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        return [str(r[0]) for r in con.execute(
            "SELECT user_id FROM user_group_members WHERE group_id=?",
            (int(group_id),)).fetchall()]
    finally:
        con.close()


def groups_for_user(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    """Gruppen eines Kontos (nur aktive — eine stillgelegte Gruppe gibt nichts)."""
    if not str(user_id or "").strip():
        return []
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            """SELECT g.* FROM user_groups g
               JOIN user_group_members m ON m.group_id = g.id
               WHERE m.user_id=? AND g.active=1
               ORDER BY g.name""", (str(user_id),)).fetchall()
        return [_row_to_group(r) for r in rows]
    finally:
        con.close()


def groups_for_users(user_ids: list[str],
                     db_path: Path = DEFAULT_DB_PATH) -> dict[str, list[dict[str, Any]]]:
    """Gruppen für viele Konten in **einer** Abfrage.

    Die Benutzerliste im Admin-UI zeigt alle Konten; je Konto zu fragen wären
    bei 50 Benutzern 50 Abfragen (die Fehlerklasse aus #1703/S6).
    """
    ids = {str(u) for u in (user_ids or []) if str(u or "").strip()}
    if not ids:
        return {}
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        # Feste Abfrage statt einer ``IN``-Liste aus Platzhaltern: Die Zahl der
        # Mitgliedschaften ist durch Konten × Gruppen begrenzt und damit klein,
        # und der einzige Aufrufer (Benutzerliste im Admin) braucht ohnehin
        # alle. Dafür steht hier kein zusammengesetztes SQL — die Prüfung soll
        # nicht jedes Mal entscheiden müssen, ob die Platzhalter wirklich aus
        # dem Code und nicht aus den Daten kommen.
        rows = con.execute(
            """SELECT m.user_id AS uid, g.* FROM user_groups g
               JOIN user_group_members m ON m.group_id = g.id
               WHERE g.active=1
               ORDER BY g.name""").fetchall()
        out: dict[str, list[dict[str, Any]]] = {u: [] for u in ids}
        for r in rows:
            d = dict(r)
            uid = str(d["uid"])
            if uid in ids:
                out[uid].append(_row_to_group(d))
        return out
    finally:
        con.close()


# ── Schreiben ───────────────────────────────────────────────────────────────

def create_group(name: str, *, beschreibung: str = "", roles: list[str] | None = None,
                 extra_permissions: list[str] | None = None, active: bool = True,
                 db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    name = str(name or "").strip()
    if not name:
        raise ValueError("Der Name der Gruppe ist Pflicht")
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            """INSERT INTO user_groups
                 (name, beschreibung, roles_json, extra_permissions_json, active)
               VALUES (?,?,?,?,?) RETURNING id""",
            (name, str(beschreibung or ""),
             json.dumps(_liste(roles), ensure_ascii=False),
             json.dumps(_liste(extra_permissions), ensure_ascii=False),
             1 if active else 0))
        gid = int((cur.fetchone() or [0])[0] or cur.lastrowid or 0)
        con.commit()
    finally:
        con.close()
    erg = get_group(gid, db_path)
    assert erg is not None
    return erg


def update_group(group_id: int, db_path: Path = DEFAULT_DB_PATH,
                 **felder: Any) -> dict[str, Any] | None:
    """Gruppe ändern. Nur übergebene Felder werden angefasst."""
    ensure_db(db_path)
    name: str | None = None
    if "name" in felder:
        name = str(felder["name"] or "").strip()
        if not name:
            raise ValueError("Der Name der Gruppe ist Pflicht")
    if not any(k in felder for k in
               ("name", "beschreibung", "roles", "extra_permissions", "active")):
        return get_group(group_id, db_path)
    # Feste Anweisung mit COALESCE statt zusammengesetztem SET: ``NULL`` heißt
    # „nicht übergeben, Wert behalten" (Muster aus ``cra.db.save_sbom``, #1771).
    # Ein zusammengebautes SQL wäre hier zwar aus eigenen Zeichenketten gebaut,
    # aber von einem zusammengebauten aus Eingaben nicht mehr zu unterscheiden.
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE user_groups SET
                 name                   = COALESCE(?, name),
                 beschreibung           = COALESCE(?, beschreibung),
                 roles_json             = COALESCE(?, roles_json),
                 extra_permissions_json = COALESCE(?, extra_permissions_json),
                 active                 = COALESCE(?, active),
                 updated_at             = aics_now()
               WHERE id=?""",
            (name,
             str(felder["beschreibung"] or "") if "beschreibung" in felder else None,
             json.dumps(_liste(felder["roles"]), ensure_ascii=False)
             if "roles" in felder else None,
             json.dumps(_liste(felder["extra_permissions"]), ensure_ascii=False)
             if "extra_permissions" in felder else None,
             (1 if felder["active"] else 0) if "active" in felder else None,
             int(group_id)))
        con.commit()
    finally:
        con.close()
    return get_group(group_id, db_path)


def delete_group(group_id: int, db_path: Path = DEFAULT_DB_PATH) -> bool:
    """Gruppe löschen — die Mitgliedschaften gehen mit, die Konten bleiben.

    Es gibt bewusst kein Soft-Delete: Eine Gruppe ist kein Nachweisdokument,
    sondern eine Rechte-Zuordnung. Wer sie behalten, aber abschalten will,
    setzt ``active=0``; dann wirken ihre Rechte nicht mehr und die
    Mitgliederliste bleibt lesbar.
    """
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM user_group_members WHERE group_id=?", (int(group_id),))
        cur = con.execute("DELETE FROM user_groups WHERE id=?", (int(group_id),))
        con.commit()
        return bool(getattr(cur, "rowcount", 0))
    finally:
        con.close()


def add_member(group_id: int, user_id: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    """Konto in die Gruppe aufnehmen (idempotent)."""
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            "INSERT INTO user_group_members(group_id, user_id) VALUES (?,?) "
            "ON CONFLICT (group_id, user_id) DO NOTHING",
            (int(group_id), str(user_id)))
        con.commit()
        return True
    finally:
        con.close()


def remove_member(group_id: int, user_id: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            "DELETE FROM user_group_members WHERE group_id=? AND user_id=?",
            (int(group_id), str(user_id)))
        con.commit()
        return bool(getattr(cur, "rowcount", 0))
    finally:
        con.close()


def set_groups_for_user(user_id: str, group_ids: list[int],
                        db_path: Path = DEFAULT_DB_PATH) -> list[int]:
    """Gruppen eines Kontos setzen; liefert die Gruppen, die sich geändert haben."""
    ensure_db(db_path)
    ziel = {int(g) for g in (group_ids or []) if str(g).strip()}
    con = _connect(db_path)
    try:
        vorher = {int(r[0]) for r in con.execute(
            "SELECT group_id FROM user_group_members WHERE user_id=?",
            (str(user_id),)).fetchall()}
        for gid in ziel - vorher:
            con.execute(
                "INSERT INTO user_group_members(group_id, user_id) VALUES (?,?) "
                "ON CONFLICT (group_id, user_id) DO NOTHING", (gid, str(user_id)))
        for gid in vorher - ziel:
            con.execute(
                "DELETE FROM user_group_members WHERE group_id=? AND user_id=?",
                (gid, str(user_id)))
        con.commit()
        return sorted((ziel - vorher) | (vorher - ziel))
    finally:
        con.close()


# ── Auflösung ───────────────────────────────────────────────────────────────

def effektiv(user: dict[str, Any], db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    """Konto **plus** Gruppenrechte — als Kopie (siehe Modul-Docstring).

    ``roles``/``extra_permissions`` enthalten danach die Vereinigung, und
    ``gruppen`` sagt, woher die Zusätze kommen. Fällt die Auflösung aus, kommt
    das Konto unverändert zurück: Ein Fehler im Gruppen-Register darf keine
    Anmeldung verhindern — aber er darf auch keine Rechte erfinden.
    """
    out = dict(user or {})
    out.setdefault("roles", [])
    out.setdefault("extra_permissions", [])
    try:
        gruppen = groups_for_user(str(out.get("id") or ""), db_path)
    except Exception:  # noqa: BLE001
        log.warning("Gruppen konnten nicht aufgelöst werden", exc_info=True)
        out["gruppen"] = []
        return out
    return _mischen(out, gruppen)


def _mischen(user: dict[str, Any], gruppen: list[dict[str, Any]]) -> dict[str, Any]:
    """Vereinigung bilden und die Herkunft mitführen (reine Funktion)."""
    out = dict(user)
    eigene_rollen = _liste(out.get("roles"))
    eigene_perms = _liste(out.get("extra_permissions"))
    rollen = list(eigene_rollen)
    perms = list(eigene_perms)
    for g in gruppen:
        for r in g.get("roles") or []:
            if r not in rollen:
                rollen.append(r)
        for p in g.get("extra_permissions") or []:
            if p not in perms:
                perms.append(p)
    out["roles"] = rollen
    out["extra_permissions"] = perms
    out["eigene_rollen"] = eigene_rollen
    out["eigene_permissions"] = eigene_perms
    out["gruppen"] = [{"id": g["id"], "name": g["name"],
                       "roles": list(g.get("roles") or []),
                       "extra_permissions": list(g.get("extra_permissions") or [])}
                      for g in gruppen]
    return out


def effektiv_viele(users: list[dict[str, Any]],
                   db_path: Path = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    """Wie :func:`effektiv` für eine ganze Liste — eine Abfrage für alle."""
    try:
        karte = groups_for_users([str(u.get("id") or "") for u in users], db_path)
    except Exception:  # noqa: BLE001
        log.warning("Gruppen konnten nicht aufgelöst werden", exc_info=True)
        karte = {}
    return [_mischen(u, karte.get(str(u.get("id") or ""), [])) for u in users]


def tokens_invalidieren(user_ids: list[str], db_path: Path = DEFAULT_DB_PATH) -> int:
    """``token_version`` der betroffenen Konten erhöhen (#738).

    Siehe Modul-Docstring: Ohne diesen Schritt wirkt eine Rechteänderung erst
    beim Ablauf des Tokens — bei entzogenen Rechten die falsche Richtung.
    """
    from server.auth.users_db import bump_token_version

    n = 0
    for uid in {str(u) for u in (user_ids or []) if str(u or "").strip()}:
        try:
            bump_token_version(uid, db_path)
            n += 1
        except Exception:  # noqa: BLE001 — ein fehlendes Konto darf nicht blockieren
            log.warning("token_version für %s nicht erhöht", uid, exc_info=True)
    return n
