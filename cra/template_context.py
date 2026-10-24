"""CRA-Adapter für die zentrale Word-Vorlagen-Engine (#993, Story 5).

Liefert einen für Jinja-Vorlagen robusten Kontext (``build_cra_context``) sowie
die dokumentierte Variablenliste (``CRA_VARIABLES``). Die Engine in
``shared/templates/engine.py`` rendert hochgeladene DOCX-Vorlagen mit diesem
Kontext; ``shared/templates/schema.py`` lädt beide Symbole per guarded import.

Design-Regeln:
  - **Keine None-Werte**: fehlende Daten werden zu leeren Strings/Listen/0.
  - Vorhandene Bericht-Logik (Reifegrad, verknüpfte Risikobewertung) wird über
    ``cra.report_export``/``cra.requirements`` wiederverwendet, NICHT dupliziert.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any


# ── Dokumentierte Variablen ────────────────────────────────────────────────────
# Blattpfade (``projekt.name``) statt fünf Objekte mit Prosa-Beschreibung der
# Unterfelder (#1741). Vorher war CRA das einzige Modul, für das man die
# Unterfelder aus einem Beschreibungstext herauslesen musste — und damit das
# Modul, für das eine Vorlage am schwersten zu schreiben war. Jetzt zeigt das
# Admin-UI die Tokens kopierbar an wie bei den anderen sieben Modulen.
# Listen bleiben ein Eintrag mit der Aufzählung ihrer Felder (Muster NIS2):
# ein Blattpfad je Listenelement wäre ohne Index nicht benutzbar.
# **Der Kontext ist unverändert** — hier wird nur anders deklariert.
CRA_VARIABLES: list[dict[str, Any]] = [
    {"key": "projekt.name", "typ": "text",
     "beschreibung": "Name des CRA-Projekts.", "pflicht": True},
    {"key": "projekt.unternehmen", "typ": "text",
     "beschreibung": "Herstellendes Unternehmen.", "pflicht": True},
    {"key": "projekt.produkt", "typ": "text",
     "beschreibung": "Produkt mit digitalen Elementen, auf das sich der Nachweis "
                     "bezieht.", "pflicht": False},
    {"key": "projekt.produktklasse", "typ": "text",
     "beschreibung": "Schlüssel der Produktklasse (default/wichtig_1/wichtig_2/"
                     "kritisch) — für Bedingungen in der Vorlage.", "pflicht": False},
    {"key": "projekt.produktklasse_label", "typ": "text",
     "beschreibung": "Anzeigename der Produktklasse.", "pflicht": False},
    {"key": "projekt.beschreibung", "typ": "text",
     "beschreibung": "Freitext-Beschreibung des Projekts.", "pflicht": False},
    {"key": "projekt.berater", "typ": "text",
     "beschreibung": "Verantwortlicher Berater.", "pflicht": False},
    {"key": "projekt.konformitaet", "typ": "text",
     "beschreibung": "Konformitätsbewertungsverfahren der Produktklasse "
                     "(Annex VIII).", "pflicht": False},
    {"key": "projekt.referenz", "typ": "text",
     "beschreibung": "Rechtsreferenz der Produktklasse in der CRA.",
     "pflicht": False},

    {"key": "meta.datum", "typ": "text",
     "beschreibung": "Erstelldatum des Berichts (ISO, JJJJ-MM-TT).", "pflicht": False},
    {"key": "meta.reifegrad_pct", "typ": "zahl",
     "beschreibung": "Gewichteter Gesamt-Reifegrad in Prozent.", "pflicht": False},
    {"key": "meta.ampel", "typ": "text",
     "beschreibung": "Ampelstufe zum Reifegrad (gruen/gelb/rot).", "pflicht": False},
    {"key": "meta.bewertete_count", "typ": "zahl",
     "beschreibung": "Anzahl der bereits bewerteten Anforderungen.", "pflicht": False},
    {"key": "meta.gesamt_count", "typ": "zahl",
     "beschreibung": "Anzahl der Anforderungen im Katalog.", "pflicht": False},
    {"key": "meta.risiko_verknuepft", "typ": "wahrheitswert",
     "beschreibung": "Ob eine Risikobewertung verknüpft ist — sonst bleibt "
                     "``risiken`` leer.", "pflicht": False},
    {"key": "meta.risiko_projekt", "typ": "text",
     "beschreibung": "Name des verknüpften Risikobewertungs-Projekts.",
     "pflicht": False},
    {"key": "meta.framework", "typ": "text",
     "beschreibung": "Bewertungs-Framework der verknüpften Risikobewertung bzw. "
                     "des Threat-Models (z. B. STRIDE).", "pflicht": False},
    {"key": "meta.kapitel", "typ": "liste",
     "beschreibung": "Kapitel-Übersicht; je Eintrag id, titel, referenz, "
                     "reifegrad_pct.", "pflicht": False},
    {"key": "meta.vulns", "typ": "liste",
     "beschreibung": "Erfasste Schwachstellen; je Eintrag cve_id, titel, schwere, "
                     "status.", "pflicht": False},
    {"key": "meta.threatmodel.framework", "typ": "text",
     "beschreibung": "Framework des CRA-Threat-Models (C5).", "pflicht": False},
    {"key": "meta.threatmodel.scope", "typ": "text",
     "beschreibung": "Betrachtungsumfang des Threat-Models.", "pflicht": False},

    {"key": "bewertungen", "typ": "liste",
     "beschreibung": "Anforderungsbewertungen je CRA-Anforderung; je Eintrag id, "
                     "kapitel, titel, ref, bewertung, bewertung_label, kommentar, "
                     "massnahme, verantwortlich, zieldatum, gewichtung.",
     "pflicht": False},
    {"key": "risiken", "typ": "liste",
     "beschreibung": "Top-Risiken aus der verknüpften Risikobewertung; je Eintrag "
                     "name, label, wert. Leer, wenn keine RB verknüpft ist.",
     "pflicht": False},
    {"key": "dokumente", "typ": "liste",
     "beschreibung": "Finalisierte/freigegebene gemanagte Dokumente des Projekts; "
                     "je Eintrag titel, doc_type, rechtsgrundlage, status, version, "
                     "stand, doc_mode, external_url.", "pflicht": False},

    # ── EU-Konformitätserklärung, Anhang V (#1753) ────────────────────────────
    # Diese Variablen tragen ein eigenes Dokument: die Erklärung, die der
    # Hersteller unterschreibt. Eine Vorlage, die ``doc.*`` benutzt, wird
    # deshalb von ``shared/templates/validate.py`` auf **Vollständigkeit nach
    # Anhang V** geprüft — bei einem Bericht ist eine freie Vorlage
    # Geschmacksfrage, hier ein Rechtsrisiko. Die Pflichtliste steht in
    # ``cra/doc_export.py`` (eine Quelle für Aufbau, Prüfung und Vorlage).
    {"key": "doc.produkt_name", "typ": "text",
     "beschreibung": "Anhang V Nr. 1 — Produktname.", "pflicht": True},
    {"key": "doc.produkt_typ", "typ": "text",
     "beschreibung": "Anhang V Nr. 1 — Typbezeichnung/Modell.", "pflicht": True},
    {"key": "doc.produkt_charge", "typ": "text",
     "beschreibung": "Anhang V Nr. 1 — Charge, Serie oder Version, die das "
                     "Produkt eindeutig identifiziert.", "pflicht": True},
    {"key": "doc.hersteller", "typ": "text",
     "beschreibung": "Anhang V Nr. 2 — Name des Herstellers (Vorbelegung aus "
                     "den Projekt-Stammdaten).", "pflicht": True},
    {"key": "doc.hersteller_adresse", "typ": "text",
     "beschreibung": "Anhang V Nr. 2 — Anschrift des Herstellers.",
     "pflicht": True},
    {"key": "doc.bevollmaechtigter", "typ": "text",
     "beschreibung": "Anhang V Nr. 2 — EU-Bevollmächtigter, soweit vorhanden "
                     "(Art. 22).", "pflicht": False},
    {"key": "doc.verantwortungssatz", "typ": "text",
     "beschreibung": "Anhang V Nr. 3 — Festtext zur alleinigen Verantwortung "
                     "des Herstellers. Kein Eingabefeld.", "pflicht": True},
    {"key": "doc.gegenstand", "typ": "text",
     "beschreibung": "Anhang V Nr. 4 — Gegenstand der Erklärung "
                     "(Produktbeschreibung zur Rückverfolgbarkeit).",
     "pflicht": True},
    {"key": "doc.konformitaetsaussage", "typ": "text",
     "beschreibung": "Anhang V Nr. 5 — Aussage, dass der Gegenstand die "
                     "Verordnung (EU) 2024/2847 und das genannte weitere "
                     "Unionsrecht erfüllt. Abgeleitet, kein Eingabefeld.",
     "pflicht": True},
    {"key": "doc.weiteres_unionsrecht", "typ": "text",
     "beschreibung": "Anhang V Nr. 5 — weitere Rechtsakte der Union, auf die "
                     "sich die Erklärung mit erstreckt.", "pflicht": False},
    {"key": "doc.normen", "typ": "liste",
     "beschreibung": "Anhang V Nr. 6 — angewandte Normen/Spezifikationen als "
                     "Liste.", "pflicht": False},
    {"key": "doc.normen_text", "typ": "text",
     "beschreibung": "Anhang V Nr. 6 — dieselben Normen als ein Textfeld "
                     "(komfortabler in einfachen Vorlagen).", "pflicht": False},
    {"key": "doc.nb_name", "typ": "text",
     "beschreibung": "Anhang V Nr. 7 — Name der notifizierten Stelle.",
     "pflicht": False},
    {"key": "doc.nb_kennnummer", "typ": "text",
     "beschreibung": "Anhang V Nr. 7 — Kennnummer der notifizierten Stelle.",
     "pflicht": False},
    {"key": "doc.nb_zertifikat", "typ": "text",
     "beschreibung": "Anhang V Nr. 7 — Nummer/Bezeichnung des Zertifikats.",
     "pflicht": False},
    {"key": "doc.nb_verfahren", "typ": "text",
     "beschreibung": "Anhang V Nr. 7 — durchgeführtes Konformitätsbewertungs"
                     "verfahren (Anhang VIII).", "pflicht": False},
    {"key": "doc.nb_erforderlich", "typ": "wahrheitswert",
     "beschreibung": "Ob der gewählte Bewertungsweg eine notifizierte Stelle "
                     "einschließt — dann sind die Nr.-7-Angaben Pflicht.",
     "pflicht": False},
    {"key": "doc.zusatzangaben", "typ": "text",
     "beschreibung": "Anhang V Nr. 8 — Zusatzangaben.", "pflicht": False},
    {"key": "doc.ort", "typ": "text",
     "beschreibung": "Anhang V Nr. 8 — Ort der Ausstellung.", "pflicht": True},
    {"key": "doc.datum", "typ": "text",
     "beschreibung": "Anhang V Nr. 8 — Datum der Ausstellung.", "pflicht": True},
    {"key": "doc.unterzeichner_name", "typ": "text",
     "beschreibung": "Anhang V Nr. 8 — Name des Unterzeichners.",
     "pflicht": True},
    {"key": "doc.unterzeichner_funktion", "typ": "text",
     "beschreibung": "Anhang V Nr. 8 — Funktion des Unterzeichners; ohne sie "
                     "ist die Erklärung nicht zurechenbar.", "pflicht": True},
    {"key": "doc.rechtsgrundlage", "typ": "text",
     "beschreibung": "Rechtsgrundlage der Erklärung (Art. 28 i.V.m. Anhang V).",
     "pflicht": False},
    {"key": "doc.release_version", "typ": "text",
     "beschreibung": "Release, auf das sich die Erklärung bezieht (leer = "
                     "Produkt-Datensatz).", "pflicht": False},
    {"key": "doc.version", "typ": "zahl",
     "beschreibung": "Fassungsnummer der Erklärung (``doc_version``).",
     "pflicht": False},
    {"key": "doc.ausgestellt_am", "typ": "text",
     "beschreibung": "Zeitpunkt der Ausstellung; leer, solange Entwurf.",
     "pflicht": False},
    {"key": "doc.ist_entwurf", "typ": "wahrheitswert",
     "beschreibung": "True, solange Pflichtangaben fehlen oder nicht "
                     "ausgestellt wurde — die Vorlage sollte dann sichtbar "
                     "„ENTWURF“ kennzeichnen.", "pflicht": False},
    {"key": "doc.fassung", "typ": "text",
     "beschreibung": "„ausgestellt“ oder der Entwurfsvermerk im Klartext.",
     "pflicht": False},
    {"key": "doc.fehlende_pflichtfelder", "typ": "liste",
     "beschreibung": "Fehlende Anhang-V-Angaben; je Eintrag nr, bezeichnung.",
     "pflicht": False},
    {"key": "doc.fehlende_pflichtfelder_text", "typ": "text",
     "beschreibung": "Dieselben Lücken als Satz („Nr. 8: Ort und Datum“); "
                     "leer, wenn vollständig.", "pflicht": False},

    # #1777: der Konformitätsnachweis je Release. Bis v8.0.3 war er der einzige
    # CRA-Bericht, den eine Word-Vorlage nicht erzeugen konnte — es gab keine
    # Variablen dafür. Die Werte kommen aus ``konformitaet_report.kontext`` und
    # damit aus derselben Erhebung wie der programmatische Nachweis.
    {"key": "nachweis.version", "typ": "text",
     "beschreibung": "Release/Version, auf die sich der Nachweis bezieht "
                     "(leer = aktueller Stand).", "pflicht": False},
    {"key": "nachweis.hersteller", "typ": "text",
     "beschreibung": "Hersteller des Produkts.", "pflicht": False},
    {"key": "nachweis.produkt", "typ": "text",
     "beschreibung": "Produkt mit digitalen Elementen.", "pflicht": False},
    {"key": "nachweis.produktklasse_label", "typ": "text",
     "beschreibung": "Produktklasse im Klartext.", "pflicht": False},
    {"key": "nachweis.produktklasse_referenz", "typ": "text",
     "beschreibung": "Rechtsreferenz der Produktklasse.", "pflicht": False},
    {"key": "nachweis.bewertungsweg_label", "typ": "text",
     "beschreibung": "Konformitätsbewertungsverfahren nach Anhang VIII.",
     "pflicht": False},
    {"key": "nachweis.rechtsgrundlage", "typ": "text",
     "beschreibung": "Verordnung (EU) 2024/2847.", "pflicht": False},
    {"key": "nachweis.ce_kennzeichnung", "typ": "text",
     "beschreibung": "Stand der CE-Kennzeichnung.", "pflicht": False},
    {"key": "nachweis.datum", "typ": "text",
     "beschreibung": "Ausstellungsdatum des Nachweises (ISO).", "pflicht": False},
    {"key": "nachweis.ampel", "typ": "text",
     "beschreibung": "Gate-Stufe (gruen/bedingt/rot).", "pflicht": False},
    {"key": "nachweis.ampel_label", "typ": "text",
     "beschreibung": "Gesamturteil im Klartext (KONFORM / BEDINGT KONFORM / "
                     "NICHT KONFORM).", "pflicht": False},
    {"key": "nachweis.konform", "typ": "wahrheitswert",
     "beschreibung": "Ist das Release konform?", "pflicht": False},
    {"key": "nachweis.reifegrad_pct", "typ": "zahl",
     "beschreibung": "Reifegrad in Prozent.", "pflicht": False},
    {"key": "nachweis.erfuellt", "typ": "zahl",
     "beschreibung": "Anzahl erfüllter Anforderungen.", "pflicht": False},
    {"key": "nachweis.begruendet_akzeptiert", "typ": "zahl",
     "beschreibung": "Anzahl begründet akzeptierter Abweichungen.", "pflicht": False},
    {"key": "nachweis.offen", "typ": "zahl",
     "beschreibung": "Anzahl offener Nicht-Konformitäten.", "pflicht": False},
    {"key": "nachweis.gesamt_anforderungen", "typ": "zahl",
     "beschreibung": "Anzahl der Anforderungen insgesamt.", "pflicht": False},
    {"key": "nachweis.annex_vollstaendig", "typ": "wahrheitswert",
     "beschreibung": "Ist die technische Dokumentation (Anhang VII) vollständig?",
     "pflicht": False},
    {"key": "nachweis.doc_ausgestellt", "typ": "wahrheitswert",
     "beschreibung": "Ist die EU-Konformitätserklärung ausgestellt?", "pflicht": False},
    {"key": "nachweis.offene_kritische_schwachstellen", "typ": "zahl",
     "beschreibung": "Offene kritische/hohe Schwachstellen.", "pflicht": False},
    {"key": "nachweis.anforderungen", "typ": "liste",
     "beschreibung": "Anforderungen mit Rechtsgrundlage: id, titel, "
                     "rechtsgrundlage, status, status_label, hinweis, bewertung.",
     "pflicht": False},
    {"key": "nachweis.abweichungen_begruendet", "typ": "liste",
     "beschreibung": "Begründet akzeptierte Abweichungen: requirement_id, titel, "
                     "kategorie, grund, von, rechtsgrundlage.", "pflicht": False},
    {"key": "nachweis.nicht_konformitaeten", "typ": "liste",
     "beschreibung": "Offene Nicht-Konformitäten: requirement_id, titel, ref.",
     "pflicht": False},
    {"key": "nachweis.annex_vii", "typ": "liste",
     "beschreibung": "Anhang-VII-Bausteine: label, belegt, nachweis_count.",
     "pflicht": False},
    {"key": "nachweis.akzeptierte_restrisiken", "typ": "liste",
     "beschreibung": "Formal akzeptierte Restrisiken: nr, name, kategorie, von, "
                     "rechtsgrundlage, grund.", "pflicht": False},
    {"key": "nachweis.hinweis", "typ": "text",
     "beschreibung": "Standardhinweis zur Gültigkeit des Nachweises.",
     "pflicht": False},
]


# DB-Modulkennung für die generische Dokument-Persistenz (shared.documents).
_DOC_MODUL = "cra"


def _s(value: Any) -> str:
    """None-sichere String-Konvertierung."""
    return "" if value is None else str(value)


def _dokumente(db_path: Path, projekt_name: str) -> list[dict[str, Any]]:
    """Finalisierte/freigegebene gemanagte Dokumente (Jinja-sicher, nie None)."""
    try:
        from shared.documents.db import list_documents
        from shared.documents.catalog import get_doc_spec
        out: list[dict[str, Any]] = []
        for d in list_documents(db_path, _DOC_MODUL, projekt_name):
            if _s(d.get("status")) not in ("final", "freigegeben"):
                continue
            spec = get_doc_spec(_DOC_MODUL, _s(d.get("doc_type"))) or {}
            mode = _s(d.get("doc_mode")) or "inapp"
            out.append({
                "titel": _s(d.get("titel")),
                "doc_type": _s(d.get("doc_type")),
                "rechtsgrundlage": _s(spec.get("rechtsgrundlage")),
                "status": _s(d.get("status")),
                "version": d.get("version") if d.get("version") is not None else 1,
                "stand": _s(d.get("updated_at")),
                # #1233 additiv: extern → URL statt Volltext; in-app → leere URL.
                "doc_mode": mode,
                "external_url": _s(d.get("external_url")) if mode == "extern" else "",
            })
        return out
    except Exception:
        return []


def _nachweis(db_path: Path, projekt_name: str, version: str = "") -> dict[str, Any]:
    """``nachweis``-Teilbaum; ein Fehler darf keinen CRA-Bericht verhindern."""
    try:
        from cra.konformitaet_report import kontext
        return kontext(db_path, projekt_name, version or None)
    except Exception:  # noqa: BLE001
        return {}


def build_cra_context(db_path: Path | str, projekt_name: str, *,
                      bericht_typ: str = "", version: str = "") -> dict[str, Any]:
    """Baut den Vorlagen-Kontext für ein CRA-Projekt.

    Liefert immer ein vollständiges Dict mit den Top-Level-Keys
    ``projekt``, ``bewertungen``, ``risiken``, ``meta`` — fehlende Daten als
    leere Defaults (nie ``None``).

    ``bericht_typ`` und ``version`` sind optional und kommen aus dem
    Berichts-Center (#1777): Der Konformitätsnachweis ist versionsgebunden, der
    Gesamtbericht nicht. Der Kontext bleibt **vollständig** — es wird nichts
    weggelassen, nur die versionsabhängigen Angaben richten sich nach dem
    gewählten Release. Eine Vorlage, die auf ``bericht_typ`` verzweigt, findet
    deshalb in jedem Fall alle deklarierten Variablen vor."""
    from cra import db as cdb
    from cra.requirements import (
        BEWERTUNG_SKALA,
        CRA_ANFORDERUNGEN,
        KAPITEL,
        PRODUKTKLASSEN,
        berechne_reifegrad,
    )
    from cra.report_export import build_rb_risk_summary

    db_path = Path(db_path)

    proj = cdb.load_projekt(db_path, projekt_name) or {}
    produktklasse = _s(proj.get("produktklasse") or "default") or "default"
    pk_info = PRODUKTKLASSEN.get(produktklasse, PRODUKTKLASSEN["default"])

    projekt = {
        "name": _s(proj.get("name") or projekt_name),
        "unternehmen": _s(proj.get("unternehmen")),
        "produkt": _s(proj.get("produkt")),
        "produktklasse": produktklasse,
        "produktklasse_label": _s(pk_info.get("label")),
        "beschreibung": _s(proj.get("beschreibung")),
        "berater": _s(proj.get("berater")),
        "konformitaet": _s(pk_info.get("konformitaet")),
        "referenz": _s(pk_info.get("referenz")),
    }

    # ── Bewertungen je Anforderung (stabile Anzeige-Reihenfolge) ───────────────
    bew_raw = cdb.load_bewertungen(db_path, projekt_name)
    bewertungen: list[dict[str, Any]] = []
    for req in CRA_ANFORDERUNGEN:
        rid = req["id"]
        d = bew_raw.get(rid, {})
        bval = int(d.get("bewertung", 0) or 0)
        binfo = BEWERTUNG_SKALA.get(bval, BEWERTUNG_SKALA[0])
        bewertungen.append({
            "id": rid,
            "kapitel": _s(req.get("kapitel")),
            "titel": _s(req.get("titel")),
            "ref": _s(req.get("ref")),
            "bewertung": bval,
            "bewertung_label": _s(binfo.get("label")),
            "kommentar": _s(d.get("kommentar")),
            "massnahme": _s(d.get("massnahme")),
            "verantwortlich": _s(d.get("verantwortlich")),
            "zieldatum": _s(d.get("zieldatum")),
            "gewichtung": int(req.get("gewichtung", 1) or 1),
        })

    # ── Reifegrad (wiederverwendete Bericht-Logik) ─────────────────────────────
    reife = berechne_reifegrad({rid: int(d.get("bewertung", 0) or 0)
                                for rid, d in bew_raw.items()})
    kapitel_meta = []
    for kap_id, kap_info in KAPITEL.items():
        kapitel_meta.append({
            "id": kap_id,
            "titel": _s(kap_info.get("titel")),
            "referenz": _s(kap_info.get("referenz")),
            "reifegrad_pct": reife["kapitel_pct"].get(kap_id, 0.0),
        })

    # ── Verknüpfte Risikobewertung (Top-Risiken) ───────────────────────────────
    rb = build_rb_risk_summary(db_path, projekt_name)
    risiken = [{
        "name": _s(t.get("name")),
        "label": _s(t.get("label")),
        "wert": t.get("wert") if t.get("wert") is not None else "",
    } for t in (rb.get("top") or [])]

    # ── Zusatz-Doku (Vulns / Threatmodel) ──────────────────────────────────────
    try:
        vulns = cdb.list_vuln(db_path, projekt_name)
    except Exception:
        vulns = []
    try:
        tm = cdb.load_threatmodel(db_path, projekt_name) or {}
    except Exception:
        tm = {}

    meta = {
        "datum": date.today().isoformat(),
        "reifegrad_pct": reife.get("gesamt_pct", 0.0),
        "ampel": _s(reife.get("ampel")),
        "bewertete_count": reife.get("bewertete_count", 0),
        "gesamt_count": reife.get("gesamt_count", 0),
        "kapitel": kapitel_meta,
        "risiko_verknuepft": bool(rb.get("linked")),
        "risiko_projekt": _s(rb.get("rb_projekt")),
        "framework": _s(rb.get("framework")) or _s(tm.get("framework")),
        "vulns": [{
            "cve_id": _s(v.get("cve_id")),
            "titel": _s(v.get("titel")),
            "schwere": _s(v.get("schwere")),
            "status": _s(v.get("status")),
        } for v in vulns],
        "threatmodel": {
            "framework": _s(tm.get("framework")),
            "scope": _s(tm.get("scope")),
        },
    }

    return {
        "projekt": projekt,
        "bewertungen": bewertungen,
        "risiken": risiken,
        "meta": meta,
        "dokumente": _dokumente(db_path, projekt_name),
        # #1753: Die EU-Konformitätserklärung (Anhang V). ``doc_export.kontext``
        # liefert jeden deklarierten Schlüssel auch für ein Projekt ohne
        # Erklärung — leere Zeichenketten, nie ``None`` (Jinja druckt ``None``
        # wörtlich), und der Fehlerfall bleibt dort gekapselt.
        "doc": _doc(db_path, projekt_name),
        # #1777: der Konformitätsnachweis je Release.
        "nachweis": _nachweis(db_path, projekt_name, version),
    }


def _doc(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """``doc``-Teilbaum; ein Fehler darf keinen CRA-Bericht verhindern."""
    try:
        from cra.doc_export import kontext
        return kontext(db_path, projekt_name)
    except Exception:  # noqa: BLE001
        from cra.doc_export import EINGABEFELDER, VERANTWORTUNGSSATZ
        leer: dict[str, Any] = {f: "" for f in EINGABEFELDER}
        leer.update({"normen": [], "normen_text": "",
                     "verantwortungssatz": VERANTWORTUNGSSATZ,
                     "konformitaetsaussage": "", "rechtsgrundlage": "",
                     "release_version": "", "version": 0, "ausgestellt_am": "",
                     "ist_entwurf": True, "fassung": "",
                     "fehlende_pflichtfelder": [],
                     "fehlende_pflichtfelder_text": "",
                     "nb_erforderlich": False})
        return leer
