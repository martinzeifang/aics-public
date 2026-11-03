"""CRA Art. 52-56 — Register der Marktüberwachungsvorgänge (#1762).

WAS HIER FEHLTE
``cra/korrektur_db.py`` deckt den Fall ab, in dem **der Hersteller** aktiv wird:
Er stellt eine Nicht-Konformität fest, ergreift Korrekturmaßnahmen, nimmt vom
Markt, ruft zurück und informiert die Behörde. Der umgekehrte Fall hatte keinen
Ort: Die **Behörde** wird aktiv, verlangt Unterlagen (Art. 52), ordnet
Maßnahmen an (Art. 53/54), setzt eine Frist. Diese Vorgänge landeten bisher in
Postfächern.

Drei Dinge brauchen deshalb einen Platz, und zwar vor dem ersten Vorgang und
nicht während:

1. **Die Frist der Behörde.** Sie ist kurz, sie läuft, und sie ist das einzige
   Datum in diesem Modul, dessen Versäumnis eine Pflichtverletzung ist (anders
   als die endenden Pflichten aus Art. 13, siehe ``cra/fristenuhr.py``).
2. **Die bereitgestellten Unterlagen.** Was die Behörde bekommen hat, ist
   später die einzige Antwort auf „was haben Sie vorgelegt?". Deshalb ist
   ``beantwortet`` ohne Unterlage oder Ergebnis nicht speicherbar: Ein Haken,
   hinter dem nichts steht, ist schlimmer als ein offener Vorgang — er beendet
   das Nachfragen.
3. **Das Aktenzeichen der Behörde.** Ohne es ist der Vorgang in jedem
   Schriftwechsel neu zu suchen.

Tabelle ``cra_marktaufsicht`` (projekt-scoped, in ``PROJEKT_TABELLEN``
eingetragen). Reiner Kompat-Layer (``shared.db``), ``ensure_table`` idempotent.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from shared import db as _sdb

from cra import fristenuhr

DB_PATH = Path("data/db/cra.sqlite")

#: Vorgangsarten. Die Bezeichnungen sind absichtlich die des Verwaltungswegs und
#: nicht nach Absätzen sortiert: Welcher Artikel eine Anordnung trägt, hängt am
#: Fall (Art. 53 bei Risiko trotz Konformität, Art. 54 bei formaler
#: Nicht-Konformität). Die Zuordnung gehört in den Vorgang, nicht in das Schema.
VORGANGSARTEN = (
    "auskunftsverlangen",     # Unterlagen/Informationen werden verlangt (Art. 52)
    "pruefung",               # Produktprüfung / Marktkontrolle
    "anordnung",              # verbindliche Anordnung (Art. 53/54)
    "korrekturverlangen",     # Abhilfe wird verlangt
    "marktbeschraenkung",     # Rücknahme-/Bereitstellungsverbot
    "sonstiges",
)

#: Bearbeitungsstand. Nur diese fünf — ein Freitextstatus wäre in einem Register,
#: das eine Frist überwacht, kein Status.
STATUS = ("offen", "in_bearbeitung", "beantwortet", "abgeschlossen", "eingestellt")

#: Mindestlänge des Ergebnistexts, wenn keine Unterlage hinterlegt ist.
ERGEBNIS_MIN_ZEICHEN = 10


def _connect(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer (#1332)."""
    return _sdb.connect(db_path)


def ensure_table(db_path: Path = DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS cra_marktaufsicht (
                id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                projekt_name    TEXT NOT NULL,
                vorgangsart     TEXT NOT NULL DEFAULT 'auskunftsverlangen',
                behoerde_name   TEXT NOT NULL DEFAULT '',
                behoerde_land   TEXT NOT NULL DEFAULT '',   -- Mitgliedstaat
                aktenzeichen    TEXT NOT NULL DEFAULT '',   -- Zeichen der Behörde
                eingang_am      TEXT,                       -- Zugang des Schreibens
                frist_am        TEXT,                       -- von der Behörde gesetzte Frist
                gegenstand      TEXT NOT NULL DEFAULT '',
                verlangen       TEXT NOT NULL DEFAULT '',   -- was gefordert wird
                betroffene_versionen TEXT NOT NULL DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'offen',
                beantwortet_am  TEXT,
                unterlagen_json TEXT NOT NULL DEFAULT '[]', -- [{titel, ref, uebergeben_am}]
                ergebnis        TEXT NOT NULL DEFAULT '',
                notizen         TEXT NOT NULL DEFAULT '',
                audit_json      TEXT NOT NULL DEFAULT '[]',
                created_at      TEXT DEFAULT (aics_now()),
                updated_at      TEXT DEFAULT (aics_now())
            );
            CREATE INDEX IF NOT EXISTS idx_cra_marktaufsicht_projekt
                ON cra_marktaufsicht(projekt_name);
            CREATE INDEX IF NOT EXISTS idx_cra_marktaufsicht_frist
                ON cra_marktaufsicht(projekt_name, status, frist_am);
            """
        )
        con.commit()
    finally:
        con.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


#: Stände, in denen die Frist noch gegen den Hersteller läuft.
_LAUFEND = ("offen", "in_bearbeitung")


def _row(r: Any, *, heute: Optional[date] = None) -> dict[str, Any]:
    d = dict(r)
    try:
        d["unterlagen"] = json.loads(d.get("unterlagen_json") or "[]")
    except Exception:  # noqa: BLE001
        d["unterlagen"] = []
    try:
        d["audit_trail"] = json.loads(d.get("audit_json") or "[]")
    except Exception:  # noqa: BLE001
        d["audit_trail"] = []
    d["frist"] = fristenuhr.behoerdenfrist(d.get("frist_am"), heute=heute)
    # Eine verstrichene Frist ist nur dann ein Versäumnis, wenn der Vorgang noch
    # läuft. Nach „beantwortet" interessiert das Datum als Historie, nicht als
    # Mahnung — sonst zeigt das Register dauerhaft Rot für erledigte Vorgänge.
    d["frist_versaeumt"] = bool(d["frist"]["verstrichen"]
                                and str(d.get("status") or "") in _LAUFEND)
    return d


def _pruefe_datum(wert: Any, feld: str) -> Optional[str]:
    """ISO-Datum oder ``ValueError``. Leer bleibt leer."""
    s = str(wert or "").strip()
    if not s:
        return None
    if fristenuhr.parse_datum(s) is None:
        raise ValueError(
            f"{feld}: '{s}' ist kein Datum. Fristen werden als JJJJ-MM-TT erfasst — "
            "aus einer Umschreibung lässt sich kein Fristenlauf rechnen.")
    return s[:10]


def _pruefe_stammdaten(data: dict, *, bestand: Optional[dict] = None) -> None:
    art = data.get("vorgangsart", (bestand or {}).get("vorgangsart") or "auskunftsverlangen")
    if art not in VORGANGSARTEN:
        raise ValueError(f"Unbekannte Vorgangsart: {art}")
    status = data.get("status", (bestand or {}).get("status") or "offen")
    if status not in STATUS:
        raise ValueError(f"Unbekannter Status: {status}")
    name = str(data.get("behoerde_name", (bestand or {}).get("behoerde_name") or "")).strip()
    if not name:
        raise ValueError(
            "Behörde fehlt: Ein Vorgang der Marktüberwachung ohne Behörde lässt "
            "sich nicht beantworten und in keinem Schriftwechsel wiederfinden.")


def _pruefe_antwort(status: str, unterlagen: list, ergebnis: str) -> None:
    """``beantwortet``/``abgeschlossen`` verlangt einen Beleg.

    Serverseitig, nicht nur im Formular: Der Haken „beantwortet" beendet die
    Fristüberwachung dieses Vorgangs. Was ihn trägt, muss im Register stehen —
    entweder die vorgelegten Unterlagen oder, wenn nichts vorzulegen war, ein
    Satz, was der Behörde mitgeteilt wurde.
    """
    if status not in ("beantwortet", "abgeschlossen"):
        return
    if unterlagen:
        return
    if len(str(ergebnis or "").strip()) >= ERGEBNIS_MIN_ZEICHEN:
        return
    raise ValueError(
        "Für den Stand „beantwortet“ fehlt der Beleg: Mindestens eine "
        "bereitgestellte Unterlage erfassen — oder im Feld Ergebnis festhalten, "
        f"was der Behörde mitgeteilt wurde (mindestens {ERGEBNIS_MIN_ZEICHEN} "
        "Zeichen). Ohne das ist die Frist als erledigt markiert, ohne dass "
        "nachvollziehbar wäre, womit.")


def list_vorgaenge(db_path: Path, projekt_name: str,
                   *, heute: Optional[date] = None) -> list[dict[str, Any]]:
    """Vorgänge eines Projekts — laufende mit der dringendsten Frist zuerst."""
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM cra_marktaufsicht WHERE projekt_name=? "
            "ORDER BY created_at DESC, id DESC",
            (projekt_name,),
        ).fetchall()
    finally:
        con.close()
    vorgaenge = [_row(r, heute=heute) for r in rows]
    # Laufend vor erledigt, innerhalb davon nach Frist (ohne Frist ans Ende).
    def _schluessel(v: dict[str, Any]) -> tuple:
        laufend = 0 if str(v.get("status")) in _LAUFEND else 1
        tage = v["frist"]["tage_verbleibend"]
        return (laufend, 0 if tage is not None else 1, tage if tage is not None else 0)
    return sorted(vorgaenge, key=_schluessel)


def get_vorgang(db_path: Path, vorgang_id: int,
                projekt_name: Optional[str] = None) -> Optional[dict[str, Any]]:
    """IDOR-sicher: optional auf ``projekt_name`` scopen."""
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        if projekt_name is not None:
            r = con.execute(
                "SELECT * FROM cra_marktaufsicht WHERE id=? AND projekt_name=?",
                (vorgang_id, projekt_name),
            ).fetchone()
        else:
            r = con.execute("SELECT * FROM cra_marktaufsicht WHERE id=?",
                            (vorgang_id,)).fetchone()
        return _row(r) if r else None
    finally:
        con.close()


def _append_audit(con: Any, vorgang_id: int, projekt_name: str,
                  event: str, **extra: Any) -> None:
    r = con.execute(
        "SELECT audit_json FROM cra_marktaufsicht WHERE id=? AND projekt_name=?",
        (vorgang_id, projekt_name),
    ).fetchone()
    if not r:
        return
    try:
        trail = json.loads(r["audit_json"] or "[]")
    except Exception:  # noqa: BLE001
        trail = []
    trail.append({"event": event, "ts": _now_iso(), **extra})
    con.execute(
        "UPDATE cra_marktaufsicht SET audit_json=? WHERE id=? AND projekt_name=?",
        (json.dumps(trail, ensure_ascii=False), vorgang_id, projekt_name),
    )


def create_vorgang(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_table(db_path)
    _pruefe_stammdaten(data)
    eingang = _pruefe_datum(data.get("eingang_am"), "Eingang")
    frist = _pruefe_datum(data.get("frist_am"), "Frist")
    unterlagen = data.get("unterlagen") or []
    status = data.get("status") or "offen"
    _pruefe_antwort(status, unterlagen, data.get("ergebnis", ""))
    con = _connect(db_path)
    try:
        cur = con.execute(
            """
            INSERT INTO cra_marktaufsicht
                (projekt_name, vorgangsart, behoerde_name, behoerde_land, aktenzeichen,
                 eingang_am, frist_am, gegenstand, verlangen, betroffene_versionen,
                 status, beantwortet_am, unterlagen_json, ergebnis, notizen, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,aics_now())
            """,
            (projekt_name, data.get("vorgangsart") or "auskunftsverlangen",
             str(data.get("behoerde_name", "")).strip(), data.get("behoerde_land", ""),
             data.get("aktenzeichen", ""), eingang, frist,
             data.get("gegenstand", ""), data.get("verlangen", ""),
             data.get("betroffene_versionen", ""), status,
             _pruefe_datum(data.get("beantwortet_am"), "Beantwortet am"),
             json.dumps(unterlagen, ensure_ascii=False),
             data.get("ergebnis", ""), data.get("notizen", "")),
        )
        pk = int(cur.lastrowid)
        _append_audit(con, pk, projekt_name, "angelegt",
                      vorgangsart=data.get("vorgangsart") or "auskunftsverlangen",
                      frist_am=frist)
        con.commit()
        return pk
    finally:
        con.close()


_UPDATE_FELDER = ("vorgangsart", "behoerde_name", "behoerde_land", "aktenzeichen",
                  "gegenstand", "verlangen", "betroffene_versionen", "ergebnis",
                  "notizen")


def update_vorgang(db_path: Path, vorgang_id: int, projekt_name: str,
                   data: dict) -> Optional[dict[str, Any]]:
    ensure_table(db_path)
    bestand = get_vorgang(db_path, vorgang_id, projekt_name)
    if not bestand:
        return None
    _pruefe_stammdaten(data, bestand=bestand)
    if "status" in data:
        _pruefe_antwort(str(data["status"]),
                        data.get("unterlagen", bestand.get("unterlagen") or []),
                        data.get("ergebnis", bestand.get("ergebnis") or ""))
    sets, vals = [], []
    for f in _UPDATE_FELDER:
        if f in data:
            sets.append(f"{f}=?")
            vals.append(data[f])
    for f, label in (("eingang_am", "Eingang"), ("frist_am", "Frist"),
                     ("beantwortet_am", "Beantwortet am")):
        if f in data:
            sets.append(f"{f}=?")
            vals.append(_pruefe_datum(data[f], label))
    if "status" in data:
        sets.append("status=?")
        vals.append(data["status"])
    if "unterlagen" in data:
        sets.append("unterlagen_json=?")
        vals.append(json.dumps(data.get("unterlagen") or [], ensure_ascii=False))
    if not sets:
        return bestand
    vals += [vorgang_id, projekt_name]
    con = _connect(db_path)
    try:
        cur = con.execute(
            f"UPDATE cra_marktaufsicht SET {', '.join(sets)}, updated_at=aics_now() "
            "WHERE id=? AND projekt_name=?", vals)
        if cur.rowcount == 0:
            return None
        _append_audit(con, vorgang_id, projekt_name, "geaendert",
                      felder=sorted(set(data) & (set(_UPDATE_FELDER) | {
                          "eingang_am", "frist_am", "beantwortet_am", "status",
                          "unterlagen"})))
        con.commit()
    finally:
        con.close()
    return get_vorgang(db_path, vorgang_id, projekt_name)


def set_status(db_path: Path, vorgang_id: int, projekt_name: str,
               status: str) -> Optional[dict[str, Any]]:
    """Stand wechseln. ``beantwortet``/``abgeschlossen`` stempeln das Datum.

    Der Beleg-Zwang aus ``_pruefe_antwort`` greift auch hier — sonst wäre der
    Statuswechsel der Weg um die Prüfung herum.
    """
    ensure_table(db_path)
    if status not in STATUS:
        raise ValueError(f"Unbekannter Status: {status}")
    bestand = get_vorgang(db_path, vorgang_id, projekt_name)
    if not bestand:
        return None
    _pruefe_antwort(status, bestand.get("unterlagen") or [],
                    bestand.get("ergebnis") or "")
    stempel = (bestand.get("beantwortet_am") or date.today().isoformat()) \
        if status in ("beantwortet", "abgeschlossen") else bestand.get("beantwortet_am")
    con = _connect(db_path)
    try:
        con.execute(
            "UPDATE cra_marktaufsicht SET status=?, beantwortet_am=?, "
            "updated_at=aics_now() WHERE id=? AND projekt_name=?",
            (status, stempel, vorgang_id, projekt_name))
        _append_audit(con, vorgang_id, projekt_name, "status_gewechselt",
                      von=bestand.get("status"), nach=status)
        con.commit()
    finally:
        con.close()
    return get_vorgang(db_path, vorgang_id, projekt_name)


def add_unterlage(db_path: Path, vorgang_id: int, projekt_name: str,
                  titel: str, *, ref: str = "",
                  uebergeben_am: str = "") -> Optional[dict[str, Any]]:
    """Eine der Behörde bereitgestellte Unterlage festhalten."""
    ensure_table(db_path)
    titel = str(titel or "").strip()
    if not titel:
        raise ValueError("Die Unterlage braucht eine Bezeichnung — „Anlage 1“ "
                         "allein ist später nicht wiederzufinden.")
    bestand = get_vorgang(db_path, vorgang_id, projekt_name)
    if not bestand:
        return None
    eintrag = {"titel": titel, "ref": str(ref or "").strip(),
               "uebergeben_am": _pruefe_datum(uebergeben_am, "Übergeben am")
               or date.today().isoformat()}
    unterlagen = list(bestand.get("unterlagen") or []) + [eintrag]
    con = _connect(db_path)
    try:
        con.execute(
            "UPDATE cra_marktaufsicht SET unterlagen_json=?, updated_at=aics_now() "
            "WHERE id=? AND projekt_name=?",
            (json.dumps(unterlagen, ensure_ascii=False), vorgang_id, projekt_name))
        _append_audit(con, vorgang_id, projekt_name, "unterlage_bereitgestellt",
                      titel=titel)
        con.commit()
    finally:
        con.close()
    return get_vorgang(db_path, vorgang_id, projekt_name)


def delete_vorgang(db_path: Path, vorgang_id: int, projekt_name: str) -> bool:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            "DELETE FROM cra_marktaufsicht WHERE id=? AND projekt_name=?",
            (vorgang_id, projekt_name))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def uebersicht(db_path: Path, projekt_name: str,
               *, heute: Optional[date] = None) -> dict[str, Any]:
    """Kennzahlen für Panel und Gate: offen, versäumt, nächste Frist."""
    vorgaenge = list_vorgaenge(db_path, projekt_name, heute=heute)
    laufend = [v for v in vorgaenge if str(v.get("status")) in _LAUFEND]
    versaeumt = [v for v in laufend if v["frist_versaeumt"]]
    mit_frist = [v for v in laufend
                 if v["frist"]["datum"] and not v["frist_versaeumt"]]
    naechste = min(mit_frist, key=lambda v: v["frist"]["datum"]) if mit_frist else None
    ampeln = [v["frist"]["ampel"] for v in laufend if v["frist"]["datum"]]
    return {
        "gesamt": len(vorgaenge),
        "laufend": len(laufend),
        "versaeumt": len(versaeumt),
        "versaeumte_vorgaenge": [
            {"id": v["id"], "aktenzeichen": v.get("aktenzeichen"),
             "behoerde_name": v.get("behoerde_name"), "vorgangsart": v.get("vorgangsart"),
             "frist_am": v["frist"]["datum"],
             "tage_ueberschritten": -(v["frist"]["tage_verbleibend"] or 0)}
            for v in versaeumt],
        "naechste_frist": ({"id": naechste["id"], "frist_am": naechste["frist"]["datum"],
                            "tage_verbleibend": naechste["frist"]["tage_verbleibend"],
                            "behoerde_name": naechste.get("behoerde_name")}
                           if naechste else None),
        "schlechteste_ampel": fristenuhr.schlechteste_ampel(ampeln),
    }
