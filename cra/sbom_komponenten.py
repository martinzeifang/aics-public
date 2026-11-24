"""Komponentenliste je SBOM, Vergleich zweier Releases (Art. 13 Abs. 5, #1761).

``cra_sbom`` hielt bis v8.0.0 nur eine **Zahl** (``komponenten_count``) und eine
Lizenzliste. Damit war der Release-Prüfpunkt ``fremdkomponenten_bewertet``
unbeantwortbar: Welche Fremdkomponente in diesem Release *neu* ist oder
*angehoben* wurde, stand nirgends — der Anwender musste außerhalb der Suite
nachsehen und hier einen Haken setzen. Genau die Umgehung, vor der der Dateikopf
von ``cra/release_checkliste.py`` warnt.

Diese Datei schließt die Datenlücke und nichts darüber hinaus:

* **Komponenten je SBOM** (``cra_sbom_komponenten``): Name, Version, Lieferant,
  Lizenz, purl — aus einer CycloneDX- oder SPDX-Datei geparst oder von Hand
  erfasst.
* **Vergleich zweier Releases** (``vergleiche``): ``neu`` / ``angehoben`` /
  ``entfallen`` / ``unveraendert``. Reine Funktion, ohne Datenbank testbar.
* **Bewertung je Komponente** — die Sorgfaltspflicht ist eine Aussage über eine
  *bestimmte* Abhängigkeit, nicht über ein Release. Sie gehört deshalb an die
  Komponente und nicht in einen Sammelhaken. Erst dadurch wird aus der Frage
  „haben Sie die neuen Komponenten bewertet?" ein **gerechneter** Befund:
  „2 von 7 neu aufgenommenen Komponenten tragen keine Bewertung".

**Identität einer Komponente.** Der Vergleich braucht einen Schlüssel, der die
Version *nicht* enthält — sonst wäre jede Anhebung ein Paar aus „entfallen" und
„neu", und die interessanteste Kategorie („angehoben", also dieselbe Komponente
in einer anderen Version) existierte nicht. ``komponent_key`` ist deshalb die
purl ohne Version und Qualifier (``pkg:npm/lodash``), sonst der kleingeschriebene
Name. Dass bei scoped npm-Paketen (``pkg:npm/@babel/core@7.0.0``) am **letzten**
``@`` getrennt wird, ist kein Detail: am ersten getrennt hieße jedes
Babel-Paket ``pkg:npm/``.

**Was hier bewusst nicht passiert.** Die SBOM wird nicht aus ``blob_path``
nachgeladen. Das wäre ein serverseitiger Abruf einer vom Anwender bestimmten
URL (SSRF); die Datei kommt über den Endpunkt herein.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared import db as _sdb

DB_PATH = Path("data/db/cra.sqlite")

#: Bewertungszustand einer Komponente (Art. 13 Abs. 5).
#:
#: ``nicht_relevant`` ist kein Synonym für „erledigt": Es ist die Aussage, dass
#: die Komponente die Sicherheitseigenschaften des Produkts nicht berührt (etwa
#: ein Build-Werkzeug, das nicht ausgeliefert wird). Wie bei
#: ``release_checkliste.STATUS`` braucht diese Aussage eine Begründung — „gilt
#: hier nicht" ist eine Feststellung über das Produkt und keine Formalie.
BEWERTUNG_STATUS = ("offen", "geprueft", "nicht_relevant")

#: Mindestlänge der Begründung, wenn eine Komponente nicht mehr ``offen`` ist.
#: Gleicher Wert wie ``konformitaet_db.MIN_GRUND`` — bewusst dieselbe Hürde.
MIN_GRUND = 10

#: Obergrenze beim Import. Eine SBOM mit mehr Einträgen ist kein Nachweis, den
#: ein Mensch noch bewertet, sondern ein Ressourcen-Problem im Browser.
MAX_KOMPONENTEN = 20000


def _connect(db_path: Path) -> Any:
    """Postgres-Verbindung (Schema je Modul) über den zentralen Kompat-Layer (#1332)."""
    return _sdb.connect(db_path)


def ensure_table(db_path: Path = DB_PATH) -> None:
    """Idempotent — neue Tabelle, keine Migration über Bestandsdaten."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS cra_sbom_komponenten (
                id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                projekt_name    TEXT NOT NULL,
                sbom_id         BIGINT NOT NULL,
                komponent_key   TEXT NOT NULL,
                name            TEXT NOT NULL DEFAULT '',
                version         TEXT NOT NULL DEFAULT '',
                lieferant       TEXT NOT NULL DEFAULT '',
                lizenz          TEXT NOT NULL DEFAULT '',
                purl            TEXT NOT NULL DEFAULT '',
                typ             TEXT NOT NULL DEFAULT '',
                bewertung_status TEXT NOT NULL DEFAULT 'offen',
                bewertung_notiz TEXT NOT NULL DEFAULT '',
                bewertet_von    TEXT NOT NULL DEFAULT '',
                bewertet_am     TEXT,
                created_at      TEXT DEFAULT (aics_now()),
                updated_at      TEXT DEFAULT (aics_now()),
                UNIQUE(sbom_id, komponent_key, version)
            );
            CREATE INDEX IF NOT EXISTS idx_cra_sbom_komp_projekt
                ON cra_sbom_komponenten(projekt_name);
            CREATE INDEX IF NOT EXISTS idx_cra_sbom_komp_sbom
                ON cra_sbom_komponenten(sbom_id);
            """
        )
        con.commit()
    finally:
        con.close()


# ── Identität und Normalisierung (reine Funktionen) ──────────────────────────

def _norm_version(value: Any) -> str:
    """Versionsangaben vergleichbar machen — delegiert an das Gate.

    Dieselbe Regel an zwei Orten wären zwei Wahrheiten (die Lehre aus
    #1726/#1727). Die Funktion liegt in ``cra.konformitaet_gate``; hier steht
    nur der Aufruf. Der Import ist bewusst lazy, weil das Gate diese Datei lädt.
    """
    from cra.konformitaet_gate import _norm_version as _nv
    return _nv(value)


def purl_ohne_version(purl: str) -> str:
    """purl auf den versionsunabhängigen Teil kürzen.

    ``pkg:npm/lodash@4.17.21?arch=x64#sub`` → ``pkg:npm/lodash``.
    Getrennt wird am **letzten** ``@``, damit scoped Namen
    (``pkg:npm/@babel/core@7.0.0``) ganz bleiben.
    """
    s = str(purl or "").strip()
    if not s:
        return ""
    for trenner in ("#", "?"):
        if trenner in s:
            s = s.split(trenner, 1)[0]
    if "@" in s:
        kopf, _, schwanz = s.rpartition("@")
        # Ein ``@`` direkt hinter ``pkg:`` oder am Anfang eines Namens ist Teil
        # des Namens, keine Version — dann bleibt die purl, wie sie ist.
        if kopf and schwanz and not kopf.endswith("/"):
            s = kopf
    return s.lower()


def purl_version(purl: str) -> str:
    """Version aus einer purl lesen (leer, wenn keine darin steht)."""
    s = str(purl or "").strip()
    for trenner in ("#", "?"):
        if trenner in s:
            s = s.split(trenner, 1)[0]
    kopf, _, schwanz = s.rpartition("@")
    if kopf and schwanz and not kopf.endswith("/"):
        return schwanz
    return ""


def komponent_key(name: str, purl: str = "") -> str:
    """Versionsunabhängige Identität einer Komponente.

    purl zuerst: Sie trennt ``pkg:npm/foo`` von ``pkg:pypi/foo``, der Name
    allein nicht. Ohne purl bleibt der kleingeschriebene Name — unschärfer,
    aber besser als nichts; der Vergleich sagt im Zweifel „neu", und das ist
    die Richtung, in die ein Nachweis irren darf.
    """
    p = purl_ohne_version(purl)
    if p:
        return p
    return " ".join(str(name or "").strip().lower().split())


# ── SBOM-Dateien lesen ───────────────────────────────────────────────────────

def _lizenz_cyclonedx(eintrag: Any) -> str:
    """Lizenzangaben einer CycloneDX-Komponente zu einem Text zusammenziehen."""
    namen: list[str] = []
    for lic in eintrag if isinstance(eintrag, list) else []:
        if not isinstance(lic, dict):
            continue
        if lic.get("expression"):
            namen.append(str(lic["expression"]))
            continue
        inner = lic.get("license")
        if isinstance(inner, dict):
            wert = inner.get("id") or inner.get("name")
            if wert:
                namen.append(str(wert))
    return ", ".join(dict.fromkeys(n.strip() for n in namen if n.strip()))


def _spdx_lieferant(wert: Any) -> str:
    """``Organization: Foo Inc.`` → ``Foo Inc.``; ``NOASSERTION`` → leer."""
    s = str(wert or "").strip()
    if not s or s.upper() == "NOASSERTION":
        return ""
    for prefix in ("Organization:", "Person:"):
        if s.startswith(prefix):
            return s[len(prefix):].strip()
    return s


def _parse_cyclonedx(doc: dict) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def walk(liste: Any) -> None:
        for c in liste if isinstance(liste, list) else []:
            if not isinstance(c, dict):
                continue
            purl = str(c.get("purl") or "")
            lieferant = ""
            if isinstance(c.get("supplier"), dict):
                lieferant = str(c["supplier"].get("name") or "")
            lieferant = lieferant or str(c.get("publisher") or "")
            out.append({
                "name": str(c.get("name") or ""),
                "version": str(c.get("version") or "") or purl_version(purl),
                "lieferant": lieferant,
                "lizenz": _lizenz_cyclonedx(c.get("licenses")),
                "purl": purl,
                "typ": str(c.get("type") or ""),
            })
            walk(c.get("components"))

    walk(doc.get("components"))
    return out


def _parse_spdx(doc: dict) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in doc.get("packages") or []:
        if not isinstance(p, dict):
            continue
        purl = ""
        for ref in p.get("externalRefs") or []:
            if isinstance(ref, dict) and str(ref.get("referenceType")) == "purl":
                purl = str(ref.get("referenceLocator") or "")
                break
        lizenz = ""
        for feld in ("licenseConcluded", "licenseDeclared"):
            wert = str(p.get(feld) or "").strip()
            if wert and wert.upper() != "NOASSERTION":
                lizenz = wert
                break
        out.append({
            "name": str(p.get("name") or ""),
            "version": str(p.get("versionInfo") or "") or purl_version(purl),
            "lieferant": _spdx_lieferant(p.get("supplier") or p.get("originator")),
            "lizenz": lizenz,
            "purl": purl,
            "typ": str(p.get("primaryPackagePurpose") or "").lower(),
        })
    return out


def parse_sbom(inhalt: str | bytes | dict) -> tuple[list[dict[str, Any]], str]:
    """CycloneDX- oder SPDX-JSON zu einer Komponentenliste lesen.

    Rückgabe ``(komponenten, format)`` mit ``format`` ∈ ``cyclonedx|spdx``.
    Wirft ``ValueError`` bei unlesbarem oder unbekanntem Inhalt — ein Import,
    der stillschweigend eine leere Liste speichert, wäre schlimmer als ein
    Fehler: Er sähe aus wie eine SBOM ohne Fremdkomponenten.

    Tag-Value-SPDX (``.spdx``) und XML-CycloneDX werden **nicht** gelesen; beide
    Werkzeugketten erzeugen JSON, und ein halb verstandenes Format ergibt eine
    halbe Komponentenliste.
    """
    doc: Any = inhalt
    if isinstance(inhalt, (str, bytes)):
        try:
            doc = json.loads(inhalt)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"SBOM ist kein lesbares JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("SBOM-JSON muss ein Objekt sein")

    if str(doc.get("bomFormat") or "").lower() == "cyclonedx" or "components" in doc:
        fmt, komponenten = "cyclonedx", _parse_cyclonedx(doc)
    elif doc.get("spdxVersion") or "packages" in doc:
        fmt, komponenten = "spdx", _parse_spdx(doc)
    else:
        raise ValueError("Unbekanntes SBOM-Format — CycloneDX- oder SPDX-JSON erwartet")

    komponenten = [k for k in komponenten if (k.get("name") or k.get("purl"))]
    if not komponenten:
        raise ValueError(f"{fmt.upper()}-SBOM gelesen, enthält aber keine Komponenten")
    if len(komponenten) > MAX_KOMPONENTEN:
        raise ValueError(f"SBOM nennt {len(komponenten)} Komponenten — "
                         f"Obergrenze ist {MAX_KOMPONENTEN}")
    return komponenten, fmt


# ── Speichern und Lesen ──────────────────────────────────────────────────────

def list_komponenten(db_path: Path, projekt_name: str,
                     sbom_id: int | None = None) -> list[dict[str, Any]]:
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        if sbom_id is None:
            rows = con.execute(
                "SELECT * FROM cra_sbom_komponenten WHERE projekt_name=? "
                "ORDER BY name, version", (projekt_name,)).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM cra_sbom_komponenten WHERE projekt_name=? AND sbom_id=? "
                "ORDER BY name, version", (projekt_name, int(sbom_id))).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def anzahl_je_sbom(db_path: Path, projekt_name: str) -> dict[int, int]:
    """Wie viele Komponenten je SBOM erfasst sind — **eine** Abfrage.

    Die Liste der SBOMs braucht diese Zahl, um „Komponentenliste vorhanden?"
    zu beantworten, ohne jede Liste einzeln zu laden. Ohne sie zeigte die
    Oberfläche vor dem Aufklappen bei **jeder** SBOM „⚠️ keine Liste" — eine
    Behauptung über die Nachweislage, die in Wirklichkeit nur hieß „noch nicht
    geladen". Für ein Werkzeug, das Nachweisführung verkauft, ist ein falsches
    „nicht belegbar" so schlimm wie ein falsches „belegt".
    """
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT sbom_id, COUNT(*) AS n FROM cra_sbom_komponenten "
            "WHERE projekt_name=? GROUP BY sbom_id", (projekt_name,)).fetchall()
        return {int(dict(r)["sbom_id"]): int(dict(r)["n"]) for r in rows}
    finally:
        con.close()


def replace_komponenten(db_path: Path, projekt_name: str, sbom_id: int,
                        komponenten: list[dict[str, Any]]) -> dict[str, Any]:
    """Komponentenliste einer SBOM ersetzen — **Bewertungen bleiben erhalten**.

    Ein erneuter Import derselben SBOM (korrigierte Datei, zweiter CI-Lauf) darf
    die Bewertungen nicht löschen: Sie sind die menschliche Aussage, die
    Komponentenliste ist der maschinelle Befund. Übernommen wird je
    ``(komponent_key, version)`` — dieselbe Komponente in derselben Version ist
    dieselbe Aussage; eine Anhebung ist bewusst eine neue, unbewertete Zeile.
    """
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        alt: dict[tuple[str, str], dict[str, Any]] = {}
        for r in con.execute(
                "SELECT komponent_key, version, bewertung_status, bewertung_notiz, "
                "bewertet_von, bewertet_am FROM cra_sbom_komponenten "
                "WHERE projekt_name=? AND sbom_id=?",
                (projekt_name, int(sbom_id))).fetchall():
            d = dict(r)
            alt[(str(d["komponent_key"]), str(d["version"]))] = d
        con.execute("DELETE FROM cra_sbom_komponenten WHERE projekt_name=? AND sbom_id=?",
                    (projekt_name, int(sbom_id)))

        gesehen: set[tuple[str, str]] = set()
        eingefuegt = uebernommen = 0
        for k in komponenten or []:
            name = str(k.get("name") or "").strip()
            purl = str(k.get("purl") or "").strip()
            key = komponent_key(name, purl)
            if not key:
                continue
            version = str(k.get("version") or "").strip()
            if (key, version) in gesehen:
                continue   # Dubletten innerhalb einer SBOM sind keine zwei Komponenten
            gesehen.add((key, version))
            vor = alt.get((key, version)) or {}
            if vor.get("bewertung_status") and vor["bewertung_status"] != "offen":
                uebernommen += 1
            con.execute(
                """INSERT INTO cra_sbom_komponenten
                       (projekt_name, sbom_id, komponent_key, name, version, lieferant,
                        lizenz, purl, typ, bewertung_status, bewertung_notiz,
                        bewertet_von, bewertet_am)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (projekt_name, int(sbom_id), key, name or key, version,
                 str(k.get("lieferant") or ""), str(k.get("lizenz") or ""), purl,
                 str(k.get("typ") or ""),
                 str(vor.get("bewertung_status") or "offen"),
                 str(vor.get("bewertung_notiz") or ""),
                 str(vor.get("bewertet_von") or ""), vor.get("bewertet_am")))
            eingefuegt += 1
        con.commit()
        return {"gespeichert": eingefuegt, "bewertungen_uebernommen": uebernommen}
    finally:
        con.close()


def set_bewertung(db_path: Path, projekt_name: str, komponent_ids: list[int],
                  status: str, notiz: str, von: str) -> int:
    """Bewertung je Komponente setzen (Art. 13 Abs. 5). Rückgabe: geänderte Zeilen.

    Mehrere IDs in einem Aufruf, weil ein Erst-Release alle Komponenten als neu
    führt: Ohne Sammelbewertung wäre der Prüfpunkt rechnerisch sauber und in der
    Bedienung unbrauchbar — und ein unbrauchbarer Prüfpunkt wird umgangen.
    """
    if status not in BEWERTUNG_STATUS:
        raise ValueError(f"Status muss einer sein von: {list(BEWERTUNG_STATUS)}")
    text = (notiz or "").strip()
    if status != "offen" and len(text) < MIN_GRUND:
        raise ValueError(f"Bewertung braucht eine Begründung "
                         f"(mindestens {MIN_GRUND} Zeichen)")
    ids = [int(i) for i in (komponent_ids or [])]
    if not ids:
        raise ValueError("Keine Komponente ausgewählt")
    ensure_table(db_path)
    jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
    con = _connect(db_path)
    try:
        geaendert = 0
        for kid in ids:
            cur = con.execute(
                """UPDATE cra_sbom_komponenten
                      SET bewertung_status=?, bewertung_notiz=?, bewertet_von=?,
                          bewertet_am=?, updated_at=aics_now()
                    WHERE id=? AND projekt_name=?""",
                (status, text, von or "",
                 None if status == "offen" else jetzt, kid, projekt_name))
            geaendert += int(cur.rowcount or 0)
        con.commit()
        return geaendert
    finally:
        con.close()


def delete_fuer_sbom(db_path: Path, projekt_name: str, sbom_id: int) -> None:
    """Komponenten einer gelöschten SBOM mitentfernen."""
    ensure_table(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM cra_sbom_komponenten WHERE projekt_name=? AND sbom_id=?",
                    (projekt_name, int(sbom_id)))
        con.commit()
    finally:
        con.close()


# ── Vergleich zweier Releases (reine Funktion) ───────────────────────────────

def vergleiche(alt: list[dict[str, Any]],
               neu: list[dict[str, Any]]) -> dict[str, Any]:
    """Zwei Komponentenlisten gegenüberstellen.

    * ``neu``        — Schlüssel nur in der neuen Liste.
    * ``angehoben``  — Schlüssel in beiden, Version verschieden.
    * ``entfallen``  — Schlüssel nur in der alten Liste.
    * ``unveraendert`` — Anzahl der Schlüssel mit gleicher Version.

    Führt eine Liste denselben Schlüssel mehrfach (verschiedene Versionen
    desselben Pakets, in Monorepos üblich), gelten alle Versionen gemeinsam:
    ``angehoben`` meldet nur, wenn die Versionsmengen sich unterscheiden. Sonst
    wäre jedes solche Paket dauerhaft „angehoben".
    """
    def gruppen(liste: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for k in liste or []:
            key = str(k.get("komponent_key") or komponent_key(
                str(k.get("name") or ""), str(k.get("purl") or "")))
            if not key:
                continue
            eintrag = out.setdefault(key, {"key": key, "versionen": set(), "muster": k})
            eintrag["versionen"].add(str(k.get("version") or ""))
        return out

    a, n = gruppen(alt), gruppen(neu)

    def zeile(key: str, quelle: dict[str, Any], **extra: Any) -> dict[str, Any]:
        m = quelle["muster"]
        z = {"komponent_key": key, "name": str(m.get("name") or key),
             "lieferant": str(m.get("lieferant") or ""),
             "lizenz": str(m.get("lizenz") or ""),
             "purl": str(m.get("purl") or ""),
             "version": ", ".join(sorted(v for v in quelle["versionen"] if v))}
        z.update(extra)
        return z

    neu_liste = [zeile(k, n[k]) for k in sorted(n) if k not in a]
    entfallen = [zeile(k, a[k]) for k in sorted(a) if k not in n]
    angehoben: list[dict[str, Any]] = []
    unveraendert = 0
    for k in sorted(set(a) & set(n)):
        va, vn = a[k]["versionen"], n[k]["versionen"]
        if va == vn:
            unveraendert += 1
            continue
        angehoben.append(zeile(
            k, n[k],
            version_alt=", ".join(sorted(v for v in va if v)),
            version_neu=", ".join(sorted(v for v in vn if v))))
    return {"neu": neu_liste, "angehoben": angehoben, "entfallen": entfallen,
            "unveraendert": unveraendert}


def vorgaenger_sbom(sboms: list[dict[str, Any]],
                    ziel: dict[str, Any]) -> dict[str, Any] | None:
    """Die SBOM, gegen die verglichen wird — reine Auswahl auf der Liste.

    Gewählt wird die **zuletzt vor dieser erfasste** SBOM einer anderen
    Release-Version. Nach Erfassungsdatum, nicht nach Versionsnummer:
    Versionsnummern lassen sich nicht allgemein ordnen (``1.10`` gegen ``1.9``,
    ``2.0-rc1`` gegen ``2.0``), das Erfassungsdatum schon. Wer eine andere
    Bezugsversion braucht, nennt sie ausdrücklich (``befund(...,
    vorgaenger_version=...)``).
    """
    ziel_version = _norm_version((ziel or {}).get("release_version"))
    ziel_datum = str((ziel or {}).get("sbom_datum") or "")
    # #1771: Nur **dasselbe Artefakt**. Ein Produkt besteht oft aus mehreren
    # (Anwendung, Webserver, Agent); jedes bringt seine eigene SBOM mit. Würde
    # die Webserver-SBOM gegen die der Anwendung verglichen, käme eine
    # plausibel aussehende und völlig falsche Zahl heraus — „178 neu, 3
    # entfallen" sagt dann nichts über Sorgfaltspflicht, sondern nur, dass
    # zwei verschiedene Dinge verglichen wurden.
    ziel_artefakt = str((ziel or {}).get("artefakt") or "")
    kandidaten = [s for s in sboms or []
                  if str(s.get("artefakt") or "") == ziel_artefakt
                  and _norm_version(s.get("release_version"))
                  and _norm_version(s.get("release_version")) != ziel_version
                  and str(s.get("sbom_datum") or "") <= ziel_datum]
    if not kandidaten:
        return None
    return max(kandidaten, key=lambda s: (str(s.get("sbom_datum") or ""),
                                          int(s.get("id") or 0)))


# ── Der gerechnete Befund für das Gate ───────────────────────────────────────

def _befund_artefakt(db_path: Path, projekt_name: str, version: str,
                     sboms: list[dict[str, Any]], ziel: dict[str, Any],
                     *, vorgaenger_version: str | None = None) -> dict[str, Any]:
    """Sorgfaltspflicht-Befund zu einer Release-Version (Art. 13 Abs. 5).

    Liefert den Vergleich und — das ist der Zweck — die Liste der **neu
    aufgenommenen oder angehobenen** Komponenten **ohne Bewertung**. Daraus
    rechnet das Gate den Prüfpunkt; niemand setzt ihn von Hand.

    Drei Lagen, die auseinandergehalten werden müssen, weil sie Verschiedenes
    bedeuten:

    * ``sbom_fehlt``  — keine SBOM zu dieser Version. Dass sie fehlt, meldet
      bereits der SBOM-Prüfpunkt; hier ist nichts zu rechnen.
    * ``liste_fehlt`` — SBOM vorhanden, aber ohne Komponentenliste (Altbestand
      oder nur die Zahl erfasst). Dann ist die Sorgfaltspflicht **nicht
      belegbar** — und genau das sagt der Befund, statt einen Haken anzubieten.
    * ``erstbewertung`` — kein Vorgänger-Release. Dann ist jede Komponente neu
      integriert; der Vergleich gegen die leere Menge ist hier die richtige
      Aussage und nicht eine Notlösung.
    """
    out: dict[str, Any] = {
        "version": str(version or ""), "sbom_id": None, "sbom_fehlt": True,
        "liste_fehlt": False, "erstbewertung": False,
        "vorgaenger_version": "", "vorgaenger_sbom_id": None,
        "komponenten": 0, "vergleich": {"neu": [], "angehoben": [], "entfallen": [],
                                        "unveraendert": 0},
        "pflichtig": 0, "bewertet": 0, "unbewertet": [],
    }
    out["artefakt"] = str(ziel.get("artefakt") or "")
    out["sbom_fehlt"] = False
    out["sbom_id"] = int(ziel.get("id") or 0)

    neu_liste = list_komponenten(db_path, projekt_name, int(ziel["id"]))
    out["komponenten"] = len(neu_liste)
    if not neu_liste:
        out["liste_fehlt"] = True
        return out

    if vorgaenger_version:
        vg_kandidaten = [s for s in sboms
                         if _norm_version(s.get("release_version"))
                         == _norm_version(vorgaenger_version)]
        vorher = (max(vg_kandidaten, key=lambda s: str(s.get("sbom_datum") or ""))
                  if vg_kandidaten else None)
    else:
        vorher = vorgaenger_sbom(sboms, ziel)

    alt_liste: list[dict[str, Any]] = []
    if vorher:
        out["vorgaenger_version"] = str(vorher.get("release_version") or "")
        out["vorgaenger_sbom_id"] = int(vorher.get("id") or 0)
        alt_liste = list_komponenten(db_path, projekt_name, int(vorher["id"]))
    if not alt_liste:
        # Auch ein Vorgänger **ohne** Komponentenliste führt hierhin: Verglichen
        # wird dann gegen die leere Menge, und der Befund sagt das offen.
        out["erstbewertung"] = True

    out["vergleich"] = vergleiche(alt_liste, neu_liste)

    # Pflichtig sind die neu aufgenommenen und die angehobenen Komponenten. Die
    # Bewertung hängt an der Zeile der **neuen** SBOM, also hier.
    pflicht_keys = {z["komponent_key"] for z in out["vergleich"]["neu"]} | \
                   {z["komponent_key"] for z in out["vergleich"]["angehoben"]}
    unbewertet: list[dict[str, Any]] = []
    bewertet = 0
    for k in neu_liste:
        if str(k.get("komponent_key")) not in pflicht_keys:
            continue
        if str(k.get("bewertung_status") or "offen") == "offen":
            unbewertet.append({"id": k.get("id"), "name": k.get("name"),
                               "version": k.get("version"),
                               "komponent_key": k.get("komponent_key")})
        else:
            bewertet += 1
    out["pflichtig"] = len(pflicht_keys)
    out["bewertet"] = bewertet
    out["unbewertet"] = unbewertet
    return out


def befund(db_path: Path, projekt_name: str, version: str,
           *, vorgaenger_version: str | None = None) -> dict[str, Any]:
    """Sorgfaltspflicht-Befund einer Release-Version über **alle Artefakte**.

    Ein Produkt besteht oft aus mehreren Artefakten — Anwendung, Webserver,
    Agent —, und jedes bringt seine eigene SBOM mit (#1771). Vorher nahm diese
    Funktion die **neueste** SBOM der Version und ließ die übrigen liegen: Der
    Prüfpunkt hätte dann eine Teilmenge des Produkts bewertet und das Ergebnis
    für das Ganze ausgegeben.

    Verglichen wird je Artefakt gegen **dessen** Vorgänger; zusammengezählt
    wird erst danach. Die Form der Rückgabe bleibt, damit Gate, Bericht und
    Panel unverändert lesen; ``artefakte`` kommt additiv dazu.

    Zur Auslegung von ``liste_fehlt``: Fehlt auch nur **einem** Artefakt die
    Komponentenliste, ist die Sorgfaltspflicht für das Release nicht belegt —
    ein „teilweise belegbar" gibt es nicht.
    """
    from cra.db import list_sbom

    sboms = list_sbom(db_path, projekt_name)
    ziel_version = _norm_version(version)
    passend = [s for s in sboms if _norm_version(s.get("release_version")) == ziel_version]

    gesamt: dict[str, Any] = {
        "version": str(version or ""), "sbom_id": None, "sbom_fehlt": True,
        "liste_fehlt": False, "erstbewertung": False,
        "vorgaenger_version": "", "vorgaenger_sbom_id": None,
        "komponenten": 0, "vergleich": {"neu": [], "angehoben": [], "entfallen": [],
                                        "unveraendert": 0},
        "pflichtig": 0, "bewertet": 0, "unbewertet": [], "artefakte": [],
    }
    if not passend:
        return gesamt

    # Je Artefakt die neueste SBOM. Mehrere Stände desselben Artefakts zur
    # selben Version sind möglich (korrigierte Datei, zweiter CI-Lauf).
    je_artefakt: dict[str, dict[str, Any]] = {}
    for sb in passend:
        key = str(sb.get("artefakt") or "")
        vorhanden = je_artefakt.get(key)
        if (vorhanden is None
                or (str(sb.get("sbom_datum") or ""), int(sb.get("id") or 0))
                > (str(vorhanden.get("sbom_datum") or ""), int(vorhanden.get("id") or 0))):
            je_artefakt[key] = sb

    gesamt["sbom_fehlt"] = False
    erst = []
    for key in sorted(je_artefakt):
        teil = _befund_artefakt(db_path, projekt_name, version, sboms, je_artefakt[key],
                                vorgaenger_version=vorgaenger_version)
        gesamt["artefakte"].append(teil)
        if teil.get("liste_fehlt"):
            gesamt["liste_fehlt"] = True
        erst.append(bool(teil.get("erstbewertung")))
        gesamt["komponenten"] += int(teil.get("komponenten") or 0)
        v = teil.get("vergleich") or {}
        for feld in ("neu", "angehoben", "entfallen"):
            gesamt["vergleich"][feld].extend(v.get(feld) or [])
        gesamt["vergleich"]["unveraendert"] += int(v.get("unveraendert") or 0)
        gesamt["pflichtig"] += int(teil.get("pflichtig") or 0)
        gesamt["bewertet"] += int(teil.get("bewertet") or 0)
        gesamt["unbewertet"].extend(teil.get("unbewertet") or [])

    gesamt["erstbewertung"] = all(erst) if erst else False
    # Bei genau einem Artefakt bleibt die Rückgabe wortgleich zu vorher.
    erstes = gesamt["artefakte"][0] if gesamt["artefakte"] else {}
    gesamt["sbom_id"] = erstes.get("sbom_id")
    gesamt["vorgaenger_version"] = erstes.get("vorgaenger_version", "")
    gesamt["vorgaenger_sbom_id"] = erstes.get("vorgaenger_sbom_id")
    return gesamt
