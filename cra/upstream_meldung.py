"""Art. 13 Abs. 6 — Meldung an den Hersteller der Fremdkomponente (#1761).

Wer in einer Komponente Dritter eine Schwachstelle **findet**, muss sie der
Person oder Stelle melden, die diese Komponente herstellt oder pflegt, und die
Meldung dokumentieren. Im Modul gab es dazu nichts: ein Katalogeintrag zum
Selbstbewerten, kein Feld, kein Prüfpunkt. Die Pflicht entsteht bei jedem
Befund in einer Abhängigkeit, also laufend.

Diese Datei hält drei Dinge zusammen, weil sie nur zusammen Sinn ergeben: die
Felder am Befund, die **Regel**, wann die Pflicht überhaupt greift, und den
gerechneten Befund für das Release-Gate.

**Wann die Pflicht greift — und wann nicht.** Art. 13 Abs. 6 richtet sich an
den Hersteller, der die Schwachstelle *identifiziert*. Ein CVE, das aus einem
veröffentlichten Advisory oder aus Dependabot in die Suite gelaufen ist, hat
der Upstream-Hersteller selbst publiziert — ihn darüber zu unterrichten wäre
sinnlos, und ein Prüfpunkt, der es verlangt, wäre nach dem ersten
Abhängigkeits-Scan dauerhaft rot und damit wirkungslos. Die Pflicht greift
deshalb bei **eigenen** Funden (manuelle Erfassung, Pentest, eigene Analyse) in
einer Komponente, die nachweislich von Dritten stammt.

**Woran „von Dritten" erkannt wird.** An der Komponentenliste aus
``cra/sbom_komponenten.py`` — das ist die Verbindung, die dieses Issue
herstellt. Ohne Komponentenliste lässt sich der Fremdbezug nicht belegen; dann
sagt der Befund genau das (``ohne_komponentenliste``) und behauptet keine
Pflicht, die er nicht begründen kann. Umgekehrt gilt ein Befund, dessen
betroffene Komponente in keiner SBOM auftaucht, als **eigener Code** — die
Richtung, in die ein Nachweis irren darf, ist hier die zurückhaltende.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared import db as _sdb

DB_PATH = Path("data/db/cra.sqlite")

#: Zustand der Upstream-Meldung je Befund.
#:
#: ``nicht_erforderlich`` ist die begründete Aussage, dass hier nichts zu melden
#: ist (eigener Code, Komponente nicht mehr gepflegt, Upstream hat selbst
#: veröffentlicht). Sie braucht wie jede „gilt hier nicht"-Aussage einen Grund.
UPSTREAM_STATUS = ("offen", "gemeldet", "nicht_erforderlich")

#: Mindestlänge der Begründung — wie ``konformitaet_db.MIN_GRUND``.
MIN_GRUND = 10

#: Quellen, deren Befunde der Upstream-Hersteller selbst veröffentlicht hat.
#: Für sie entsteht keine Meldepflicht nach Art. 13 Abs. 6.
QUELLEN_UPSTREAM_BEKANNT = frozenset({"github_advisory", "github_dependabot", "gitlab"})

#: Status, in denen unsere Behandlung des Befundes nach außen sichtbar ist.
#: Ab hier ist ein Versäumnis endgültig (siehe ``_ueberfaellig``).
STATUS_VEROEFFENTLICHT = frozenset({"fixed", "disclosed"})


def _connect(db_path: Path) -> Any:
    return _sdb.connect(db_path)


def ensure_columns(db_path: Path = DB_PATH) -> None:
    """Spalten additiv an ``cra_vuln`` ergänzen (idempotent, keine Migration).

    Die Tabelle gehört ``cra/db.py``; dort stehen die Spalten auch im Schema
    und in ``_COLUMN_MIGRATIONS``. Dieser Aufruf ist die Absicherung für den
    Fall, dass eine Funktion dieser Datei vor ``cra.db.ensure_db`` läuft — ein
    fehlendes Feld wäre sonst ein 500er statt eines leeren Werts.
    """
    from cra.db import ensure_db   # legt Tabelle + Spalten an (neue DBs)

    ensure_db(db_path)
    con = _connect(db_path)
    try:
        for ddl in (
            "ALTER TABLE cra_vuln ADD COLUMN IF NOT EXISTS upstream_status "
            "TEXT NOT NULL DEFAULT 'offen'",
            "ALTER TABLE cra_vuln ADD COLUMN IF NOT EXISTS upstream_gemeldet_am TEXT",
            "ALTER TABLE cra_vuln ADD COLUMN IF NOT EXISTS upstream_kanal "
            "TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_vuln ADD COLUMN IF NOT EXISTS upstream_referenz "
            "TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_vuln ADD COLUMN IF NOT EXISTS upstream_begruendung "
            "TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE cra_vuln ADD COLUMN IF NOT EXISTS upstream_von "
            "TEXT NOT NULL DEFAULT ''",
        ):
            con.try_execute(ddl)
        con.commit()
    finally:
        con.close()


# ── Fremdbezug: Befund ↔ Komponentenliste (reine Funktionen) ─────────────────

def _norm(text: Any) -> str:
    return " ".join(str(text or "").strip().lower().split())


def komponenten_index(komponenten: list[dict[str, Any]]) -> dict[str, str]:
    """Nachschlagewerk „Textbezeichnung → ``komponent_key``".

    Eingetragen wird jede Form, in der ein Mensch oder ein Scanner die
    Komponente benennt: der Name, der Schlüssel und das letzte Glied der purl
    (``pkg:npm/lodash`` → ``lodash``). Mehr Formen heißt mehr Treffer, und ein
    Treffer ist hier die *strengere* Aussage — er begründet eine Meldepflicht.
    """
    idx: dict[str, str] = {}
    for k in komponenten or []:
        key = str(k.get("komponent_key") or "")
        if not key:
            continue
        for form in (key, str(k.get("name") or ""), key.rsplit("/", 1)[-1]):
            f = _norm(form)
            if f:
                idx.setdefault(f, key)
    return idx


def fremdbezug(vuln: dict[str, Any], index: dict[str, str]) -> str:
    """``komponent_key`` der betroffenen Fremdkomponente, sonst ``''``.

    ``affected_component`` ist Freitext und kommt in allen Formen vor
    (``lodash``, ``lodash@4.17.21``, ``npm:lodash``, ``pkg:npm/lodash``). Die
    Angleichung ist hier bewusst nachsichtig; der Vergleich bleibt aber exakt —
    eine Teilstring-Suche würde ``requests`` in ``requests-oauthlib`` finden und
    eine Meldepflicht an den falschen Hersteller erfinden.
    """
    roh = _norm(vuln.get("affected_component"))
    if not roh or not index:
        return ""
    kandidaten = [roh]
    if "@" in roh:
        kopf = roh.rpartition("@")[0]
        if kopf and not kopf.endswith("/"):
            kandidaten.append(kopf)
    if ":" in roh and not roh.startswith("pkg:"):
        kandidaten.append(roh.split(":", 1)[1])
    if "/" in roh:
        kandidaten.append(roh.rsplit("/", 1)[-1])
    for c in kandidaten:
        if c in index:
            return index[c]
    return ""


def _ueberfaellig(vuln: dict[str, Any]) -> bool:
    """Ist das Versäumnis endgültig?

    Art. 13 Abs. 6 nennt keine Frist, und deshalb darf ein frischer Befund das
    Release nicht blockieren: Eine gestern gefundene Schwachstelle ist heute
    noch nicht zu spät gemeldet. Endgültig wird das Versäumnis in dem Moment, in
    dem **wir** mit dem Befund nach außen gehen — behoben, offengelegt oder mit
    einer Advisory-Adresse versehen. Dann haben wir über eine Schwachstelle in
    fremdem Code informiert, ohne dessen Hersteller zu unterrichten; „ohne
    unangemessene Verzögerung" ist damit verfehlt.
    """
    return (str(vuln.get("status") or "") in STATUS_VEROEFFENTLICHT
            or bool(str(vuln.get("advisory_url") or "").strip()))


def pflicht(vuln: dict[str, Any], index: dict[str, str]) -> dict[str, Any]:
    """Beurteilt einen einzelnen Befund gegen Art. 13 Abs. 6.

    Rückgabe: ``{pflichtig, grund, komponent_key, erledigt, ueberfaellig}``.
    ``erledigt`` ist ``True`` bei ``gemeldet`` **und** bei begründetem
    ``nicht_erforderlich`` — beides sind Aussagen, die in der Akte stehen; die
    eine erfüllt die Pflicht, die andere verneint sie nachvollziehbar.
    """
    status = str(vuln.get("upstream_status") or "offen")
    key = fremdbezug(vuln, index)
    quelle = str(vuln.get("source") or "manual")
    erledigt = status == "gemeldet" or (
        status == "nicht_erforderlich"
        and len(str(vuln.get("upstream_begruendung") or "").strip()) >= MIN_GRUND)

    if quelle in QUELLEN_UPSTREAM_BEKANNT:
        return {"pflichtig": False,
                "grund": "aus einer Upstream-Quelle übernommen — der Hersteller "
                         "der Komponente hat den Befund selbst veröffentlicht",
                "komponent_key": key, "erledigt": erledigt, "ueberfaellig": False}
    if not key:
        return {"pflichtig": False,
                "grund": "kein Bezug zu einer Komponente der SBOM — gilt als "
                         "eigener Code",
                "komponent_key": "", "erledigt": erledigt, "ueberfaellig": False}
    return {"pflichtig": True,
            "grund": "eigener Fund in einer Fremdkomponente",
            "komponent_key": key, "erledigt": erledigt,
            "ueberfaellig": (not erledigt) and _ueberfaellig(vuln)}


# ── Schreiben ────────────────────────────────────────────────────────────────

def set_upstream(db_path: Path, projekt_name: str, vuln_id: int, *,
                 status: str, kanal: str = "", referenz: str = "",
                 begruendung: str = "", gemeldet_am: str = "",
                 von: str = "") -> dict[str, Any]:
    """Meldung an den Komponenten-Hersteller festhalten (Art. 13 Abs. 6).

    ``gemeldet`` verlangt einen **Kanal** und eine **Referenz**: „gemeldet" ohne
    Angabe, wohin und unter welcher Nummer, ist keine Dokumentation der Meldung,
    sondern deren Behauptung — und dokumentiert werden muss sie nach Art. 13
    Abs. 6 ausdrücklich.
    """
    if status not in UPSTREAM_STATUS:
        raise ValueError(f"Status muss einer sein von: {list(UPSTREAM_STATUS)}")
    kanal, referenz = (kanal or "").strip(), (referenz or "").strip()
    grund = (begruendung or "").strip()
    if status == "gemeldet":
        if not kanal:
            raise ValueError("Kanal der Meldung angeben (z. B. „GitHub Security "
                             "Advisory“, „security@…“, Bugtracker)")
        if not referenz:
            raise ValueError("Referenz der Meldung angeben (URL, Advisory- oder "
                             "Ticket-Nummer) — Art. 13 Abs. 6 verlangt die "
                             "Dokumentation der Meldung")
    if status == "nicht_erforderlich" and len(grund) < MIN_GRUND:
        raise ValueError(f"„nicht erforderlich“ braucht eine Begründung "
                         f"(mindestens {MIN_GRUND} Zeichen)")

    stempel = (gemeldet_am or "").strip() or (
        datetime.now(timezone.utc).isoformat(timespec="seconds")
        if status == "gemeldet" else None)
    ensure_columns(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(
            """UPDATE cra_vuln
                  SET upstream_status=?, upstream_kanal=?, upstream_referenz=?,
                      upstream_begruendung=?, upstream_gemeldet_am=?,
                      upstream_von=?, updated_at=aics_now()
                WHERE id=? AND projekt_name=?""",
            (status, kanal, referenz, grund,
             stempel if status == "gemeldet" else None,
             von or "", int(vuln_id), projekt_name))
        if not int(cur.rowcount or 0):
            raise ValueError("Schwachstelle nicht gefunden")
        con.commit()
    finally:
        con.close()
    return {"vuln_id": int(vuln_id), "upstream_status": status,
            "upstream_kanal": kanal, "upstream_referenz": referenz,
            "upstream_gemeldet_am": stempel}


# ── Der gerechnete Befund für das Gate ───────────────────────────────────────

def befund(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Offene Upstream-Meldepflichten des Projekts (Art. 13 Abs. 6).

    Bewusst **nicht** release-gefiltert: Die Pflicht hängt am Befund, nicht an
    der Version, in der er behoben wurde. Ein Release, das eine unbeachtete
    Meldepflicht offen lässt, soll sie im Gate sehen — auch wenn der Befund
    älter ist.
    """
    from cra.db import list_vuln
    from cra.sbom_komponenten import list_komponenten

    ensure_columns(db_path)
    komponenten = list_komponenten(db_path, projekt_name)
    index = komponenten_index(komponenten)
    out: dict[str, Any] = {
        "ohne_komponentenliste": not index,
        "pflichtig": 0, "gemeldet": 0, "nicht_erforderlich": 0,
        "offen": [], "ueberfaellig": [],
    }
    for v in list_vuln(db_path, projekt_name):
        p = pflicht(v, index)
        if not p["pflichtig"]:
            continue
        out["pflichtig"] += 1
        status = str(v.get("upstream_status") or "offen")
        if p["erledigt"]:
            if status == "gemeldet":
                out["gemeldet"] += 1
            else:
                out["nicht_erforderlich"] += 1
            continue
        zeile = {"vuln_id": v.get("id"),
                 "cve_id": v.get("cve_id") or f"#{v.get('id')}",
                 "komponente": v.get("affected_component") or p["komponent_key"],
                 "komponent_key": p["komponent_key"],
                 "schwere": v.get("schwere"), "status": v.get("status")}
        out["offen"].append(zeile)
        if p["ueberfaellig"]:
            out["ueberfaellig"].append(zeile)
    return out
