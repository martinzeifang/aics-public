"""Anhang I Teil II Nr. 3 — regelmäßig und wirksam testen (#1824).

Der Wortlaut der amtlichen deutschen Fassung (ABl. L vom 20.11.2024, S. 69; in
der Installation unter ``data/cra_resources/32024R2847_DEU.pdf``) verlangt vom
Hersteller, „die Sicherheit des Produkts mit digitalen Elementen **regelmäßig
und wirksam** zu testen und zu überprüfen". Anhang VII Nr. 6 verlangt die
Berichte darüber als **Pflichtinhalt der technischen Dokumentation**.

**Was vorher fehlte.** Der Testbericht war in der Anhang-VII-Beleg-Matrix ein
Haken: belegt oder nicht belegt. Ob er aus einer Zeit stammt, in der das
Produkt noch anders aussah, rechnete niemand — ein Bericht von 2023 belegte ein
Release von 2026 genauso gut wie einer von gestern. Damit war von den drei
Wörtern der Vorschrift genau eines abgebildet („testen"), und die beiden
anderen — „regelmäßig" und „wirksam" — standen nirgends. Die Akte zeigte grün,
und das ist die gefährliche Richtung: Nichts schlägt fehl, es steht nur eine
falsche Aussage an der Stelle, an der ein Prüfer sie liest (dieselbe Form wie
#1805 und #1820).

WOHER DIE NACHWEISE KOMMEN — die vorhandene Zuordnung, nicht eine zweite
``cra/annex_evidence.py`` bildet bereits ``pentest``/``testbericht`` auf den
Anhang-VII-Baustein ``testberichte`` ab, ``cra/annex_vii.py`` nennt die
zugehörigen ``doc_types``, und ``pentest/verknuepfung.py`` legt den übernommenen
Bericht mit genau diesem Baustein an. Dieses Modul dreht diese Zuordnung um,
statt eine eigene zu erfinden (Lehre aus #1774): Es liest dieselben Quellen und
holt zusätzlich das, was die Matrix nicht braucht und diese Prüfung ausmacht —
**das Datum**.

DREI ENTSCHEIDUNGEN, DIE ERKLÄRUNG BRAUCHEN

*Die 18 Monate sind unsere Regel, nicht die der Verordnung.* „Regelmäßig" ist
nicht beziffert. Eine Zahl braucht es trotzdem, sonst ist der Punkt nicht
rechenbar und damit wieder ein Haken. Weil die Zahl von uns stammt und nicht
vom Gesetzgeber, wirkt ihr Reißen ``bedingt`` und niemals ``rot``: Sie sagt
„hier ist lange nichts passiert", nicht „das Produkt ist nicht konform".

*Der härtere Maßstab ist nicht die Uhr, sondern das Produkt.* Ein Test belegt
den Stand, den er vorgefunden hat. Ist seither eine **Funktionsaktualisierung
oder wesentliche Änderung** herausgegangen, belegt er den ausgelieferten Stand
nicht mehr — unabhängig davon, wie jung er ist. Ein **Sicherheitsupdate** zählt
hier bewusst nicht: Nach Erwägungsgrund 39 ist es keine wesentliche Änderung,
und ein Prüfpunkt, der nach jedem Sicherheitsupdate einen neuen Pentest
verlangt, wird umgangen statt befolgt (#1792/#1793).

*Offene schwere Befunde macht dieser Punkt nicht rot.* Ein offener Befund aus
einem Testbericht ist kein Mangel des Testens — er ist der Beweis, dass das
Testen gewirkt hat. Dass das Produkt mit einer bekannten ausnutzbaren
Schwachstelle nicht in Verkehr gebracht werden darf (Anhang I Teil I Nr. 2
Buchst. a), meldet ``offene_kritische_schwachstellen`` bereits rot — über
``cra_vuln``, wo Pentest-Befunde mit ``source='pentest'`` landen. Zwei
Prüfpunkte für denselben Sachverhalt wären zwei Wahrheiten (#1726/#1727/#1776).
**Eine** Lage bleibt deshalb übrig und ist hier richtig aufgehoben und **rot**:
ein schwerer Befund, der im Testbericht steht und **nie ins
Schwachstellenregister übernommen wurde**. Dann weiß die Akte von ihm und
schweigt — und keine andere Prüfung sieht ihn.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

CRA_DB = Path("data/db/cra.sqlite")

#: Womit wird Anhang I Teil II Nr. 3 belegt?
#:
#: Die Auswahl heißt bewusst **nicht** „Pentest ja/nein": Die Verordnung ist
#: methodenneutral. Sie verlangt wirksame und regelmäßige Tests, nicht ein
#: bestimmtes Verfahren — ein durchgeführter Fuzzing-Lauf mit Protokoll belegt
#: die Pflicht, ein Penetrationstest ohne Bericht nicht.
ARTEN: tuple[str, ...] = ("pentest_extern", "pentest_intern", "automatisiert",
                          "kein_test")

ART_LABEL: dict[str, str] = {
    "pentest_extern": "Externer Penetrationstest (Bericht in der Akte)",
    "pentest_intern": "Interner Test durch eigenes Personal (Testprotokoll)",
    "automatisiert": "Automatisierte Tests (DAST/SAST/Fuzzing) mit Protokoll",
    "kein_test": "Kein gesonderter Sicherheitstest — Entscheidung erklärt",
    "": "nicht festgelegt",
}

#: Mindestlänge der Verzichts-Begründung. Dieselbe Größenordnung wie
#: ``cra.db.pruefe_support_period`` (#1762) — ein Wort ist keine Begründung,
#: und eine Pflichtangabe, die sich mit „n/a" erfüllen lässt, ist keine.
MIN_BEGRUENDUNG = 20

#: Unsere Auslegung von „regelmäßig" (siehe Dateikopf). Kalendermonate, nicht
#: 18 × 30 Tage: Der Anwender liest „seit Mai 2025 kein Test", und das soll
#: dasselbe heißen wie im Kalender (Muster ``cra/deadlines.py``, #1760).
MAX_MONATE = 18

#: Release-Arten, die einen vorhandenen Testnachweis überholen. Ein
#: Sicherheitsupdate steht bewusst nicht dabei (Erwägungsgrund 39).
UEBERHOLENDE_ARTEN = ("funktionsupdate", "wesentliche_aenderung")

_HERAUSGEGEBEN = ("freigegeben", "veroeffentlicht")

#: Wirkung der einzelnen Befunde auf die Ampel. Nur ein einziger ist ``rot``,
#: und zwar der, den sonst **niemand** sieht (siehe Dateikopf).
WIRKUNG: dict[str, str] = {
    "kein_nachweis": "bedingt",
    "verzicht_erklaert": "bedingt",
    "verzicht_unvollstaendig": "bedingt",
    "verzicht_faellig": "bedingt",
    "veraltet": "bedingt",
    "zu_alt": "bedingt",
    "befunde_nicht_im_register": "rot",
}


# ── Datums-Kleinkram ─────────────────────────────────────────────────────────

def _als_datum(wert: Any) -> date | None:
    """Aus dem, was die Register führen, ein Datum machen — oder ``None``.

    Die Quellen sind uneinheitlich: ``cra_dokumente.created_at`` ist ein
    ISO-Zeitstempel, ``pentest_berichte.datum_bis`` ein reines Datum, und der
    Nachweis-Store führt Sekunden seit 1970. Ein unlesbarer Wert wird hier zu
    ``None`` und damit zu „kein Datum" — nicht zu „heute". Ein geratenes Datum
    wäre in dieser Prüfung das Schlimmste: Es macht einen alten Nachweis jung.
    """
    if wert is None or wert == "":
        return None
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    if isinstance(wert, (int, float)):
        try:
            return datetime.fromtimestamp(float(wert), tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None
    text = str(wert).strip()
    if text.isdigit() and len(text) >= 9:          # Epoch als Text
        return _als_datum(int(text))
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _minus_monate(d: date, monate: int) -> date:
    """``d`` minus ``monate`` Kalendermonate (31.03. minus 1 Monat = 28./29.02.).

    Ein **negatives** ``monate`` rechnet vorwärts. Das braucht die Anwendung
    nicht, der Test aber schon: 18 Monate als 540 Tage nachzubauen wäre genau
    die zweite Rechnung, deren Abweichung niemand bemerkt.
    """
    gesamt = (d.year * 12 + d.month - 1) - monate
    jahr, monat = divmod(gesamt, 12)
    monat += 1
    tag = d.day
    while tag > 0:
        try:
            return date(jahr, monat, tag)
        except ValueError:
            tag -= 1
    return date(jahr, monat, 1)


# ── Nachweise einsammeln ─────────────────────────────────────────────────────

def _test_doc_types() -> set[str]:
    """Die Dokumentarten, die der Anhang-VII-Baustein ``testberichte`` kennt.

    Aus ``cra/annex_vii.py`` gelesen, nicht hier wiederholt: Käme eine Art
    dazu, zählte sie in der Beleg-Matrix und nicht in dieser Prüfung — und zwei
    Antworten auf „liegt ein Testbericht vor?" sind eine zu viel.
    """
    try:
        from cra import annex_vii

        for p in annex_vii.PUNKTE:
            if (p.baustein_key or p.key) == "testberichte":
                return {t.lower() for t in p.doc_types}
    except Exception:  # noqa: BLE001
        pass
    return {"testbericht", "test", "pentest"}


def _firma_doc_stichworte() -> set[str]:
    """Stichworte, mit denen ``annex_evidence`` Firmen-Nachweise auf
    ``testberichte`` abbildet — dieselbe Zuordnung, umgedreht (#1774)."""
    try:
        from cra.annex_evidence import _FIRMA_DOC_BAUSTEIN

        return {k for k, v in _FIRMA_DOC_BAUSTEIN.items() if v == "testberichte"}
    except Exception:  # noqa: BLE001
        return {"pentest", "testbericht"}


def _pentest_berichte(projekt_name: str) -> dict[str, dict[str, Any]]:
    """Pentest-Berichte dieses CRA-Projekts, nach ``evidence_doc_id``.

    Der Schlüssel ist die Kennung der hochgeladenen Datei — über sie hängt der
    Bericht mit seinem Eintrag in der CRA-Akte zusammen
    (``cra_dokumente.doc_path = 'evidence:<id>'``, ``pentest/verknuepfung``).
    Berichte ohne Datei liegen unter ihrer ID, damit sie nicht verschwinden.
    """
    try:
        from pentest import db as pdb

        out: dict[str, dict[str, Any]] = {}
        for b in pdb.berichte_fuer_modul(pdb.DB_PATH, "cra", projekt_name):
            key = str(b.get("evidence_doc_id") or "") or f"#{b.get('id')}"
            out[key] = b
        return out
    except Exception:  # noqa: BLE001
        return {}


def _pentest_eintrag(b: dict[str, Any]) -> dict[str, Any]:
    return {"label": f"Pentest-Bericht „{b.get('titel') or b.get('filename') or '—'}“",
            "quelle": "🛡️ Pentest",
            "datum": (_als_datum(b.get("datum_bis"))
                      or _als_datum(b.get("datum_von"))
                      or _als_datum(b.get("created_at")))}


def nachweise(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    """Alle Testnachweise des Projekts mit **Datum**, neueste zuerst.

    Jede Quelle ist einzeln gekapselt: Fällt eine aus, fehlen ihre Nachweise,
    aber die übrigen zählen weiter. Ein abgebrochener Aufruf würde hier aus
    „eine Quelle schweigt" ein „es gibt keine Tests" machen.

    **Dieselbe Prüfung wird nur einmal gezählt.** Die drei Quellen überlappen:
    Ein übernommener Pentest steht als Zeile in ``cra_dokumente``, als Bericht
    im Pentest-Modul und oft auch als Datei im Firmen-Nachweis-Store — das ist
    *ein* Test und nicht drei. Ohne diese Zusammenführung stand auf der
    Testinstanz „Nachweise in der Akte: 10" für einen einzigen
    Penetrationstest; eine Zahl, die der Anwender nicht nachvollziehen kann,
    beschädigt die Aussage mehr als sie stützt. Zusammengeführt wird über die
    Kennung der hochgeladenen Datei, nicht über den Namen — gleiche Namen sind
    ein Indiz, keine Identität.
    """
    out: list[dict[str, Any]] = []
    typen = _test_doc_types()
    berichte = _pentest_berichte(projekt_name)
    verbraucht: set[str] = set()

    # 1) Zugeordnete Nachweise in der CRA-Akte (``cra_dokumente``). Hierher
    #    legt auch die Pentest-Übernahme ihren Bericht (#1581) — dann gilt
    #    dessen **Prüfzeitraum** als Datum und nicht der Tag des Imports.
    try:
        from cra.traceability_db import list_dokumente

        for d in list_dokumente(db_path, projekt_name):
            baustein = str(d.get("annex_baustein") or "").strip()
            dtype = str(d.get("doc_type") or "").strip().lower()
            if baustein != "testberichte" and dtype not in typen:
                continue
            pfad = str(d.get("doc_path") or "")
            eid = pfad[len("evidence:"):] if pfad.startswith("evidence:") else ""
            if eid and eid in berichte:
                verbraucht.add(eid)
                out.append(_pentest_eintrag(berichte[eid]))
                continue
            if eid:
                verbraucht.add(eid)
            out.append({"label": str(d.get("doc_name") or "Testbericht"),
                        "quelle": "📎 CRA-Nachweis",
                        "datum": _als_datum(d.get("created_at"))})
    except Exception:  # noqa: BLE001
        pass

    # 2) Pentest-Berichte, die noch **nicht** in der CRA-Akte stehen. Sie
    #    gehören dort hin (Anhang VII Nr. 6), zählen hier aber mit: Der Test
    #    hat stattgefunden, nur die Zuordnung fehlt.
    for key, b in berichte.items():
        if key not in verbraucht:
            out.append(_pentest_eintrag(b))

    # 3) Firmenweiter Nachweis-Store (dieselbe Stichwort-Zuordnung wie die
    #    Beleg-Matrix). Hier ist nur das Hochladedatum bekannt — das ist eine
    #    Obergrenze für das Testdatum und damit die vorsichtige Richtung.
    try:
        from cra.db import load_projekt

        fid = (load_projekt(db_path, projekt_name) or {}).get("firmen_id")
        if fid:
            from evidence.db import list_documents as list_ev

            stichworte = _firma_doc_stichworte()
            for ev in list_ev(Path("data/db/evidence.sqlite"), firmen_id=str(fid)):
                if str(ev.id) in verbraucht or str(ev.id) in berichte:
                    continue        # dieselbe Datei steht schon in der Akte
                hint = str(ev.doc_type or "").lower()
                tags = " ".join(str(t).lower() for t in (ev.tags or []))
                if not any(s in hint or s in tags for s in stichworte):
                    continue
                out.append({"label": f"Firmen-Nachweis „{ev.filename}“",
                            "quelle": "🏢 Firmen-Nachweis",
                            "datum": _als_datum(ev.added_at)})
    except Exception:  # noqa: BLE001
        pass

    # Gleiche Quelle, gleicher Name, gleiches Datum = dieselbe Zeile zweimal.
    # Auf der Testinstanz lag derselbe Bericht achtmal in ``cra_dokumente``;
    # „8 Nachweise" wäre eine Behauptung, die die Akte nicht trägt. Über
    # Quellen hinweg wird **nicht** nach Namen zusammengeführt — dafür ist die
    # Datei-Kennung oben zuständig.
    gesehen: set[tuple[str, str, str]] = set()
    eindeutig: list[dict[str, Any]] = []
    for n in out:
        schluessel = (n["quelle"], n["label"],
                      n["datum"].isoformat() if n["datum"] else "")
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        eindeutig.append(n)
    out = eindeutig

    out.sort(key=lambda n: (n["datum"] or date.min), reverse=True)
    return out


def bezugszeitpunkt(db_path: Path, projekt_name: str, version: str) -> date | None:
    """Ab wann muss ein Test sein, um den ausgelieferten Stand zu belegen?

    Das ist die letzte **Funktionsaktualisierung oder wesentliche Änderung** —
    ein Sicherheitsupdate überholt einen Testbericht nicht (Erwägungsgrund 39,
    siehe Dateikopf). Berücksichtigt werden herausgegebene Vorgänge **und** der
    gerade bewertete, sobald er selbst als solche Änderung erklärt ist: Wer eine
    Funktionsänderung erklärt und einen Testbericht von davor vorlegt, hat die
    Änderung nicht getestet.
    """
    kandidaten: list[date] = []
    try:
        from cra import konformitaet_db as kdb

        for k in kdb.list_konformitaet(db_path, projekt_name):
            eigene = str(k.get("release_version") or "")
            if not eigene:
                continue                       # Produkt-Datensatz, kein Release
            art = str(k.get("release_art") or "")
            wesentlich = str(k.get("wesentliche_aenderung") or "") == "ja"
            if art not in UEBERHOLENDE_ARTEN and not wesentlich:
                continue
            if eigene == str(version or ""):
                # Der laufende Vorgang: Maßstab ist sein Beginn — ein Datum der
                # Herausgabe gibt es noch nicht, und bis dahin zu warten hieße,
                # die Prüfung genau dann abzuschalten, wenn sie gebraucht wird.
                d = _als_datum(k.get("created_at"))
            elif str(k.get("freigabe_status") or "") in _HERAUSGEGEBEN:
                d = (_als_datum(k.get("veroeffentlicht_am"))
                     or _als_datum(k.get("freigegeben_am")))
            else:
                continue                       # fremder Entwurf: nicht in Verkehr
            if d:
                kandidaten.append(d)
    except Exception:  # noqa: BLE001
        return None
    return max(kandidaten) if kandidaten else None


def offene_testbefunde(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Schwere offene Befunde aus Testberichten — und wie viele davon die
    Schwachstellenliste **nicht** kennt.

    Nur die zweite Zahl ist hier ein Befund (siehe Dateikopf). Die erste steht
    im Ergebnis, damit der Hinweistext sie nennen kann, ohne dass eine zweite
    Stelle dieselbe Pflicht meldet.
    """
    ergebnis: dict[str, Any] = {"offen": 0, "nicht_im_register": [], "geprueft": False}
    try:
        from pentest import db as pdb
        from pentest.verknuepfung import finding_kennung

        berichte = pdb.berichte_fuer_modul(pdb.DB_PATH, "cra", projekt_name)
    except Exception:  # noqa: BLE001
        return ergebnis
    try:
        from cra.db import list_vuln

        bekannt = {str(v.get("cve_id") or "").strip()
                   for v in (list_vuln(db_path, projekt_name) or [])}
    except Exception:  # noqa: BLE001
        # Ohne Schwachstellenliste lässt sich „nicht übernommen" nicht
        # feststellen. ``geprueft`` bleibt False — und damit meldet diese
        # Prüfung nichts, statt jeden Befund als ungemeldet auszuweisen.
        return ergebnis
    ergebnis["geprueft"] = True
    for b in berichte:
        try:
            findings = pdb.list_findings(pdb.DB_PATH, int(b["id"]))
        except Exception:  # noqa: BLE001
            continue
        for f in findings:
            if str(f.get("status") or "") != pdb.OFFEN:
                continue
            if str(f.get("schwere") or "") not in ("critical", "high"):
                continue
            ergebnis["offen"] += 1
            kennung = finding_kennung(int(b["id"]), str(f.get("ref") or ""))
            if kennung not in bekannt:
                ergebnis["nicht_im_register"].append(
                    f"{kennung} — {f.get('titel') or ''}".strip(" —"))
    return ergebnis


# ── Der Befund ───────────────────────────────────────────────────────────────

def _mangel(mid: str, text: str, hinweis: str) -> dict[str, Any]:
    return {"id": mid, "text": text, "hinweis": hinweis,
            "wirkung": WIRKUNG.get(mid, "bedingt")}


def befund(db_path: Path, projekt_name: str, version: str,
           *, heute: date | None = None) -> dict[str, Any]:
    """Der vollständige Stand zu Anhang I Teil II Nr. 3.

    Liefert ``maengel`` — die Liste, aus der das Gate seine offenen Punkte baut
    — und die Zahlen dahinter.

    Die **Nebenquellen** sind einzeln gekapselt (siehe :func:`nachweise`), der
    Datensatz selbst nicht: Lässt sich ``cra_konformitaet`` nicht lesen, gibt es
    keinen Stand, und dann ist der richtige Ausgang das Netz des Gates
    (``_ungeprueft`` → „nicht geprüft", #1751) und nicht ein leerer Befund, der
    wie ein erfüllter Punkt aussieht.
    """
    heute = heute or date.today()
    from cra import konformitaet_db as kdb

    rec = kdb.get_konformitaet(db_path, projekt_name, str(version or "")) or {}
    if not rec and version:
        # Für diese Version gibt es (noch) keinen Vorgang — das Gate wird auch
        # vor dem Anlegen abgerufen (``release-check``, #1615). Dann gilt der
        # Produkt-Datensatz. ``get_konformitaet`` erbt nur in eine vorhandene
        # Zeile hinein; ohne diesen Rückfall stünde der erklärte Verzicht da
        # und der Punkt meldete trotzdem „kein Nachweis" — eine Aussage, die
        # der Anwender nicht mehr abstellen kann.
        rec = kdb.get_konformitaet(db_path, projekt_name, "") or {}
    art = str(rec.get("testnachweis_art") or "").strip()
    begruendung = str(rec.get("test_verzicht_begruendung") or "").strip()
    review = str(rec.get("test_verzicht_review") or "")[:10]
    review_datum = _als_datum(review)

    nw = nachweise(db_path, projekt_name)
    mit_datum = [n for n in nw if n["datum"]]
    juengster = mit_datum[0]["datum"] if mit_datum else None
    bezug = bezugszeitpunkt(db_path, projekt_name, str(version or ""))
    befunde = offene_testbefunde(db_path, projekt_name)

    out: dict[str, Any] = {
        "art": art,
        "art_label": ART_LABEL.get(art, art or ART_LABEL[""]),
        "nachweise": [{"label": n["label"], "quelle": n["quelle"],
                       "datum": n["datum"].isoformat() if n["datum"] else ""}
                      for n in nw],
        "nachweis_count": len(nw),
        "juengster": juengster.isoformat() if juengster else None,
        "alter_tage": (heute - juengster).days if juengster else None,
        "bezug": bezug.isoformat() if bezug else None,
        "verzicht": {
            "erklaert": art == "kein_test",
            "begruendung": begruendung,
            "von": str(rec.get("test_verzicht_von") or ""),
            "am": str(rec.get("test_verzicht_am") or "")[:10],
            "review": review,
            "faellig": bool(art == "kein_test" and review_datum
                            and review_datum < heute),
        },
        "offene_befunde": befunde["offen"],
        "befunde_nicht_im_register": befunde["nicht_im_register"],
        "maengel": [],
    }
    maengel: list[dict[str, Any]] = out["maengel"]

    # 1) Der erklärte Verzicht. Er ersetzt den Nachweis — aber er wird nicht
    #    grün: Anhang I Teil II Nr. 3 ist dann nicht erfüllt, und das darf die
    #    Akte nicht verschweigen. Würde der Verzicht den Punkt schließen, wäre
    #    er der bequemste Weg um die Prüfung herum (#1814/#1751).
    if art == "kein_test":
        if len(begruendung) < MIN_BEGRUENDUNG or not review:
            maengel.append(_mangel(
                "verzicht_unvollstaendig",
                "Verzicht auf eigene Sicherheitstests ohne vollständige Erklärung",
                "Begründung (mindestens "
                f"{MIN_BEGRUENDUNG} Zeichen) und Wiedervorlage im Tab "
                "„✅ Konformität“ erfassen — ein Verzicht ohne Begründung und "
                "ohne Ablaufdatum ist in der Akte keine Entscheidung, sondern "
                "eine Lücke"))
        else:
            maengel.append(_mangel(
                "verzicht_erklaert",
                "Auf eigene Sicherheitstests wird bewusst verzichtet",
                f"erklärt von {out['verzicht']['von'] or '—'} am "
                f"{out['verzicht']['am'] or '—'}, Wiedervorlage {review}. "
                "Anhang I Teil II Nr. 3 ist damit nicht belegt; der Punkt "
                "bleibt sichtbar und wird im Nachweis ausgewiesen"))
        if out["verzicht"]["faellig"]:
            maengel.append(_mangel(
                "verzicht_faellig",
                f"Der Verzicht auf Sicherheitstests ist seit {review} zur "
                "Wiedervorlage fällig",
                "Entscheidung erneut treffen und begründen — oder Tests "
                "durchführen und den Bericht in die Akte legen"))
    else:
        # 2) Kein Nachweis in der Akte.
        if not nw:
            maengel.append(_mangel(
                "kein_nachweis",
                "Kein Bericht über Sicherheitstests in der Akte",
                "Testbericht, Testprotokoll oder Pentest-Bericht hinterlegen "
                "(Anhang VII Nr. 6 verlangt ihn als Inhalt der technischen "
                "Dokumentation) — oder im Tab „✅ Konformität“ erklären, dass "
                "auf eigene Sicherheitstests verzichtet wird"))
        else:
            # 3) Überholt durch eine Funktionsänderung — der härtere Maßstab.
            if juengster and bezug and juengster < bezug:
                maengel.append(_mangel(
                    "veraltet",
                    f"Letzter Testnachweis ({juengster.isoformat()}) ist älter "
                    f"als die letzte Funktionsänderung ({bezug.isoformat()})",
                    "Der Bericht belegt einen Produktstand, der so nicht mehr "
                    "ausgeliefert wird — nach einer Funktionsaktualisierung "
                    "bzw. wesentlichen Änderung erneut testen"))
            # 4) Die Hausregel zur Regelmäßigkeit.
            grenze = _minus_monate(heute, MAX_MONATE)
            if juengster and juengster < grenze:
                maengel.append(_mangel(
                    "zu_alt",
                    f"Letzter Testnachweis ist älter als {MAX_MONATE} Monate "
                    f"({juengster.isoformat()})",
                    "Anhang I Teil II Nr. 3 verlangt regelmäßiges Testen; die "
                    f"{MAX_MONATE} Monate sind der Richtwert dieser Anwendung "
                    "und keine Frist der Verordnung"))
            if not juengster:
                maengel.append(_mangel(
                    "zu_alt",
                    "Zu den vorhandenen Testnachweisen ist kein Datum lesbar",
                    "Ohne Datum ist nicht bestimmbar, ob regelmäßig getestet "
                    "wurde — Prüfzeitraum am Nachweis erfassen"))

    # 5) Der einzige rote Befund: ein schwerer Befund aus dem eigenen
    #    Testbericht, den die Schwachstellenliste nicht kennt.
    nicht_im_register = out["befunde_nicht_im_register"]
    if nicht_im_register:
        gelistet = ", ".join(nicht_im_register[:5])
        if len(nicht_im_register) > 5:
            gelistet += " …"
        maengel.append(_mangel(
            "befunde_nicht_im_register",
            f"{len(nicht_im_register)} schwere(r) offene(r) Befund(e) aus "
            "Testberichten fehlen im Schwachstellenregister",
            f"{gelistet} — im Pentest-Reiter nach CRA übernehmen. Solange sie "
            "dort fehlen, erscheinen sie in keiner Schwachstellen-Auswertung, "
            "obwohl die eigene Akte sie kennt (Anhang I Teil I Nr. 2 "
            "Buchst. a)"))
    return out
