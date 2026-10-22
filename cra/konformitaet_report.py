"""Kundenfähiger CRA-Konformitätsnachweis je Release (#1610/#1613).

Erzeugt einen versionsgebundenen Nachweis (DOCX/PDF, A4, vektoriell) mit sichtbarer
Rechtsgrundlage: Erfüllungsgrad je Anforderung (Artikel-/Annex-Referenz), begründete
Abweichungen inkl. akzeptiertem Risiko, Annex-VII-Vollständigkeit, Schwachstellen-Status,
EU-Konformitätserklärung/CE und das Konformitäts-Gate-Fazit.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document
from docx.shared import Pt, RGBColor

CRA_DB = Path("data/db/cra.sqlite")

_EU_BLUE = RGBColor(0x00, 0x33, 0x99)
_REGULATION = "Verordnung (EU) 2024/2847 (Cyber Resilience Act)"
_VERFAHREN = {"A": "Modul A — interne Kontrolle (Selbstbewertung), Annex VIII",
              "B+C": "Modul B+C — EU-Baumusterprüfung, Annex VIII",
              "H": "Modul H — umfassende Qualitätssicherung, Annex VIII",
              "EUCC": "EUCC-Zertifizierung"}
_AMPEL = {"gruen": "KONFORM", "bedingt": "BEDINGT KONFORM", "rot": "NICHT KONFORM"}
_STATUS_LABEL = {"erfuellt": "erfüllt", "begruendet": "Abweichung begründet akzeptiert",
                 "offen": "offen (nicht konform)"}


def _ce_text(konf: dict | None) -> str:
    """CE-Kennzeichnungs-Status für den Nachweis (#1671)."""
    k = konf or {}
    if k.get("ce_status") == "ce_angebracht" or k.get("ce_angebracht_am"):
        am = str(k.get("ce_angebracht_am") or "")[:10]
        ort = k.get("ce_ort") or ""
        teile = ["angebracht"]
        if am:
            teile.append(f"am {am}")
        if ort:
            teile.append(f"({ort})")
        return " ".join(teile)
    if k.get("doc_ausgestellt"):
        return "DoC ausgestellt — CE anzubringen"
    return "noch nicht angebracht"


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


def build_docx(projekt_name: str, *, version: str | None = None) -> bytes:
    from shared.reports.docx_pdf import set_a4
    from cra.db import load_bewertungen, load_projekt
    from cra.requirements import CRA_ANFORDERUNGEN, KAPITEL, PRODUKTKLASSEN
    from cra.konformitaet_gate import evaluate
    from cra import konformitaet_db as kdb

    projekt = load_projekt(CRA_DB, projekt_name) or {}
    gate = evaluate(projekt_name, version=version)
    bew_raw = load_bewertungen(CRA_DB, projekt_name)
    bew = {rid: d.get("bewertung", 0) for rid, d in bew_raw.items()}

    # Konformitätsbewertungsverfahren + Produktklasse
    konf = None
    try:
        for k in kdb.list_konformitaet(CRA_DB, projekt_name):
            if not version or str(k.get("release_version") or "") == str(version):
                konf = k; break
    except Exception:  # noqa: BLE001
        konf = None
    pklasse = (konf or {}).get("produktklasse") or projekt.get("produktklasse") or "default"
    pk_info = PRODUKTKLASSEN.get(pklasse, PRODUKTKLASSEN.get("default", {}))
    weg = (konf or {}).get("bewertungsweg") or "A"

    doc = Document(); set_a4(doc)

    _h(doc, "EU-Konformitätsnachweis (Cyber Resilience Act)", size=18, color=_EU_BLUE, space_before=0)
    _p(doc, _REGULATION)

    # Meta
    meta = [
        ("Hersteller", projekt.get("unternehmen") or "–"),
        ("Produkt", projekt.get("produkt") or projekt_name),
        ("Version / Release", version or (konf or {}).get("release_version") or "–"),
        ("Produktklasse", f"{pk_info.get('label', pklasse)} — {pk_info.get('referenz', '')}".strip(" —")),
        ("Konformitätsbewertungsverfahren", _VERFAHREN.get(weg, weg)),
        ("Rechtsgrundlage", _REGULATION),
        ("CE-Kennzeichnung", _ce_text(konf)),
        ("Datum", date.today().isoformat()),
    ]
    t = doc.add_table(rows=len(meta), cols=2); t.style = "Light Grid Accent 1"
    for i, (k, v) in enumerate(meta):
        t.rows[i].cells[0].text = k; t.rows[i].cells[1].text = str(v)

    # Gesamturteil
    _h(doc, "Gesamturteil (Konformitäts-Gate)", color=_EU_BLUE)
    _p(doc, f"Ergebnis: {_AMPEL.get(gate['ampel'], gate['ampel'])}  ·  "
            f"Reifegrad {gate.get('reifegrad_pct')} %  ·  "
            f"erfüllt {gate['erfuellt']}, begründet akzeptiert {gate['begruendet_akzeptiert']}, "
            f"offen {gate['offen']} von {gate['gesamt_anforderungen']} Anforderungen.")
    _p(doc, f"Annex VII vollständig: {'ja' if gate['annex_vollstaendig'] else 'nein'}  ·  "
            f"EU-Konformitätserklärung ausgestellt: {'ja' if gate['doc_ausgestellt'] else 'nein'}  ·  "
            f"offene kritische/hohe Schwachstellen: {gate['offene_kritische_schwachstellen']}.")

    # Anforderungsstatus je Kapitel (mit Rechtsgrundlage)
    _h(doc, "Erfüllung der essenziellen Anforderungen (Annex I) — mit Rechtsgrundlage", color=_EU_BLUE)
    abw_by_id = {a["requirement_id"]: a for a in gate.get("abweichungen", [])}
    tbl = doc.add_table(rows=1, cols=4); tbl.style = "Light Grid Accent 1"
    hdr = tbl.rows[0].cells
    hdr[0].text = "Anforderung"; hdr[1].text = "Rechtsgrundlage"; hdr[2].text = "Status"; hdr[3].text = "Hinweis"
    for req in CRA_ANFORDERUNGEN:
        rid = req["id"]; b = int(bew.get(rid, 0) or 0)
        if b >= 4:
            status = "erfuellt"; hinweis = ""
        elif rid in abw_by_id and abw_by_id[rid]["art"] == "begruendet":
            status = "begruendet"
            a = abw_by_id[rid]
            hinweis = f"{a.get('kategorie')}: {a.get('grund') or ''}".strip(": ")
        else:
            status = "offen"; hinweis = "nicht erfüllt / nicht begründet"
        kref = KAPITEL.get(req.get("kapitel"), {}).get("referenz", "")
        row = tbl.add_row().cells
        row[0].text = f"{rid} — {req.get('titel', '')}"
        row[1].text = f"{req.get('ref', '')} · {kref}".strip(" ·")
        row[2].text = _STATUS_LABEL[status]
        row[3].text = hinweis

    # Begründete Abweichungen (akzeptierte Restrisiken)
    begr = [a for a in gate.get("abweichungen", []) if a.get("art") == "begruendet"]
    _h(doc, "Begründete Abweichungen (als Risiko akzeptiert)", color=_EU_BLUE)
    if not begr:
        _p(doc, "Keine — alle anwendbaren Anforderungen sind erfüllt.")
    else:
        for a in begr:
            _p(doc, f"• {a['requirement_id']} — {a.get('titel', '')}", size=10)
            _p(doc, f"   Kategorie: {a.get('kategorie')} · akzeptiert von: {a.get('von') or '—'} · "
                    f"Rechtsgrundlage: {a.get('rechtsgrundlage') or '—'}", size=9)
            _p(doc, f"   Begründung: {a.get('grund') or '—'}", size=9)

    # Offene Nicht-Konformitäten
    offen = [a for a in gate.get("abweichungen", []) if a.get("art") == "offen"]
    if offen:
        _h(doc, "Offene Nicht-Konformitäten (Korrekturmaßnahmen erforderlich)", color=RGBColor(0xC6, 0x28, 0x28))
        for a in offen:
            _p(doc, f"• {a['requirement_id']} — {a.get('titel', '')} ({a.get('ref', '')})", size=10)

    # Annex VII
    _h(doc, "Technische Dokumentation (Annex VII)", color=_EU_BLUE)
    try:
        from cra.traceability_db import annex_vii_status
        annex = annex_vii_status(CRA_DB, projekt_name)
        for b in annex.get("bausteine", []):
            mark = "✓" if b.get("ampel") == "belegt" else "✗"
            _p(doc, f"{mark} {b.get('label')} ({b.get('nachweis_count', 0)} Nachweis(e))", size=9)
    except Exception:  # noqa: BLE001
        _p(doc, "Annex-VII-Status nicht verfügbar.", size=9)

    # Akzeptierte Restrisiken der verknüpften Risikobewertung (#1674) — auch nicht-
    # anforderungsbezogene, formal akzeptierte Risiken sind hier nachgewiesen.
    _h(doc, "Akzeptierte Restrisiken (Risikobewertung)", color=_EU_BLUE)
    meta = projekt.get("meta") if isinstance(projekt.get("meta"), dict) else {}
    rb_name = (meta.get("linked_risk_projekt") or "").strip()
    akzeptiert = []
    if rb_name:
        try:
            from pathlib import Path as _P
            from risikobewertung.db import load_risiken
            for r in load_risiken(_P("data/db/risikobewertung.sqlite"), rb_name):
                if (r.get("behandlung") or "") == "akzeptiert":
                    akzeptiert.append(r)
        except Exception:  # noqa: BLE001
            pass
    if not akzeptiert:
        _p(doc, "Keine formal akzeptierten Restrisiken.")
    else:
        for r in akzeptiert:
            _p(doc, f"• #{r.get('nr')} {r.get('risk_name') or ''}", size=10)
            _p(doc, f"   Kategorie: {r.get('akzeptanz_kategorie') or '—'} · akzeptiert von: "
                    f"{r.get('akzeptanz_von') or '—'} · Rechtsgrundlage: {r.get('rechtsgrundlage') or '—'}", size=9)
            if r.get("akzeptanz_grund"):
                _p(doc, f"   Begründung: {r.get('akzeptanz_grund')}", size=9)

    _h(doc, "Hinweis", color=_EU_BLUE)
    _p(doc, "Dieser Nachweis dokumentiert den Stand zum angegebenen Datum/Release. Begründete Abweichungen "
            "beruhen auf dem risikobasierten Ansatz des CRA; offene Nicht-Konformitäten sind vor der "
            "CE-Kennzeichnung zu schließen.", size=9)

    bio = BytesIO(); doc.save(bio); return bio.getvalue()


def build_pdf(projekt_name: str, *, version: str | None = None) -> bytes:
    from shared.reports.docx_pdf import docx_bytes_to_pdf
    return docx_bytes_to_pdf(build_docx(projekt_name, version=version))
