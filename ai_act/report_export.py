"""AI Act report export (Markdown, DOCX, PDF) — mit Pflicht-Doku-Nachweisen.

DIE SPRACHE GEHÖRT DEM MANDANTEN (#1954)
Dieser Bericht geht an den Mandanten (und von dort an Prüfer und Behörden);
über seine Sprache entscheidet deshalb ``firmen.sprache`` und nicht der
Bearbeiter, der ihn zufällig erzeugt. Die Prosa liegt in :data:`TEXTE` und
wird über ``shared/reports/texte`` gedruckt, aufgelöst in jeder der drei
Export-Funktionen selbst — nicht beim Aufrufer: Das Berichts-Center reicht
``sprache`` nur durch, wenn die Signatur den Parameter führt
(``shared/reports/api._zusatz``). Fail-open auf Deutsch.

Der Modulschlüssel ist ``aiact`` und **nicht** ``ai_act`` — siehe :data:`MODUL`.

Ohne ``sprache`` ändert sich nichts: Das deutsche Dokument bleibt
byte-identisch, damit jeder Bestandstest ein Regressionsschutz bleibt.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from ai_act.db import (
    load_bewertungen, load_projekt,
    load_system_doku, load_data_governance, linked_a3_risks,
    load_human_oversight, load_pmm,
)
from ai_act.requirements import AI_ACT_REQUIREMENTS, BEWERTUNG_SKALA, berechne_reifegrad
from shared.reports import texte as _rt


#: Modulschlüssel für die Sprachauflösung. **Nicht** ``ai_act``: Aufgelöst
#: wird über ``shared/templates/schema.MODULE_DB``, und dort heißt das Modul
#: ``aiact``. Ein falscher Schlüssel löst den Mandanten nicht auf und sieht
#: dabei genau wie „bei diesem Mandanten ist keine Sprache gesetzt" aus —
#: dieselbe Klasse wie #1805/#1892. Derselbe Wert steht in
#: ``ai_act/berichte_provider.MODUL`` und ``ai_act/doc_export.MODUL``.
MODUL = "aiact"


#: Die Prosa dieses Berichts je Sprache (#1954).
#:
#: KONVENTION: Die Werte tragen **keine** Satzzeichen. Doppelpunkt, ``**``
#: und Zeilenpräfixe (``- ``, ``## ``) stehen im Code, weil sie Struktur sind
#: und in beiden Sprachen gleich — so gibt es je Beschriftung genau einen
#: Eintrag, auch wenn sie an einer Stelle fett in Markdown und an der anderen
#: als Run im DOCX erscheint. Zwei Einträge mit demselben Wort wären zwei
#: Gelegenheiten, nur einen davon zu ändern.
#:
#: Amtliche englische Begriffe der Verordnung (EU) 2024/1689: ``Anbieter`` →
#: *provider*, ``Risikomanagement`` → *risk management*, ``Daten-Governance``
#: → *data governance*, ``menschliche Aufsicht`` → *human oversight*,
#: ``Konformitätsbewertung`` → *conformity assessment*, ``Beobachtung nach dem
#: Inverkehrbringen`` → *post-market monitoring*, ``Reifegrad`` → *maturity*,
#: ``Pflicht-Doku`` → *mandatory documentation*. Die Bezeichnung der Anlage
#: folgt dem Amtsblatt (``Anhang IV`` → *Annex IV*), die **Ziffern nie**
#: (#1763/#1792).
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        # ── Titel und Überschriften ──────────────────────────────────────
        # Zwei Titel-Einträge, weil der Bestand zwei Gedankenstriche führt:
        # Markdown schreibt den Halbgeviertstrich (–), das DOCX den
        # Geviertstrich (—). Das ist ein Schönheitsfehler im **deutschen**
        # Bericht; er bleibt, weil er sonst hier stillschweigend begradigt
        # würde und das Dokument nicht mehr byte-identisch wäre. Gemeldet.
        "t_titel_md": "AI Act Readiness Report – {projekt}",
        "t_titel_docx": "AI Act Readiness Report — {projekt}",
        "t_a6": "A6 — Risk-Tier (AI Act Annex III)",
        "t_a6_docx": "Risk-Tier (Annex III)",
        "t_a1": "A1 — Technische System-Doku (Art. 11 + Annex IV)",
        "t_a2": "A2 — Data-Governance (Art. 10)",
        "t_a3": "A3 — Risk-Management (Art. 9) — {n} Risiken",
        "t_a4": "A4 — Human-Oversight (Art. 14)",
        "t_a5": "A5 — Post-Market-Monitoring (Art. 72-73)",
        "t_anforderungen": "Anforderungen",
        "t_pflicht_doku": "Pflicht-Dokumentation (Nachweise)",
        "t_anforderungs_bewertungen": "Anforderungs-Bewertungen",
        # ── Sätze ────────────────────────────────────────────────────────
        "erstellt": "Erstellt: {datum} · Verordnung (EU) 2024/1689 (AI Act)",
        # Datumsformat statt eines festen Musters: `%d.%m.%Y` liest ein
        # englischer Leser als Monat/Tag, und `%B` hinge an der Locale des
        # Containers und schriebe deutsche Monatsnamen in ein englisches
        # Dokument. Englisch bekommt deshalb ISO 8601.
        "datum_format": "%d.%m.%Y",
        "pd_ja": "Ja (Rechtsgrundlage: {basis})",
        # ── Beschriftungen ──────────────────────────────────────────────
        "l_reifegrad": "Reifegrad",
        "l_bewertet": "Bewertet",
        "l_organisation": "Organisation",
        "l_produkt": "Produkt/System",
        "l_klasse": "Klasse",
        "l_annex_iii_kategorie": "Annex-III-Kategorie",
        "l_konformitaetsbewertung": "Konformitätsbewertung",
        "l_begruendung": "Begründung",
        "l_personenbezogene_daten": "Personenbezogene Daten",
        "l_kapitel": "Kapitel",
        "l_bewertung": "Bewertung",
        "l_ref": "Ref",
        "l_beschreibung": "Beschreibung",
        "l_kommentar": "Kommentar",
        "l_massnahme": "Maßnahme",
        # A1 — technische System-Doku
        "l_system_name": "System-Name",
        "l_version": "Version",
        "l_provider": "Anbieter",
        "l_intended_purpose": "Intended Purpose",
        "l_architecture": "Architektur",
        "l_training_methodology": "Training-Methodology",
        "l_computational_resources": "Compute-Resources",
        "l_test_methodology": "Test-Methodology",
        "l_cybersecurity": "Cybersecurity",
        "l_accuracy_robustness": "Accuracy/Robustness",
        # A2 — Daten-Governance
        "l_training_data_source": "Training-Data-Source",
        "l_training_data_size": "Training-Data-Size",
        "l_validation_data_split": "Validation-Split",
        "l_test_data_split": "Test-Split",
        "l_data_collection_method": "Collection-Method",
        "l_data_labelling_method": "Labelling-Method",
        "l_bias_assessment": "Bias-Assessment",
        "l_bias_mitigation": "Bias-Mitigation",
        "l_representativeness": "Representativeness",
        "l_legal_basis_gdpr": "GDPR-Rechtsgrundlage",
        # A4 — menschliche Aufsicht
        "l_oversight_mode": "Modus",
        "l_intervention_mechanisms": "Intervention-Mechanismen",
        "l_monitoring_interface": "Monitoring-Interface",
        "l_output_interpretation_aids": "Output-Interpretation-Hilfen",
        "l_abnormal_behavior_detection": "Abnormal-Behavior-Detection",
        "l_training_program": "Schulungs-Programm",
        # A5 — Beobachtung nach dem Inverkehrbringen
        "l_monitoring_plan": "Monitoring-Plan",
        "l_performance_metrics": "Performance-Metrics",
        "l_drift_detection": "Drift-Detection",
        "l_user_feedback_channel": "User-Feedback-Channel",
        "l_incident_threshold": "Incident-Threshold",
        "l_market_surveillance_contact": "Marktaufsicht",
        # Zwei Einträge, weil der Bestand die Fundstelle nur im DOCX nennt.
        "l_reporting_sla": "Reporting-SLA",
        "l_reporting_sla_art73": "Reporting-SLA (Art. 73)",
        # ── Tabellenköpfe ───────────────────────────────────────────────
        "h_id": "ID",
        "h_titel": "Titel",
        "h_phase": "Phase",
        "h_kategorie": "Kategorie",
        "h_score": "Score",
        "h_status": "Status",
    },
    "en": {
        "t_titel_md": "AI Act Readiness Report – {projekt}",
        "t_titel_docx": "AI Act Readiness Report — {projekt}",
        "t_a6": "A6 — Risk tier (AI Act Annex III)",
        "t_a6_docx": "Risk tier (Annex III)",
        "t_a1": "A1 — Technical system documentation (Art. 11 + Annex IV)",
        "t_a2": "A2 — Data governance (Art. 10)",
        "t_a3": "A3 — Risk management (Art. 9) — {n} risks",
        "t_a4": "A4 — Human oversight (Art. 14)",
        "t_a5": "A5 — Post-market monitoring (Art. 72-73)",
        "t_anforderungen": "Requirements",
        "t_pflicht_doku": "Mandatory documentation (evidence)",
        "t_anforderungs_bewertungen": "Requirement assessments",
        "erstellt": "Created: {datum} · Regulation (EU) 2024/1689 (AI Act)",
        "datum_format": "%Y-%m-%d",
        "pd_ja": "Yes (legal basis: {basis})",
        "l_reifegrad": "Maturity",
        "l_bewertet": "Assessed",
        "l_organisation": "Organisation",
        "l_produkt": "Product/system",
        "l_klasse": "Class",
        "l_annex_iii_kategorie": "Annex III category",
        "l_konformitaetsbewertung": "Conformity assessment",
        "l_begruendung": "Rationale",
        "l_personenbezogene_daten": "Personal data",
        "l_kapitel": "Chapter",
        "l_bewertung": "Assessment",
        "l_ref": "Ref",
        "l_beschreibung": "Description",
        "l_kommentar": "Comment",
        "l_massnahme": "Measure",
        "l_system_name": "System name",
        "l_version": "Version",
        "l_provider": "Provider",
        "l_intended_purpose": "Intended purpose",
        "l_architecture": "Architecture",
        "l_training_methodology": "Training methodology",
        "l_computational_resources": "Computational resources",
        "l_test_methodology": "Test methodology",
        "l_cybersecurity": "Cybersecurity",
        "l_accuracy_robustness": "Accuracy/robustness",
        "l_training_data_source": "Training data source",
        "l_training_data_size": "Training data size",
        "l_validation_data_split": "Validation split",
        "l_test_data_split": "Test split",
        "l_data_collection_method": "Collection method",
        "l_data_labelling_method": "Labelling method",
        "l_bias_assessment": "Bias assessment",
        "l_bias_mitigation": "Bias mitigation",
        "l_representativeness": "Representativeness",
        "l_legal_basis_gdpr": "GDPR legal basis",
        "l_oversight_mode": "Mode",
        "l_intervention_mechanisms": "Intervention mechanisms",
        "l_monitoring_interface": "Monitoring interface",
        "l_output_interpretation_aids": "Output interpretation aids",
        # EU-Englisch schreibt „behaviour"; der deutsche Bestand trägt die
        # US-Schreibung im Feldnamen, der Feldname selbst bleibt unberührt.
        "l_abnormal_behavior_detection": "Abnormal behaviour detection",
        "l_training_program": "Training programme",
        "l_monitoring_plan": "Monitoring plan",
        "l_performance_metrics": "Performance metrics",
        "l_drift_detection": "Drift detection",
        "l_user_feedback_channel": "User feedback channel",
        "l_incident_threshold": "Incident threshold",
        "l_market_surveillance_contact": "Market surveillance",
        "l_reporting_sla": "Reporting SLA",
        "l_reporting_sla_art73": "Reporting SLA (Art. 73)",
        "h_id": "ID",
        "h_titel": "Title",
        "h_phase": "Phase",
        "h_kategorie": "Category",
        "h_score": "Score",
        "h_status": "Status",
    },
}

_t = _rt.macher(TEXTE)


# ─────────────────────────────────────────────────────────────────────────
# Daten-Helper
# ─────────────────────────────────────────────────────────────────────────

# #1765: Die alte Inline-Kennzeichnung („🤖 KI-generiert … fachlich zu
# prüfen") steht in Bestandstexten und gehört nicht in ein Dokument. Sie
# wird beim Drucken entfernt; die Herkunft führt `shared/ki_herkunft`.
from shared.ki_herkunft import ohne_marker as _ohne_ki_marker


# ── #1954: Katalogeinträge in der Sprache des Dokuments ──────────────────
# `AI_ACT_REQUIREMENTS` und `BEWERTUNG_SKALA` werden hier direkt gelesen;
# ohne diesen Helfer käme die englische Fassung (`titel_en`,
# `beschreibung_en`, `label_en`) nie an — die Übersetzung wäre vorhanden und
# wirkungslos (der Defekt aus #1735). `uebersetze` liefert **Kopien**: Die
# Modul-Literale werden von mehreren Anfragen gleichzeitig gelesen und
# dürfen nicht an Ort und Stelle geändert werden.
def _kat(eintrag: dict, sp: str) -> dict:
    from shared.katalog_sprache import uebersetze

    return uebersetze(eintrag or {}, sp)


def _safe_filename(s: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in s)


def _gather_pflicht_doku(db_path: Path, projekt_name: str) -> dict[str, Any]:
    return {
        'system_doku': load_system_doku(db_path, projekt_name) or {},
        'data_governance': load_data_governance(db_path, projekt_name) or {},
        'risks': linked_a3_risks(db_path, projekt_name),
        'human_oversight': load_human_oversight(db_path, projekt_name) or {},
        'pmm': load_pmm(db_path, projekt_name) or {},
    }


def _gather_risk_tier(projekt: dict) -> dict[str, Any]:
    try:
        meta = json.loads(projekt.get('meta_json') or '{}')
        return (meta.get('aiact') or {}).get('risk_tier') or {}
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────
# Markdown (existing — erweitert um Pflicht-Doku)
# ─────────────────────────────────────────────────────────────────────────

def export_markdown(*, db_path: Path, projekt_name: str, out_dir: Path,
                    sprache: str | None = None) -> Path:
    """Markdown-Fassung des Berichts.

    ``sprache`` übersteuert die Sprache des Mandanten für diesen einen Lauf;
    ohne Angabe entscheidet ``firmen.sprache`` (#1954).
    """
    sp = _rt.aufloesen(MODUL, projekt_name, sprache)
    out_dir.mkdir(parents=True, exist_ok=True)
    proj = load_projekt(db_path, projekt_name) or {}
    bew_raw = load_bewertungen(db_path, projekt_name)
    bew = {rid: int(d.get("bewertung", 0) or 0) for rid, d in bew_raw.items()}
    reife = berechne_reifegrad(bew)
    pdoku = _gather_pflicht_doku(db_path, projekt_name)
    tier = _gather_risk_tier(proj)

    def _label(val: int) -> str:
        return str(_kat(BEWERTUNG_SKALA.get(val, {}), sp).get("label", str(val)))

    lines: list[str] = []
    lines.append(f"# {_t(sp, 't_titel_md', projekt=projekt_name)}")
    lines.append("")
    # `ampel` ist der **Datenwert** ('gruen'|'orange'|'rot') und wird hier roh
    # gedruckt — schon im deutschen Bericht. Das bleibt so: Eine Übersetzung
    # nur fürs Englische würde einen vorhandenen Mangel in einer Sprache
    # verdecken und in der anderen stehen lassen. Gemeldet, nicht geglättet.
    lines.append(f"- {_t(sp, 'l_reifegrad')}: {float(reife.get('gesamt_pct', 0.0) or 0.0):.0f}% ({reife.get('ampel','')})")
    lines.append(f"- {_t(sp, 'l_bewertet')}: {int(reife.get('bewertete_count', 0) or 0)}/{int(reife.get('gesamt_count', 0) or 0)}")
    org = str(proj.get("organisation") or "").strip()
    prod = str(proj.get("produkt") or "").strip()
    if org: lines.append(f"- {_t(sp, 'l_organisation')}: {org}")
    if prod: lines.append(f"- {_t(sp, 'l_produkt')}: {prod}")
    lines.append("")

    # A6 Risk-Tier
    if tier.get('tier'):
        lines.append(f"## {_t(sp, 't_a6')}")
        lines.append(f"- **{_t(sp, 'l_klasse')}:** `{tier['tier']}`")
        if tier.get('annex_iii_kategorie'):
            lines.append(f"- **{_t(sp, 'l_annex_iii_kategorie')}:** {tier['annex_iii_kategorie']}")
        if tier.get('konformitaetsbewertung'):
            lines.append(f"- **{_t(sp, 'l_konformitaetsbewertung')}:** {tier['konformitaetsbewertung']}")
        if tier.get('begruendung'):
            lines.append(f"- **{_t(sp, 'l_begruendung')}:** {tier['begruendung']}")
        lines.append("")

    # Pflicht-Doku-Sections
    sd = pdoku['system_doku']
    if sd:
        lines.append(f"## {_t(sp, 't_a1')}")
        for k, label in [('system_name', _t(sp, 'l_system_name')), ('version', _t(sp, 'l_version')),
                          ('provider', _t(sp, 'l_provider')), ('intended_purpose', _t(sp, 'l_intended_purpose')),
                          ('architecture', _t(sp, 'l_architecture')),
                          ('training_methodology', _t(sp, 'l_training_methodology')),
                          ('computational_resources', _t(sp, 'l_computational_resources')),
                          ('test_methodology', _t(sp, 'l_test_methodology')),
                          ('cybersecurity_measures', _t(sp, 'l_cybersecurity')),
                          ('accuracy_robustness', _t(sp, 'l_accuracy_robustness'))]:
            if sd.get(k):
                lines.append(f"- **{label}:** {sd[k]}")
        lines.append("")

    dg = pdoku['data_governance']
    if dg:
        lines.append(f"## {_t(sp, 't_a2')}")
        for k, label in [('training_data_source', _t(sp, 'l_training_data_source')),
                          ('training_data_size', _t(sp, 'l_training_data_size')),
                          ('validation_data_split', _t(sp, 'l_validation_data_split')),
                          ('test_data_split', _t(sp, 'l_test_data_split')),
                          ('data_collection_method', _t(sp, 'l_data_collection_method')),
                          ('data_labelling_method', _t(sp, 'l_data_labelling_method')),
                          ('bias_assessment', _t(sp, 'l_bias_assessment')),
                          ('bias_mitigation', _t(sp, 'l_bias_mitigation')),
                          ('representativeness', _t(sp, 'l_representativeness'))]:
            if dg.get(k):
                lines.append(f"- **{label}:** {dg[k]}")
        if dg.get('personal_data_used'):
            lines.append(f"- **{_t(sp, 'l_personenbezogene_daten')}:** "
                         f"{_t(sp, 'pd_ja', basis=dg.get('legal_basis_gdpr', '?'))}")
        lines.append("")

    risks = pdoku['risks']
    if risks:
        lines.append(f"## {_t(sp, 't_a3', n=len(risks))}")
        lines.append("")
        _hdr = [_t(sp, 'h_id'), _t(sp, 'h_titel'), _t(sp, 'h_phase'),
                _t(sp, 'h_kategorie'), _t(sp, 'h_score'), _t(sp, 'h_status')]
        lines.append("| " + " | ".join(_hdr) + " |")
        lines.append("|---|---|---|---|---|---|")
        for r in risks:
            lines.append(f"| {r.get('risk_id','')} | {r.get('titel','')} | {r.get('lifecycle_phase','')} | "
                         f"{r.get('risk_category','')} | {r.get('risk_score','')} | {r.get('status','')} |")
        lines.append("")

    ho = pdoku['human_oversight']
    if ho:
        lines.append(f"## {_t(sp, 't_a4')}")
        for k, label in [('oversight_mode', _t(sp, 'l_oversight_mode')),
                          ('intervention_mechanisms', _t(sp, 'l_intervention_mechanisms')),
                          ('monitoring_interface', _t(sp, 'l_monitoring_interface')),
                          ('output_interpretation_aids', _t(sp, 'l_output_interpretation_aids')),
                          ('abnormal_behavior_detection', _t(sp, 'l_abnormal_behavior_detection')),
                          ('training_program', _t(sp, 'l_training_program'))]:
            if ho.get(k):
                lines.append(f"- **{label}:** {ho[k]}")
        lines.append("")

    pmm = pdoku['pmm']
    if pmm:
        lines.append(f"## {_t(sp, 't_a5')}")
        for k, label in [('monitoring_plan', _t(sp, 'l_monitoring_plan')),
                          ('performance_metrics', _t(sp, 'l_performance_metrics')),
                          ('drift_detection', _t(sp, 'l_drift_detection')),
                          ('user_feedback_channel', _t(sp, 'l_user_feedback_channel')),
                          ('incident_threshold', _t(sp, 'l_incident_threshold')),
                          ('market_surveillance_contact', _t(sp, 'l_market_surveillance_contact')),
                          ('serious_incident_reporting_sla', _t(sp, 'l_reporting_sla'))]:
            if pmm.get(k):
                lines.append(f"- **{label}:** {pmm[k]}")
        lines.append("")

    # Anforderungen (existing)
    lines.append(f"## {_t(sp, 't_anforderungen')}")
    lines.append("")
    for req in (_kat(r, sp) for r in AI_ACT_REQUIREMENTS):
        rid = str(req.get("id") or "")
        if not rid: continue
        r = bew_raw.get(rid, {})
        score = int(r.get("bewertung", 0) or 0)
        kom = _ohne_ki_marker(r.get("kommentar", "")).strip()
        mass = str(r.get("massnahme", "") or "").strip()
        lines.append(f"### {rid} – {req.get('titel','')}")
        lines.append(f"- {_t(sp, 'l_kapitel')}: {req.get('kapitel','')}")
        lines.append(f"- {_t(sp, 'l_bewertung')}: {score} – {_label(score)}")
        if req.get("ref"):
            lines.append(f"- {_t(sp, 'l_ref')}: {req.get('ref')}")
        if req.get("beschreibung"):
            lines.append(f"- {_t(sp, 'l_beschreibung')}: {str(req.get('beschreibung') or '').strip()}")
        if kom: lines.append(f"- {_t(sp, 'l_kommentar')}: {kom}")
        if mass: lines.append(f"- {_t(sp, 'l_massnahme')}: {mass}")
        lines.append("")

    out_path = out_dir / f"AI-Act-Report_{_safe_filename(projekt_name)}.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


# ─────────────────────────────────────────────────────────────────────────
# DOCX (neu)
# ─────────────────────────────────────────────────────────────────────────

def export_docx(*, db_path: Path, projekt_name: str, out_dir: Path,
                sprache: str | None = None) -> Path:
    """DOCX-Fassung des Berichts.

    ``sprache`` übersteuert die Sprache des Mandanten für diesen einen Lauf;
    ohne Angabe entscheidet ``firmen.sprache`` (#1954).
    """
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor

    sp = _rt.aufloesen(MODUL, projekt_name, sprache)
    out_dir.mkdir(parents=True, exist_ok=True)
    proj = load_projekt(db_path, projekt_name) or {}
    bew_raw = load_bewertungen(db_path, projekt_name)
    pdoku = _gather_pflicht_doku(db_path, projekt_name)
    tier = _gather_risk_tier(proj)

    doc = Document()
    # #1614 A4; #1954 Dokumentsprache (`w:lang`) nur bei Abweichung von der
    # Standardsprache — `None` heißt „nicht anfassen" und hält das deutsche
    # Dokument byte-identisch (Muster `ai_act/doc_export`).
    from shared.reports.docx_pdf import set_a4 as _a4
    _a4(doc, sprache=(sp if sp != _rt.STANDARD else None))
    for section in doc.sections:
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)

    # Titel
    h = doc.add_heading(_t(sp, 't_titel_docx', projekt=projekt_name), level=0)
    doc.add_paragraph(
        _t(sp, 'erstellt',
           datum=date.today().strftime(_t(sp, 'datum_format'))))

    # Meta
    meta_p = doc.add_paragraph()
    meta_p.add_run(f"{_t(sp, 'l_organisation')}: ").bold = True
    meta_p.add_run(f"{proj.get('organisation', '')}\n")
    meta_p.add_run(f"{_t(sp, 'l_produkt')}: ").bold = True
    meta_p.add_run(f"{proj.get('produkt', '')}")

    # A6 Risk-Tier Banner
    if tier.get('tier'):
        doc.add_heading(_t(sp, 't_a6_docx'), level=1)
        p = doc.add_paragraph()
        p.add_run(f"{_t(sp, 'l_klasse')}: ").bold = True
        run = p.add_run(tier['tier'].upper())
        run.bold = True
        tier_colors = {
            'prohibited': RGBColor(0xB7, 0x1C, 0x1C),
            'high-risk': RGBColor(0xBF, 0x36, 0x0C),
            'limited-risk': RGBColor(0xF5, 0x7F, 0x17),
            'minimal-risk': RGBColor(0x2E, 0x7D, 0x32),
        }
        run.font.color.rgb = tier_colors.get(tier['tier'], RGBColor(0x42, 0x42, 0x42))
        if tier.get('annex_iii_kategorie'):
            doc.add_paragraph(f"{_t(sp, 'l_annex_iii_kategorie')}: {tier['annex_iii_kategorie']}")
        if tier.get('konformitaetsbewertung'):
            doc.add_paragraph(f"{_t(sp, 'l_konformitaetsbewertung')}: {tier['konformitaetsbewertung']}")
        if tier.get('begruendung'):
            doc.add_paragraph(tier['begruendung'])

    # Pflicht-Doku
    doc.add_heading(_t(sp, 't_pflicht_doku'), level=1)

    def _kv_block(title: str, mapping: dict, fields: list[tuple[str, str]]) -> None:
        any_filled = any(mapping.get(k) for k, _ in fields)
        if not any_filled:
            return
        doc.add_heading(title, level=2)
        for k, label in fields:
            if mapping.get(k):
                p = doc.add_paragraph()
                p.add_run(f"{label}: ").bold = True
                p.add_run(str(mapping[k])[:500])

    _kv_block(_t(sp, 't_a1'), pdoku['system_doku'], [
        ('system_name', _t(sp, 'l_system_name')), ('version', _t(sp, 'l_version')),
        ('provider', _t(sp, 'l_provider')), ('intended_purpose', _t(sp, 'l_intended_purpose')),
        ('architecture', _t(sp, 'l_architecture')),
        ('training_methodology', _t(sp, 'l_training_methodology')),
        ('computational_resources', _t(sp, 'l_computational_resources')),
        ('test_methodology', _t(sp, 'l_test_methodology')),
        ('cybersecurity_measures', _t(sp, 'l_cybersecurity')),
        ('accuracy_robustness', _t(sp, 'l_accuracy_robustness')),
    ])

    _kv_block(_t(sp, 't_a2'), pdoku['data_governance'], [
        ('training_data_source', _t(sp, 'l_training_data_source')),
        ('training_data_size', _t(sp, 'l_training_data_size')),
        ('validation_data_split', _t(sp, 'l_validation_data_split')),
        ('test_data_split', _t(sp, 'l_test_data_split')),
        ('bias_assessment', _t(sp, 'l_bias_assessment')),
        ('bias_mitigation', _t(sp, 'l_bias_mitigation')),
        ('representativeness', _t(sp, 'l_representativeness')),
        ('legal_basis_gdpr', _t(sp, 'l_legal_basis_gdpr')),
    ])

    risks = pdoku['risks']
    if risks:
        doc.add_heading(_t(sp, 't_a3', n=len(risks)), level=2)
        tbl = doc.add_table(rows=len(risks) + 1, cols=6)
        tbl.style = 'Light Grid Accent 1'
        for ci, hdr in enumerate([_t(sp, 'h_id'), _t(sp, 'h_titel'), _t(sp, 'h_phase'),
                                  _t(sp, 'h_kategorie'), _t(sp, 'h_score'), _t(sp, 'h_status')]):
            tbl.cell(0, ci).paragraphs[0].add_run(hdr).bold = True
        for ri, r in enumerate(risks, start=1):
            tbl.cell(ri, 0).text = r.get('risk_id', '')
            tbl.cell(ri, 1).text = r.get('titel', '')[:60]
            tbl.cell(ri, 2).text = r.get('lifecycle_phase', '')
            tbl.cell(ri, 3).text = r.get('risk_category', '')
            tbl.cell(ri, 4).text = str(r.get('risk_score', 0))
            tbl.cell(ri, 5).text = r.get('status', '')

    _kv_block(_t(sp, 't_a4'), pdoku['human_oversight'], [
        ('oversight_mode', _t(sp, 'l_oversight_mode')),
        ('intervention_mechanisms', _t(sp, 'l_intervention_mechanisms')),
        ('monitoring_interface', _t(sp, 'l_monitoring_interface')),
        ('output_interpretation_aids', _t(sp, 'l_output_interpretation_aids')),
        ('abnormal_behavior_detection', _t(sp, 'l_abnormal_behavior_detection')),
        ('training_program', _t(sp, 'l_training_program')),
    ])

    _kv_block(_t(sp, 't_a5'), pdoku['pmm'], [
        ('monitoring_plan', _t(sp, 'l_monitoring_plan')),
        ('performance_metrics', _t(sp, 'l_performance_metrics')),
        ('drift_detection', _t(sp, 'l_drift_detection')),
        ('user_feedback_channel', _t(sp, 'l_user_feedback_channel')),
        ('incident_threshold', _t(sp, 'l_incident_threshold')),
        ('market_surveillance_contact', _t(sp, 'l_market_surveillance_contact')),
        ('serious_incident_reporting_sla', _t(sp, 'l_reporting_sla_art73')),
    ])

    # Anforderungen
    doc.add_heading(_t(sp, 't_anforderungs_bewertungen'), level=1)
    bew_tbl = doc.add_table(rows=len(AI_ACT_REQUIREMENTS) + 1, cols=4)
    bew_tbl.style = 'Light Grid Accent 1'
    for ci, hdr in enumerate([_t(sp, 'h_id'), _t(sp, 'h_titel'),
                              _t(sp, 'l_kapitel'), _t(sp, 'l_bewertung')]):
        bew_tbl.cell(0, ci).paragraphs[0].add_run(hdr).bold = True
    for ri, req in enumerate((_kat(r, sp) for r in AI_ACT_REQUIREMENTS), start=1):
        rid = req.get('id', '')
        b = bew_raw.get(rid, {})
        score = int(b.get('bewertung', 0) or 0)
        label = _kat(BEWERTUNG_SKALA.get(score, {}), sp).get('label', str(score))
        bew_tbl.cell(ri, 0).text = rid
        bew_tbl.cell(ri, 1).text = req.get('titel', '')[:50]
        bew_tbl.cell(ri, 2).text = req.get('kapitel', '')
        bew_tbl.cell(ri, 3).text = f"{score} – {label}"

    out_path = out_dir / f"AI-Act-Report_{_safe_filename(projekt_name)}.docx"
    doc.save(str(out_path))
    return out_path


# ─────────────────────────────────────────────────────────────────────────
# PDF (neu, simpel via PIL)
# ─────────────────────────────────────────────────────────────────────────

def export_pdf(*, sprache: str | None = None, **kwargs) -> Path:
    """#1614: PDF vektoriell aus dem DOCX (A4) statt Rasterbild.

    ``sprache`` steht ausdrücklich in der Signatur und wird nicht nur über
    ``**kwargs`` durchgereicht: ``shared/reports/api._zusatz`` entscheidet
    anhand der **Signatur**, ob es den Parameter übergibt (#1954).
    """
    from shared.reports.docx_pdf import docx_to_pdf_bytes
    docx_path = export_docx(sprache=sprache, **kwargs)
    pdf_path = Path(docx_path).with_suffix(".pdf")
    pdf_path.write_bytes(docx_to_pdf_bytes(docx_path))
    return pdf_path
def _wrap(text: str, max_chars: int) -> list[str]:
    if not text:
        return []
    words = text.split()
    line, lines = '', []
    for w in words:
        if len(line) + len(w) + 1 > max_chars:
            lines.append(line); line = w
        else:
            line = (line + ' ' + w) if line else w
    if line:
        lines.append(line)
    return lines
