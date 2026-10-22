"""CRA-Konformitäts-Gate je Release (#1612/#1613) + Release-Pflichten (#1745).

Entscheidet maschinell, ob ein Produkt-Release als CRA-konform ausgewiesen werden darf.
Grundsatz (CRA): essenzielle Anforderungen (Annex I) sind verpflichtend. Eine Abweichung
gilt nur dann als konform, wenn sie **risikobasiert begründet** ist — das verknüpfte
Nichterfüllungs-Risiko ist als Restrisiko **akzeptiert** (Kategorie nicht_anwendbar /
restrisiko / kompensierend, #1613). Eine offene Nicht-Konformität einer anwendbaren
Anforderung verhindert die grüne Ampel.

**Zwei Phasen (#1742/#1745).** CRA zerfällt für den Anwender in zwei Fragen, und die
muss das Ergebnis auseinanderhalten — sonst weiß er nicht, ob sein *Produkt* oder sein
*Release* das Problem ist:

- ``phase='produkt'`` — ``evaluate(projekt)`` ohne Version: der Produktzustand
  (Anforderungen, offene kritische Schwachstellen, Annex VII, DoC). Unverändert
  gegenüber dem Bestand; die Release-Prüfungen laufen hier **gar nicht**.
- ``phase='release'`` — ``evaluate(projekt, version='…')``: zusätzlich die Pflichten,
  die sich bei *jedem* Release stellen (Advisory zu behobenen Schwachstellen, SBOM zur
  Version, Support-Zeitraum, Meldefristen, dokumentierte Schwachstellenbehandlung).

Die offenen Punkte liegen getrennt als ``produkt_punkte`` / ``release_punkte`` vor;
``offene_punkte`` bleibt deren Vereinigung, damit Panel und ``release-check`` unverändert
weiterlaufen. Jeder Punkt behält die Form ``{typ, titel, hinweis, link}`` — daraus baut
das Frontend „→ hier pflegen". Die gerechneten Zahlen dahinter stehen in
``release_befunde`` und zusätzlich flach unter den Namen, die der Release-Katalog
(#1744) als ``quelle`` nennt (``behobene_ohne_advisory``, ``sbom_version_fehlt``,
``support_ueberschritten``, ``ueberfaellige_meldungen``,
``bewertungsweg_unzulaessig``).

``bewertungsweg_unzulaessig`` (#1759) ist der einzige davon, der **in beiden
Phasen** gerechnet wird: Ob der gewählte Konformitätsbewertungsweg für die
Produktklasse zulässig ist (Art. 32), ist eine Frage an das Produkt und an jedes
Release. Er wirkt ``rot``.

Ampel:
- ``gruen``   — alle anwendbaren Anforderungen erfüllt oder begründet, keine offenen
               kritischen/hohen Schwachstellen, Annex VII vollständig, DoC ausgestellt,
               und (Phase 2) kein offener Release-Punkt.
- ``bedingt`` — nur noch begründete Abweichungen mit Auflagen / kleinere offene Punkte.
- ``rot``     — offene Nicht-Konformitäten / offene kritische Schwachstellen /
               überfällige Meldefrist / Release außerhalb des Support-Zeitraums.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

CRA_DB = Path("data/db/cra.sqlite")
RB_DB = Path("data/db/risikobewertung.sqlite")

# Bewertung >= 4 (überwiegend/vollständig umgesetzt) gilt als erfüllt.
_ERFUELLT_AB = 4


def _accepted_gap_for(rb_name: str, requirement_id: str,
                      risks_by_src: dict[str, list[dict]]) -> dict | None:
    """Liefert ein akzeptiertes Nichterfüllungs-Risiko für die Anforderung, falls vorhanden."""
    src_id = f"cra:requirement:{requirement_id}"
    for r in risks_by_src.get(src_id, []):
        if (r.get("behandlung") or "") == "akzeptiert" and (r.get("akzeptanz_kategorie") or ""):
            return r
    return None


# ── Phase 2: Release-Pflichten (#1745) ────────────────────────────────────────
#
# Ampel-Wirkung je Prüfpunkt — bewusst so und nicht anders:
#
# ``rot``      überfällige Meldefrist (Art. 14) und ein Release außerhalb des
#              Support-Zeitraums (Art. 13 Abs. 8). Beides ist eine *Pflicht-
#              verletzung* gegenüber Behörde bzw. Nutzer, kein Nachweismangel —
#              das Release darf nicht als konform ausgewiesen werden.
# ``bedingt``  fehlendes Advisory (Anhang I Teil II Nr. 8), keine SBOM zur
#              Release-Version (Anhang I Teil II Nr. 1), nicht dokumentierte
#              Schwachstellenbehandlung (Anhang I Teil II), fehlende Angaben zum
#              Support-Zeitraum. Begründung: Ein fehlendes Advisory macht ein
#              Release nicht nicht-konform, aber nicht nachweisbar. Die Akte ist
#              unvollständig, der Inhalt kann stimmen.
#
# Ein Prüfpunkt, der wegen eines Datenfehlers **nicht geprüft werden konnte**,
# erscheint als eigener Punkt mit ``ungeprueft=True`` und wirkt wie ``bedingt``.
# Das ist hier die wichtigste Regel: Ein stilles ``except: pass`` ließe den Punkt
# verschwinden, die Ampel würde grün — und der Anwender hielte für geprüft, was
# niemand geprüft hat. Unprüfbar ist nicht erfüllt.

# Punkte der Phase 2 tragen zusätzlich ``phase`` und ``ampel_wirkung``; die Felder
# der Phase-1-Punkte bleiben unangetastet (Panel-Vertrag).
_WIRKUNG_ROT = "rot"
_WIRKUNG_BEDINGT = "bedingt"


def _norm_version(value: Any) -> str:
    """Versionsangaben vergleichbar machen: Leerraum weg, Kleinschreibung, ein
    führendes ``v`` entfällt.

    Grund: Release-Tags kommen als ``v7.4.8`` aus dem Repo, ``fixed_in_version``
    tippt ein Mensch meist als ``7.4.8``. Ohne diese Angleichung findet der
    Advisory-Check seine Schwachstellen nicht — und ein Prüfpunkt, der nichts
    findet, sieht aus wie ein erfüllter.
    """
    s = str(value or "").strip().lower()
    return s[1:] if len(s) > 1 and s.startswith("v") else s


def _punkt(typ: str, titel: str, hinweis: str, link: str,
           *, wirkung: str = _WIRKUNG_BEDINGT, **extra: Any) -> dict[str, Any]:
    """Offener Punkt der Phase 2 in der Form, die das Panel erwartet."""
    p: dict[str, Any] = {"typ": typ, "titel": titel, "hinweis": hinweis, "link": link,
                         "phase": "release", "ampel_wirkung": wirkung}
    p.update(extra)
    return p


def _ungeprueft(typ: str, titel: str, link: str, exc: BaseException) -> dict[str, Any]:
    """Punkt für eine Prüfung, die nicht laufen konnte — sichtbar, nicht verschluckt."""
    return _punkt(typ, titel,
                  f"konnte nicht geprüft werden ({type(exc).__name__}: {exc}) — "
                  "Datenquelle prüfen und erneut bewerten",
                  link, ungeprueft=True)


# ── Art. 32: Bewertungsweg gegen die Produktklasse (#1759) ───────────────────
#
# Dieser Prüfpunkt gilt in **beiden** Phasen, denn die Frage stellt sich zweimal:
# am Produkt (welcher Weg wurde für dieses Produkt gewählt?) und am Release
# (welcher Weg steht im Vorgang dieser Version?). Er wirkt **rot** — ein für die
# Produktklasse unzulässiger Weg ist keine Lücke in der Akte, sondern eine
# Nicht-Konformität: Die darauf gestützte EU-Konformitätserklärung trägt nicht.

def _weg_befund(projekt_name: str, version: str) -> dict[str, Any]:
    """Ist der gewählte Bewertungsweg für die Produktklasse zulässig?

    ``zulaessig`` ist ``True`` (geprüft, in Ordnung), ``False`` (unzulässig) oder
    ``None`` — und ``None`` heißt zwei verschiedene Dinge, die auseinandergehalten
    werden müssen: Es ist **kein Weg gewählt** (dann gibt es nichts zu beurteilen;
    dass die Erklärung fehlt, meldet der DoC-Prüfpunkt), oder die **Quelle fiel
    aus** (dann zusätzlich ``ungeprueft`` — ungeprüft ist nicht erfüllt, #1751).

    Wirft nicht: Die Ampel darf an einem Datenfehler nicht hängen bleiben,
    sichtbar bleibt er über ``ungeprueft``.
    """
    befund: dict[str, Any] = {"zulaessig": None, "ungeprueft": False,
                              "klasse": "", "weg": ""}
    try:
        from cra import konformitaet_db as kdb
        from cra import requirements as req
        from cra.db import load_projekt

        rec = kdb.get_konformitaet(CRA_DB, projekt_name, str(version or "")) or {}
        weg = str(rec.get("bewertungsweg") or "").strip()
        if not weg:
            return befund
        # Die Klasse liegt an zwei Stellen (Projekt + Kopie im Record) und die
        # Oberfläche schickt beim Speichern des Records keine mit. Die strengere
        # gilt — sonst hebt ein leeres Feld die Prüfung auf.
        klasse = req.strengste_klasse(
            rec.get("produktklasse"),
            (load_projekt(CRA_DB, projekt_name) or {}).get("produktklasse"))
        befund.update({"klasse": klasse, "weg": weg,
                       "ref": req.weg_regel_referenz(klasse)})
        ablehnung = req.weg_ablehnung(klasse, weg)
        if not ablehnung:
            befund["zulaessig"] = True
            return befund
        befund.update({
            "zulaessig": False,
            "titel": (f"Bewertungsweg {weg} ist für die Produktklasse "
                      f"„{req.klasse_label(klasse)}“ nicht zulässig"),
            "hinweis": ablehnung,
        })
        return befund
    except Exception as exc:  # noqa: BLE001
        return {"zulaessig": None, "ungeprueft": True, "klasse": "", "weg": "",
                "fehler": exc}


def _weg_flach(befund: dict[str, Any]) -> bool | None:
    """Flacher Gate-Wert: ``True`` meldet den **Mangel** (Muster ``sbom_version_fehlt``)."""
    zulaessig = befund.get("zulaessig")
    return None if zulaessig is None else (not zulaessig)


def _check_bewertungsweg(projekt_name: str, version: str,
                         befunde: dict[str, Any], punkte: list[dict[str, Any]]) -> None:
    """Art. 32 — der gewählte Weg muss für die Produktklasse zulässig sein (#1759)."""
    b = _weg_befund(projekt_name, str(version or ""))
    befunde["bewertungsweg"] = {"klasse": b.get("klasse"), "weg": b.get("weg"),
                                "zulaessig": b.get("zulaessig")}
    befunde["bewertungsweg_unzulaessig"] = _weg_flach(b)
    if b.get("ungeprueft"):
        punkte.append(_ungeprueft("bewertungsweg",
                                  "Bewertungsweg der Produktklasse ungeprüft",
                                  "konformitaet", b.get("fehler") or RuntimeError("?")))
    elif b.get("zulaessig") is False:
        punkte.append(_punkt("bewertungsweg", str(b.get("titel")), str(b.get("hinweis")),
                             "konformitaet", wirkung=_WIRKUNG_ROT,
                             ref=str(b.get("ref") or "Art. 32")))


def _check_advisories(projekt_name: str, version: str,
                      befunde: dict[str, Any], punkte: list[dict[str, Any]]) -> None:
    """Anhang I Teil II Nr. 8 — behobene Schwachstellen veröffentlichen.

    Rechenbar: welche ``cra_vuln`` tragen ``fixed_in_version = <Release>`` und haben
    keine ``advisory_url``? ``wontfix`` bleibt außen vor — dort wurde nichts behoben,
    also ist auch nichts zu veröffentlichen.
    """
    try:
        from cra.db import list_vuln
        ziel = _norm_version(version)
        ohne: list[str] = []
        behoben = 0
        for v in list_vuln(CRA_DB, projekt_name):
            if _norm_version(v.get("fixed_in_version")) != ziel:
                continue
            if str(v.get("status") or "") == "wontfix":
                continue
            behoben += 1
            if not str(v.get("advisory_url") or "").strip():
                ohne.append(str(v.get("cve_id") or f"#{v.get('id')}"))
        befunde["behobene_in_version"] = behoben
        befunde["behobene_ohne_advisory"] = ohne
        if ohne:
            gelistet = ", ".join(ohne[:5]) + (" …" if len(ohne) > 5 else "")
            punkte.append(_punkt(
                "advisory",
                f"{len(ohne)} in {version} behobene Schwachstelle(n) ohne Advisory",
                f"Advisory-URL je behobener Schwachstelle hinterlegen ({gelistet})",
                "pflichtdoku", ref="Annex I Part II (8)"))
    except Exception as exc:  # noqa: BLE001 — Nebenquelle darf das Gate nicht sprengen
        befunde["behobene_ohne_advisory"] = None
        punkte.append(_ungeprueft("advisory",
                                  "Advisories zu behobenen Schwachstellen ungeprüft",
                                  "pflichtdoku", exc))


def _check_sbom(projekt_name: str, version: str,
                befunde: dict[str, Any], punkte: list[dict[str, Any]]) -> None:
    """Anhang I Teil II Nr. 1 — SBOM zur Release-Version.

    ``cra_sbom.release_version`` existiert seit Anlage der Tabelle (Teil des
    UNIQUE-Keys), eine Schema-Ergänzung ist nicht nötig. Altbestand ohne
    Versionsangabe gilt als **nicht zuordenbar**: er belegt das Release nicht, ist
    aber auch kein Datenfehler — der Hinweis sagt das ausdrücklich, damit niemand
    eine vorhandene SBOM für verloren hält.
    """
    try:
        from cra.db import list_sbom
        ziel = _norm_version(version)
        treffer = ohne_version = 0
        for s in list_sbom(CRA_DB, projekt_name):
            rv = _norm_version(s.get("release_version"))
            if not rv:
                ohne_version += 1
            elif rv == ziel:
                treffer += 1
        befunde["sbom_version_fehlt"] = treffer == 0
        befunde["sbom_ohne_versionsbezug"] = ohne_version
        if treffer == 0:
            hinweis = f"SBOM für {version} hinterlegen"
            if ohne_version:
                hinweis += (f" — {ohne_version} vorhandene(r) SBOM-Eintrag/Einträge ohne "
                            "Versionsangabe sind diesem Release nicht zuordenbar")
            punkte.append(_punkt("sbom", f"Keine SBOM zur Release-Version {version}",
                                 hinweis, "pflichtdoku", ref="Annex I Part II (1)"))
    except Exception as exc:  # noqa: BLE001
        befunde["sbom_version_fehlt"] = None
        punkte.append(_ungeprueft("sbom", f"SBOM zur Version {version} ungeprüft",
                                  "pflichtdoku", exc))


def _check_support_zeitraum(projekt_name: str, version: str,
                            befunde: dict[str, Any], punkte: list[dict[str, Any]]) -> None:
    """Art. 13 Abs. 8 — der Support-Zeitraum muss das Release tragen.

    Gemessen wird gegen **heute**: bewertet wird, ob dieses Release *jetzt* als
    konform ausgewiesen werden darf. Ein Release nach EOL ist ``rot`` — der
    Hersteller verspricht Sicherheitsupdates, die er nicht mehr liefert.
    Fehlen Markteintritt/Support-Jahre, ist die Frage nicht entscheidbar: dann
    ``bedingt`` (Akte unvollständig), nicht ``rot`` (Pflichtverletzung).
    """
    try:
        from cra.db import load_support_period
        sp = load_support_period(CRA_DB, projekt_name) or {}
        eol_raw = str(sp.get("eol_datum") or "")[:10]
        kanal = str(sp.get("update_kanal") or "").strip()
        befunde["support"] = {
            "markteintritt": str(sp.get("markteintritt_datum") or "")[:10] or None,
            "support_jahre": sp.get("support_jahre"),
            "eol": eol_raw or None,
            "update_kanal": kanal,
        }
        # ``None`` = nicht entscheidbar. Ein ``False`` an dieser Stelle wäre die
        # Aussage „Support deckt das Release" — die darf nur fallen, wenn ein
        # lesbares Support-Ende vorliegt.
        befunde["support_ueberschritten"] = None
        if not eol_raw:
            punkte.append(_punkt(
                "support", "Support-Zeitraum nicht festgelegt",
                "Markteintritt und Support-Jahre erfassen — das Support-Ende (EOL) "
                "wird daraus berechnet",
                "pflichtdoku", ref="Art. 13(8)"))
        else:
            try:
                eol = date.fromisoformat(eol_raw)
            except ValueError:
                # Unlesbares Datum ist ein Datenmangel, kein erfüllter Prüfpunkt.
                punkte.append(_punkt(
                    "support", f"Support-Ende '{eol_raw}' ist kein gültiges Datum",
                    "Support-Ende als ISO-Datum (JJJJ-MM-TT) erfassen",
                    "pflichtdoku", ref="Art. 13(8)", ungeprueft=True))
            else:
                befunde["support_ueberschritten"] = eol < date.today()
                befunde["support"]["eol_ueberschritten"] = befunde["support_ueberschritten"]
                if eol < date.today():
                    punkte.append(_punkt(
                        "support",
                        f"Release {version} liegt nach dem Support-Ende ({eol.isoformat()})",
                        "Support-Zeitraum verlängern und begründen — oder dieses Release "
                        "nicht als CRA-konform ausweisen",
                        "pflichtdoku", wirkung=_WIRKUNG_ROT, ref="Art. 13(8)"))
        if not kanal:
            punkte.append(_punkt(
                "support", "Update-Kanal nicht dokumentiert",
                "Wie erreichen Sicherheitsupdates die Nutzer? (Art. 13 Abs. 8: Angabe "
                "zum Support-Zeitraum inkl. Bereitstellungsweg)",
                "pflichtdoku", ref="Art. 13(8)"))
    except Exception as exc:  # noqa: BLE001
        befunde["support"] = None
        befunde["support_ueberschritten"] = None
        punkte.append(_ungeprueft("support", "Support-Zeitraum ungeprüft",
                                  "pflichtdoku", exc))


def _check_meldefristen(projekt_name: str, version: str,
                        befunde: dict[str, Any], punkte: list[dict[str, Any]]) -> None:
    """Art. 14 — offene und überfällige Meldefristen.

    Ein Release während einer laufenden 24h/72h-Frist ist ein Signal (``bedingt``);
    eine **versäumte** Frist ist eine Pflichtverletzung (``rot``).

    Eine Stufe gilt als erledigt, wenn sie **oder eine spätere** Stufe gemeldet ist:
    ``set_stufe`` stempelt nur die erreichte Stufe, ein Sprung von „erkannt" direkt
    auf die 72h-Meldung lässt ``early_warning_gemeldet_am`` leer. Ohne diese Regel
    meldete das Gate eine Frist als versäumt, die der spätere Bericht abgedeckt hat.
    """
    try:
        import cra.deadlines as dl
        from cra import meldung_db as mdb
        ueberfaellig: list[dict[str, Any]] = []
        laufend: list[dict[str, Any]] = []
        unlesbar: list[str] = []
        for m in mdb.list_meldungen(CRA_DB, projekt_name):
            stage_set = ("cra_art14_incident"
                         if str(m.get("typ") or "") == "serious_incident" else "cra_art14")
            try:
                res = dl.evaluate(str(m.get("erkannt_am") or ""), stage_set)
            except Exception:  # noqa: BLE001 — je Meldung, nicht für alle
                unlesbar.append(str(m.get("titel") or m.get("id")))
                continue
            stages = res.get("stages", [])
            # Rückwärts laufen: sobald eine Stufe gemeldet ist, sind die früheren abgedeckt.
            abgedeckt = False
            for st in reversed(stages):
                if str(m.get(f"{st['key']}_gemeldet_am") or "").strip():
                    abgedeckt = True
                    continue
                if abgedeckt:
                    continue
                eintrag = {"meldung_id": m.get("id"), "titel": m.get("titel"),
                           "stufe": st.get("label"), "due_at": st.get("due_at")}
                (ueberfaellig if st.get("overdue") else laufend).append(eintrag)
        befunde["meldefristen"] = {"ueberfaellig": ueberfaellig, "laufend": laufend,
                                   "unlesbar": unlesbar}
        befunde["ueberfaellige_meldungen"] = ueberfaellig
        befunde["laufende_meldefristen"] = laufend
        if ueberfaellig:
            stufen = "; ".join(f"{e['titel'] or 'Meldung'} — {e['stufe']}"
                               for e in ueberfaellig[:5])
            punkte.append(_punkt(
                "meldefrist", f"{len(ueberfaellig)} überfällige Meldefrist(en)",
                f"Meldung an die zuständige Stelle nachholen und dokumentieren ({stufen})",
                "meldungen", wirkung=_WIRKUNG_ROT, ref="Art. 14"))
        if laufend:
            stufen = "; ".join(f"{e['titel'] or 'Meldung'} — {e['stufe']} bis {e['due_at']}"
                               for e in laufend[:5])
            punkte.append(_punkt(
                "meldefrist", f"{len(laufend)} laufende Meldefrist(en) zum Release-Zeitpunkt",
                f"Frist vor der Veröffentlichung bedienen ({stufen})",
                "meldungen", ref="Art. 14"))
        for titel in unlesbar:
            punkte.append(_punkt(
                "meldefrist", f"Meldefristen der Meldung '{titel}' ungeprüft",
                "Erkennungszeitpunkt (erkannt_am) ist nicht lesbar — Frist kann nicht "
                "berechnet werden",
                "meldungen", ungeprueft=True))
    except Exception as exc:  # noqa: BLE001
        befunde["meldefristen"] = None
        befunde["ueberfaellige_meldungen"] = None
        befunde["laufende_meldefristen"] = None
        punkte.append(_ungeprueft("meldefrist", "Meldefristen ungeprüft", "meldungen", exc))


def _check_vuln_handling(projekt_name: str, version: str,
                         befunde: dict[str, Any], punkte: list[dict[str, Any]]) -> None:
    """Anhang I Teil II — Schwachstellenbehandlung dokumentiert.

    Quelle ist ``cra_psirt`` (#1745 nennt die Tabelle ``cra_vuln_handling``; die
    genannten Felder ``disclosure_policy_url``/``psirt_contacts``/``security_md_url``
    liegen tatsächlich dort). Eine SECURITY.md zählt wie eine Disclosure-Policy —
    beide beantworten dieselbe Pflicht: Wohin melden Dritte eine Schwachstelle?
    """
    try:
        from cra.db import load_psirt
        p = load_psirt(CRA_DB, projekt_name) or {}
        policy = (str(p.get("disclosure_policy_url") or "").strip()
                  or str(p.get("security_md_url") or "").strip())
        kontakte = p.get("psirt_contacts") or []
        befunde["vuln_handling"] = {"policy_url": bool(policy),
                                    "psirt_kontakte": len(kontakte)}
        fehlt = []
        if not policy:
            fehlt.append("Disclosure-Policy- oder SECURITY.md-URL")
        if not kontakte:
            fehlt.append("PSIRT-Kontakt")
        if fehlt:
            punkte.append(_punkt(
                "vuln_handling", "Schwachstellenbehandlung nicht vollständig dokumentiert",
                "fehlt: " + ", ".join(fehlt),
                "pflichtdoku", ref="Annex I Part II"))
    except Exception as exc:  # noqa: BLE001
        befunde["vuln_handling"] = None
        punkte.append(_ungeprueft("vuln_handling", "Schwachstellenbehandlung ungeprüft",
                                  "pflichtdoku", exc))


# Reihenfolge = Reihenfolge im Panel. Jede Prüfung kapselt ihre Fehler selbst, damit
# ein Ausfall die folgenden Prüfungen nicht mitnimmt.
def _check_neubewertung(projekt_name: str, version: str,
                        befunde: dict[str, Any], punkte: list[dict[str, Any]]) -> None:
    """#1755 — Wesentliche Änderung (Art. 3 Nr. 31) zieht eine Neubewertung nach.

    Die vier Punkte wirken **rot**, nicht ``bedingt``: Eine wesentliche Änderung
    ohne wiederholte Konformitätsbewertung ist eine Nicht-Konformität und keine
    Lücke in der Akte. Das ist der einzige Ort in Phase 2, an dem ein offener
    Punkt das Release wirklich stoppt — und so soll es sein.

    Zusätzlich wird für die Risikoabschätzung **gerechnet**, ob in der
    verknüpften Risikobewertung seit Beginn des Vorgangs etwas passiert ist.
    Das ersetzt die Aussage des Menschen nicht (eine Änderung ohne neue Risiken
    ist möglich), aber es macht den Unterschied sichtbar zwischen „geprüft und
    nichts gefunden" und „niemand hat nachgesehen".
    """
    from cra import konformitaet_db as kdb
    from cra import release_checkliste as rc

    rec = kdb.get_konformitaet(CRA_DB, projekt_name, version) or {}
    wesentlich = str(rec.get("wesentliche_aenderung") or "")
    befunde["wesentliche_aenderung"] = wesentlich or None
    if wesentlich != "ja":
        # Ohne wesentliche Änderung gibt es nichts nachzubewerten. Die Frage
        # selbst ist ein `entscheidung`-Punkt und wird dort eingefordert.
        return

    stand = rec.get("release_checkliste") or {}
    offen = [i for i in rc.KATALOG if i.art == "neubewertung"
             and str((stand.get(i.id) or {}).get("status") or "offen") == "offen"]
    befunde["neubewertung_offen"] = [i.id for i in offen]
    for item in offen:
        punkte.append(_punkt(
            "neubewertung", f"Neubewertung offen: {item.label}",
            "wesentliche Änderung erklärt — diesen Punkt bearbeiten und begründen",
            item.link or "releases", wirkung=_WIRKUNG_ROT, ref=item.rechtsbezug))

    # Gerechneter Hinweis zur Risikoabschätzung.
    projekt = {}
    try:
        from cra.db import load_projekt
        projekt = load_projekt(CRA_DB, projekt_name) or {}
    except Exception as exc:  # noqa: BLE001
        punkte.append(_ungeprueft("neubewertung",
                                  "Verknüpfte Risikobewertung ungeprüft", "releases", exc))
        return
    meta = projekt.get("meta") if isinstance(projekt.get("meta"), dict) else {}
    rb_name = str((meta or {}).get("linked_risk_projekt") or "").strip()
    if not rb_name:
        befunde["rb_neue_risiken"] = None
        # Zwei verschiedene Lagen, und sie verdienen verschiedene Farben:
        #   • Der Punkt ist noch offen und es gibt keine Risikobewertung → der
        #     Neubewertung fehlt die Grundlage, auf die Art. 13 verweist: rot.
        #   • Jemand hat die Neubewertung ausdrücklich erklärt, nur ist keine
        #     Risikobewertung verknüpft → die Aussage steht, der Nachweis zeigt
        #     auf nichts. Das ist ein Nachweismangel, keine Nicht-Konformität:
        #     bedingt. Wer seine Risikoabschätzung außerhalb der Suite führt,
        #     wird sonst nie grün — und das Werkzeug hätte über die Arbeitsweise
        #     entschieden statt über die Konformität.
        risiko_offen = any(i.id == "neubewertung_risikobewertung" for i in offen)
        punkte.append(_punkt(
            "neubewertung", "Keine Risikobewertung verknüpft",
            ("Art. 13 verweist auf die Risikoabschätzung — ohne verknüpftes "
             "Projekt fehlt die Grundlage der Neubewertung")
            if risiko_offen else
            ("Neubewertung erklärt, aber keine Risikobewertung verknüpft — der "
             "Nachweis zeigt auf kein Projekt"),
            "releases",
            wirkung=_WIRKUNG_ROT if risiko_offen else _WIRKUNG_BEDINGT,
            ref="Art. 13 Abs. 1"))
        return

    seit = str(rec.get("created_at") or "")
    try:
        from risikobewertung.db import load_risiken
        neue = [r for r in load_risiken(RB_DB, rb_name)
                if str(r.get("updated_at") or r.get("created_at") or "") > seit]
        befunde["rb_neue_risiken"] = len(neue)
        befunde["rb_projekt"] = rb_name
    except Exception as exc:  # noqa: BLE001
        befunde["rb_neue_risiken"] = None
        punkte.append(_ungeprueft("neubewertung",
                                  "Verknüpfte Risikobewertung ungeprüft", "releases", exc))


def _check_ki_pruefung(projekt_name: str, version: str,
                       befunde: dict[str, Any], punkte: list[dict[str, Any]]) -> None:
    """#1765 — Steht hinter jeder KI-Bewertung ein Mensch?

    Seit v8.0.0 trägt der gespeicherte Text die Kennzeichnung nicht mehr; sie
    steht in ``shared/ki_herkunft``, zusammen mit der Angabe, wer sie geprüft
    hat. Damit ist die Frage erstmals **beantwortbar** — und sie gehört hierher:
    Eine EU-Konformitätserklärung ist die Aussage eines Herstellers, nicht die
    Ausgabe eines Modells.

    **Wirkung bedingt, nicht rot.** Zwei Gründe. Erstens trägt den Vorgang die
    Freigabe durch einen Menschen (Vier-Augen-Prinzip, #1743); die Aussage ist
    also nicht unbeaufsichtigt. Zweitens ist ein ungeprüfter Entwurf ein Mangel
    in der **Nachweiskette**, keine Eigenschaft des Produkts — rot ist für
    Nicht-Konformität reserviert.

    Was ungeprüft bleibt, wird dafür **nicht gedruckt**: Die Berichte für
    Kunden und die Konformitätsunterlagen lassen solche Inhalte weg
    (``cra/kundenfassung.py``, ``cra/konformitaet_report.py``). Beides
    zusammen ist die Regel: Das Release ist nicht blockiert, aber ein
    ungeprüfter Entwurf wird nirgends als geprüfte Aussage ausgegeben.
    """
    from shared import ki_herkunft

    offen: list[str] = []
    for art in ("requirement", "owasp"):
        for objekt_id, st in ki_herkunft.fuer_projekt("cra", projekt_name, art).items():
            if not st.get("geprueft"):
                offen.append(f"{art}:{objekt_id}")
    befunde["ki_ungeprueft"] = len(offen)
    befunde["ki_ungeprueft_ids"] = sorted(offen)[:20]
    if not offen:
        return
    punkte.append(_punkt(
        "ki_pruefung",
        f"{len(offen)} KI-Bewertung(en) fachlich nicht geprüft",
        "im Anforderungsregister je Eintrag „Fachlich geprüft“ bestätigen — "
        "ungeprüfte Entwürfe werden nicht in die Nachweise übernommen",
        "anforderungen", ref="AI Act Art. 14 (menschliche Aufsicht)"))


_RELEASE_CHECKS = (_check_bewertungsweg, _check_advisories, _check_sbom,
                   _check_support_zeitraum, _check_meldefristen,
                   _check_vuln_handling, _check_neubewertung, _check_ki_pruefung)


def _release_punkte(projekt_name: str, version: str) -> tuple[list[dict[str, Any]],
                                                              dict[str, Any]]:
    """Alle Release-Prüfungen laufen lassen → (offene Punkte, gerechnete Befunde)."""
    punkte: list[dict[str, Any]] = []
    befunde: dict[str, Any] = {}
    for check in _RELEASE_CHECKS:
        try:
            check(projekt_name, version, befunde, punkte)
        except Exception as exc:  # noqa: BLE001 — Netz unter dem Netz
            punkte.append(_ungeprueft(getattr(check, "__name__", "release"),
                                      f"Prüfung {getattr(check, '__name__', '?')} ungeprüft",
                                      "pflichtdoku", exc))
    return punkte, befunde


def evaluate(projekt_name: str, *, version: str | None = None) -> dict[str, Any]:
    """Bewertet die Konformität eines Projekts/Release. Best effort, nie Exception nach außen.

    Ohne ``version`` ist das Ergebnis die Phase-1-Bewertung des Bestands (#1612) —
    die Release-Prüfungen aus #1745 laufen dann nicht, ``release_punkte`` ist leer.
    """
    from cra.db import load_bewertungen, load_projekt, list_vuln
    from cra.requirements import CRA_ANFORDERUNGEN, berechne_reifegrad
    from cra.traceability_db import annex_vii_status

    projekt = load_projekt(CRA_DB, projekt_name) or {}
    meta = projekt.get("meta") if isinstance(projekt.get("meta"), dict) else {}
    rb_name = (meta.get("linked_risk_projekt") or "").strip()

    bewertungen_raw = load_bewertungen(CRA_DB, projekt_name)
    bewertungen = {rid: d.get("bewertung", 0) for rid, d in bewertungen_raw.items()}

    # akzeptierte Nichterfüllungs-Risiken je Quelle einsammeln
    risks_by_src: dict[str, list[dict]] = {}
    if rb_name:
        try:
            from risikobewertung.db import load_risiken
            for r in load_risiken(RB_DB, rb_name):
                fe = r.get("felder") or {}
                sid = str(fe.get("_source_id") or "")
                if sid:
                    risks_by_src.setdefault(sid, []).append(r)
        except Exception:  # noqa: BLE001
            pass

    erfuellt = begruendet = offen = 0
    offene_punkte: list[dict[str, Any]] = []
    abweichungen: list[dict[str, Any]] = []
    for req in CRA_ANFORDERUNGEN:
        rid = req["id"]
        bew = int(bewertungen.get(rid, 0) or 0)
        if bew >= _ERFUELLT_AB:
            erfuellt += 1
            continue
        acc = _accepted_gap_for(rb_name, rid, risks_by_src) if rb_name else None
        if acc:
            begruendet += 1
            abweichungen.append({"requirement_id": rid, "titel": req.get("titel"),
                                 "ref": req.get("ref"), "art": "begruendet",
                                 "kategorie": acc.get("akzeptanz_kategorie"),
                                 "grund": acc.get("akzeptanz_grund"),
                                 "von": acc.get("akzeptanz_von"),
                                 "rechtsgrundlage": acc.get("rechtsgrundlage")})
        else:
            offen += 1
            offene_punkte.append({"typ": "anforderung", "requirement_id": rid,
                                  "titel": req.get("titel"), "ref": req.get("ref"),
                                  "hinweis": "nicht erfüllt und nicht begründet akzeptiert",
                                  "link": "requirements"})
            abweichungen.append({"requirement_id": rid, "titel": req.get("titel"),
                                 "ref": req.get("ref"), "art": "offen"})

    # Schwachstellen
    offene_krit = 0
    vuln_ungeprueft = False
    try:
        for v in list_vuln(CRA_DB, projekt_name):
            if str(v.get("status") or "open") in ("open", "triaging") \
               and str(v.get("schwere") or "").lower() in ("critical", "high"):
                offene_krit += 1
    except Exception as e:  # noqa: BLE001
        # #1751: Hier stand ``pass``. Fiel die Abfrage aus, blieb ``offene_krit``
        # auf 0 und die Ampel wurde GRÜN, obwohl nichts geprüft worden war —
        # in einem Konformitäts-Gate der gefährlichste Fehler, weil er wie ein
        # gutes Ergebnis aussieht. Der Annex-VII-Block daneben fiel immer auf die
        # sichere Seite (``annex_ok`` blieb False); dieser nicht.
        vuln_ungeprueft = True
        offene_punkte.append({
            "typ": "schwachstelle",
            "titel": "Schwachstellen konnten nicht geprüft werden",
            "hinweis": f"Datenquelle prüfen ({type(e).__name__}: {e}) — "
                       f"ungeprüft ist nicht erfüllt",
            "link": "pflichtdoku", "ungeprueft": True})
    if offene_krit:
        offene_punkte.append({"typ": "schwachstelle", "titel": f"{offene_krit} offene kritische/hohe Schwachstelle(n)",
                              "hinweis": "beheben oder als Risiko akzeptieren", "link": "pflichtdoku"})

    # Annex VII
    annex_ok = False
    try:
        annex = annex_vii_status(CRA_DB, projekt_name)
        annex_ok = bool(annex.get("vollstaendig"))
        for b in annex.get("bausteine", []):
            if b.get("ampel") != "belegt":
                offene_punkte.append({"typ": "annex", "titel": f"Annex VII: {b.get('label')} fehlt",
                                      "hinweis": "Nachweis ergänzen", "link": "traceability"})
    except Exception:  # noqa: BLE001
        pass

    # DoC — formaler Konformitäts-Record ODER freigegebenes managed_doc (#1665)
    doc_ok = False
    try:
        from cra import konformitaet_db as kdb
        for k in kdb.list_konformitaet(CRA_DB, projekt_name):
            if version and str(k.get("release_version") or "") != str(version):
                continue
            if k.get("doc_ausgestellt") or k.get("freigabe_status") == "freigegeben":
                doc_ok = True
                break
    except Exception:  # noqa: BLE001
        pass
    if not doc_ok:
        # #1665: eine im Dokumente-Tab freigegebene EU-Konformitätserklärung zählt ebenfalls.
        try:
            from shared.documents.db import list_documents as _list_managed
            for d in _list_managed(CRA_DB, "cra", projekt_name):
                if str(d.get("doc_type")) == "konformitaetserklaerung" \
                   and str(d.get("status")) in ("freigegeben", "final"):
                    doc_ok = True
                    break
        except Exception:  # noqa: BLE001
            pass
    if not doc_ok:
        offene_punkte.append({"typ": "doc", "titel": "EU-Konformitätserklärung (DoC) nicht ausgestellt",
                              "hinweis": "DoC ausstellen/freigeben", "link": "konformitaet"})

    # #1759: Bewertungsweg gegen die Produktklasse — in der **Produktsicht** am
    # Datensatz ohne Version (das ist der Produkt-Datensatz, Phase 1). Der Punkt
    # trägt bewusst nur die Phase-1-Felder: ``phase``/``ampel_wirkung`` hängen
    # ausschließlich an Release-Punkten (Panel-Vertrag), die Wirkung läuft hier
    # über die Ampel-Flags.
    weg_befund = _weg_befund(projekt_name, "")
    weg_unzulaessig = weg_befund.get("zulaessig") is False
    weg_ungeprueft = bool(weg_befund.get("ungeprueft"))
    if weg_ungeprueft:
        offene_punkte.append({
            "typ": "bewertungsweg",
            "titel": "Bewertungsweg der Produktklasse ungeprüft",
            "hinweis": f"Datenquelle prüfen ({type(weg_befund.get('fehler')).__name__}: "
                       f"{weg_befund.get('fehler')}) — ungeprüft ist nicht erfüllt",
            "link": "konformitaet", "ungeprueft": True})
    elif weg_unzulaessig:
        offene_punkte.append({
            "typ": "bewertungsweg", "titel": str(weg_befund.get("titel")),
            "hinweis": str(weg_befund.get("hinweis")), "link": "konformitaet",
            "ref": str(weg_befund.get("ref") or "Art. 32")})

    reife = berechne_reifegrad(bewertungen)

    # ── Phase 2 (#1745): nur mit Version. Ohne Version bleibt alles wie bisher.
    produkt_punkte = list(offene_punkte)
    release_punkte: list[dict[str, Any]] = []
    release_befunde: dict[str, Any] = {}
    if version:
        release_punkte, release_befunde = _release_punkte(projekt_name, str(version))
    # ``offene_punkte`` bleibt die Vereinigung — Panel und ``release-check`` lesen sie
    # unverändert; wer die Phasen trennen will, nimmt produkt_punkte/release_punkte.
    alle_punkte = produkt_punkte + release_punkte

    # Ampel
    if offen == 0 and offene_krit == 0 and not vuln_ungeprueft \
            and not weg_ungeprueft and annex_ok and doc_ok:
        ampel = "gruen"
    elif offen == 0 and offene_krit == 0:
        ampel = "bedingt"   # inhaltlich konform, aber Akte/DoC noch unvollständig
    else:
        ampel = "rot"
    # #1759: Ein unzulässiger Bewertungsweg ist eine Nicht-Konformität, nicht ein
    # Nachweismangel — er sticht die obige Einstufung durch. Steht er allein,
    # wäre die Ampel sonst „bedingt": alle Anforderungen erfüllt, Akte
    # vollständig, DoC ausgestellt — und das Verfahren dahinter unzulässig.
    if weg_unzulaessig:
        ampel = "rot"

    # Release-Punkte können die Ampel nur verschärfen, nie entschärfen.
    if any(p.get("ampel_wirkung") == _WIRKUNG_ROT for p in release_punkte):
        ampel = "rot"
    elif release_punkte and ampel == "gruen":
        ampel = "bedingt"

    konform = ampel == "gruen"
    return {
        "projekt_name": projekt_name,
        "version": version,
        "phase": "release" if version else "produkt",
        "ampel": ampel,
        "konform": konform,
        "erfuellt": erfuellt,
        "begruendet_akzeptiert": begruendet,
        "offen": offen,
        "gesamt_anforderungen": len(CRA_ANFORDERUNGEN),
        "offene_kritische_schwachstellen": offene_krit,
        "annex_vollstaendig": annex_ok,
        "doc_ausgestellt": doc_ok,
        "reifegrad_pct": reife.get("gesamt_pct"),
        "offene_punkte": alle_punkte,
        "produkt_punkte": produkt_punkte,
        "release_punkte": release_punkte,
        "release_befunde": release_befunde,
        # Gerechnete Release-Befunde flach — unter genau den Namen, die der
        # Release-Katalog (#1744) als ``quelle`` seiner gerechneten Punkte nennt,
        # passend zu den vorhandenen flachen Befunden (``annex_vollstaendig`` …).
        # Die Werte sind **Kopien** aus ``release_befunde``, kein zweiter Rechenweg;
        # ``None`` heißt „nicht geprüft" — in Phase 1 (nicht Teil der Produktsicht)
        # genauso wie nach einem Ausfall der Datenquelle.
        "behobene_ohne_advisory": release_befunde.get("behobene_ohne_advisory"),
        "sbom_version_fehlt": release_befunde.get("sbom_version_fehlt"),
        "support_ueberschritten": release_befunde.get("support_ueberschritten"),
        "ueberfaellige_meldungen": release_befunde.get("ueberfaellige_meldungen"),
        # #1759: Der einzige flache Befund, der auch in Phase 1 einen Wert hat —
        # die Frage „zulässiger Weg für diese Klasse?" stellt sich am Produkt
        # genauso wie am Release. In Phase 2 gilt der Vorgang dieser Version;
        # hat er keinen eigenen Weg (kein Record zur Version), fällt der Wert
        # auf die Produktsicht zurück, statt als „nicht geprüft" zu erscheinen,
        # obwohl geprüft wurde.
        "bewertungsweg_unzulaessig": (
            release_befunde.get("bewertungsweg_unzulaessig")
            if release_befunde.get("bewertungsweg_unzulaessig") is not None
            else _weg_flach(weg_befund)),
        "abweichungen": abweichungen,
    }
