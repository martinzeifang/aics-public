"""Anhang-V-Angaben aus den Quellen vorschlagen — ohne KI (#1884).

WARUM OHNE KI
-------------
#1874 hat dem **Assistenten** die erfassten Daten gegeben; das war richtig für
die Angaben, die ein Mensch formuliert. Nr. 1 (Charge/Version), Nr. 4
(Gegenstand) und die Kandidaten für Nr. 6 sind etwas anderes: keine
Formulierungsleistung, sondern eine **Zusammenstellung**. Die Bestandteile
stehen strukturiert in der Akte — Projekt-Stammdaten, Release-Historie,
SBOM-Verzeichnis. Ein Sprachmodell dazwischenzuschalten ersetzt eine
nachweisbare Angabe durch eine wahrscheinliche; in einem Dokument, das der
Hersteller unter seiner Alleinverantwortung unterschreibt (Art. 28 i.V.m.
Anhang V), ist das der falsche Tausch. Dazu wäre das Ergebnis ein KI-Entwurf,
der nach :mod:`shared.ki_herkunft` erst geprüft werden müsste, bevor er
gedruckt werden darf (#1765).

DREI REGELN, DIE JEDE FUNKTION HIER EINHÄLT
-------------------------------------------
1. **Was nicht in der Akte steht, erscheint nicht.** Kein Platzhalter, keine
   Vermutung — eine leere Zeile im Ergebnis lädt zum Ausfüllen ein, und
   ausgefüllt würde sie erfunden (Linie aus
   ``komponenten_klassen.nachweise_aus_projekt``). Jede Auslassung wird in
   ``fehlend`` **benannt**, statt stillschweigend zu passieren.
2. **Jede Aussage trägt ihre Fundstelle.** ``fundstellen`` nennt, woraus der
   Satz entstanden ist. Ein Vorschlag, dessen Grundlage man nicht nachsehen
   kann, ist in einem Nachweiswerkzeug wenig wert (#1878).
3. **Es ist ein Vorschlag.** Diese Funktionen schreiben nichts. Ein gefülltes
   Feld ist die Aussage eines Menschen; es beim Öffnen des Formulars
   stillschweigend zu ersetzen wäre derselbe Fehler wie der Verzeichnis-Scan in
   #1769 und die Gruppenübernahme ohne ``nur_offene`` (#1773).

Die reinen Funktionen (:func:`charge`, :func:`gegenstand`,
:func:`normen_kandidaten`) nehmen alles als Argument und sind ohne Datenbank
prüfbar; :func:`vorschlag` ist der eine Ort, an dem gelesen wird.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from cra import normen_katalog as nk
from shared.formular_vorschlag import (KLASSE_AUSWAHL, KLASSE_GERECHNET,
                                       KLASSE_KI, KLASSE_UEBERNOMMEN, Sammler,
                                       filter_ki)

DB_PATH = Path("data/db/cra.sqlite")

#: Ein Digest ist ``sha256:`` plus **64** Hex-Zeichen. Dasselbe Muster steht in
#: ``cra/sbom_registry._REF``; hier wird es gebraucht, um einen unvollständigen
#: Digest **nicht** in den Vorschlag zu schreiben (der Befund aus #1885).
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")

#: Versionsähnliche Zeichenfolgen in einem Text — Grundlage des
#: Widerspruchs-Abgleichs in :mod:`cra.doc_pruefung`.
_VERSION = re.compile(r"\b[vV]?(\d+(?:\.\d+){1,3})\b")


#: Welche Klasse ein Feld der Erklärung hat — und damit, welcher Knopf daneben
#: steht (#1887).
#:
#: * ``gerechnet`` — die Akte weiß die Antwort. Version, Gegenstand (mit Image
#:   und Digest), das durchlaufene Verfahren, das Ausstellungsdatum.
#: * ``uebernommen`` — die Angabe steht an anderer Stelle in der Suite.
#: * ``auswahl`` — ein Katalog zum Anhaken, keine Prosa.
#: * ``ki`` — Prosa, die sonst ein Mensch formuliert.
#:
#: Felder ohne Eintrag sind reine Eingabe (``produkt_typ`` steht als ``ki``
#: drin, weil ein Entwurf daraus entstehen kann; ``nb_name`` und
#: ``nb_zertifikat`` kommen von der notifizierten Stelle und von nirgends sonst).
FELD_KLASSE: dict[str, str] = {
    "produkt_charge": KLASSE_GERECHNET,
    "gegenstand": KLASSE_GERECHNET,
    "nb_verfahren": KLASSE_GERECHNET,
    "datum": KLASSE_GERECHNET,
    "produkt_name": KLASSE_UEBERNOMMEN,
    "hersteller": KLASSE_UEBERNOMMEN,
    "hersteller_adresse": KLASSE_UEBERNOMMEN,
    "ort": KLASSE_UEBERNOMMEN,
    "unterzeichner_name": KLASSE_UEBERNOMMEN,
    "unterzeichner_funktion": KLASSE_UEBERNOMMEN,
    "bevollmaechtigter": KLASSE_UEBERNOMMEN,
    "nb_kennnummer": KLASSE_UEBERNOMMEN,
    "normen": KLASSE_AUSWAHL,
    "weiteres_unionsrecht": KLASSE_AUSWAHL,
    "produkt_typ": KLASSE_KI,
    "zusatzangaben": KLASSE_KI,
}

#: Felder, die eine KI-Antwort setzen darf — **abschließend**.
#:
#: Dies ist die wichtigste Zeile dieser Datei. Ein Modell, das „Release 8.0.11"
#: plausibel findet, erzeugt genau den Fall aus #1885 — nur sieht es dann wie
#: eine Aussage aus. Version, Hersteller, Anschrift, Unterzeichner, Datum,
#: Digest und die NB-Angaben sind gerechnet oder übernommen; sie stammen aus
#: der Akte und nicht aus einer Wahrscheinlichkeit. ``gegenstand`` steht hier,
#: weil der Feinschliff der Prosa erwünscht ist — die **Zahlen** darin prüft
#: ``cra.doc_pruefung`` anschließend gegen die Akte, und ein Widerspruch
#: blockiert das Ausstellen.
KI_FELDER: frozenset[str] = frozenset({"produkt_typ", "zusatzangaben",
                                       "gegenstand"})


def _s(wert: Any) -> str:
    return "" if wert is None else str(wert).strip()


def _version_nummer(wert: Any) -> str:
    """``v8.2.3`` → ``8.2.3``. Die Zahl ist der Vergleichsgegenstand.

    ``v1.0`` und ``1.0`` bezeichnen dasselbe Release; als Zeichenketten sind
    sie verschieden, und ein Abgleich auf der Zeichenkette hätte einen
    Widerspruch gemeldet, den es nicht gibt.
    """
    m = _VERSION.search(_s(wert))
    return m.group(1) if m else ""


def versionen_im_text(text: Any) -> list[str]:
    """Alle versionsähnlichen Zahlen eines Textes, Reihenfolge erhalten."""
    out: list[str] = []
    for m in _VERSION.finditer(_s(text)):
        if m.group(1) not in out:
            out.append(m.group(1))
    return out


# ── Nr. 1 — Charge, Serie oder Version ──────────────────────────────────────

def charge(*, release_version: str = "", abgeleitete_version: str = "") -> str:
    """Anhang V Nr. 1 — die Version, die das Produkt in Verkehr bringt.

    **Vorrang hat der Release-Vorgang.** Wird die Erklärung aus einem Vorgang
    heraus gepflegt, ist dessen Version die genauere Angabe; die Erklärung
    gehört zwar dem Produkt (#1805), aber ein Vorgang bezeichnet genau einen
    Stand.

    Ohne Vorgang gilt ``abgeleitete_version`` — die **höchste herausgegebene**
    Version aus ``release_db.abgeleitete_version`` (#1820). Der dort
    gespeicherte Wert (``aktuelle_version_gespeichert``) ist bewusst **nicht**
    die Quelle: Er wird nur über den Weg „wesentliche Änderung erfassen"
    geschrieben und bleibt auf Installationen, die ihre Releases über den
    Releases-Tab führen, dauerhaft auf einem alten Wert stehen. Genau das war
    der Defekt aus #1820, und hier landete er in einem unterschriebenen
    Dokument.
    """
    roh = _s(release_version) or _s(abgeleitete_version)
    if not roh:
        return ""
    nummer = _version_nummer(roh)
    return f"Version {nummer}" if nummer else roh


# ── Nr. 4 — Gegenstand der Erklärung ────────────────────────────────────────

def gegenstand(*, produkt: str = "", beschreibung: str = "",
               version: str = "", artefakte: list[dict[str, Any]] | None = None,
               bereitstellung: str = "",
               versionsanzeige: str = "") -> dict[str, Any]:
    """Anhang V Nr. 4 — die Bezeichnung, die das Produkt rückverfolgbar macht.

    ``artefakte`` ist eine Liste aus ``{name, referenz, digest, format}``.
    **Alle** werden genannt, nicht nur das erste: Ein Produkt führt Anwendung,
    Webserver und Agent als eigene SBOMs derselben Version (#1771). Nur die
    neueste Zeile zu nehmen ist die Falle, in die ``befund()`` dort schon
    gelaufen ist — in einer Erklärung wäre es eine unvollständige Bezeichnung
    des Gegenstands.

    **Ein unvollständiger Digest wird weggelassen, nicht angedeutet.** Steht in
    der Akte kein ``sha256:`` plus 64 Hex-Zeichen, erscheint die Referenz ohne
    Digest und die Auslassung in ``fehlend``. Ein ``sha256:…`` im Text wäre ein
    Platzhalter in einer Konformitätserklärung — der erste Befund aus #1885.
    """
    artefakte = list(artefakte or [])
    saetze: list[str] = []
    fundstellen: list[dict[str, str]] = []
    fehlend: list[dict[str, str]] = []

    produkt, beschreibung = _s(produkt), _s(beschreibung)
    nummer = _version_nummer(version)

    # Satz 1 — Produkt, Release, Zweck, Bereitstellungsform.
    kopf = produkt or ""
    if not kopf:
        fehlend.append({"feld": "produkt",
                        "text": "Produktname (Projekt-Stammdaten) ist leer."})
    if nummer:
        kopf = f"{kopf}, Release {nummer}" if kopf else f"Release {nummer}"
        fundstellen.append({"quelle": "release",
                            "text": f"Herausgegebene Version: {nummer}"})
    else:
        fehlend.append({"feld": "version",
                        "text": "Keine herausgegebene Version bekannt — der "
                                "Satz nennt deshalb kein Release."})
    if beschreibung:
        kopf = f"{kopf} – {beschreibung}" if kopf else beschreibung
        fundstellen.append({"quelle": "projekt",
                            "text": "Beschreibung aus den Projekt-Stammdaten"})
    else:
        fehlend.append({"feld": "beschreibung",
                        "text": "Projekt-Beschreibung ist leer — der Zweck des "
                                "Produkts fehlt damit im Gegenstand."})
    if _s(bereitstellung):
        kopf = (f"{kopf}, bereitgestellt als {_s(bereitstellung)}"
                if kopf else f"Bereitgestellt als {_s(bereitstellung)}")
        fundstellen.append({"quelle": "projekt",
                            "text": f"Bereitstellungsform: {_s(bereitstellung)}"})
    else:
        fehlend.append({"feld": "bereitstellung",
                        "text": "Bereitstellungsform ist in den Projekt-"
                                "Stammdaten nicht erfasst (Container-Image, "
                                "Installationspaket, SaaS …)."})
    if kopf:
        saetze.append(kopf.rstrip(".") + ".")

    # Satz 2 — die Artefakte mit Referenz und Digest.
    mit_digest = 0
    formate: list[str] = []
    for a in artefakte:
        ref = _s(a.get("referenz"))
        if not ref:
            continue
        name = _s(a.get("name"))
        digest = _s(a.get("digest"))
        teil = f"{name}: {ref}" if name else ref
        if _DIGEST.match(digest):
            teil += f", Digest {digest}"
            mit_digest += 1
            fmt = _s(a.get("format")).upper()
            if fmt and fmt not in formate:
                formate.append(fmt)
        elif digest:
            fehlend.append({
                "feld": "digest",
                "text": f"Der gespeicherte Digest zu {ref} ist kein "
                        "vollständiger sha256-Wert und wird weggelassen."})
        else:
            fehlend.append({
                "feld": "digest",
                "text": f"Zu {ref} ist kein Digest gespeichert — „SBOM vom "
                        "Image holen" "" " im C1-Abschnitt löst ihn auf."})
        saetze.append(teil + ".")
        fundstellen.append({"quelle": "sbom",
                            "text": f"SBOM-Verzeichnis: {teil}"})
    if not artefakte:
        fehlend.append({"feld": "artefakt",
                        "text": "Im SBOM-Verzeichnis ist kein Artefakt mit "
                                "Image-Referenz erfasst."})

    # Satz 3 — die Bindung der SBOM. Belegt ist sie durch den Abrufweg: Die
    # SBOM liegt in der Registry unter dem cosign-Tag `sha256-<digest>.att`
    # als signierter DSSE-Envelope (`cra/sbom_registry.hole_sbom`). Behauptet
    # wird deshalb die **Form** („signierte Attestierung am Digest"), nicht die
    # Gültigkeit der Signatur — die prüft `cosign verify-attestation` und nicht
    # diese Anwendung. Ohne gespeicherten Digest entfällt der Satz: Dann ist
    # die Bindung nicht belegt.
    if mit_digest:
        fmt = " / ".join(formate) if formate else "SBOM"
        ziel = "diesen Digest" if mit_digest == 1 else "die genannten Digests"
        saetze.append(
            f"Die zugehörige Stückliste ({fmt}) ist als mit Sigstore/cosign "
            f"signierte Attestierung an {ziel} gebunden.")
        fundstellen.append({
            "quelle": "registry",
            "text": "Die Attestierung wurde über den cosign-Tag "
                    "sha256-<digest>.att aus der Registry gelesen."})

    # Satz 4 — die Versionsanzeige. Eine Behauptung über das Produkt, die nur
    # haltbar ist, wenn die Akte sie trägt (zweiter Befund aus #1885).
    if _s(versionsanzeige):
        saetze.append("Die installierte Version wird in der Anwendung unter "
                      f"„{_s(versionsanzeige)}" "" "“ angezeigt.")
        fundstellen.append({"quelle": "projekt",
                            "text": f"Versionsanzeige: {_s(versionsanzeige)}"})
    else:
        fehlend.append({
            "feld": "versionsanzeige",
            "text": "Wo die installierte Version sichtbar ist, ist nicht "
                    "erfasst — der Satz dazu entfällt. Er wäre sonst eine "
                    "Behauptung über das Produkt ohne Grundlage in der Akte."})

    return {"text": "\n".join(saetze), "fundstellen": fundstellen,
            "fehlend": fehlend}


# ── Nr. 6 — Kandidaten für angewandte Spezifikationen ───────────────────────

def normen_kandidaten(*, owasp_bewertet: int = 0, threat_framework: str = "",
                      sbom_formate: tuple[str, ...] | list[str] = (),
                      wiba_projekt: str = "") -> list[dict[str, Any]]:
    """Welche Spezifikationen die Akte selbst belegt.

    Das ist die Ausfüllhilfe, die ohne KI auskommt: Was das Haus angewandt hat,
    steht an anderer Stelle in dieser Anwendung schon — im OWASP-Register, im
    Bedrohungsmodell, im SBOM-Format, im verknüpften WiBA-Projekt. Daraus
    entsteht eine **Vorschlagsliste zum Anhaken**, keine Eintragung: Was in der
    Erklärung steht, muss der Unterzeichner bewusst gewählt haben.

    **Harmonisierte Normen kommen hier nie vor.** Sie sind nicht aus dem
    Arbeitsstand herleitbar, und eine hergeleitete Vermutungswirkung (Art. 27)
    wäre der folgenschwerste Fehler, den diese Datei machen könnte.
    """
    belegt: dict[str, str] = {}
    if int(owasp_bewertet or 0) > 0:
        belegt["owasp"] = (f"{int(owasp_bewertet)} bewertete Kontrolle(n) im "
                           "OWASP-Register dieses Projekts")
    tf = _s(threat_framework).upper()
    if tf.startswith("STRIDE"):
        belegt["threat_stride"] = f"Bedrohungsmodell mit Framework {_s(threat_framework)}"
    for fmt in sbom_formate or ():
        f = _s(fmt).lower()
        if f == "spdx":
            belegt["sbom_spdx"] = "SBOM im Format SPDX im Verzeichnis erfasst"
        elif f == "cyclonedx":
            belegt["sbom_cyclonedx"] = "SBOM im Format CycloneDX im Verzeichnis erfasst"
    if _s(wiba_projekt):
        belegt["wiba"] = f"Verknüpftes WiBA-Projekt „{_s(wiba_projekt)}“"

    out: list[dict[str, Any]] = []
    for norm in nk.SPEZIFIKATIONEN:
        treffer = [belegt[b] for b in norm.belege if b in belegt]
        if treffer:
            eintrag = norm.as_dict()
            eintrag["herkunft"] = "; ".join(treffer)
            out.append(eintrag)
    return out


# ── Feldvorschläge je Quelle ────────────────────────────────────────────────

def feld_vorschlaege(*, projekt: dict[str, Any] | None = None,
                     hersteller_stamm: dict[str, Any] | None = None,
                     bevollmaechtigter: dict[str, Any] | None = None,
                     bewertungsweg: str = "", nb_kennnummer: str = "",
                     release_version: str = "", abgeleitete_version: str = "",
                     gegenstand_text: str = "",
                     heute: str = "") -> dict[str, dict[str, Any]]:
    """Was die Anwendung zu jedem Feld aus den Quellen sagen kann (#1887).

    Jeder Eintrag trägt ``wert``, ``quelle`` (woher) und ``klasse``. Ein Feld
    ohne Quelle erscheint **nicht** — ein leerer Vorschlag mit Quellenangabe
    wäre ein Angebot, das ins Nichts führt.

    Reine Funktion: Alle Quellen kommen als Argument. Gelesen wird in
    :func:`vorschlag`.
    """
    projekt = projekt or {}
    hersteller_stamm = hersteller_stamm or {}
    # Der Sammler aus #1893 setzt die Regel „nur mit Wert **und** Quelle" an
    # einer Stelle für alle Module.
    sammler = Sammler(FELD_KLASSE)
    _setze = sammler.setze

    _setze("produkt_name", _s(projekt.get("produkt")) or _s(projekt.get("name")),
           "Projekt-Stammdaten")
    _setze("hersteller", _s(projekt.get("unternehmen")), "Projekt-Stammdaten")
    _setze("hersteller_adresse", _s(hersteller_stamm.get("anschrift")),
           "Herstellerangaben des Mandanten")
    _setze("ort", _s(hersteller_stamm.get("ort")),
           "Herstellerangaben des Mandanten")
    _setze("unterzeichner_name", _s(hersteller_stamm.get("unterzeichner_name")),
           "Herstellerangaben des Mandanten")
    _setze("unterzeichner_funktion",
           _s(hersteller_stamm.get("unterzeichner_funktion")),
           "Herstellerangaben des Mandanten")

    if bevollmaechtigter:
        teile = [_s(bevollmaechtigter.get("name")),
                 _s(bevollmaechtigter.get("anschrift"))]
        _setze("bevollmaechtigter", ", ".join(t for t in teile if t),
               "CRA-Akteure (Rolle „Bevollmächtigter“)")

    _setze("nb_kennnummer", _s(nb_kennnummer), "Konformitätsbewertung")
    if _s(bewertungsweg):
        _setze("nb_verfahren", f"Modul {_s(bewertungsweg)} (Anhang VIII)",
               "Gewählter Bewertungsweg")

    _setze("produkt_charge",
           charge(release_version=release_version,
                  abgeleitete_version=abgeleitete_version),
           "Release-Vorgang" if _s(release_version) else "Release-Historie (#1820)")
    _setze("gegenstand", gegenstand_text,
           "Projekt, Release und SBOM-Verzeichnis")
    # Das Ausstellungsdatum ist der Tag, an dem unterschrieben wird. Ein
    # Vorschlag „heute" ist deshalb richtig — und `doc_pruefung` hält ihn
    # gegen das Freigabedatum des erklärten Release.
    _setze("datum", _s(heute), "Heutiges Datum")
    return sammler.ergebnis()


# ── Der eine Ort, an dem gelesen wird ───────────────────────────────────────

#: Welche Spalte des Mandanten welche Angabe der Erklärung speist (#1892).
_STAMM_SPALTEN: dict[str, str] = {
    "anschrift": "anschrift",
    "ort": "ort",
    "unterzeichner_name": "vertreter_name",
    "unterzeichner_funktion": "vertreter_funktion",
}


def hersteller_stammdaten(firma: dict[str, Any] | None) -> dict[str, Any]:
    """Herstellerangaben des **Mandanten** (#1887, Spalten seit #1892).

    Anschrift, Ort und Unterzeichner gehören dem Mandanten, nicht dem
    einzelnen Produkt: Ein Mandant hat mehrere Produkte, und die Anschrift je
    CRA-Projekt zu tippen ist genau die Doppelpflege, die hier wegfällt. Beim
    vierten Mal steht sonst eine andere da.

    **Gelesen werden die echten Spalten**, nicht mehr ``meta.hersteller``.
    #1887 hatte sie dort notdürftig abgelegt — richtige Ebene, falscher Ort:
    ``meta_json`` erscheint in keiner Firmenmaske. ``meta`` bleibt der
    **Rückfall**, damit eine Installation, die zwischen zwei Versionen
    springt, ihre Angaben noch findet; der Umzug in die Spalten läuft
    idempotent beim Start (``firmen.db._migrate_hersteller_meta``).

    Die Anschrift wird **formatiert** übernommen (``firmen.db.anschrift_text``)
    — damit die Erklärung und ein Bericht desselben Mandanten nicht
    verschieden aussehen.
    """
    firma = dict(firma or {})
    meta = firma.get("meta") if isinstance(firma.get("meta"), dict) else {}
    alt = meta.get("hersteller") if isinstance(meta.get("hersteller"), dict) else {}

    out: dict[str, Any] = {}
    for schluessel, spalte in _STAMM_SPALTEN.items():
        wert = _s(firma.get(spalte)) or _s(alt.get(schluessel))
        if wert:
            out[schluessel] = wert
    # Die vollständige Anschrift, soweit die Spalten sie tragen.
    if _s(firma.get("anschrift")):
        try:
            from firmen.db import anschrift_text

            voll = _s(anschrift_text(firma))
            if voll:
                out["anschrift"] = voll
        except Exception:  # noqa: BLE001 — die Rohanschrift ist gut genug
            pass
    return out

def _artefakte_aus_sbom(zeilen: list[dict[str, Any]],
                        version: str) -> list[dict[str, Any]]:
    """SBOM-Zeilen mit Image-Referenz → Artefakte des Gegenstands.

    Gefiltert wird auf die **Version**, um die es geht: Die SBOM einer alten
    Fassung beschreibt ein anderes Artefakt. Gibt es zur Version keine Zeile,
    bleibt die Liste leer — und der Gegenstand nennt kein Image, statt das
    falsche zu nennen.
    """
    from cra.sbom_registry import ist_image_referenz, zerlege

    nummer = _version_nummer(version)
    out: list[dict[str, Any]] = []
    for z in zeilen:
        if nummer and _version_nummer(z.get("release_version")) != nummer:
            continue
        ref = _s(z.get("blob_path"))
        if not ist_image_referenz(ref):
            continue
        digest = _s(z.get("image_digest"))
        # Die Referenz mit Digest ist die eindeutige: Ein Tag kann neu belegt
        # werden, ein Digest nicht. Steht der Digest schon in der Referenz,
        # bleibt sie, wie sie ist.
        anzeige = ref
        if digest and "@sha256:" not in ref:
            try:
                t = zerlege(ref) or {}
                anzeige = f"{t.get('host', '')}/{t.get('repo', '')}:{t.get('tag', '')}"
            except Exception:  # noqa: BLE001 — die Rohreferenz ist gut genug
                anzeige = ref
        elif "@sha256:" in ref and not digest:
            digest = "sha256:" + ref.split("@sha256:", 1)[1]
        out.append({"name": _s(z.get("artefakt")), "referenz": anzeige,
                    "digest": digest, "format": _s(z.get("sbom_format")),
                    "sbom_id": z.get("id")})
    return out


def vorschlag(db_path: Path | str = DB_PATH, projekt_name: str = "",
              release_version: str = "") -> dict[str, Any]:
    """Vorschläge für Nr. 1, Nr. 4 und die Kandidaten zu Nr. 6.

    Liest, rechnet, schreibt **nichts**. Jede Teilquelle ist einzeln
    abgesichert: Eine Erklärung muss auch dann vorbereitbar sein, wenn ein
    Register noch leer oder ein Modul nicht angebunden ist.
    """
    from cra.db import list_sbom, load_owasp_checks, load_projekt, load_threatmodel

    db_path = Path(db_path)

    def _sicher(fn, standard):
        """Eine ausgefallene Teilquelle darf den Vorschlag nicht verhindern.

        **Aber nicht jeden Fehler:** ``ImportError`` und ``AttributeError``
        sind Programmierfehler und werden durchgelassen. Die erste Fassung
        fing sie mit — und verschluckte damit einen falschen Importnamen
        (``firmen.db.DB_PATH`` statt ``DEFAULT_DB_PATH``). Der Mandant wurde
        nie aufgelöst, die Herstellerangaben blieben leer, und nichts schlug
        fehl. Genau die Fehlerklasse, die dieses Projekt wiederholt bezahlt
        hat (#1805/#1870): Es wird das Falsche gelesen, und es sieht aus wie
        „nichts erfasst".
        """
        try:
            return fn()
        except (ImportError, AttributeError):
            raise
        except Exception:  # noqa: BLE001 — leere oder kaputte Teilquelle
            return standard

    proj = _sicher(lambda: load_projekt(db_path, projekt_name) or {}, {})
    meta = proj.get("meta") if isinstance(proj.get("meta"), dict) else {}
    doc_meta = meta.get("doc") if isinstance(meta.get("doc"), dict) else {}

    abgeleitete = ""
    if not _s(release_version):
        rel = _sicher(lambda: __import__(
            "cra.release_db", fromlist=["get_release"]
        ).get_release(db_path, projekt_name) or {}, {})
        abgeleitete = _s(rel.get("aktuelle_version"))

    version = _s(release_version) or abgeleitete
    sboms = _sicher(lambda: list_sbom(db_path, projekt_name) or [], [])
    artefakte = _sicher(lambda: _artefakte_aus_sbom(sboms, version), [])

    owasp = _sicher(lambda: load_owasp_checks(db_path, projekt_name) or {}, {})
    bewertet = sum(1 for v in owasp.values()
                   if int((v or {}).get("status") or 0) > 0)
    tm = _sicher(lambda: load_threatmodel(db_path, projekt_name) or {}, {})

    geg = gegenstand(
        produkt=_s(proj.get("produkt")) or _s(proj.get("name")) or _s(projekt_name),
        beschreibung=_s(proj.get("beschreibung")),
        version=version, artefakte=artefakte,
        bereitstellung=_s(doc_meta.get("bereitstellung")),
        versionsanzeige=_s(doc_meta.get("versionsanzeige")))

    # Der Konformitäts-Record liefert Bewertungsweg und NB-Kennnummer; die
    # Herstellerangaben kommen vom Mandanten, der Bevollmächtigte aus den
    # CRA-Akteuren.
    rec = _sicher(lambda: __import__(
        "cra.konformitaet_db", fromlist=["get_konformitaet"]
    ).get_konformitaet(db_path, projekt_name, _s(release_version)) or {}, {})
    firma = _sicher(lambda: _firma_des_projekts(db_path, projekt_name), {})
    bevoll = _sicher(lambda: _bevollmaechtigter(db_path, projekt_name), {})

    from datetime import date as _date

    felder = feld_vorschlaege(
        projekt=proj, hersteller_stamm=hersteller_stammdaten(firma),
        bevollmaechtigter=bevoll,
        bewertungsweg=_s(rec.get("bewertungsweg")),
        nb_kennnummer=_s(rec.get("nb_kennnummer")),
        release_version=_s(release_version), abgeleitete_version=abgeleitete,
        gegenstand_text=geg["text"], heute=_date.today().isoformat())

    return {
        "charge": charge(release_version=release_version,
                         abgeleitete_version=abgeleitete),
        "gegenstand": geg,
        "felder": felder,
        "klassen": dict(FELD_KLASSE),
        "ki_felder": sorted(KI_FELDER),
        "normen": normen_kandidaten(
            owasp_bewertet=bewertet,
            threat_framework=_s(tm.get("framework")),
            sbom_formate=tuple(_s(z.get("sbom_format")) for z in sboms),
            wiba_projekt=_s(meta.get("linked_wiba_projekt"))),
        "katalog": nk.katalog(),
        "unionsrecht": nk.unionsrecht_katalog(),
        "hersteller_stamm": hersteller_stammdaten(firma),
        "firma": _s((firma or {}).get("name")),
        "version": version,
        "version_quelle": ("release-vorgang" if _s(release_version)
                           else ("abgeleitet" if abgeleitete else "")),
    }


def _firma_des_projekts(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Den Mandanten zum CRA-Projekt auflösen.

    Über ``shared.firmen_link.projekt_firmen_id`` — dieselbe Auflösung, die die
    Firmen-ACL benutzt (``server/middleware/firma_acl``). Eine zweite Abfrage
    dafür wäre die zweite Wahrheit über die Zugehörigkeit, und an ihr hängt
    hier, wessen Anschrift in einer Konformitätserklärung steht.
    """
    from firmen.db import DEFAULT_DB_PATH as FIRMEN_DB, load_firma
    from shared.firmen_link import firmen_name_to_id, projekt_firmen_id

    # ``projekt_firmen_id`` nimmt den **DB-Pfad**, nicht den Modulnamen:
    # ``MODULE_PROJECT_TABLES`` ist nach Dateinamen geschlüsselt
    # (``cra.sqlite``). Mit ``"cra"`` kam immer ``None`` zurück — und weil der
    # Aufrufer fail-open ist, blieb es stumm.
    fid = projekt_firmen_id(db_path, projekt_name)
    if not fid:
        return {}
    # Umgekehrt über ``firmen_name_to_id`` statt über die Zeilen der
    # Firmenliste: Deren Form (Liste oder Dict) hängt von der Abfrage ab, und
    # eine zweite Auflösung Name→ID wäre die Spiegel-Liste aus #1731.
    for name, kennung in (firmen_name_to_id(FIRMEN_DB) or {}).items():
        if int(kennung) == int(fid):
            return load_firma(FIRMEN_DB, str(name)) or {}
    return {}


def _bevollmaechtigter(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Der erfasste EU-Bevollmächtigte aus ``cra_akteure`` (Anhang V Nr. 2)."""
    from cra.akteure_db import list_akteure

    for a in list_akteure(db_path, projekt_name) or []:
        if _s(a.get("rolle")) == "bevollmaechtigter" and _s(a.get("name")):
            return dict(a)
    return {}


def uebernahme_filter(felder: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Was eine KI-Antwort setzen darf — und was verworfen wird (#1887).

    Serverseitig, nicht im Browser: Die Grenze zwischen „die KI formuliert" und
    „die Akte rechnet" ist der Kern dieser Erweiterung, und eine Grenze, die
    der Client zieht, ist keine. Verworfene Felder werden **benannt** — ein
    stilles Weglassen sähe aus, als hätte das Modell sie nicht geliefert.
    """
    return filter_ki(felder, KI_FELDER)


__all__ = ["charge", "gegenstand", "normen_kandidaten", "vorschlag",
           "versionen_im_text", "feld_vorschlaege", "hersteller_stammdaten",
           "uebernahme_filter", "FELD_KLASSE", "KI_FELDER"]
