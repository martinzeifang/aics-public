"""Die Modul-Hilfe gibt es in beiden Sprachen — und sie bleibt deckungsgleich (#1954).

DER GRÖSSTE EINZELNE POSTEN
Die Hilfe war mit **1.353 Texten** der größte Block der Übersetzung — mehr als
alle Masken zusammen. Sie lag als `help/<modul>.ts`, acht davon mit dem Kopf
„Auto-generiert (#926)" und einem reinen Datenobjekt darin.

WARUM JSON UND NICHT vue-i18n
Die Hilfe ist kein Vorrat von Beschriftungen, sondern ein **Dokument** mit
Listen beliebiger Länge (`bullets`, `pflichtfelder`, `tipps`, `areas`). Über
`t()` bräuchte jeder Eintrag einen eigenen Schlüssel, und die Länge einer Liste
ließe sich nicht mehr aus den Daten ablesen. Als JSON bleibt die Struktur Teil
des Inhalts — und **dieser Test kann sie lesen**, was der eigentliche Grund für
das Format ist (dieselbe Überlegung wie in `i18n/index.ts`).

WAS HIER FESTGEHALTEN WIRD
Struktur-Parität in beide Richtungen: gleiche Schlüssel, gleich viele Einträge
je Liste, gleiche `areas` in gleicher Reihenfolge, gleiche Adressen. Eine
englische Fassung mit drei statt fünf Pflichtfeldern ist keine Übersetzung,
sondern eine andere Aussage über die Rechtslage — und sie fällt niemandem auf,
weil nichts fehlschlägt (die Klasse aus #1805/#1870).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
HILFE = WURZEL / "frontend" / "src" / "help"
INDEX = HILFE / "index.ts"
SPRACHEN = ("de", "en")

#: Die Felder von ``ModuleHelp``, die Text tragen. Aus ``types.ts``, aber
#: ausdrücklich hier wiederholt: Ein neues Feld soll den Test **rot** machen
#: und nicht stillschweigend unübersetzt bleiben.
PFLICHT_FELDER = ("module", "title", "regulation", "purpose",
                  "legalBasis", "implementation")

#: Adressen gehören nicht zur Übersetzung. `docs:`-Marken löst der Lader auf.
ADRESS_FELDER = ("href",)


def _ohne_kommentare(text: str) -> str:
    """JS-/TS-Kommentare entfernen (Lehre aus #1834 und vier Wiederholungen)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(z for z in text.split("\n")
                     if not z.lstrip().startswith(("//", "*")))


def _module() -> list[str]:
    """Die Modulschlüssel aus ``DATEI_JE_MODUL`` in ``help/index.ts``.

    Gelesen wird die **Zuordnung**, nicht ein Verzeichnis: Eine Datei, die
    niemand registriert, erreicht keinen Anwender, und ein Eintrag ohne Datei
    liefert keine Hilfe. Beides soll auffallen.
    """
    quelle = INDEX.read_text(encoding="utf-8")
    block = re.search(r"DATEI_JE_MODUL:\s*Record<string, string>\s*=\s*\{(.*?)\n\}",
                      quelle, re.S)
    assert block, "DATEI_JE_MODUL nicht gefunden"
    paare = re.findall(r"^\s*'?([\w-]+)'?\s*:\s*'([\w-]+)'", block.group(1), re.M)
    assert paare, "Zuordnung konnte nicht gelesen werden"
    return [datei for _, datei in paare]


def _lies(code: str, datei: str) -> dict:
    return json.loads((HILFE / code / f"{datei}.json").read_text(encoding="utf-8"))


def _vorhanden(code: str, datei: str) -> bool:
    return (HILFE / code / f"{datei}.json").exists()


def _geruest(wert, pfad: str = "") -> dict[str, str]:
    """Die **Form** eines Dokuments, ohne seine Wörter.

    Zu jedem Pfad die Art (``str``/``list[n]``/``dict``). Ein Vergleich der
    Wörter wäre sinnlos — ein Vergleich der Form ist genau das, was zwei
    Sprachfassungen desselben Dokuments gemeinsam haben müssen.
    """
    out: dict[str, str] = {}
    if isinstance(wert, dict):
        out[pfad or "."] = "dict"
        for k, v in wert.items():
            out.update(_geruest(v, f"{pfad}.{k}" if pfad else k))
    elif isinstance(wert, list):
        out[pfad] = f"list[{len(wert)}]"
        for i, v in enumerate(wert):
            out.update(_geruest(v, f"{pfad}[{i}]"))
    else:
        out[pfad] = type(wert).__name__
    return out


def _texte(wert, pfad: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    if isinstance(wert, dict):
        for k, v in wert.items():
            out.update(_texte(v, f"{pfad}.{k}" if pfad else k))
    elif isinstance(wert, list):
        for i, v in enumerate(wert):
            out.update(_texte(v, f"{pfad}[{i}]"))
    elif isinstance(wert, str):
        out[pfad] = wert
    return out


# ── Bestand ──────────────────────────────────────────────────────────────────

def test_jedes_registrierte_modul_hat_eine_deutsche_fassung():
    fehlt = [m for m in _module() if not _vorhanden("de", m)]
    assert not fehlt, f"registriert, aber ohne Katalogdatei: {fehlt}"


def test_jede_katalogdatei_ist_registriert():
    """Die Gegenrichtung — die Lehre aus #1878.

    Eine Datei, die niemand registriert, ist totes Gewicht: Sie wird
    mitgebaut, mitgewartet und erreicht keinen Anwender.
    """
    registriert = set(_module())
    for code in SPRACHEN:
        ordner = HILFE / code
        if not ordner.exists():
            continue
        vorhanden = {p.stem for p in ordner.glob("*.json")}
        fremd = vorhanden - registriert
        assert not fremd, f"{code}: nicht registrierte Dateien: {sorted(fremd)}"


def test_der_lader_kennt_keine_hilfe_ts_mehr():
    """Nach dem Umzug darf keine Modul-Hilfe mehr als TypeScript liegen.

    Sonst gibt es sie zweimal — und die `.ts` wäre die Fassung, die niemand
    übersetzt (#1731/#1735).
    """
    reste = sorted(p.name for p in HILFE.glob("*.ts")
                   if p.name not in ("index.ts", "types.ts", "docsUrl.ts"))
    assert not reste, f"Modul-Hilfe noch als TypeScript: {reste}"


# ── Parität ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("datei", _module())
def test_struktur_ist_in_jeder_sprache_dieselbe(datei):
    """Gleiche Form, nicht gleiche Wörter.

    Eine englische Fassung mit drei statt fünf Pflichtfeldern ist keine
    Übersetzung, sondern eine andere Aussage über die Rechtslage.
    """
    if not _vorhanden("en", datei):
        pytest.skip(f"{datei}: englische Fassung steht noch aus")
    de, en = _geruest(_lies("de", datei)), _geruest(_lies("en", datei))
    abweichung = {p: (de.get(p), en.get(p)) for p in set(de) | set(en)
                  if de.get(p) != en.get(p)}
    assert not abweichung, f"{datei}: {abweichung}"


@pytest.mark.parametrize("datei", _module())
def test_pflichtfelder_sind_gefuellt(datei):
    for code in SPRACHEN:
        if not _vorhanden(code, datei):
            continue
        daten = _lies(code, datei)
        for feld in PFLICHT_FELDER:
            assert daten.get(feld), f"{code}/{datei}: {feld} fehlt"
        for pfad, text in _texte(daten).items():
            assert text.strip(), f"{code}/{datei}: {pfad} ist leer"


@pytest.mark.parametrize("datei", _module())
def test_adressen_und_bereichs_ids_bleiben_gleich(datei):
    """`id` und `href` sind **Technik**, nicht Text.

    Die `id` eines Bereichs ist die Tab-id der View (kontext-sensitives
    Öffnen, #1223) — übersetzt sie jemand, öffnet die Hilfe den falschen
    Bereich oder keinen. Dasselbe gilt für `module`.
    """
    if not _vorhanden("en", datei):
        pytest.skip(f"{datei}: englische Fassung steht noch aus")
    de, en = _lies("de", datei), _lies("en", datei)
    assert de["module"] == en["module"], f"{datei}: Modulschlüssel übersetzt"
    assert ([a["id"] for a in de.get("areas") or []]
            == [a["id"] for a in en.get("areas") or []]), (
        f"{datei}: Bereichs-ids weichen ab")
    for i, (a, b) in enumerate(zip(de.get("links") or [], en.get("links") or [])):
        # `docs:` zeigt auf **unsere** Seite — dieselbe in jeder Sprache. Eine
        # Abweichung wäre ein Tippfehler, den niemand bemerkt.
        if a["href"].startswith("docs:") or b["href"].startswith("docs:"):
            assert a["href"] == b["href"], f"{datei}: links[{i}].href weicht ab"
            continue
        # Fremde Adressen **dürfen** abweichen, und das ist der Zweck: Der
        # EUR-Lex-Link gehört in der englischen Hilfe auf `/EN/TXT/`, nicht auf
        # `/DE/TXT/`, und neben die deutsche Aufsichtsbehörde gehört dort der
        # EDSA. Ein Prüfer, der das beanstandet, erzwingt eine Übersetzung, die
        # den Leser auf einen deutschen Rechtstext schickt.
        for adresse in (a["href"], b["href"]):
            assert adresse.startswith(("http://", "https://")), (
                f"{datei}: links[{i}] ist keine absolute Adresse: {adresse!r}")


@pytest.mark.parametrize("datei", _module())
def test_die_uebersetzung_ist_eine_uebersetzung(datei):
    """Kein Abschnitt darf wörtlich die deutsche Fassung sein.

    Eine kopierte Datei erfüllt jede Struktur-Prüfung und ist keine
    Übersetzung — genau der Fall, den `test_die_listen_sind_nicht_dieselbe_liste`
    in #1954 für die Begriffsliste abfängt. Geprüft werden die langen Texte;
    kurze Bezeichnungen sind zu Recht oft gleich („SBOM", „CRA").
    """
    if not _vorhanden("en", datei):
        pytest.skip(f"{datei}: englische Fassung steht noch aus")
    de, en = _texte(_lies("de", datei)), _texte(_lies("en", datei))
    gleich = [p for p, t in de.items()
              if len(t) >= 60 and en.get(p) == t and not p.endswith("href")]
    assert not gleich, f"{datei}: unübersetzt geblieben: {gleich[:5]}"


@pytest.mark.parametrize("datei", _module())
def test_sinnbilder_der_bereiche_bleiben_gleich(datei):
    """Der Tab heißt in der Oberfläche „📊 Dashboard" — das Bild gehört dazu."""
    if not _vorhanden("en", datei):
        pytest.skip(f"{datei}: englische Fassung steht noch aus")
    import unicodedata

    def bild(t: str) -> str:
        return t.split(" ", 1)[0] if t and unicodedata.category(t[0]) == "So" else ""

    de, en = _lies("de", datei), _lies("en", datei)
    for a, b in zip(de.get("areas") or [], en.get("areas") or []):
        assert bild(a["title"]) == bild(b["title"]), (
            f"{datei}/{a['id']}: Sinnbild weicht ab "
            f"({bild(a['title'])!r} vs {bild(b['title'])!r})")


# ── Die Lücke wird benannt ───────────────────────────────────────────────────

def test_offene_sprachfassungen_sind_benannt():
    """Eine benannte Lücke ist etwas anderes als eine stillschweigende.

    Solange Module ohne englische Fassung sind, fällt die Hilfe dort **ganz**
    auf Deutsch zurück (nicht gemischt — ein zweisprachiges Dokument liest sich
    wie ein Fehler). Dieser Test meldet den Stand, damit er in der Ausgabe
    steht und nicht in einer Annahme.
    """
    offen = sorted(m for m in _module() if not _vorhanden("en", m))
    print(f"\nEnglische Hilfe offen für: {offen or 'keine — alle übersetzt'}")
    assert len(offen) < len(_module()), (
        "keine einzige englische Fassung — der Lader hätte nichts zu tun")

def test_der_wiki_generator_liest_die_echte_hilfe():
    """`tools/wiki/gen.mts` erzeugt Wiki und Handbuch aus der Hilfe.

    Bis #1954 importierte er `./help/index.ts` — eine **unversionierte Kopie**
    der Modul-Hilfe. In einem frischen Klon fehlte sie ganz, und mit jedem
    Hilfe-Update entfernte sie sich weiter von der Anwendung: Das Wiki und das
    daraus erzeugte Handbuch sagten dann etwas anderes als das Produkt. Dieselbe
    Fehlerklasse wie #1731/#1735, nur schweigend.
    """
    # **Ohne Kommentare.** Der Dateikopf von `gen.mts` zitiert den alten Pfad,
    # um zu erklären, warum er weg ist — und daran wurde dieser Test beim ersten
    # Anlauf rot. Dieselbe Falle wie #1834/#1867/#1878/#1903/#1954: das Programm
    # prüfen, nicht die Erzählung.
    quelle = _ohne_kommentare(
        (WURZEL / "tools" / "wiki" / "gen.mts").read_text(encoding="utf-8"))
    assert "./help/index.ts" not in quelle, (
        "der Generator liest wieder die Kopie unter tools/wiki/help/")
    # Auf das **Katalog-Verzeichnis**, nicht auf `frontend/src/help/` allgemein:
    # Den Teilstring enthält auch der Lesepfad von `docsUrl.ts`, und damit blieb
    # die erste Fassung dieser Zusicherung grün, als der Generator wieder auf
    # eine Kopie zeigte. In der Rotprobe aufgefallen — eine Prüfung, die bei
    # ihrem eigenen Fehlerbild grün bleibt, prüft nichts (#1805).
    assert re.search(r"frontend/src/help/(?:\$\{\w+\}|de|en)/", quelle), (
        "der Generator liest die Hilfe-Kataloge der Anwendung nicht")
    assert ".json" in quelle, "der Generator liest keine Katalogdateien"
    # Und die Doku-Domain wird gelesen, nicht abgeschrieben (#1011).
    basis = (WURZEL / "frontend" / "src" / "help" / "docsUrl.ts").read_text(
        encoding="utf-8")
    domain = re.search(r"PUBLIC_DOCS_BASE_URL\s*=\s*'([^']+)'", basis)
    assert domain, "PUBLIC_DOCS_BASE_URL nicht gefunden"
    assert domain.group(1) not in quelle, (
        f"gen.mts schreibt die Doku-Domain {domain.group(1)!r} ab — sie gehoert "
        f"aus docsUrl.ts gelesen")

