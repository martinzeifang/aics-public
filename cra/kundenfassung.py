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
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

DB_PATH = Path("data/db/cra.sqlite")

#: Begriffe, die in einer Kundenfassung nichts zu suchen haben. Der Test
#: ``tests/test_kundenfassung_1758.py`` sucht sie im erzeugten Dokument — nicht
#: weil die Liste vollständig wäre, sondern weil sie die typischen Rutschbahnen
#: abdeckt, falls jemand den Renderer später „nur kurz" erweitert.
VERBOTENE_BEGRIFFE: tuple[str, ...] = (
    "akzeptiert", "Restrisiko", "offene Punkte", "Freigeber", "geprüft von",
    "Maßnahmenplan", "Zieldatum", "verantwortlich", "Ampel", "Reifegrad",
)


def _s(wert: Any) -> str:
    return "" if wert is None else str(wert).strip()


def sammle(projekt_name: str, *, db_path: Path = DB_PATH,
           version: str | None = None) -> dict[str, Any]:
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
        from cra.requirements import PRODUKTKLASSEN

        p = load_projekt(db_path, projekt_name) or {}
        klasse = _s(p.get("produktklasse")) or "default"
        d["produkt"] = {
            "name": _s(p.get("produkt")) or _s(p.get("name")),
            "hersteller": _s(p.get("unternehmen")),
            "beschreibung": _s(p.get("beschreibung")),
            "klasse_label": _s((PRODUKTKLASSEN.get(klasse) or {}).get("label")),
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
        }
    except Exception:  # noqa: BLE001
        d["support"] = {}

    try:
        from cra.db import load_psirt

        ps = load_psirt(db_path, projekt_name) or {}
        d["meldestelle"] = {
            "policy_url": _s(ps.get("disclosure_policy_url")),
            "security_md": _s(ps.get("security_md_url")),
            "kontakt": _s(ps.get("psirt_contacts")),
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


def build_docx(projekt_name: str, *, db_path: Path = DB_PATH,
               version: str | None = None) -> bytes:
    """Kundenfassung als DOCX."""
    import io

    from docx import Document
    from docx.shared import Pt

    from cra import ce_mark
    from shared.reports.docx_pdf import apply_base_font, set_a4

    d = sammle(projekt_name, db_path=db_path, version=version)
    doc = Document()
    set_a4(doc)

    prod = d.get("produkt") or {}
    titel = doc.add_heading("Cybersicherheit — Information für Kunden", level=0)
    titel.runs[0].font.size = Pt(18)
    doc.add_paragraph(
        f"{prod.get('name') or projekt_name} · {prod.get('hersteller') or ''}"
        f" · Stand {d['erstellt_am']}")
    doc.add_paragraph(
        "Dieses Dokument fasst zusammen, was für Sie als Anwender dieses "
        "Produkts mit digitalen Elementen von Bedeutung ist. Die vollständige "
        "technische Dokumentation einschließlich der Risikoabschätzung wird "
        "der Marktaufsichtsbehörde auf Verlangen vorgelegt "
        "(Verordnung (EU) 2024/2847, Art. 13 Abs. 1–3 i.V.m. Anhang VII).")

    k = d.get("konformitaet") or {}
    doc.add_heading("Konformität", level=1)
    if k.get("doc_ausgestellt"):
        doc.add_paragraph(
            f"Für dieses Produkt liegt eine EU-Konformitätserklärung nach "
            f"Art. 28 i.V.m. Anhang V vor (Fassung {k.get('doc_version')}, "
            f"ausgestellt am {k.get('doc_ausgestellt_am')}).")
    else:
        doc.add_paragraph("Die EU-Konformitätserklärung ist noch nicht ausgestellt.")
    if k.get("bewertungsweg"):
        satz = f"Angewandtes Konformitätsbewertungsverfahren: Modul {k['bewertungsweg']} (Anhang VIII)."
        if k.get("nb_kennnummer"):
            satz += (f" Beteiligte notifizierte Stelle: {k.get('nb_name') or ''} "
                     f"(Kennnummer {k['nb_kennnummer']}).")
        doc.add_paragraph(satz)
    for a in d.get("erklaerung_archiv") or []:
        if a.get("sha256"):
            doc.add_paragraph(
                f"Hinterlegte Fassung {a['version']} vom {a['am']} — "
                f"SHA-256 {a['sha256'][:16]}…")

    doc.add_heading("CE-Kennzeichnung", level=1)
    ce_mark.einfuegen(doc, d.get("_record") or {}, bool(k.get("doc_ausgestellt")))

    s = d.get("support") or {}
    doc.add_heading("Unterstützungszeitraum und Updates", level=1)
    if s.get("eol"):
        doc.add_paragraph(
            f"Sicherheitsupdates werden bis zum {s['eol']} bereitgestellt"
            + (f" (Markteintritt {s['markteintritt']}, {s['jahre']} Jahre)."
               if s.get("markteintritt") else "."))
    else:
        doc.add_paragraph("Der Unterstützungszeitraum ist noch nicht festgelegt.")
    if s.get("update_kanal"):
        doc.add_paragraph(f"Bezug der Updates: {s['update_kanal']}")

    m = d.get("meldestelle") or {}
    doc.add_heading("Schwachstellen melden", level=1)
    if m.get("policy_url") or m.get("security_md") or m.get("kontakt"):
        if m.get("kontakt"):
            doc.add_paragraph(f"Kontakt: {m['kontakt']}")
        for url in (m.get("policy_url"), m.get("security_md")):
            if url:
                doc.add_paragraph(url)
    else:
        doc.add_paragraph("Eine Meldestelle ist noch nicht veröffentlicht.")

    r = d.get("risikomanagement") or {}
    doc.add_heading("Risikomanagement", level=1)
    if r.get("gefuehrt"):
        satz = "Für dieses Produkt wird eine Cybersicherheits-Risikoabschätzung geführt"
        if r.get("methode"):
            satz += f" (Methode: {r['methode']})"
        if r.get("stand"):
            satz += f", zuletzt fortgeschrieben am {r['stand']}"
        doc.add_paragraph(satz + ".")
    else:
        doc.add_paragraph("Die Risikoabschätzung wird außerhalb dieses Systems geführt.")
    doc.add_paragraph(
        "Die Abschätzung selbst ist Teil der technischen Dokumentation und "
        "wird nicht veröffentlicht: Sie beschreibt Angriffswege und "
        "Schutzmaßnahmen im Einzelnen.")

    doc.add_heading("Veröffentlichte Sicherheitshinweise", level=1)
    adv = d.get("advisories") or []
    if adv:
        doc.add_paragraph(
            "Zu folgenden behobenen Schwachstellen wurden Hinweise "
            "veröffentlicht (Anhang I Teil II Nr. 8):")
        for a in adv:
            doc.add_paragraph(
                f"{a['id']} — behoben in {a['behoben_in'] or '—'} — {a['url']}",
                style="List Bullet")
    else:
        doc.add_paragraph("Es wurden bislang keine Sicherheitshinweise veröffentlicht.")

    sb = d.get("sbom") or {}
    doc.add_heading("Software-Stückliste (SBOM)", level=1)
    doc.add_paragraph(
        (f"Eine SBOM im Format {sb.get('format') or '—'} liegt vor "
         f"(Stand {sb.get('stand') or '—'}"
         + (f", Version {sb['version']}" if sb.get("version") else "")
         + "). Sie wird auf Anfrage bereitgestellt.")
        if sb.get("vorhanden") else
        "Eine Software-Stückliste liegt derzeit nicht vor.")

    apply_base_font(doc)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_pdf(projekt_name: str, *, db_path: Path = DB_PATH,
              version: str | None = None) -> bytes:
    from shared.reports.docx_pdf import docx_bytes_to_pdf

    return docx_bytes_to_pdf(build_docx(projekt_name, db_path=db_path, version=version))


def build(projekt_name: str, *, fmt: str = "docx", db_path: Path = DB_PATH,
          version: str | None = None) -> bytes:
    if (fmt or "docx").lower() == "pdf":
        return build_pdf(projekt_name, db_path=db_path, version=version)
    return build_docx(projekt_name, db_path=db_path, version=version)


def summary_context(projekt_name: str, *, db_path: Path = DB_PATH) -> dict[str, Any]:
    """Kontext für die KI-Zusammenfassung (#1725) — ebenfalls ohne Internas."""
    d = sammle(projekt_name, db_path=db_path)
    k = d.get("konformitaet") or {}
    return {
        "reifegrad": None,
        "offene": [],
        "kundenfassung": {
            "produkt": (d.get("produkt") or {}).get("name"),
            "erklaerung_ausgestellt": bool(k.get("doc_ausgestellt")),
            "support_bis": (d.get("support") or {}).get("eol"),
            "advisories": len(d.get("advisories") or []),
            "sbom": bool((d.get("sbom") or {}).get("vorhanden")),
        },
    }
