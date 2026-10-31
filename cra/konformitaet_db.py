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
            # #1824: Womit wird Anhang I Teil II Nr. 3 belegt (regelmäßig und
            # wirksam testen)? Leer = unbestimmt, so steht jeder
            # Bestandsvorgang da. Die vier ``test_verzicht_*``-Spalten folgen
            # bewusst der Benennung der Risikoakzeptanz aus #1608/#1613
            # (``akzeptanz_grund``/``_von``/``_am``/``_review``) — es ist
            # dieselbe Art von Entscheidung, und sie soll sich auch so lesen.
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS verworfen_grund TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS verworfen_von TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS verworfen_am TEXT",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS testnachweis_art TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS test_verzicht_begruendung TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS test_verzicht_von TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS test_verzicht_am TEXT",
            "ALTER TABLE cra_konformitaet ADD COLUMN IF NOT EXISTS test_verzicht_review TEXT NOT NULL DEFAULT ''",
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
                   "veroeffentlicht", "verworfen")

#: #1876: Ein Vorgang, der doch nicht in Verkehr gebracht wird, ist **verworfen**
#: — nicht geloescht.
#:
#: Dies ist ein Nachweiswerkzeug. Dass eine Version erwogen und dann verworfen
#: wurde, ist selbst eine Aussage ueber das Produkt. Verschwindet die Zeile
#: spurlos, laesst sich spaeter nicht sagen, ob es den Vorgang nie gab oder ob
#: ihn jemand entfernt hat. Dieselbe Entscheidung steht hinter dem Soft-Delete
#: der finalisierten Gutachten (#969) und der Mandanten (#1808).
#:
#: **Nie aus `veroeffentlicht`:** Ein veroeffentlichtes Release ist in Verkehr;
#: seine Akte bleibt (Art. 13 Abs. 9 und 13).
VERWERFBAR_AUS = ("entwurf", "zurueckgewiesen", "in_pruefung", "freigegeben")

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


#: Felder der Konformitätsbewertung, die ein Release vom **Produkt** erbt.
#: Leer bzw. 0 heißt „am Release nicht eigens vermerkt" — dann gilt der Stand
#: des Produkt-Datensatzes (``release_version=''``). Siehe `_erbe_vom_produkt`.
#:
#: #1824: Die Entscheidung, **womit** Anhang I Teil II Nr. 3 belegt wird, gehört
#: ebenfalls dem Produkt — eine Teststrategie wird nicht je Release neu
#: gewählt. Die vier ``test_verzicht_*``-Felder erben nach derselben Regel
#: („leer heißt nicht eigens vermerkt"); sie werden ausschließlich gelesen,
#: wenn die *wirksame* Art ``kein_test`` ist, ein geerbter Rest bleibt also
#: ohne Wirkung. Ein eigener Wert am Release übersteuert weiter — nach einer
#: wesentlichen Änderung kann eigens zu testen sein.
GEERBTE_FELDER = ("bewertungsweg", "bewertung_abgeschlossen",
                  "nb_kennnummer", "eucc_level",
                  "testnachweis_art", "test_verzicht_begruendung",
                  "test_verzicht_von", "test_verzicht_am",
                  "test_verzicht_review")


#: Felder der Erklärung, die **nicht** vom Produkt geerbt werden (#1886).
#:
#: Alles andere in ``doc_json`` beschreibt Haus und Produkt — Hersteller,
#: Anschrift, Bevollmächtigter, angewandte Spezifikationen, Ort, Unterzeichner.
#: Diese drei beschreiben den **einzelnen Stand**, und geerbt wären sie eine
#: falsche Aussage über das Release:
#:
#: * ``produkt_charge`` — bezeichnet genau diesen Stand. Wird in
#:   ``doc_export.doc_daten`` aus der Version der Zeile abgeleitet.
#: * ``gegenstand`` — nennt Version und Image-Digest. Geerbt stünde in der
#:   Erklärung für 8.2.3 weiter „Release 8.0.11"; genau das war der gemeldete
#:   Fall aus #1885. Gefüllt wird er über den Vorschlag aus #1884.
#: * ``datum`` — das Ausstellungsdatum *dieser* Erklärung. Geerbt wäre es das
#:   der vorigen, und die Erklärung wäre vordatiert.
NICHT_GEERBTE_DOC_FELDER: tuple[str, ...] = ("produkt_charge", "gegenstand",
                                             "datum")


def _erbe_erklaerung(d: dict[str, Any], produkt: dict[str, Any],
                     quelle: dict[str, str]) -> None:
    """Den Inhalt der Erklärung vom Produkt übernehmen (#1886).

    **Der Befund:** ``doc_json`` stand nicht in :data:`GEERBTE_FELDER`. Die
    Zeile eines Release-Vorgangs war damit leer, und eine Eingabestelle dafür
    gab es nicht — dieselbe Form wie der Haken aus #1805, nur eine Ebene
    tiefer. Wer die Erklärung im Tagesgeschäft brauchte, pflegte sie am
    Produkt-Datensatz und tippte die Version von Hand.

    Geerbt wird **feldweise**, nicht als Block: Ein Vorgang, der eine eigene
    Anschrift oder eigene Normen trägt, behält sie. Und geerbt wird nur in ein
    *leeres* Feld — ein am Vorgang gesetzter Wert ist eine Aussage und wird
    nicht überschrieben.
    """
    # ``produkt`` ist die **Rohzeile** (``dict(p)``), nicht das Ergebnis von
    # ``_row`` — sie trägt ``doc_json`` als Text und kein ``doc``.
    pdoc = produkt.get("doc")
    if not isinstance(pdoc, dict):
        try:
            pdoc = json.loads(produkt.get("doc_json") or "{}")
        except Exception:  # noqa: BLE001
            pdoc = {}
    if not isinstance(pdoc, dict) or not pdoc:
        return
    eigen = d.get("doc") if isinstance(d.get("doc"), dict) else {}
    zusammen = dict(eigen)
    geerbt: list[str] = []
    for feld, wert in pdoc.items():
        if feld in NICHT_GEERBTE_DOC_FELDER:
            continue
        if wert in (None, "", [], {}, False):
            continue
        if zusammen.get(feld) in (None, "", [], {}, False):
            zusammen[feld] = wert
            geerbt.append(feld)
    d["doc"] = zusammen
    if geerbt:
        quelle["doc"] = "produkt"
        d["doc_geerbte_felder"] = sorted(geerbt)


def _erbe_vom_produkt(con: Any, projekt_name: str, d: dict[str, Any]) -> dict[str, Any]:
    """Die Konformitätsbewertung gehört dem Produkt, nicht dem einzelnen Release (#1805).

    **Der Befund aus dem Betrieb:** Die Meldung verwies auf einen Haken im Tab
    „✅ Konformität" — „dort pflegen was fehlt. Ich finde es nicht."

    Er konnte es nicht finden, weil es die Stelle nicht gab. ``cra_konformitaet``
    führt je ``(projekt, release_version)`` eine eigene Zeile; der Konformitäts-Tab
    pflegt ausschließlich die Zeile mit ``release_version=''`` — den
    **Produkt**-Datensatz (Phase 1 aus #1742). Für ein Release legt
    ``POST /releases/<version>`` eine **zweite** Zeile mit
    ``bewertung_abgeschlossen = 0`` an, und für die gab es keine Eingabestelle.
    Wer der Meldung folgte, setzte den Haken, bekam „gespeichert" — und das
    Release blieb unverändert gesperrt. Dieselbe Form wie #1796: Die Suite
    verlangte etwas, das sich durch Bedienung nicht erreichen ließ, nur noch
    heimtückischer, weil das Speichern Erfolg meldete.

    **Fachlich ist das Erben die richtige Richtung**, nicht eine zweite
    Eingabemaske: Das Verfahren nach Art. 32 / Anhang VIII wird für das
    *Produkt* durchlaufen. Erwägungsgrund 39 sagt für die Sicherheits-
    aktualisierung ausdrücklich, dass sie keine neue Konformitätsbewertung
    auslöst (#1792/#1793) — ein Haken je Release würde also genau das Gegenteil
    dessen verlangen, was die Verordnung sagt.

    **Dass die Release-Zeile die Spalten trotzdem trägt, bleibt richtig:** Nach
    einer wesentlichen Änderung ist die Bewertung für dieses Release eigens zu
    wiederholen. Nachgewiesen wird das über den Checklisten-Punkt
    ``neubewertung_konformitaetsbewertung`` (#1755) und nicht über diese Spalte —
    sie kann „nein" und „nicht gesetzt" nicht unterscheiden (``INTEGER NOT NULL
    DEFAULT 0``), wäre als Verneinung also nicht lesbar. Ein eigener Wert am
    Release übersteuert das Erben weiterhin.

    Geerbt wird **dynamisch beim Lesen**, nicht als Kopie beim Anlegen: Sonst
    bliebe jeder Bestandsvorgang auf seinem geerbten Nullwert sitzen — auf
    Produktiv steht genau so ein Vorgang (8.0.1) und war nicht freigebbar.
    """
    quelle = {f: "release" for f in GEERBTE_FELDER}
    p = con.execute(
        "SELECT * FROM cra_konformitaet WHERE projekt_name=? AND release_version=''",
        (projekt_name,),
    ).fetchone()
    if p:
        produkt = dict(p)
        for feld in GEERBTE_FELDER:
            # „Nicht eigens vermerkt" = leerer String bzw. 0/False. Beim
            # Bewertungsweg ist das nie der Fall (NOT NULL, beim Anlegen
            # vorbelegt) — er wird deshalb beim Anlegen gesetzt, siehe
            # `save_konformitaet`; hier fängt der Zweig nur Altzeilen auf.
            if not d.get(feld) and produkt.get(feld):
                d[feld] = produkt[feld]
                quelle[feld] = "produkt"
        _erbe_erklaerung(d, produkt, quelle)
    d["bewertung_abgeschlossen"] = bool(d.get("bewertung_abgeschlossen"))
    d["soll_nachweise"] = CHECKLISTE.get(d.get("bewertungsweg", "A"), [])
    # Damit die Oberfläche sagen kann, woher der Stand kommt: Ein geerbter Haken
    # ohne diese Auskunft sieht wie eine Eingabe am Release aus.
    d["geerbt_vom_produkt"] = sorted(f for f, q in quelle.items() if q == "produkt")
    return d


def get_konformitaet(db_path: Path, projekt_name: str, release_version: str = "",
                     *, erben: bool = True) -> Optional[dict[str, Any]]:
    """Den Datensatz lesen — standardmäßig mit dem vom Produkt geerbten Stand.

    ``erben=False`` liefert die Zeile, wie sie in der Tabelle steht. Das braucht
    ``save_konformitaet``: Würde es den geerbten Wert zurückschreiben, wäre das
    Erben nach dem ersten Speichern eine Kopie, und eine späterere Änderung am
    Produkt zöge nicht mehr nach.
    """
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        r = con.execute(
            "SELECT * FROM cra_konformitaet WHERE projekt_name=? AND release_version=?",
            (projekt_name, release_version),
        ).fetchone()
        if not r:
            return None
        d = _row(r)
        if release_version and erben:
            d = _erbe_vom_produkt(con, projekt_name, d)
        else:
            d["geerbt_vom_produkt"] = []
        return d
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
    # #1220-A: freigegebener Record ist gesperrt (Lock) — erst reopen nötig.
    # Bleibt die **erste** inhaltliche Prüfung: Bei einem gesperrten Record ist
    # „erst zurücksetzen" die Auskunft, die weiterhilft, und nicht eine
    # Beanstandung an Angaben, die ohnehin nicht geschrieben werden.
    existing = get_konformitaet(db_path, projekt_name, release, erben=False)
    if existing and existing.get("freigabe_status") == "freigegeben":
        raise ValueError("Record ist freigegeben und gesperrt — erst zurücksetzen (reopen)")

    # #1805: Teil-Update — was der Aufrufer nicht nennt, behält seinen Wert.
    # Vorher schrieb jedes Speichern `data.get(feld, "")`. Das Konformitäts-
    # Formular nennt `notizen` nicht, also leerte **jedes** Speichern im Tab die
    # Notizen des Datensatzes, ohne dass das irgendwo zu sehen war. Dieselbe
    # Klasse wie der `artefakt`-Verlust in #1771 und der `meta_json`-Verlust in
    # #1540 — und wie dort gehört der Schutz in die Speicherfunktion und nicht
    # in jeden Aufrufer.
    #
    # Ausdrücklich leer geschickt bleibt leer. Nur so bleibt die #1759-Prüfung
    # unten wirksam, die „abgeschlossen" mit geleerter NB-Angabe ablehnt: Sie
    # soll die Eingabe beanstanden, nicht einen Altwert durchwinken.
    def feld(name: str, default: Any = "") -> Any:
        if name in data:
            return data[name]
        return (existing or {}).get(name, default)

    ce_status = feld("ce_status") or "offen"
    if ce_status not in CE_STATUS:
        raise ValueError(f"Ungültiger CE-Status: {ce_status}")
    abgeschlossen = 1 if feld("bewertung_abgeschlossen") else 0
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
        # #1805: Für eine **neue Release-Zeile** gilt der Weg des Produkts, nicht
        # der erste zulässige der Klasse. Sonst trägt der Release-Vorgang einen
        # anderen Weg als die Akte, aus der er hervorgeht: Bei einem Produkt mit
        # Modul H stand im Vorgang „B+C", weil das der erste zulässige ist —
        # eine Abweichung, die niemand eingegeben hat und die im Nachweis wie
        # eine Entscheidung aussieht. Nur ein für die Klasse **zulässiger**
        # Produkt-Weg wird übernommen, sonst ließe eine unzulässige Altangabe am
        # Produkt kein Release mehr anlegen (die Falle aus #1759).
        weg = str((existing or {}).get("bewertungsweg") or "")
        if not weg and release:
            produkt_weg = str((get_konformitaet(db_path, projekt_name, "") or {})
                              .get("bewertungsweg") or "")
            if produkt_weg and not _req.weg_ablehnung(klasse, produkt_weg):
                weg = produkt_weg
        weg = weg or _req.zulaessige_wege(klasse)[0]
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
        mangel = _req.abschluss_mangel(weg, feld("nb_kennnummer"),
                                       feld("eucc_level"))
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
             json.dumps(feld("checkliste", {}) or {}, ensure_ascii=False),
             abgeschlossen, feld("nb_kennnummer"), feld("eucc_level"),
             ce_status, feld("notizen"),
             (feld("ce_angebracht_am") or None), feld("ce_ort"), feld("ce_nachweis")),
        )
        con.commit()
    finally:
        con.close()
    return get_konformitaet(db_path, projekt_name, release)


# ── Anhang I Teil II Nr. 3: Sicherheitstests (#1824) ─────────────────────────
#
# Eigener Schreibweg und **nicht** ein paar Felder mehr in ``save_konformitaet``.
# Zwei Gründe, beide aus der Sache:
#
# * Der Verzicht trägt Person und Zeitpunkt. Die stempelt der Server, nicht das
#   Formular — eine Entscheidung, deren Urheber der Browser mitschickt, ist
#   keine (dieselbe Überlegung wie bei ``set_release_art``, #1793).
# * ``save_konformitaet`` schreibt die Spalten damit gar nicht. Ein Speichern im
#   Konformitäts-Formular kann sie also auch nicht leeren — der Schutz aus
#   #1805/#1771/#1540 ergibt sich hier aus dem getrennten Weg statt aus einem
#   weiteren ``feld()``-Rückfall.

def pruefe_sicherheitstests(art: str, begruendung: str, review: str) -> str:
    """Prüft die Eingabe. Leerer Rückgabewert = in Ordnung, sonst der Mangel.

    Serverseitig, nicht nur im Formular (Lehre aus #1760/#1762/#1814): Ein
    Verzicht ohne Begründung ist in der Akte keine Entscheidung, sondern eine
    Lücke mit einem Haken davor — und die Pflichtangabe nur im Browser zu
    prüfen hieße, sie über die API wegzulassen zu können.
    """
    from cra import sicherheitstests as st

    art = str(art or "").strip()
    if art and art not in st.ARTEN:
        return (f"Unbekannte Art des Testnachweises: {art!r} — "
                f"zulässig: {', '.join(st.ARTEN)}")
    if art != "kein_test":
        return ""
    if len(str(begruendung or "").strip()) < st.MIN_BEGRUENDUNG:
        return ("Der Verzicht auf eigene Sicherheitstests ist zu begründen "
                f"(mindestens {st.MIN_BEGRUENDUNG} Zeichen). Anhang I Teil II "
                "Nr. 3 verlangt regelmäßiges und wirksames Testen; die "
                "Entscheidung dagegen bleibt im Nachweis sichtbar.")
    review = str(review or "").strip()[:10]
    if not review:
        return ("Für den Verzicht ist eine Wiedervorlage anzugeben — ohne "
                "Ablaufdatum wäre er eine Dauerentscheidung.")
    try:
        datetime.strptime(review, "%Y-%m-%d")
    except ValueError:
        return f"Wiedervorlage ist kein gültiges Datum (JJJJ-MM-TT): {review!r}"
    return ""


def set_sicherheitstests(db_path: Path, projekt_name: str, release_version: str,
                         data: dict, *, von: str = "") -> dict[str, Any]:
    """Art des Testnachweises setzen (und beim Verzicht dessen Begründung).

    Gepflegt wird der **Produkt**-Datensatz (``release_version=''``); ein
    Release erbt ihn (#1805). Der Parameter bleibt, weil nach einer
    wesentlichen Änderung für ein einzelnes Release eigens zu entscheiden sein
    kann.
    """
    ensure_table(db_path)
    art = str(data.get("testnachweis_art") or "").strip()
    begruendung = str(data.get("test_verzicht_begruendung") or "").strip()
    review = str(data.get("test_verzicht_review") or "").strip()[:10]
    mangel = pruefe_sicherheitstests(art, begruendung, review)
    if mangel:
        raise ValueError(mangel)
    bestand = get_konformitaet(db_path, projekt_name, release_version, erben=False)
    if not bestand:
        # Ohne Datensatz gibt es nichts zu ergänzen — er entsteht beim ersten
        # Speichern der Konformitätsbewertung bzw. beim Anlegen des Vorgangs.
        save_konformitaet(db_path, projekt_name,
                          {"release_version": release_version})
    if art != "kein_test":
        # Der Verzicht wird mitgelöscht: Stünde seine Begründung noch da,
        # nachdem jemand auf „externer Pentest" umgestellt hat, trüge die Akte
        # eine Erklärung für eine Entscheidung, die niemand mehr trifft.
        begruendung, review, von = "", "", ""
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE cra_konformitaet
                  SET testnachweis_art=?, test_verzicht_begruendung=?,
                      test_verzicht_review=?, test_verzicht_von=?,
                      test_verzicht_am=?, updated_at=aics_now()
                WHERE projekt_name=? AND release_version=?""",
            (art, begruendung, review, von,
             (datetime.now(timezone.utc).isoformat(timespec="seconds")
              if art == "kein_test" else None),
             projekt_name, release_version))
        con.commit()
    finally:
        con.close()
    return get_konformitaet(db_path, projekt_name, release_version)


def _pruefe_anhang_v(db_path: Path, projekt_name: str, release_version: str,
                     doc: dict, rec: dict,
                     bestaetigt: tuple[str, ...] | list[str] = ()) -> None:
    """Die Pflichtangaben nach Anhang V — oder eine Meldung, die sie nennt (#1814).

    Geprüft wird der Stand **nach** dem Speichern: `doc_daten` führt den
    übergebenen Entwurf mit den Stammdaten zusammen (Hersteller, Produktname,
    NB-Kennnummer stehen dort ohnehin). So beanstandet die Prüfung nur, was
    wirklich fehlt, und nicht, was der Aufrufer schlicht nicht mitgeschickt hat.

    Scheitert die Prüfung selbst — etwa weil der Anhang-V-Katalog nicht lesbar
    ist —, wird **nicht** ausgestellt. Eine Konformitätserklärung, deren
    Vollständigkeit niemand bestätigen konnte, ist das Gegenteil eines
    Nachweises; hier ist fail-closed die einzige vertretbare Richtung (#1751).
    """
    from cra import doc_export as _de

    zusammen = dict(rec.get("doc") or {})
    zusammen.update(doc or {})
    try:
        daten = _de.doc_daten(db_path, projekt_name, release_version or None)
        vorhanden = dict(daten.get("doc") or {})
        vorhanden.update(zusammen)
        nb = _req.weg_braucht_notifizierte_stelle(str(rec.get("bewertungsweg") or ""))
        fehlend = _de.fehlende_pflichtfelder(vorhanden, nb_pflichtig=nb)
    except Exception as e:  # noqa: BLE001
        raise ValueError(
            "Die Pflichtangaben nach Anhang V konnten nicht geprüft werden — "
            f"die Erklärung wurde nicht ausgestellt ({type(e).__name__}).") from e
    if fehlend:
        namen = "; ".join(
            f"Nr. {f.get('nr')} {f.get('bezeichnung')}" for f in fehlend[:6])
        raise ValueError(
            "Die EU-Konformitätserklärung ist ohne diese Pflichtangaben nach "
            f"Anhang V unwirksam: {namen}"
            + (" …" if len(fehlend) > 6 else ""))

    # #1885: Vollständig ist nicht widerspruchsfrei. `fehlende_pflichtfelder`
    # prüft ausschließlich Leere — ein Feld, das gefüllt ist und „sha256:…"
    # oder eine Version enthält, die der eigenen Akte widerspricht, war für
    # diese Prüfung vollständig. Genau das kam aus dem Betrieb zurück, und
    # zwar als **KI-Bemerkung nach** dem Dokument: ein Befund, der einen Lauf
    # kostet und nicht zuverlässig wiederkehrt.
    #
    # Geprüft wird hier, weil diese Funktion das eine Tor ist (#1814): Der
    # REST-Endpunkt und jeder andere Aufrufer von `issue_doc` gehen durch sie.
    from cra import doc_pruefung as _pr

    try:
        befunde = _pr.befunde(db_path, projekt_name, release_version or "",
                              doc=zusammen)
    except Exception as e:  # noqa: BLE001
        # Fail-closed wie oben: Eine Erklärung, deren Widerspruchsfreiheit
        # niemand bestätigen konnte, ist das Gegenteil eines Nachweises (#1751).
        raise ValueError(
            "Die Erklärung konnte nicht auf Widersprüche geprüft werden — sie "
            f"wurde nicht ausgestellt ({type(e).__name__}).") from e
    if _pr.blockierend(befunde):
        raise _pr.ErklaerungUnstimmig(_pr.blockierend(befunde))
    offen = [b for b in _pr.bestaetigungen(befunde)
             if b.get("confirm") not in set(bestaetigt or ())]
    if offen:
        raise _pr.BestaetigungErforderlich(offen)


def save_doc(db_path: Path, projekt_name: str, doc: dict,
             release_version: str = "") -> dict[str, Any]:
    """Die Erklärung als **Entwurf** speichern (#1887).

    **Der Mangel, den das behebt:** ``doc_json`` wurde ausschließlich von
    :func:`issue_doc` geschrieben — und die verlangt alle Pflichtangaben nach
    Anhang V. Wer die Erklärung ausfüllte und noch nicht ausstellen konnte
    (weil eine Angabe fehlt oder der Bewertungsweg nicht abgeschlossen ist),
    verlor beim nächsten Laden alles. Dieselbe Form wie #1805: Die Oberfläche
    bot eine Eingabe an, die nirgends ankam.

    **Teil-Update**, kein Ersetzen: Wer ein Feld nachreicht, soll die übrigen
    nicht verlieren (die Falle aus #1540/#1771/#1805). Ausdrücklich leer
    geschickt bleibt leer — sonst könnte eine Angabe nicht zurückgenommen
    werden.

    ``doc_version`` und ``doc_ausgestellt`` bleiben **unberührt**: Ein Entwurf
    ist keine Fassung. Ein Datensatz, dessen Fassungsnummer beim Tippen
    hochläuft, behauptet Ausstellungen, die nie stattgefunden haben.
    """
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Konformitätsbewertungs-Record vorhanden")
    # Der geerbte Stand ist die Grundlage (#1886) — sonst schreibt das erste
    # Speichern am Release die geerbten Felder als Leerwerte fest.
    zusammen = dict(rec.get("doc") or {})
    zusammen.update(doc or {})
    con = _connect(db_path)
    try:
        con.execute(
            """UPDATE cra_konformitaet SET doc_json=?, updated_at=aics_now()
               WHERE projekt_name=? AND release_version=?""",
            (json.dumps(zusammen, ensure_ascii=False), projekt_name,
             release_version))
        con.commit()
    finally:
        con.close()
    return get_konformitaet(db_path, projekt_name, release_version)


def issue_doc(db_path: Path, projekt_name: str, doc: dict,
              release_version: str = "",
              bestaetigt: tuple[str, ...] | list[str] = ()) -> dict[str, Any]:
    """Annex-V-DoC ausstellen — Gate: Bewertungsweg **und** Pflichtangaben.

    Erhöht ``doc_version``, setzt CE-Status auf ``doc_ausgestellt``.

    #1814: Bis v8.0.11 prüfte diese Funktion **nur** den Bewertungsweg. Ein
    leeres Dokument (``{}``) wurde angenommen und setzte ``doc_ausgestellt=1``,
    ``ce_status='doc_ausgestellt'`` und ``doc_version+1`` — das Gate las das
    und schaltete auf **grün**. Eine Erklärung ohne Produktidentifikation
    (Anhang V Nr. 1), ohne Hersteller (Nr. 2) und ohne Unterzeichner (Nr. 8)
    ist jedoch unwirksam; die Akte behauptete damit etwas, das der
    Marktüberwachung nicht vorgelegt werden könnte.

    #1753 hatte die Prüfung bereits gebaut — nur an einer zweiten Stelle
    (``cra.doc_export.ausstellen``), und der ältere Weg hier blieb daneben
    stehen. Zwei Entstehungswege für dieselbe Aussage sind zwei Wahrheiten
    (dieselbe Lehre wie #1726/#1727 und #1776). Geprüft wird deshalb mit
    **derselben** Funktion, nicht mit einer nachgebauten.
    """
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Konformitätsbewertungs-Record vorhanden")
    if not rec.get("bewertung_abgeschlossen"):
        raise ValueError("DoC erst ausstellbar, wenn der Bewertungsweg abgeschlossen ist")
    _pruefe_anhang_v(db_path, projekt_name, release_version, doc, rec, bestaetigt)
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
    # #1803: Die harte Vorbedingung der Freigabe wird hier vorgezogen. Ein
    # Vorgang ohne abgeschlossenen Bewertungsweg kann später **zwangsläufig**
    # nicht freigegeben werden — ihn trotzdem einzureichen bindet eine
    # Prüfperson an etwas, das nur zurückgewiesen werden kann, und der
    # Einreicher erfährt den Grund erst über den Umweg einer Zurückweisung.
    #
    # Die Ampel bleibt davon unberührt: Ein **rotes** Gate darf eingereicht
    # werden, denn genau darüber soll die Prüfung entscheiden (die Freigabe
    # verlangt dafür `confirm_rot`). Gesperrt ist nur, was die Freigabe
    # ausnahmslos verhindert.
    if not rec.get("bewertung_abgeschlossen"):
        raise ValueError(
            "Der Bewertungsweg ist nicht als abgeschlossen vermerkt — Haken "
            "„Bewertungsweg abgeschlossen“ im Tab „✅ Konformität“. Er gilt für "
            "das Produkt; jedes Release übernimmt ihn von dort. Ohne ihn kann "
            "das Release später nicht freigegeben werden.")
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


def verwerfen(db_path: Path, projekt_name: str, release_version: str,
              von: str, grund: str) -> dict[str, Any]:
    """#1876: Einen nicht veröffentlichten Release-Vorgang verwerfen.

    Nicht löschen, sondern verwerfen — die Begründung steht bei
    :data:`VERWERFBAR_AUS`. Die Person und der Zeitpunkt werden **hier**
    gestempelt, nicht vom Aufrufer übernommen: Eine Entscheidung, deren
    Urheber der Browser mitschickt, ist keine (Muster `set_release_art`,
    #1793).
    """
    if not str(release_version or "").strip():
        # Die Zeile mit leerer Version ist der PRODUKT-Datensatz (#1805).
        # Sie zu verwerfen nähme dem Produkt seine Konformitätsbewertung, und
        # jedes Release erbte anschließend ins Leere.
        raise ValueError("Der Produkt-Datensatz kann nicht verworfen werden — "
                         "nur ein Release-Vorgang")
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Release-Vorgang zu dieser Version vorhanden")
    status = str(rec.get("freigabe_status") or "entwurf")
    if status == "verworfen":
        return rec  # schon verworfen — idempotent, kein Fehler
    if status not in VERWERFBAR_AUS:
        raise ValueError(
            "Ein veröffentlichtes Release kann nicht verworfen werden — es ist "
            "in Verkehr, seine Akte bleibt (Art. 13 Abs. 9 und 13)")
    if len((grund or "").strip()) < MIN_GRUND:
        raise ValueError(
            f"Begründung erforderlich (mindestens {MIN_GRUND} Zeichen) — warum "
            f"ein Release nicht in Verkehr kam, ist Teil der Akte")
    return _setze(
        db_path, projekt_name, release_version,
        "freigabe_status='verworfen', verworfen_von=?, verworfen_am=aics_now(), "
        "verworfen_grund=?",
        (von or "", grund.strip()))


def wiederaufnehmen(db_path: Path, projekt_name: str, release_version: str,
                    von: str) -> dict[str, Any]:
    """#1876: Einen verworfenen Vorgang zurück in den Entwurf holen.

    Ein Irrtum beim Verwerfen soll nicht teurer sein als der Irrtum beim
    Anlegen. Die Begründung des Verwerfens bleibt stehen — sie dokumentiert,
    dass es den Vorgang gab; ein stiller Reset wäre genau die Spur, die hier
    nicht verloren gehen darf.
    """
    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec:
        raise ValueError("Kein Release-Vorgang zu dieser Version vorhanden")
    if str(rec.get("freigabe_status") or "") != "verworfen":
        raise ValueError("Nur ein verworfener Vorgang kann wiederaufgenommen werden")
    return _setze(db_path, projekt_name, release_version,
                  "freigabe_status='entwurf', geprueft_von=?", (von or "",))


def unberuehrt(db_path: Path, projekt_name: str, release_version: str) -> bool:
    """Hängt an diesem Vorgang nachweislich nichts? (#1876)

    Nur dann ist hartes Löschen vertretbar — das ist der Vertipper beim
    Anlegen („8.2.1" statt „8.2.2"), bei dem es nichts zu bewahren gibt.
    Geprüft wird gegen die **Daten**, nicht gegen den Status allein: eine
    Checklisten-Antwort, eine ausgestellte Erklärung, ein eingefrorener
    Snapshot oder ein Archiv-Eintrag sind jeweils eine Aussage.
    """
    import json as _json

    rec = get_konformitaet(db_path, projekt_name, release_version)
    if not rec or str(rec.get("freigabe_status") or "entwurf") != "entwurf":
        return False
    if int(rec.get("doc_ausgestellt") or 0):
        return False
    for feld in ("release_checkliste_json", "checkliste_json"):
        roh = rec.get(feld)
        if isinstance(roh, str):
            try:
                roh = _json.loads(roh or "{}")
            except Exception:  # noqa: BLE001
                return False  # unlesbar → im Zweifel bewahren
        if roh:
            return False
    try:
        from cra import release_db as _rdb
        if any(str(s.get("version") or "") == str(release_version)
               for s in (_rdb.list_snapshots(db_path, projekt_name) or [])):
            return False
    except Exception:  # noqa: BLE001 — kein Snapshot-Modul, kein Hinderungsgrund
        pass
    try:
        from cra import konformitaet_final_db as _fdb
        if any(str(a.get("version") or "") == str(release_version)
               for a in (_fdb.list_archiv(db_path, projekt_name) or [])):
            return False
    except Exception:  # noqa: BLE001
        pass
    return True


def loeschen(db_path: Path, projekt_name: str, release_version: str) -> None:
    """#1876: Einen **unberührten** Entwurf hart entfernen.

    Die Ausnahme, nicht die Regel: Alles, woran etwas hängt, wird verworfen
    (:func:`verwerfen`), nicht entfernt.
    """
    if not str(release_version or "").strip():
        raise ValueError("Der Produkt-Datensatz kann nicht gelöscht werden")
    if not unberuehrt(db_path, projekt_name, release_version):
        raise ValueError(
            "An diesem Vorgang hängen bereits Angaben — er kann verworfen, "
            "aber nicht gelöscht werden")
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM cra_konformitaet WHERE projekt_name=? "
                    "AND release_version=?", (projekt_name, release_version))
        con.commit()
    finally:
        con.close()


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
        raise ValueError(
            "Freigabe erst möglich, wenn der Bewertungsweg abgeschlossen ist — "
            "Haken „Bewertungsweg abgeschlossen“ im Tab „✅ Konformität“ (gilt "
            "für das Produkt, jedes Release übernimmt ihn von dort).")
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
