from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared import db as _sdb
from ai_compliance_suite.config import load_config as _load_suite_config
from shared.crypto_at_rest import EncryptionConfig, encrypt_bytes


DEFAULT_DB_PATH = Path("data/db/evidence.sqlite")
DEFAULT_STORE_DIR = Path("data/evidence")

#: Was eine Zeile über ihre Datei aussagt (#1974).
#:
#: ``ohne_datei`` ist bewusst **kein** Mangel: Ein Nachweis der Art ``web``
#: (``doc_kind='web'``, ``stored_path=''``) ist eine URL und hatte nie eine
#: Datei. Auf Produktiv sind das 35 von 69 Zeilen — sie als „fehlt" zu melden
#: wäre ein Befund, der die Hälfte des Bestands trifft, und ein Befund, der bei
#: allen anschlägt, wird abgeschaltet statt beachtet (#1774/#1877).
DATEI_VORHANDEN = "vorhanden"
DATEI_FEHLT = "fehlt"
OHNE_DATEI = "ohne_datei"


@dataclass
class EvidenceDocument:
    id: str
    filename: str
    stored_path: str
    source_path: str | None
    doc_type: str
    owner: str
    version: str
    tags: list[str]
    added_at: int
    updated_at: int
    doc_kind: str = "file"   # "file" | "web"
    url: str | None = None
    firmen_id: str = ""


@dataclass
class EvidenceChunkRow:
    doc_id: str
    chunk_idx: int
    text: str
    citation: dict[str, Any]
    created_at: int


@dataclass
class ApprovedMappingRow:
    requirement_id: str
    claim: str
    citations: list[dict[str, Any]]
    confidence: float
    rationale: str
    approved_by: str
    approved_at: int
    firmen_id: str = ""


SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_documents (
  id          TEXT PRIMARY KEY,
  filename    TEXT NOT NULL,
  stored_path TEXT NOT NULL,
  source_path TEXT,
  doc_type    TEXT NOT NULL DEFAULT '',
  owner       TEXT NOT NULL DEFAULT '',
  version     TEXT NOT NULL DEFAULT '',
  tags_json   TEXT NOT NULL DEFAULT '[]',
  added_at    INTEGER NOT NULL,
  updated_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ev_updated ON evidence_documents(updated_at DESC);

CREATE TABLE IF NOT EXISTS evidence_text (
  doc_id       TEXT PRIMARY KEY,
  text         TEXT NOT NULL,
  extracted_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_chunks (
  doc_id        TEXT NOT NULL,
  chunk_idx     INTEGER NOT NULL,
  text          TEXT NOT NULL,
  citation_json TEXT NOT NULL,
  created_at    INTEGER NOT NULL,
  PRIMARY KEY (doc_id, chunk_idx)
);
CREATE INDEX IF NOT EXISTS idx_ev_chunks_doc ON evidence_chunks(doc_id, chunk_idx);

CREATE TABLE IF NOT EXISTS evidence_mappings_approved (
  requirement_id TEXT NOT NULL,
  claim          TEXT NOT NULL,
  citations_json TEXT NOT NULL,
  confidence     REAL NOT NULL,
  rationale      TEXT NOT NULL,
  approved_by    TEXT NOT NULL,
  approved_at    INTEGER NOT NULL,
  PRIMARY KEY (requirement_id, claim)
);
CREATE INDEX IF NOT EXISTS idx_ev_map_req ON evidence_mappings_approved(requirement_id, approved_at DESC);

-- #1861: Die **Vorschlagsstufe**. Bewusst eine eigene Tabelle und nicht
-- `evidence_mappings_approved` mit leerem `approved_by`: Jeder Leser von
-- `list_approved_mappings` bekäme sonst Vermutungen als Belege serviert — und
-- dieser Leser ist der Nachweis-Block **jeder** KI-Bewertung (#1483). Eine
-- Tabelle, deren Name „freigegeben“ sagt und die Unfreigegebenes enthält, ist
-- genau die stille Bedeutungsverschiebung, die in #1805 so teuer war.
CREATE TABLE IF NOT EXISTS evidence_mappings_vorschlag (
  id             TEXT PRIMARY KEY,
  doc_id         TEXT NOT NULL,
  modul          TEXT NOT NULL DEFAULT '',
  requirement_id TEXT NOT NULL,
  claim          TEXT NOT NULL,
  citations_json TEXT NOT NULL DEFAULT '[]',
  confidence     REAL NOT NULL DEFAULT 0,
  rationale      TEXT NOT NULL DEFAULT '',
  firmen_id      TEXT NOT NULL DEFAULT '',
  provider       TEXT NOT NULL DEFAULT '',
  erzeugt_am     INTEGER NOT NULL,
  erzeugt_von    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_ev_vor_doc ON evidence_mappings_vorschlag(doc_id, erzeugt_am DESC);
CREATE INDEX IF NOT EXISTS idx_ev_vor_firma ON evidence_mappings_vorschlag(firmen_id, erzeugt_am DESC);
"""


def _connect(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer (#1332)."""
    return _sdb.connect(db_path)


def ensure_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    con = _connect(db_path)
    try:
        con.executescript(SCHEMA)

        def _has_col(table: str, col: str) -> bool:
            row = con.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name=? AND column_name=?",
                (table, col),
            ).fetchone()
            return bool(row)

        # #1003: Legacy-Spalte kunden_id → firmen_id umbenennen (Daten erhalten),
        # bevor firmen_id ggf. neu angelegt wird.
        for _tbl in ("evidence_documents", "evidence_mappings_approved"):
            if _has_col(_tbl, "kunden_id") and not _has_col(_tbl, "firmen_id"):
                try:
                    con.execute(f"ALTER TABLE {_tbl} RENAME COLUMN kunden_id TO firmen_id")
                except Exception:
                    pass

        # Migrations: add new columns if they don't exist yet (Postgres: ADD COLUMN IF NOT EXISTS)
        for _col_sql in [
            "ALTER TABLE evidence_documents ADD COLUMN IF NOT EXISTS doc_kind TEXT NOT NULL DEFAULT 'file'",
            "ALTER TABLE evidence_documents ADD COLUMN IF NOT EXISTS url TEXT",
            "ALTER TABLE evidence_documents ADD COLUMN IF NOT EXISTS firmen_id TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE evidence_mappings_approved ADD COLUMN IF NOT EXISTS firmen_id TEXT NOT NULL DEFAULT ''",
        ]:
            try:
                con.execute(_col_sql)
            except Exception:
                pass  # column already exists

        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_ev_firmen ON evidence_documents(firmen_id, updated_at DESC);"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_ev_map_firmen ON evidence_mappings_approved(firmen_id, requirement_id, approved_at DESC);"
        )
        con.commit()
    finally:
        con.close()


def _now_ts() -> int:
    return int(time.time())


def _safe_tags(tags: Any) -> list[str]:
    if not isinstance(tags, list):
        return []
    out: list[str] = []
    for t in tags:
        s = str(t).strip()
        if s:
            out.append(s)
    seen: set[str] = set()
    dedup: list[str] = []
    for t in out:
        if t not in seen:
            dedup.append(t)
            seen.add(t)
    return dedup


#: Was in einem Ablagenamen stehen darf. **Positivliste**, weil der Name zu
#: einem Pfad wird: Was nicht ausdrücklich erlaubt ist, fällt durch — auch in
#: einer Schreibweise, an die eine Negativliste nicht gedacht hat (die Lehre
#: aus #1784). Alles andere wird zu ``_``, nicht entfernt, damit aus
#: ``a/../b`` kein neuer Pfad entsteht, sondern ``a____b``.
_ABLAGE_ERLAUBT = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. ")


def _anzeigename(roh: str) -> str:
    """Der Name, den die Liste zeigt und den ein Download trägt (#1982).

    Verzeichnisanteile fallen weg (ein Browser schickt bei einem Ordner-Upload
    ``unterordner/datei.pdf``, und ein ``../`` hat hier nichts zu suchen),
    ebenso Steuerzeichen — ein Name mit Zeilenumbruch darin ist genau die
    „komische Anzeige", um die es geht. Gekürzt wird auf 255 Zeichen: Das ist
    die Grenze, die auch ein Dateisystem zieht.
    """
    name = Path(str(roh or "")).name
    name = "".join(c for c in name if c.isprintable()).strip()
    return "" if name in {".", ".."} else name[:255]


def _ablagename(anzeige: str) -> str:
    """Der Name, unter dem die Datei auf der Platte liegt (#1982).

    Vom Anzeigenamen getrennt: Umlaute und andere Schriftzeichen gehören in
    die Anzeige, aber nicht zwingend in einen Dateipfad — ein Dateisystem oder
    ein Archiv kann sie anders normalisieren, und dann findet der Datensatz
    seine Datei nicht mehr.
    """
    roh = Path(str(anzeige or "")).name
    sauber = "".join(c if c in _ABLAGE_ERLAUBT else "_" for c in roh).strip(" .")
    return sauber[:120]


def add_document(
    db_path: Path,
    source_file: Path,
    *,
    store_dir: Path = DEFAULT_STORE_DIR,
    doc_type: str = "",
    owner: str = "",
    version: str = "",
    tags: list[str] | None = None,
    copy_into_store: bool = True,
    firmen_id: str = "",
    filename: str = "",
) -> EvidenceDocument:
    """Ein Nachweisdokument ablegen.

    ``filename`` ist der **Anzeigename** (#1982). Ohne ihn gilt der Name der
    übergebenen Datei — und genau das war der Defekt: Die beiden
    Upload-Endpunkte schreiben den Upload in eine
    ``tempfile.NamedTemporaryFile`` und übergaben deren Pfad, also stand in der
    Akte ``tmpoqguoy01.md``. Der Name ist nicht nur Beschriftung: Er ist der
    ``download_name``, mit dem ein Anhang-VII-Beleg bei einer Behörde ankommt.
    """
    ensure_db(db_path)
    store_dir.mkdir(parents=True, exist_ok=True)

    src = Path(source_file)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(str(src))

    doc_id = str(uuid.uuid4())
    # Anzeigename und Ablagename sind zwei verschiedene Dinge, und das ist der
    # Kern dieser Stelle: Angezeigt und heruntergeladen gehört der Name, den
    # der Anwender vergeben hat — auf die Platte gehört einer, der als Pfad
    # unbedenklich ist. Sie zusammenzuwerfen kostet entweder die Lesbarkeit
    # (``secure_filename`` nimmt die Umlaute mit) oder die Sicherheit.
    filename = _anzeigename(filename) or _anzeigename(src.name) or src.name

    if copy_into_store:
        stored_name = f"{doc_id}_{_ablagename(filename) or src.name}"
        dst = store_dir / stored_name

        # Optional at-rest encryption for evidence files
        try:
            cfg = _load_suite_config()
            sec = cfg.get("security", {}) if isinstance(cfg, dict) else {}
            at = sec.get("at_rest_encryption", {}) if isinstance(sec, dict) else {}
            enc_cfg = EncryptionConfig(
                enabled=bool(at.get("enabled", False)),
                key_env=str(at.get("key_env", "AICS_AT_REST_KEY")),
                encrypt_backups=bool(at.get("encrypt_backups", True)),
                encrypt_evidence=bool(at.get("encrypt_evidence", False)),
            )
        except Exception:
            enc_cfg = EncryptionConfig(enabled=False, key_env="AICS_AT_REST_KEY")

        if enc_cfg.enabled and enc_cfg.encrypt_evidence:
            blob = encrypt_bytes(src.read_bytes(), key_env=enc_cfg.key_env)
            dst_enc = dst.with_suffix(dst.suffix + ".enc")
            dst_enc.write_bytes(blob)
            stored_path = str(dst_enc.as_posix())
            source_path = str(src)
        else:
            shutil.copy2(str(src), str(dst))
            stored_path = str(dst.as_posix())
            source_path = str(src)
    else:
        stored_path = str(src)
        source_path = None

    ts = _now_ts()
    tags_json = json.dumps(_safe_tags(tags or []), ensure_ascii=False)

    with _connect(db_path) as con:
        con.execute(
            """
            INSERT INTO evidence_documents (
              id, filename, stored_path, source_path, doc_type, owner, version,
              tags_json, added_at, updated_at, firmen_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (doc_id, filename, stored_path, source_path, doc_type or "", owner or "",
             version or "", tags_json, ts, ts, firmen_id or ""),
        )

    return EvidenceDocument(
        id=doc_id,
        filename=filename,
        stored_path=stored_path,
        source_path=source_path,
        doc_type=doc_type or "",
        owner=owner or "",
        version=version or "",
        tags=_safe_tags(tags or []),
        added_at=ts,
        updated_at=ts,
        firmen_id=firmen_id or "",
    )


def add_web_document(
    db_path: Path,
    url: str,
    title: str,
    text: str,
    *,
    doc_type: str = "web",
    owner: str = "",
    version: str = "",
    tags: list[str] | None = None,
    firmen_id: str = "",
) -> EvidenceDocument:
    """Register a web page as an evidence document and persist its text."""
    ensure_db(db_path)
    from urllib.parse import urlparse as _up
    hostname = _up(url).netloc or url[:60]
    filename = f"{hostname} – {title[:60]}" if title else hostname

    doc_id = str(uuid.uuid4())
    ts = _now_ts()
    tags_json = json.dumps(_safe_tags(tags or ["web"]), ensure_ascii=False)

    with _connect(db_path) as con:
        con.execute(
            """
            INSERT INTO evidence_documents
              (id, filename, stored_path, source_path, doc_type, owner, version,
               tags_json, added_at, updated_at, doc_kind, url, firmen_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'web', ?, ?)
            """,
            (doc_id, filename, "", None, doc_type or "web", owner or "", version or "",
             tags_json, ts, ts, url, firmen_id or ""),
        )
        con.execute(
            """
            INSERT INTO evidence_text (doc_id, text, extracted_at) VALUES (?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
              text=excluded.text,
              extracted_at=excluded.extracted_at
            """,
            (doc_id, text, ts),
        )

    return EvidenceDocument(
        id=doc_id,
        filename=filename,
        stored_path="",
        source_path=None,
        doc_type=doc_type or "web",
        owner=owner or "",
        version=version or "",
        tags=_safe_tags(tags or ["web"]),
        added_at=ts,
        updated_at=ts,
        doc_kind="web",
        url=url,
        firmen_id=firmen_id or "",
    )


def list_documents(db_path: Path, *, firmen_id: str | None = None) -> list[EvidenceDocument]:
    """List evidence documents. Pass firmen_id to restrict to a specific customer."""
    ensure_db(db_path)
    with _connect(db_path) as con:
        if firmen_id is not None:
            rows = con.execute(
                "SELECT * FROM evidence_documents WHERE firmen_id=? ORDER BY updated_at DESC, filename ASC",
                (firmen_id,),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM evidence_documents ORDER BY updated_at DESC, filename ASC"
            ).fetchall()
    out: list[EvidenceDocument] = []
    for r in rows:
        try:
            tags = json.loads(r["tags_json"]) if r["tags_json"] else []
        except Exception:
            tags = []
        keys = r.keys()
        out.append(
            EvidenceDocument(
                id=str(r["id"]),
                filename=str(r["filename"]),
                stored_path=str(r["stored_path"]),
                source_path=str(r["source_path"]) if r["source_path"] else None,
                doc_type=str(r["doc_type"] or ""),
                owner=str(r["owner"] or ""),
                version=str(r["version"] or ""),
                tags=_safe_tags(tags),
                added_at=int(r["added_at"]),
                updated_at=int(r["updated_at"]),
                doc_kind=str(r["doc_kind"]) if "doc_kind" in keys else "file",
                url=str(r["url"]) if "url" in keys and r["url"] else None,
                firmen_id=str(r["firmen_id"]) if "firmen_id" in keys and r["firmen_id"] else "",
            )
        )
    return out


def update_document_metadata(
    db_path: Path,
    doc_id: str,
    *,
    doc_type: str | None = None,
    owner: str | None = None,
    version: str | None = None,
    tags: list[str] | None = None,
) -> None:
    ensure_db(db_path)
    ts = _now_ts()
    with _connect(db_path) as con:
        row = con.execute("SELECT id FROM evidence_documents WHERE id=?", (doc_id,)).fetchone()
        if not row:
            raise KeyError(doc_id)
        if tags is not None:
            tags_json = json.dumps(_safe_tags(tags), ensure_ascii=False)
            con.execute(
                "UPDATE evidence_documents SET tags_json=?, updated_at=? WHERE id=?",
                (tags_json, ts, doc_id),
            )
        for col, val in [("doc_type", doc_type), ("owner", owner), ("version", version)]:
            if val is not None:
                con.execute(
                    f"UPDATE evidence_documents SET {col}=?, updated_at=? WHERE id=?",
                    (str(val), ts, doc_id),
                )


def delete_document(db_path: Path, doc_id: str, *, delete_file: bool = True) -> None:
    ensure_db(db_path)
    with _connect(db_path) as con:
        row = con.execute(
            "SELECT stored_path FROM evidence_documents WHERE id=?", (doc_id,)
        ).fetchone()
        if not row:
            return
        stored_path = str(row[0])
        con.execute("DELETE FROM evidence_documents WHERE id=?", (doc_id,))
        con.execute("DELETE FROM evidence_text WHERE doc_id=?", (doc_id,))
        con.execute("DELETE FROM evidence_chunks WHERE doc_id=?", (doc_id,))

    if delete_file:
        try:
            p = Path(stored_path)
            if p.exists() and p.is_file():
                os.remove(str(p))
        except Exception:
            pass


def upsert_extracted_text(db_path: Path, doc_id: str, text: str) -> None:
    ensure_db(db_path)
    ts = _now_ts()
    with _connect(db_path) as con:
        con.execute(
            """
            INSERT INTO evidence_text (doc_id, text, extracted_at)
            VALUES (?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
              text=excluded.text,
              extracted_at=excluded.extracted_at
            """,
            (doc_id, text or "", ts),
        )
        con.execute("UPDATE evidence_documents SET updated_at=? WHERE id=?", (ts, doc_id))


def get_extracted_text(db_path: Path, doc_id: str) -> str | None:
    ensure_db(db_path)
    with _connect(db_path) as con:
        row = con.execute("SELECT text FROM evidence_text WHERE doc_id=?", (doc_id,)).fetchone()
    return str(row[0]) if row else None


def get_document(db_path: Path, doc_id: str) -> EvidenceDocument | None:
    """Einzelnes Dokument anhand der ID (für Download/Anzeige, #1603)."""
    ensure_db(db_path)
    with _connect(db_path) as con:
        row = con.execute(
            "SELECT id, filename, stored_path, source_path, doc_type, owner, version, "
            "tags_json, added_at, updated_at, firmen_id FROM evidence_documents WHERE id=?",
            (doc_id,)).fetchone()
    if not row:
        return None
    try:
        tags = json.loads(row[7] or "[]")
    except Exception:  # noqa: BLE001
        tags = []
    return EvidenceDocument(
        id=str(row[0]), filename=str(row[1] or ""), stored_path=str(row[2] or ""),
        source_path=row[3], doc_type=str(row[4] or ""), owner=str(row[5] or ""),
        version=str(row[6] or ""), tags=tags, added_at=str(row[8] or ""),
        updated_at=str(row[9] or ""), firmen_id=str(row[10] or ""))


def replace_chunks(
    db_path: Path,
    doc_id: str,
    chunks: list[tuple[int, str]],
    *,
    citation_kind: str = "chunk",
) -> None:
    """Replace stored chunks for a document."""
    ensure_db(db_path)
    ts = _now_ts()
    with _connect(db_path) as con:
        con.execute("DELETE FROM evidence_chunks WHERE doc_id=?", (doc_id,))
        for idx, text in chunks:
            citation = {"kind": citation_kind, "doc_id": doc_id, "chunk": int(idx)}
            con.execute(
                """
                INSERT INTO evidence_chunks (doc_id, chunk_idx, text, citation_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (doc_id, int(idx), text or "", json.dumps(citation, ensure_ascii=False), ts),
            )
        con.execute("UPDATE evidence_documents SET updated_at=? WHERE id=?", (ts, doc_id))


def erschliessungsstand(db_path: Path, doc_ids: list[str]) -> dict[str, dict]:
    """Je Dokument: wie viele Abschnitte und wie viele Zeichen Volltext (#1984).

    **Eine** Abfrage für die ganze Liste, nicht eine je Zeile — die Lehre aus
    #1703/S6 (dort waren es 51 Roundtrips für 50 Mandanten).

    Gebraucht wird das, weil die Nachweisliste sonst nicht zeigt, ob ein
    Dokument lesbar ist: „Extrahieren" lief, gab 200 zurück und die Zeile sah
    danach aus wie vorher. Ein Knopf, dessen Wirkung man nicht sieht, ist für
    den Anwender ein Knopf ohne Wirkung (#1805/#1830).
    """
    ensure_db(db_path)
    ids = [str(d) for d in (doc_ids or []) if str(d or "").strip()]
    out: dict[str, dict] = {i: {"abschnitte": 0, "zeichen": 0} for i in ids}
    if not ids:
        return out
    platzhalter = ",".join("?" for _ in ids)
    with _connect(db_path) as con:
        for r in con.execute(
            f"SELECT doc_id, COUNT(*) AS n FROM evidence_chunks "
            f"WHERE doc_id IN ({platzhalter}) GROUP BY doc_id",  # nosec B608
            tuple(ids),
        ).fetchall():
            out[str(r["doc_id"])]["abschnitte"] = int(r["n"] or 0)
        for r in con.execute(
            f"SELECT doc_id, LENGTH(text) AS n FROM evidence_text "
            f"WHERE doc_id IN ({platzhalter})",  # nosec B608
            tuple(ids),
        ).fetchall():
            out[str(r["doc_id"])]["zeichen"] = int(r["n"] or 0)
    return out


def datei_vorhanden(stored_path: Any) -> bool:
    """Liegt die Datei dieses Nachweises da? (#1974)

    **Die eine Stelle, die das entscheidet** — und sie entscheidet es genau so,
    wie der Download und die Textextraktion es tun:
    ``server/api/cra_traceability.download_dokument`` prüft
    ``Path(stored).is_file()``, ``evidence.extract.extract_text`` dasselbe. Eine
    zweite, klügere Definition wäre die schlimmere Hälfte dieses Vorgangs:
    Sie würde „Datei fehlt" an Zeilen schreiben, die sich sehr wohl ausliefern
    lassen.

    Zwei Dinge, die hier bewusst **nicht** passieren:

    * **Kein Herumprobieren mit ``.enc``.** Die Verschlüsselung ist im
      ``stored_path`` enthalten: ``add_document`` schreibt ihn mit der Endung,
      und ``scripts/ops/nachweise_verschluesseln.py`` stellt ihn beim
      Nachverschlüsseln um. Läge nur ``<pfad>.enc`` auf der Platte, während die
      Datenbank den Klartextnamen nennt, wäre die Datei auch über den Download
      nicht erreichbar — „vorhanden" zu melden hieße dann, eine Lücke als
      Erfüllung auszugeben.
    * **Keine eigene Wurzel.** Ein relativer ``stored_path``
      (``data/evidence/…`` — so schreibt ``add_document`` ihn) wird gegen das
      Arbeitsverzeichnis aufgelöst, weil der Download es ebenso tut. Eine
      ``AICS_DATA_DIR``-Auflösung hier wäre eine zweite Wahrheit über denselben
      Pfad.
    """
    p = str(stored_path or "").strip()
    if not p:
        return False
    try:
        return Path(p).is_file()
    except OSError:
        # Ein unlesbarer Pfad (zu lang, kaputtes Encoding) ist nicht „vorhanden",
        # aber auch kein Grund, die Liste scheitern zu lassen.
        return False


def dateistand(dokumente: Any) -> dict[str, str]:
    """Je Dokument: ``vorhanden`` · ``fehlt`` · ``ohne_datei`` (#1974).

    DER BEFUND
    Auf Produktiv zeigten **31 von 34** Zeilen mit ``stored_path`` auf eine
    Datei, die es nicht gibt (Folge von #1808: die Übernahme brachte die
    Dateien erst nachträglich mit). Die Liste zählte 34 Nachweise, vorlegen
    ließen sich 3 — und nichts schlug fehl, es stand nur eine falsche Zahl an
    der Stelle, an der ein Prüfer sie liest.

    Nimmt die Zeilen, die der Aufrufer **schon hat** (``list_documents``),
    nicht eine Dokument-ID-Liste: Eine zweite Abfrage für Daten, die eine
    Zeile weiter oben liegen, ist der Anfang von #1703/S6.

    ZU DEN KOSTEN (gemessen, nicht geschätzt)
    Ein ``stat`` je Zeile. 34 Zeilen (die Produktiv-Zahl) in einem Ablageordner
    mit 2 000 Dateien: **0,20 ms**; 2 500 Zeilen: 15,8 ms. Der naheliegende
    Bündelungsversuch — ein ``listdir`` je Ordner und Mengenvergleich — war in
    beiden Fällen **langsamer** (0,48 ms bzw. 28,2 ms), weil der Ablageordner
    die Dateien *aller* Mandanten führt, die Liste aber die eines einzigen
    zeigt. Hier ist der einfache Weg auch der schnellere.
    """
    out: dict[str, str] = {}
    for d in dokumente or []:
        doc_id = d.get("id") if isinstance(d, dict) else getattr(d, "id", None)
        if doc_id is None:
            continue
        pfad = d.get("stored_path") if isinstance(d, dict) else getattr(d, "stored_path", "")
        if not str(pfad or "").strip():
            out[str(doc_id)] = OHNE_DATEI
            continue
        out[str(doc_id)] = DATEI_VORHANDEN if datei_vorhanden(pfad) else DATEI_FEHLT
    return out


def list_chunks(db_path: Path, doc_id: str) -> list[EvidenceChunkRow]:
    ensure_db(db_path)
    with _connect(db_path) as con:
        rows = con.execute(
            "SELECT doc_id, chunk_idx, text, citation_json, created_at FROM evidence_chunks WHERE doc_id=? ORDER BY chunk_idx ASC",
            (doc_id,),
        ).fetchall()
    out: list[EvidenceChunkRow] = []
    for r in rows:
        try:
            citation = json.loads(r["citation_json"]) if r["citation_json"] else {}
        except Exception:
            citation = {}
        out.append(
            EvidenceChunkRow(
                doc_id=str(r["doc_id"]),
                chunk_idx=int(r["chunk_idx"]),
                text=str(r["text"]),
                citation=citation if isinstance(citation, dict) else {},
                created_at=int(r["created_at"]),
            )
        )
    return out


def list_all_chunks(
    db_path: Path,
    *,
    limit: int = 800,
    firmen_id: str | None = None,
) -> list[EvidenceChunkRow]:
    """List chunks across all documents (most recently created first).

    Pass firmen_id to restrict to documents belonging to a specific customer.
    """
    ensure_db(db_path)
    lim = max(1, int(limit))
    with _connect(db_path) as con:
        if firmen_id is not None:
            rows = con.execute(
                """
                SELECT c.doc_id, c.chunk_idx, c.text, c.citation_json, c.created_at
                FROM evidence_chunks c
                JOIN evidence_documents d ON d.id = c.doc_id
                WHERE d.firmen_id = ?
                ORDER BY c.created_at DESC
                LIMIT ?
                """,
                (firmen_id, lim),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT doc_id, chunk_idx, text, citation_json, created_at FROM evidence_chunks ORDER BY created_at DESC LIMIT ?",
                (lim,),
            ).fetchall()
    out: list[EvidenceChunkRow] = []
    for r in rows:
        try:
            citation = json.loads(r["citation_json"]) if r["citation_json"] else {}
        except Exception:
            citation = {}
        out.append(
            EvidenceChunkRow(
                doc_id=str(r["doc_id"]),
                chunk_idx=int(r["chunk_idx"]),
                text=str(r["text"]),
                citation=citation if isinstance(citation, dict) else {},
                created_at=int(r["created_at"]),
            )
        )
    return out


def save_approved_mapping(
    db_path: Path,
    *,
    requirement_id: str,
    claim: str,
    citations: list[dict[str, Any]],
    confidence: float,
    rationale: str,
    approved_by: str,
    firmen_id: str = "",
) -> bool:
    """Eine Freigabe ablegen. Liefert ``True``, wenn sie **neu** ist (#1988).

    Der Schlüssel ist ``(requirement_id, claim)``, und der Konflikt wird
    aktualisiert. Trifft eine Freigabe auf einen gleichlautenden Beleg, ersetzt
    sie die frühere **samt Urheber und Zeitpunkt** — ohne dass es jemandem
    auffällt: Auf Produktiv standen 103 Freigaben im Revisionspfad und 91
    Zeilen in der Tabelle. Der Rückgabewert ist da, damit der Endpunkt es
    sagen kann.
    """
    ensure_db(db_path)
    rid = (requirement_id or "").strip()
    cl = (claim or "").strip()
    if not rid or not cl:
        raise ValueError("requirement_id and claim are required")
    ts = _now_ts()
    with _connect(db_path) as con:
        vorher = con.execute(
            "SELECT 1 FROM evidence_mappings_approved "
            "WHERE requirement_id=? AND claim=?", (rid, cl)).fetchone()
        con.execute(
            """
            INSERT INTO evidence_mappings_approved (
              requirement_id, claim, citations_json, confidence, rationale,
              approved_by, approved_at, firmen_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(requirement_id, claim) DO UPDATE SET
              citations_json=excluded.citations_json,
              confidence=excluded.confidence,
              rationale=excluded.rationale,
              approved_by=excluded.approved_by,
              approved_at=excluded.approved_at,
              firmen_id=excluded.firmen_id
            """,
            (
                rid,
                cl,
                json.dumps(citations or [], ensure_ascii=False),
                float(confidence),
                str(rationale or ""),
                str(approved_by or ""),
                ts,
                firmen_id or "",
            ),
        )
    return vorher is None


def freigegebene_zuordnungen(db_path: Path, *,
                             firmen_id: str = "") -> list[dict[str, Any]]:
    """Alle Freigaben einer Firma (#1988) — nicht je Anforderung.

    `list_approved_mappings` fragt **eine** Anforderung ab, weil der
    Nachweis-Block das so braucht. Eine Liste über die Firma gab es nicht, und
    damit gab es in der ganzen Anwendung **keine Stelle, die eine Freigabe
    zeigt**: Sie verschwindet aus dem Erschließungs-Dialog und erscheint
    nirgends wieder. Wer 36 Belege freigibt, kann seine Arbeit nicht
    nachsehen — und hält sie für verloren.
    """
    ensure_db(db_path)
    with _connect(db_path) as con:
        if firmen_id:
            rows = con.execute(
                "SELECT requirement_id, claim, citations_json, confidence, "
                "rationale, approved_by, approved_at, firmen_id "
                "FROM evidence_mappings_approved WHERE firmen_id=? "
                "ORDER BY requirement_id, approved_at DESC",
                (str(firmen_id),)).fetchall()
        else:
            rows = con.execute(
                "SELECT requirement_id, claim, citations_json, confidence, "
                "rationale, approved_by, approved_at, firmen_id "
                "FROM evidence_mappings_approved "
                "ORDER BY requirement_id, approved_at DESC").fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            zitate = json.loads(r["citations_json"]) if r["citations_json"] else []
        except Exception:  # noqa: BLE001
            zitate = []
        out.append({
            "requirement_id": str(r["requirement_id"]),
            "claim": str(r["claim"]),
            "citations": zitate if isinstance(zitate, list) else [],
            "confidence": float(r["confidence"]),
            "rationale": str(r["rationale"]),
            "approved_by": str(r["approved_by"]),
            "approved_at": int(r["approved_at"]),
        })
    return out


def list_approved_mappings(
    db_path: Path,
    requirement_id: str,
    *,
    firmen_id: str | None = None,
) -> list[ApprovedMappingRow]:
    """List approved mappings for a requirement.

    Pass firmen_id to restrict to a specific customer's approvals.
    """
    ensure_db(db_path)
    rid = (requirement_id or "").strip()
    if not rid:
        return []
    with _connect(db_path) as con:
        if firmen_id is not None:
            rows = con.execute(
                """
                SELECT requirement_id, claim, citations_json, confidence, rationale,
                       approved_by, approved_at, firmen_id
                FROM evidence_mappings_approved
                WHERE requirement_id=? AND firmen_id=?
                ORDER BY approved_at DESC
                """,
                (rid, firmen_id),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT requirement_id, claim, citations_json, confidence, rationale,
                       approved_by, approved_at, firmen_id
                FROM evidence_mappings_approved
                WHERE requirement_id=?
                ORDER BY approved_at DESC
                """,
                (rid,),
            ).fetchall()
    out: list[ApprovedMappingRow] = []
    for r in rows:
        try:
            citations = json.loads(r["citations_json"]) if r["citations_json"] else []
        except Exception:
            citations = []
        keys = r.keys()
        out.append(
            ApprovedMappingRow(
                requirement_id=str(r["requirement_id"]),
                claim=str(r["claim"]),
                citations=citations if isinstance(citations, list) else [],
                confidence=float(r["confidence"]),
                rationale=str(r["rationale"]),
                approved_by=str(r["approved_by"]),
                approved_at=int(r["approved_at"]),
                firmen_id=str(r["firmen_id"]) if "firmen_id" in keys and r["firmen_id"] else "",
            )
        )
    return out


def ersetze_vorschlaege(
    db_path: Path,
    doc_id: str,
    modul: str,
    vorschlaege: list[dict[str, Any]],
    *,
    firmen_id: str = "",
    provider: str = "",
    erzeugt_von: str = "",
) -> int:
    """Vorschläge eines Erschließungslaufs ablegen (#1861).

    **Ersetzt** die Vorschläge dieses Dokuments für dieses Modul: Ein zweiter
    Lauf ist eine neue Aussage über denselben Gegenstand, und zwei Generationen
    nebeneinander wären für den Freigebenden nicht unterscheidbar. Freigegebene
    Mappings bleiben unberührt — sie stehen in der anderen Tabelle und sind die
    Entscheidung eines Menschen.
    """
    import uuid as _uuid

    ensure_db(db_path)
    ts = _now_ts()
    with _connect(db_path) as con:
        con.execute(
            "DELETE FROM evidence_mappings_vorschlag WHERE doc_id=? AND modul=?",
            (str(doc_id), str(modul or "")),
        )
        n = 0
        for v in vorschlaege or []:
            rid = str((v or {}).get("requirement_id") or "").strip()
            claim = str((v or {}).get("claim") or "").strip()
            if not rid or not claim:
                continue
            try:
                conf = max(0.0, min(1.0, float(v.get("confidence") or 0)))
            except (TypeError, ValueError):
                conf = 0.0
            con.execute(
                """
                INSERT INTO evidence_mappings_vorschlag (
                  id, doc_id, modul, requirement_id, claim, citations_json,
                  confidence, rationale, firmen_id, provider, erzeugt_am, erzeugt_von
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (str(_uuid.uuid4()), str(doc_id), str(modul or ""), rid, claim,
                 json.dumps(v.get("citations") or [], ensure_ascii=False),
                 conf, str(v.get("rationale") or ""), firmen_id or "",
                 str(provider or ""), ts, str(erzeugt_von or "")),
            )
            n += 1
    return n


def list_vorschlaege(
    db_path: Path,
    *,
    doc_id: str | None = None,
    firmen_id: str | None = None,
    modul: str | None = None,
) -> list[dict[str, Any]]:
    """Offene Vorschläge — je Dokument, je Firma oder je Modul."""
    ensure_db(db_path)
    sql = ("SELECT id, doc_id, modul, requirement_id, claim, citations_json, "
           "confidence, rationale, firmen_id, provider, erzeugt_am, erzeugt_von "
           "FROM evidence_mappings_vorschlag WHERE 1=1")
    params: list[Any] = []
    if doc_id:
        sql += " AND doc_id=?"
        params.append(str(doc_id))
    if firmen_id is not None:
        sql += " AND firmen_id=?"
        params.append(str(firmen_id))
    if modul:
        sql += " AND modul=?"
        params.append(str(modul))
    sql += " ORDER BY confidence DESC, requirement_id ASC"
    with _connect(db_path) as con:
        rows = con.execute(sql, tuple(params)).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            cits = json.loads(r["citations_json"]) if r["citations_json"] else []
        except Exception:  # noqa: BLE001
            cits = []
        out.append({
            "id": str(r["id"]), "doc_id": str(r["doc_id"]),
            "modul": str(r["modul"]), "requirement_id": str(r["requirement_id"]),
            "claim": str(r["claim"]),
            "citations": cits if isinstance(cits, list) else [],
            "confidence": float(r["confidence"] or 0),
            "rationale": str(r["rationale"] or ""),
            "firmen_id": str(r["firmen_id"] or ""),
            "provider": str(r["provider"] or ""),
            "erzeugt_am": int(r["erzeugt_am"] or 0),
            "erzeugt_von": str(r["erzeugt_von"] or ""),
        })
    return out


def get_vorschlag(db_path: Path, vorschlag_id: str) -> dict[str, Any] | None:
    for v in list_vorschlaege(db_path):
        if v["id"] == str(vorschlag_id):
            return v
    return None


def loesche_vorschlag(db_path: Path, vorschlag_id: str) -> None:
    ensure_db(db_path)
    with _connect(db_path) as con:
        con.execute("DELETE FROM evidence_mappings_vorschlag WHERE id=?",
                    (str(vorschlag_id),))


def delete_approved_mapping(db_path: Path, requirement_id: str, claim: str) -> None:
    ensure_db(db_path)
    rid = (requirement_id or "").strip()
    cl = (claim or "").strip()
    if not rid or not cl:
        return
    with _connect(db_path) as con:
        con.execute(
            "DELETE FROM evidence_mappings_approved WHERE requirement_id=? AND claim=?",
            (rid, cl),
        )
