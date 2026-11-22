"""Word-Vorlagen für die Modul-Dokumente (#1997).

Bis v8.6.2 ließ sich für ein Dokument aus ``<modul>_managed_docs`` **keine**
Vorlage hinterlegen — an jeder anderen Stelle der Suite, an der ein Dokument
entsteht, geht das (Berichts-Center #1735/#1777/#1778, EU-Konformitätserklärung
#1753/#1889, Konformitätsnachweis #1776, Gutachten #957/#959). Getroffen hat es
genau die Dokumente, die das Haus **herausgibt**: Benutzerinformationen nach
Anhang II, SBOM-Begleitdokument, Offenlegungs- und Update-Policy.

**Warum das nicht der Berichts-Weg ist.** Ein Bericht ist *Daten*: Die Vorlage
schreibt ``{{ reifegrad }}``, der Modul-Adapter liefert die Zahl. Ein
Modul-Dokument ist *freie Prosa*, die ein Mensch geschrieben hat. Die Vorlage
leistet hier nichts für den Inhalt — sie gibt dem Dokument seine **Form** und
braucht eine Stelle, an der die Prosa hineinläuft. Daraus folgen die drei
Entscheidungen, die dieses Modul tragen:

1. **Eigener Kontext.** ``dokument.*``, ``firma.*``, ``projekt.*``, ``inhalt``
   — **nicht** der Modul-Kontext. Läge der Modul-Kontext an, würde
   ``{{ reifegrad }}`` dank ``ChainableUndefined`` *leer* rendern, und ein
   Dokument sähe fertig aus, in dem eine Zahl fehlt (die Lehre aus #1741).
2. **Eigener Schlüsselraum.** Der Geltungsbereich steht in
   ``template_registry.bericht_typ`` als ``dokument`` bzw.
   ``dokument:<doc_type>``. Eine Vorlage **ohne** Geltungsbereich (der
   modulweite Standard) greift hier ausdrücklich **nicht**: Sie ist für den
   Berichts-Kontext gebaut, und genau diese Verwechslung ist #1777 — ein
   Haus-Standard für „den CRA-Bericht" hat dort lautlos ein Rechtsdokument
   ersetzt.
3. **Die Prosa trägt die Formatvorlagen der Vorlage.** Sie wird nicht als Text
   eingesetzt, sondern als Absätze, Überschriften und Tabellen **in das
   gerenderte Vorlagendokument** gebaut — damit gelten dessen ``Heading``-,
   ``List Bullet``- und Tabellen-Formate.

**Der Weg ohne neue Abhängigkeit.** docxtpls eigener Mechanismus dafür
(``new_subdoc``) braucht ``docxcompose``; das Paket ist nicht im Image, und für
diesen Zweck ist es auch nicht nötig. Stattdessen rendert docxtpl die
Datenfelder und setzt für ``{{ inhalt }}`` eine **Marke**; danach baut
python-docx die Prosa in dasselbe Dokument und verschiebt sie an die Stelle der
Marke. Der Gutachten-Renderer (Bracket-Mapping, #963) wird dafür nicht
angefasst — er löst eine andere Aufgabe für eine andere Engine.

**Eine Vorlage ohne ``{{ inhalt }}`` wird abgewiesen.** Sie erzeugt ein Dokument
ohne seinen Inhalt — und das ist die schlimmste Form des Fehlschlags, weil das
Ergebnis fertig aussieht (dieselbe Klasse wie #1805/#1870: nichts schlägt fehl,
es steht nur das Falsche da).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

#: Geltungsbereich „alle Dokumente dieses Moduls".
DOKUMENT = "dokument"
#: Trenner zum Dokumenttyp: ``dokument:sbom_begleitdoc``.
TRENNER = ":"

#: Die Marke, die docxtpl für ``{{ inhalt }}`` setzt und an deren Stelle die
#: Prosa wandert. Bewusst ohne ``&``, ``<`` und ``>``: Die Engine rendert mit
#: ``autoescape=True`` (#1791), und eine escapte Marke fände sich nicht wieder.
INHALT_MARKE = "[[AICS-DOKUMENT-INHALT]]"

#: Variablen des Dokument-Kontexts — das Gegenstück zu ``<MODUL>_VARIABLES``.
#: Das Admin-UI zeigt sie, und die Prüfung aus #1741 vergleicht gegen sie.
VARIABLEN: list[dict[str, Any]] = [
    {"key": "inhalt", "typ": "block", "pflicht": True,
     "beschreibung": "Der geschriebene Text des Dokuments. Pflicht — ohne "
                     "diese Variable hat die Prosa keinen Ort und das Dokument "
                     "erscheint leer."},
    {"key": "dokument.titel", "typ": "text", "pflicht": True,
     "beschreibung": "Titel des Dokuments"},
    {"key": "dokument.typ_titel", "typ": "text", "pflicht": False,
     "beschreibung": "Bezeichnung des Dokumenttyps aus dem Rechts-Kanon"},
    {"key": "dokument.doc_type", "typ": "text", "pflicht": False,
     "beschreibung": "Schlüssel des Dokumenttyps (z. B. sbom_begleitdoc)"},
    {"key": "dokument.rechtsgrundlage", "typ": "text", "pflicht": False,
     "beschreibung": "Fundstelle aus dem Rechts-Kanon (z. B. „Anhang I Teil II "
                     "Nr. 1 CRA“)"},
    {"key": "dokument.status", "typ": "text", "pflicht": False,
     "beschreibung": "entwurf | final | freigegeben"},
    {"key": "dokument.status_label", "typ": "text", "pflicht": False,
     "beschreibung": "Status ausgeschrieben"},
    {"key": "dokument.version", "typ": "zahl", "pflicht": False,
     "beschreibung": "Fassung des Dokuments"},
    {"key": "dokument.stand", "typ": "datum", "pflicht": False,
     "beschreibung": "Datum der letzten Änderung"},
    {"key": "dokument.geaendert_von", "typ": "text", "pflicht": False,
     "beschreibung": "Wer zuletzt geändert hat"},
    {"key": "dokument.sha256", "typ": "text", "pflicht": False,
     "beschreibung": "Prüfsumme des freigegebenen Inhalts — leer, solange das "
                     "Dokument nicht freigegeben ist"},
    {"key": "dokument.vertraulich", "typ": "ja/nein", "pflicht": False,
     "beschreibung": "Vertraulichkeitskennzeichnung aus den Metadaten"},
    {"key": "dokument.kategorie", "typ": "text", "pflicht": False,
     "beschreibung": "Kategorie des Dokumenttyps aus dem Rechts-Kanon"},
    {"key": "projekt.name", "typ": "text", "pflicht": False,
     "beschreibung": "Projekt, zu dem das Dokument gehört"},
    {"key": "projekt.modul", "typ": "text", "pflicht": False,
     "beschreibung": "Modulschlüssel (cra, nis2, ai_act, dsgvo, wiba)"},
    {"key": "projekt.modul_label", "typ": "text", "pflicht": False,
     "beschreibung": "Modulname ausgeschrieben"},
    {"key": "firma.name", "typ": "text", "pflicht": False,
     "beschreibung": "Mandant (Kurzname)"},
    {"key": "firma.unternehmen", "typ": "text", "pflicht": False,
     "beschreibung": "Firmierung des Mandanten"},
    {"key": "firma.rechtsform", "typ": "text", "pflicht": False,
     "beschreibung": "Rechtsform"},
    {"key": "firma.anschrift_text", "typ": "block", "pflicht": False,
     "beschreibung": "Anschrift als Briefkopf-Zeilen (#1892) — leere Teile "
                     "entfallen, es entsteht kein Platzhalter"},
    {"key": "firma.anschrift", "typ": "text", "pflicht": False,
     "beschreibung": "Straße und Hausnummer"},
    {"key": "firma.plz", "typ": "text", "pflicht": False, "beschreibung": "Postleitzahl"},
    {"key": "firma.ort", "typ": "text", "pflicht": False, "beschreibung": "Ort"},
    {"key": "firma.land", "typ": "text", "pflicht": False, "beschreibung": "Land"},
    {"key": "firma.vertreter_name", "typ": "text", "pflicht": False,
     "beschreibung": "Vertretungsberechtigte Person"},
    {"key": "firma.vertreter_funktion", "typ": "text", "pflicht": False,
     "beschreibung": "Funktion der vertretungsberechtigten Person"},
]

#: Top-Level-Namen des Dokument-Kontexts. Die Prüfung aus #1741 vergleicht auf
#: Wurzeln; ``firma.ort`` und ``firma`` sind für sie dasselbe.
WURZELN: frozenset[str] = frozenset(
    str(v["key"]).split(".", 1)[0] for v in VARIABLEN)

_STATUS_LABEL: dict[str, str] = {
    "entwurf": "Entwurf",
    "final": "Final",
    "freigegeben": "Freigegeben",
}

#: Modulschlüssel → Anzeigename. Dieselbe Liste wie
#: ``shared.templates.validate.MODUL_LABEL``, aber mit den **Dokument**-Keys
#: (``ai_act``, nicht ``aiact``) — die beiden Schlüsselräume laufen im Haus
#: auseinander (#1735), und hier gilt der der Dokumenten-Register.
MODUL_LABEL: dict[str, str] = {
    "cra": "CRA",
    "nis2": "NIS2",
    "ai_act": "AI Act",
    "dsgvo": "DSGVO",
    "wiba": "WiBA",
}


class VorlageUngeeignet(ValueError):
    """Die Vorlage taugt nicht für ein Dokument (kein Platz für die Prosa)."""


# ── Geltungsbereich ─────────────────────────────────────────────────────────

def scope(doc_type: str = "") -> str:
    """Geltungsbereich-Schlüssel für die Registry.

    Ohne ``doc_type`` der modulweite Dokument-Bereich, sonst der Bereich genau
    dieses Dokumenttyps.
    """
    dt = str(doc_type or "").strip()
    return f"{DOKUMENT}{TRENNER}{dt}" if dt else DOKUMENT


def ist_dokument_scope(bericht_typ: Any) -> bool:
    """Beschreibt dieser ``bericht_typ`` einen Dokument-Geltungsbereich?

    Leer heißt **nein** — der modulweite Standard des Berichts-Centers gilt für
    Dokumente nicht (siehe Modul-Docstring, Punkt 2).
    """
    t = str(bericht_typ or "").strip()
    return t == DOKUMENT or t.startswith(DOKUMENT + TRENNER)


def doc_type_aus_scope(bericht_typ: Any) -> str:
    """Dokumenttyp eines Geltungsbereichs — leer heißt „alle Dokumente"."""
    t = str(bericht_typ or "").strip()
    if not t.startswith(DOKUMENT + TRENNER):
        return ""
    return t.split(TRENNER, 1)[1].strip()


def gilt_fuer(bericht_typ: Any, doc_type: str) -> bool:
    """Ist diese Vorlage für dieses Dokument benutzbar?"""
    if not ist_dokument_scope(bericht_typ):
        return False
    eigen = doc_type_aus_scope(bericht_typ)
    return not eigen or eigen == str(doc_type or "").strip()


def scopes_fuer_modul(modul: str) -> list[dict[str, str]]:
    """Auswählbare Geltungsbereiche — womit das Admin-UI die Frage füllt.

    Der modulweite Dokument-Bereich zuerst, danach die Dokumenttypen aus dem
    Rechts-Kanon (``shared.documents.catalog``). Der Katalog ist die Quelle,
    keine zweite Liste (#1731).
    """
    from shared.documents import catalog as dcat

    aus: list[dict[str, str]] = [
        {"key": DOKUMENT, "titel": "Alle Dokumente dieses Moduls",
         "gruppe": "Dokumente"}]
    try:
        # #2089: Die Variablenliste erscheint im Admin-UI — Anzeigesprache.
        specs = dcat.get_catalog(modul, _anzeige_sprache()) or []
    except Exception:  # noqa: BLE001 — ein kaputter Katalog darf den Upload nicht stoppen
        specs = []
    for s in specs:
        dt = str(s.get("doc_type") or "").strip()
        if not dt:
            continue
        aus.append({"key": scope(dt),
                    "titel": str(s.get("titel") or dt),
                    "gruppe": "Dokumente"})
    return aus


# ── Kontext ─────────────────────────────────────────────────────────────────

def _s(wert: Any) -> str:
    return str(wert or "").strip()


def kontext(modul: str, projekt: str, doc: dict[str, Any], *,
            module_db: Path | None = None,
            firma: dict[str, Any] | None = None) -> dict[str, Any]:
    """Der Kontext einer Dokument-Vorlage.

    ``firma`` lässt sich mitgeben (der Aufrufer hat sie oft schon); sonst wird
    sie über ``shared.firmen_link.firma_des_projekts`` aufgelöst — dieselbe
    Auflösung, die die Firmen-ACL benutzt.

    **Kein Platzhalter für Fehlendes.** Leere Angaben bleiben leer; eine halbe
    Anschrift ist eine halbe Angabe und soll als solche erkennbar sein (#1892).
    """
    from shared.documents import catalog as dcat

    d = dict(doc or {})
    meta = d.get("meta") or {}
    if isinstance(meta, str):
        import json
        try:
            meta = json.loads(meta) or {}
        except ValueError:
            meta = {}
    # #2089: Das gerenderte Dokument gibt der **Mandant** heraus.
    spec = dcat.get_doc_spec(modul, _s(d.get("doc_type")),
                             _inhalt_sprache(modul, projekt)) or {}

    if firma is None:
        firma = {}
        if module_db is not None:
            try:
                from shared.firmen_link import firma_des_projekts
                firma = firma_des_projekts(Path(module_db), projekt) or {}
            except Exception:  # noqa: BLE001 — ohne Mandant bleibt der Briefkopf leer
                firma = {}
    try:
        from firmen.db import anschrift_text
        anschrift = anschrift_text(firma)
    except Exception:  # noqa: BLE001
        anschrift = ""

    status = _s(d.get("status")) or "entwurf"
    return {
        "dokument": {
            "titel": _s(d.get("titel")) or _s(spec.get("titel")),
            "typ_titel": _s(spec.get("titel")),
            "doc_type": _s(d.get("doc_type")),
            "rechtsgrundlage": _s(d.get("rechtsgrundlage")) or _s(spec.get("rechtsgrundlage")),
            "kategorie": _s(spec.get("kategorie")),
            "status": status,
            "status_label": _STATUS_LABEL.get(status, status),
            "version": d.get("version") or 1,
            "stand": _s(d.get("updated_at")) or _s(d.get("created_at")),
            "geaendert_von": _s(d.get("updated_by")) or _s(d.get("created_by")),
            # Leer, solange nicht freigegeben: `set_status` berechnet die
            # Prüfsumme erst bei der Freigabe. Eine Prüfsumme an einem Entwurf
            # wäre eine Zusage, die nicht gilt.
            "sha256": _s(d.get("sha256")) if status == "freigegeben" else "",
            "vertraulich": bool(meta.get("vertraulich")),
        },
        "projekt": {
            "name": _s(projekt),
            "modul": _s(modul),
            "modul_label": MODUL_LABEL.get(_s(modul), _s(modul)),
        },
        "firma": {
            "name": _s(firma.get("name")),
            "unternehmen": _s(firma.get("unternehmen")),
            "rechtsform": _s(firma.get("rechtsform")),
            "anschrift_text": anschrift,
            "anschrift": _s(firma.get("anschrift")),
            "plz": _s(firma.get("plz")),
            "ort": _s(firma.get("ort")),
            "land": _s(firma.get("land")),
            "vertreter_name": _s(firma.get("vertreter_name")),
            "vertreter_funktion": _s(firma.get("vertreter_funktion")),
        },
        # Die Marke, an deren Stelle die Prosa wandert.
        "inhalt": INHALT_MARKE,
    }


# ── Render ──────────────────────────────────────────────────────────────────

def _marken_absatz(docx_doc: Any):
    """Den Absatz mit der Marke finden — oder ``None``.

    Gesucht wird über den **Absatztext**, nicht über einzelne Runs: docxtpl
    kann den gerenderten Wert über mehrere Runs verteilen, und eine Suche je
    Run fände die Marke dann nie.
    """
    for p in docx_doc.paragraphs:
        if INHALT_MARKE in (p.text or ""):
            return p
    # Auch in Tabellenzellen: ein Briefkopf-Layout legt den Textbereich
    # gelegentlich in eine Tabelle.
    for tabelle in docx_doc.tables:
        for reihe in tabelle.rows:
            for zelle in reihe.cells:
                for p in zelle.paragraphs:
                    if INHALT_MARKE in (p.text or ""):
                        return p
    return None


def prosa_einsetzen(gerendert: Any, html: str) -> None:
    """Die Prosa an die Stelle der Marke setzen — im gerenderten Vorlagendokument.

    Eigene Funktion, damit sie **aufgerufen** und nicht nachgebaut wird: Der
    erste Test hatte die Logik kopiert und damit den Doppelgänger geprüft, nicht
    den Code — und übersah genau den Fehler, den er finden sollte.

    Welche Elemente beim Bauen der Prosa entstanden sind, wird **an den
    Abschnittseigenschaften abgelesen**. Zwei naheliegende Wege sind beide
    falsch, und beide sind hier schon einmal falsch gewesen:

    * ``list(koerper)[vorher:]`` — ``add_paragraph`` hängt **nicht** ans Ende
      des Körpers, sondern vor ``w:sectPr``; der Schnitt übersprang das erste
      neue Element und nahm ``sectPr`` mit. Die Seiteneinrichtung samt Kopf- und
      Fußzeile wanderte dann vor den Text, und **Word zeigt das Dokument
      trotzdem an** — es wäre nicht aufgefallen.
    * Vergleich über ``id(el)`` — lxml legt seine Element-Proxys bei jedem
      Zugriff neu an. Hält man keine Referenz, werden sie freigegeben und ihre
      Kennungen **neu vergeben**: Neue Absätze erschienen damit als „schon
      vorhanden". Der Fehler trat nicht zuverlässig auf, was ihn schlimmer
      macht als einen, der immer passiert.

    ``sectPr`` ist der feste Punkt: Es steht im Körper immer zuletzt, und die
    neuen Elemente liegen genau zwischen seiner alten und seiner neuen Position.
    """
    from docx.oxml.ns import qn

    from shared.documents import export as dx

    marke = _marken_absatz(gerendert)
    if marke is None:
        raise VorlageUngeeignet(
            "Die Vorlage hat keine Stelle für den Text des Dokuments. "
            "Setze an die gewünschte Position {{ inhalt }}.")

    koerper = marke._p.getparent()
    sect = koerper.find(qn("w:sectPr"))

    def _grenze() -> int:
        return koerper.index(sect) if sect is not None else len(koerper)

    von = _grenze()
    dx.html_in_dokument(gerendert, html or "")
    for el in list(koerper)[von:_grenze()]:
        koerper.remove(el)
        marke._p.addprevious(el)
    koerper.remove(marke._p)


def render_docx(modul: str, projekt: str, doc: dict[str, Any],
                template_id: int, *, module_db: Path | None = None,
                firma: dict[str, Any] | None = None) -> bytes:
    """Dokument durch die Vorlage rendern.

    Zwei Schritte: docxtpl setzt die Datenfelder (und für ``{{ inhalt }}`` die
    Marke), danach baut ``shared.documents.export`` die Prosa **in dasselbe
    Dokument** und verschiebt sie an die Stelle der Marke. Dadurch trägt die
    Prosa die Formatvorlagen der Vorlage.
    """
    import io

    from docx import Document

    from shared.templates import db as tdb
    from shared.templates import engine

    ctx = kontext(modul, projekt, doc, module_db=module_db, firma=firma)
    rohe = engine.render_docx(tdb.DEFAULT_DB_PATH, int(template_id), ctx)

    gerendert = Document(io.BytesIO(rohe))
    prosa_einsetzen(gerendert, _s(doc.get("content_html")))
    buf = io.BytesIO()
    gerendert.save(buf)
    return buf.getvalue()


def render_pdf(modul: str, projekt: str, doc: dict[str, Any],
               template_id: int, **kw: Any) -> bytes:
    """Wie :func:`render_docx`, danach durch den PDF-Konverter.

    Konverter-Fehler laufen bewusst durch: ``server/app.py`` bildet sie über
    den ``errorhandler`` aus #1903 auf 503/504/502 ab.
    """
    from shared.templates.pdf_converter import convert_docx_to_pdf

    return convert_docx_to_pdf(render_docx(modul, projekt, doc, template_id, **kw))


# ── Prüfung beim Hochladen ──────────────────────────────────────────────────

def pruefe_datei(pfad: Path | str) -> None:
    """Taugt die Datei als Dokument-Vorlage? Wirft :class:`VorlageUngeeignet`.

    Geprüft wird genau eine Zusage: Es gibt eine Stelle für die Prosa. Alles
    andere ist Gestaltung und gehört dem Anwender — aber eine Vorlage ohne
    ``{{ inhalt }}`` erzeugt ein Dokument ohne seinen Inhalt, und das sieht
    fertig aus.
    """
    from shared.templates.engine import extract_variables

    try:
        namen = extract_variables(pfad)
    except Exception as exc:  # noqa: BLE001
        raise VorlageUngeeignet(
            f"Die Vorlage ließ sich nicht lesen: {exc}") from exc
    if "inhalt" not in {str(n).split(".", 1)[0].split("[", 1)[0] for n in namen}:
        raise VorlageUngeeignet(
            "Die Vorlage hat keine Stelle für den Text des Dokuments. "
            "Setze an die gewünschte Position {{ inhalt }}.")


# ── Auswahl und Vorauswahl ──────────────────────────────────────────────────

def engine_modul(modul: str) -> str:
    """Dokument-Modulschlüssel → Vorlagen-Engine-Schlüssel (``ai_act`` → ``aiact``)."""
    from shared.reports.vorlagen import engine_modul as _em

    return _em(modul)


def vorlagen(modul: str, doc_type: str = "", *,
             firmen_id: int | None = None) -> list[dict[str, Any]]:
    """Auswählbare Vorlagen für dieses Dokument.

    Mit ``firmen_id`` kommen die Vorlagen **dieses** Mandanten und die
    Haus-Vorlagen; ohne auflösbaren Mandanten nur die Haus-Vorlagen. Das ist
    die engere Seite, und sie ist richtig: Eine Kundenvorlage trägt den Namen
    eines fremden Mandanten (#1778).
    """
    from shared.templates import db as tdb

    try:
        recs = tdb.list_templates(tdb.DEFAULT_DB_PATH, engine_modul(modul),
                                  firmen_id=firmen_id,
                                  nur_haus=firmen_id in (None, 0))
    except Exception:  # noqa: BLE001 — ohne Vorlagen-DB bleibt der Export nutzbar
        return []
    aus: list[dict[str, Any]] = []
    for r in recs:
        if not r.get("aktiv", 1):
            continue
        bt = r.get("bericht_typ")
        if not gilt_fuer(bt, doc_type):
            continue
        aus.append({"id": r["id"], "name": r["name"], "version": r.get("version"),
                    "ist_default": bool(r.get("ist_default")),
                    "bericht_typ": str(bt or ""),
                    "doc_type": doc_type_aus_scope(bt),
                    "firmen_id": r.get("firmen_id")})
    return aus


def vorauswahl(modul: str, doc_type: str, *, firmen_id: int | None = None,
               alle: list[dict[str, Any]] | None = None) -> int:
    """Welche Vorlage ist vorausgewählt? (0 = programmatischer Standard)

    Rangfolge: Mandanten-Vorlage für genau diesen Dokumenttyp → Haus-Vorlage
    für genau diesen Dokumenttyp → Mandanten-Vorlage für alle Dokumente →
    Haus-Vorlage für alle Dokumente. Ein modulweiter **Berichts**-Standard
    kommt nie in Frage (siehe Modul-Docstring).

    Die Rechnung steht hier und nicht im Frontend: Dieselbe Rangfolge an zwei
    Stellen läuft auseinander, und dann meint die Anzeige eine andere Vorlage
    als der Export (#1703/S9).
    """
    if alle is None:
        alle = vorlagen(modul, doc_type, firmen_id=firmen_id)
    # **Selbst filtern, nicht auf den Aufrufer vertrauen.** Eine Vorlage ohne
    # Geltungsbereich hat ``doc_type == ""`` — genau wie eine modulweite
    # Dokument-Vorlage. Die Rangfolge unten konnte sie deshalb wählen, sobald
    # eine ungefilterte Liste hereinkam, und damit war die Zusage aus #1777
    # beim ersten Aufrufer wieder offen. Eine Funktion, die stillschweigend
    # voraussetzt, dass jemand anders gefiltert hat, ist keine Zusage.
    defaults = [v for v in alle
                if v["ist_default"] and ist_dokument_scope(v.get("bericht_typ"))]
    fid = firmen_id if firmen_id not in (None, 0) else None
    dt = str(doc_type or "").strip()

    for treffer in (
        lambda v: v["doc_type"] == dt and dt and v["firmen_id"] == fid and fid is not None,
        lambda v: v["doc_type"] == dt and dt and v["firmen_id"] is None,
        lambda v: not v["doc_type"] and v["firmen_id"] == fid and fid is not None,
        lambda v: not v["doc_type"] and v["firmen_id"] is None,
    ):
        for v in defaults:
            if treffer(v):
                return int(v["id"])
    return 0


def pruefe(modul: str, template_id: int, doc_type: str, *,
           firmen_id: int | None = None) -> dict[str, Any]:
    """Darf diese Vorlage für dieses Dokument benutzt werden?

    Wirft ``shared.reports.vorlagen.VorlageFehlt`` mit Klartext. Geprüft wird
    dasselbe wie beim Bericht (Existenz, Modulzugehörigkeit, Mandant) **plus**
    der Dokument-Geltungsbereich: Eine Berichts-Vorlage dieses Moduls darf hier
    nicht durchrutschen, ihr Kontext ist ein anderer.
    """
    from shared.reports.vorlagen import VorlageFehlt
    from shared.templates import db as tdb

    rec = tdb.get_template(tdb.DEFAULT_DB_PATH, int(template_id))
    if not rec or not rec.get("aktiv", 1):
        raise VorlageFehlt(f"Vorlage {template_id} nicht gefunden")
    if rec.get("modul") != engine_modul(modul):
        raise VorlageFehlt(
            f"Vorlage {template_id} gehört zu Modul '{rec.get('modul')}', "
            f"nicht zu '{engine_modul(modul)}'")
    bt = rec.get("bericht_typ")
    if not ist_dokument_scope(bt):
        raise VorlageFehlt(
            f"Vorlage „{rec.get('name')}“ ist keine Dokument-Vorlage. Sie ist "
            f"für das Berichts-Center hinterlegt und bekommt dort einen anderen "
            f"Kontext.")
    if not gilt_fuer(bt, doc_type):
        raise VorlageFehlt(
            f"Vorlage „{rec.get('name')}“ gilt für den Dokumenttyp "
            f"'{doc_type_aus_scope(bt)}', angefordert wurde '{doc_type}'")
    eigen = tdb._firmen_id(rec.get("firmen_id"))
    if eigen and firmen_id and int(eigen) != int(firmen_id):
        raise VorlageFehlt(
            f"Vorlage „{rec.get('name')}“ gehört zu einem anderen Mandanten")
    return rec


def vorlage_name(modul: str, template_id: int) -> str:
    """Name für den Revisionspfad; leer, wenn nicht ermittelbar.

    Der Export schreibt ``<modul>.dokument.exported``; ohne den Namen stünde
    dort nicht, **womit** das herausgegebene Dokument erzeugt wurde — und genau
    das ist die Frage, die bei einem Dokument im falschen Briefkopf gestellt
    wird (#1778/#1784).
    """
    from shared.templates import db as tdb

    try:
        rec = tdb.get_template(tdb.DEFAULT_DB_PATH, int(template_id)) or {}
    except Exception:  # noqa: BLE001
        return ""
    name = _s(rec.get("name"))
    return f"{name} v{rec.get('version', '')}".strip() if name else ""


def _anzeige_sprache() -> str:
    """Die Sprache des Bedieners (Admin-UI, Variablenliste) — #2089."""
    try:
        from shared.sprache import anzeige_sprache
        return anzeige_sprache()
    except Exception:  # noqa: BLE001 — Sprache bricht keinen Upload
        return ""


def _inhalt_sprache(modul: str, projekt: str) -> str:
    """Die Inhaltssprache des Mandanten (gedrucktes Dokument) — #2089.

    Die beiden Kanäle dürfen auseinanderlaufen: Ein deutscher Bearbeiter
    arbeitet für einen englischen Mandanten (#1954). Was gedruckt wird, folgt
    dem Mandanten.
    """
    try:
        from shared.reports import texte as _rt
        return _rt.aufloesen(modul, projekt or "", "")
    except Exception:  # noqa: BLE001
        return ""
