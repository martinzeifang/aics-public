"""CRA Art. 32 / Annex VIII — Konformitätsbewertung + DoC/CE-Record (#1201).

Pro Projekt/Release ein Konformitätsbewertungs-Record: gewählter Bewertungsweg
(Modul A | B+C | H | EUCC), Nachweis-Checkliste je Modul, Notified-Body-Kennnummer/
EUCC-Level, CE-Status, strukturierter Annex-V-DoC-Record (versioniert). Gate:
DoC erst ausstellbar, wenn der Bewertungsweg abgeschlossen ist.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from shared import db as _sdb
from shared import vier_augen
from cra import requirements as _req

DB_PATH = Path("data/db/cra.sqlite")

# Konformitätsbewertungs-Wege (Annex VIII).
# #1759: abgeleitet aus ``cra.requirements.BEWERTUNGSWEGE`` — dort steht auch,
# welche Wege welcher Produktklasse offenstehen und welcher eine notifizierte
# Stelle braucht. Eine eigene Liste hier wäre die zweite Wahrheit.
WEGE = tuple(_req.BEWERTUNGSWEGE)

# Nachweis-Checkliste je Modul (Soll-Nachweise).
CHECKLISTE: dict[str, list[str]] = {
    "A": ["technische_dokumentation", "interne_fertigungskontrolle"],
    "B+C": ["technische_dokumentation", "eu_baumusterpruefung", "konformitaet_mit_baumuster",
            "nb_zertifikat"],
    "H": ["technische_dokumentation", "umfassendes_qm_system", "nb_zertifikat"],
    "EUCC": ["technische_dokumentation", "eucc_zertifikat", "eucc_level"],
}

# CE-Status-Werte.
CE_STATUS = ("offen", "in_bewertung", "bewertung_abgeschlossen", "doc_ausgestellt", "ce_angebracht")


def _connect(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer (#1332)."""
    return _sdb.connect(db_path)


def ensure_table(db_path: Path = DB_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS cra_konformitaet (
                id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                projekt_name    TEXT NOT NULL,
                release_version TEXT NOT NULL DEFAULT '',
                bewertungsweg   TEXT NOT NULL DEFAULT 'A',
                produktklasse   TEXT NOT NULL DEFAULT 'default',
                checkliste_json TEXT NOT NULL DEFAULT '{}',   -- {nachweis: bool}
                bewertung_abgeschlossen INTEGER NOT NULL DEFAULT 0,
                nb_kennnummer   TEXT NOT NULL DEFAULT '',      -- Notified-Body-Kennnummer
                eucc_level      TEXT NOT NULL DEFAULT '',
                ce_status       TEXT NOT NULL DEFAULT 'offen',
                doc_json        TEXT NOT NULL DEFAULT '{}',    -- strukturierter Annex-V-DoC
                doc_version     INTEGER NOT NULL DEFAULT 0,
                doc_ausgestellt INTEGER NOT NULL DEFAULT 0,
                doc_ausgestellt_am TEXT,
                notizen         TEXT NOT NULL DEFAULT '',
                created_at      TEXT DEFAULT (aics_now()),
                updated_at      TEXT DEFAULT (aics_now()),
                UNIQUE(projekt_name, release_version)
            );
            CREATE INDEX IF NOT EXISTS idx_cra_konformitaet_projekt
                ON cra_konformitaet(projekt_name);
            """
        )
        # #1220-A: Sign-off-/Lock-Spalten idempotent ergänzen (Bestands-DBs).
        for ddl in (
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS freigabe_status TEXT NOT NULL DEFAULT 'entwurf'",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS freigegeben_von TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS freigegeben_am TEXT",
            # #1671: CE-Kennzeichnungs-Nachweis
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS ce_angebracht_am TEXT",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS ce_ort TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS ce_nachweis TEXT NOT NULL DEFAULT ''",
            # #1743/#1744 (v8.0.0): Der Release-Vorgang. Diese Tabelle ist
            # bereits UNIQUE(projekt_name, release_version) — sie IST der
            # Vorgang je Release. Eine zweite Tabelle daneben wäre die
            # Fehlerklasse, die dieses Projekt schon mehrfach bezahlt hat
            # (fünf Kopien der Adapter-Verdrahtung in #1731, sechs Kopien der
            # Modul→DB-Zuordnung in #1735): zwei Orte, eine Wahrheit.
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS erstellt_von TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS eingereicht_am TEXT",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS geprueft_von TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS geprueft_am TEXT",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS zurueckweisung_grund TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS veroeffentlicht_am TEXT",
            # Eigene Spalte, NICHT in checkliste_json gemischt: dort stehen die
            # Verfahrensschritte nach Anhang VIII, hier die Release-Pflichten.
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS release_checkliste_json TEXT NOT NULL DEFAULT '{}'",
            # Eingefrorener Rechenstand bei Einreichung. Gerechneter Stand und
            # menschliche Aussage bleiben getrennt (Muster compliance_audit
            # status_json/ki_json) — sonst ist später nicht nachvollziehbar,
            # was gerechnet und was erklärt wurde.
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS gate_json TEXT NOT NULL DEFAULT '{}'",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS wesentliche_aenderung TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS wesentliche_aenderung_grund TEXT NOT NULL DEFAULT ''",
            # #1748-Fund: Die wichtigste Entscheidung des Vorgangs hatte keinen
            # Autor. Jeder Checklisten-Punkt hält Person und Zeit fest, gerade
            # die Frage nach der wesentlichen Änderung (Art. 3 Nr. 30) aber
            # nicht — im Nachweis stand dort „(nicht erfasst)".
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS wesentliche_aenderung_von TEXT NOT NULL DEFAULT ''",
            # #1793: Welcher Art ist dieses Release? Leer = unbestimmt, so steht
            # jeder Bestandsvorgang da. Die Art ersetzt die Kernfrage nicht, sie
            # schlägt deren Antwort vor und wird gegen die Akte gerechnet.
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS release_art TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS release_art_von TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS release_art_am TEXT",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS wesentliche_aenderung_am TEXT",
        ):
            con.execute(ddl)
        con.commit()
    finally:
        con.close()


# #1220-A: Freigabe-Status-Werte (Governance-Gate).
# #1743 (v8.0.0): um die Prüfschritte erweitert. Entwicklung reicht ein,
# Compliance gibt frei oder weist zurück, Entwicklung veröffentlicht.
#   entwurf → in_pruefung → freigegeben → veroeffentlicht
#                        ↘ zurueckgewiesen → entwurf
FREIGABE_STATUS = ("entwurf", "in_pruefung", "freigegeben", "zurueckgewiesen",
                   "veroeffentlicht")

#: Zustände, in denen die Stammdaten des Vorgangs gesperrt sind.
GESPERRTE_STATUS = ("in_pruefung", "freigegeben", "veroeffentlicht")

#: Mindestlänge einer Zurückweisungs-Begründung. Ohne Begründung ist eine
#: Zurückweisung für den Einreicher nicht verwertbar (Muster #969).
MIN_GRUND = 10


def _row(r: Any) -> dict[str, Any]:
    d = dict(r)
    for col, key in (("checkliste_json", "checkliste"), ("doc_json", "doc"),
                     ("release_checkliste_json", "release_checkliste"),
                     ("gate_json", "gate")):
        try:
            d[key] = json.loads(d.get(col) or "{}")
        except Exception:
            d[key] = {}
    d["bewertung_abgeschlossen"] = bool(d.get("bewertung_abgeschlossen"))
    d["doc_ausgestellt"] = bool(d.get("doc_ausgestellt"))
    d["soll_nachweise"] = CHECKLISTE.get(d.get("bewertungsweg", "A"), [])
    d.setdefault("freigabe_status", "entwurf")
    # #1220-A Lock, #1743 erweitert: Ab der Einreichung sind die Stammdaten
    # gesperrt. Wer nach dem Einreichen noch ändern könnte, würde dem Prüfer
    # einen anderen Stand vorlegen als den geprüften.
    d["gesperrt"] = d.get("freigabe_status") in GESPERRTE_STATUS
    return d


def get_konformitaet(db_path: Path, projekt_name: str,
                     release_version: str = "") -> Optional[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        r = con.execute(
            "SELECT * FROM cra_konformitaet WHERE projekt_name=? AND release_version=?",
            (projekt_name, release_version),
        ).fetchone()
        return _row(r) if r else None
    finally:
        con.close()


def produktklasse_projekt(db_path: Path, projekt_name: str) -> str:
    """Die auf dem **Projekt** erfasste Produktklasse (``cra_projekte``).

    Dort entscheidet der Anwender sie (Endpunkt ``/klassifizierung``); im
    Konformitäts-Record liegt nur eine Kopie, und die Oberfläche schickt beim
    Speichern keine mit. Best effort: Ein unlesbares Projekt darf das Speichern
    nicht verhindern — es führt nur dazu, dass gegen die mitgeschickte Klasse
    geprüft wird.
    """
    try:
        from cra.db import load_projekt
        return str((load_projekt(db_path, projekt_name) or {}).get("produktklasse") or "")
    except Exception:  # noqa: BLE001
        return ""


def effektive_produktklasse(db_path: Path, projekt_name: str,
                            data: dict | None = None) -> str:
    """Die Klasse, gegen die geprüft wird: die **strengste** aus Eingabe und Projekt.

    Grund (#1759): Würde nur die Eingabe zählen, ließe sich die Prüfung mit einem
    weggelassenen Feld aushebeln — die Oberfläche lässt die Klasse im
    Konformitäts-Formular ohnehin weg, der Record stand damit bisher immer auf
    ``default``. Würde nur der Record zählen, bliebe die Klassifizierung des
    Projekts ohne Wirkung. Beides wäre genau das Loch, das dieses Issue schließt.
    """
    projekt_klasse = produktklasse_projekt(db_path, projekt_name)
    eingabe = str((data or {}).get("produktklasse") or "").strip()
    return _req.strengste_klasse(eingabe or projekt_klasse, projekt_klasse)


def save_konformitaet(db_path: Path, projekt_name: str, data: dict) -> dict[str, Any]:
    ensure_table(db_path)
    release = data.get("release_version", "")
    ce_status = data.get("ce_status") or "offen"
    if ce_status not in CE_STATUS:
        raise ValueError(f"Ungültiger CE-Status: {ce_status}")
    abgeschlossen = 1 if data.get("bewertung_abgeschlossen") else 0
    # #1220-A: freigegebener Record ist gesperrt (Lock) — erst reopen nötig.
    # Bleibt die **erste** inhaltliche Prüfung: Bei einem gesperrten Record ist
    # „erst zurücksetzen" die Auskunft, die weiterhilft, und nicht eine
    # Beanstandung an Angaben, die ohnehin nicht geschrieben werden.
    existing = get_konformitaet(db_path, projekt_name, release)
    if existing and existing.get("freigabe_status") == "freigegeben":
        raise ValueError("Record ist freigegeben und gesperrt — erst zurücksetzen (reopen)")
    # #1759: Der Weg muss für die Produktklasse zulässig sein. Vorher wurde nur
    # geprüft, ob er *einer der vier* ist — ein als „critical" (Anhang IV)
    # klassifiziertes Produkt ließ sich über Modul A selbstdeklarieren und bekam
    # dafür eine EU-Konformitätserklärung und eine grüne Ampel.
    klasse = effektive_produktklasse(db_path, projekt_name, data)
    weg = str(data.get("bewertungsweg") or "").strip()
    if not weg:
        # Ohne Angabe gilt der bisherige Weg, sonst der **erste zulässige** der
        # Klasse. Der frühere Festwert ``"A"`` war genau die Lücke an einer
        # zweiten Stelle: ``POST /releases/<version>`` legt den Vorgang ohne Weg
        # an — bei einem Anhang-IV-Produkt stand danach Modul A im Datensatz
        # (und mit der neuen Prüfung ließe sich kein Release mehr anlegen).
        # Für ``default``/``important_i`` bleibt das ``A`` wie bisher.
        weg = str((existing or {}).get("bewertungsweg") or "") \
            or _req.zulaessige_wege(klasse)[0]
    if weg not in WEGE:
        raise ValueError(f"Ungültiger Bewertungsweg: {weg}")
    ablehnung = _req.weg_ablehnung(klasse, weg)
    if ablehnung:
        raise ValueError(ablehnung)
    if abgeschlossen:
        # #1759, Punkt 4: Bei B+C/H/EUCC ist eine dritte Stelle beteiligt. Der
        # Abschluss trägt anschließend Freigabe, DoC und CE-Kennzeichnung — ohne
        # jede Angabe zu dieser Stelle ist er keine Aussage. Die Pflicht griff
        # bisher erst im DoC-Formular, also eine Station zu spät.
        #
        # Geprüft wird die **Eingabe**, nicht der gespeicherte Stand: Dieselbe
        # Anweisung schreibt ``nb_kennnummer``/``eucc_level`` mit, ein Rückfall
        # auf den Altwert würde also „abgeschlossen" mit einem anschließend
        # geleerten Feld erlauben — genau das Loch wieder.
        mangel = _req.abschluss_mangel(weg, data.get("nb_kennnummer", ""),
                                       data.get("eucc_level", ""))
        if mangel:
            raise ValueError(mangel)
    con = _connect(db_path)
    try:
        con.execute(
            """INSERT INTO cra_konformitaet
                   (projekt_name, release_version, bewertungsweg, produktklasse,
                    checkliste_json, bewertung_abgeschlossen, nb_kennnummer, eucc_level,
                    ce_status, notizen, ce_angebracht_am, ce_ort, ce_nachweis, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,aics_now())
               ON CONFLICT(projekt_name, release_version) DO UPDATE SET
                   bewertungsweg=excluded.bewertungsweg,
                   produktklasse=excluded.produktklasse,
                   checkliste_json=excluded.checkliste_json,
                   bewertung_abgeschlossen=excluded.bewertung_abgeschlossen,
                   nb_kennnummer=excluded.nb_kennnummer,
                   eucc_level=excluded.eucc_level,
                   ce_status=excluded.ce_status,
                   ce_angebracht_am=excluded.ce_angebracht_am,
                   ce_ort=excluded.ce_ort,
                   ce_nachweis=excluded.ce_nachweis,
                   notizen=excluded.notizen,
                   updated_at=aics_now()""",
            # Gespeichert wird die **geprüfte** Klasse: Der Record hält damit
            # fest, gegen was der Weg zulässig war. Bestands-Records werden
            # dadurch nicht angefasst — nur ein ausdrückliches Speichern
            # schreibt den Wert, und dann denselben, gegen den gerade geprüft
            # wurde (sonst stünde im Nachweis eine andere Klasse als in der
            # Prüfung).
            (projekt_name, release, weg, klasse,
             json.dumps(data.get("checkliste") or {}, ensure_ascii=False),
             abgeschlossen, data.get("nb_kennnummer", ""), data.get("eucc_level", ""),
             ce_status, data.get("notizen", ""),
             (data.get("ce_angebracht_am") or None), data.get("ce_ort", ""), data.get("ce_nachweis", "")),
        )
        con.commit()
    finally:
        con.close()
    return get_konformitaet(db_path, projekt_name, release)


def issue_doc(db_path: Path, projekt_name: str, doc: dict,
              release_version: str = "") -> dict[str, Any]:
    """Annex-V-DoC ausstellen — Gate: nur bei abgeschlossenem Bewertungsweg.

    Erhöht ``doc_version``, setzt CE-Status auf ``doc_ausgestellt``.
    """
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Konformitätsbewertungs-Record vorhanden")
    if not rec.get("bewertung_abgeschlossen"):
        raise ValueError("DoC erst ausstellbar, wenn der Bewertungsweg abgeschlossen ist")
    new_version = int(rec.get("doc_version") or 0) + 1
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE cra_konformitaet SET doc_json=?, doc_version=?, doc_ausgestellt=1,
                      doc_ausgestellt_am=aics_now(), ce_status='doc_ausgestellt',
                      updated_at=aics_now()
               WHERE projekt_name=? AND release_version=?""",
            (json.dumps(doc or {}, ensure_ascii=False), new_version,
             projekt_name, release_version),
        )
        con.commit()
    finally:
        con.close()
    return get_konformitaet(db_path, projekt_name, release_version)


def _setze(db_path: Path, projekt_name: str, release_version: str,
           zuweisungen: str, werte: tuple[Any, ...]) -> dict[str, Any]:
    """UPDATE auf genau einen Vorgang. Hält die SQL-Wiederholung klein."""
    con = _connect(db_path)
    try:
        con.execute(
            f"""UPDATE cra_konformitaet SET {zuweisungen}, updated_at=aics_now()
                WHERE projekt_name=? AND release_version=?""",
            (*werte, projekt_name, release_version),
        )
        con.commit()
    finally:
        con.close()
    return get_konformitaet(db_path, projekt_name, release_version)


def einreichen(db_path: Path, projekt_name: str, release_version: str,
               von: str, gate: dict[str, Any] | None = None) -> dict[str, Any]:
    """#1743: Release zur Prüfung geben (Entwicklung, CRA_WRITE).

    Friert den gerechneten Stand (``gate``) mit ein. Ohne dieses Einfrieren
    prüft Compliance gegen eine Datenlage, die sich bis zur Freigabe verschoben
    haben kann — und der Nachweis sagt später nicht, auf welcher Grundlage
    freigegeben wurde.
    """
    if not str(release_version or ""):
        # Der Datensatz ohne Version ist der Produkt-Datensatz (Phase 1), kein
        # Release. Ihn „einzureichen" hätte keine Bedeutung.
        raise ValueError("Einreichen braucht eine Release-Version")
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Konformitätsbewertungs-Record vorhanden")
    status = rec.get("freigabe_status", "entwurf")
    if status not in ("entwurf", "zurueckgewiesen"):
        raise ValueError(f"Einreichen ist im Zustand '{status}' nicht möglich")
    # erstellt_von wird beim ersten Einreichen gesetzt und danach nicht mehr
    # überschrieben: Es ist die eine Hälfte der Vier-Augen-Prüfung. Würde ein
    # zweites Einreichen den Namen ändern, könnte der Einreicher sich durch
    # erneutes Einreichen selbst zum Freigeber machen.
    ersteller = rec.get("erstellt_von") or (von or "")
    return _setze(
        db_path, projekt_name, release_version,
        "freigabe_status='in_pruefung', erstellt_von=?, eingereicht_am=aics_now(), "
        "gate_json=?, zurueckweisung_grund=''",
        (ersteller, json.dumps(gate or rec.get("gate") or {}, ensure_ascii=False)))


def zurueckweisen(db_path: Path, projekt_name: str, release_version: str,
                  von: str, grund: str) -> dict[str, Any]:
    """#1743: Prüfung mit Begründung zurückweisen (Compliance, CRA_APPROVE)."""
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Konformitätsbewertungs-Record vorhanden")
    if rec.get("freigabe_status") != "in_pruefung":
        raise ValueError("Zurückweisen ist nur in der Prüfung möglich")
    if len((grund or "").strip()) < MIN_GRUND:
        raise ValueError(
            f"Begründung erforderlich (mindestens {MIN_GRUND} Zeichen) — eine "
            f"Zurückweisung ohne Grund ist für den Einreicher nicht verwertbar")
    return _setze(
        db_path, projekt_name, release_version,
        "freigabe_status='zurueckgewiesen', geprueft_von=?, geprueft_am=aics_now(), "
        "zurueckweisung_grund=?",
        (von or "", grund.strip()))


def veroeffentlichen(db_path: Path, projekt_name: str, release_version: str) -> dict[str, Any]:
    """#1743: Freigegebenes Release als veröffentlicht markieren (Entwicklung)."""
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Konformitätsbewertungs-Record vorhanden")
    if rec.get("freigabe_status") != "freigegeben":
        raise ValueError("Veröffentlichen setzt eine Freigabe voraus")
    return _setze(db_path, projekt_name, release_version,
                  "freigabe_status='veroeffentlicht', veroeffentlicht_am=aics_now()", ())


def set_release_checkliste(db_path: Path, projekt_name: str, release_version: str,
                           item_id: str, status: str, begruendung: str,
                           von: str) -> dict[str, Any]:
    """#1744: Einen Punkt der Release-Checkliste setzen.

    Drei Regeln, jede mit einem Grund:

    * ``gerechnet``-Punkte sind nicht setzbar — wären sie es, ließe sich der
      Nachweis mit einem Klick erzeugen, statt ihn zu erbringen.
    * ``entscheidung``-Punkte brauchen eine Begründung, sobald sie nicht mehr
      offen sind. „Erledigt" ohne Begründung ist kein Nachweis, sondern ein Haken.
    * Nach dem Einreichen ist Schluss: Sonst prüft Compliance einen Stand, der
      sich unter der Hand noch ändert.
    """
    from cra import release_checkliste as rc

    item = rc.item(item_id)
    if item is None:
        raise ValueError(f"Unbekannter Prüfpunkt: {item_id}")
    if item.art == "gerechnet":
        raise ValueError(
            f"'{item.label}' wird aus den Daten der Anwendung gerechnet und "
            f"kann nicht von Hand gesetzt werden")
    if status not in rc.STATUS:
        raise ValueError(f"Unzulässiger Status: {status}")
    if status != "offen" and item_id in rc.BEGRUENDUNG_PFLICHT \
            and len((begruendung or "").strip()) < MIN_GRUND:
        raise ValueError(
            f"'{item.label}' braucht eine Begründung (mindestens {MIN_GRUND} Zeichen)")

    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Konformitätsbewertungs-Record vorhanden")
    if rec.get("freigabe_status") in GESPERRTE_STATUS:
        raise ValueError(
            f"Der Vorgang ist im Zustand '{rec.get('freigabe_status')}' gesperrt")

    stand = dict(rec.get("release_checkliste") or {})
    stand[item_id] = {"status": status, "begruendung": (begruendung or "").strip(),
                      "von": von or "", "am": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    return _setze(db_path, projekt_name, release_version,
                  "release_checkliste_json=?",
                  (json.dumps(stand, ensure_ascii=False),))


def set_release_art(db_path: Path, projekt_name: str, release_version: str,
                    art: str, von: str = "") -> dict[str, Any]:
    """#1793: Die Art des Releases erklären.

    **Ohne Begründungspflicht** — anders als bei der Kernfrage. Die Art ist eine
    Einordnung, die Begründung gehört zur Antwort auf die Kernfrage, und dort
    wird sie erzwungen. Zwei Begründungen zum selben Sachverhalt wären zwei
    Stellen, an denen dasselbe steht, und eine davon veraltet.

    Die Antwort auf die Kernfrage wird hier **nicht** mitgeschrieben. Der
    Vorschlag aus :func:`cra.release_art.vorschlag` geht in die Oberfläche;
    gespeichert wird er erst, wenn ihn jemand abschickt.
    """
    from cra import release_art as ra

    art = str(art or "").strip()
    if not ra.ist_gueltig(art):
        raise ValueError(f"Unbekannte Release-Art: {art!r}")
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Konformitätsbewertungs-Record vorhanden")
    if rec.get("freigabe_status") in GESPERRTE_STATUS:
        raise ValueError(f"Der Vorgang ist im Zustand "
                         f"'{rec.get('freigabe_status')}' gesperrt")
    return _setze(db_path, projekt_name, release_version,
                  "release_art=?, release_art_von=?, release_art_am=aics_now()",
                  (art, von or ""))


def set_wesentliche_aenderung(db_path: Path, projekt_name: str, release_version: str,
                              wert: str, grund: str,
                              von: str = "") -> dict[str, Any]:
    """#1744: Die Kernfrage des Vorgangs beantworten (Art. 3 Nr. 30).

    Beide Antworten brauchen eine Begründung — auch „nein". Gerade die Aussage
    „das war keine wesentliche Änderung" ist die, die später hinterfragt wird.
    """
    if wert not in ("ja", "nein"):
        raise ValueError("Wert muss 'ja' oder 'nein' sein")
    if len((grund or "").strip()) < MIN_GRUND:
        raise ValueError(
            f"Begründung erforderlich (mindestens {MIN_GRUND} Zeichen) — auch für 'nein'")
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Konformitätsbewertungs-Record vorhanden")
    if rec.get("freigabe_status") in GESPERRTE_STATUS:
        raise ValueError(f"Der Vorgang ist im Zustand "
                         f"'{rec.get('freigabe_status')}' gesperrt")
    rec = _setze(db_path, projekt_name, release_version,
                 "wesentliche_aenderung=?, wesentliche_aenderung_grund=?, "
                 "wesentliche_aenderung_von=?, wesentliche_aenderung_am=aics_now()",
                 (wert, grund.strip(), von or ""))
    if wert != "ja":
        return rec

    # #1755: „ja" löst aus, statt nur dokumentiert zu werden.
    # ``release_db.substantial_modification`` friert den bisherigen Stand ein und
    # öffnet die vier Neubewertungs-Punkte. Die Funktion existiert seit #1609 und
    # wurde von niemandem aufgerufen — die Frage wurde beantwortet und abgelegt,
    # und damit blieb folgenlos, was die Konformitätsbewertung erneut auslöst
    # (Art. 3 Nr. 30).
    #
    # Die Antwort ist oben bereits gespeichert; schlägt das Einfrieren fehl, geht
    # sie also nicht verloren. Der Fehler wird trotzdem durchgereicht, weil ein
    # „ja" ohne eingefrorenen Vorstand den Nachweis unvollständig lässt — still
    # weitermachen wäre hier das Schlechtere.
    from cra import release_db as _rdb

    try:
        _rdb.substantial_modification(db_path, projekt_name,
                                      neue_version=release_version, grund=grund.strip())
    except Exception as e:  # noqa: BLE001
        raise ValueError(
            f"Antwort gespeichert, aber der bisherige Stand konnte nicht "
            f"eingefroren werden ({type(e).__name__}: {e}). Die Neubewertungs-"
            f"Punkte fehlen dadurch — bitte erneut versuchen.") from e
    return get_konformitaet(db_path, projekt_name, release_version)


def freigeben(db_path: Path, projekt_name: str, release_version: str,
              von: str) -> dict[str, Any]:
    """#1220-A: Konformitäts-Record freigeben (Governance-Sign-off, CRA_APPROVE).

    Gate: nur bei abgeschlossenem Bewertungsweg. Setzt freigabe_status + Freigeber/Zeit;
    danach ist der Record gesperrt (Lock) bis zum reopen.

    #1743 (v8.0.0): Bei einem **versionierten** Vorgang setzt die Freigabe eine
    Einreichung voraus, und der Freigeber darf nicht der Einreicher sein. Ohne
    diese beiden Bedingungen ist die Vier-Augen-Prüfung eine Absprache und keine
    Eigenschaft der Anwendung — und genau das soll ein Nachweis belegen.

    Der Datensatz mit **leerer** ``release_version`` ist kein Release, sondern
    der Produkt-Datensatz: Bewertungsweg, Notified Body, CE. Dessen Sign-off ist
    Phase 1 und behält den Ablauf aus #1220-A — sonst müsste jede bestehende
    Installation ihren Produkt-Datensatz durch einen Prüfschritt schicken, den
    es für sie nie gab. Die zwei Phasen des Anwenders finden sich hier also
    direkt im Datenmodell wieder.
    """
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Konformitätsbewertungs-Record vorhanden")
    if rec.get("freigabe_status") in ("freigegeben", "veroeffentlicht"):
        raise ValueError("Record ist bereits freigegeben")
    if str(release_version or ""):
        if rec.get("freigabe_status") != "in_pruefung":
            raise ValueError(
                "Freigabe setzt eine Einreichung voraus — den Vorgang zuerst "
                "zur Prüfung geben")
        # #1780: Die Regel steht seit jetzt an einer Stelle (shared/vier_augen).
        # Sie war hier und im AI-Act-Modul doppelt formuliert — und im
        # DSGVO-Jahresbericht fehlte sie.
        vier_augen.pruefe(
            rec.get("erstellt_von"), von,
            erste_handlung="einreicht", zweite_handlung="freigeben",
            rechtsgrundlage="Verordnung (EU) 2024/2847, Art. 13 Abs. 1")
    if not rec.get("bewertung_abgeschlossen"):
        raise ValueError("Freigabe erst möglich, wenn der Bewertungsweg abgeschlossen ist")
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE cra_konformitaet
                   SET freigabe_status='freigegeben', freigegeben_von=?,
                       freigegeben_am=aics_now(), geprueft_von=?,
                       geprueft_am=aics_now(), zurueckweisung_grund='',
                       updated_at=aics_now()
                   WHERE projekt_name=? AND release_version=?""",
            (von or "", von or "", projekt_name, release_version),
        )
        con.commit()
    finally:
        con.close()
    return get_konformitaet(db_path, projekt_name, release_version)


def reopen(db_path: Path, projekt_name: str, release_version: str) -> dict[str, Any]:
    """#1220-A: Freigabe zurücksetzen (entsperren) → erneut editierbar."""
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Konformitätsbewertungs-Record vorhanden")
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE cra_konformitaet
                   SET freigabe_status='entwurf', freigegeben_von='', freigegeben_am=NULL,
                       updated_at=aics_now()
                   WHERE projekt_name=? AND release_version=?""",
            (projekt_name, release_version),
        )
        con.commit()
    finally:
        con.close()
    return get_konformitaet(db_path, projekt_name, release_version)


def list_konformitaet(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM cra_konformitaet WHERE projekt_name=? ORDER BY release_version",
            (projekt_name,),
        ).fetchall()
        return [_row(r) for r in rows]
    finally:
        con.close()
