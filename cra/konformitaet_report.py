"""Kundenfähiger CRA-Konformitätsnachweis je Release (#1610/#1613).

Erzeugt einen versionsgebundenen Nachweis (DOCX/PDF, A4, vektoriell) mit sichtbarer
Rechtsgrundlage: Erfüllungsgrad je Anforderung (Artikel-/Annex-Referenz), begründete
Abweichungen inkl. akzeptiertem Risiko, Annex-VII-Vollständigkeit, Schwachstellen-Status,
EU-Konformitätserklärung/CE und das Konformitäts-Gate-Fazit.

**Die Sprache gehört dem Mandanten (#1954).** Dieses Dokument wird der
Marktüberwachungsbehörde auf Verlangen vorgelegt und vom Kunden weitergegeben;
über seine Sprache entscheidet deshalb ``firmen.sprache`` und nicht der
Bearbeiter, der es zufällig erzeugt (aufgelöst in :func:`daten` über
``shared.reports.texte.aufloesen``, fail-open auf Deutsch).

Zwei Dinge bleiben dabei unberührt:

* **Die Fundstellen je Anforderung.** Sie kommen aus :mod:`cra.requirements`
  (``ref`` und ``KAPITEL[...]['referenz']``) und werden hier nur
  durchgereicht. Eine Fundstelle in einer Nachweisakte liest sich wie eine
  Feststellung — sie wird nicht nebenbei übersetzt (Lehre aus #1763/#1792,
  Gegenstand von #1913).
* :data:`PFLICHT_VORLAGEN` — das sind **Variablenpfade** (``nachweis.version``)
  und Prüfmaßstab für hochgeladene Word-Vorlagen, keine Anzeigetexte.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document
from docx.shared import Pt, RGBColor

from shared.reports import texte as _rt

CRA_DB = Path("data/db/cra.sqlite")

_EU_BLUE = RGBColor(0x00, 0x33, 0x99)
_REGULATION = "Verordnung (EU) 2024/2847 (Cyber Resilience Act)"
_VERFAHREN = {"A": "Modul A — interne Kontrolle (Selbstbewertung), Anhang VIII",
              "B+C": "Modul B+C — EU-Baumusterprüfung, Anhang VIII",
              "H": "Modul H — umfassende Qualitätssicherung, Annex VIII",
              "EUCC": "EUCC-Zertifizierung"}
_AMPEL = {"gruen": "KONFORM", "bedingt": "BEDINGT KONFORM", "rot": "NICHT KONFORM"}
_STATUS_LABEL = {"erfuellt": "erfüllt", "begruendet": "Abweichung begründet akzeptiert",
                 "offen": "offen (nicht konform)"}

#: Die drei Zuordnungen oben auf Englisch (#1954).
#:
#: **Eigene Tabellen und nicht ein Eintrag im Katalog je Wert**: Die Schlüssel
#: (``gruen``, ``erfuellt``, ``B+C``) sind **Datenwerte** — sie kommen aus dem
#: Gate bzw. aus ``cra_konformitaet.bewertungsweg`` und bleiben unverändert.
#: Übersetzt wird allein ihre Beschriftung; ein fehlender Eintrag fällt auf die
#: deutsche zurück, statt die Zelle leer zu lassen.
#:
#: Die Modul-Bezeichnungen folgen den amtlichen Teil-Überschriften von
#: Anhang VIII: Teil I „internal control (based on Module A)", Teil II
#: „EU-type examination (based on Module B)", Teil IV „full quality assurance
#: (based on Module H)".
_VERFAHREN_EN = {"A": "Module A — internal control (self-assessment), Annex VIII",
                 "B+C": "Module B+C — EU-type examination, Annex VIII",
                 "H": "Module H — full quality assurance, Annex VIII",
                 "EUCC": "EUCC certification"}
_AMPEL_EN = {"gruen": "IN CONFORMITY", "bedingt": "CONDITIONALLY IN CONFORMITY",
             "rot": "NOT IN CONFORMITY"}
_STATUS_LABEL_EN = {"erfuellt": "fulfilled",
                    "begruendet": "deviation accepted with justification",
                    "offen": "open (not in conformity)"}


def _verfahren(weg: str, sprache: str) -> str:
    tab = _VERFAHREN_EN if sprache == "en" else _VERFAHREN
    return tab.get(weg) or _VERFAHREN.get(weg, weg)


def _ampel_label(ampel: Any, sprache: str) -> str:
    tab = _AMPEL_EN if sprache == "en" else _AMPEL
    return tab.get(ampel) or _AMPEL.get(ampel, str(ampel or ""))


def _status_label(status: str, sprache: str) -> str:
    tab = _STATUS_LABEL_EN if sprache == "en" else _STATUS_LABEL
    return tab.get(status) or _STATUS_LABEL[status]


def _ce_text(konf: dict | None, sprache: str = "de") -> str:
    """CE-Kennzeichnungs-Status für den Nachweis (#1671)."""
    k = konf or {}
    if k.get("ce_status") == "ce_angebracht" or k.get("ce_angebracht_am"):
        am = str(k.get("ce_angebracht_am") or "")[:10]
        ort = k.get("ce_ort") or ""
        teile = [_t(sprache, "ce_angebracht")]
        if am:
            teile.append(_t(sprache, "ce_am", am=am))
        if ort:
            teile.append(_t(sprache, "ce_ort", ort=ort))
        return " ".join(teile)
    if k.get("doc_ausgestellt"):
        return _t(sprache, "ce_doc_offen")
    return _t(sprache, "ce_offen")


def _h(doc, text, size=13, color=None, space_before=10):
    p = doc.add_paragraph()
    r = p.add_run(text); r.bold = True; r.font.size = Pt(size)
    if color:
        r.font.color.rgb = color
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(4)
    return p


def _p(doc, text, size=10):
    p = doc.add_paragraph()
    r = p.add_run(text); r.font.size = Pt(size)
    return p


#: Was eine Word-Vorlage des Nachweises mindestens benutzen muss (#1777).
#:
#: Gelesen von ``shared.templates.validate`` (guarded import, Muster
#: ``cra/doc_export.PFLICHT_VORLAGEN``). Die Liste ist **kurz und bewusst
#: nicht nummeriert**: Der Nachweis ist kein Formular aus einem Anhang, sein
#: Aufbau gehört uns. Was nicht uns gehört, ist sein Zweck — und daraus folgen
#: genau drei Angaben: Ohne Produkt und Release belegt er nichts Bestimmtes,
#: ohne Rechtsgrundlage ist er ein Produktblatt, und ohne Gesamturteil trifft
#: er keine Aussage. Eine Vorlage, die eine davon weglässt, erzeugt ein
#: Dokument, das wie ein Nachweis aussieht und keiner ist. Eine längere Liste
#: wäre eine erfundene Rechtspflicht — in einer Nachweisakte schlechter als
#: keine.
PFLICHT_VORLAGEN: list[dict[str, Any]] = [{
    "dokument": "Konformitätsnachweis",
    "rechtsgrundlage": "Verordnung (EU) 2024/2847, Art. 13 i.V.m. Anhang I und VII",
    "erkennung": "nachweis",
    "angaben": [
        {"bezeichnung": "Produkt und Release, auf das sich der Nachweis bezieht",
         "tokens": ["nachweis.produkt", "nachweis.version"]},
        {"bezeichnung": "Rechtsgrundlage",
         "tokens": ["nachweis.rechtsgrundlage"],
         "textbeleg": "2024/2847"},
        {"bezeichnung": "Gesamturteil (Konformitäts-Gate)",
         "tokens": ["nachweis.ampel_label"],
         "alternativen": ["nachweis.ampel", "nachweis.konform"]},
    ],
}]


HINWEIS_TEXT = (
    "Dieser Nachweis dokumentiert den Stand zum angegebenen Datum/Release. "
    "Begründete Abweichungen beruhen auf dem risikobasierten Ansatz des CRA; "
    "offene Nicht-Konformitäten sind vor der CE-Kennzeichnung zu schließen.")


#: Die Prosa des Nachweises je Sprache (#1954).
#:
#: ``hinweis`` referenziert :data:`HINWEIS_TEXT` statt ihn abzuschreiben — der
#: Text steht auch im Vorlagen-Kontext (``nachweis.hinweis``), und zwei
#: Fassungen desselben Satzes wären die Spiegel-Liste aus #1731/#1735.
#:
#: **Nummern und Fundstellen bleiben**, nur die Bezeichnung der Anlage wird
#: übersetzt: „Anhang I Teil II Nr. 3" → „Annex I Part II No. 3" bezeichnet
#: dieselbe Stelle derselben Verordnung. Die englischen Begriffe folgen dem
#: Verordnungstext: „essential cybersecurity requirements" (Art. 13 Abs. 1,
#: Anhang I), „conformity assessment procedure" (Art. 32), „market
#: surveillance authority" (Art. 52).
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        "hinweis": HINWEIS_TEXT,
        "regulation": _REGULATION,

        "ce_angebracht": "angebracht",
        "ce_am": "am {am}",
        "ce_ort": "({ort})",
        "ce_doc_offen": "DoC ausgestellt — CE anzubringen",
        "ce_offen": "noch nicht angebracht",
        "art_label_leer": "nicht festgelegt",
        "req_hinweis_offen": "nicht erfüllt / nicht begründet",
        "abweichung_hinweis": "{kategorie}: {grund}",

        "titel": "EU-Konformitätsnachweis (Cyber Resilience Act)",
        "k_hersteller": "Hersteller",
        "k_produkt": "Produkt",
        "k_version": "Version / Release",
        "k_produktklasse": "Produktklasse",
        "k_verfahren": "Konformitätsbewertungsverfahren",
        "k_rechtsgrundlage": "Rechtsgrundlage",
        "k_ce": "CE-Kennzeichnung",
        "k_datum": "Datum",
        # Zwei Striche, und das bleibt so: Die Kopftabelle und die
        # Testangaben führen seit #1610 den Halbgeviertstrich, die
        # Abweichungs- und Restrisiko-Zeilen den Geviertstrich. Beide sind in
        # jeder Sprache gleich — einer von ihnen wegzulassen hätte das
        # deutsche Dokument verändert.
        "leer": "–",
        "leer_em": "—",

        "h_gesamturteil": "Gesamturteil (Konformitäts-Gate)",
        "urteil": ("Ergebnis: {ampel}  ·  Reifegrad {pct} %  ·  "
                   "erfüllt {erfuellt}, begründet akzeptiert {begruendet}, "
                   "offen {offen} von {gesamt} Anforderungen."),
        "urteil_annex": ("Annex VII vollständig: {annex}  ·  "
                         "EU-Konformitätserklärung ausgestellt: {doc}  ·  "
                         "offene kritische/hohe Schwachstellen: {vuln}."),
        "ja": "ja",
        "nein": "nein",

        "h_anforderungen": ("Erfüllung der essenziellen Anforderungen "
                            "(Annex I) — mit Rechtsgrundlage"),
        "t_anforderung": "Anforderung",
        "t_rechtsgrundlage": "Rechtsgrundlage",
        "t_status": "Status",
        "t_hinweis": "Hinweis",
        "req_zeile": "{id} — {titel}",

        "h_abweichungen": "Begründete Abweichungen (als Risiko akzeptiert)",
        "abweichungen_keine": "Keine — alle anwendbaren Anforderungen sind erfüllt.",
        "abweichung_zeile": "• {id} — {titel}",
        "abweichung_meta": ("   Kategorie: {kategorie} · akzeptiert von: {von} · "
                            "Rechtsgrundlage: {rechtsgrundlage}"),
        "abweichung_grund": "   Begründung: {grund}",

        "h_nicht_konform": ("Offene Nicht-Konformitäten "
                            "(Korrekturmaßnahmen erforderlich)"),
        "nicht_konform_zeile": "• {id} — {titel} ({ref})",

        "h_tests": "Sicherheitstests (Anhang I Teil II Nr. 3)",
        "tests_zeile": ("Art des Nachweises: {art}  ·  "
                        "Nachweise in der Akte: {anzahl}  ·  "
                        "jüngster Nachweis: {juengster}"),
        "tests_verzicht": ("Der Hersteller verzichtet bewusst auf eigene "
                           "Sicherheitstests. Erklärt von {von} am {am}; "
                           "Wiedervorlage {review}."),
        "tests_begruendung": "Begründung: {grund}",
        "tests_feststellung": "• {text}",
        "tests_belegt": ("Keine Feststellungen — die vorliegenden Testnachweise "
                         "belegen den ausgelieferten Produktstand."),

        "h_annex": "Technische Dokumentation (Annex VII)",
        "annex_fehlt": "Annex-VII-Status nicht verfügbar.",
        "annex_zeile": "{mark} {label} ({anzahl} Nachweis(e))",

        "h_restrisiken": "Akzeptierte Restrisiken (Risikobewertung)",
        "restrisiken_keine": "Keine formal akzeptierten Restrisiken.",
        "restrisiko_zeile": "• #{nr} {name}",

        "h_hinweis": "Hinweis",
    },
    "en": {
        "hinweis": (
            "This record documents the status as at the date/release stated "
            "above. Justified deviations rest on the risk-based approach of "
            "the CRA; open non-conformities must be closed before the CE "
            "marking is affixed."),
        "regulation": "Regulation (EU) 2024/2847 (Cyber Resilience Act)",

        "ce_angebracht": "affixed",
        "ce_am": "on {am}",
        "ce_ort": "({ort})",
        "ce_doc_offen": ("EU declaration of conformity issued — CE marking to "
                         "be affixed"),
        "ce_offen": "not yet affixed",
        # Wortgleich mit ``cra.sicherheitstests.ART_LABEL_EN[""]``: Derselbe
        # Zustand darf im Nachweis nicht zwei Namen haben, je nachdem ob
        # ``befund`` geantwortet hat oder ausgefallen ist.
        "art_label_leer": "not specified",
        "req_hinweis_offen": "not fulfilled / not justified",
        "abweichung_hinweis": "{kategorie}: {grund}",

        "titel": "EU record of conformity (Cyber Resilience Act)",
        "k_hersteller": "Manufacturer",
        "k_produkt": "Product",
        "k_version": "Version / release",
        "k_produktklasse": "Product class",
        "k_verfahren": "Conformity assessment procedure",
        "k_rechtsgrundlage": "Legal basis",
        "k_ce": "CE marking",
        "k_datum": "Date",
        "leer": "–",
        "leer_em": "—",

        "h_gesamturteil": "Overall assessment (conformity gate)",
        "urteil": ("Result: {ampel}  ·  maturity {pct} %  ·  "
                   "fulfilled {erfuellt}, accepted with justification "
                   "{begruendet}, open {offen} of {gesamt} requirements."),
        "urteil_annex": ("Annex VII complete: {annex}  ·  "
                         "EU declaration of conformity issued: {doc}  ·  "
                         "open critical/high vulnerabilities: {vuln}."),
        "ja": "yes",
        "nein": "no",

        # Amtlich englisch: „essential cybersecurity requirements" (Anhang I).
        "h_anforderungen": ("Fulfilment of the essential cybersecurity "
                            "requirements (Annex I) — with legal basis"),
        "t_anforderung": "Requirement",
        "t_rechtsgrundlage": "Legal basis",
        "t_status": "Status",
        "t_hinweis": "Note",
        "req_zeile": "{id} — {titel}",

        "h_abweichungen": "Justified deviations (accepted as a risk)",
        "abweichungen_keine": ("None — all applicable requirements are "
                               "fulfilled."),
        "abweichung_zeile": "• {id} — {titel}",
        "abweichung_meta": ("   Category: {kategorie} · accepted by: {von} · "
                            "legal basis: {rechtsgrundlage}"),
        "abweichung_grund": "   Justification: {grund}",

        "h_nicht_konform": "Open non-conformities (corrective action required)",
        "nicht_konform_zeile": "• {id} — {titel} ({ref})",

        "h_tests": "Security testing (Annex I Part II No. 3)",
        "tests_zeile": ("Type of evidence: {art}  ·  "
                        "items of evidence in the file: {anzahl}  ·  "
                        "most recent evidence: {juengster}"),
        "tests_verzicht": ("The manufacturer deliberately refrains from "
                           "carrying out its own security tests. Declared by "
                           "{von} on {am}; review due {review}."),
        "tests_begruendung": "Justification: {grund}",
        "tests_feststellung": "• {text}",
        "tests_belegt": ("No findings — the available test evidence covers the "
                         "version of the product that was placed on the "
                         "market."),

        "h_annex": "Technical documentation (Annex VII)",
        "annex_fehlt": "Annex VII status not available.",
        "annex_zeile": "{mark} {label} ({anzahl} item(s) of evidence)",

        "h_restrisiken": "Accepted residual risks (risk assessment)",
        "restrisiken_keine": "No formally accepted residual risks.",
        "restrisiko_zeile": "• #{nr} {name}",

        "h_hinweis": "Note",
    },
}

_t = _rt.macher(TEXTE)


# ── #1954: Katalogeinträge in der Sprache des Dokuments ──────────────────────
# Die Literale werden hier direkt gelesen; ohne diesen Helfer käme die
# englische Fassung (`titel_en`, `label_en`, `referenz_en`) nie an — die
# Übersetzung wäre vorhanden und wirkungslos (der Defekt aus #1735).
# `uebersetze` liefert **Kopien**: Das Modul-Literal wird von mehreren
# Anfragen gleichzeitig gelesen.
def _kat(eintrag: dict, sp: str) -> dict:
    from shared.katalog_sprache import uebersetze

    return uebersetze(eintrag or {}, sp)


def daten(projekt_name: str, *, version: str | None = None,
          db_path: Path = CRA_DB, sprache: str | None = None) -> dict[str, Any]:
    """Alle Angaben des Nachweises — **eine** Erhebung für beide Wege (#1777).

    Der Nachweis entsteht seit #1610 programmatisch; seit #1777 kann ihn auch
    eine hochgeladene Word-Vorlage erzeugen. Beide müssen dieselben Zahlen
    nennen, sonst gibt es zwei Konformitätsaussagen zum selben Release — und die
    Abweichung fällt erst auf, wenn jemand die Dokumente nebeneinander legt.
    Deshalb erhebt diese Funktion, und :func:`build_docx` setzt nur noch.

    ``evaluate`` rechnet bewusst gegen die Produktiv-Datenbank des Moduls (sie
    liest ein Dutzend Register); ``db_path`` gilt für die Stammdaten.

    Die Sprache löst **diese** Funktion auf (#1954) und nicht der Aufrufer: Sie
    ist die eine Erhebung, aus der beide Wege schöpfen — der programmatische
    Renderer und die Word-Vorlage über :func:`kontext`. Würde jeder Weg sie
    selbst bestimmen, hätte derselbe Nachweis je Weg eine andere Sprache.
    """
    from cra.db import load_bewertungen, load_projekt
    from cra.requirements import (CRA_ANFORDERUNGEN, KAPITEL, PRODUKTKLASSEN,
                                  klasse_label)
    from cra.konformitaet_gate import evaluate
    from cra import konformitaet_db as kdb

    sp = _rt.aufloesen("cra", projekt_name, sprache)
    projekt = load_projekt(db_path, projekt_name) or {}
    gate = evaluate(projekt_name, version=version)
    bew_raw = load_bewertungen(db_path, projekt_name)
    bew = {rid: d.get("bewertung", 0) for rid, d in bew_raw.items()}

    # Konformitätsbewertungsverfahren + Produktklasse
    konf = None
    try:
        for k in kdb.list_konformitaet(db_path, projekt_name):
            if not version or str(k.get("release_version") or "") == str(version):
                konf = k
                break
    except Exception:  # noqa: BLE001
        konf = None
    pklasse = (konf or {}).get("produktklasse") or projekt.get("produktklasse") or "default"
    pk_info = _kat(PRODUKTKLASSEN.get(
        pklasse, PRODUKTKLASSEN.get("default", {})), sp)
    weg = (konf or {}).get("bewertungsweg") or "A"

    abw_by_id = {a["requirement_id"]: a for a in gate.get("abweichungen", [])}
    anforderungen: list[dict[str, Any]] = []
    for req in (_kat(r, sp) for r in CRA_ANFORDERUNGEN):
        rid = req["id"]
        b = int(bew.get(rid, 0) or 0)
        if b >= 4:
            status, hinweis = "erfuellt", ""
        elif rid in abw_by_id and abw_by_id[rid]["art"] == "begruendet":
            status = "begruendet"
            a = abw_by_id[rid]
            hinweis = _t(sp, "abweichung_hinweis", kategorie=a.get('kategorie'),
                         grund=a.get('grund') or '').strip(": ")
        else:
            status, hinweis = "offen", _t(sp, "req_hinweis_offen")
        kref = _kat(KAPITEL.get(req.get("kapitel"), {}),
                    sp).get("referenz", "")
        anforderungen.append({
            "id": rid,
            # Titel und Fundstelle kommen aus `cra/requirements.py` und werden
            # nur durchgereicht — siehe Modul-Docstring (#1913).
            "titel": str(req.get("titel") or ""),
            "rechtsgrundlage": f"{req.get('ref', '')} · {kref}".strip(" ·"),
            "status": status,
            "status_label": _status_label(status, sp),
            "hinweis": hinweis,
            "bewertung": b,
        })

    annex_vii: list[dict[str, Any]] = []
    annex_verfuegbar = True
    try:
        from cra.traceability_db import annex_vii_status
        for b in annex_vii_status(db_path, projekt_name).get("bausteine", []):
            annex_vii.append({"label": str(b.get("label") or ""),
                              "belegt": b.get("ampel") == "belegt",
                              "nachweis_count": int(b.get("nachweis_count", 0) or 0)})
    except Exception:  # noqa: BLE001 — Teilangabe darf den Nachweis nicht verhindern
        annex_verfuegbar = False

    return {
        "projekt_name": projekt_name,
        "sprache": sp,
        "sicherheitstests": _sicherheitstests(db_path, projekt_name, version,
                                              sprache=sp),
        "version": str(version or (konf or {}).get("release_version") or ""),
        "hersteller": str(projekt.get("unternehmen") or ""),
        "produkt": str(projekt.get("produkt") or projekt_name),
        "produktklasse": str(pklasse),
        # #1954: Auf Deutsch bleibt es bei ``PRODUKTKLASSEN[...]['label']`` —
        # ``klasse_label`` liefert das **kurzlabel** und hätte den deutschen
        # Nachweis verändert. Englisch gibt es nur dort (``KLASSE_LABEL_EN``);
        # die **Fundstelle** darunter bleibt deutsch, weil sie aus
        # ``cra/requirements.py`` kommt (siehe Modul-Docstring).
        "produktklasse_label": (klasse_label(pklasse, sprache=sp) if sp == "en"
                                else str(pk_info.get("label") or pklasse)),
        "produktklasse_referenz": str(pk_info.get("referenz") or ""),
        "bewertungsweg": str(weg),
        "bewertungsweg_label": _verfahren(weg, sp),
        "rechtsgrundlage": _t(sp, "regulation"),
        "ce_kennzeichnung": _ce_text(konf, sp),
        "datum": date.today().isoformat(),
        "ampel": str(gate.get("ampel") or ""),
        "ampel_label": _ampel_label(gate.get("ampel"), sp),
        "konform": bool(gate.get("konform")),
        "reifegrad_pct": gate.get("reifegrad_pct"),
        "erfuellt": int(gate.get("erfuellt") or 0),
        "begruendet_akzeptiert": int(gate.get("begruendet_akzeptiert") or 0),
        "offen": int(gate.get("offen") or 0),
        "gesamt_anforderungen": int(gate.get("gesamt_anforderungen") or 0),
        "annex_vollstaendig": bool(gate.get("annex_vollstaendig")),
        "doc_ausgestellt": bool(gate.get("doc_ausgestellt")),
        "offene_kritische_schwachstellen": int(
            gate.get("offene_kritische_schwachstellen") or 0),
        "anforderungen": anforderungen,
        "abweichungen_begruendet": [a for a in gate.get("abweichungen", [])
                                    if a.get("art") == "begruendet"],
        "nicht_konformitaeten": [a for a in gate.get("abweichungen", [])
                                 if a.get("art") == "offen"],
        "annex_vii": annex_vii,
        "annex_vii_verfuegbar": annex_verfuegbar,
        "akzeptierte_restrisiken": _akzeptierte_restrisiken(projekt),
        "hinweis": _t(sp, "hinweis"),
    }


#: Leerstand der Testangaben. Ein Nachweis ohne diesen Block wäre eine Vorlage,
#: die an einer Teilangabe scheitert (``kontext`` darf kein ``None`` liefern).
_TEST_LEER: dict[str, Any] = {
    "art": "", "art_label": "nicht festgelegt", "nachweis_count": 0,
    "juengster": "", "verzicht_erklaert": False, "verzicht_begruendung": "",
    "verzicht_von": "", "verzicht_am": "", "verzicht_review": "",
    "belegt": False, "feststellungen": [],
}


def _test_leer(sprache: str = "de") -> dict[str, Any]:
    """:data:`_TEST_LEER` in der Sprache des Dokuments (#1954).

    Nur ``art_label`` ist ein Anzeigetext; ``art`` ist ein **Datenwert** und
    bleibt leer. „not determined" statt „nicht festgelegt" ist hier keine
    Kosmetik: Die Zeile sagt dem Leser, dass zur Testart nichts feststeht —
    eine Lücke, die er in seiner Sprache lesen muss.
    """
    leer = dict(_TEST_LEER)
    leer["art_label"] = _t(sprache, "art_label_leer")
    return leer


def _sicherheitstests(db_path: Path, projekt_name: str,
                      version: str | None, *,
                      sprache: str = "de") -> dict[str, Any]:
    """Anhang I Teil II Nr. 3 für den Nachweis (#1824).

    **Dieselbe Funktion wie das Gate** (``cra.sicherheitstests.befund``) — der
    Nachweis rechnet nicht selbst. Zwei Rechenwege für eine Konformitätsaussage
    wären zwei Wahrheiten, und die Abweichung fiele erst auf, wenn jemand Gate
    und Dokument nebeneinanderlegt (#1726/#1727/#1776).

    **Ein erklärter Verzicht wird gedruckt.** Ein Nachweis, der verschweigt,
    dass der Hersteller auf eigene Sicherheitstests verzichtet, ist gegenüber
    dem Empfänger irreführend — und genau dieses Dokument reicht der Kunde
    weiter.
    """
    try:
        from cra import sicherheitstests as st

        b = st.befund(Path(db_path), projekt_name, str(version or ""))
    except Exception:  # noqa: BLE001 — Teilangabe darf den Nachweis nicht kippen
        return _test_leer(sprache)
    v = b.get("verzicht") or {}
    return {
        "art": b.get("art") or "",
        # #1954: `befund` liefert die deutsche Bezeichnung mit; sie wird hier
        # in der Sprache des Dokuments neu aufgelöst (wie in
        # `cra/kundenfassung.py`).
        "art_label": (st.art_label(str(b.get("art") or ""), sprache=sprache)
                      or _t(sprache, "art_label_leer")),
        "nachweis_count": int(b.get("nachweis_count") or 0),
        "juengster": b.get("juengster") or "",
        "verzicht_erklaert": bool(v.get("erklaert")),
        "verzicht_begruendung": str(v.get("begruendung") or ""),
        "verzicht_von": str(v.get("von") or ""),
        "verzicht_am": str(v.get("am") or ""),
        "verzicht_review": str(v.get("review") or ""),
        "belegt": not b.get("maengel"),
        "feststellungen": [{"text": m.get("text") or "",
                            "hinweis": m.get("hinweis") or ""}
                           for m in (b.get("maengel") or [])],
    }


def _akzeptierte_restrisiken(projekt: dict[str, Any]) -> list[dict[str, Any]]:
    """Formal akzeptierte Restrisiken der verknüpften Risikobewertung (#1674).

    Auch nicht-anforderungsbezogene Risiken sind hier nachgewiesen — eine
    Akzeptanz ohne Bezug zu einer Annex-I-Anforderung bleibt eine Entscheidung
    über das Produkt.
    """
    meta = projekt.get("meta") if isinstance(projekt.get("meta"), dict) else {}
    rb_name = str((meta or {}).get("linked_risk_projekt") or "").strip()
    if not rb_name:
        return []
    try:
        from risikobewertung.db import load_risiken
        rows = load_risiken(Path("data/db/risikobewertung.sqlite"), rb_name)
    except Exception:  # noqa: BLE001
        return []
    return [{"nr": r.get("nr"), "name": str(r.get("risk_name") or ""),
             "kategorie": str(r.get("akzeptanz_kategorie") or ""),
             "von": str(r.get("akzeptanz_von") or ""),
             "rechtsgrundlage": str(r.get("rechtsgrundlage") or ""),
             "grund": str(r.get("akzeptanz_grund") or "")}
            for r in rows if (r.get("behandlung") or "") == "akzeptiert"]


def kontext(db_path: Path | str, projekt_name: str,
            version: str | None = None, *,
            sprache: str | None = None) -> dict[str, Any]:
    """``nachweis``-Teilbaum für den CRA-Vorlagen-Kontext (#1777).

    Wie bei der Erklärung (``doc_export.kontext``) gilt: kein ``None``, kein
    fehlender Schlüssel. Jede in ``CRA_VARIABLES`` deklarierte Variable muss
    auch für ein Projekt ohne jede Erfassung ankommen — Jinja druckt ``None``
    wörtlich, und eine Vorlage darf nie an einer Teilangabe scheitern.

    Der **Leerstand** wird in derselben Sprache aufgelöst wie die Erhebung
    (#1954): Scheitert ``daten``, dürfen nicht plötzlich deutsche Texte in
    einer englischen Vorlage stehen — der Ausfall einer Teilangabe wäre dann
    am Dokument sichtbar, aber als Sprachbruch und nicht als Lücke.
    """
    sp = _rt.aufloesen("cra", projekt_name, sprache)
    try:
        d = daten(projekt_name, version=version, db_path=Path(db_path), sprache=sp)
    except Exception:  # noqa: BLE001
        d = {}
    leer = {
        "projekt_name": projekt_name, "version": "", "hersteller": "",
        "produkt": projekt_name, "produktklasse": "", "produktklasse_label": "",
        "produktklasse_referenz": "", "bewertungsweg": "", "bewertungsweg_label": "",
        "rechtsgrundlage": _t(sp, "regulation"), "ce_kennzeichnung": "",
        "datum": date.today().isoformat(), "ampel": "", "ampel_label": "",
        "konform": False, "reifegrad_pct": 0, "erfuellt": 0,
        "begruendet_akzeptiert": 0, "offen": 0, "gesamt_anforderungen": 0,
        "annex_vollstaendig": False, "doc_ausgestellt": False,
        "offene_kritische_schwachstellen": 0, "anforderungen": [],
        "abweichungen_begruendet": [], "nicht_konformitaeten": [],
        "annex_vii": [], "annex_vii_verfuegbar": False,
        "akzeptierte_restrisiken": [], "hinweis": _t(sp, "hinweis"),
        "sicherheitstests": _test_leer(sp), "sprache": sp,
    }
    out = {**leer, **{k: v for k, v in d.items() if v is not None}}
    if out.get("reifegrad_pct") is None:
        out["reifegrad_pct"] = 0
    return out


def build_docx(projekt_name: str, *, version: str | None = None,
               db_path: Path = CRA_DB, sprache: str | None = None) -> bytes:
    """Der programmatische Nachweis. Setzt nur, erhebt nicht (siehe :func:`daten`)."""
    from shared.reports.docx_pdf import set_a4

    d = daten(projekt_name, version=version, db_path=db_path, sprache=sprache)
    sp = str(d.get("sprache") or "de")
    leer = _t(sp, "leer")
    em = _t(sp, "leer_em")

    doc = Document(); set_a4(doc, sprache=sp)

    _h(doc, _t(sp, "titel"), size=18, color=_EU_BLUE, space_before=0)
    _p(doc, _t(sp, "regulation"))

    kopf = [
        (_t(sp, "k_hersteller"), d["hersteller"] or leer),
        (_t(sp, "k_produkt"), d["produkt"]),
        (_t(sp, "k_version"), d["version"] or leer),
        (_t(sp, "k_produktklasse"),
         f"{d['produktklasse_label']} — {d['produktklasse_referenz']}".strip(" —")),
        (_t(sp, "k_verfahren"), d["bewertungsweg_label"]),
        (_t(sp, "k_rechtsgrundlage"), d["rechtsgrundlage"]),
        (_t(sp, "k_ce"), d["ce_kennzeichnung"]),
        (_t(sp, "k_datum"), d["datum"]),
    ]
    t = doc.add_table(rows=len(kopf), cols=2); t.style = "Light Grid Accent 1"
    for i, (k, v) in enumerate(kopf):
        t.rows[i].cells[0].text = k; t.rows[i].cells[1].text = str(v)

    # Gesamturteil
    _h(doc, _t(sp, "h_gesamturteil"), color=_EU_BLUE)
    _p(doc, _t(sp, "urteil", ampel=d['ampel_label'], pct=d['reifegrad_pct'],
               erfuellt=d['erfuellt'], begruendet=d['begruendet_akzeptiert'],
               offen=d['offen'], gesamt=d['gesamt_anforderungen']))
    ja, nein = _t(sp, "ja"), _t(sp, "nein")
    _p(doc, _t(sp, "urteil_annex",
               annex=ja if d['annex_vollstaendig'] else nein,
               doc=ja if d['doc_ausgestellt'] else nein,
               vuln=d['offene_kritische_schwachstellen']))

    # Anforderungsstatus je Kapitel (mit Rechtsgrundlage)
    _h(doc, _t(sp, "h_anforderungen"), color=_EU_BLUE)
    tbl = doc.add_table(rows=1, cols=4); tbl.style = "Light Grid Accent 1"
    hdr = tbl.rows[0].cells
    hdr[0].text = _t(sp, "t_anforderung"); hdr[1].text = _t(sp, "t_rechtsgrundlage")
    hdr[2].text = _t(sp, "t_status"); hdr[3].text = _t(sp, "t_hinweis")
    for a in d["anforderungen"]:
        row = tbl.add_row().cells
        row[0].text = _t(sp, "req_zeile", id=a['id'], titel=a['titel'])
        row[1].text = a["rechtsgrundlage"]
        row[2].text = a["status_label"]
        row[3].text = a["hinweis"]

    # Begründete Abweichungen (akzeptierte Restrisiken)
    _h(doc, _t(sp, "h_abweichungen"), color=_EU_BLUE)
    if not d["abweichungen_begruendet"]:
        _p(doc, _t(sp, "abweichungen_keine"))
    else:
        for a in d["abweichungen_begruendet"]:
            _p(doc, _t(sp, "abweichung_zeile", id=a['requirement_id'],
                       titel=a.get('titel', '')), size=10)
            _p(doc, _t(sp, "abweichung_meta", kategorie=a.get('kategorie'),
                       von=a.get('von') or em,
                       rechtsgrundlage=a.get('rechtsgrundlage') or em), size=9)
            _p(doc, _t(sp, "abweichung_grund", grund=a.get('grund') or em), size=9)

    # Offene Nicht-Konformitäten
    if d["nicht_konformitaeten"]:
        _h(doc, _t(sp, "h_nicht_konform"), color=RGBColor(0xC6, 0x28, 0x28))
        for a in d["nicht_konformitaeten"]:
            _p(doc, _t(sp, "nicht_konform_zeile", id=a['requirement_id'],
                       titel=a.get('titel', ''), ref=a.get('ref', '')), size=10)

    # #1824: Sicherheitstests. Eigener Abschnitt und nicht eine Zeile in der
    # Annex-VII-Liste: Dort steht „Testberichte belegt ja/nein" — hier steht,
    # ob sie den ausgelieferten Stand belegen, und ob der Hersteller auf eigene
    # Tests verzichtet.
    st = d["sicherheitstests"]
    _h(doc, _t(sp, "h_tests"), color=_EU_BLUE)
    _p(doc, _t(sp, "tests_zeile", art=st['art_label'],
               anzahl=st['nachweis_count'], juengster=st['juengster'] or leer))
    if st["verzicht_erklaert"]:
        _p(doc, _t(sp, "tests_verzicht", von=st['verzicht_von'] or em,
                   am=st['verzicht_am'] or em,
                   review=st['verzicht_review'] or em), size=10)
        _p(doc, _t(sp, "tests_begruendung",
                   grund=st['verzicht_begruendung'] or em), size=9)
    for f in st["feststellungen"]:
        _p(doc, _t(sp, "tests_feststellung", text=f['text']), size=9)
    if st["belegt"]:
        _p(doc, _t(sp, "tests_belegt"), size=9)

    # Annex VII
    _h(doc, _t(sp, "h_annex"), color=_EU_BLUE)
    if not d["annex_vii_verfuegbar"]:
        _p(doc, _t(sp, "annex_fehlt"), size=9)
    for b in d["annex_vii"]:
        mark = "✓" if b["belegt"] else "✗"
        # `label` ist die Baustein-Bezeichnung aus `cra/traceability_db.py` und
        # wird nur durchgereicht — sie bleibt deutsch (siehe Bericht zu #1954).
        _p(doc, _t(sp, "annex_zeile", mark=mark, label=b['label'],
                   anzahl=b['nachweis_count']), size=9)

    _h(doc, _t(sp, "h_restrisiken"), color=_EU_BLUE)
    if not d["akzeptierte_restrisiken"]:
        _p(doc, _t(sp, "restrisiken_keine"))
    else:
        for r in d["akzeptierte_restrisiken"]:
            _p(doc, _t(sp, "restrisiko_zeile", nr=r['nr'], name=r['name']), size=10)
            # Dieselbe Zeile wie bei den Abweichungen oben — ein eigener
            # Katalogeintrag mit identischem Text wären zwei Orte für eine
            # Beschriftung.
            _p(doc, _t(sp, "abweichung_meta", kategorie=r['kategorie'] or em,
                       von=r['von'] or em,
                       rechtsgrundlage=r['rechtsgrundlage'] or em), size=9)
            if r["grund"]:
                _p(doc, _t(sp, "abweichung_grund", grund=r['grund']), size=9)

    _h(doc, _t(sp, "h_hinweis"), color=_EU_BLUE)
    _p(doc, d["hinweis"], size=9)

    bio = BytesIO(); doc.save(bio); return bio.getvalue()


def build_pdf(projekt_name: str, *, version: str | None = None,
              db_path: Path = CRA_DB, sprache: str | None = None) -> bytes:
    from shared.reports.docx_pdf import docx_bytes_to_pdf
    return docx_bytes_to_pdf(build_docx(projekt_name, version=version,
                                        db_path=db_path, sprache=sprache))


def build(projekt_name: str, *, fmt: str = "docx", version: str | None = None,
          db_path: Path = CRA_DB, sprache: str | None = None) -> bytes:
    """Format-Weiche für das Berichts-Center (#1776) — Muster ``doc_export.build``."""
    if (fmt or "docx").lower() == "pdf":
        return build_pdf(projekt_name, version=version, db_path=db_path,
                         sprache=sprache)
    return build_docx(projekt_name, version=version, db_path=db_path,
                      sprache=sprache)
