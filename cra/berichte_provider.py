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

# #1954: ``titel_en``/``beschreibung_en`` gehören in den Katalog und **nicht**
# in einen ``TEXTE``-Katalog: Diese Liste ist Bedienoberfläche und folgt der
# Anzeigesprache des Bedieners, das Dokument folgt der Sprache des Mandanten
# (``ReportSpec.as_dict``). Beides darf auseinanderfallen — ein
# deutschsprachiger Berater erzeugt einen englischen Bericht für seinen
# Mandanten. ``norm`` bleibt in beiden Sprachen gleich (Fundstelle, kein Text).
CATALOG: list[ReportSpec] = [
    ReportSpec("gesamt", "Gesamtbericht", "CRA (EU) 2024/2847",
               "Vollständiger CRA-Bericht: Anforderungen, OWASP, Maßnahmenplan, Quellen.",
               titel_en="Overall report",
               beschreibung_en="Complete CRA report: requirements, OWASP, "
                               "action plan, sources."),
    ReportSpec("anforderungen", "Anforderungs-Status", "CRA Anhang I",
               "Kapitelweise Bewertung der CRA-Anforderungen (ohne OWASP/Maßnahmenplan).",
               titel_en="Requirement status",
               beschreibung_en="Chapter-by-chapter assessment of the CRA "
                               "requirements (without OWASP/action plan).",
               norm_en="CRA Annex I"),
    ReportSpec("massnahmen", "Maßnahmenplan", "CRA Art. 13/14",
               "Offene Lücken als Maßnahmenplan (Owner, Zieldatum).",
               titel_en="Action plan",
               beschreibung_en="Open gaps as an action plan (owner, target date)."),
    # #1748: der Vorgangsbericht je Release — Management und Ablage, nicht der
    # juristische Nachweis. Dieser Typ läuft **nicht** über cra.report_export,
    # sondern über cra.release_bericht; der Nachweis selbst
    # (cra.konformitaet_report) bleibt unberührt und wird nur zitiert. Zwei
    # Renderer für dasselbe Dokument wären zwei Wahrheiten (#1727).
    ReportSpec("release", "Release-Vorgangsbericht", "CRA Art. 3 Nr. 30, Art. 13/14",
               "Vorgang zum jüngsten Release: Ampel, Phase-1-Feststellung, "
               "wesentliche Änderung mit Begründung, Release-Checkliste in ihren "
               "drei Arten, offene Punkte, akzeptierte Restrisiken, Prüfer und "
               "Freigeber, Verweis auf die archivierten Nachweise (SHA-256).",
               titel_en="Release record report",
               beschreibung_en="Record of the most recent release: traffic "
                               "light, phase 1 determination, substantial "
                               "modification with its justification, the "
                               "release checklist in its three kinds, open "
                               "items, accepted residual risks, reviewer and "
                               "approver, reference to the archived records "
                               "(SHA-256).",
               norm_en="CRA Art. 3 No. 30, Art. 13/14"),
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
               "Ohne einzelne Risiken, offene Punkte oder interne Namen.",
               titel_en="Customer version",
               beschreibung_en="For passing on to customers: statement on "
                               "conformity and the declaration, CE marking, "
                               "support period and how to obtain updates, "
                               "reporting point, published security "
                               "advisories, state of the SBOM. Without "
                               "individual risks, open items or internal "
                               "names.",
               norm_en="CRA Annex II, Art. 28"),
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
               "der aktuelle Stand.", vorgeschrieben=True,
               titel_en="Record of conformity (per release)",
               beschreibung_en="Version-bound record: degree of fulfilment per "
                               "requirement with its legal basis, deviations "
                               "with their justification including the "
                               "accepted risk, open non-conformities, state of "
                               "Annex VII, CE marking and the conclusion of "
                               "the gate. Without a version, today's state "
                               "applies.",
               norm_en="CRA Art. 13 in conjunction with Annexes I, VII and VIII"),
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
               vorgeschrieben=True,
               titel_en="EU declaration of conformity",
               beschreibung_en="The declaration to be signed by the "
                               "manufacturer, built from the recorded Annex V "
                               "particulars. Without complete mandatory "
                               "particulars a document marked as a DRAFT is "
                               "produced that names the gaps — nothing is "
                               "printed blank in silence.",
               norm_en="CRA Art. 28 in conjunction with Annex V"),
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


def _falls_bekannt(fn: Any, **werte: Any) -> dict[str, Any]:
    """Nur die Schlüsselwörter zurückgeben, die ``fn`` auch annimmt (#1954).

    Dasselbe Verfahren wie ``shared/reports/api._zusatz``: Die Signatur wird
    gefragt, statt einen ``TypeError`` zu verschlucken. Gebraucht wird es für
    ``cra.report_export``, das die Sprache (noch) nicht kennt — so bekommt es
    sie in dem Moment, in dem es den Parameter führt, und nicht erst, wenn
    jemand an diese Datei denkt. Eine Zuordnungsliste „welcher Renderer kann
    schon was" wäre die Spiegel-Liste aus #1731/#1735.
    """
    import inspect

    try:
        erlaubt = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return {}
    hat_rest = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in erlaubt.values())
    return {k: v for k, v in werte.items()
            if v is not None and (k in erlaubt or hat_rest)}


def render(typ: str, fmt: str, *, projekt: str, von: str | None = None,
           bis: str | None = None, version: str | None = None,
           sprache: str | None = None, **_ctx: Any) -> bytes:
    """Erzeugt den CRA-Bericht für ``projekt`` als DOCX/PDF-Bytes (kein Zeitraum).

    ``version`` wählt beim Typ ``release`` den Release-Vorgang. Das
    Berichts-Center reicht die Angabe heute nicht durch — ohne sie nimmt der
    Bericht den jüngsten Vorgang (siehe ``release_bericht.waehle_vorgang``).

    ``sprache`` übersteuert die Sprache des Mandanten für diesen einen Lauf
    (#1954). **Der Parameter muss hier stehen**, nicht nur in ``**_ctx``
    aufgefangen werden: ``shared/reports/api._zusatz`` reicht ihn durch, weil
    ``render`` ein ``**``-Rest hat — ohne ausdrückliche Weitergabe an den
    Renderer käme er an und würde verworfen (die Fehlerklasse aus #1805).
    Ohne Angabe entscheidet ``firmen.sprache``, fail-open auf Deutsch.
    """
    from cra.db import load_bewertungen, load_projekt
    from cra.report_export import export_report_docx, export_report_pdf

    if typ == "kundenfassung":
        # Eigener Renderer mit eigener Datensammlung — bewusst nicht über
        # cra.report_export, dessen Bausteine die internen Angaben enthalten.
        from cra import kundenfassung
        return kundenfassung.build(projekt, fmt=fmt, version=version,
                                   sprache=sprache)

    if typ == "release":
        # Eigener Weg: Der Vorgangsbericht liest den Vorgang, nicht die
        # Anforderungs-Bewertungen, und läuft deshalb nicht über die
        # Options-Flags von cra.report_export. Ein fehlendes Projekt ist hier
        # kein Abbruch — ein Entwurf muss berichtbar sein (#1748).
        from cra import release_bericht
        return release_bericht.build(projekt, fmt=fmt, version=version,
                                     db_path=DB_PATH, sprache=sprache)

    if typ == "konformitaetsnachweis":
        # Eigener Weg: Der Nachweis liest das Konformitäts-Gate, nicht die
        # Anforderungs-Bewertungen — und ist damit auch für ein Projekt ohne
        # Stammdaten erzeugbar. Dieselbe Funktion wie der Knopf im Releases-Tab
        # (#1776); ein zweiter Renderer wären zwei Konformitätsaussagen.
        from cra import konformitaet_report
        return konformitaet_report.build(projekt, fmt=fmt, version=version,
                                         db_path=DB_PATH, sprache=sprache)

    if typ == "konformitaetserklaerung":
        # Eigener Weg wie beim Release-Vorgang: Die Erklärung liest den
        # DoC-Datensatz, nicht die Anforderungs-Bewertungen. Ein fehlendes
        # Projekt ist auch hier kein Abbruch — der Entwurf ist der Weg, über
        # den man die Lücken sieht (#1753).
        from cra import doc_export
        return doc_export.build(projekt, fmt=fmt, release_version=(version or ""),
                                db_path=DB_PATH, sprache=sprache)

    proj = load_projekt(DB_PATH, projekt)
    if not proj:
        raise ValueError("Projekt nicht gefunden")
    opts = _OPTS.get(typ, _OPTS["gesamt"])
    out_dir = Path(tempfile.mkdtemp(prefix="cra_report_"))
    renderer = export_report_docx if fmt == "docx" else export_report_pdf
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
        # Gefragt wird die Signatur von ``export_report_docx`` — auch für PDF:
        # ``export_report_pdf(**kwargs)`` nimmt alles an und reicht es genau
        # dorthin weiter. Gegen den PDF-Einstieg geprüft, bekäme der
        # DOCX-Renderer ein Schlüsselwort, das er nicht kennt (``TypeError``,
        # und zwar nur im PDF-Weg).
        **_falls_bekannt(export_report_docx, sprache=sprache),
    )
    path = renderer(**kwargs)
    return Path(path).read_bytes()
