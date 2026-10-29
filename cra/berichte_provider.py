"""CRA-Adapter für das geteilte Berichts-Center (Sprint #35, #1384).

Liefert Katalog + Render-Callable; die eigentliche Dokumenterzeugung bleibt im
bestehenden :mod:`cra.report_export` (kein Re-Write). Mehrere Berichtstypen werden
auf Options-Kombinationen desselben Generators abgebildet — gleiche Optik wie SOC.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from shared.reports.core import ReportSpec

DB_PATH = Path("data/db/cra.sqlite")

CATALOG: list[ReportSpec] = [
    ReportSpec("gesamt", "Gesamtbericht", "CRA (EU) 2024/2847",
               "Vollständiger CRA-Bericht: Anforderungen, OWASP, Maßnahmenplan, Quellen."),
    ReportSpec("anforderungen", "Anforderungs-Status", "CRA Annex I",
               "Kapitelweise Bewertung der CRA-Anforderungen (ohne OWASP/Maßnahmenplan)."),
    ReportSpec("massnahmen", "Maßnahmenplan", "CRA Art. 13/14",
               "Offene Lücken als Maßnahmenplan (Owner, Zieldatum)."),
    # #1748: der Vorgangsbericht je Release — Management und Ablage, nicht der
    # juristische Nachweis. Dieser Typ läuft **nicht** über cra.report_export,
    # sondern über cra.release_bericht; der Nachweis selbst
    # (cra.konformitaet_report) bleibt unberührt und wird nur zitiert. Zwei
    # Renderer für dasselbe Dokument wären zwei Wahrheiten (#1727).
    ReportSpec("release", "Release-Vorgangsbericht", "CRA Art. 3 Nr. 30, Art. 13/14",
               "Vorgang zum jüngsten Release: Ampel, Phase-1-Feststellung, "
               "wesentliche Änderung mit Begründung, Release-Checkliste in ihren "
               "drei Arten, offene Punkte, akzeptierte Restrisiken, Prüfer und "
               "Freigeber, Verweis auf die archivierten Nachweise (SHA-256)."),
    # #1758: die Fassung für den Kunden. Alle übrigen Typen sind interne
    # Dokumente — offene Punkte, Bewertungslücken, akzeptierte Restrisiken,
    # Prüfer und Freigeber. Wer dem Kunden „etwas zur CRA" geben wollte, hatte
    # bisher nur die Wahl zwischen einem internen Dokument und gar nichts.
    # Gebaut wird **additiv**: cra.kundenfassung sammelt ausdrücklich erlaubte
    # Angaben ein, statt aus dem internen Bericht etwas wegzulassen — sonst
    # landet beim nächsten neuen internen Feld etwas beim Kunden.
    ReportSpec("kundenfassung", "Kundenfassung", "CRA Anhang II, Art. 28",
               "Für die Weitergabe an Kunden: Konformitätsaussage und Erklärung, "
               "CE-Kennzeichnung, Unterstützungszeitraum und Update-Bezug, "
               "Meldestelle, veröffentlichte Sicherheitshinweise, SBOM-Stand. "
               "Ohne einzelne Risiken, offene Punkte oder interne Namen."),
    # #1776: der Konformitätsnachweis je Release — das Dokument, das belegt, dass
    # das Release die essenziellen Anforderungen erfüllt. Er existierte seit
    # #1610, hing aber allein am Knopf im Releases-Tab. Wer ihn im
    # Berichts-Center suchte, fand den nächstliegenden Typ und bekam den
    # Readiness-Bericht: gleicher Gegenstand, aber ohne Rechtsgrundlage je
    # Anforderung, ohne begründete Abweichungen, ohne Annex-VII-Stand. Renderer:
    # cra.konformitaet_report — nicht cra.doc_export, das ist die Erklärung.
    ReportSpec("konformitaetsnachweis", "Konformitätsnachweis (je Release)",
               "CRA Art. 13 i.V.m. Anhang I, VII, VIII",
               "Versionsgebundener Nachweis: Erfüllungsgrad je Anforderung mit "
               "Rechtsgrundlage, begründete Abweichungen samt akzeptiertem "
               "Risiko, offene Nicht-Konformitäten, Annex-VII-Stand, "
               "CE-Kennzeichnung und das Gate-Fazit. Ohne Versionsangabe gilt "
               "der aktuelle Stand.", vorgeschrieben=True),
    # #1753: die EU-Konformitätserklärung selbst — das Dokument, das der
    # Hersteller unterschreibt und das dem Produkt beiliegt. Als Berichtstyp,
    # damit DOCX, PDF, Historie und **Word-Vorlage** (#1735) ohne Zusatzcode
    # kommen; ein eigener Vorlagen-Modulschlüssel hätte die Verdrahtung an fünf
    # Stellen verdoppelt (Fehlerklasse #1731). Renderer: cra.doc_export —
    # nicht cra.konformitaet_report, das ist der Nachweis.
    ReportSpec("konformitaetserklaerung", "EU-Konformitätserklärung",
               "CRA Art. 28 i.V.m. Anhang V",
               "Die vom Hersteller zu unterzeichnende Erklärung aus den "
               "erfassten Anhang-V-Angaben. Ohne vollständige Pflichtangaben "
               "entsteht ein als ENTWURF gekennzeichnetes Dokument, das die "
               "Lücken benennt — nichts wird stillschweigend leer gedruckt.",
               vorgeschrieben=True),
]

# Berichtstyp → Options-Flags des bestehenden Generators
_OPTS: dict[str, dict[str, bool]] = {
    "gesamt": dict(incl_massnahmen=True, incl_details=True, incl_owasp=True, incl_referenzen=True),
    "anforderungen": dict(incl_massnahmen=False, incl_details=True, incl_owasp=False, incl_referenzen=True),
    "massnahmen": dict(incl_massnahmen=True, incl_details=False, incl_owasp=False, incl_referenzen=False),
}


def catalog() -> list[ReportSpec]:
    return CATALOG


def summary_context(projekt: str) -> dict:
    """Kennzahlen-Kontext für die KI-Management-Zusammenfassung (#1393).

    ``reifegrad`` und ``offene`` sind der Vertrag von
    :mod:`shared.reports.summary` — nur über diese zwei Schlüssel kommen die
    Zahlen überhaupt in den Prompt. Zusatzschlüssel gehen seit #1725 als
    JSON-Block mit; genutzt wird das hier für den Release-Vorgang (#1748), damit
    die Zusammenfassung nicht nur den Produktzustand kennt, sondern auch, ob das
    jüngste Release geprüft und freigegeben ist.
    """
    from cra.db import load_bewertungen
    from cra.requirements import berechne_reifegrad, load_merged_anforderungen
    bew = load_bewertungen(DB_PATH, projekt)
    scores = {rid: int(b.get("bewertung", 0) or 0) for rid, b in bew.items()}
    anf = load_merged_anforderungen(DB_PATH)
    reif = berechne_reifegrad(scores, anforderungen=anf)
    offene = [{"id": a["id"], "titel": a.get("titel", ""), "bewertung": scores.get(a["id"], 0)}
              for a in anf if scores.get(a["id"], 0) < 3][:50]
    ctx: dict[str, Any] = {"reifegrad": reif, "offene": offene}
    try:
        from cra import release_bericht
        ctx.update(release_bericht.summary_kontext(projekt, db_path=DB_PATH))
    except Exception:  # noqa: BLE001 — Zusatzangabe darf die Zusammenfassung nicht kippen
        pass
    return ctx


def render(typ: str, fmt: str, *, projekt: str, von: str | None = None,
           bis: str | None = None, version: str | None = None,
           **_ctx: Any) -> bytes:
    """Erzeugt den CRA-Bericht für ``projekt`` als DOCX/PDF-Bytes (kein Zeitraum).

    ``version`` wählt beim Typ ``release`` den Release-Vorgang. Das
    Berichts-Center reicht die Angabe heute nicht durch — ohne sie nimmt der
    Bericht den jüngsten Vorgang (siehe ``release_bericht.waehle_vorgang``).
    """
    from cra.db import load_bewertungen, load_projekt
    from cra.report_export import export_report_docx, export_report_pdf

    if typ == "kundenfassung":
        # Eigener Renderer mit eigener Datensammlung — bewusst nicht über
        # cra.report_export, dessen Bausteine die internen Angaben enthalten.
        from cra import kundenfassung
        return kundenfassung.build(projekt, fmt=fmt, version=version)

    if typ == "release":
        # Eigener Weg: Der Vorgangsbericht liest den Vorgang, nicht die
        # Anforderungs-Bewertungen, und läuft deshalb nicht über die
        # Options-Flags von cra.report_export. Ein fehlendes Projekt ist hier
        # kein Abbruch — ein Entwurf muss berichtbar sein (#1748).
        from cra import release_bericht
        return release_bericht.build(projekt, fmt=fmt, version=version,
                                     db_path=DB_PATH)

    if typ == "konformitaetsnachweis":
        # Eigener Weg: Der Nachweis liest das Konformitäts-Gate, nicht die
        # Anforderungs-Bewertungen — und ist damit auch für ein Projekt ohne
        # Stammdaten erzeugbar. Dieselbe Funktion wie der Knopf im Releases-Tab
        # (#1776); ein zweiter Renderer wären zwei Konformitätsaussagen.
        from cra import konformitaet_report
        return konformitaet_report.build(projekt, fmt=fmt, version=version,
                                         db_path=DB_PATH)

    if typ == "konformitaetserklaerung":
        # Eigener Weg wie beim Release-Vorgang: Die Erklärung liest den
        # DoC-Datensatz, nicht die Anforderungs-Bewertungen. Ein fehlendes
        # Projekt ist auch hier kein Abbruch — der Entwurf ist der Weg, über
        # den man die Lücken sieht (#1753).
        from cra import doc_export
        return doc_export.build(projekt, fmt=fmt, release_version=(version or ""),
                                db_path=DB_PATH)

    proj = load_projekt(DB_PATH, projekt)
    if not proj:
        raise ValueError("Projekt nicht gefunden")
    opts = _OPTS.get(typ, _OPTS["gesamt"])
    out_dir = Path(tempfile.mkdtemp(prefix="cra_report_"))
    kwargs = dict(
        out_dir=out_dir,
        projekt_name=projekt,
        unternehmen=proj.get("unternehmen", ""),
        produkt=proj.get("produkt", ""),
        produktklasse=proj.get("produktklasse", "default"),
        berater=proj.get("berater", ""),
        bewertungen_raw=load_bewertungen(DB_PATH, projekt),
        db_path=DB_PATH,
        **opts,
    )
    path = export_report_docx(**kwargs) if fmt == "docx" else export_report_pdf(**kwargs)
    return Path(path).read_bytes()
