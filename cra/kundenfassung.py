"""Kundenfassung des CRA-Berichts — zeigbar statt intern (#1758).

Alle übrigen Berichte des Moduls sind **interne** Dokumente: Sie enthalten
offene Punkte, Bewertungslücken, akzeptierte Restrisiken mit Begründung,
interne Verantwortliche und die Namen von Prüfern und Freigebern. Wer einem
Kunden „etwas zur CRA" geben wollte, hatte bisher die Wahl zwischen einem
internen Dokument und gar nichts — und griff im Zweifel zum internen.

Rechtlich muss der Kunde zweierlei bekommen: die Informationen nach Anhang II
(Art. 13 Abs. 18) und die EU-Konformitätserklärung (Art. 28). Die
**Risikoabschätzung gehört nicht dazu** — sie geht in die technische
Dokumentation und von dort an die Marktaufsicht (Art. 13 Abs. 1–3, Anhang VII
Nr. 3). Das ist kein Versehen des Gesetzgebers: Eine vollständige
Risikobewertung ist eine Landkarte der Schwachstellen.

WARUM ADDITIV UND NICHT SUBTRAKTIV
Dieses Modul sammelt **ausdrücklich erlaubte** Angaben ein, statt aus dem
internen Bericht etwas wegzulassen. Der Fehler ist hier asymmetrisch: Eine zu
knappe Kundenfassung kostet eine Rückfrage, eine zu offene kostet Vertrauen
oder liefert einem Angreifer Vorarbeit. Mit der Weglass-Variante landet beim
nächsten neuen internen Feld irgendwann etwas beim Kunden, das niemand dort
haben wollte — bei dieser Bauweise kann das nicht passieren, weil ein neues
Feld schlicht nicht abgeholt wird.

DIE SPRACHE GEHÖRT DEM MANDANTEN (#1954)
Dieses Dokument ist der Fall, für den die Firmensprache gebaut ist: Es geht
vom Hersteller an **seinen** Kunden. Über seine Sprache entscheidet deshalb
``firmen.sprache`` und nicht der Bearbeiter, der es zufällig erzeugt —
aufgelöst serverseitig in :func:`_sprache_fuer`, fail-open auf Deutsch.

Mit der Zweisprachigkeit wurde der Riegel aus #1758 scharfgestellt: Die
Begriffsliste war deutsch und wurde nur im Test gesucht, also hätte eine
englische Kundenfassung sie zwangsläufig grün passiert. Geprüft wird jetzt
**zur Laufzeit** am fertigen Dokument und gegen alle Sprachen — siehe
:data:`VERBOTENE` und :func:`pruefe`.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

DB_PATH = Path("data/db/cra.sqlite")

#: Begriffe, die in einer Kundenfassung nichts zu suchen haben — **je Sprache**
#: (#1954).
#:
#: Bis 8.3.4 war das eine Liste mit zehn deutschen Wörtern, und geprüft wurde
#: sie ausschließlich in ``tests/test_kundenfassung_1758.py``. Beides war falsch,
#: sobald das Dokument auch englisch entstehen kann:
#:
#: - Eine **englische** Kundenfassung passierte die deutsche Liste zwangsläufig
#:   grün. Der Riegel gegen Informationsabfluss wäre in genau dem Fall aus
#:   gewesen, für den man ihn braucht — und zwar lautlos, weil ein Prüfer, der
#:   nichts findet, wie ein Prüfer aussieht, der nichts zu finden hatte.
#: - Eine Prüfung, die nur im Test läuft, prüft den **Fixture-Datensatz**, nicht
#:   das Dokument, das ein Mandant herunterlädt.
#:
#: Geprüft wird deshalb zur Laufzeit und gegen die **Vereinigung aller**
#: Sprachen (:func:`alle_verbotenen`): Das fertige Dokument ist stellenweise
#: gemischt — Katalogbezeichnungen aus anderen Modulen können deutsch sein,
#: auch wenn die Prosa englisch ist. Ein Prüfer, der nur die eine Sprache
#: ansieht, hätte dort ein Loch.
VERBOTENE: dict[str, tuple[str, ...]] = {
    "de": (
        "akzeptiert", "Restrisiko", "offene Punkte", "Freigeber", "geprüft von",
        "Maßnahmenplan", "Zieldatum", "verantwortlich", "Ampel", "Reifegrad",
    ),
    # Keine Wort-für-Wort-Übersetzung, sondern **dieselben Rutschbahnen** in der
    # englischen Fachsprache: So heißen die internen Felder, wenn jemand den
    # Renderer später „nur kurz" erweitert. „accepted" deckt „accepted risk"
    # und „risk accepted" mit ab, „maturity" den Reifegrad in jeder Schreibung.
    "en": (
        "accepted", "residual risk", "open items", "open points", "approver",
        "sign-off", "reviewed by", "action plan", "target date", "responsible",
        "traffic light", "maturity",
    ),
}


class InternasImDokument(RuntimeError):
    """Die Kundenfassung trägt einen Begriff, der das Haus nicht verlassen darf.

    Erbt von ``RuntimeError`` (Muster ``vcs.errors.IssueBackendFehlt``, #1815),
    damit ein bestehendes ``except RuntimeError`` den Fall weiter fängt.

    **Das ist ein Programmierfehler, kein Datenzustand** — und deshalb ist der
    Abbruch hier richtig. Dieses Modul sammelt ausdrücklich erlaubte Angaben
    ein (siehe Dateikopf); ein verbotener Begriff kann nur entstehen, wenn der
    Renderer erweitert wurde und dabei ein internes Feld mitgenommen hat. Die
    Abwägung steht ebenfalls im Dateikopf und gilt unverändert: Eine fehlende
    Kundenfassung kostet eine Rückfrage, eine zu offene kostet Vertrauen oder
    liefert einem Angreifer Vorarbeit.
    """


def verbotene_begriffe(sprache: str | None = None) -> tuple[str, ...]:
    """Die verbotenen Begriffe einer Sprache."""
    from shared import sprache as _sp

    return VERBOTENE.get(_sp.oder_standard(sprache)) or VERBOTENE["de"]


def alle_verbotenen() -> tuple[str, ...]:
    """Alle verbotenen Begriffe über alle Sprachen — der Maßstab zur Laufzeit."""
    gesammelt: list[str] = []
    for begriffe in VERBOTENE.values():
        for b in begriffe:
            if b not in gesammelt:
                gesammelt.append(b)
    return tuple(gesammelt)


def treffer(text: str, *, eigene: Iterable[str] = ()) -> list[str]:
    """Welche verbotenen Begriffe stehen im Text?

    ``eigene`` sind die **Angaben aus den Registern des Mandanten**, die der
    Renderer in das Dokument eingesetzt hat: Produktname, Hersteller,
    Update-Kanal, PSIRT-Kontakt, Adressen. Sie werden vor der Prüfung
    ausgeblendet, und das ist der Teil, der diesen Riegel überhaupt
    scharfstellbar macht:

    Geprüft werden soll die **Prosa des Renderers** — was *wir* über das
    Produkt schreiben. Was der Mandant selbst in seine Stammdaten getippt hat,
    gehört ihm; steht in seinem Update-Kanal das Wort „verantwortlich", ist das
    kein Informationsabfluss, sondern seine eigene Angabe. Ohne diese
    Unterscheidung wäre die Liste mit Wörtern wie „akzeptiert" oder
    „verantwortlich" für einen **blockierenden** Prüfer zu weit, und wir hätten
    uns genau den Fehlalarm gebaut, der in #1885 schon einmal jede Erklärung
    unmöglich gemacht hat.

    Ersetzt wird durch ein **Leerzeichen** und nicht durch die leere
    Zeichenkette: Sonst könnte das Entfernen eines Stücks zwei Bruchstücke zu
    einem verbotenen Begriff zusammenschieben — ein Fehlalarm, den niemand im
    Dokument wiederfinden würde.
    """
    rest = text or ""
    for wert in eigene:
        w = (wert or "").strip()
        # Unter drei Zeichen bringt das Ausblenden nichts (so kurz ist kein
        # verbotener Begriff) und würde reihenweise Buchstaben wegnehmen.
        if len(w) >= 3:
            rest = rest.replace(w, " ")
    klein = rest.lower()
    return [b for b in alle_verbotenen() if b.lower() in klein]


def pruefe(text: str, *, eigene: Iterable[str] = ()) -> None:
    """Riegel vor der Ausgabe. Wirft :class:`InternasImDokument` bei einem Treffer."""
    gefunden = treffer(text, eigene=eigene)
    if gefunden:
        raise InternasImDokument(
            "Die Kundenfassung enthält interne Begriffe und wird nicht "
            "ausgegeben: " + ", ".join(repr(b) for b in gefunden)
            + ". Dieses Dokument verlässt das Haus — die betreffende Angabe "
              "gehört in den internen Konformitätsnachweis.")


def _mandantendaten(d: dict[str, Any]) -> list[str]:
    """Alle Zeichenketten aus :func:`sammle` — die Angaben des Mandanten.

    Zwei Schlüssel bleiben ausdrücklich draußen: ``art_label`` und
    ``klasse_label`` sind **unsere** Katalogbezeichnungen und sollen geprüft
    werden. Sie auszublenden hieße, dem Riegel genau die Texte zu entziehen,
    über die er wachen soll.
    """
    unsere = {"art_label", "klasse_label"}
    gesammelt: list[str] = []

    def lauf(wert: Any, schluessel: str = "") -> None:
        if isinstance(wert, dict):
            for k, v in wert.items():
                lauf(v, str(k))
        elif isinstance(wert, (list, tuple)):
            for v in wert:
                lauf(v, schluessel)
        elif isinstance(wert, str) and schluessel not in unsere:
            gesammelt.append(wert)

    lauf(d)
    return gesammelt


def _s(wert: Any) -> str:
    return "" if wert is None else str(wert).strip()


def sammle(projekt_name: str, *, db_path: Path = DB_PATH,
           version: str | None = None, sprache: str | None = None) -> dict[str, Any]:
    """Die erlaubten Angaben — und nur die.

    Jeder Block ist einzeln gekapselt: Fällt eine Quelle aus, fehlt dieser
    Block, statt dass der ganze Bericht scheitert. Für eine Kundenfassung ist
    das richtig herum — ein fehlender Abschnitt ist eine Rückfrage, ein
    abgebrochener Export ist ein geplatzter Termin.
    """
    d: dict[str, Any] = {"erstellt_am": date.today().isoformat(),
                         "projekt_name": projekt_name}

    try:
        from cra.db import load_projekt
        from cra.requirements import klasse_label

        p = load_projekt(db_path, projekt_name) or {}
        d["produkt"] = {
            "name": _s(p.get("produkt")) or _s(p.get("name")),
            "hersteller": _s(p.get("unternehmen")),
            "beschreibung": _s(p.get("beschreibung")),
            # #1954: über die Funktion statt über `PRODUKTKLASSEN[...]['label']`
            # — nur sie kennt die Sprache und die Normalisierung aus #1919.
            "klasse_label": klasse_label(_s(p.get("produktklasse")),
                                         sprache=sprache),
        }
    except Exception:  # noqa: BLE001
        d["produkt"] = {}

    # ── Konformität: Verfahren, Erklärung, CE ───────────────────────────────
    try:
        from cra import doc_export

        dd = doc_export.doc_daten(db_path, projekt_name, version)
        rec = dd.get("record") or {}
        d["konformitaet"] = {
            "bewertungsweg": _s(rec.get("bewertungsweg")),
            "nb_name": _s((dd.get("doc") or {}).get("nb_name")),
            "nb_kennnummer": _s(rec.get("nb_kennnummer")),
            "doc_ausgestellt": bool(dd.get("doc_ausgestellt")) and not dd.get("fehlend"),
            "doc_ausgestellt_am": _s(dd.get("ausgestellt_am")),
            "doc_version": dd.get("doc_version"),
            "release_version": _s(dd.get("release_version")) or _s(version),
        }
        d["_record"] = rec          # nur für die CE-Sperre, nicht gedruckt
    except Exception:  # noqa: BLE001
        d["konformitaet"] = {}
        d["_record"] = {}

    # Hash der abgelegten Erklärung — der Kunde soll prüfen können, dass er
    # dieselbe Fassung hat.
    try:
        from cra import doc_export

        archiv = doc_export.list_archiv(db_path, projekt_name) or []
        d["erklaerung_archiv"] = [
            {"version": _s(a.get("doc_version") or a.get("version")),
             "am": _s(a.get("erstellt_am") or a.get("freigegeben_am"))[:10],
             "sha256": _s(a.get("sha256"))}
            for a in archiv[:5]]
    except Exception:  # noqa: BLE001
        d["erklaerung_archiv"] = []

    # ── Anhang II: was der Kunde wirklich braucht ───────────────────────────
    try:
        from cra.db import load_support_period

        sp = load_support_period(db_path, projekt_name) or {}
        d["support"] = {
            "markteintritt": _s(sp.get("markteintritt_datum"))[:10],
            "jahre": sp.get("support_jahre"),
            "eol": _s(sp.get("eol_datum"))[:10],
            "update_kanal": _s(sp.get("update_kanal")),
            # #1762: Die beiden Zusagen und die Kauf-Sichtbarkeit sind genau die
            # Art von Angabe, die hierher gehört — der Kunde soll sie schriftlich
            # haben und nicht erfragen müssen.
            "kostenlos": bool(sp.get("sicherheitsupdates_kostenlos")),
            "getrennt": bool(sp.get("kanaele_getrennt")),
            "sicherheitsupdate_kanal": _s(sp.get("sicherheitsupdate_kanal")),
            "funktionsupdate_kanal": _s(sp.get("funktionsupdate_kanal")),
            "zusagen_nachweis": _s(sp.get("update_zusagen_nachweis")),
            "kaufhinweis_url": _s(sp.get("support_end_kaufhinweis_url")),
        }
    except Exception:  # noqa: BLE001
        d["support"] = {}

    try:
        from cra.db import load_psirt

        from cra.psirt import als_text

        ps = load_psirt(db_path, projekt_name) or {}
        d["meldestelle"] = {
            "policy_url": _s(ps.get("disclosure_policy_url")),
            "security_md": _s(ps.get("security_md_url")),
            # #1796: `_s` einer Liste druckte `['security@…']` wörtlich in das
            # Dokument, das das Haus verlässt. Die Spalte trägt beides, also
            # entscheidet eine Stelle, wie Kontakte aussehen.
            "kontakt": als_text(ps),
        }
    except Exception:  # noqa: BLE001
        d["meldestelle"] = {}

    # ── Veröffentlichte Advisories ──────────────────────────────────────────
    # Nur **behobene** Schwachstellen mit veröffentlichter Advisory-Adresse.
    # Offene Befunde erscheinen hier unter keinen Umständen: Sie sind die
    # Angriffsfläche von heute, nicht die Historie von gestern.
    try:
        from cra.db import list_vuln

        d["advisories"] = [
            {"id": _s(v.get("cve_id")), "behoben_in": _s(v.get("fixed_in_version")),
             "url": _s(v.get("advisory_url"))}
            for v in (list_vuln(db_path, projekt_name) or [])
            if _s(v.get("advisory_url")) and _s(v.get("status")) in ("fixed", "resolved")
        ][:50]
    except Exception:  # noqa: BLE001
        d["advisories"] = []

    # ── SBOM: Stand, nicht Inhalt ───────────────────────────────────────────
    try:
        from cra.db import list_sbom

        sbom = list_sbom(db_path, projekt_name) or []
        neueste = sbom[0] if sbom else {}
        d["sbom"] = {"vorhanden": bool(sbom),
                     "format": _s(neueste.get("sbom_format")),
                     "stand": _s(neueste.get("sbom_datum"))[:10],
                     "version": _s(neueste.get("release_version"))}
    except Exception:  # noqa: BLE001
        d["sbom"] = {"vorhanden": False}

    # ── Sicherheitstests: Art und Stand, keine Befunde (#1824) ──────────────
    # Anhang I Teil II Nr. 3 ist eine Pflicht gegenüber dem Markt, und was der
    # Hersteller dazu tut — oder bewusst nicht tut —, ist eine Aussage über das
    # Produkt und keine interne Notiz. Ein Dokument, das den Verzicht
    # verschweigt, ist gegenüber dem Empfänger irreführend.
    #
    # Gedruckt wird **Art und Zeitpunkt**, nie ein Befund: Welche Lücke ein
    # Test gefunden hat, ist die Angriffsfläche von heute und bleibt — wie die
    # offenen Schwachstellen oben — außen vor.
    try:
        from cra import sicherheitstests as st

        b = st.befund(db_path, projekt_name, _s(version))
        v = b.get("verzicht") or {}
        d["tests"] = {
            "art": _s(b.get("art")),
            # #1954: `befund` liefert die deutsche Bezeichnung mit; für ein
            # Dokument, das das Haus verlässt, wird sie hier in der Sprache des
            # Mandanten neu aufgelöst.
            "art_label": st.art_label(_s(b.get("art")), sprache=sprache),
            "juengster": _s(b.get("juengster")),
            "anzahl": int(b.get("nachweis_count") or 0),
            "verzicht": bool(v.get("erklaert")),
            "verzicht_begruendung": _s(v.get("begruendung")),
            "verzicht_review": _s(v.get("review")),
        }
    except Exception:  # noqa: BLE001
        d["tests"] = {}

    # ── Risikomanagement: Methode und Stand, keine Risiken ──────────────────
    try:
        from cra.db import load_projekt
        from risikobewertung.db import load_projekt as rb_projekt

        meta = (load_projekt(db_path, projekt_name) or {}).get("meta") or {}
        rb_name = _s(meta.get("linked_risk_projekt"))
        rb = rb_projekt(Path("data/db/risikobewertung.sqlite"), rb_name) if rb_name else {}
        d["risikomanagement"] = {
            "gefuehrt": bool(rb_name),
            "methode": _s((rb or {}).get("framework")),
            "stand": _s((rb or {}).get("updated_at"))[:10],
        }
    except Exception:  # noqa: BLE001
        d["risikomanagement"] = {"gefuehrt": False}

    return d


#: Die Prosa des Dokuments je Sprache (#1954).
#:
#: Die Kundenfassung ist der Fall, für den die Firmensprache gebaut ist: Sie
#: geht vom Hersteller an **seinen** Kunden, also entscheidet der Mandant über
#: ihre Sprache und nicht der Bearbeiter, der sie zufällig erzeugt. Aufgelöst
#: wird sie serverseitig aus ``firmen.sprache``.
#:
#: **Nummern und Fundstellen werden nicht übersetzt**, nur die Bezeichnung der
#: Anlage: „Anhang V" heißt im englischen Amtsblatt „Annex V" und bezeichnet
#: dieselbe Anlage derselben Verordnung. Die Ziffern bleiben unangetastet — die
#: Lehre aus #1763/#1792, wo sechs geratene Fundstellen in Dokumente gedruckt
#: wurden, die ein Prüfer liest.
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        "titel": "Cybersicherheit — Information für Kunden",
        "kopfzeile": "{produkt} · {hersteller} · Stand {stand}",
        "einleitung": (
            "Dieses Dokument fasst zusammen, was für Sie als Anwender dieses "
            "Produkts mit digitalen Elementen von Bedeutung ist. Die "
            "vollständige technische Dokumentation einschließlich der "
            "Risikoabschätzung wird der Marktaufsichtsbehörde auf Verlangen "
            "vorgelegt (Verordnung (EU) 2024/2847, Art. 13 Abs. 1–3 i.V.m. "
            "Anhang VII)."),

        "h_konformitaet": "Konformität",
        "doc_vorhanden": (
            "Für dieses Produkt liegt eine EU-Konformitätserklärung nach "
            "Art. 28 i.V.m. Anhang V vor (Fassung {fassung}, ausgestellt am "
            "{am})."),
        "doc_fehlt": "Die EU-Konformitätserklärung ist noch nicht ausgestellt.",
        "verfahren": ("Angewandtes Konformitätsbewertungsverfahren: Modul {weg} "
                      "(Anhang VIII)."),
        "notifizierte_stelle": (" Beteiligte notifizierte Stelle: {name} "
                                "(Kennnummer {nummer})."),
        "archiv": "Hinterlegte Fassung {fassung} vom {am} — SHA-256 {hash}…",

        "h_ce": "CE-Kennzeichnung",

        "h_support": "Unterstützungszeitraum und Updates",
        "eol": "Sicherheitsupdates werden bis zum {eol} bereitgestellt",
        "eol_markteintritt": " (Markteintritt {am}, {jahre} Jahre).",
        "eol_offen": "Der Unterstützungszeitraum ist noch nicht festgelegt.",
        "kostenlos_ja": ("Sicherheitsupdates werden während des "
                         "Unterstützungszeitraums kostenlos bereitgestellt."),
        "kostenlos_offen": ("Zur Entgeltfreiheit der Sicherheitsupdates liegt "
                            "keine dokumentierte Zusage vor."),
        "getrennt_ja": (
            "Sicherheitsupdates werden getrennt von Funktionsupdates "
            "bereitgestellt: Sie können Sicherheitsupdates beziehen, ohne "
            "Funktionsänderungen übernehmen zu müssen."),
        "kanal_sicherheit_satz": " Kanal für Sicherheitsupdates: {kanal}.",
        "kanal_sicherheit": "Kanal für Sicherheitsupdates: {kanal}",
        "kanal_funktion": "Kanal für Funktionsupdates: {kanal}",
        "kanal_update": "Bezug der Updates: {kanal}",
        "zusagen_nachweis": "Diese Zusagen sind veröffentlicht unter: {url}",
        "kaufhinweis": ("Das Ende des Unterstützungszeitraums ist vor dem Kauf "
                        "einsehbar unter: {url}"),

        "h_meldestelle": "Schwachstellen melden",
        "kontakt": "Kontakt: {kontakt}",
        "meldestelle_offen": "Eine Meldestelle ist noch nicht veröffentlicht.",

        "h_risiko": "Risikomanagement",
        "risiko_gefuehrt": ("Für dieses Produkt wird eine "
                            "Cybersicherheits-Risikoabschätzung geführt"),
        "risiko_methode": " (Methode: {methode})",
        "risiko_stand": ", zuletzt fortgeschrieben am {stand}",
        "risiko_extern": ("Die Risikoabschätzung wird außerhalb dieses Systems "
                          "geführt."),
        "risiko_nicht_veroeffentlicht": (
            "Die Abschätzung selbst ist Teil der technischen Dokumentation und "
            "wird nicht veröffentlicht: Sie beschreibt Angriffswege und "
            "Schutzmaßnahmen im Einzelnen."),

        "h_tests": "Sicherheitstests",
        "tests_verzicht": ("Der Hersteller führt für dieses Produkt derzeit "
                           "keine gesonderten Sicherheitstests durch. Diese "
                           "Entscheidung ist dokumentiert"),
        "tests_verzicht_review": " und zum {review} erneut zu treffen",
        "tests_vorhanden": "Die Sicherheit dieses Produkts wird getestet: {art}",
        "tests_juengster": "; jüngster Nachweis vom {am}",
        "tests_nicht_veroeffentlicht": (
            ". Die Testberichte sind Teil der technischen Dokumentation "
            "(Anhang VII Nr. 6) und werden nicht veröffentlicht."),
        "tests_offen": ("Zu Sicherheitstests liegt in dieser Akte derzeit kein "
                        "Nachweis vor."),

        "h_advisories": "Veröffentlichte Sicherheitshinweise",
        "advisories_vorhanden": ("Zu folgenden behobenen Schwachstellen wurden "
                                 "Hinweise veröffentlicht (Anhang I Teil II "
                                 "Nr. 4):"),
        "advisory_zeile": "{id} — behoben in {fassung} — {url}",
        "advisories_keine": ("Es wurden bislang keine Sicherheitshinweise "
                             "veröffentlicht."),

        "h_sbom": "Software-Stückliste (SBOM)",
        "sbom_vorhanden": ("Eine SBOM im Format {format} liegt vor (Stand "
                           "{stand}{fassung}). Sie wird auf Anfrage "
                           "bereitgestellt."),
        "sbom_fassung": ", Version {version}",
        "sbom_keine": "Eine Software-Stückliste liegt derzeit nicht vor.",
        "leer": "—",
    },
    "en": {
        "titel": "Cybersecurity — Information for Customers",
        "kopfzeile": "{produkt} · {hersteller} · As of {stand}",
        "einleitung": (
            "This document summarises what matters to you as a user of this "
            "product with digital elements. The complete technical "
            "documentation, including the risk assessment, is made available "
            "to the market surveillance authority upon request (Regulation "
            "(EU) 2024/2847, Art. 13(1) to (3) in conjunction with Annex "
            "VII)."),

        "h_konformitaet": "Conformity",
        "doc_vorhanden": (
            "An EU declaration of conformity pursuant to Art. 28 in "
            "conjunction with Annex V has been issued for this product "
            "(version {fassung}, issued on {am})."),
        "doc_fehlt": "The EU declaration of conformity has not been issued yet.",
        "verfahren": ("Conformity assessment procedure applied: Module {weg} "
                      "(Annex VIII)."),
        "notifizierte_stelle": (" Notified body involved: {name} "
                                "(identification number {nummer})."),
        "archiv": "Archived version {fassung} of {am} — SHA-256 {hash}…",

        "h_ce": "CE marking",

        "h_support": "Support period and updates",
        "eol": "Security updates will be provided until {eol}",
        "eol_markteintritt": " (placed on the market {am}, {jahre} years).",
        "eol_offen": "The support period has not been determined yet.",
        "kostenlos_ja": ("Security updates are provided free of charge "
                         "throughout the support period."),
        "kostenlos_offen": ("There is no documented commitment that security "
                            "updates are provided free of charge."),
        "getrennt_ja": (
            "Security updates are provided separately from functionality "
            "updates: you can obtain security updates without having to adopt "
            "changes in functionality."),
        "kanal_sicherheit_satz": " Channel for security updates: {kanal}.",
        "kanal_sicherheit": "Channel for security updates: {kanal}",
        "kanal_funktion": "Channel for functionality updates: {kanal}",
        "kanal_update": "How to obtain updates: {kanal}",
        "zusagen_nachweis": "These commitments are published at: {url}",
        "kaufhinweis": ("The end of the support period can be consulted before "
                        "purchase at: {url}"),

        "h_meldestelle": "Reporting vulnerabilities",
        "kontakt": "Contact: {kontakt}",
        "meldestelle_offen": "No reporting point has been published yet.",

        "h_risiko": "Risk management",
        "risiko_gefuehrt": ("A cybersecurity risk assessment is maintained for "
                            "this product"),
        "risiko_methode": " (method: {methode})",
        "risiko_stand": ", last updated on {stand}",
        "risiko_extern": ("The risk assessment is maintained outside this "
                          "system."),
        "risiko_nicht_veroeffentlicht": (
            "The assessment itself forms part of the technical documentation "
            "and is not published: it describes attack paths and protective "
            "measures in detail."),

        "h_tests": "Security testing",
        "tests_verzicht": ("The manufacturer currently does not carry out "
                           "dedicated security tests for this product. This "
                           "decision is documented"),
        "tests_verzicht_review": " and is to be taken again by {review}",
        "tests_vorhanden": "The security of this product is tested: {art}",
        "tests_juengster": "; most recent evidence dated {am}",
        "tests_nicht_veroeffentlicht": (
            ". The test reports form part of the technical documentation "
            "(Annex VII No. 6) and are not published."),
        "tests_offen": ("This file currently contains no evidence of security "
                        "testing."),

        "h_advisories": "Published security advisories",
        "advisories_vorhanden": ("Advisories have been published for the "
                                 "following remediated vulnerabilities "
                                 "(Annex I Part II No. 4):"),
        "advisory_zeile": "{id} — fixed in {fassung} — {url}",
        "advisories_keine": "No security advisories have been published to date.",

        "h_sbom": "Software bill of materials (SBOM)",
        "sbom_vorhanden": ("An SBOM in {format} format is available (as of "
                           "{stand}{fassung}). It is provided on request."),
        "sbom_fassung": ", version {version}",
        "sbom_keine": "A software bill of materials is not currently available.",
        "leer": "—",
    },
}


def _t(sprache: str, schluessel: str, **werte: Any) -> str:
    katalog = TEXTE.get(sprache) or TEXTE["de"]
    muster = katalog.get(schluessel)
    if muster is None:          # fehlt die Übersetzung, gilt der deutsche Text
        muster = TEXTE["de"].get(schluessel, "")
    return muster.format(**werte) if werte else muster


def _sprache_fuer(projekt_name: str, sprache: str | None) -> str:
    """Die Sprache des Dokuments: ausdrücklich gesetzt oder die des Mandanten.

    Fail-open auf die Standardsprache (Muster ``shared.firmen_link``): Ein
    Mandant, der sich nicht auflösen lässt, bekommt das bisherige Verhalten und
    keinen Fehler — eine nicht erzeugte Kundenfassung wäre der teurere Ausgang.
    """
    from shared import sprache as _sp

    if sprache:
        return _sp.oder_standard(sprache)
    return _sp.inhalt_fuer_projekt("cra", projekt_name)


def build_docx(projekt_name: str, *, db_path: Path = DB_PATH,
               version: str | None = None, sprache: str | None = None) -> bytes:
    """Kundenfassung als DOCX — in der Sprache des Mandanten (#1954)."""
    import io

    from docx import Document
    from docx.shared import Pt

    from cra import ce_mark
    from shared.reports.docx_pdf import apply_base_font, set_a4

    spr = _sprache_fuer(projekt_name, sprache)
    d = sammle(projekt_name, db_path=db_path, version=version, sprache=spr)
    doc = Document()
    set_a4(doc, sprache=spr)

    prod = d.get("produkt") or {}
    titel = doc.add_heading(_t(spr, "titel"), level=0)
    titel.runs[0].font.size = Pt(18)
    doc.add_paragraph(_t(spr, "kopfzeile",
                         produkt=prod.get("name") or projekt_name,
                         hersteller=prod.get("hersteller") or "",
                         stand=d["erstellt_am"]))
    doc.add_paragraph(_t(spr, "einleitung"))

    k = d.get("konformitaet") or {}
    doc.add_heading(_t(spr, "h_konformitaet"), level=1)
    if k.get("doc_ausgestellt"):
        doc.add_paragraph(_t(spr, "doc_vorhanden",
                             fassung=k.get("doc_version"),
                             am=k.get("doc_ausgestellt_am")))
    else:
        doc.add_paragraph(_t(spr, "doc_fehlt"))
    # `produkt.klasse_label` wird bewusst **nicht** gedruckt — so war es vor
    # #1954, und eine Übersetzung ist kein Anlass, den Inhalt eines Dokuments zu
    # erweitern, das ein Mandant unter seinem Namen herausgibt. Die Bezeichnung
    # ist trotzdem sprachbewusst aufgelöst: Wer sie aufnimmt, bekommt sie
    # richtig und muss nicht daran denken.
    if k.get("bewertungsweg"):
        satz = _t(spr, "verfahren", weg=k["bewertungsweg"])
        if k.get("nb_kennnummer"):
            satz += _t(spr, "notifizierte_stelle",
                       name=k.get("nb_name") or "", nummer=k["nb_kennnummer"])
        doc.add_paragraph(satz)
    for a in d.get("erklaerung_archiv") or []:
        if a.get("sha256"):
            doc.add_paragraph(_t(spr, "archiv", fassung=a["version"], am=a["am"],
                                 hash=a["sha256"][:16]))

    doc.add_heading(_t(spr, "h_ce"), level=1)
    ce_mark.einfuegen(doc, d.get("_record") or {},
                      bool(k.get("doc_ausgestellt")), sprache=spr)

    s = d.get("support") or {}
    doc.add_heading(_t(spr, "h_support"), level=1)
    if s.get("eol"):
        doc.add_paragraph(
            _t(spr, "eol", eol=s["eol"])
            + (_t(spr, "eol_markteintritt", am=s["markteintritt"], jahre=s["jahre"])
               if s.get("markteintritt") else "."))
    else:
        doc.add_paragraph(_t(spr, "eol_offen"))
    # #1762 — zwei Zusagen, die der Kunde schwarz auf weiß haben soll. Fehlt
    # eine, wird das gesagt und nicht verschwiegen: Eine Kundenfassung, die eine
    # nicht dokumentierte Zusage behauptet, ist schlimmer als eine, die ihre
    # Lücke zeigt. Die Angabe der Verordnungsstelle fehlt hier absichtlich — das
    # Issue markiert sie als unsicher (Art. 13 Abs. 12-14, nicht nachgeprüft),
    # und ein falsches Zitat in einem Kundendokument ist schlechter als keines.
    doc.add_paragraph(_t(spr, "kostenlos_ja" if s.get("kostenlos")
                         else "kostenlos_offen"))
    if s.get("getrennt"):
        doc.add_paragraph(
            _t(spr, "getrennt_ja")
            + (_t(spr, "kanal_sicherheit_satz", kanal=s["sicherheitsupdate_kanal"])
               if s.get("sicherheitsupdate_kanal") else ""))
    elif s.get("sicherheitsupdate_kanal"):
        doc.add_paragraph(_t(spr, "kanal_sicherheit",
                             kanal=s["sicherheitsupdate_kanal"]))
    if s.get("funktionsupdate_kanal"):
        doc.add_paragraph(_t(spr, "kanal_funktion",
                             kanal=s["funktionsupdate_kanal"]))
    if s.get("update_kanal"):
        doc.add_paragraph(_t(spr, "kanal_update", kanal=s["update_kanal"]))
    if s.get("zusagen_nachweis"):
        doc.add_paragraph(_t(spr, "zusagen_nachweis", url=s["zusagen_nachweis"]))
    if s.get("kaufhinweis_url"):
        doc.add_paragraph(_t(spr, "kaufhinweis", url=s["kaufhinweis_url"]))

    m = d.get("meldestelle") or {}
    doc.add_heading(_t(spr, "h_meldestelle"), level=1)
    if m.get("policy_url") or m.get("security_md") or m.get("kontakt"):
        if m.get("kontakt"):
            doc.add_paragraph(_t(spr, "kontakt", kontakt=m["kontakt"]))
        for url in (m.get("policy_url"), m.get("security_md")):
            if url:
                doc.add_paragraph(url)
    else:
        doc.add_paragraph(_t(spr, "meldestelle_offen"))

    r = d.get("risikomanagement") or {}
    doc.add_heading(_t(spr, "h_risiko"), level=1)
    if r.get("gefuehrt"):
        satz = _t(spr, "risiko_gefuehrt")
        if r.get("methode"):
            satz += _t(spr, "risiko_methode", methode=r["methode"])
        if r.get("stand"):
            satz += _t(spr, "risiko_stand", stand=r["stand"])
        doc.add_paragraph(satz + ".")
    else:
        doc.add_paragraph(_t(spr, "risiko_extern"))
    doc.add_paragraph(_t(spr, "risiko_nicht_veroeffentlicht"))

    # #1824 — Anhang I Teil II Nr. 3. Zwei Dinge stehen hier bewusst **nicht**:
    # kein Befund (die Lücke von heute gehört nicht in ein Dokument, das das
    # Haus verlässt — dieselbe Regel wie bei den Advisories oben) und nicht die
    # interne Begründung des Verzichts. Dass verzichtet wird, ist eine Aussage
    # über das Produkt; *warum*, ist die Abwägung des Hauses und steht im
    # Konformitätsnachweis (`cra/konformitaet_report.py`), der auf Verlangen
    # vorgelegt wird. Verschwiegen wird der Verzicht aber nicht: Ein Dokument,
    # das Tests offenlässt, obwohl der Hersteller sich dagegen entschieden hat,
    # führt den Empfänger in die Irre.
    t = d.get("tests") or {}
    doc.add_heading(_t(spr, "h_tests"), level=1)
    if t.get("verzicht"):
        satz = _t(spr, "tests_verzicht")
        if t.get("verzicht_review"):
            satz += _t(spr, "tests_verzicht_review", review=t["verzicht_review"])
        doc.add_paragraph(satz + ".")
    elif t.get("anzahl"):
        satz = _t(spr, "tests_vorhanden", art=t["art_label"])
        if t.get("juengster"):
            satz += _t(spr, "tests_juengster", am=t["juengster"])
        doc.add_paragraph(satz + _t(spr, "tests_nicht_veroeffentlicht"))
    else:
        doc.add_paragraph(_t(spr, "tests_offen"))

    doc.add_heading(_t(spr, "h_advisories"), level=1)
    adv = d.get("advisories") or []
    if adv:
        doc.add_paragraph(_t(spr, "advisories_vorhanden"))
        for a in adv:
            doc.add_paragraph(
                _t(spr, "advisory_zeile", id=a["id"],
                   fassung=a["behoben_in"] or _t(spr, "leer"), url=a["url"]),
                style="List Bullet")
    else:
        doc.add_paragraph(_t(spr, "advisories_keine"))

    sb = d.get("sbom") or {}
    doc.add_heading(_t(spr, "h_sbom"), level=1)
    doc.add_paragraph(
        _t(spr, "sbom_vorhanden",
           format=sb.get("format") or _t(spr, "leer"),
           stand=sb.get("stand") or _t(spr, "leer"),
           fassung=(_t(spr, "sbom_fassung", version=sb["version"])
                    if sb.get("version") else ""))
        if sb.get("vorhanden") else _t(spr, "sbom_keine"))

    apply_base_font(doc)

    # ── Riegel vor der Ausgabe (#1954) ──────────────────────────────────────
    # Geprüft wird das **fertige Dokument**, nicht der Datensatz davor: Die
    # Prosa oben entsteht erst hier, und genau sie ist der Weg, auf dem ein
    # internes Feld in ein Dokument gerät, das das Haus verlässt. Dasselbe
    # Prinzip wie in #1824 und #1827 — der Riegel beurteilt das Ergebnis und
    # nicht das Bruchstück, das der Aufrufer mitgebracht hat.
    pruefe("\n".join(p.text for p in doc.paragraphs),
           eigene=_mandantendaten(d))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_pdf(projekt_name: str, *, db_path: Path = DB_PATH,
              version: str | None = None, sprache: str | None = None) -> bytes:
    from shared.reports.docx_pdf import docx_bytes_to_pdf

    return docx_bytes_to_pdf(build_docx(projekt_name, db_path=db_path,
                                        version=version, sprache=sprache))


def build(projekt_name: str, *, fmt: str = "docx", db_path: Path = DB_PATH,
          version: str | None = None, sprache: str | None = None) -> bytes:
    if (fmt or "docx").lower() == "pdf":
        return build_pdf(projekt_name, db_path=db_path, version=version,
                         sprache=sprache)
    return build_docx(projekt_name, db_path=db_path, version=version,
                      sprache=sprache)


def summary_context(projekt_name: str, *, db_path: Path = DB_PATH,
                    sprache: str | None = None) -> dict[str, Any]:
    """Kontext für die KI-Zusammenfassung (#1725) — ebenfalls ohne Internas.

    Die Sprache wird mitgeführt, damit nicht in einer englischen
    Zusammenfassung eine deutsche Katalogbezeichnung steht. Die **Antwort**
    selbst stellt der Vorrang-Block um (#1832/#1954) — das ist eine andere
    Stelle und bleibt es.
    """
    d = sammle(projekt_name, db_path=db_path,
               sprache=_sprache_fuer(projekt_name, sprache))
    k = d.get("konformitaet") or {}
    return {
        "reifegrad": None,
        "offene": [],
        "kundenfassung": {
            "produkt": (d.get("produkt") or {}).get("name"),
            "erklaerung_ausgestellt": bool(k.get("doc_ausgestellt")),
            "support_bis": (d.get("support") or {}).get("eol"),
            "updates_kostenlos": bool((d.get("support") or {}).get("kostenlos")),
            "updates_getrennt": bool((d.get("support") or {}).get("getrennt")),
            "advisories": len(d.get("advisories") or []),
            "sbom": bool((d.get("sbom") or {}).get("vorhanden")),
            # #1824: Der Verzicht gehört auch in eine Zusammenfassung — sonst
            # formuliert die KI um ihn herum.
            "sicherheitstests": (d.get("tests") or {}).get("art_label"),
            "ohne_sicherheitstests": bool((d.get("tests") or {}).get("verzicht")),
        },
    }
