"""Daten aus einer anderen Installation **übernehmen**, nicht überschreiben (#1808/#1810).

DER BEFUND, DER ZU DIESEM MODUL GEFÜHRT HAT

Ein Archiv der Testinstanz wurde auf der Produktivinstallation eingespielt, in
der Erwartung, die Daten kämen **dazu**. ``stelle_wieder_her`` macht aber
``TRUNCATE … CASCADE`` auf jede Tabelle, die im Archiv steht. Weg waren elf von
zwölf Mandanten, drei von vier DSGVO-Projekten, 63 von 66 Nachweisdokumenten.
Unberührt blieb nur, was die Quelle gar nicht hatte.

Der Restore ist für den **Wiederanlauf** gebaut und tut dort das Richtige. Was
fehlte, ist der zweite Anwendungsfall, und der ist mindestens so häufig: Daten
aus einer anderen Installation holen, ohne den eigenen Bestand zu verlieren.

WIE ES HIER GEMACHT WIRD

*Kein* ``TRUNCATE``, *kein* ``UPDATE``. Es werden ausschließlich Zeilen
**eingefügt**, und zwar die eines ausgewählten Mandanten. Was im Ziel schon
steht, bleibt wie es ist — es sei denn, der Betreiber entscheidet für einen
einzelnen Mandanten ausdrücklich anders.

DIE SCHLÜSSELFRAGE: TECHNISCHE IDs

Zwischen zwei Installationen bedeutet dieselbe Zahl etwas anderes. Zeile 7 ist
hier die Firma A und dort das Projekt B. Deshalb:

* **Fachlicher Name ist der Schlüssel.** Zugeordnet wird über
  ``firmen.name``, ``projekt_name`` und Verwandte — nie über die ID.
* **Alle technischen IDs eines Laufs wandern um denselben Versatz.** Das ist
  die ganze Kunst: Weil *jede* ID im Archiv um dieselbe Zahl verschoben wird,
  bleibt jeder Verweis innerhalb des Archivs richtig, ohne dass dieses Modul
  wissen muss, worauf er zeigt. Der Versatz liegt über dem höchsten Wert, den
  das Ziel kennt — eine Kollision ist damit ausgeschlossen, nicht
  unwahrscheinlich.
* **Eine Ausnahme: ``firmen_id``.** Existiert der Mandant im Ziel bereits, muss
  der Verweis auf **dessen** Zeile zeigen, nicht auf eine verschobene. Diese
  Zuordnung wird über den Namen gebildet und ist die einzige Stelle, an der
  umgerechnet statt verschoben wird.

WARUM DIE ARBEIT IN SQL PASSIERT

Jede Tabelle läuft über eine temporäre Kopie: ``COPY`` aus dem Archiv hinein,
Filtern und Verschieben per ``UPDATE``/``DELETE``, dann ``INSERT … SELECT`` in
die Zieltabelle. Grund ist nicht Geschwindigkeit, sondern Genauigkeit: Das
Archiv schreibt mit ``FORCE_QUOTE *``, weil nur so die leere Zeichenkette von
NULL zu unterscheiden ist (#1785). Pythons CSV-Leser kennt diesen Unterschied
nicht — er würde aus ``notiz = ''`` ein ``NULL`` machen, über den ganzen
Datenbestand, ohne eine Fehlermeldung. PostgreSQL liest sein eigenes Format
richtig.

TABELLEN, DIE ES IM ZIEL NOCH NICHT GIBT (#1879)

Eine Tabelle, die diese Installation nicht kennt, wird aus der Archivstruktur
**angelegt** — und zwar nur, soweit die Übernahme sie auch nehmen will. Ohne
diesen Schritt blieben ihre Zeilen stillschweigend liegen: ``_gemeinsame_spalten``
meldete „Tabelle gibt es auf dieser Installation nicht", der Bericht nannte eine
Null, und niemand liest eine Null. Betroffen ist jede Tabelle, die sich erst
beim ersten Zugriff selbst anlegt — darunter ``linked_issues`` (steht in keinem
``ensure_db`` und nicht im Warmup; ``shared/issue_links.ensure_tables`` legt sie
an, sobald das erste Issue verknüpft wird). Genau das war der Befund aus dem
Betrieb: Mandanten, Projekte und Nachweise kamen an, die Issue-Verknüpfungen
nicht.

WAS AUSDRÜCKLICH NICHT MITWANDERT

Revisionspfad, Zeitpläne, Lizenz- und Instanzkonfiguration, Passkeys. Der
Revisionspfad gehört zu der Installation, auf der gehandelt wurde; ein Passkey
ist an die Domain gebunden und auf der Zielinstallation wertlos (#1811). Siehe
``NICHT_UEBERNOMMEN`` — dort steht je Position der Grund, und der Bericht nennt
sie.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, Iterable

from shared.backup import dateien as f_dateien
from shared.backup import datenbank as f_db
from shared.backup import paket as f_paket


class UebernahmeFehler(RuntimeError):
    """Die Übernahme konnte nicht sicher laufen."""


# ── Was übernommen wird, und was nicht ──────────────────────────────────────

#: Schemata, deren Inhalt zu einem Mandanten gehört und mitwandern kann.
#:
#: ``ki_herkunft`` (#1765) und ``prompt_hinweise`` (#1835) sind geteilte
#: Register in **eigenen** Schemata und fehlten hier (#1879) — eine Liste, die
#: zwei Module vergisst, ist die Fehlerklasse aus #1731/#1735. Beide führen
#: Projektdaten (``modul`` + ``projekt_name``) und werden wie jede andere
#: Tabelle über den Projektnamen gefiltert. Beim KI-Prüfvermerk ist die Folge
#: mehr als eine Lücke: ``_check_ki_pruefung`` im CRA-Release-Gate meldet nach
#: einer Übernahme ungeprüfte KI-Entwürfe, die längst geprüft sind.
FACHSCHEMATA = (
    "firmen", "cra", "nis2", "ai_act", "dsgvo", "risikobewertung", "wiba",
    "gutachten", "pentest", "evidence", "templates",
    "ki_herkunft", "prompt_hinweise",
)

#: Schemata, die bewusst draußen bleiben — mit dem Grund, der im Bericht steht.
#:
#: Einträge für **entfernte** Module bleiben hier stehen (DORA seit #1500, SOC
#: seit #1905): Alte Archive führen deren Tabellen weiter, und sie sollen auch
#: künftig nicht stillschweigend eingespielt werden. Die Positivliste
#: ``FACHSCHEMATA`` wächst nicht von selbst mit — genau daran hing #1879.
NICHT_UEBERNOMMEN = {
    "audit": "Der Revisionspfad gehört zu der Installation, auf der gehandelt wurde.",
    "scheduler": "Zeitpläne gehören zur Installation, nicht zu den Daten.",
    "soc": "Das SOC-Modul ist seit v8.3.0 entfernt (#1905).",
    "dora": "Das DORA-Modul ist seit v6.25.0 entfernt (#1500).",
    "public": "Hilfsfunktionen der Datenbank, keine Daten.",
}

#: Spalten, über die eine Zeile ihrem Projekt zugeordnet ist. Die Vielfalt ist
#: historisch gewachsen; sie hier aufzuzählen ist ehrlicher, als sie zu erraten.
ZUORDNUNGSSPALTEN = (
    "projekt_name", "projekt", "project_name", "rb_projekt_name", "audit_projekt",
)

#: Tabellen, deren Zeilen zu einem **Mandanten** (nicht Projekt) gehören.
MANDANTENSPALTEN = ("firma", "unternehmen", "organisation")

#: Kinder ohne eigene Zuordnungsspalte: ``(schema, tabelle) -> (eltern, fk)``.
#:
#: Sie hängen allein an der ID ihres Elternteils. Weil alle IDs um denselben
#: Versatz wandern, bleibt die Kette richtig — aber **welche** Zeilen überhaupt
#: mitkommen, lässt sich nur über die Eltern entscheiden.
KINDER: dict[tuple[str, str], tuple[str, str]] = {
    ("cra", "cra_doc_checklist"): ("cra_managed_docs", "doc_id"),
    ("nis2", "nis2_doc_checklist"): ("nis2_managed_docs", "doc_id"),
    ("ai_act", "ai_act_doc_checklist"): ("ai_act_managed_docs", "doc_id"),
    ("dsgvo", "dsgvo_doc_checklist"): ("dsgvo_managed_docs", "doc_id"),
    ("wiba", "wiba_doc_checklist"): ("wiba_managed_docs", "doc_id"),
    ("pentest", "pentest_findings"): ("pentest_berichte", "bericht_id"),
    ("evidence", "evidence_text"): ("evidence_documents", "doc_id"),
    ("evidence", "evidence_chunks"): ("evidence_documents", "doc_id"),
    ("gutachten", "gerichtsgutachten_hypothesen"):
        ("gerichtsgutachten_beurteilungen", "beurteilung_id"),
    ("nis2", "nis2_governance_teilnehmer"): ("nis2_governance_nachweis", "nachweis_id"),
}

#: Stammdaten, die vollständig mitkommen, weil Projektzeilen sie per ID
#: referenzieren (Gutachter-Profile, Hilfspersonen, Werkzeug-Register).
#:
#: Sie sind nicht mandantengebunden; ließe man sie weg, zeigte
#: ``gutachten.gerichtsgutachten.gutachter_profil_id`` ins Leere. Ein Duplikat
#: im Register ist das kleinere Übel als ein Verweis auf nichts — und es ist
#: eines, das ein Mensch sieht und zusammenführen kann.
STAMMDATEN = frozenset({
    ("gutachten", "gutachter_profile"),
    ("gutachten", "hilfspersonen"),
    ("gutachten", "gutachten_werkzeuge_register"),
})

#: Tabellen, die trotz Zuordnungsspalte draußen bleiben.
#:
#: Ein Änderungsprotokoll hält fest, wer **auf dieser Installation** was getan
#: hat; übernommen wäre es die Behauptung, es sei hier geschehen. Die
#: Berichtsläufe verweisen auf Dateien, die zur Quellinstanz gehören.
UEBERGANGEN = frozenset({
    ("risikobewertung", "rb_change_log"),
    ("cra", "cra_bericht_runs"), ("nis2", "nis2_bericht_runs"),
    ("ai_act", "ai_act_bericht_runs"), ("dsgvo", "dsgvo_bericht_runs"),
    ("wiba", "wiba_bericht_runs"), ("gutachten", "gutachten_bericht_runs"),
    ("firmen", "firmen_bericht_runs"),
    ("risikobewertung", "risikobewertung_bericht_runs"),
})

#: Tabellen im ``users``-Schema, die bei ``mit_benutzern`` mitkommen.
#:
#: Passkeys bleiben draußen: Sie sind an die Domain gebunden (#1811) und auf der
#: Zielinstallation nicht verwendbar — mitgenommen erzeugen sie ein Konto, das
#: einen zweiten Faktor verlangt, den niemand erfüllen kann. Genau der Fall, der
#: den Betreiber aus seiner eigenen Installation ausgesperrt hat.
BENUTZER_TABELLEN = ("users", "user_groups", "user_group_members")

#: Was beim Namensgleichstand passieren soll.
KOLLISIONEN = ("behalten", "ersetzen")

#: Die Tabelle, deren Fremdverweis in einer **Textspalte** steckt.
#:
#: ``linked_issues`` ist *eine* Tabelle (eine DDL in ``shared/issue_links``), die
#: in sechs Schemata liegt — cra, nis2, ai_act, dsgvo, risikobewertung, wiba.
#: Darum wird sie hier über den Namen angesprochen und nicht je Schema
#: aufgezählt: Es ist derselbe Sachverhalt, nicht sechs ähnliche.
ISSUE_TABELLE = "linked_issues"

#: Objektarten, deren ``object_id`` eine **laufende Nummer** ist (#1879).
#:
#: ``linked_issues.object_id`` ist TEXT und trägt zweierlei: bei den Arten unten
#: die Zeilennummer des Objekts (``cra_vuln.id``, ``rb_risiken.id``,
#: ``<modul>_managed_docs.id``, ``aiact_incidents.id``), bei allen übrigen einen
#: fachlichen Schlüssel (``CRA-A-01``). Die Nummern müssen mit dem Versatz
#: wandern; der Text darf es nicht.
#:
#: Warum das wichtiger ist, als es aussieht: Bliebe die Nummer stehen, zeigte die
#: Verknüpfung nach einer Übernahme in eine **bespielte** Installation nicht ins
#: Leere, sondern auf eine **fremde, hier bereits vorhandene** Schwachstelle. Das
#: ist der stille Fehler aus #1773 — die Verknüpfung sieht aus wie eine Aussage.
OBJEKT_ID_IST_NUMMER = frozenset({
    "vuln", "risk", "cra_doc", "aiact_incident", "soc_incident",
})

#: Objektarten mit fachlichem Schlüssel — ausdrücklich genannt, damit eine neue
#: Art nicht stillschweigend als „kein Fall" durchläuft. Der Wächtertest in
#: ``tests/test_uebernahme_issues_1879.py`` hält beide Mengen gegen die
#: ``object_kind``-Werte, die die Anwendung wirklich schreibt.
OBJEKT_ID_IST_FACHSCHLUESSEL = frozenset({
    "requirement", "owasp", "owasp_llm", "wiba_control",
})


# ── Lesen: was steckt im Archiv? ────────────────────────────────────────────

def _csv_zeilen(zf: zipfile.ZipFile, eintrag: str) -> Iterable[list[str]]:
    """Eine Archiv-Tabelle zeilenweise — nur zum **Anzeigen**.

    Für das Einspielen wird das Archiv nicht hier geparst, sondern von
    PostgreSQL (siehe Modulkopf). Für eine Inhaltsübersicht genügt diese
    Sicht, weil dort nur Namen und Zahlen gebraucht werden.
    """
    import csv
    import io

    with zf.open(eintrag) as fh:
        text = io.StringIO(fh.read().decode("utf-8", "replace"), newline="")
        yield from csv.reader(text)


def _spalten_aus_struktur(struktur: dict[str, Any], schema: str,
                          tabelle: str) -> list[str]:
    bau = (struktur.get("schemata", {}).get(schema, {})
           .get("tabellen", {}).get(tabelle) or {})
    return [s["name"] for s in bau.get("spalten", [])]


#: Projekttabellen je Modul: ``(schema, tabelle, namensspalte)``.
PROJEKTTABELLEN = (
    ("cra", "cra_projekte", "CRA"),
    ("nis2", "nis2_projekte", "NIS2"),
    ("ai_act", "ai_act_projekte", "AI Act"),
    ("dsgvo", "dsgvo_projekte", "DSGVO"),
    ("wiba", "wiba_projekte", "WiBA"),
    ("risikobewertung", "rb_projekte", "Risikobewertung"),
    ("gutachten", "gutachten_projects", "Compliance-Audit"),
    ("gutachten", "gerichtsgutachten", "Gutachten"),
)


def inhalt(archiv: Path) -> dict[str, Any]:
    """Was das Archiv enthält — je Mandant, mit Projekten und Zahlen.

    Zeigt außerdem, was es im Ziel **schon gibt**: Das ist die Grundlage für
    die Kollisionsfrage, und ohne sie wäre die Auswahl ein Blindflug.
    """
    archiv = Path(archiv)
    info = f_paket.beschreibe(archiv)
    if int(info.get("format") or 1) < f_paket.FORMAT_VERSION:
        raise UebernahmeFehler(
            "Archiv im alten Format (bis v8.0.4): Es enthält keine "
            "Datenbankinhalte und kann nicht übernommen werden.")

    with zipfile.ZipFile(archiv, "r") as zf:
        struktur = f_db.struktur_aus_json(zf.read("struktur.json"))
        vorhanden = set(zf.namelist())

        # Mandanten des Archivs
        mandanten: dict[str, dict[str, Any]] = {}
        eintrag = "db/firmen/firmen.csv"
        if eintrag in vorhanden:
            spalten = _spalten_aus_struktur(struktur, "firmen", "firmen")
            i_name = spalten.index("name") if "name" in spalten else None
            i_unt = spalten.index("unternehmen") if "unternehmen" in spalten else None
            for zeile in _csv_zeilen(zf, eintrag):
                if i_name is None or i_name >= len(zeile):
                    continue
                name = zeile[i_name]
                if not name:
                    continue
                mandanten[name] = {
                    "name": name,
                    "unternehmen": zeile[i_unt] if i_unt is not None and i_unt < len(zeile) else "",
                    "projekte": [],
                }

        # Projekte je Mandant — über Name, `unternehmen`/`organisation`
        # (Zuordnung wie in firmen/uebersicht.py) statt über die ID.
        for schema, tabelle, modul in PROJEKTTABELLEN:
            eintrag = f"db/{schema}/{tabelle}.csv"
            if eintrag not in vorhanden:
                continue
            spalten = _spalten_aus_struktur(struktur, schema, tabelle)
            if "name" not in spalten:
                continue
            i_name = spalten.index("name")
            i_firma = next((spalten.index(s) for s in MANDANTENSPALTEN
                            if s in spalten), None)
            for zeile in _csv_zeilen(zf, eintrag):
                if i_name >= len(zeile) or not zeile[i_name]:
                    continue
                projekt = zeile[i_name]
                firma = (zeile[i_firma] if i_firma is not None and i_firma < len(zeile)
                         else "")
                schluessel = _mandant_fuer(projekt, firma, mandanten)
                mandanten.setdefault(schluessel, {
                    "name": schluessel, "unternehmen": "", "projekte": [],
                })["projekte"].append({
                    "modul": modul, "schema": schema, "tabelle": tabelle,
                    "name": projekt,
                })

    im_ziel = _namen_im_ziel()
    for name, eintrag_m in mandanten.items():
        eintrag_m["im_ziel"] = name in im_ziel["firmen"]
        eintrag_m["im_ziel_gelöscht"] = name in im_ziel["firmen_gelöscht"]
        for p in eintrag_m["projekte"]:
            p["im_ziel"] = p["name"] in im_ziel["projekte"].get(p["schema"], set())

    return {
        "archiv": info,
        "mandanten": sorted(mandanten.values(), key=lambda m: m["name"].lower()),
        "nicht_uebernommen": dict(NICHT_UEBERNOMMEN),
    }


def _mandant_fuer(projekt: str, firma: str, bekannt: dict[str, Any]) -> str:
    """Zu welchem Mandanten gehört dieses Projekt?

    Dieselbe Reihenfolge wie ``firmen/uebersicht.py``: Firmenfeld, dann der
    Projektname selbst (die Auto-Anlage aus #430 benennt das Projekt nach der
    Firma). Ein Projekt ohne Zuordnung erscheint unter seinem eigenen Namen —
    sichtbar statt stillschweigend weggelassen.
    """
    if firma and firma in bekannt:
        return firma
    if projekt in bekannt:
        return projekt
    return firma or projekt


def _namen_im_ziel() -> dict[str, Any]:
    """Firmen- und Projektnamen der Zielinstallation."""
    ergebnis: dict[str, Any] = {"firmen": set(), "firmen_gelöscht": set(),
                                "projekte": {}}
    try:
        pool, conn = f_paket._roh_verbindung()
    except Exception:  # noqa: BLE001 — ohne Datenbank keine Vorschau
        return ergebnis
    try:
        cur = conn.cursor()
        # Ein als gelöscht markierter Mandant (Soft-Delete in `firmen/db.py`)
        # ist für den Anwender weg — er gilt hier nicht als vorhanden, sonst
        # würde die Übernahme ihn stillschweigend überspringen. Seine Zeile
        # belegt aber den Namen; `_firmen_uebernehmen` holt sie deshalb zurück.
        cur.execute("SELECT name, COALESCE(is_deleted, 0) FROM firmen.firmen")
        for name, gelöscht in cur.fetchall():
            if not name:
                continue
            if gelöscht:
                ergebnis["firmen_gelöscht"].add(name)
            else:
                ergebnis["firmen"].add(name)
    except Exception:  # noqa: BLE001
        conn.rollback()
    for schema, tabelle, _modul in PROJEKTTABELLEN:
        try:
            cur = conn.cursor()
            cur.execute(f'SELECT name FROM {f_db._q(schema, tabelle)}')  # nosec B608 — Bezeichner über _q
            ergebnis["projekte"].setdefault(schema, set()).update(
                r[0] for r in cur.fetchall() if r[0])
        except Exception:  # noqa: BLE001 — Tabelle fehlt auf dieser Installation
            conn.rollback()
    # Zurückgeben, nicht schließen: Der Pool gehört der Anwendung.
    try:
        conn.rollback()
        pool.putconn(conn)
    except Exception:  # noqa: BLE001
        pass
    return ergebnis


# ── Übernehmen ──────────────────────────────────────────────────────────────

def _dateien_ergaenzen(zf: zipfile.ZipFile, bericht: dict[str, Any]) -> None:
    """Dateien aus dem Archiv ergänzen, die es hier **noch nicht** gibt.

    Ohne diesen Schritt wäre die Übernahme halb: Die Datensätze verweisen auf
    Dateien — hochgeladene Word-Vorlagen (``template_registry.datei_pfad``),
    Nachweisdokumente (``evidence_documents.stored_path``), finalisierte
    Gutachten, Pentest-PDFs, Kontroll-Anhänge. Kommen die Zeilen ohne ihre
    Dateien, zeigt jeder Download ins Leere, und das sieht nach einem Defekt
    der Anwendung aus statt nach einer unvollständigen Übernahme.

    **Nur ergänzend.** Eine Datei, die hier schon liegt, wird nicht
    überschrieben — das ist dieselbe Regel wie für die Datensätze, und sie ist
    hier noch wichtiger: Die Dateinamen tragen Prüfsummen, und eine
    überschriebene Datei stimmte nicht mehr mit dem SHA-256 im Datensatz der
    Zielinstallation zusammen.

    Dateien, die zu einem **nicht** gewählten Mandanten gehören, kommen mit —
    sie sind ohne ihren Datensatz unerreichbar, und eine Zuordnung von Pfaden
    zu Mandanten gibt es nicht durchgehend. Lieber ein paar Bytes zu viel als
    ein Nachweis, den der Anwender nicht öffnen kann.
    """
    wurzel = f_paket.daten_wurzel()
    wurzel.mkdir(parents=True, exist_ok=True)
    neu = schon = 0
    for name in zf.namelist():
        if not name.startswith("dateien/") or name.endswith("/"):
            continue
        rel = name[len("dateien/"):]
        ziel = f_dateien.ziel_pruefen(rel, wurzel)
        if ziel is None:
            bericht["warnungen"].append(f"Unsicherer Pfad im Archiv übergangen: {rel}")
            continue
        if ziel.exists():
            schon += 1
            continue
        try:
            ziel.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as quelle, open(ziel, "wb") as senke:
                for block in iter(lambda: quelle.read(1024 * 256), b""):
                    senke.write(block)
            neu += 1
        except Exception as e:  # noqa: BLE001 — eine Datei darf den Lauf nicht abbrechen
            bericht["warnungen"].append(f"Datei nicht übernommen: {rel} ({f_db._kurz(e)})")
    bericht["dateien_neu"] = neu
    bericht["dateien_vorhanden"] = schon


def uebernimm(archiv: Path, *, mandanten: list[str],
              bei_kollision: str = "behalten",
              mit_benutzern: bool = False,
              mit_dateien: bool = True,
              trockenlauf: bool = False) -> dict[str, Any]:
    """Die Daten der genannten Mandanten einfügen, ohne Bestand zu löschen.

    ``bei_kollision``
        ``behalten`` — ein Mandant, den es im Ziel schon gibt, wird
        übersprungen. Der Bestand ist eine Aussage; ihn stillschweigend zu
        ersetzen wäre genau der Fehler, der zu diesem Modul geführt hat.
        ``ersetzen`` — die Zeilen dieses Mandanten werden im Ziel entfernt und
        durch die des Archivs ersetzt. Ausdrücklich zu wählen.
    ``mit_benutzern``
        Konten, Gruppen und Mitgliedschaften zusätzlich übernehmen — ohne
        Passkeys (#1811). Ein Konto, das es im Ziel schon gibt (gleiche
        E-Mail), bleibt unverändert; Kennwörter werden nicht angetastet.
    ``mit_dateien``
        Hochgeladene Dateien der übernommenen Datensätze ergänzen (Vorgabe an).
        Vorhandene Dateien bleiben unberührt. Ohne diesen Schritt zeigt jeder
        Download ins Leere — siehe ``_dateien_ergaenzen``.
    ``trockenlauf``
        Alles rechnen, nichts schreiben. Liefert denselben Bericht.
    """
    if bei_kollision not in KOLLISIONEN:
        raise ValueError(f"Unbekannte Kollisionsregel: {bei_kollision!r} "
                         f"(erlaubt: {', '.join(KOLLISIONEN)})")
    archiv = Path(archiv)
    gewaehlt = [m for m in (mandanten or []) if m]
    if not gewaehlt:
        raise ValueError("Es wurde kein Mandant ausgewählt.")

    uebersicht = inhalt(archiv)
    nach_name = {m["name"]: m for m in uebersicht["mandanten"]}
    unbekannt = [m for m in gewaehlt if m not in nach_name]
    if unbekannt:
        raise UebernahmeFehler(
            "Im Archiv nicht enthalten: " + ", ".join(sorted(unbekannt)))

    uebersprungen = [m for m in gewaehlt
                     if nach_name[m]["im_ziel"] and bei_kollision == "behalten"]
    zu_tun = [m for m in gewaehlt if m not in uebersprungen]

    projekte: set[str] = set()
    for m in zu_tun:
        projekte.update(p["name"] for p in nach_name[m]["projekte"])

    bericht: dict[str, Any] = {
        "mandanten": zu_tun,
        "uebersprungen": uebersprungen,
        "projekte": sorted(projekte),
        "bei_kollision": bei_kollision,
        "mit_benutzern": bool(mit_benutzern),
        "mit_dateien": bool(mit_dateien),
        "trockenlauf": bool(trockenlauf),
        "tabellen": 0, "zeilen": 0,
        "je_tabelle": {},
        "warnungen": [],
        "nicht_uebernommen": dict(NICHT_UEBERNOMMEN),
    }
    if not zu_tun:
        bericht["warnungen"].append(
            "Alle gewählten Mandanten gibt es im Ziel bereits — nichts übernommen. "
            "Mit 'ersetzen' würden ihre Daten durch die des Archivs ersetzt.")
        return bericht

    with zipfile.ZipFile(archiv, "r") as zf:
        struktur = f_db.struktur_aus_json(zf.read("struktur.json"))
        _einspielen(zf, struktur, zu_tun, projekte, bericht,
                    bei_kollision=bei_kollision, mit_benutzern=mit_benutzern,
                    trockenlauf=trockenlauf)
        # Dateien **nach** den Datensätzen und nur im echten Lauf: Ein
        # Trockenlauf, der Dateien ablegt, wäre keiner.
        if mit_dateien and not trockenlauf:
            _dateien_ergaenzen(zf, bericht)
    return bericht


def _einspielen(zf: zipfile.ZipFile, struktur: dict[str, Any],
                mandanten: list[str], projekte: set[str],
                bericht: dict[str, Any], *, bei_kollision: str,
                mit_benutzern: bool, trockenlauf: bool) -> None:
    """Alles in **einer** Transaktion — ganz oder gar nicht.

    Ein halb übernommener Mandant wäre das schlechteste Ergebnis: Er sieht aus
    wie ein Mandant.
    """
    pool, conn = f_paket._roh_verbindung()
    try:
        conn.rollback()
        cur = conn.cursor()
        try:
            cur.execute("SET session_replication_role = replica")
        except Exception:  # noqa: BLE001 — braucht erhöhte Rechte
            conn.rollback()
            bericht["warnungen"].append(
                "Fremdschlüssel konnten nicht ausgesetzt werden (fehlende Rechte); "
                "die Reihenfolge der Tabellen kann zu Fehlern führen.")

        # **Vor** allem anderen: Was es hier noch nicht gibt, kann sonst nichts
        # aufnehmen — auch nicht `firmen.firmen` auf einer frischen Installation.
        _fehlende_tabellen_anlegen(conn, zf, struktur, bericht,
                                   mit_benutzern=mit_benutzern)

        versatz = _versatz(conn, cur, struktur)
        bericht["versatz"] = versatz

        firmen_abbildung = _firmen_uebernehmen(
            conn, zf, struktur, mandanten, versatz, bericht)

        if bei_kollision == "ersetzen":
            _bestand_entfernen(conn, struktur, mandanten, projekte, bericht)

        for schema, tabelle, eintrag in _tabellen_in_reihenfolge(zf, struktur):
            if (schema, tabelle) == ("firmen", "firmen"):
                continue  # oben erledigt
            grund = _ueberspringen(schema, tabelle, mit_benutzern)
            if grund:
                bericht.setdefault("ausgelassen", {})[f"{schema}.{tabelle}"] = grund
                continue
            zeilen = _tabelle_uebernehmen(
                conn, schema, tabelle, _spalten_aus_struktur(struktur, schema, tabelle),
                zf.read(eintrag), versatz, firmen_abbildung, mandanten, projekte,
                bericht)
            if zeilen:
                bericht["tabellen"] += 1
                bericht["zeilen"] += zeilen
                bericht["je_tabelle"][f"{schema}.{tabelle}"] = zeilen

        _sequenzen_nachziehen(conn, struktur, bericht)

        try:
            cur.execute("SET session_replication_role = origin")
        except Exception:  # noqa: BLE001
            pass

        if trockenlauf:
            conn.rollback()
        else:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def _tabellen_in_reihenfolge(zf: zipfile.ZipFile,
                             struktur: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Eltern vor Kindern.

    Mit ausgesetzten Fremdschlüsseln wäre die Reihenfolge gleichgültig — ohne
    sie (fehlende Rechte) nicht, und dann soll es trotzdem laufen.
    """
    alle: list[tuple[str, str, str]] = []
    for name in sorted(zf.namelist()):
        if not (name.startswith("db/") and name.endswith(".csv")):
            continue
        teile = name[len("db/"):-len(".csv")].split("/")
        if len(teile) != 2:
            continue
        schema, tabelle = teile
        alle.append((schema, tabelle, name))
    kinder = set(KINDER)
    return ([t for t in alle if (t[0], t[1]) not in kinder]
            + [t for t in alle if (t[0], t[1]) in kinder])


def _fehlende_tabellen_anlegen(conn, zf: zipfile.ZipFile,
                               struktur: dict[str, Any], bericht: dict[str, Any],
                               *, mit_benutzern: bool) -> None:
    """Tabellen anlegen, die das Archiv mitbringt und diese Installation nicht
    hat (#1879).

    DER BEFUND: ``cra.linked_issues`` und ``risikobewertung.linked_issues``
    standen nach einer Übernahme auf 0, während Mandanten, Projekte und
    Nachweise angekommen waren. Der Restore kann das — er ruft
    ``datenbank.struktur_herstellen`` und legt fehlende Tabellen vorher an. Die
    Übernahme hatte dazu kein Gegenstück: ``_gemeinsame_spalten`` fand im Ziel
    keine Spalten, meldete „Tabelle gibt es auf dieser Installation nicht" und
    ließ die Zeilen liegen. Gemeldet wurde kein Fehler, nur eine Null.

    Es trifft jede Tabelle, die sich erst beim ersten Zugriff selbst anlegt.
    ``linked_issues`` ist der Fall, der auffällt: Sie steht in **keinem**
    ``ensure_db`` und nicht in ``shared/warmup._PLAN`` — ``shared/issue_links.
    ensure_tables`` legt sie an, sobald das erste Issue verknüpft wird. Auf einer
    Installation, auf der das nie geschah, war die Übernahme der
    Issue-Verknüpfungen folgenlos. Dieselbe Bauart haben
    ``risk_requirement_links`` (#1564), ``ki_herkunft`` (#1765) und
    ``prompt_hinweise`` (#1835).

    **Nur, was die Übernahme auch nehmen will.** ``struktur_herstellen``
    pauschal zu rufen wäre falsch: Es legte leere SOC-, Revisions- und
    Zeitplan-Tabellen an — das Gegenteil der Zusage aus ``NICHT_UEBERNOMMEN``,
    dass sie nicht mitwandern. Deshalb läuft hier dieselbe Entscheidung wie im
    Haupt-Durchlauf (``_ueberspringen``), und gebaut wird mit den Helfern aus
    ``datenbank.py`` statt mit einem zweiten DDL-Bauer (#1731/#1735).

    Constraints und Indizes gehören dazu: ``_einfuegen`` verlässt sich mit
    ``ON CONFLICT DO NOTHING`` auf den Primärschlüssel und die eindeutigen
    Indizes. Fehlten sie, käme beim zweiten Lauf jede Zeile ein zweites Mal
    herein — eine Übernahme, die Dubletten erzeugt, ist schlimmer als eine, die
    nichts tut.
    """
    cur = conn.cursor()
    angelegt: list[str] = []
    for schema, tabelle, _eintrag in _tabellen_in_reihenfolge(zf, struktur):
        if _ueberspringen(schema, tabelle, mit_benutzern):
            continue
        bau = (struktur.get("schemata", {}).get(schema, {})
               .get("tabellen", {}).get(tabelle) or {})
        if not bau.get("spalten"):
            continue
        if f_db._vorhandene_spalten(cur, schema, tabelle):
            continue
        try:
            # Savepoint je Tabelle: Eine Strukturangabe, die hier nicht mehr
            # passt, darf nicht die ganze Übernahme aufreißen — unter PostgreSQL
            # bricht ein fehlgeschlagenes Statement die **Transaktion** ab.
            with conn.transaction():
                cur.execute(f'CREATE SCHEMA IF NOT EXISTS {f_db._q(schema)}')
                f_db._tabelle_anlegen(conn.cursor(), schema, tabelle, bau)
        except Exception as e:  # noqa: BLE001
            bericht["warnungen"].append(
                f"{schema}.{tabelle}: nicht anlegbar ({f_db._kurz(e)}) — "
                "ihre Zeilen bleiben liegen")
            continue
        f_db._beiwerk_anlegen(conn, schema, tabelle, bau, bericht["warnungen"])
        angelegt.append(f"{schema}.{tabelle}")
    if angelegt:
        # In den Bericht, nicht nur ins Log: Eine Tabelle, die diese
        # Installation noch nicht kannte, ist eine Aussage über den Lauf.
        bericht["tabellen_angelegt"] = angelegt


def _ueberspringen(schema: str, tabelle: str, mit_benutzern: bool) -> str:
    """Grund, diese Tabelle auszulassen — oder ``''``."""
    if schema in NICHT_UEBERNOMMEN:
        return NICHT_UEBERNOMMEN[schema]
    if schema == "users":
        if not mit_benutzern:
            return "Benutzerkonten wurden nicht angefordert."
        if tabelle not in BENUTZER_TABELLEN:
            return ("An die Domain gebundene oder flüchtige Daten "
                    "(Passkeys, Challenges, Token) wandern nicht mit (#1811).")
        return ""
    if (schema, tabelle) in UEBERGANGEN:
        return "Gehört zur Quellinstallation, nicht zu den Daten."
    if schema not in FACHSCHEMATA:
        return f"Schema '{schema}' ist nicht für die Übernahme vorgesehen."
    return ""


# ── Der Versatz ─────────────────────────────────────────────────────────────

def _versatz(conn, cur, struktur: dict[str, Any]) -> int:
    """Eine Zahl, die über jedem technischen Schlüssel des Ziels liegt.

    Alle IDs des Archivs wandern um genau diesen Betrag. Damit ist eine
    Kollision ausgeschlossen und gleichzeitig jeder Verweis **innerhalb** des
    Archivs weiterhin richtig — ohne dass dieses Modul wissen muss, worauf er
    zeigt. Das ist der Grund, warum es nur eine einzige Ausnahme braucht
    (``firmen_id``) und nicht eine Liste aller Verweise.
    """
    hoechste = 0
    for schema in list(struktur.get("schemata", {})) + ["firmen", "users"]:
        if schema in NICHT_UEBERNOMMEN:
            continue
        try:
            with conn.transaction():
                cur.execute(
                    """
                    SELECT c.table_name, c.column_name
                    FROM information_schema.columns c
                    WHERE c.table_schema = %s
                      AND (c.column_name = 'id' OR c.column_name LIKE %s)
                      AND c.data_type IN ('integer', 'bigint')
                    """,
                    (schema, "%\\_id"))
                spalten = cur.fetchall()
        except Exception:  # noqa: BLE001
            continue
        for tabelle, spalte in spalten:
            try:
                # Savepoint je Abfrage: Ein fehlgeschlagenes Statement bricht in
                # PostgreSQL die **Transaktion** ab, nicht nur sich selbst —
                # ohne Savepoint scheiterte danach jede weitere Abfrage mit
                # „current transaction is aborted", und der Versatz käme zu
                # klein heraus. Ein zu kleiner Versatz ist der schlimmste Fall
                # überhaupt: Er erzeugt Kollisionen mit vorhandenen Schlüsseln.
                with conn.transaction():
                    cur.execute(
                        f'SELECT max({f_db._q(spalte)}) FROM {f_db._q(schema, tabelle)}')  # nosec B608 — Bezeichner über _q()
                    wert = (cur.fetchone() or [None])[0]
                if wert:
                    hoechste = max(hoechste, int(wert))
            except Exception:  # noqa: BLE001 — Tabelle/Spalte gibt es hier nicht
                continue
    # Luft nach oben, damit ein paralleler Schreibvorgang während des Laufs
    # nicht in den verschobenen Bereich hineinwächst.
    return hoechste + 10_000


# ── firmen: der einzige Verweis, der umgerechnet wird ───────────────────────

def _firmen_uebernehmen(conn, zf: zipfile.ZipFile, struktur: dict[str, Any],
                        mandanten: list[str], versatz: int,
                        bericht: dict[str, Any]) -> dict[int, int]:
    """Die gewählten Mandanten anlegen und ``alt_id → neu_id`` liefern.

    Hierher kommt nur, was ``uebernimm`` nicht übersprungen hat — bei
    ``behalten`` fehlen vorhandene Mandanten also schon in ``mandanten``.
    Steht der Name dennoch im Ziel (``ersetzen``, oder als gelöscht markiert),
    zeigt die Abbildung auf **dessen** Zeile: Produkte, Projekte und Nachweise
    hängen daran, und eine zweite Firma gleichen Namens wäre für den Betreiber
    nicht unterscheidbar.
    """
    eintrag = "db/firmen/firmen.csv"
    if eintrag not in set(zf.namelist()):
        bericht["warnungen"].append("Das Archiv enthält keine Mandantentabelle.")
        return {}

    spalten = _spalten_aus_struktur(struktur, "firmen", "firmen")
    nehmen = _gemeinsame_spalten(conn, "firmen", "firmen", spalten, bericht)
    if not nehmen or "name" not in nehmen or "id" not in nehmen:
        bericht["warnungen"].append(
            "firmen.firmen: 'id' oder 'name' fehlt — Mandanten nicht übernommen.")
        return {}

    hilfs = _temp_befuellen(conn, "firmen", "firmen", spalten, nehmen,
                            zf.read(eintrag))
    cur = conn.cursor()
    cur.execute(
        f"DELETE FROM {hilfs} WHERE name IS NULL OR NOT (name = ANY(%s))",  # nosec B608 — Bezeichner aus Positivliste
        (mandanten,))

    cur.execute("SELECT name, id, COALESCE(is_deleted, 0) FROM firmen.firmen")
    schon_da = {r[0]: (int(r[1]), bool(r[2])) for r in cur.fetchall()
                if r[0] is not None}

    cur.execute(f"SELECT id, name FROM {hilfs}")  # nosec B608 — Bezeichner aus Positivliste
    abbildung: dict[int, int] = {}
    neu_anlegen: list[int] = []
    reaktiviert: list[str] = []
    for alt, name in cur.fetchall():
        if alt is None:
            continue
        if name in schon_da:
            ziel_id, gelöscht = schon_da[name]
            abbildung[int(alt)] = ziel_id
            if gelöscht:
                # Der Mandant war als gelöscht markiert. Eine zweite Zeile mit
                # demselben Namen geht nicht (eindeutiger Index), und eine
                # Übernahme, die unsichtbar bleibt, wäre folgenlos — also wird
                # die vorhandene Zeile zurückgeholt und es im Bericht gesagt.
                cur.execute(
                    "UPDATE firmen.firmen SET is_deleted = 0, deleted_at = NULL "
                    "WHERE id = %s", (ziel_id,))
                reaktiviert.append(str(name))
        else:
            abbildung[int(alt)] = int(alt) + versatz
            neu_anlegen.append(int(alt))
    if reaktiviert:
        bericht["firmen_reaktiviert"] = sorted(reaktiviert)
        bericht["warnungen"].append(
            "Wieder eingesetzt (waren als gelöscht markiert): "
            + ", ".join(sorted(reaktiviert)))

    # Vorhandene Mandanten nicht erneut anlegen — ihre Daten hängen sich über
    # die Abbildung an die bestehende Zeile.
    cur.execute(
        f"DELETE FROM {hilfs} WHERE NOT (id = ANY(%s))", (neu_anlegen,))  # nosec B608 — Bezeichner aus Positivliste
    cur.execute(f"UPDATE {hilfs} SET id = id + %s", (versatz,))  # nosec B608
    zeilen = _einfuegen(conn, "firmen", "firmen", nehmen, hilfs, bericht)
    cur.execute(f"DROP TABLE {hilfs}")  # nosec B608 — Bezeichner aus Positivliste

    if zeilen:
        bericht["tabellen"] += 1
        bericht["zeilen"] += zeilen
        bericht["je_tabelle"]["firmen.firmen"] = zeilen
    bericht["firmen_neu"] = zeilen
    bericht["firmen_vorhanden"] = len(abbildung) - zeilen
    return abbildung


def _bestand_entfernen(conn, struktur: dict[str, Any], mandanten: list[str],
                       projekte: set[str], bericht: dict[str, Any]) -> None:
    """``ersetzen``: die Zeilen dieser Mandanten im Ziel entfernen.

    Begrenzt auf die gewählten Namen — alles andere bleibt. Das ist der
    Unterschied zum Restore, der die ganze Tabelle leert.
    """
    cur = conn.cursor()
    entfernt = 0
    projekt_namen = sorted(projekte)

    # Kinder zuerst: Die Fremdschlüssel sind für die Dauer des Laufs ausgesetzt,
    # also räumt keine Kaskade hinter uns auf. Zurückbleibende Kinder wären
    # Zeilen, die auf nichts mehr zeigen — und die nächste Übernahme würde sie
    # über den Versatz einem **anderen** Elternteil zuordnen.
    for (schema, tabelle), (eltern, fk) in sorted(KINDER.items()):
        if schema not in FACHSCHEMATA:
            continue
        ziel_eltern = _vorhandene(conn, schema, eltern)
        if not _vorhandene(conn, schema, tabelle) or not ziel_eltern:
            continue
        auswahl = _filter(schema, eltern, ziel_eltern)
        if auswahl is None or auswahl[0] != "spalte":
            continue
        spalte, art = auswahl[1]
        werte = projekt_namen if art == "projekt" else mandanten
        if not werte:
            continue
        try:
            # Savepoint, **nicht** `conn.rollback()`: Ein Rollback mitten im
            # Lauf würde die ganze Transaktion wegwerfen — samt der schon
            # eingefügten Mandanten — und die folgenden Anweisungen liefen in
            # einer neuen. Das Ergebnis wäre ein teilweise übernommener
            # Bestand, der aussieht wie ein Bestand. Genau das soll die
            # Transaktion verhindern.
            with conn.transaction():
                cur.execute(
                    f'DELETE FROM {f_db._q(schema, tabelle)} WHERE {f_db._q(fk)} IN '  # nosec B608 — Bezeichner über _q()
                    f'(SELECT id FROM {f_db._q(schema, eltern)} '
                    f'WHERE {f_db._q(spalte)} = ANY(%s))', (werte,))
                entfernt += cur.rowcount or 0
        except Exception as e:  # noqa: BLE001
            bericht["warnungen"].append(
                f"{schema}.{tabelle}: Bestand nicht entfernt ({f_db._kurz(e)})")

    for schema in sorted(struktur.get("schemata", {})):
        if schema not in FACHSCHEMATA:
            continue
        for tabelle in sorted(struktur["schemata"][schema].get("tabellen", {})):
            if (schema, tabelle) in UEBERGANGEN or (schema, tabelle) in STAMMDATEN:
                continue
            # Die Mandantenzeile selbst bleibt stehen: Alles hängt über ihre ID
            # daran, und sie zu löschen wäre eine Kaskade durch den ganzen
            # Bestand — genau das, was hier vermieden wird.
            if (schema, tabelle) == ("firmen", "firmen"):
                continue
            ziel = _vorhandene(conn, schema, tabelle)
            if not ziel:
                continue
            auswahl = _filter(schema, tabelle, ziel)
            if auswahl is None or auswahl[0] != "spalte":
                continue  # Kinder gehen über die Kaskade der Eltern
            spalte, art = auswahl[1]
            werte = projekt_namen if art == "projekt" else mandanten
            if not werte:
                continue
            try:
                with conn.transaction():      # Savepoint, siehe oben
                    cur.execute(
                        f'DELETE FROM {f_db._q(schema, tabelle)} '  # nosec B608 — Bezeichner über _q()
                        f'WHERE {f_db._q(spalte)} = ANY(%s)', (werte,))
                    entfernt += cur.rowcount or 0
            except Exception as e:  # noqa: BLE001
                bericht["warnungen"].append(
                    f"{schema}.{tabelle}: Bestand nicht entfernt ({f_db._kurz(e)})")
    bericht["ersetzt_entfernt"] = entfernt


# ── Eine Tabelle ────────────────────────────────────────────────────────────

def _tabelle_uebernehmen(conn, schema: str, tabelle: str,
                         spalten: list[str], csv_bytes: bytes, versatz: int,
                         firmen_abbildung: dict[int, int],
                         mandanten: list[str], projekte: set[str],
                         bericht: dict[str, Any]) -> int:
    """Zeilen einer Tabelle filtern, IDs verschieben, einfügen."""
    if not spalten:
        return 0
    nehmen = _gemeinsame_spalten(conn, schema, tabelle, spalten, bericht)
    if not nehmen:
        return 0

    auswahl = _filter(schema, tabelle, nehmen)
    if auswahl is None:
        bericht.setdefault("ausgelassen", {})[f"{schema}.{tabelle}"] = (
            "Keine Zuordnung zu einem Mandanten erkennbar — Katalog- oder "
            "Installationsdaten bleiben unberührt.")
        return 0

    hilfs = _temp_befuellen(conn, schema, tabelle, spalten, nehmen, csv_bytes)
    cur = conn.cursor()
    try:
        art, angabe = auswahl
        if art == "spalte":
            werte = sorted(projekte) if angabe[1] == "projekt" else mandanten
            cur.execute(
                f'DELETE FROM {hilfs} WHERE {f_db._q(angabe[0])} IS NULL '  # nosec B608 — Bezeichner über _q()
                f'OR NOT ({f_db._q(angabe[0])} = ANY(%s))', (werte,))
        elif art == "eltern":
            eltern, fk = angabe
            # Die Eltern stehen zu diesem Zeitpunkt bereits mit verschobener ID
            # im Ziel; das Kind trägt die unverschobene — bei einem **Zahlen**-
            # Schlüssel also + Versatz.
            #
            # Nicht jeder Schlüssel ist eine Zahl: Der Nachweis-Store adressiert
            # seine Dokumente über eine UUID (`evidence_documents.id` ist TEXT).
            # Die ist von sich aus eindeutig, wird nicht verschoben, und `+`
            # gibt es für Text nicht. Der Typ entscheidet, nicht der Name.
            if _ist_ganzzahl(conn, schema, tabelle, fk):
                cur.execute(
                    f'DELETE FROM {hilfs} WHERE {f_db._q(fk)} IS NULL OR '  # nosec B608 — Bezeichner über _q()
                    f'{f_db._q(fk)} + %s NOT IN '
                    f'(SELECT id FROM {f_db._q(schema, eltern)})',
                    (versatz,))
            else:
                cur.execute(
                    f'DELETE FROM {hilfs} WHERE {f_db._q(fk)} IS NULL OR '  # nosec B608 — Bezeichner über _q()
                    f'{f_db._q(fk)} NOT IN '
                    f'(SELECT id FROM {f_db._q(schema, eltern)})')
        # art == "alles": Stammdaten kommen vollständig mit.

        _ids_verschieben(conn, hilfs, schema, tabelle, nehmen, versatz,
                         firmen_abbildung, bericht)
        return _einfuegen(conn, schema, tabelle, nehmen, hilfs, bericht)
    finally:
        try:
            cur.execute(f"DROP TABLE IF EXISTS {hilfs}")  # nosec B608
        except Exception:  # noqa: BLE001
            pass


def _filter(schema: str, tabelle: str,
            nehmen: list[str]) -> tuple[str, Any] | None:
    """Wie die Zeilen dieser Tabelle ausgewählt werden — oder ``None``.

    ``None`` heißt: nicht zuordenbar. Dann bleibt die Tabelle unberührt. Das
    ist die fail-closed-Richtung: Lieber ein Katalog, der nicht mitkommt, als
    Zeilen, die irgendwohin eingefügt werden.
    """
    if (schema, tabelle) in STAMMDATEN:
        return ("alles", None)
    if (schema, tabelle) in KINDER:
        return ("eltern", KINDER[(schema, tabelle)])
    if schema == "users":
        return ("alles", None)
    for s in ZUORDNUNGSSPALTEN:
        if s in nehmen:
            return ("spalte", (s, "projekt"))
    # Projekttabellen **vor** den Mandantenspalten: `cra_projekte` trägt beides,
    # und `unternehmen` ist dort nur ein Anzeigefeld. Ein Projekt, das über den
    # Namen zur Firma gehört (Auto-Anlage #430) hat es womöglich leer — nach
    # `unternehmen` gefiltert fiele es weg.
    if any((schema, tabelle) == (s, t) for s, t, _m in PROJEKTTABELLEN):
        return ("spalte", ("name", "projekt"))
    for s in MANDANTENSPALTEN:
        if s in nehmen:
            return ("spalte", (s, "mandant"))
    return None


def _ids_verschieben(conn, hilfs: str, schema: str, tabelle: str,
                     nehmen: list[str], versatz: int,
                     firmen_abbildung: dict[int, int],
                     bericht: dict[str, Any]) -> None:
    """Technische Schlüssel um den Versatz, ``firmen_id`` über die Abbildung.

    Entschieden wird über den **Typ** der Spalte. Den einen Verweis, der als
    Text gespeichert ist, kennt diese Regel nicht — er steht am Ende eigens
    (``_issue_objekt_id_verschieben``).
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
          AND data_type IN ('integer', 'bigint')
          AND (column_name = 'id' OR column_name LIKE %s)
        """,
        (schema, tabelle, "%\\_id"))
    id_spalten = [r[0] for r in cur.fetchall() if r[0] in nehmen]

    for spalte in id_spalten:
        if spalte == "firmen_id":
            if not firmen_abbildung:
                continue
            paare = list(firmen_abbildung.items())
            cur.execute(
                f'UPDATE {hilfs} SET firmen_id = m.neu '  # nosec B608 — Bezeichner über _q()
                f'FROM (SELECT * FROM unnest(%s::bigint[], %s::bigint[]) AS t(alt, neu)) m '
                f'WHERE {hilfs}.firmen_id = m.alt',
                ([p[0] for p in paare], [p[1] for p in paare]))
            # Ein Verweis auf eine Firma, die nicht mitkommt, wird gelöst statt
            # geraten: Eine falsche Firmenzuordnung ist ein stiller Fehler.
            cur.execute(
                f'UPDATE {hilfs} SET firmen_id = NULL WHERE firmen_id IS NOT NULL '  # nosec B608 — Bezeichner über _q()
                f'AND firmen_id NOT IN (SELECT id FROM firmen.firmen)')
            continue
        cur.execute(
            f'UPDATE {hilfs} SET {f_db._q(spalte)} = {f_db._q(spalte)} + %s '  # nosec B608 — Bezeichner über _q()
            f'WHERE {f_db._q(spalte)} IS NOT NULL', (versatz,))

    _issue_objekt_id_verschieben(conn, hilfs, tabelle, nehmen, versatz)


def _issue_objekt_id_verschieben(conn, hilfs: str, tabelle: str,
                                 nehmen: list[str], versatz: int) -> None:
    """Der eine Fremdverweis, der in einer Textspalte steckt (#1879).

    ``linked_issues.object_id`` ist TEXT, trägt aber bei den Objektarten aus
    ``OBJEKT_ID_IST_NUMMER`` die **laufende Nummer** der Zeile, auf die der Link
    zeigt — ``cra_vuln.id``, ``rb_risiken.id`` und Verwandte. Die Regel aus dem
    Modulkopf („alle technischen Schlüssel wandern um denselben Versatz") greift
    dort nicht von selbst, weil sie über den **Typ** entscheidet und dieser Typ
    Text ist.

    Bleibt die Nummer stehen, zeigt die Verknüpfung nach einer Übernahme in eine
    bespielte Installation nicht ins Leere, sondern auf eine **fremde, hier
    bereits vorhandene** Schwachstelle: der stille Fehler aus #1773 — sie sieht
    aus wie eine Aussage. Ein Verweis auf eine Zeile, die nicht mitgekommen ist,
    ist dagegen sichtbar tot und damit das kleinere Übel; verschoben wird
    deshalb auch dann.

    Die Zahlenprüfung im ``WHERE`` ist kein Misstrauen gegen die Liste, sondern
    gegen die Daten: Ein ``object_id``, das wider Erwarten keine Zahl ist, würde
    den Cast zum Scheitern bringen und die ganze Übernahme mitnehmen.
    """
    if tabelle != ISSUE_TABELLE:
        return
    if not {"object_kind", "object_id"} <= set(nehmen):
        return
    conn.cursor().execute(
        f'UPDATE {hilfs} SET object_id = '  # nosec B608 — Bezeichner aus Positivliste
        f"(object_id::bigint + %s)::text "
        f"WHERE object_kind = ANY(%s) AND object_id ~ '^[0-9]+$'",
        (versatz, sorted(OBJEKT_ID_IST_NUMMER)))


# ── Werkzeug ────────────────────────────────────────────────────────────────

def _ist_ganzzahl(conn, schema: str, tabelle: str, spalte: str) -> bool:
    """Ist diese Spalte ein Zahlen-Schlüssel (und damit zu verschieben)?"""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT data_type FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
        """,
        (schema, tabelle, spalte))
    zeile = cur.fetchone()
    return bool(zeile) and zeile[0] in ("integer", "bigint", "smallint")


def _vorhandene(conn, schema: str, tabelle: str) -> list[str]:
    return f_db._vorhandene_spalten(conn.cursor(), schema, tabelle) or []


def _gemeinsame_spalten(conn, schema: str, tabelle: str, spalten: list[str],
                        bericht: dict[str, Any]) -> list[str]:
    """Schnitt aus Archiv- und Zielspalten — wie beim Restore (#1785)."""
    ziel = _vorhandene(conn, schema, tabelle)
    if not ziel:
        bericht.setdefault("ausgelassen", {})[f"{schema}.{tabelle}"] = (
            "Tabelle gibt es auf dieser Installation nicht.")
        return []
    nehmen = [s for s in spalten if s in ziel]
    fehlend = [s for s in spalten if s not in ziel]
    if fehlend:
        bericht["warnungen"].append(
            f"{schema}.{tabelle}: Spalte(n) {', '.join(fehlend)} gibt es nicht mehr "
            "— übergangen")
    return nehmen


_ZAEHLER = {"n": 0}


def _temp_befuellen(conn, schema: str, tabelle: str, spalten: list[str],
                    nehmen: list[str], csv_bytes: bytes) -> str:
    """Archivdaten in eine temporäre Kopie der Zieltabelle laden.

    ``WITH NO DATA`` gibt die Spaltentypen der Zieltabelle ohne Constraints,
    ohne Identity und ohne Vorgabewerte — genau richtig für eine Zwischenstufe,
    an der noch gefiltert und gerechnet wird. Das Lesen des CSV macht
    PostgreSQL selbst: Nur so bleibt die leere Zeichenkette von NULL
    unterschieden (siehe Modulkopf).
    """
    _ZAEHLER["n"] += 1
    name = f"_uebernahme_{_ZAEHLER['n']}"
    cur = conn.cursor()
    liste = ", ".join(f_db._q(s) for s in nehmen)
    cur.execute(
        f'CREATE TEMP TABLE {f_db._q(name)} AS '  # nosec B608 — Bezeichner über _q()
        f'SELECT {liste} FROM {f_db._q(schema, tabelle)} WITH NO DATA')
    roh = (csv_bytes if spalten == nehmen
           else b"".join(f_db._csv_auf_spalten(csv_bytes, spalten, nehmen)))
    sql = (f'COPY {f_db._q(name)} ({liste}) '  # nosec B608 — Bezeichner über _q()
           f'FROM STDIN WITH (FORMAT csv)')
    with cur.copy(sql) as copy:
        copy.write(roh)
    return f_db._q(name)


def _einfuegen(conn, schema: str, tabelle: str, nehmen: list[str],
               hilfs: str, bericht: dict[str, Any]) -> int:
    """Die gefilterten Zeilen einfügen — ohne vorhandene anzutasten.

    ``ON CONFLICT DO NOTHING`` ist hier kein Notausgang, sondern die Regel:
    Trifft eine Zeile auf einen bestehenden Schlüssel, gilt der Bestand. Die
    Alternative wäre, ihn zu überschreiben — und das ist genau der Fehler, den
    dieses Modul behebt.

    ``OVERRIDING SYSTEM VALUE`` braucht es für ``GENERATED ALWAYS AS IDENTITY``
    (Lehre aus #1785): Ohne das vergibt die Datenbank neue Schlüssel, und jeder
    Verweis zeigte auf einen anderen Datensatz.
    """
    liste = ", ".join(f_db._q(s) for s in nehmen)
    cur = conn.cursor()
    letzter: Exception | None = None
    for ueberschreiben in (" OVERRIDING SYSTEM VALUE", ""):
        try:
            with conn.transaction():
                cur.execute(
                    f'INSERT INTO {f_db._q(schema, tabelle)} ({liste})'  # nosec B608 — Bezeichner über _q()
                    f'{ueberschreiben} SELECT {liste} FROM {hilfs} '
                    f'ON CONFLICT DO NOTHING')
                return cur.rowcount or 0
        except Exception as e:  # noqa: BLE001
            letzter = e
            continue
    bericht["warnungen"].append(
        f"{schema}.{tabelle}: nicht übernommen ({f_db._kurz(letzter)})")
    return 0


def _sequenzen_nachziehen(conn, struktur: dict[str, Any],
                          bericht: dict[str, Any]) -> None:
    """Zähler über den höchsten eingefügten Schlüssel setzen.

    Ohne das vergibt die nächste Anlage einen Schlüssel, der schon belegt ist —
    die Übernahme sähe erfolgreich aus und die erste neue Zeile schlüge fehl.
    """
    cur = conn.cursor()
    schemata = [s for s in struktur.get("schemata", {})
                if s in FACHSCHEMATA or s == "users"]
    try:
        with conn.transaction():
            cur.execute(
                """
                SELECT c.table_schema, c.table_name, c.column_name,
                       pg_get_serial_sequence(
                           quote_ident(c.table_schema) || '.'
                           || quote_ident(c.table_name),
                           c.column_name)
                FROM information_schema.columns c
                WHERE c.table_schema = ANY(%s)
                  AND (c.is_identity = 'YES' OR c.column_default LIKE 'nextval%%')
                """,
                (schemata,))
            spalten = [r for r in cur.fetchall() if r[3]]
    except Exception as e:  # noqa: BLE001
        # Kein `conn.rollback()`: Diese Funktion läuft **nach** allen Einfügungen.
        # Ein Rollback hier würde die ganze Übernahme verwerfen und der
        # anschließende Commit nichts committen — gemeldet würde trotzdem
        # Erfolg. Der Savepoint um die Abfrage hält den Schaden bei der Abfrage.
        bericht["warnungen"].append(f"Zähler nicht ermittelt ({f_db._kurz(e)})")
        return

    for schema, tabelle, spalte, sequenz in spalten:
        try:
            with conn.transaction():
                cur.execute(
                    f'SELECT setval(%s, GREATEST(COALESCE(max({f_db._q(spalte)}), 0), 1)) '  # nosec B608 — Bezeichner über _q()
                    f'FROM {f_db._q(schema, tabelle)}', (sequenz,))
        except Exception as e:  # noqa: BLE001
            bericht["warnungen"].append(
                f"{schema}.{tabelle}.{spalte}: Zähler nicht nachgezogen "
                f"({f_db._kurz(e)})")
