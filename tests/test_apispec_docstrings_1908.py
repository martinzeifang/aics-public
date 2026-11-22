"""Endpunkt-Docstrings dürfen die API-Spezifikation nicht brechen (#1908).

**Was passiert ist.** Ein ausführlicher Docstring an ``POST /api/admin/update``
ließ ``GET /api/apispec.json`` mit HTTP 500 antworten:

    yaml.scanner.ScannerError: mapping values are not allowed here

Und damit nicht nur diesen Endpunkt, sondern **die ganze Spezifikation** samt
Swagger-Oberfläche.

**Die Ursache, nachgelesen statt vermutet.** ``flasgger/utils.py`` tut dies:

    yaml_sep = full_doc.find('---')
    ...
    swag = yaml.safe_load(full_doc[yaml_sep:])

Ein nacktes ``find('---')`` — **kein Zeilenanker, keine Rücksicht auf
Backticks.** Jedes Vorkommen von drei Bindestrichen irgendwo im Docstring macht
alles dahinter zu YAML. Bei mir war es zuerst eine RST-Überschrift
(``------------``), danach — beim *Erklären* des Fehlers im Kommentar — die
Zeichenfolge in Anführungsstrichen. Beide Male brach ein ``wort: wert`` im
Text, der danach stand.

**Der erste Anlauf dieses Prüfers war zu eng** und meldete über 30
Bestandsstellen, die nachweislich funktionieren (``Body: {…}`` und Ähnliches) —
weil er die Regel geraten hatte statt sie nachzulesen. Ein Prüfer, dessen
Ausgabe man nicht mehr liest, prüft nichts (#1805/#1834). Jetzt bildet er genau
die drei Zeilen oben nach: **ohne** ``---`` ist jeder Text erlaubt, **mit**
``---`` muss der Teil dahinter gültiges YAML sein.

Warum überhaupt, wenn ``test_modules_smoke.py::TestSwaggerDocs::test_apispec_json``
es ohnehin findet: Der prüft das **Ergebnis** und braucht dafür App und
Datenbank — in der CI 16 Minuten Test-Shard. Dieser hier prüft die **Ursache**
in einer Sekunde und nennt Datei, Funktion und Zeile.
"""
from __future__ import annotations

import ast
from pathlib import Path

import yaml

WURZEL = Path(__file__).resolve().parents[1]
API = WURZEL / "server" / "api"

#: Genau die Zeichenfolge, nach der Flasgger sucht (``full_doc.find('---')``).
TRENNER = "---"


def _routen_docstrings() -> list[tuple[str, str, str]]:
    """``(datei, funktionsname, docstring)`` für jede Blueprint-Route."""
    gefunden: list[tuple[str, str, str]] = []
    for datei in sorted(API.rglob("*.py")):
        try:
            baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
        except SyntaxError:
            continue
        for knoten in ast.walk(baum):
            if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Eine Route erkennt man am Dekorator `@<etwas>_bp.get/post/...`.
            ist_route = any(
                isinstance(ziel := (dek.func if isinstance(dek, ast.Call) else dek),
                           ast.Attribute)
                and ziel.attr in ("get", "post", "put", "patch", "delete", "route")
                and isinstance(ziel.value, ast.Name)
                and ziel.value.id.endswith("_bp")
                for dek in knoten.decorator_list)
            if not ist_route:
                continue
            doc = ast.get_docstring(knoten)
            if doc:
                gefunden.append(
                    (datei.relative_to(WURZEL).as_posix(), knoten.name, doc))
    return gefunden


def _flasgger_yaml_teil(doc: str) -> str | None:
    """Der Teil, den Flasgger als YAML liest — ``None``, wenn es keinen gibt."""
    pos = doc.find(TRENNER)
    return None if pos < 0 else doc[pos:]


def test_es_gibt_ueberhaupt_routen_zu_pruefen():
    """Sonst wäre dieser Prüfer still grün und nützlich wie keiner."""
    routen = _routen_docstrings()
    assert len(routen) > 100, (
        f"Nur {len(routen)} Routen-Docstrings gefunden — die Erkennung passt "
        "nicht mehr zu den Blueprints")


def test_jeder_yaml_teil_laesst_sich_lesen():
    """Die eigentliche Regel.

    Bricht ein einziger Docstring, antwortet ``/api/apispec.json`` mit 500 —
    und die Swagger-Oberfläche ist für **alle** Endpunkte weg.
    """
    kaputt: list[str] = []
    for datei, name, doc in _routen_docstrings():
        teil = _flasgger_yaml_teil(doc)
        if teil is None:
            continue
        try:
            yaml.safe_load(teil)
        except yaml.YAMLError as exc:
            erste = str(exc).strip().splitlines()[0]
            kaputt.append(f"{datei}::{name} — {erste}")
    assert not kaputt, (
        "Flasgger liest ab dem ersten „---\" alles als YAML, und hier geht das "
        "schief → GET /api/apispec.json antwortet 500 (auch die "
        "Swagger-Oberfläche):\n  " + "\n  ".join(kaputt)
        + "\n\nEntweder den Doppelpunkt im Prosa-Teil umformulieren oder die "
        "drei Bindestriche entfernen — auch in Anführungsstrichen zählen sie.")


def test_kein_zufaelliges_dreifach_minus_im_prosa_teil():
    """Drei Bindestriche in der Erklärung machen sie zum Schema.

    Zulässig ist der **absichtliche** Trenner: Danach folgt die
    OpenAPI-Beschreibung (``tags:``, ``responses:`` …). Beanstandet wird, wenn
    der Teil dahinter aussieht wie weitergehende Prosa — das ist das Muster,
    das hier zweimal zugeschlagen hat.
    """
    verdaechtig: list[str] = []
    for datei, name, doc in _routen_docstrings():
        teil = _flasgger_yaml_teil(doc)
        if teil is None:
            continue
        geladen = None
        try:
            geladen = yaml.safe_load(teil)
        except yaml.YAMLError:
            continue          # fängt der Test oben, mit besserer Meldung
        # Ein echter Spezifikationsteil ist ein Mapping mit bekannten
        # Schlüsseln. Eine Zeichenkette heißt: Der „Trenner" war Prosa, und
        # alles dahinter ist als Beschreibung verloren gegangen.
        if isinstance(geladen, str):
            verdaechtig.append(f"{datei}::{name} — {geladen.strip()[:80]}")
    assert not verdaechtig, (
        "Hier wirkt ein „---\" im Text als YAML-Trenner; was dahinter steht, "
        "ist für Flasgger die Spezifikation und nicht mehr Erklärung:\n  "
        + "\n  ".join(verdaechtig))


def test_der_pruefer_findet_den_echten_fall():
    """Nachweis mit genau dem Docstring, der es ausgelöst hat."""
    kaputt = (
        "Stößt ein Update an.\n\n"
        "WAS HIER FALSCH WAR\n"
        "-------------------\n"
        "An Stack 45 hängt ollama mit 3,2 GB (gemessen: 35 Minuten).\n"
    )
    teil = _flasgger_yaml_teil(kaputt)
    assert teil is not None, "Der RST-Unterstrich muss als Trenner gelten"
    with __import__("pytest").raises(yaml.YAMLError):
        yaml.safe_load(teil)

    # Und der zweite Anlauf: die Zeichenfolge in Anführungsstrichen.
    zweiter = (
        "Stößt ein Update an.\n\n"
        "Hinweis: keine RST-Unterstriche (``-----``) hier; ein wort: wert "
        "darin bricht die Spezifikation.\n"
    )
    teil2 = _flasgger_yaml_teil(zweiter)
    assert teil2 is not None, (
        "Flasgger nutzt ein nacktes find('---') — Backticks schützen nicht")


def test_der_pruefer_ist_nicht_zu_eng():
    """Der erste Anlauf meldete 30 funktionierende Bestandsstellen."""
    harmlos = [
        "Lädt ein Projekt oder liefert 404.",
        'Body: { "code": "123456" }',
        "Optionale Query-Filter: ``source`` (rb|cra), ``severity``.",
        "Schritt 6 final: ausgewählte Risiken in DB speichern.",
    ]
    for doc in harmlos:
        assert _flasgger_yaml_teil(doc) is None, (
            f"Ohne „---\" liest Flasgger nichts als YAML: {doc!r}")

    # Und ein echter Spezifikationsteil bleibt unbeanstandet.
    echt = (
        "Legt etwas an.\n"
        "---\n"
        "tags:\n"
        "  - admin\n"
        "responses:\n"
        "  200:\n"
        "    description: ok\n"
    )
    assert isinstance(yaml.safe_load(_flasgger_yaml_teil(echt)), dict)
