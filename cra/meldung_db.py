"""CRA Art. 14 — Melde-Register (#1192) + Nutzer-Advisory (#1209).

Gestufter Melde-Workflow für aktiv ausgenutzte Schwachstellen UND schwerwiegende
Sicherheitsvorfälle (ENISA Single Reporting Platform). Lifecycle:
``erkannt → early_warning_24h → notification_72h → final_report``.

Tabelle ``cra_meldung`` (projekt-scoped, optionaler FK auf ``cra_vuln.id``).
Reines ``sqlite3``, kein ORM. ``ensure_table`` idempotent.

Empfänger je Stufe (#1760): Art. 14 verlangt die Meldung **gleichzeitig** an den
CSIRT-Koordinator des Mitgliedstaats und an die ENISA. Eine Meldeakte, die nur
Zeitstempel hält, belegt die Meldung nicht — ohne Adressat und Einreichungs-
referenz ist sie im Streitfall nicht auffindbar. Deshalb sind Mitgliedstaat und
beide Referenzen Pflicht, bevor eine Stufe als gemeldet gilt
(``set_stufe``/``set_empfaenger`` erzwingen das, nicht erst das Formular).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from shared import db as _sdb

DB_PATH = Path("data/db/cra.sqlite")

# Meldungstypen + Status (Single Source of Truth fürs Frontend).
TYPEN = ("vuln_exploited", "serious_incident")
STATUS = ("erkannt", "early_warning_24h", "notification_72h", "final_report")

# Stufen-Reihenfolge für Transition-Validierung.
_STATUS_ORDER = {s: i for i, s in enumerate(STATUS)}

# Status → STAGE_SET-Stufenschlüssel (für „gemeldet-am"-Mapping).
_STATUS_STAGE = {
    "early_warning_24h": "early_warning",
    "notification_72h": "notification",
    "final_report": "final_report",
}

# ── Empfänger der Meldung (#1760, Art. 14) ─────────────────────────────────────

# Die drei Meldestufen, für die es einen Adressaten gibt. 'erkannt' ist kein
# Meldevorgang, sondern der Zustand davor.
STUFEN = ("early_warning", "notification", "final_report")

# Die zwei Adressaten. Art. 14 verlangt beide gleichzeitig: den als Koordinator
# benannten CSIRT des Mitgliedstaats UND die ENISA. Eine Meldung an nur einen
# von beiden erfüllt die Pflicht nicht.
KANAELE = ("csirt", "enisa")
_KANAL_LABEL = {"csirt": "CSIRT-Koordinator", "enisa": "ENISA"}

# Pflichtfelder je Kanal. Die Eingangsbestätigung ist bewusst NICHT Pflicht —
# sie kommt erst nach der Meldung und darf die Meldung nicht blockieren; sie
# erscheint stattdessen als offener Punkt im Nachweis (``nachweis_luecken``).
PFLICHT_FELDER = {
    "csirt": (("mitgliedstaat", "Mitgliedstaat des CSIRT-Koordinators"),
              ("referenz", "Einreichungsreferenz CSIRT")),
    "enisa": (("referenz", "Einreichungsreferenz ENISA"),),
}
# Angaben, die den Nachweis vollständig machen, aber die Meldung nicht aufhalten.
OFFENE_FELDER = {
    "csirt": (("stelle", "Name der meldenden Stelle/des CSIRT"),
              ("eingang_bestaetigt_am", "Eingangsbestätigung CSIRT")),
    "enisa": (("eingang_bestaetigt_am", "Eingangsbestätigung ENISA"),),
}
# Übernommene Felder je Kanal (alles andere wird verworfen — kein Freitext-Müll
# in einer Akte, die etwas belegen soll).
_KANAL_FELDER = ("mitgliedstaat", "stelle", "referenz", "gemeldet_am",
                 "eingang_bestaetigt_am", "bemerkung")

# EU-Mitgliedstaaten (ISO-3166-1 alpha-2). Der je Staat als Koordinator benannte
# CSIRT wird hier NICHT gepflegt: die Benennung liegt beim Mitgliedstaat und
# ändert sich — der Name wird als 'stelle' erfasst, statt eine Liste zu raten.
MITGLIEDSTAATEN = {
    "AT": "Österreich", "BE": "Belgien", "BG": "Bulgarien", "CY": "Zypern",
    "CZ": "Tschechien", "DE": "Deutschland", "DK": "Dänemark", "EE": "Estland",
    "ES": "Spanien", "FI": "Finnland", "FR": "Frankreich", "GR": "Griechenland",
    "HR": "Kroatien", "HU": "Ungarn", "IE": "Irland", "IT": "Italien",
    "LT": "Litauen", "LU": "Luxemburg", "LV": "Lettland", "MT": "Malta",
    "NL": "Niederlande", "PL": "Polen", "PT": "Portugal", "RO": "Rumänien",
    "SE": "Schweden", "SI": "Slowenien", "SK": "Slowakei",
}

# Pflichtfelder der Nutzerunterrichtung (Art. 14 Abs. 8), sobald sie als
# veröffentlicht gemeldet wird. Vorher war das ein Freitextfeld „Kanal" — damit
# ist nicht belegt, dass die Information die Nutzer erreicht hat.
ADVISORY_PFLICHT = (
    ("veroeffentlichungskanal", "Veröffentlichungskanal"),
    ("url", "URL der Veröffentlichung"),
    ("veroeffentlicht_am", "Datum der Veröffentlichung"),
    ("empfaengerkreis", "Unterrichteter Empfängerkreis"),
)


class AngabenUnvollstaendig(ValueError):
    """Pflichtangaben fehlen. Trägt die Feldliste für die API-Antwort."""

    def __init__(self, fehlende: list[str], kontext: str = ""):
        self.fehlende = list(fehlende)
        self.kontext = kontext
        rumpf = ", ".join(self.fehlende)
        super().__init__(
            (f"{kontext}: " if kontext else "") + f"Pflichtangaben fehlen: {rumpf}")


def _connect(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer (#1332)."""
    return _sdb.connect(db_path)


def ensure_table(db_path: Path = DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS cra_meldung (
                id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                projekt_name    TEXT NOT NULL,
                vuln_id         INTEGER,                       -- optionaler FK auf cra_vuln.id
                typ             TEXT NOT NULL DEFAULT 'vuln_exploited',
                titel           TEXT NOT NULL DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'erkannt',
                erkannt_am      TEXT NOT NULL DEFAULT (aics_now()),
                betroffene_ms   TEXT NOT NULL DEFAULT '',      -- betroffene Mitgliedstaaten
                vermutete_ursache TEXT NOT NULL DEFAULT '',
                mitigation      TEXT NOT NULL DEFAULT '',
                beschreibung    TEXT NOT NULL DEFAULT '',
                -- 'Gemeldet-am' je Stufe (ISO-Timestamps).
                early_warning_gemeldet_am   TEXT,
                notification_gemeldet_am    TEXT,
                final_report_gemeldet_am    TEXT,
                -- Nutzer-Advisory (#1209, Art. 14(8)).
                advisory_json   TEXT NOT NULL DEFAULT '{}',
                created_at      TEXT DEFAULT (aics_now()),
                updated_at      TEXT DEFAULT (aics_now())
            );
            CREATE INDEX IF NOT EXISTS idx_cra_meldung_projekt
                ON cra_meldung(projekt_name);
            """
        )
        # #1760: additive Spalten für Bestands-DBs (keine Migration über
        # Kundendaten — bestehende Akten bleiben lesbar, nur ohne Empfänger).
        for ddl in (
            # Empfänger + Einreichungsreferenzen je Stufe (JSON, Form siehe
            # ``leere_empfaenger``). Eine Spalte je Stufe und Kanal wären zwölf
            # Spalten für dieselbe Struktur.
            "ALTER TABLE cra_meldung ADD COLUMN IF NOT EXISTS "
            "empfaenger_json TEXT NOT NULL DEFAULT '{}'",
            # Fristbeginn des Abschlussberichts bei Schwachstellen (#1760):
            # Zeitpunkt, ab dem eine Korrektur-/Minderungsmaßnahme verfügbar
            # ist. Ohne diesen Wert läuft die 14-Tage-Frist nicht.
            "ALTER TABLE cra_meldung ADD COLUMN IF NOT EXISTS "
            "massnahme_verfuegbar_ab TEXT",
        ):
            con.execute(ddl)
        con.commit()
    finally:
        con.close()


def stufe_fuer_status(status: str) -> str:
    """Status → Meldestufe ('' für ``erkannt``, das keine Meldung ist)."""
    return _STATUS_STAGE.get(status, "")


def leere_empfaenger() -> dict[str, Any]:
    """Leeres Empfänger-Gerüst: je Stufe beide Kanäle mit leeren Feldern."""
    return {stufe: {kanal: {f: "" for f in _KANAL_FELDER} for kanal in KANAELE}
            for stufe in STUFEN}


def _normiere_empfaenger(raw: Any) -> dict[str, Any]:
    """Gespeichertes JSON auf das vollständige Gerüst bringen (robust)."""
    out = leere_empfaenger()
    if not isinstance(raw, dict):
        return out
    for stufe in STUFEN:
        stufe_raw = raw.get(stufe)
        if not isinstance(stufe_raw, dict):
            continue
        for kanal in KANAELE:
            kanal_raw = stufe_raw.get(kanal)
            if not isinstance(kanal_raw, dict):
                continue
            for feld in _KANAL_FELDER:
                wert = kanal_raw.get(feld)
                out[stufe][kanal][feld] = "" if wert is None else str(wert).strip()
    return out


def _row(r: Any) -> dict[str, Any]:
    d = dict(r)
    try:
        d["advisory"] = json.loads(d.get("advisory_json") or "{}")
    except Exception:
        d["advisory"] = {}
    try:
        d["empfaenger"] = _normiere_empfaenger(json.loads(d.get("empfaenger_json") or "{}"))
    except Exception:
        d["empfaenger"] = leere_empfaenger()
    return d


def validiere_empfaenger(stufe: str, empfaenger_stufe: dict) -> list[str]:
    """Fehlende **Pflicht**angaben eines Stufen-Empfängers (Labels, leer = ok)."""
    if stufe not in STUFEN:
        raise ValueError(f"Unbekannte Meldestufe: {stufe}")
    daten = _normiere_empfaenger({stufe: empfaenger_stufe or {}})[stufe]
    fehlt: list[str] = []
    for kanal in KANAELE:
        for feld, label in PFLICHT_FELDER[kanal]:
            if not daten[kanal].get(feld):
                fehlt.append(label)
    ms = daten["csirt"].get("mitgliedstaat", "").upper()
    if ms and ms not in MITGLIEDSTAATEN:
        # Als Substantiv formuliert, damit die Angabe auch in der Lückenliste
        # („… fehlt") und in der 400-Antwort lesbar bleibt.
        fehlt.append(f"gültiger Mitgliedstaat des CSIRT-Koordinators "
                     f"(Angabe '{ms}' ist kein EU-Mitgliedstaat)")
    return fehlt


def validiere_advisory(advisory: dict) -> list[str]:
    """Fehlende Pflichtangaben der Nutzerunterrichtung (Art. 14 Abs. 8).

    Prüft nur, wenn die Unterrichtung als **veröffentlicht** gemeldet wird. Ein
    Entwurf darf lückenhaft gespeichert werden; er belegt dann aber auch nichts
    und erscheint als Lücke im Nachweis.
    """
    adv = advisory or {}
    if not adv.get("veroeffentlicht"):
        return []
    fehlt: list[str] = []
    for feld, label in ADVISORY_PFLICHT:
        if not str(adv.get(feld) or "").strip():
            fehlt.append(label)
    url = str(adv.get("url") or "").strip().lower()
    if url and not (url.startswith("http://") or url.startswith("https://")):
        fehlt.append("URL der Veröffentlichung (muss mit http:// oder https:// beginnen)")
    return fehlt


def _stunden_differenz(a: str, b: str) -> Optional[float]:
    """Abstand zweier Zeitstempel in Stunden; None, wenn nicht lesbar."""
    from shared.deadlines import parse_dt
    da, db = parse_dt(a), parse_dt(b)
    if da is None or db is None:
        return None
    return abs((da - db).total_seconds()) / 3600.0


def nachweis_luecken(meldung: dict) -> list[dict[str, Any]]:
    """Was die Meldeakte (noch) nicht belegt — sichtbar statt durchgelassen.

    Jeder Eintrag: ``{bereich, label, text, schwere}`` mit ``schwere``
    ``pflicht`` (Meldung ist nicht belegt) oder ``offen`` (Beleg unvollständig).
    """
    luecken: list[dict[str, Any]] = []
    empf = _normiere_empfaenger(meldung.get("empfaenger") or {})
    for stufe in STUFEN:
        gemeldet = str(meldung.get(f"{stufe}_gemeldet_am") or "").strip()
        if not gemeldet:
            continue  # Stufe noch nicht gemeldet → keine Nachweispflicht.
        label = _STUFE_LABEL.get(stufe, stufe)
        for feld in validiere_empfaenger(stufe, empf[stufe]):
            luecken.append({"bereich": stufe, "label": label, "schwere": "pflicht",
                            "text": f"{label}: {feld} fehlt"})
        for kanal in KANAELE:
            for feld, feld_label in OFFENE_FELDER[kanal]:
                if not empf[stufe][kanal].get(feld):
                    luecken.append({"bereich": stufe, "label": label,
                                    "schwere": "offen",
                                    "text": f"{label}: {feld_label} fehlt"})
        # Gleichzeitigkeit (Art. 14): beide Adressaten zur selben Zeit. Eine
        # Abweichung ist kein Formfehler des Werkzeugs, sondern eine Angabe,
        # die im Nachweis stehen muss.
        a = empf[stufe]["csirt"].get("gemeldet_am", "")
        b = empf[stufe]["enisa"].get("gemeldet_am", "")
        if a and b:
            diff = _stunden_differenz(a, b)
            if diff is not None and diff > 1.0:
                luecken.append({
                    "bereich": stufe, "label": label, "schwere": "offen",
                    "text": (f"{label}: CSIRT und ENISA liegen {diff:.1f} h "
                             "auseinander — Art. 14 verlangt die gleichzeitige "
                             "Meldung an beide"),
                })

    adv = meldung.get("advisory") or {}
    if adv.get("veroeffentlicht"):
        for feld in validiere_advisory(adv):
            luecken.append({"bereich": "nutzerunterrichtung",
                            "label": "Nutzerunterrichtung (Art. 14 Abs. 8)",
                            "schwere": "pflicht", "text": f"{feld} fehlt"})
    elif any(str(adv.get(f) or "").strip() for f, _ in ADVISORY_PFLICHT) or \
            str(adv.get("empfohlene_massnahmen") or "").strip():
        luecken.append({
            "bereich": "nutzerunterrichtung",
            "label": "Nutzerunterrichtung (Art. 14 Abs. 8)", "schwere": "offen",
            "text": "Nutzerunterrichtung ist nur Entwurf — Veröffentlichung "
                    "(URL, Datum, Empfängerkreis) nicht belegt",
        })

    # Fristbeginn des Abschlussberichts (#1760): ohne ihn ist die Frist nicht
    # berechenbar — weder für uns noch für eine Behörde.
    if meldung.get("typ") != "serious_incident" and \
            not str(meldung.get("massnahme_verfuegbar_ab") or "").strip():
        luecken.append({
            "bereich": "final_report", "label": "Abschlussbericht",
            "schwere": "offen",
            "text": "Verfügbarkeit der Korrektur-/Minderungsmaßnahme nicht "
                    "erfasst — Fristbeginn des Abschlussberichts unbestimmt",
        })
    return luecken


def nachweis_status(meldung: dict) -> dict[str, Any]:
    """Nachweis-Übersicht je Meldung (für API/Panel).

    ``gemeldet`` sagt, ob überhaupt eine Stufe abgegeben wurde. Ohne diese
    Angabe sah eine frisch erfasste Akte aus wie eine vollständig belegte:
    Es gibt nichts zu belegen, also auch keine Lücke, also „✓ belegt". Das ist
    formal richtig und praktisch gefährlich — es liest sich wie „Meldepflicht
    erfüllt". Gefunden beim Ansehen der Firefox-Aufnahmen (#1760).
    """
    luecken = nachweis_luecken(meldung)
    pflicht = [l for l in luecken if l["schwere"] == "pflicht"]
    gemeldet = any(str(meldung.get(f"{k}_gemeldet_am") or "").strip()
                   for k in ("early_warning", "notification", "final_report"))
    return {
        "vollstaendig": not luecken,
        "belegt": not pflicht,          # Meldung ist belegt (Adressat+Referenz da)
        "gemeldet": gemeldet,           # wurde überhaupt schon eine Stufe abgegeben?
        "luecken": luecken,
        "pflicht_offen": len(pflicht),
        "offen": len(luecken) - len(pflicht),
    }


def list_meldungen(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM cra_meldung WHERE projekt_name=? ORDER BY erkannt_am DESC, id DESC",
            (projekt_name,),
        ).fetchall()
        return [_row(r) for r in rows]
    finally:
        con.close()


def get_meldung(db_path: Path, meldung_id: int,
                projekt_name: Optional[str] = None) -> Optional[dict[str, Any]]:
    """IDOR-sicher: optional auf projekt_name scopen (#1173-Muster)."""
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        if projekt_name is not None:
            r = con.execute(
                "SELECT * FROM cra_meldung WHERE id=? AND projekt_name=?",
                (meldung_id, projekt_name),
            ).fetchone()
        else:
            r = con.execute(
                "SELECT * FROM cra_meldung WHERE id=?", (meldung_id,)
            ).fetchone()
        return _row(r) if r else None
    finally:
        con.close()


def create_meldung(db_path: Path, projekt_name: str, data: dict) -> int:
    ensure_table(db_path)
    typ = data.get("typ") or "vuln_exploited"
    if typ not in TYPEN:
        raise ValueError(f"Ungültiger Typ: {typ}")
    erkannt = (data.get("erkannt_am") or "").strip()
    con = _connect(db_path)
    try:
        cur = con.execute(
            """
            INSERT INTO cra_meldung
                (projekt_name, vuln_id, typ, titel, status, erkannt_am,
                 betroffene_ms, vermutete_ursache, mitigation, beschreibung,
                 advisory_json, empfaenger_json, massnahme_verfuegbar_ab, updated_at)
            VALUES (?, ?, ?, ?, 'erkannt', COALESCE(NULLIF(?, ''), aics_now()),
                    ?, ?, ?, ?, ?, ?, NULLIF(?, ''), aics_now())
            """,
            (projekt_name, data.get("vuln_id"), typ, data.get("titel", ""),
             erkannt, data.get("betroffene_ms", ""), data.get("vermutete_ursache", ""),
             data.get("mitigation", ""), data.get("beschreibung", ""),
             json.dumps(data.get("advisory") or {}, ensure_ascii=False),
             json.dumps(_normiere_empfaenger(data.get("empfaenger") or {}),
                        ensure_ascii=False),
             str(data.get("massnahme_verfuegbar_ab") or "").strip()),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def update_meldung(db_path: Path, meldung_id: int, projekt_name: str,
                   data: dict) -> bool:
    ensure_table(db_path)
    # #1760: massnahme_verfuegbar_ab ist der Fristbeginn des Abschlussberichts
    # bei Schwachstellen — pflegbar wie jedes andere Sachfeld.
    fields = ["titel", "betroffene_ms", "vermutete_ursache", "mitigation",
              "beschreibung", "vuln_id", "massnahme_verfuegbar_ab"]
    sets, vals = [], []
    for f in fields:
        if f in data:
            sets.append(f"{f}=?")
            vals.append(data[f])
    if not sets:
        return True
    vals += [meldung_id, projekt_name]
    con = _connect(db_path)
    try:
        cur = con.execute(
            f"UPDATE cra_meldung SET {', '.join(sets)}, updated_at=aics_now() "
            "WHERE id=? AND projekt_name=?",
            vals,
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def set_stufe(db_path: Path, meldung_id: int, projekt_name: str,
              neuer_status: str,
              empfaenger: Optional[dict] = None) -> dict[str, Any]:
    """Stufen-Transition (nur vorwärts) + Empfänger/'Gemeldet-am' der Stufe.

    Eine Stufe wird nur erreicht, wenn der Adressat belegt ist (#1760):
    Mitgliedstaat des CSIRT-Koordinators und Einreichungsreferenz von CSIRT und
    ENISA. ``empfaenger`` ergänzt bereits gespeicherte Angaben; fehlt danach
    etwas, wird ``AngabenUnvollstaendig`` geworfen und **nichts** geschrieben.
    Erzwungen wird das hier, nicht im Formular.
    """
    if neuer_status not in STATUS:
        raise ValueError(f"Ungültiger Status: {neuer_status}")
    m = get_meldung(db_path, meldung_id, projekt_name)
    if not m:
        raise ValueError("Meldung nicht gefunden")
    cur_idx = _STATUS_ORDER[m["status"]]
    new_idx = _STATUS_ORDER[neuer_status]
    if new_idx <= cur_idx:
        raise ValueError("Stufe kann nur vorwärts gewechselt werden")
    stage_col = _STATUS_STAGE.get(neuer_status)

    empf = _normiere_empfaenger(m.get("empfaenger") or {})
    if stage_col:
        if empfaenger:
            empf[stage_col] = _merge_kanaele(empf[stage_col], empfaenger)
        fehlt = validiere_empfaenger(stage_col, empf[stage_col])
        if fehlt:
            raise AngabenUnvollstaendig(
                fehlt, f"Stufe „{_STUFE_LABEL.get(stage_col, stage_col)}“")

    con = _connect(db_path)
    try:
        if stage_col:
            con.execute(
                f"UPDATE cra_meldung SET status=?, {stage_col}_gemeldet_am=aics_now(), "
                "empfaenger_json=?, updated_at=aics_now() "
                "WHERE id=? AND projekt_name=?",
                (neuer_status, json.dumps(empf, ensure_ascii=False),
                 meldung_id, projekt_name),
            )
        else:
            con.execute(
                "UPDATE cra_meldung SET status=?, updated_at=aics_now() "
                "WHERE id=? AND projekt_name=?",
                (neuer_status, meldung_id, projekt_name),
            )
        con.commit()
    finally:
        con.close()
    neu = get_meldung(db_path, meldung_id, projekt_name)
    # Meldezeitpunkt je Kanal: nicht gesetzt → Stufenzeitpunkt. Das ist der
    # Beleg der Gleichzeitigkeit; eine Abweichung trägt der Anwender selbst ein.
    if stage_col and neu:
        stufen_zeit = neu.get(f"{stage_col}_gemeldet_am") or ""
        offen = {k: {"gemeldet_am": stufen_zeit}
                 for k in KANAELE if not neu["empfaenger"][stage_col][k].get("gemeldet_am")}
        if offen and stufen_zeit:
            neu = set_empfaenger(db_path, meldung_id, projekt_name, stage_col,
                                 offen, strikt=False) or neu
    return neu


def _merge_kanaele(bestand: dict, neu: dict) -> dict:
    """Kanal-Angaben zusammenführen; leere Werte überschreiben nichts."""
    out = {k: dict(v) for k, v in (bestand or {}).items()}
    for kanal in KANAELE:
        teil = (neu or {}).get(kanal)
        if not isinstance(teil, dict):
            continue
        ziel = out.setdefault(kanal, {f: "" for f in _KANAL_FELDER})
        for feld in _KANAL_FELDER:
            if feld in teil:
                wert = "" if teil[feld] is None else str(teil[feld]).strip()
                if wert:
                    ziel[feld] = wert
                elif teil[feld] == "":
                    ziel[feld] = ""   # ausdrücklich geleert (Korrektur)
    if "mitgliedstaat" in out.get("csirt", {}):
        out["csirt"]["mitgliedstaat"] = out["csirt"]["mitgliedstaat"].upper()
    return out


def set_empfaenger(db_path: Path, meldung_id: int, projekt_name: str,
                   stufe: str, daten: dict,
                   *, strikt: Optional[bool] = None) -> Optional[dict[str, Any]]:
    """Empfänger/Referenzen einer Stufe setzen bzw. ergänzen (#1760).

    ``strikt=None`` (Default) heißt: Pflichtangaben werden erzwungen, **sobald
    die Stufe gemeldet ist**. Vorab-Erfassung darf lückenhaft sein — eine
    bereits abgegebene Meldung darf ihren Adressaten aber nicht verlieren.
    """
    if stufe not in STUFEN:
        raise ValueError(f"Unbekannte Meldestufe: {stufe}")
    m = get_meldung(db_path, meldung_id, projekt_name)
    if not m:
        return None
    empf = _normiere_empfaenger(m.get("empfaenger") or {})
    empf[stufe] = _merge_kanaele(empf[stufe], daten or {})
    if strikt is None:
        strikt = bool(str(m.get(f"{stufe}_gemeldet_am") or "").strip())
    if strikt:
        fehlt = validiere_empfaenger(stufe, empf[stufe])
        if fehlt:
            raise AngabenUnvollstaendig(
                fehlt, f"Stufe „{_STUFE_LABEL.get(stufe, stufe)}“")
    con = _connect(db_path)
    try:
        con.execute(
            "UPDATE cra_meldung SET empfaenger_json=?, updated_at=aics_now() "
            "WHERE id=? AND projekt_name=?",
            (json.dumps(empf, ensure_ascii=False), meldung_id, projekt_name),
        )
        con.commit()
    finally:
        con.close()
    return get_meldung(db_path, meldung_id, projekt_name)


def set_advisory(db_path: Path, meldung_id: int, projekt_name: str,
                 advisory: dict) -> Optional[dict[str, Any]]:
    """Nutzer-Advisory-Record je Meldung speichern (#1209, Art. 14 Abs. 8).

    Wird ``veroeffentlicht`` gesetzt, sind URL, Datum, Kanal und Empfängerkreis
    Pflicht (#1760) — sonst behauptet die Akte eine Unterrichtung, die sie nicht
    belegt. Ein Entwurf (ohne ``veroeffentlicht``) darf lückenhaft bleiben.
    """
    ensure_table(db_path)
    adv = dict(advisory or {})
    if adv.get("veroeffentlicht"):
        fehlt = validiere_advisory(adv)
        if fehlt:
            raise AngabenUnvollstaendig(fehlt, "Nutzerunterrichtung (Art. 14 Abs. 8)")
    con = _connect(db_path)
    try:
        cur = con.execute(
            "UPDATE cra_meldung SET advisory_json=?, updated_at=aics_now() "
            "WHERE id=? AND projekt_name=?",
            (json.dumps(adv, ensure_ascii=False), meldung_id, projekt_name),
        )
        con.commit()
        if cur.rowcount == 0:
            return None
    finally:
        con.close()
    return get_meldung(db_path, meldung_id, projekt_name)


def delete_meldung(db_path: Path, meldung_id: int, projekt_name: str) -> bool:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            "DELETE FROM cra_meldung WHERE id=? AND projekt_name=?",
            (meldung_id, projekt_name),
        )
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


# ── Strukturierte Meldetexte + ENISA-SRP-Export ─────────────────────────────────

_TYP_LABEL = {
    "vuln_exploited": "Aktiv ausgenutzte Schwachstelle",
    "serious_incident": "Schwerwiegender Sicherheitsvorfall",
}
_STUFE_LABEL = {
    "early_warning": "Frühwarnung (24h)",
    "notification": "Meldung (72h)",
    "final_report": "Abschlussbericht",
}


def _adressat_zeile(meldung: dict, stufe: str) -> str:
    """Adressaten einer Stufe als Klartext (für Meldetext/Nachweis)."""
    empf = _normiere_empfaenger(meldung.get("empfaenger") or {}).get(stufe, {})
    teile = []
    for kanal in KANAELE:
        d = empf.get(kanal, {})
        if kanal == "csirt":
            ms = d.get("mitgliedstaat", "")
            name = MITGLIEDSTAATEN.get(ms, ms)
            kopf = f"CSIRT-Koordinator {name or '(Mitgliedstaat nicht erfasst)'}"
            if d.get("stelle"):
                kopf += f" — {d['stelle']}"
        else:
            kopf = "ENISA"
        ref = d.get("referenz") or "(keine Einreichungsreferenz)"
        zeile = f"{kopf}, Referenz {ref}"
        if d.get("gemeldet_am"):
            zeile += f", gemeldet {d['gemeldet_am']}"
        if d.get("eingang_bestaetigt_am"):
            zeile += f", Eingang bestätigt {d['eingang_bestaetigt_am']}"
        teile.append(zeile)
    return " | ".join(teile)


def build_meldetext(meldung: dict, stufe: str) -> str:
    """Strukturierter Meldetext je Stufe (ENISA-SRP-konforme Felder)."""
    lines = [
        f"Stufe: {_STUFE_LABEL.get(stufe, stufe)}",
        f"Typ: {_TYP_LABEL.get(meldung.get('typ', ''), meldung.get('typ', ''))}",
        f"Titel: {meldung.get('titel', '')}",
        f"Erkannt am: {meldung.get('erkannt_am', '')}",
        f"Betroffene Mitgliedstaaten: {meldung.get('betroffene_ms', '') or '—'}",
        # Art. 14: Adressat gehört in jede Stufe — ohne ihn belegt der Text nichts.
        f"Gemeldet an: {_adressat_zeile(meldung, stufe)}",
    ]
    if stufe in ("notification", "final_report"):
        lines.append(f"Vermutete Ursache: {meldung.get('vermutete_ursache', '') or '—'}")
        lines.append(f"Mitigation: {meldung.get('mitigation', '') or '—'}")
    if stufe == "final_report":
        lines.append(f"Beschreibung/Abschluss: {meldung.get('beschreibung', '') or '—'}")
    return "\n".join(lines)


def _srp_recipients(meldung: dict) -> dict[str, Any]:
    """Adressaten je Stufe maschinenlesbar (#1760).

    Art. 14 verlangt die gleichzeitige Meldung an den CSIRT-Koordinator des
    Mitgliedstaats und an die ENISA — der Payload führt beide samt
    Einreichungsreferenz, sonst ist der Export kein Nachweis.
    """
    empf = _normiere_empfaenger(meldung.get("empfaenger") or {})
    out: dict[str, Any] = {}
    for stufe in STUFEN:
        csirt = empf[stufe]["csirt"]
        enisa = empf[stufe]["enisa"]
        ms = csirt.get("mitgliedstaat", "")
        out[stufe] = {
            "csirt_coordinator": {
                "member_state": ms or None,
                "member_state_name": MITGLIEDSTAATEN.get(ms) if ms else None,
                "body": csirt.get("stelle") or None,
                "submission_reference": csirt.get("referenz") or None,
                "submitted_at": csirt.get("gemeldet_am") or None,
                "acknowledged_at": csirt.get("eingang_bestaetigt_am") or None,
            },
            "enisa": {
                "submission_reference": enisa.get("referenz") or None,
                "submitted_at": enisa.get("gemeldet_am") or None,
                "acknowledged_at": enisa.get("eingang_bestaetigt_am") or None,
            },
        }
    return out


def build_srp_payload(meldung: dict, deadlines: dict | None = None) -> dict[str, Any]:
    """ENISA-SRP-naher JSON-Payload (maschinenlesbar)."""
    adv = meldung.get("advisory") or {}
    return {
        "report_type": meldung.get("typ"),
        "title": meldung.get("titel"),
        "status": meldung.get("status"),
        "detected_at": meldung.get("erkannt_am"),
        "affected_member_states": meldung.get("betroffene_ms"),
        "suspected_cause": meldung.get("vermutete_ursache"),
        "mitigation": meldung.get("mitigation"),
        "description": meldung.get("beschreibung"),
        "reported_at": {
            "early_warning": meldung.get("early_warning_gemeldet_am"),
            "notification": meldung.get("notification_gemeldet_am"),
            "final_report": meldung.get("final_report_gemeldet_am"),
        },
        "recipients": _srp_recipients(meldung),
        "corrective_measure_available_at": meldung.get("massnahme_verfuegbar_ab") or None,
        "deadlines": deadlines or {},
        "stage_texts": {
            "early_warning": build_meldetext(meldung, "early_warning"),
            "notification": build_meldetext(meldung, "notification"),
            "final_report": build_meldetext(meldung, "final_report"),
        },
        "user_advisory": adv,
        # Nutzerunterrichtung nach Art. 14 Abs. 8 als Beleg, nicht als Freitext.
        "user_notification": {
            "published": bool(adv.get("veroeffentlicht")),
            "channel": adv.get("veroeffentlichungskanal") or None,
            "url": adv.get("url") or None,
            "published_at": adv.get("veroeffentlicht_am") or None,
            "audience": adv.get("empfaengerkreis") or None,
        },
        "evidence_gaps": nachweis_luecken(meldung),
    }
