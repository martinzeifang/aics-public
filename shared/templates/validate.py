"""Prüft die Variablen einer hochgeladenen Word-Vorlage gegen ein Modul (#1741).

Der Anlass: Eine Vorlage mit den Variablen des Compliance-Audit-Moduls
(``wasserstand``, ``fragen``, ``luecken`` …) lag als **Standard** für ``cra``.
CRA liefert diese Variablen nicht; ``ChainableUndefined`` rendert sie leer, bis in
Zeile 11 ein ``round``-Filter darauf zugreift — ``TypeError``, HTTP 500, und im
Frontend stand nur „Bericht konnte nicht erzeugt werden". Jeder CRA-Export war
kaputt, bis jemand den Standard entfernte.

Die Information, die gefehlt hat, lag die ganze Zeit vor: ``extract_variables()``
kennt die Variablen der Vorlage, ``schema.get_variables()`` die des Moduls — und
weil alle acht Listen vorliegen, lässt sich auch sagen, **wohin** eine fremde
Variable gehört („``wasserstand`` gehört zu Compliance-Audit"). Genau das baut
dieses Modul zusammen.

Zwei Fallen, die den Vergleich sonst unbrauchbar machen:

* **Ebenen.** ``extract_variables()`` liefert nur Top-Level-Namen (``meta``), die
  Module deklarieren überwiegend Blattpfade (``meta.datum``). Verglichen wird
  deshalb immer das **erste Pfadsegment** — sonst wäre jede Vorlage voller
  Fehlalarme.
* **Der Kontext ist mehr als das Modul-Schema.** Die Berichts-Center-Brücke legt
  ``bericht_typ`` und ``zeitraum`` zusätzlich in den Kontext. Diese Variablen sind
  in keiner Modul-Liste deklariert, aber in jedem Modul vorhanden.

Kein Füllen von Lücken: Es wird geprüft und benannt, nicht ersetzt. Eine fehlende
Zahl als „0 %" in einen Compliance-Bericht zu drucken wäre schlimmer als ein
Fehler — der Bericht sieht dann korrekt aus und ist falsch.

**Die Gegenrichtung (#1753).** Bisher ging es nur um Variablen, die ein Modul
*nicht* liefert. Manche Dokumente haben aber Variablen, die eine Vorlage
benutzen **muss**: Die EU-Konformitätserklärung ist ohne die Pflichtangaben aus
Anhang V unwirksam, und eine freie Vorlage kann sie weglassen. Bei einem Bericht
ist die Vorlage Geschmacksfrage, bei der Erklärung ein Rechtsrisiko — deshalb
wird eine Vorlage dieses Dokuments zusätzlich auf Vollständigkeit geprüft, und
eine lückenhafte Vorlage lässt sich nicht als Standard setzen. Die Pflichtliste
steht beim Dokument selbst (``cra/doc_export.py``), nicht hier: eine zweite
Liste derselben Angaben wäre die Fehlerklasse aus #1731.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from shared.templates import schema

#: Anzeigenamen für die Meldung. „``wasserstand`` gehört zu compliance_audit"
#: hilft weniger als „… zu Compliance-Audit" — der Anwender sieht im Admin-UI die
#: Labels, nicht die Modulschlüssel.
MODUL_LABEL: dict[str, str] = {
    "cra": "CRA",
    "nis2": "NIS2",
    "aiact": "AI Act",
    "dsgvo": "DSGVO",
    "risikobewertung": "Risikobewertung",
    "wiba": "WiBA",
    "soc": "SOC",
    "compliance_audit": "Compliance-Audit",
}

#: Vom Rahmen beigesteuerte Kontext-Variablen, die in **keiner** Modul-Liste
#: stehen und trotzdem in jedem Modul funktionieren: ``shared/reports/vorlagen.py``
#: legt sie bei jedem Vorlagen-Export dazu, damit eine Vorlage auf den gewählten
#: Berichtstyp verzweigen kann. Ohne diesen Eintrag würde die Prüfung genau die
#: Vorlagen abweisen, die das vorgesehene Merkmal nutzen.
#: ``tests/test_vorlagen_pruefung_1741.py`` hält Liste und Brücke zusammen.
ZUSATZ_WURZELN: frozenset[str] = frozenset({"bericht_typ", "zeitraum"})

#: Jinja stellt diese Namen selbst bereit; ``find_undeclared_variables`` meldet sie
#: trotzdem als undeklariert. Als „unbekannte Variable" wären sie irreführend.
JINJA_GLOBALS: frozenset[str] = frozenset({
    "range", "dict", "lipsum", "cycler", "namespace", "joiner", "loop",
})


#: Module mit Pflicht-Dokumenten: Modulschlüssel → (Modulpfad, Symbol). Guarded
#: import wie bei den Kontext-Adaptern (``schema.py``) — ein Modul ohne Eintrag
#: wird wie bisher nur auf unbekannte Variablen geprüft.
PFLICHT_QUELLEN: dict[str, tuple[str, str]] = {
    "cra": ("cra.doc_export", "PFLICHT_VORLAGEN"),
}


def pflicht_vorlagen(modul: str) -> list[dict[str, Any]]:
    """Pflicht-Dokumente eines Moduls (leer, wenn es keine gibt).

    Jeder Eintrag beschreibt ein Dokument: ``erkennung`` ist die Variablen-
    Wurzel, an der eine Vorlage sich als dieses Dokument ausweist, ``angaben``
    sind die Pflichtangaben mit ihrer Nummer im Rechtstext.
    """
    eintrag = PFLICHT_QUELLEN.get(engine_modul(modul))
    if not eintrag:
        return []
    pfad, symbol = eintrag
    try:
        import importlib

        return list(getattr(importlib.import_module(pfad), symbol) or [])
    except Exception:  # noqa: BLE001 — ohne Quelle gilt nur die bisherige Prüfung
        return []


def _wurzel(name: str) -> str:
    """Erstes Pfadsegment — der einzige Teil, auf dem beide Seiten vergleichbar sind.

    Trennt an ``.`` und an ``[``, damit auch ``risiken[0]`` auf ``risiken`` fällt.
    """
    roh = str(name or "").strip()
    for trenner in (".", "["):
        roh = roh.split(trenner, 1)[0]
    return roh.strip()


def engine_modul(modul: str) -> str:
    """Modulschlüssel normalisieren (``ai_act`` → ``aiact``).

    Die Abbildung lebt in der Berichts-Center-Brücke (#1735); eine zweite Tabelle
    derselben Zuordnung wäre eine weitere Stelle, die auseinanderlaufen kann.
    Der Import ist absichtlich verzögert: ``shared.reports`` liegt über
    ``shared.templates`` und importiert von hier.
    """
    try:
        from shared.reports.vorlagen import engine_modul as _em
        return _em(modul)
    except Exception:  # noqa: BLE001 — Normalisierung darf die Prüfung nie verhindern
        return str(modul or "")


def deklarierte_wurzeln(modul: str) -> set[str]:
    """Top-Level-Namen, die ein Modul in seinem Kontext anbietet."""
    em = engine_modul(modul)
    wurzeln = {_wurzel(v.get("key", "")) for v in schema.get_variables(em)}
    wurzeln.discard("")
    return wurzeln | set(ZUSATZ_WURZELN)


def wurzeln_je_modul() -> dict[str, list[str]]:
    """Umkehrung: Top-Level-Name → Module, die ihn deklarieren.

    Das ist die Tabelle, aus der der Hinweis „gehört zu Compliance-Audit" kommt.
    """
    out: dict[str, list[str]] = {}
    for m in schema.MODULE:
        for v in schema.get_variables(m):
            w = _wurzel(v.get("key", ""))
            # Ein Modul nur einmal je Wurzel: ``wasserstand.stufe`` und
            # ``wasserstand.quote`` sind zwei Deklarationen, aber eine Herkunft —
            # sonst stünde „gehört zu Compliance-Audit / Compliance-Audit" im Text.
            if w and m not in out.setdefault(w, []):
                out[w].append(m)
    return out


# ── Pflichtangaben: was eine Vorlage benutzen MUSS ──────────────────────────
# Für die Pflichtprüfung reicht die Variablenliste von ``extract_variables()``
# nicht: Jinja meldet nur Wurzeln (``doc`` für ``{{ doc.ort }}``), und ob die
# Vorlage „Ort und Datum" enthält, steht gerade im Pfad dahinter. Deshalb wird
# die Vorlagendatei hier noch einmal geöffnet und ihr Jinja-Baum ausgelesen.

def _pfad_zum_namen(knoten: Any) -> str:
    """Punkt-Pfad eines Jinja-Zugriffs (``doc.unterzeichner_name``).

    Ein Index (``risiken[0]``) endet den Pfad, weil er ohne Laufvariable nichts
    über das Feld dahinter sagt.
    """
    from jinja2 import nodes

    teile: list[str] = []
    cur = knoten
    while isinstance(cur, (nodes.Getattr, nodes.Getitem)):
        if isinstance(cur, nodes.Getattr):
            teile.append(str(cur.attr))
        elif isinstance(cur.arg, nodes.Const) and isinstance(cur.arg.value, str):
            teile.append(str(cur.arg.value))
        else:
            teile = []          # dynamischer Index → Pfad nicht auswertbar
        cur = cur.node
    if not isinstance(cur, nodes.Name) or not teile:
        return ""
    return ".".join([cur.name, *reversed(teile)])


def vorlage_inhalt(pfad: Path | str) -> tuple[set[str], str]:
    """(Variablen-Pfade, Fließtext) einer Vorlagendatei.

    Der Fließtext wird mitgegeben, weil zwei Anhang-V-Angaben Gesetzesformeln
    sind (Alleinverantwortung, Nennung der Verordnung). Eine Vorlage darf sie
    wörtlich enthalten statt über eine Variable; eine reine Variablenprüfung
    würde solche — vollständig korrekten — Vorlagen zu Unrecht abweisen.

    Aufgebaut wie ``DocxTemplate.get_undeclared_template_variables``: Word
    zerlegt ``{{ doc.ort }}`` gern in mehrere Runs, erst ``patch_xml`` fügt die
    Tags wieder zusammen. Kopf- und Fußzeilen gehören dazu — Ort und Datum
    stehen dort öfter als im Fließtext.
    """
    from docx import Document
    from docx.oxml import parse_xml
    from docxtpl import DocxTemplate
    from jinja2 import Environment, nodes

    tpl = DocxTemplate(str(pfad))
    temp = Document(str(pfad))
    xml = tpl.patch_xml(tpl.xml_to_string(temp._element.body))
    for uri in (tpl.HEADER_URI, tpl.FOOTER_URI):
        for _rel, val in temp._part.rels.items():
            if val.reltype == uri and val.target_part.blob:
                xml += tpl.patch_xml(tpl.xml_to_string(parse_xml(val.target_part.blob)))

    tokens: set[str] = set()
    try:
        # `autoescape=True`, obwohl hier **nur geparst und nie gerendert** wird:
        # Für die Token-Gewinnung ist die Einstellung wirkungslos. Bandit stuft
        # ein Environment ohne sie aber als B701 (Hoch) ein, und eine
        # Unterdrückungs-Anweisung für etwas, das ohnehin die sichere Variante
        # sein soll, wäre der schlechtere Tausch: Sie bliebe stehen, wenn hier
        # eines Tages doch gerendert wird. (Das Schlüsselwort selbst steht
        # bewusst nicht in diesem Kommentar — Bandit liest es auch hier und
        # würde die Zeile dann wirklich übergehen.)
        baum = Environment(autoescape=True).parse(xml)
    except Exception:  # noqa: BLE001 — unparsierbare Vorlage fällt beim Rendern auf
        baum = None
    if baum is not None:
        for knoten in baum.find_all((nodes.Getattr, nodes.Getitem)):
            name = _pfad_zum_namen(knoten)
            if name:
                tokens.add(name)
        for knoten in baum.find_all(nodes.Name):
            tokens.add(str(knoten.name))
    text = re.sub(r"<[^>]+>", " ", xml)
    return tokens, text


def _angabe_belegt(angabe: dict[str, Any], tokens: set[str], text: str) -> bool:
    """Trägt die Vorlage diese Angabe?

    ``tokens`` müssen **alle** vorkommen (eine Produktidentifikation ohne Typ
    identifiziert nichts); ``alternativen`` ersetzen die ganze Angabe (z. B.
    ``doc.normen_text`` statt ``doc.normen``), ``textbeleg`` deckt die
    wörtlich ausgeschriebene Gesetzesformel.
    """
    pflicht = [str(t) for t in (angabe.get("tokens") or [])]
    if pflicht and all(t in tokens for t in pflicht):
        return True
    if any(str(a) in tokens for a in (angabe.get("alternativen") or [])):
        return True
    beleg = str(angabe.get("textbeleg") or "").strip()
    return bool(beleg) and beleg.lower() in text.lower()


def _fehlende_angaben(spec: dict[str, Any], tokens: set[str],
                      text: str) -> list[dict[str, Any]]:
    """Pflichtangaben eines Dokuments, die die Vorlage nicht benutzt."""
    return [{"dokument": str(spec.get("dokument") or ""),
             "rechtsgrundlage": str(spec.get("rechtsgrundlage") or ""),
             "nr": a.get("nr"), "bezeichnung": str(a.get("bezeichnung") or ""),
             "tokens": list(a.get("tokens") or [])}
            for a in (spec.get("angaben") or [])
            if not _angabe_belegt(a, tokens, text)]


def pflicht_befunde(modul: str,
                    kandidaten: list[tuple[set[str], str]]) -> list[dict[str, Any]]:
    """Beweisbar fehlende Pflichtangaben über alle Kandidaten hinweg.

    Mehrere Kandidaten gibt es, wenn aus einer Variablenliste nicht eindeutig
    hervorgeht, welche Datei gemeint ist (siehe
    :func:`_kandidaten_aus_registry`). Gemeldet wird dann nur, was in **allen**
    Kandidaten fehlt — das fehlt unabhängig davon, welche Vorlage es ist.
    Geraten wird nichts.
    """
    specs = pflicht_vorlagen(modul)
    if not specs or not kandidaten:
        return []
    je_kandidat: list[dict[tuple, dict[str, Any]]] = []
    for tokens, text in kandidaten:
        treffer: dict[tuple, dict[str, Any]] = {}
        for spec in specs:
            wurzel = str(spec.get("erkennung") or "")
            if wurzel and wurzel not in {_wurzel(t) for t in tokens}:
                continue    # die Vorlage schreibt dieses Dokument nicht
            for fehlt in _fehlende_angaben(spec, tokens, text):
                treffer[(fehlt["dokument"], fehlt["nr"], fehlt["bezeichnung"])] = fehlt
        je_kandidat.append(treffer)
    gemeinsam = set(je_kandidat[0])
    for weitere in je_kandidat[1:]:
        gemeinsam &= set(weitere)
    return [je_kandidat[0][k] for k in je_kandidat[0] if k in gemeinsam]


def _kandidaten_aus_registry(modul: str,
                             namen: Iterable[str]) -> list[tuple[set[str], str]]:
    """Vorlagendateien, auf die diese Variablenliste passt.

    Warum nötig: Wer über „als Standard setzen" entscheidet
    (``server/api/templates``), hat nur die beim Upload gespeicherte
    Variablenliste — und die kennt nur Wurzeln. Für die Pflichtprüfung braucht
    es die Datei. Gesucht wird deshalb unter den Vorlagen des Moduls die, deren
    gespeicherte Liste genau diese ist.

    Treffer können mehrere sein (zwei Vorlagen dürfen dieselben Wurzeln
    benutzen); :func:`pflicht_befunde` meldet dann nur, was in allen fehlt.
    Kein Treffer → keine Aussage; die Prüfung mit Datei
    (:func:`pruefe_variablen`) bleibt davon unberührt.
    """
    try:
        from shared.templates import db as tdb

        recs = tdb.list_templates(tdb.DEFAULT_DB_PATH, engine_modul(modul))
    except Exception:  # noqa: BLE001 — ohne Registry keine Aussage
        return []
    ziel = sorted({str(n) for n in namen})
    out: list[tuple[set[str], str]] = []
    for rec in recs:
        if not rec.get("aktiv", 1):
            continue
        try:
            gespeichert = sorted({str(n) for n in
                                  json.loads(rec.get("variablen_json") or "[]")})
        except Exception:  # noqa: BLE001
            continue
        pfad = str(rec.get("datei_pfad") or "")
        if gespeichert != ziel or not pfad:
            continue
        try:
            out.append(vorlage_inhalt(pfad))
        except Exception:  # noqa: BLE001 — unlesbare Datei ist ein anderer Fehler
            continue
    return out


@dataclass
class Pruefergebnis:
    """Ergebnis einer Variablen-Prüfung — als Antwort-Body und als Meldung nutzbar."""

    modul: str
    variablen: list[str] = field(default_factory=list)
    unbekannt: list[dict[str, Any]] = field(default_factory=list)
    #: #1753: Pflichtangaben eines Dokuments, die die Vorlage nicht benutzt.
    fehlende_pflicht: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.unbekannt and not self.fehlende_pflicht

    @property
    def namen(self) -> list[str]:
        """Nur die Namen der unbekannten Variablen — für knappe Meldungen."""
        return [u["name"] for u in self.unbekannt]

    @property
    def pflicht_meldung(self) -> str:
        """Welche Pflichtangaben fehlen — mit ihrer Nummer im Rechtstext (#1753).

        Die Nummer ist der eigentliche Inhalt der Meldung: „Nr. 8: Ort und
        Datum fehlt" sagt dem Anwender, was er in seine Vorlage schreiben muss,
        und zugleich, warum es nicht verhandelbar ist.
        """
        if not self.fehlende_pflicht:
            return ""
        dokument = str(self.fehlende_pflicht[0].get("dokument") or "das Dokument")
        grundlage = str(self.fehlende_pflicht[0].get("rechtsgrundlage") or "")
        luecken = "; ".join(f"Nr. {f.get('nr')}: {f.get('bezeichnung')} fehlt"
                            for f in self.fehlende_pflicht)
        return (f"Die Vorlage erzeugt „{dokument}“, lässt aber Pflichtangaben aus: "
                f"{luecken}. Ohne diese Angaben ist das Dokument unwirksam"
                + (f" ({grundlage})" if grundlage else "")
                + " — die Vorlage kann deshalb nicht als Standard gesetzt werden.")

    @property
    def meldung(self) -> str:
        """Ein Satz Klartext für Anwender und Fehlerantwort."""
        label = MODUL_LABEL.get(self.modul, self.modul)
        if self.ok:
            return (f"Alle {len(self.variablen)} Variablen der Vorlage sind im Modul "
                    f"{label} vorhanden.")
        if not self.unbekannt:
            # Nur Pflichtangaben fehlen: Die Variablen passen zum Modul, das
            # Dokument ist aber unvollständig.
            return self.pflicht_meldung
        teile: list[str] = []
        # Nach Herkunft gruppieren: „a, b gehören zu X" liest sich besser als
        # dieselbe Herkunft hinter jeder einzelnen Variable.
        gruppen: dict[tuple[str, ...], list[str]] = {}
        for u in self.unbekannt:
            gruppen.setdefault(tuple(u["bekannt_in"]), []).append(u["name"])
        for herkunft, namen in gruppen.items():
            liste = ", ".join(namen)
            if herkunft:
                quelle = " / ".join(MODUL_LABEL.get(m, m) for m in herkunft)
                teile.append(f"{liste} {'gehört' if len(namen) == 1 else 'gehören'} "
                             f"zu {quelle}")
            else:
                teile.append(f"{liste} {'ist' if len(namen) == 1 else 'sind'} in keinem "
                             f"Modul deklariert")
        satz = (f"Die Vorlage passt nicht zum Modul {label}: "
                f"{', '.join(self.namen)} {'wird' if len(self.namen) == 1 else 'werden'} "
                f"dort nicht geliefert ({'; '.join(teile)}).")
        return f"{satz} {self.pflicht_meldung}".strip()

    def as_dict(self) -> dict[str, Any]:
        return {"modul": self.modul, "ok": self.ok, "variablen": list(self.variablen),
                "unbekannt": list(self.unbekannt),
                "fehlende_pflicht": list(self.fehlende_pflicht),
                "meldung": self.meldung}


def pruefe_namen(modul: str, namen: Iterable[str], *,
                 inhalt: tuple[set[str], str] | None = None) -> Pruefergebnis:
    """Vergleicht fertige Variablennamen mit den Deklarationen eines Moduls.

    Der Vergleich auf unbekannte Variablen bleibt eine reine Funktion ohne
    Datei- oder DB-Zugriff — dadurch auch für die in der Registry gespeicherte
    Variablenliste nutzbar (``variablen_json``), ohne die Vorlagendatei erneut
    zu öffnen.

    Die Pflichtprüfung (#1753) braucht mehr als Wurzeln. ``inhalt`` ist der
    direkte Weg (Tokens + Fließtext, siehe :func:`vorlage_inhalt`); fehlt er
    und deutet die Namensliste auf ein Pflicht-Dokument, wird die Datei über
    die Registry gesucht. Ohne Fund bleibt die Pflichtprüfung stumm, statt eine
    Vorlage auf Verdacht abzuweisen.
    """
    em = engine_modul(modul)
    bekannt = deklarierte_wurzeln(em)
    herkunft = wurzeln_je_modul()

    variablen = sorted({str(n) for n in namen if str(n).strip()})
    unbekannt: list[dict[str, Any]] = []
    for name in variablen:
        w = _wurzel(name)
        if not w or w in bekannt or w in JINJA_GLOBALS:
            continue
        quellen = [m for m in herkunft.get(w, []) if m != em]
        unbekannt.append({
            "name": name,
            "wurzel": w,
            "bekannt_in": quellen,
            "bekannt_in_labels": [MODUL_LABEL.get(m, m) for m in quellen],
        })
    kandidaten: list[tuple[set[str], str]] = []
    if inhalt is not None:
        kandidaten = [inhalt]
    elif _deutet_auf_pflichtdokument(em, variablen):
        kandidaten = _kandidaten_aus_registry(em, variablen)
    return Pruefergebnis(modul=em, variablen=variablen, unbekannt=unbekannt,
                         fehlende_pflicht=pflicht_befunde(em, kandidaten))


def _deutet_auf_pflichtdokument(modul: str, namen: list[str]) -> bool:
    """Benutzt diese Variablenliste die Wurzel eines Pflicht-Dokuments?

    Nur dann lohnt der Griff zur Datei. Jede andere Vorlage des Moduls bleibt
    von der Pflichtprüfung unberührt — ein Gesamtbericht benutzt ``doc.*``
    nicht.
    """
    wurzeln = {_wurzel(n) for n in namen}
    return any(str(spec.get("erkennung") or "") in wurzeln
               for spec in pflicht_vorlagen(modul))


def pruefe_variablen(modul: str, pfad: Path | str) -> Pruefergebnis:
    """Prüft eine Vorlagendatei gegen ein Modul.

    Lässt sich die Datei nicht lesen (gelöscht, kein DOCX), bleibt das Ergebnis
    leer und damit ``ok``: Eine nicht lesbare Datei ist ein anderer Fehler und
    wird an ihrer Stelle gemeldet, nicht als „falsches Modul".

    Die Variablen für den Modul-Vergleich kommen weiter aus
    ``extract_variables`` (Wurzeln) — daran hängt die Meldung aus #1741. Für
    die Pflichtprüfung wird zusätzlich der tiefe Inhalt gelesen.
    """
    from shared.templates.engine import extract_variables
    try:
        namen = extract_variables(pfad)
    except Exception:  # noqa: BLE001
        namen = []
    try:
        inhalt = vorlage_inhalt(pfad)
    except Exception:  # noqa: BLE001 — ohne Inhalt bleibt die Pflichtprüfung stumm
        inhalt = None
    return pruefe_namen(modul, namen, inhalt=inhalt)
