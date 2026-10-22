"""AI-Act Art. 43 Abs. 4 — Änderungsverwaltung je KI-System (#1756).

Das Geschwister zum CRA-Release-Vorgang (#1742) — mit einem anderen Auslöser und
einer Ausnahme, die es im CRA nicht gibt.

**Der Auslöser ist keine Software-Version.** Im CRA ist der Vorgang an einen
Build gebunden: etwas wird gebaut und ausgeliefert. Beim AI Act ist der Anlass
eine Änderung **am System** — Nachtraining, neue Trainingsdaten, eine geänderte
Zweckbestimmung, eine im Betrieb abweichende Leistung. Ein Build-Tag beschreibt
davon nichts. Der Vorgang trägt deshalb einen ``stand`` (Bezeichner der
Änderung), einen ``grund_art`` und getrennte Felder für ``modell_version`` und
``daten_version``: bei einem KI-System sind das zwei verschiedene Dinge, und ein
Nachtraining ändert oft nur eines von beiden.

**Die Kernfrage hat drei Antworten, nicht zwei.** Art. 43 Abs. 4 nimmt
Änderungen aus, die der Anbieter **vorab festgelegt und bei der
Konformitätsbewertung bereits mitbewertet** hat — bei fortlernenden Systemen der
Normalfall. ``wesentlich`` kennt deshalb ``ja`` / ``nein`` /
``vorab_bewertet``. Ein Zwei-Zustands-Feld wäre fachlich falsch: Jede
vorgesehene Anpassung eines fortlernenden Systems müsste entweder als
„wesentlich" gemeldet werden (Daueralarm, und die Anwendung wäre nach kurzer
Zeit abgeschaltet) oder als „nicht wesentlich" verschwinden — obwohl sie sehr
wohl zu dokumentieren ist. ``vorab_bewertet`` hält beides auseinander: **keine**
erneute Konformitätsbewertung, aber Anhang-IV-Dokumentation, Protokollierung und
Beobachtungsplan laufen weiter.

Weil die Ausnahme eine Behauptung über die **ursprüngliche** Bewertung ist,
verlangt sie zusätzlich eine Fundstelle (``vorab_referenz``) — wo die
vorgesehene Änderung samt Bewertung niedergelegt ist (Anhang IV Nr. 2 Buchst. f).
Ohne diese Fundstelle wäre ``vorab_bewertet`` der bequemste Ausweg aus jeder
Änderungspflicht, und genau das darf es nicht sein.

Eigene Tabelle ``aiact_aenderungen``. ``aiact_conformity`` bleibt unberührt: sie
hat ``projekt_name UNIQUE`` — einen Datensatz je Projekt, ohne Historie — und
trägt den Bewertungsweg, nicht den Vorgang. Sie zu versionieren hieße, jeden
bestehenden Endpunkt umzubauen.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_act.db import _connect

DB_PATH = Path("data/db/ai_act.sqlite")

#: Anlass der Änderung. Die vier ersten Werte sind die Fälle, die Art. 43 Abs. 4
#: praktisch auslösen (vgl. Art. 3 Nr. 23); ``sonstiges`` ist der Auffangwert und
#: zwingt niemanden, eine Änderung in eine unpassende Schublade zu legen.
GRUND_ARTEN: dict[str, str] = {
    "nachtraining": "Nachtraining / neues Modell",
    "daten": "Neue oder geänderte Trainings-/Eingabedaten",
    "zweck": "Geänderte Zweckbestimmung",
    "leistung": "Abweichende Leistung im Betrieb",
    "sonstiges": "Sonstige Änderung am System",
}

#: Die drei Antworten auf die Kernfrage (Art. 43 Abs. 4). ``''`` = unbeantwortet.
WESENTLICH_WERTE = ("ja", "nein", "vorab_bewertet")

WESENTLICH_LABELS: dict[str, str] = {
    "ja": "Wesentliche Änderung — erneute Konformitätsbewertung erforderlich",
    "nein": "Keine wesentliche Änderung",
    "vorab_bewertet": "Vorab festgelegt und mitbewertet (Art. 43 Abs. 4) — "
                      "keine wesentliche Änderung",
}

#: Statusmaschine. Entwicklung legt an und reicht ein, die zweite Instanz prüft,
#: Entwicklung setzt um:
#:   entwurf → in_pruefung → freigegeben → umgesetzt
#:                        ↘ zurueckgewiesen → entwurf (erneut einreichen)
STATUS = ("entwurf", "in_pruefung", "freigegeben", "zurueckgewiesen", "umgesetzt")

#: Zustände, in denen Stammdaten, Checkliste und Kernfrage gesperrt sind. Wer
#: nach dem Einreichen noch ändern könnte, legt dem Prüfer einen anderen Stand
#: vor als den geprüften.
GESPERRTE_STATUS = ("in_pruefung", "freigegeben", "umgesetzt")

#: Mindestlänge jeder Begründung. Eine Zurückweisung ohne Grund ist für den
#: Einreicher nicht verwertbar; eine Entscheidung ohne Grund ist kein Nachweis.
MIN_GRUND = 10

SCHEMA = """
CREATE TABLE IF NOT EXISTS aiact_aenderungen (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    projekt_name        TEXT NOT NULL,
    stand               TEXT NOT NULL,
    grund_art           TEXT NOT NULL DEFAULT 'sonstiges',
    beschreibung        TEXT NOT NULL DEFAULT '',
    modell_version      TEXT NOT NULL DEFAULT '',
    daten_version       TEXT NOT NULL DEFAULT '',
    wirksam_ab          TEXT NOT NULL DEFAULT '',
    wesentlich          TEXT NOT NULL DEFAULT '',
    wesentlich_grund    TEXT NOT NULL DEFAULT '',
    wesentlich_von      TEXT NOT NULL DEFAULT '',
    wesentlich_am       TEXT,
    vorab_referenz      TEXT NOT NULL DEFAULT '',
    checkliste_json     TEXT NOT NULL DEFAULT '{}',
    gate_json           TEXT NOT NULL DEFAULT '{}',
    status              TEXT NOT NULL DEFAULT 'entwurf',
    erstellt_von        TEXT NOT NULL DEFAULT '',
    eingereicht_am      TEXT,
    geprueft_von        TEXT NOT NULL DEFAULT '',
    geprueft_am         TEXT,
    zurueckweisung_grund TEXT NOT NULL DEFAULT '',
    freigegeben_von     TEXT NOT NULL DEFAULT '',
    freigegeben_am      TEXT,
    umgesetzt_am        TEXT,
    created_at          TEXT NOT NULL DEFAULT (aics_now()),
    updated_at          TEXT NOT NULL DEFAULT (aics_now()),
    UNIQUE(projekt_name, stand)
);
CREATE INDEX IF NOT EXISTS idx_aiact_aend_projekt ON aiact_aenderungen(projekt_name);
"""

#: Stammdaten-Felder, die über die API gesetzt werden dürfen. ``stand`` ist
#: bewusst nicht dabei: er ist Teil des Schlüssels — ein Umbenennen wäre ein
#: neuer Vorgang und keine Korrektur.
STAMMDATEN = ("grund_art", "beschreibung", "modell_version", "daten_version",
              "wirksam_ab")


def ensure_table(db_path: Path = DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _connect(Path(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def _now() -> str:
    """Zeitstempel **innerhalb** der Checklisten-JSON.

    Die Spalten der Tabelle werden dagegen über ``aics_now()`` gesetzt — das ist
    die Konvention des Projekts (einheitliches Format ``YYYY-MM-DD HH:MM:SS``,
    Zeit vom Datenbankserver und nicht vom Anwendungsserver).
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(r: Any) -> dict[str, Any]:
    d = dict(r)
    for col, key in (("checkliste_json", "checkliste"), ("gate_json", "gate")):
        try:
            d[key] = json.loads(d.get(col) or "{}")
        except Exception:  # noqa: BLE001
            d[key] = {}
    d.setdefault("status", "entwurf")
    d["gesperrt"] = d.get("status") in GESPERRTE_STATUS
    d["wesentlich_label"] = WESENTLICH_LABELS.get(d.get("wesentlich") or "", "")
    # Die eine abgeleitete Aussage, die der Vorgang überhaupt treffen soll:
    # Löst diese Änderung eine erneute Konformitätsbewertung aus? Nur ``ja`` tut
    # das — ``vorab_bewertet`` ist der Ausnahmetatbestand des Art. 43 Abs. 4.
    d["neubewertung_erforderlich"] = (d.get("wesentlich") == "ja")
    return d


def list_aenderungen(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        rows = con.execute(
            "SELECT * FROM aiact_aenderungen WHERE projekt_name=? "
            "ORDER BY created_at DESC, id DESC", (projekt_name,)).fetchall()
        return [_row(r) for r in rows]
    finally:
        con.close()


def get_aenderung(db_path: Path, projekt_name: str, stand: str) -> dict[str, Any] | None:
    ensure_table(db_path)
    con = _connect(Path(db_path))
    try:
        r = con.execute(
            "SELECT * FROM aiact_aenderungen WHERE projekt_name=? AND stand=?",
            (projekt_name, stand)).fetchone()
        return _row(r) if r else None
    finally:
        con.close()


def _setze(db_path: Path, projekt_name: str, stand: str,
           zuweisungen: str, werte: tuple[Any, ...]) -> dict[str, Any]:
    con = _connect(Path(db_path))
    try:
        con.execute(
            f"UPDATE aiact_aenderungen SET {zuweisungen}, updated_at=aics_now() "
            "WHERE projekt_name=? AND stand=?", (*werte, projekt_name, stand))
        con.commit()
    finally:
        con.close()
    return get_aenderung(db_path, projekt_name, stand) or {}


def _pruefe_stammdaten(data: dict[str, Any]) -> None:
    art = str(data.get("grund_art") or "sonstiges")
    if art not in GRUND_ARTEN:
        raise ValueError(f"Unbekannter Änderungsgrund: {art}")


def create_aenderung(db_path: Path, projekt_name: str, data: dict[str, Any],
                     von: str = "") -> dict[str, Any]:
    """Änderungsvorgang anlegen. Idempotent: ein vorhandener Stand wird geliefert.

    Angelegt wird ausschließlich hier, nie beim Lesen (#1747-Lehre): Sonst
    hinterlässt ein Deep-Link mit Tippfehler im Stand einen leeren Entwurf, und
    jeder Vorab-Abruf des Browsers schreibt in die Datenbank.
    """
    ensure_table(db_path)
    stand = str(data.get("stand") or "").strip()
    if not stand:
        raise ValueError('Feld "stand" ist Pflicht — der Vorgang braucht einen '
                         "Bezeichner der Änderung")
    vorhanden = get_aenderung(db_path, projekt_name, stand)
    if vorhanden:
        return vorhanden
    _pruefe_stammdaten(data)
    con = _connect(Path(db_path))
    try:
        con.execute(
            """INSERT INTO aiact_aenderungen
                   (projekt_name, stand, grund_art, beschreibung, modell_version,
                    daten_version, wirksam_ab, erstellt_von)
               VALUES (?,?,?,?,?,?,?,?)""",
            (projekt_name, stand, str(data.get("grund_art") or "sonstiges"),
             str(data.get("beschreibung") or ""), str(data.get("modell_version") or ""),
             str(data.get("daten_version") or ""), str(data.get("wirksam_ab") or ""),
             von or ""))
        con.commit()
    finally:
        con.close()
    return get_aenderung(db_path, projekt_name, stand) or {}


def update_stammdaten(db_path: Path, projekt_name: str, stand: str,
                      data: dict[str, Any]) -> dict[str, Any]:
    rec = get_aenderung(db_path, projekt_name, stand)
    if not rec:
        raise LookupError("Änderungsvorgang nicht gefunden")
    if rec.get("status") in GESPERRTE_STATUS:
        raise ValueError(f"Der Vorgang ist im Zustand '{rec.get('status')}' gesperrt")
    _pruefe_stammdaten({**rec, **data})
    felder = [f for f in STAMMDATEN if f in data]
    if not felder:
        return rec
    return _setze(db_path, projekt_name, stand,
                  ", ".join(f"{f}=?" for f in felder),
                  tuple(str(data.get(f) or "") for f in felder))


def set_wesentlich(db_path: Path, projekt_name: str, stand: str, wert: str,
                   grund: str, von: str = "",
                   vorab_referenz: str = "") -> dict[str, Any]:
    """Die Kernfrage beantworten (Art. 43 Abs. 4) — drei Antworten.

    Jede der drei braucht eine Begründung, auch ``nein``: Gerade die Aussage
    „das war keine wesentliche Änderung" ist die, die später hinterfragt wird.

    ``vorab_bewertet`` braucht zusätzlich eine **Fundstelle**. Die Ausnahme des
    Art. 43 Abs. 4 greift nur, wenn die Änderung vorab festgelegt **und bei der
    ursprünglichen Konformitätsbewertung mitbewertet** wurde — das ist eine
    Behauptung über ein vorhandenes Dokument (Anhang IV Nr. 2 Buchst. f). Ohne
    Fundstelle wäre sie der bequemste Weg, jede Änderungspflicht abzuräumen.
    """
    if wert not in WESENTLICH_WERTE:
        raise ValueError(
            "Wert muss 'ja', 'nein' oder 'vorab_bewertet' sein — Art. 43 Abs. 4 "
            "kennt drei Antworten")
    if len((grund or "").strip()) < MIN_GRUND:
        raise ValueError(f"Begründung erforderlich (mindestens {MIN_GRUND} Zeichen) — "
                         "auch für 'nein'")
    if wert == "vorab_bewertet" and len((vorab_referenz or "").strip()) < 3:
        raise ValueError(
            "Für 'vorab_bewertet' ist die Fundstelle der vorab festgelegten "
            "Änderung anzugeben (technische Dokumentation, Anhang IV Nr. 2 "
            "Buchst. f) — ohne sie ist die Ausnahme des Art. 43 Abs. 4 nicht belegt")
    rec = get_aenderung(db_path, projekt_name, stand)
    if not rec:
        raise LookupError("Änderungsvorgang nicht gefunden")
    if rec.get("status") in GESPERRTE_STATUS:
        raise ValueError(f"Der Vorgang ist im Zustand '{rec.get('status')}' gesperrt")
    return _setze(
        db_path, projekt_name, stand,
        "wesentlich=?, wesentlich_grund=?, wesentlich_von=?, "
        "wesentlich_am=aics_now(), vorab_referenz=?",
        (wert, grund.strip(), von or "",
         (vorab_referenz or "").strip() if wert == "vorab_bewertet" else ""))


def set_checkliste(db_path: Path, projekt_name: str, stand: str, item_id: str,
                   status: str, begruendung: str, von: str = "") -> dict[str, Any]:
    """Einen Punkt der Änderungs-Checkliste setzen.

    Vier Regeln, jede mit einem Grund:

    * ``gerechnet``-Punkte sind nicht setzbar — wären sie es, ließe sich der
      Nachweis mit einem Klick erzeugen, statt ihn zu erbringen.
    * Die Kernfrage läuft über :func:`set_wesentlich` — sie hat drei Antworten
      und eigene Felder (Person, Zeit, Fundstelle), ein Checklisten-Haken
      könnte das nicht tragen.
    * ``entscheidung``-Punkte brauchen eine Begründung, sobald sie nicht mehr
      offen sind — auch ``nicht_anwendbar``: „gilt hier nicht" ist eine Aussage
      über das System und keine Formalie.
    * Nach dem Einreichen ist Schluss.
    """
    from ai_act import aenderung_checkliste as ac

    item = ac.item(item_id)
    if item is None:
        raise ValueError(f"Unbekannter Prüfpunkt: {item_id}")
    if item_id == ac.KERNFRAGE_ID:
        raise ValueError(
            "Die Kernfrage nach Art. 43 Abs. 4 wird über 'wesentliche-aenderung' "
            "beantwortet — sie kennt drei Antworten und braucht eine Begründung")
    if item.art == "gerechnet":
        raise ValueError(f"'{item.label}' wird aus den Daten der Anwendung gerechnet "
                         "und kann nicht von Hand gesetzt werden")
    if status not in ac.STATUS:
        raise ValueError(f"Unzulässiger Status: {status}")
    if status != "offen" and item_id in ac.BEGRUENDUNG_PFLICHT \
            and len((begruendung or "").strip()) < MIN_GRUND:
        raise ValueError(f"'{item.label}' braucht eine Begründung (mindestens "
                         f"{MIN_GRUND} Zeichen)")

    rec = get_aenderung(db_path, projekt_name, stand)
    if not rec:
        raise LookupError("Änderungsvorgang nicht gefunden")
    if rec.get("status") in GESPERRTE_STATUS:
        raise ValueError(f"Der Vorgang ist im Zustand '{rec.get('status')}' gesperrt")

    aktuell = dict(rec.get("checkliste") or {})
    aktuell[item_id] = {"status": status, "begruendung": (begruendung or "").strip(),
                        "von": von or "", "am": _now()}
    return _setze(db_path, projekt_name, stand, "checkliste_json=?",
                  (json.dumps(aktuell, ensure_ascii=False),))


def einreichen(db_path: Path, projekt_name: str, stand: str, von: str,
               gate: dict[str, Any] | None = None) -> dict[str, Any]:
    """Vorgang zur Prüfung geben (Entwicklung, ``AIACT_WRITE``).

    Friert den gerechneten Stand (``gate``) ein. Ohne dieses Einfrieren prüft die
    zweite Instanz gegen eine Datenlage, die sich bis zur Freigabe verschoben
    haben kann — und später sagt niemand mehr, auf welcher Grundlage freigegeben
    wurde.

    Die Kernfrage muss beantwortet sein. Sie ist der Gegenstand des Vorgangs:
    Ein Vorgang ohne Antwort auf Art. 43 Abs. 4 legt dem Prüfer nichts vor.
    """
    rec = get_aenderung(db_path, projekt_name, stand)
    if not rec:
        raise LookupError("Änderungsvorgang nicht gefunden")
    status = rec.get("status", "entwurf")
    if status not in ("entwurf", "zurueckgewiesen"):
        raise ValueError(f"Einreichen ist im Zustand '{status}' nicht möglich")
    if not rec.get("wesentlich"):
        raise ValueError(
            "Vor dem Einreichen ist die Frage nach Art. 43 Abs. 4 zu beantworten "
            "(wesentliche Änderung: ja / nein / vorab festgelegt und mitbewertet)")
    # ``erstellt_von`` wird beim ersten Einreichen gesetzt und danach nicht mehr
    # überschrieben: Es ist die eine Hälfte der Vier-Augen-Prüfung. Würde ein
    # zweites Einreichen den Namen ändern, könnte der Einreicher sich durch
    # erneutes Einreichen selbst zum Freigeber machen.
    ersteller = rec.get("erstellt_von") or (von or "")
    return _setze(
        db_path, projekt_name, stand,
        "status='in_pruefung', erstellt_von=?, eingereicht_am=aics_now(), "
        "gate_json=?, zurueckweisung_grund=''",
        (ersteller, json.dumps(gate or rec.get("gate") or {}, ensure_ascii=False)))


def zurueckweisen(db_path: Path, projekt_name: str, stand: str, von: str,
                  grund: str) -> dict[str, Any]:
    """Prüfung mit Begründung zurückweisen (``AIACT_APPROVE``)."""
    rec = get_aenderung(db_path, projekt_name, stand)
    if not rec:
        raise LookupError("Änderungsvorgang nicht gefunden")
    if rec.get("status") != "in_pruefung":
        raise ValueError("Zurückweisen ist nur in der Prüfung möglich")
    if len((grund or "").strip()) < MIN_GRUND:
        raise ValueError(f"Begründung erforderlich (mindestens {MIN_GRUND} Zeichen) — "
                         "eine Zurückweisung ohne Grund ist für den Einreicher "
                         "nicht verwertbar")
    return _setze(db_path, projekt_name, stand,
                  "status='zurueckgewiesen', geprueft_von=?, "
                  "geprueft_am=aics_now(), zurueckweisung_grund=?",
                  (von or "", grund.strip()))


def freigeben(db_path: Path, projekt_name: str, stand: str, von: str) -> dict[str, Any]:
    """Vorgang freigeben (``AIACT_APPROVE``) — Vier-Augen-Prinzip.

    Zwei Bedingungen, ohne die die Freigabe nichts belegt: Sie setzt eine
    Einreichung voraus, und der Freigeber ist nicht der Einreicher. Beides muss
    eine Eigenschaft der Anwendung sein, nicht eine Absprache.
    """
    rec = get_aenderung(db_path, projekt_name, stand)
    if not rec:
        raise LookupError("Änderungsvorgang nicht gefunden")
    if rec.get("status") in ("freigegeben", "umgesetzt"):
        raise ValueError("Der Vorgang ist bereits freigegeben")
    if rec.get("status") != "in_pruefung":
        raise ValueError("Freigabe setzt eine Einreichung voraus — den Vorgang "
                         "zuerst zur Prüfung geben")
    ersteller = (rec.get("erstellt_von") or "").strip().lower()
    if ersteller and ersteller == (von or "").strip().lower():
        raise ValueError("Wer einreicht, darf nicht freigeben — die Freigabe "
                         "braucht eine zweite Person (Vier-Augen-Prinzip)")
    return _setze(db_path, projekt_name, stand,
                  "status='freigegeben', freigegeben_von=?, "
                  "freigegeben_am=aics_now(), geprueft_von=?, "
                  "geprueft_am=aics_now(), zurueckweisung_grund=''",
                  (von or "", von or ""))


def umsetzen(db_path: Path, projekt_name: str, stand: str) -> dict[str, Any]:
    """Freigegebene Änderung als umgesetzt markieren (Entwicklung).

    Der letzte Schritt ist bewusst getrennt von der Freigabe: Freigegeben heißt
    „darf in Betrieb gehen", umgesetzt heißt „ist in Betrieb". Zwischen beiden
    liegt bei einem KI-System die Ausrollung des Modells.
    """
    rec = get_aenderung(db_path, projekt_name, stand)
    if not rec:
        raise LookupError("Änderungsvorgang nicht gefunden")
    if rec.get("status") != "freigegeben":
        raise ValueError("Umsetzen setzt eine Freigabe voraus")
    return _setze(db_path, projekt_name, stand,
                  "status='umgesetzt', umgesetzt_am=aics_now()", ())


def delete_aenderung(db_path: Path, projekt_name: str, stand: str) -> bool:
    """Entwurf verwerfen. Ab der Einreichung gibt es kein Löschen mehr — ein
    eingereichter Vorgang ist Teil der Akte."""
    rec = get_aenderung(db_path, projekt_name, stand)
    if not rec:
        return False
    if rec.get("status") != "entwurf":
        raise ValueError("Nur ein Entwurf kann verworfen werden — ab der "
                         "Einreichung gehört der Vorgang zur Akte")
    con = _connect(Path(db_path))
    try:
        con.execute("DELETE FROM aiact_aenderungen WHERE projekt_name=? AND stand=?",
                    (projekt_name, stand))
        con.commit()
    finally:
        con.close()
    return True


def grund_arten() -> list[dict[str, str]]:
    return [{"code": k, "label": v} for k, v in GRUND_ARTEN.items()]


def wesentlich_werte() -> list[dict[str, Any]]:
    """Die drei Antworten mit Label und der Folge, die sie auslösen."""
    return [{"code": k, "label": WESENTLICH_LABELS[k],
             "neubewertung": k == "ja",
             "referenz_pflicht": k == "vorab_bewertet"}
            for k in WESENTLICH_WERTE]
