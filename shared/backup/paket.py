"""Das Archiv: schreiben, lesen, einspielen (#1785).

AUFBAU EINES ARCHIVS (Format 2)

``MANIFEST.json``
    Was drin ist, von wann, aus welcher Version — und die Zahlen, an denen man
    vor dem Einspielen erkennt, ob es das richtige Archiv ist.
``struktur.json``
    Das Gerüst der Datenbank (Schemata, Spalten, Constraints, Indizes,
    Sequenzstände).
``db/<schema>/<tabelle>.csv``
    Die Daten, je Tabelle eine Datei.
``dateien/<pfad>``
    Der Baum unter ``data/`` — Vorlagen, Gutachten, Nachweise, Zertifikate.
``config/<name>``
    Die Konfigurationsdateien, die außerhalb von ``data/`` liegen.

WARUM JE TABELLE EINE DATEI
Ein einziger großer Strom wäre kleiner, aber nicht lesbar: Hier kann man ein
Archiv öffnen und nachsehen, was drin ist, ohne es einzuspielen — und beim
Einspielen bleibt jede Tabelle ein eigener Schritt, dessen Fehlschlag man
benennen kann.

FORMAT 1 (bis v8.0.4)
Diese Archive enthielten ``data/db/*.sqlite`` und die Konfiguration. Sie werden
weiterhin **angenommen** und eingespielt (die Dateien landen zurück im
Datenverzeichnis), aber mit einem klaren Hinweis: Die Nutzdaten dieser
Installation liegen in PostgreSQL, und ein Format-1-Archiv enthält sie nicht.
Ohne diesen Hinweis sähe ein solcher Restore erfolgreich aus und wäre folgenlos
— genau der Befund, der zu diesem Modul geführt hat.
"""

from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.backup import dateien as f_dateien
from shared.backup import datenbank as f_db

FORMAT_VERSION = 2

#: Wo die Nutzdateien liegen. Über die Umgebung überschreibbar, damit Tests und
#: abweichende Installationen nicht auf das Arbeitsverzeichnis angewiesen sind.
def daten_wurzel() -> Path:
    return Path(os.environ.get("AICS_DATA_DIR", "data"))


class BackupFehler(RuntimeError):
    """Die Sicherung oder Wiederherstellung konnte nicht vollständig laufen."""


# ── Erstellen ───────────────────────────────────────────────────────────────

def _roh_verbindung():
    """Eine Verbindung ohne Schema-Bindung.

    ``shared.db.connect`` setzt den ``search_path`` auf ein Modul-Schema; für
    einen Lauf über alle Schemata ist das die falsche Sicht.
    """
    from shared.db import get_pool

    pool = get_pool()
    return pool, pool.getconn()


def _app_version() -> str:
    return os.environ.get("APP_VERSION", "") or "unbekannt"


def _db_kennung(cur) -> dict[str, Any]:
    cur.execute("SELECT current_database(), version()")
    name, version = cur.fetchone()
    return {"name": name, "server": str(version).split(" on ")[0]}


def erstelle_backup(ziel: Path, *, erstellt_von: str = "",
                    mit_dateien: bool = True) -> dict[str, Any]:
    """Vollständige Sicherung nach ``ziel`` schreiben.

    Geschrieben wird zuerst in eine Datei neben dem Ziel und erst am Ende
    umbenannt: Ein abgebrochener Lauf hinterlässt sonst ein Archiv, das wie
    eine fertige Sicherung aussieht.
    """
    ziel = Path(ziel)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    roh = ziel.with_suffix(ziel.suffix + ".unfertig")

    pool, conn = _roh_verbindung()
    hinweise: list[str] = []
    try:
        conn.rollback()
        cur = conn.cursor()
        struktur = f_db.struktur_lesen(cur)
        kennung = _db_kennung(cur)

        tabellen = zeilen = 0
        with zipfile.ZipFile(roh, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.writestr("struktur.json", f_db.struktur_nach_json(struktur))

            for schema, inhalt in struktur["schemata"].items():
                for tabelle, bau in inhalt["tabellen"].items():
                    spalten = [s["name"] for s in bau["spalten"]]
                    if not spalten:
                        continue
                    stuecke = list(f_db.daten_als_csv(conn, schema, tabelle, spalten))
                    zf.writestr(f"db/{schema}/{tabelle}.csv", b"".join(stuecke))
                    tabellen += 1
                    zeilen += f_db.zeilen_zahl(cur, schema, tabelle)

            datei_anzahl = datei_bytes = 0
            if mit_dateien:
                wurzel = daten_wurzel()
                for pfad, rel in f_dateien.sammle(wurzel):
                    try:
                        zf.write(pfad, f"dateien/{rel}")
                        datei_anzahl += 1
                        datei_bytes += pfad.stat().st_size
                    except OSError as e:
                        hinweise.append(f"Datei übersprungen: {rel} ({e})")

            cfg_anzahl = 0
            for cfg in _konfig_dateien():
                try:
                    zf.write(cfg, f"config/{cfg.name}")
                    cfg_anzahl += 1
                except OSError as e:
                    hinweise.append(f"Konfiguration übersprungen: {cfg.name} ({e})")

            manifest = {
                "format": FORMAT_VERSION,
                "created_at": datetime.now(tz=timezone.utc).isoformat(),
                "created_by": erstellt_von or "unbekannt",
                "app_version": _app_version(),
                "datenbank": {
                    **kennung,
                    "schemata": len(struktur["schemata"]),
                    "tabellen": tabellen,
                    "zeilen": zeilen,
                },
                "dateien": {"anzahl": datei_anzahl, "bytes": datei_bytes},
                "konfiguration": {"anzahl": cfg_anzahl},
                "hinweise": hinweise,
            }
            zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        os.replace(roh, ziel)
        manifest["groesse_bytes"] = ziel.stat().st_size
        return manifest
    except Exception:
        try:
            roh.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    finally:
        try:
            conn.rollback()
        finally:
            pool.putconn(conn)


def _konfig_dateien() -> list[Path]:
    """Konfiguration, die außerhalb des Datenverzeichnisses liegt.

    Im Container zeigt ``AICS_CONFIG_PATH`` nach ``data/`` — dann ist die Datei
    bereits über den Dateibaum gesichert und taucht hier nicht auf. In der
    Entwicklung liegt sie im Arbeitsverzeichnis.
    """
    raus: list[Path] = []
    wurzel = daten_wurzel().resolve()
    gesehen: set[str] = set()

    try:
        from ai_compliance_suite.config import DEFAULT_CONFIG_PATH
        kandidaten = [Path(DEFAULT_CONFIG_PATH)]
    except Exception:  # noqa: BLE001
        kandidaten = []
    kandidaten += sorted(Path(".").glob("*.config.json"))

    for pfad in kandidaten:
        if not pfad.exists() or not pfad.is_file():
            continue
        voll = pfad.resolve()
        if wurzel == voll or wurzel in voll.parents:
            continue  # steckt schon im Dateibaum
        if voll.name in gesehen:
            continue
        gesehen.add(voll.name)
        raus.append(pfad)
        sidecar = pfad.with_suffix(pfad.suffix + ".sha256")
        if sidecar.exists():
            raus.append(sidecar)
            gesehen.add(sidecar.name)
    return raus


# ── Lesen ───────────────────────────────────────────────────────────────────

def lies_manifest(archiv: Path) -> dict[str, Any]:
    """Das Manifest eines Archivs. Format 1 hat keins im heutigen Sinn."""
    with zipfile.ZipFile(archiv, "r") as zf:
        namen = zf.namelist()
        treffer = next((n for n in namen if n.lower() == "manifest.json"), None)
        if not treffer:
            raise BackupFehler("MANIFEST.json fehlt — das ist kein Suite-Backup")
        roh = json.loads(zf.read(treffer).decode("utf-8"))
    roh.setdefault("format", 1)
    return roh


def beschreibe(archiv: Path) -> dict[str, Any]:
    """Was in dem Archiv steckt — für die Anzeige **vor** dem Einspielen.

    Ein Restore überschreibt den Datenbestand. Wer ihn auslöst, soll vorher
    sehen, was er einspielt, statt sich auf einen Dateinamen zu verlassen.
    """
    manifest = lies_manifest(archiv)
    with zipfile.ZipFile(archiv, "r") as zf:
        namen = zf.namelist()
    tabellen = sum(1 for n in namen if n.startswith("db/") and n.endswith(".csv"))
    dateien = sum(1 for n in namen if n.startswith("dateien/") and not n.endswith("/"))
    alt_sqlite = sum(1 for n in namen if n.startswith("data/db/") and n.endswith(".sqlite"))

    info = {
        "format": manifest.get("format", 1),
        "created_at": manifest.get("created_at"),
        "app_version": manifest.get("app_version"),
        "tabellen": tabellen,
        "dateien": dateien,
        "zeilen": (manifest.get("datenbank") or {}).get("zeilen"),
        "warnungen": [],
    }
    if info["format"] < FORMAT_VERSION:
        info["warnungen"].append(
            "Archiv im alten Format: Es enthält die SQLite-Dateien "
            f"({alt_sqlite} Stück), nicht den Inhalt der PostgreSQL-Datenbank. "
            "Ein Einspielen stellt die Nutzdaten dieser Installation NICHT wieder her.")
    elif not tabellen:
        info["warnungen"].append("Das Archiv enthält keine Tabellendaten.")
    return info


# ── Einspielen ──────────────────────────────────────────────────────────────

#: Schemata, die zur **Installation** gehören und nicht zu den Fachdaten (#1813).
#:
#: Aus dem Betrieb: Ein Archiv der Testinstanz wurde auf der Produktivinstallation
#: eingespielt. Danach waren nicht nur Mandanten weg, sondern die Konten durch die
#: der Quelle **ersetzt** — samt deren Passkeys. Weil ein Passkey an die Domain
#: gebunden ist, verlangte das übernommene Konto einen zweiten Faktor, der unter
#: dem neuen Hostnamen nicht funktioniert: Der Betreiber war ausgesperrt.
#:
#: Konten, Audit-Trail und Zeitpläne gehören zu der Installation, auf der sie
#: laufen — nicht zu den Daten, die man hin- und herträgt.
INSTALLATIONS_SCHEMATA = frozenset({"users", "audit", "scheduler"})

#: Wählbarer Umfang beim Einspielen.
UMFAENGE = ("fachdaten", "alles", "nur_benutzer")


def _schema_gewollt(schema: str, umfang: str) -> bool:
    """Gehört dieses Schema zum gewählten Umfang?

    ``fachdaten``  — alles außer Konten, Audit und Zeitplänen (Vorauswahl)
    ``alles``      — der bisherige Vollumfang, für den echten Wiederanlauf
    ``nur_benutzer`` — nur Konten, etwa um Zugänge aus einer Sicherung zu holen
    """
    ist_installation = schema in INSTALLATIONS_SCHEMATA
    if umfang == "alles":
        return True
    if umfang == "nur_benutzer":
        return schema == "users"
    return not ist_installation


#: Tabellen, deren Zeilenzahl in der Vorschau etwas aussagt. Die vollständige
#: Liste wäre unleserlich; diese Handvoll beantwortet die Frage „was verliere
#: ich?" für die Dinge, die ein Betreiber vermisst.
_VORSCHAU_TABELLEN = (
    ("firmen", "firmen", "Mandanten"),
    ("cra", "cra_projekte", "CRA-Projekte"),
    ("nis2", "nis2_projekte", "NIS2-Projekte"),
    ("dsgvo", "dsgvo_projekte", "DSGVO-Projekte"),
    ("ai_act", "ai_act_projekte", "AI-Act-Projekte"),
    ("risikobewertung", "rb_projekte", "Risikobewertungen"),
    ("gutachten", "gutachten_projects", "Audit-/Gutachten-Projekte"),
    ("evidence", "evidence_documents", "Nachweisdokumente"),
    ("soc", "soc_alerts", "SOC-Alarme"),
    ("users", "users", "Benutzerkonten"),
)


def vergleiche(archiv: Path, *, umfang: str = "alles") -> dict[str, Any]:
    """Was das Einspielen ändern würde — **vor** dem Klick (#1809).

    Der Dialog fragte bisher, ob man sicher sei, sagte aber nicht, **was**
    verloren geht. Dabei weiß die Anwendung alles, was für die Antwort nötig
    ist: Das Archiv nennt seine Zeilenzahlen, das Ziel die eigenen.

    Aus dem Betrieb: Ein Archiv mit **einer** Firma wurde auf eine Installation
    mit **zwölf** eingespielt. Elf Mandanten waren weg, darunter ein echter
    Kunde. Eine Rückfrage ohne Zahlen ist keine Warnung, sondern eine
    Formalie.

    Liefert je Position die Zahl im Archiv, die Zahl im Ziel und die Differenz.
    Tabellen, die der gewählte ``umfang`` ausspart, erscheinen als
    ``betroffen: False`` — dort ändert sich nichts.
    """
    info = beschreibe(archiv)
    zeilen: list[dict[str, Any]] = []
    with zipfile.ZipFile(archiv, "r") as zf:
        vorhanden = set(zf.namelist())
        for schema, tabelle, label in _VORSCHAU_TABELLEN:
            eintrag = f"db/{schema}/{tabelle}.csv"
            im_archiv: int | None = _zeilen_im_archiv(zf, eintrag) \
                if eintrag in vorhanden else None
            im_ziel = _zeilen_im_ziel(schema, tabelle)
            betroffen = (eintrag in vorhanden) and _schema_gewollt(schema, umfang)
            zeilen.append({
                "schema": schema, "tabelle": tabelle, "bezeichnung": label,
                "im_archiv": im_archiv, "im_ziel": im_ziel,
                "betroffen": betroffen,
                "verlust": (max(0, (im_ziel or 0) - (im_archiv or 0))
                            if betroffen and im_ziel is not None else 0),
            })
    return {
        "archiv": info,
        "umfang": umfang,
        "positionen": zeilen,
        "verlust_gesamt": sum(z["verlust"] for z in zeilen),
        "installation_unberuehrt": umfang == "fachdaten",
    }


def _zeilen_im_archiv(zf: zipfile.ZipFile, eintrag: str) -> int:
    """Datensätze in einer Archiv-Tabelle zählen.

    Nicht über ``count(b"\\n")``: Ein CSV-Feld darf Zeilenumbrüche enthalten,
    und genau die Felder, um die es hier geht, tun das — eine Projekt- oder
    Firmenbeschreibung ist oft mehrzeilig. Gezählte Zeilen statt Datensätze
    hätten die Zahl im Archiv überhöht und damit den gemeldeten Verlust
    kleingerechnet: Der Dialog hätte „kein Verlust" gezeigt, wo Mandanten
    verschwinden. Eine falsche Zahl in einer Warnung ist schlimmer als keine.

    ``csv.reader`` kennt die Regel und liest strömend — es wird nichts
    zwischengespeichert.
    """
    import csv
    import io

    with zf.open(eintrag) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace", newline="")
        return sum(1 for _ in csv.reader(text))


def _zeilen_im_ziel(schema: str, tabelle: str) -> int | None:
    """Zeilenzahl im Ziel — ``None``, wenn es die Tabelle dort nicht gibt."""
    try:
        pool, conn = _roh_verbindung()
    except Exception:  # noqa: BLE001 — ohne Datenbank gibt es keine Vorschau
        return None
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s",
            (schema, tabelle))
        if not cur.fetchone():
            return None
        cur.execute(f'SELECT COUNT(*) FROM {f_db._q(schema, tabelle)}')  # nosec B608 — Bezeichner über _q
        return int((cur.fetchone() or [0])[0])
    except Exception:  # noqa: BLE001
        return None
    finally:
        # Die Verbindung zurückgeben, **nicht** den Pool schließen: Der Pool ist
        # der der ganzen Anwendung (`shared.db.get_pool`). Ihn hier zu schließen
        # nahm jedem folgenden Aufruf die Datenbank — in der laufenden
        # Installation unsichtbar, weil gunicorn den Prozess neu startet, im
        # Testlauf sofort als `PoolClosed`.
        try:
            conn.rollback()
            pool.putconn(conn)
        except Exception:  # noqa: BLE001
            pass


def stelle_wieder_her(archiv: Path, *, nur_datenbank: bool = False,
                      nur_dateien: bool = False,
                      umfang: str = "alles") -> dict[str, Any]:
    """Archiv einspielen. Liefert einen Bericht mit Zahlen und Warnungen.

    ``umfang`` steuert, **was** eingespielt wird (#1813):

    * ``alles`` — Vollumfang wie bisher; Vorgabe, damit vorhandene Aufrufer
      und gespeicherte Abläufe sich nicht ändern.
    * ``fachdaten`` — Firmen, Projekte, Bewertungen, Nachweise. Konten,
      Rollen, Gruppen, Passkeys, Audit-Trail und Zeitpläne der Zielinstallation
      bleiben unangetastet. Das ist der häufigere Fall; die Oberfläche wählt
      ihn vor.
    * ``nur_benutzer`` — nur das ``users``-Schema.

    Die Entscheidung gehört in die Hand dessen, der einspielt: Wer eine
    Sicherung einer **anderen** Installation übernimmt, will fast nie deren
    Zugänge — und merkt es erst, wenn er sich nicht mehr anmelden kann.
    """
    if umfang not in UMFAENGE:
        raise ValueError(f"Unbekannter Umfang: {umfang!r} (erlaubt: {', '.join(UMFAENGE)})")
    archiv = Path(archiv)
    manifest = lies_manifest(archiv)
    format_ = int(manifest.get("format", 1))

    if format_ < FORMAT_VERSION:
        return _wiederherstellen_format1(archiv, manifest)

    bericht: dict[str, Any] = {
        "format": format_, "tabellen": 0, "zeilen": 0, "dateien": 0,
        "konfiguration": 0, "warnungen": [],
    }

    with zipfile.ZipFile(archiv, "r") as zf:
        if not nur_dateien:
            _datenbank_einspielen(zf, bericht, umfang)
        if not nur_datenbank:
            _dateien_einspielen(zf, bericht)
            _konfig_einspielen(zf, bericht)

    return bericht


def _datenbank_einspielen(zf: zipfile.ZipFile, bericht: dict[str, Any],
                          umfang: str = "alles") -> None:
    """Struktur ergänzen, Daten ersetzen — in **einer** Transaktion.

    Entweder die ganze Datenbank steht hinterher auf dem Stand des Archivs oder
    sie ist unverändert. Ein halb eingespielter Datenbestand wäre das schlechteste
    Ergebnis: Er sieht aus wie ein Bestand.
    """
    try:
        struktur = f_db.struktur_aus_json(zf.read("struktur.json"))
    except KeyError:
        raise BackupFehler("struktur.json fehlt — Archiv unvollständig") from None

    _schema_der_anwendung(bericht)

    pool, conn = _roh_verbindung()
    try:
        conn.rollback()
        cur = conn.cursor()
        try:
            cur.execute("SET session_replication_role = replica")
        except Exception:  # noqa: BLE001 — braucht erhöhte Rechte
            conn.rollback()
            bericht["warnungen"].append(
                "Fremdschlüssel konnten nicht ausgesetzt werden (fehlende Rechte); "
                "bei Verweisen zwischen Tabellen kann das Einspielen scheitern.")

        bericht["warnungen"] += f_db.struktur_herstellen(conn, struktur)

        for name in sorted(zf.namelist()):
            if not (name.startswith("db/") and name.endswith(".csv")):
                continue
            teile = name[len("db/"):-len(".csv")].split("/")
            if len(teile) != 2:
                bericht["warnungen"].append(f"Eintrag übergangen: {name}")
                continue
            schema, tabelle = teile
            if not _schema_gewollt(schema, umfang):
                bericht.setdefault("uebersprungen", []).append(f"{schema}.{tabelle}")
                continue
            bau = (struktur.get("schemata", {}).get(schema, {})
                   .get("tabellen", {}).get(tabelle))
            if not bau:
                bericht["warnungen"].append(
                    f"{schema}.{tabelle}: keine Strukturangabe im Archiv — übersprungen")
                continue
            spalten = [s["name"] for s in bau["spalten"]]
            zeilen = f_db.tabelle_einspielen(
                conn, schema, tabelle, spalten, zf.read(name), bericht["warnungen"])
            bericht["tabellen"] += 1
            bericht["zeilen"] += zeilen

        f_db.sequenzen_setzen(conn, struktur, bericht["warnungen"])

        try:
            cur.execute("SET session_replication_role = origin")
        except Exception:  # noqa: BLE001
            pass
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def _schema_der_anwendung(bericht: dict[str, Any]) -> None:
    """Die Anwendung ihr eigenes Schema anlegen lassen — **vor** den Daten.

    Das ist der Kern der Bauweise: Nicht das Archiv bestimmt die Struktur,
    sondern die laufende Version. In einer frischen Installation existiert noch
    keine Tabelle; der Warmup legt sie mit allen Migrationen an, und erst was er
    nicht erfasst (Unter-Schemata, die sich sonst beim ersten Zugriff selbst
    anlegen), wird anschließend aus dem Archiv ergänzt.

    Läuft in eigenen Transaktionen und **vor** der großen Einspiel-Transaktion:
    Die Migrationen nehmen den globalen DDL-Lock (``shared/db``), der bis zum
    Ende seiner Transaktion gilt.
    """
    try:
        from shared.warmup import warm_schemas

        ergebnis = warm_schemas()
        if ergebnis.get("fail"):
            bericht["warnungen"].append(
                f"{ergebnis['fail']} Modul(e) konnten ihr Schema nicht vorab anlegen — "
                "fehlende Tabellen werden aus dem Archiv ergänzt.")
    except Exception as e:  # noqa: BLE001 — der Restore soll daran nicht scheitern
        bericht["warnungen"].append(f"Schema-Vorlauf übersprungen ({e}).")


def _dateien_einspielen(zf: zipfile.ZipFile, bericht: dict[str, Any]) -> None:
    wurzel = daten_wurzel()
    wurzel.mkdir(parents=True, exist_ok=True)
    for name in zf.namelist():
        if not name.startswith("dateien/") or name.endswith("/"):
            continue
        rel = name[len("dateien/"):]
        ziel = f_dateien.ziel_pruefen(rel, wurzel)
        if ziel is None:
            bericht["warnungen"].append(f"Unsicherer Pfad im Archiv übergangen: {rel}")
            continue
        ziel.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(name) as quelle, open(ziel, "wb") as senke:
            while True:
                block = quelle.read(1024 * 256)
                if not block:
                    break
                senke.write(block)
        bericht["dateien"] += 1


def _konfig_einspielen(zf: zipfile.ZipFile, bericht: dict[str, Any]) -> None:
    """Konfiguration zurückschreiben — und das Sidecar **neu** berechnen.

    Zu jeder Konfiguration gehört ein ``.sha256``-Sidecar; passt es nicht zur
    Datei, startet die Suite nicht (fail-closed, ``shared/config_io``). Das
    Sidecar ist aber seit der Härtung ein **HMAC** über einen Schlüssel aus der
    Umgebung (``JWT_SECRET_KEY`` & Co., ``_integrity_key``) — der steht
    absichtlich in keinem Backup. Übernähme man das Sidecar aus dem Archiv,
    stünde auf der Zielinstallation eine gültige Konfiguration neben einer
    Prüfsumme, die dort niemand nachrechnen kann: Die Wiederherstellung meldete
    Erfolg und die Suite käme nicht mehr hoch. Deshalb wird es hier mit den
    Mitteln der Zielinstallation erzeugt.
    """
    ziel_ordner = Path(".")
    try:
        from ai_compliance_suite.config import DEFAULT_CONFIG_PATH
        ziel_ordner = Path(DEFAULT_CONFIG_PATH).parent
    except Exception:  # noqa: BLE001
        pass
    ziel_ordner.mkdir(parents=True, exist_ok=True)

    geschrieben: list[Path] = []
    for name in zf.namelist():
        if not name.startswith("config/") or name.endswith("/"):
            continue
        datei = Path(name).name
        # Sidecars aus dem Archiv werden absichtlich verworfen (siehe oben).
        if not datei or "/" in datei or ".." in datei or datei.endswith(".sha256"):
            continue
        ziel = ziel_ordner / datei
        ziel.write_bytes(zf.read(name))
        geschrieben.append(ziel)
        bericht["konfiguration"] += 1

    for pfad in geschrieben:
        sidecar_erneuern(pfad, bericht["warnungen"])


def sidecar_erneuern(pfad: Path, warnungen: list[str]) -> None:
    """Prüfsumme einer Konfigurationsdatei für **diese** Installation schreiben."""
    try:
        from shared.config_io import _compute_sidecar_value, _sidecar_path

        ziel = _sidecar_path(pfad)
        ziel.write_text(_compute_sidecar_value(pfad.read_bytes()) + "\n", encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        warnungen.append(
            f"Integritätsprüfsumme für {pfad.name} nicht erneuert ({e}) — falls die "
            "Suite nicht startet, die zugehörige .sha256-Datei löschen.")


def _wiederherstellen_format1(archiv: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Altes Archiv (bis v8.0.4): SQLite-Dateien und Konfiguration zurückschreiben.

    Bewusst weiterhin möglich — es gibt solche Archive, und sie enthalten für
    Installationen aus der SQLite-Zeit echte Daten. Der Bericht sagt aber klar,
    dass der heutige Datenbestand davon unberührt bleibt.
    """
    bericht: dict[str, Any] = {
        "format": 1, "tabellen": 0, "zeilen": 0, "dateien": 0, "konfiguration": 0,
        "warnungen": [
            "Archiv im alten Format: Die PostgreSQL-Datenbank wurde NICHT "
            "verändert. Zurückgeschrieben wurden nur die SQLite-Dateien und die "
            "Konfiguration.",
        ],
    }
    wurzel = daten_wurzel()
    with zipfile.ZipFile(archiv, "r") as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            if name.startswith("data/db/") and name.endswith((".sqlite", ".sqlite-wal", ".sqlite-shm")):
                ziel = f_dateien.ziel_pruefen(name[len("data/"):], wurzel)
                if ziel is None:
                    continue
                ziel.parent.mkdir(parents=True, exist_ok=True)
                ziel.write_bytes(zf.read(name))
                bericht["dateien"] += 1
            elif name.endswith(".config.json") and "/" not in name:
                _konfig_einzeln(zf, name, bericht)
    return bericht


def _konfig_einzeln(zf: zipfile.ZipFile, name: str, bericht: dict[str, Any]) -> None:
    """Eine Konfigurationsdatei aus einem Format-1-Archiv.

    Das mitgelieferte ``.sha256`` bleibt auch hier liegen — es gehört zur
    Umgebung der Quellinstallation, nicht zu dieser (siehe
    :func:`_konfig_einspielen`).
    """
    ziel_ordner = Path(".")
    try:
        from ai_compliance_suite.config import DEFAULT_CONFIG_PATH
        ziel_ordner = Path(DEFAULT_CONFIG_PATH).parent
    except Exception:  # noqa: BLE001
        pass
    ziel_ordner.mkdir(parents=True, exist_ok=True)
    ziel = ziel_ordner / Path(name).name
    ziel.write_bytes(zf.read(name))
    bericht["konfiguration"] += 1
    sidecar_erneuern(ziel, bericht["warnungen"])
