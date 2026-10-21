"""Compliance-Audit API — Standortbestimmung gegen ein Framework.

Eigenes Modul seit v7.4.0 (vorher Teil von ``server/api/gutachten.py``). Fachlich
ist das etwas anderes als ein Gutachten: Hier wird per Fragenkatalog der
Umsetzungsstand des Kunden gegen ein Framework erhoben und ihm als
**Wasserstandsmeldung** zurückgegeben.

Umfang: Projekte · Framework-Bibliothek (Download/Ingest/Upload) · Fragen
(KI-Generierung, Import, Fragebogen-Export/-Reimport als XLSX) · Auswertung ·
Wasserstandsmeldung (:mod:`compliance_audit.status` + :mod:`compliance_audit.prompts`).

Autorisierung läuft über den zentralen Guard (``server/middleware/authz.py``,
Prefix ``/api/compliance-audit`` → Modul ``compliance_audit`` →
``compliance_audit:read|write|export``); das Lizenz-Gate kennt das Modul als
Grundpreis-Modul (``shared/licensing/modules.py``).

Datenhaltung weiterhin in ``data/db/gutachten.sqlite`` mit den Tabellen
``gutachten_projects``/``gutachten_questions``/``gutachten_assessments``. Die Namen
sind historisch und bleiben, damit bestehende Kundendaten nicht migriert werden
müssen (:mod:`compliance_audit.db` ergänzt nur ``erfuellung`` + ``audit_wasserstand``).
"""

import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from server.api.workspace_tmp import workspace_tmpdir
from flask import current_app, Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt

from gutachten.db import (
    list_projects,
    save_project,
    load_project,
    delete_project,
    save_questions,
    append_questions,
    load_questions,
    update_question,
    delete_question,
    update_question_answers,
    save_assessment,
    load_assessments,
    save_gutachten_draft,
    load_gutachten_draft,
    fetch_sections,
    count_sections_by_framework,
    ingest_sections,
)
from compliance_audit import db as audit_db
from compliance_audit.status import ERFUELLUNG, build_status
from compliance_audit.prompts import build_status_prompt, parse_status_response

audit_bp = Blueprint('compliance_audit', __name__, url_prefix='/api/compliance-audit')

DB_PATH = Path('data/db/gutachten.sqlite')

# DB sicherstellen (inkl. erfuellung-Spalte + audit_wasserstand)
try:
    audit_db.ensure_db(DB_PATH)
except Exception:
    pass


# #1725: Geteiltes Berichts-Center (Sprint #35) — gleicher Weg wie CRA/NIS2/
# DSGVO/WiBA. Guarded wie dort: ein Fehler hier darf den App-Start nicht kippen.
try:
    from shared.reports.api import register_report_routes as _register_report_routes
    from compliance_audit import berichte_provider as _audit_berichte
    _register_report_routes(
        audit_bp, modul='compliance_audit', db_path=DB_PATH,
        catalog=_audit_berichte.catalog(), render=_audit_berichte.render,
        project_scoped=True, zeitraum=False,
        summary_context=_audit_berichte.summary_context,
        modul_label='Compliance-Audit',
    )
except Exception as _e:  # pragma: no cover — Berichts-Center optional
    import logging as _logging
    _logging.getLogger(__name__).warning(
        'Compliance-Audit-Berichts-Center nicht registriert: %s', _e)


def _allowlist(body: Any, allowed: tuple) -> Dict[str, Any]:
    """Reduziere ein Request-JSON auf erlaubte Felder (Mass-Assignment-Schutz)."""
    if not isinstance(body, dict):
        return {}
    return {k: body[k] for k in allowed if k in body}


# ============================================================
# Hilfsfunktionen
# ============================================================

def _serialize_project(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'id': p.get('name'),
        'name': p.get('name', ''),
        'frameworks': p.get('frameworks', []),
        'pruefungsfokus': p.get('pruefungsfokus', ''),
        # Issue #427/#436: Firmen-Bezug
        'unternehmen': p.get('unternehmen', ''),
        'company': p.get('unternehmen', ''),
        'meta': p.get('meta', {}),
        'created_at': p.get('created_at'),
        'updated_at': p.get('updated_at'),
        'projectName': p.get('name', ''),
        'title': p.get('name', ''),
    }


# ============================================================
# Projekte CRUD
# ============================================================

@audit_bp.get('')
@jwt_required()
def list_all():
    """Liste aller Gutachten (auf freigegebene Mandanten gefiltert, #1707)."""
    try:
        from shared.tenancy import scope_current_request
        names = list_projects(DB_PATH)
        result = []
        for name in names:
            p = load_project(DB_PATH, name)
            if p:
                result.append(_serialize_project(p))
        return scope_current_request(result), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.get('/projekte')
@jwt_required()
def list_projekte():
    return list_all()


@audit_bp.get('/<project_name>')
@jwt_required()
def get_project(project_name: str):
    try:
        p = load_project(DB_PATH, project_name)
        if not p:
            return {'error': 'Projekt nicht gefunden'}, 404
        d = _serialize_project(p)
        d['questions'] = load_questions(DB_PATH, project_name)
        d['assessments'] = load_assessments(DB_PATH, project_name)
        return d, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.post('')
@jwt_required()
def create_project():
    try:
        data = request.json or {}
        name = (data.get('name') or data.get('projectName') or '').strip()
        if not name:
            return {'error': 'Feld "name" ist Pflicht'}, 400
        frameworks = data.get('frameworks') or []
        if isinstance(frameworks, str):
            frameworks = [f.strip() for f in frameworks.split(',') if f.strip()]
        save_project(
            DB_PATH,
            name=name,
            frameworks=frameworks,
            pruefungsfokus=data.get('pruefungsfokus', ''),
            meta=data.get('meta', {}),
            unternehmen=(data.get('unternehmen') or data.get('company') or '').strip(),
        )
        return _serialize_project(load_project(DB_PATH, name) or {}), 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.put('/<project_name>')
@jwt_required()
def update_project(project_name: str):
    try:
        existing = load_project(DB_PATH, project_name)
        if not existing:
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        # Issue #436: unternehmen-Wechsel zulassen
        if 'unternehmen' in data or 'company' in data:
            unternehmen = (data.get('unternehmen') or data.get('company') or '').strip()
        else:
            unternehmen = existing.get('unternehmen', '')
        save_project(
            DB_PATH,
            name=project_name,
            frameworks=data.get('frameworks', existing.get('frameworks', [])),
            pruefungsfokus=data.get('pruefungsfokus', existing.get('pruefungsfokus', '')),
            meta=data.get('meta', existing.get('meta', {})),
            unternehmen=unternehmen,
        )
        return _serialize_project(load_project(DB_PATH, project_name) or {}), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.delete('/<project_name>')
@jwt_required()
def delete(project_name: str):
    try:
        delete_project(DB_PATH, project_name)
        return {'deleted': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# Fragen CRUD
# ============================================================

@audit_bp.get('/<project_name>/questions')
@jwt_required()
def list_questions(project_name: str):
    try:
        if not load_project(DB_PATH, project_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        return load_questions(DB_PATH, project_name), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.put('/questions/<int:question_id>')
@jwt_required()
def edit_question(question_id: int):
    try:
        data = request.json or {}
        update_question(DB_PATH, question_id, data)
        return {'ok': True, 'id': question_id}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.delete('/questions/<int:question_id>')
@jwt_required()
def remove_question(question_id: int):
    try:
        delete_question(DB_PATH, question_id)
        return {'deleted': True, 'id': question_id}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.post('/<project_name>/questions')
@jwt_required()
def add_question(project_name: str):
    try:
        if not load_project(DB_PATH, project_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        if not data.get('frage'):
            return {'error': 'Feld "frage" ist Pflicht'}, 400
        n = append_questions(DB_PATH, project_name, [data])
        return {'ok': True, 'added': n}, 201
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.post('/<project_name>/questions/bulk-update')
@jwt_required()
def bulk_update_answers(project_name: str):
    try:
        if not load_project(DB_PATH, project_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        rows = request.json or []
        if not isinstance(rows, list):
            return {'error': 'Erwartet: Liste'}, 400
        update_question_answers(DB_PATH, rows)
        return {'ok': True, 'updated': len(rows)}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# Frameworks: Konfiguration + Verfügbarkeit
# ============================================================

# Mapping: Framework → (Beschreibung, CELEX-Codes oder None für SPARQL-derived,
#                        Default-Verzeichnis)
FRAMEWORK_CONFIG = {
    'NIS2': {
        'label': 'NIS2 – EU-Richtlinie + nationale Umsetzung',
        'description': 'EU 2022/2555 (NIS2-Richtlinie)',
        'celex_codes': ['32022L2555'],
        'sparql_derived': False,
        'data_dir': 'data/nis2_resources',
    },
    'CRA': {
        'label': 'CRA – Cyber Resilience Act',
        'description': 'EU 2024/2847',
        'celex_codes': ['32024R2847'],
        'sparql_derived': False,
        'data_dir': 'data/cra_resources',
    },
    'DSGVO': {
        'label': 'DSGVO – Datenschutz-Grundverordnung',
        'description': 'EU 2016/679',
        'celex_codes': ['32016R0679'],
        'sparql_derived': False,
        'data_dir': 'data/dsgvo_resources',
    },
    'AI_ACT': {
        'label': 'AI Act – Verordnung über Künstliche Intelligenz',
        'description': 'EU 2024/1689',
        'celex_codes': ['32024R1689'],
        'sparql_derived': False,
        'data_dir': 'data/ai_act_resources',
    },
    'ISO27001': {
        'label': 'ISO 27001 – Audit-Questionnaires + Checklisten',
        'description': 'Manueller Upload — kein EU-Dokument',
        'celex_codes': [],
        'sparql_derived': False,
        'data_dir': 'data/iso27001_questionnaires',
        'extra_resources': [],
    },
    'BSI': {
        'label': 'BSI IT-Grundschutz',
        'description': 'Kompendium + BSI-Standards (Direkt-Download von bsi.bund.de)',
        'celex_codes': [],
        'sparql_derived': False,
        'data_dir': 'data/bsi_resources',
        'extra_resources': [
            {
                'name': 'BSI IT-Grundschutz Kompendium Edition 2023',
                'url': 'https://www.bsi.bund.de/SharedDocs/Downloads/DE/BSI/Grundschutz/IT-GS-Kompendium/IT_Grundschutz_Kompendium_Edition2023.pdf?__blob=publicationFile&v=4',
                'filename': 'BSI_IT_Grundschutz_Kompendium_2023.pdf',
            },
            {
                'name': 'BSI-Standard 200-1 (ISMS)',
                'url': 'https://www.bsi.bund.de/SharedDocs/Downloads/DE/BSI/Grundschutz/BSI_Standards/standard_200_1.pdf?__blob=publicationFile&v=2',
                'filename': 'BSI_Standard_200-1_ISMS.pdf',
            },
            {
                'name': 'BSI-Standard 200-2 (IT-Grundschutz-Methodik)',
                'url': 'https://www.bsi.bund.de/SharedDocs/Downloads/DE/BSI/Grundschutz/BSI_Standards/standard_200_2.pdf?__blob=publicationFile&v=2',
                'filename': 'BSI_Standard_200-2_Methodik.pdf',
            },
        ],
    },
}


@audit_bp.get('/frameworks')
@jwt_required()
def list_frameworks():
    """Framework-Konfiguration + Status pro Framework."""
    from pathlib import Path as _Path
    counts = count_sections_by_framework(DB_PATH)
    result = []
    for fw, cfg in FRAMEWORK_CONFIG.items():
        data_dir = _Path(cfg['data_dir'])
        pdf_count = 0
        if data_dir.exists():
            pdf_count = len(list(data_dir.glob('*.pdf'))) + len(list(data_dir.glob('*.xlsx')))
        extra = cfg.get('extra_resources', []) or []
        result.append({
            'id': fw,
            'label': cfg['label'],
            'description': cfg['description'],
            'celex_codes': cfg['celex_codes'],
            'sparql_derived': cfg['sparql_derived'],
            'extra_resources': [{'name': r['name'], 'filename': r['filename']} for r in extra],
            'has_download': bool(cfg['celex_codes']) or bool(extra),
            'data_dir': cfg['data_dir'],
            'pdf_count': pdf_count,
            'sections_count': counts.get(fw, 0),
        })
    return result, 200


@audit_bp.post('/frameworks/<fw>/download')
@jwt_required()
def download_framework(fw: str):
    """Downloadet Regulierungs-PDFs für ein Framework via EUR-Lex SPARQL.

    Body: { force: bool, lang: 'DEU'|'ENG' }
    Long-running. Nur NIS2/CRA/DSGVO/AI_ACT.
    """
    if fw not in FRAMEWORK_CONFIG:
        return {'error': f'Unbekanntes Framework: {fw}'}, 400
    cfg = FRAMEWORK_CONFIG[fw]
    extra = cfg.get('extra_resources', []) or []
    if not cfg['celex_codes'] and not extra:
        return {'error': f'{fw} unterstützt keinen automatischen Download (manueller Upload nötig)'}, 400

    body = request.json or {}
    force = bool(body.get('force', False))
    lang = (body.get('lang') or 'DEU').upper()

    from pathlib import Path as _Path
    data_dir = _Path(cfg['data_dir'])
    data_dir.mkdir(parents=True, exist_ok=True)

    log_lines: List[str] = []
    def log(msg: str):
        log_lines.append(msg)
        current_app.logger.info('[%s download] %s', fw, msg)

    try:
        from gutachten.file_download import (
            build_requests_session,
            discover_regulations_based_on,
            resolve_work_uri_for_celex,
            download_doc,
            download_extra_resource,
            Doc,
            ExtraResource,
            normalize_lang,
            safe_filename,
            compute_logical_filename,
            resolve_pdf_item_and_title,
            resolve_publication_date_for_celex,
        )

        session = build_requests_session()
        celexes = list(cfg['celex_codes'])
        log(f'Starte Download für {fw} ({len(celexes)} CELEX, {len(cfg.get("extra_resources", []) or [])} Direkt-URLs, lang={lang})')

        if cfg['sparql_derived']:
            try:
                base_work = resolve_work_uri_for_celex(session, celexes[0])
                derived = discover_regulations_based_on(session, base_work)
                for c in derived:
                    if c not in celexes:
                        celexes.append(c)
                log(f'  SPARQL: {len(celexes)} Dokumente (Basis + {len(celexes)-1} abgeleitet)')
            except Exception as e:
                log(f'  WARNUNG: SPARQL-Discovery fehlgeschlagen: {e}')

        ok = 0
        failed = 0
        downloaded = []
        for celex in celexes:
            doc = Doc(title=f'CELEX {celex}', celex=celex, kind=fw, lang=lang)
            try:
                url, title = resolve_pdf_item_and_title(session, celex, lang)
                doc.pdf_item_url = url
                doc.title = title
                try:
                    doc.publication_date = resolve_publication_date_for_celex(session, celex)
                except Exception:
                    pass
            except Exception as e:
                log(f'  x {celex}: Metadaten nicht abrufbar — {e}')
                failed += 1
                continue

            desired_name = compute_logical_filename(doc) if cfg['sparql_derived'] else safe_filename(f'{celex}_{lang}.pdf')
            out_path = data_dir / desired_name
            if force and out_path.exists():
                out_path.unlink(missing_ok=True)
            elif out_path.exists():
                log(f'  - {desired_name} (bereits vorhanden, übersprungen)')
                ok += 1
                downloaded.append(desired_name)
                continue

            try:
                res = download_doc(session, doc, out_path)
                size_mb = res.bytes_written / (1024 * 1024)
                log(f'  ✓ {desired_name} ({size_mb:.1f} MB)')
                ok += 1
                downloaded.append(desired_name)
            except Exception as e:
                log(f'  x {desired_name}: {e}')
                failed += 1

        # Direkt-URL-Downloads (BSI etc.)
        for r in (cfg.get('extra_resources') or []):
            res_obj = ExtraResource(name=r['name'], url=r['url'], filename=r['filename'])
            out_path = data_dir / r['filename']
            if not force and out_path.exists():
                log(f'  - {r["filename"]} (bereits vorhanden, übersprungen)')
                ok += 1
                downloaded.append(r['filename'])
                continue
            log(f'  -> {r["filename"]}')
            try:
                ex_res = download_extra_resource(session, res_obj, data_dir, force=force)
                if ex_res.ok:
                    size_mb = ex_res.bytes_written / (1024 * 1024)
                    log(f'     ✓ {size_mb:.1f} MB — {r["name"]}')
                    ok += 1
                    downloaded.append(r['filename'])
                else:
                    log(f'     x FEHLER: {ex_res.error}')
                    failed += 1
            except Exception as e:
                log(f'     x {e}')
                failed += 1

        log(f'Fertig: {ok} OK, {failed} Fehler')
        return {
            'framework': fw,
            'ok': ok,
            'failed': failed,
            'downloaded': downloaded,
            'log': log_lines,
            'data_dir': str(data_dir),
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        log_lines.append(f'FEHLER: {e}')
        return {'error': str(e), 'type': type(e).__name__, 'log': log_lines}, 500


@audit_bp.post('/frameworks/<fw>/ingest')
@jwt_required()
def ingest_framework(fw: str):
    """Ingestiert alle PDFs aus dem Framework-Verzeichnis in die Sections-DB."""
    if fw not in FRAMEWORK_CONFIG:
        return {'error': f'Unbekanntes Framework: {fw}'}, 400
    cfg = FRAMEWORK_CONFIG[fw]

    from pathlib import Path as _Path
    data_dir = _Path(cfg['data_dir'])
    if not data_dir.exists():
        return {'error': f'Verzeichnis existiert nicht: {data_dir}'}, 404

    try:
        from gutachten.io_pdf import ingest_framework_dir
        n_sections, errors = ingest_framework_dir(
            db_path=DB_PATH,
            dir_path=data_dir,
            framework=fw,
        )
        current_app.logger.info('[%s ingest] %d sections aus %s, %d Fehler',
                                fw, n_sections, data_dir, len(errors))
        return {
            'framework': fw,
            'sections_inserted': n_sections,
            'errors': errors,
            'data_dir': str(data_dir),
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.post('/frameworks/<fw>/upload')
@jwt_required()
def upload_framework_pdf(fw: str):
    """PDF/XLSX manuell ins Framework-Verzeichnis hochladen (für ISO27001/BSI)."""
    if fw not in FRAMEWORK_CONFIG:
        return {'error': f'Unbekanntes Framework: {fw}'}, 400
    f = request.files.get('file')
    if not f or not f.filename:
        return {'error': 'Datei-Feld "file" fehlt'}, 400
    name_low = f.filename.lower()
    if not (name_low.endswith('.pdf') or name_low.endswith('.xlsx')):
        return {'error': 'Nur .pdf oder .xlsx erlaubt'}, 400

    from pathlib import Path as _Path
    from werkzeug.utils import secure_filename
    cfg = FRAMEWORK_CONFIG[fw]
    data_dir = _Path(cfg['data_dir'])
    data_dir.mkdir(parents=True, exist_ok=True)

    # #743 (WP-10): einheitlich secure_filename; leere/punkt-only Namen ablehnen.
    safe_name = secure_filename(f.filename)
    ext = _Path(safe_name).suffix.lower()
    if not safe_name or ext not in ('.pdf', '.xlsx'):
        return {'error': 'Ungültiger Dateiname'}, 400
    out_path = data_dir / safe_name
    f.save(str(out_path))
    # Magic-Byte- + (für xlsx) Zip-Bomb-Prüfung nach dem Speichern.
    from shared.upload_validation import validate_upload_file, UploadValidationError
    try:
        validate_upload_file(out_path, suffix=ext)
    except UploadValidationError as ve:
        out_path.unlink(missing_ok=True)
        return {'error': str(ve)}, 400
    current_app.logger.info('[%s upload] %s (%d bytes)', fw, safe_name, out_path.stat().st_size)
    return {'framework': fw, 'filename': safe_name, 'size': out_path.stat().st_size}, 200


# ============================================================
# Sections (Regulierungstexte)
# ============================================================

@audit_bp.get('/sections/count')
@jwt_required()
def sections_count():
    try:
        return count_sections_by_framework(DB_PATH), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.get('/sections')
@jwt_required()
def list_sections():
    try:
        fw_q = request.args.get('framework', '')
        frameworks = [f.strip() for f in fw_q.split(',') if f.strip()] or None
        secs = fetch_sections(DB_PATH, frameworks)
        return secs, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.post('/sections/ingest')
@jwt_required()
def ingest_sections_endpoint():
    """Manuelle Sections-Ingest. Body: { framework, doc_name, sections: [{section_ref, title, text}] }"""
    try:
        data = request.json or {}
        fw = (data.get('framework') or '').strip()
        doc_name = (data.get('doc_name') or '').strip()
        sections = data.get('sections') or []
        if not fw or not doc_name:
            return {'error': '"framework" und "doc_name" sind Pflicht'}, 400
        if not isinstance(sections, list) or not sections:
            return {'error': '"sections" muss nicht-leere Liste sein'}, 400
        n = ingest_sections(DB_PATH, fw, doc_name, sections)
        return {'ok': True, 'inserted': n}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# Prompt-Generierung (Fragen) — Kern-Feature
# ============================================================

@audit_bp.post('/<project_name>/fragen/prompt')
@jwt_required()
def build_fragen_prompt(project_name: str):
    """Erstellt ChatGPT-Prompt(s) zur Fragen-Generierung.

    Body: { batch_size: 15, test_mode: false }
    Returns: { prompts: [{framework, content, filename}] }
    """
    try:
        projekt = load_project(DB_PATH, project_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        batch_size = int(data.get('batch_size', 15))
        test_mode = bool(data.get('test_mode', False))

        from gutachten.prompts import _build_fragen_prompt, _pick_representative_sections
        from gutachten.config import load_config, cfg_get

        frameworks = projekt.get('frameworks') or []
        if not frameworks:
            return {'error': 'Projekt hat keine Frameworks. Erst Frameworks beim Projekt setzen.'}, 400

        cfg = load_config()
        header = cfg_get(cfg, 'prompt.fragen_header', '')
        bewertung_skala = cfg_get(cfg, 'prompt.bewertung_skala', [])
        effective_batch = 5 if test_mode else batch_size

        sections = fetch_sections(DB_PATH, frameworks)
        representative = _pick_representative_sections(
            sections, frameworks, max_per_framework=effective_batch,
        )

        prompts = []
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        for fw in frameworks:
            fw_sections = [s for s in representative if s.get('framework') == fw]
            content = _build_fragen_prompt(
                projekt_name=project_name,
                pruefungsfokus=projekt.get('pruefungsfokus', ''),
                frameworks=[fw],
                sections=fw_sections,
                batch_size=effective_batch,
                header=header,
                bewertung_skala=bewertung_skala,
            )
            safe_proj = ''.join(c if c.isalnum() or c in '-_' else '_' for c in project_name)
            safe_fw = fw.replace('/', '_')
            prompts.append({
                'framework': fw,
                'content': content,
                'filename': f'Fragebogen_{safe_proj}_{safe_fw}_{ts}.md',
                'section_count': len(fw_sections),
            })
        current_app.logger.info('Gutachten Prompt-Build: projekt=%r %d Prompts (%d Sections gesamt)',
                                project_name, len(prompts), len(sections))
        return {'prompts': prompts, 'frameworks': frameworks, 'sections_total': len(sections)}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.post('/<project_name>/fragen/import')
@jwt_required()
def import_fragen_from_chatgpt(project_name: str):
    """Importiert ChatGPT-JSON-Antwort als Fragen.

    Body: { raw: '<chatgpt-text>', replace: true|false (default false=append), source_file: '<optional>' }
    """
    try:
        if not load_project(DB_PATH, project_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        raw = data.get('raw') or ''
        if not raw:
            return {'error': 'Feld "raw" mit der ChatGPT-Antwort ist Pflicht'}, 400
        replace = bool(data.get('replace', False))
        source_file = data.get('source_file', 'manual')

        from gutachten.prompts import validate_fragen_payload
        import re

        try:
            obj = json.loads(raw)
        except Exception:
            m = re.search(r'```json\s*([\[\{].*?[\]\}])\s*```', raw, re.DOTALL)
            if m:
                obj = json.loads(m.group(1))
            else:
                m = re.search(r'(\[.*\])', raw, re.DOTALL)
                if not m:
                    return {'error': 'Keine JSON-Liste in der Antwort gefunden'}, 400
                obj = json.loads(m.group(1))

        try:
            fragen = validate_fragen_payload(obj)
        except ValueError as e:
            return {'error': f'Validierung fehlgeschlagen: {e}'}, 400

        for f in fragen:
            f['source_file'] = source_file

        if replace:
            save_questions(DB_PATH, project_name, fragen)
            n = len(fragen)
        else:
            n = append_questions(DB_PATH, project_name, fragen)

        current_app.logger.info('Gutachten Fragen-Import: projekt=%r imported=%d (replace=%s)',
                                project_name, n, replace)
        return {'ok': True, 'imported': n}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# Auditbericht
# ============================================================

@audit_bp.post('/<project_name>/bericht/prompt')
@jwt_required()
def bericht_prompt(project_name: str):
    """Prompt fuer den Auditbericht (#1723)."""
    try:
        projekt = load_project(DB_PATH, project_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404

        questions = load_questions(DB_PATH, project_name)
        if not questions:
            return {'error': 'Keine Fragen vorhanden — erst Fragen generieren und beantworten'}, 400

        # #1723: Eigener Auditbericht-Prompt. Vorher lief das ueber
        # gutachten.prompts._build_gutachten_prompt — mit einer Signatur, die nicht
        # mehr zur Aufrufstelle passte (TypeError: unexpected keyword argument
        # 'pruefungsfokus') und damit HTTP 500. Fachlich war es ohnehin falsch:
        # hier entsteht ein Auditbericht, kein Gutachten.
        from compliance_audit.prompts import build_bericht_prompt

        content = build_bericht_prompt(projekt, questions, _status_fuer(project_name))
        return {
            'prompt': content,
            'questions_count': len(questions),
            'frameworks': projekt.get('frameworks', []),
        }, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.post('/<project_name>/bericht/import')
@jwt_required()
def bericht_import(project_name: str):
    """KI-Antwort zum Auditbericht uebernehmen und als Entwurf ablegen."""
    try:
        if not load_project(DB_PATH, project_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        data = request.json or {}
        raw = data.get('raw') or ''
        if not raw:
            return {'error': 'Feld "raw" ist Pflicht'}, 400

        # #1723: Eigener Parser (tolerant gegen ```json-Rahmen und Beitext) und
        # eigenes Pflichtfeld-Set. Das Zielschema bleibt unveraendert, damit
        # /bericht/export (DOCX) weiter funktioniert.
        from compliance_audit.prompts import parse_bericht_response

        try:
            payload = parse_bericht_response(raw)
        except ValueError as e:
            return {'error': f'Antwort nicht lesbar: {e}'}, 400

        save_gutachten_draft(DB_PATH, project_name, json.dumps(payload, ensure_ascii=False))
        return {'ok': True, 'draft': payload}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.get('/<project_name>/bericht/draft')
@jwt_required()
def get_draft(project_name: str):
    try:
        if not load_project(DB_PATH, project_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        s = load_gutachten_draft(DB_PATH, project_name)
        if not s:
            return {'draft': None}, 200
        try:
            return {'draft': json.loads(s)}, 200
        except Exception:
            return {'draft': None, 'raw': s}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.put('/<project_name>/bericht/draft')
@jwt_required()
def save_draft(project_name: str):
    try:
        if not load_project(DB_PATH, project_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        body = request.json or {}
        save_gutachten_draft(DB_PATH, project_name, json.dumps(body, ensure_ascii=False))
        return {'ok': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# Export
# ============================================================

@audit_bp.get('/<project_name>/fragebogen/export')
@jwt_required()
def export_fragebogen_endpoint(project_name: str):
    try:
        projekt = load_project(DB_PATH, project_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        questions = load_questions(DB_PATH, project_name)
        if not questions:
            return {'error': 'Keine Fragen vorhanden'}, 400

        from gutachten.io_xlsx import export_fragebogen, fragebogen_filename
        out_dir = workspace_tmpdir('gutachten_xlsx_')
        path = out_dir / fragebogen_filename(project_name)
        export_fragebogen(
            questions=questions,
            out_path=path,
            projekt_name=project_name,
            frameworks=projekt.get('frameworks', []),
        )
        return send_file(str(path), as_attachment=True, download_name=path.name)
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


@audit_bp.post('/<project_name>/bericht/export')
@jwt_required()
def export_gutachten_endpoint(project_name: str):
    try:
        if not load_project(DB_PATH, project_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        body = request.json or {}
        draft = body if body else None
        if not draft:
            s = load_gutachten_draft(DB_PATH, project_name)
            if not s:
                return {'error': 'Kein Gutachten-Entwurf vorhanden'}, 400
            draft = json.loads(s)

        from gutachten.gutachten_gen import generate_gutachten_from_dict
        out_dir = workspace_tmpdir('gutachten_docx_')
        path = generate_gutachten_from_dict(
            payload=draft,
            projekt_name=project_name,
            db_path=DB_PATH,
            out_dir=out_dir,
        )
        return send_file(str(path), as_attachment=True, download_name=path.name)
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)


# ============================================================
# Excel-Import (ausgefüllter Fragebogen)
# ============================================================

@audit_bp.post('/<projekt_name>/fragebogen/import')
@jwt_required()
def import_fragebogen_endpoint(projekt_name: str):
    """Excel-Fragebogen importieren (multipart/form-data, Feld 'file')."""
    if not load_project(DB_PATH, projekt_name):
        return {'error': 'Projekt nicht gefunden'}, 404
    f = request.files.get('file')
    if not f or not f.filename:
        return {'error': 'Datei-Feld "file" fehlt'}, 400
    if not f.filename.lower().endswith('.xlsx'):
        return {'error': 'Nur .xlsx wird unterstützt'}, 400

    tmp_dir = workspace_tmpdir('gutachten_import_')
    try:
        tmp_path = tmp_dir / 'upload.xlsx'
        f.save(str(tmp_path))
        # #743 (WP-10): Magic-Byte- + Zip-Bomb-Prüfung vor dem Parsen.
        from shared.upload_validation import validate_upload_file
        validate_upload_file(tmp_path, suffix='.xlsx')
        from gutachten.io_xlsx import import_fragebogen as do_import
        _detected_name, items = do_import(tmp_path)
        rows = [
            {
                'framework': getattr(q, 'framework', ''),
                'section_ref': getattr(q, 'section_ref', ''),
                'thema': getattr(q, 'thema', ''),
                'frage': getattr(q, 'frage', ''),
                'antwort': getattr(q, 'antwort', ''),
                'bewertung': getattr(q, 'bewertung', ''),
                'kommentar': getattr(q, 'kommentar', ''),
                'source_file': f.filename,
            }
            for q in items
        ]
        if rows:
            save_questions(DB_PATH, projekt_name, rows)
        return {'imported': len(rows)}, 200
    except ValueError as e:
        return {'error': str(e)}, 400
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500  # Detail nur im Server-Log (#737)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# Wasserstandsmeldung (v7.4.0)
# Die Compliance-Stufe wird BERECHNET (compliance_audit.status), nicht von der KI
# vergeben — sie ist eine Zusage an den Kunden und muss reproduzierbar sein.
# Die KI formuliert nur den Text zur feststehenden Stufe.
# ============================================================

def _aktueller_nutzer() -> str:
    """Kennung für die Herkunft einer Wasserstandsmeldung (best effort)."""
    try:
        claims = get_jwt() or {}
    except Exception:  # noqa: BLE001 — ohne JWT-Kontext (Tests) einfach leer
        return ''
    for key in ('email', 'username', 'sub'):
        wert = claims.get(key)
        if isinstance(wert, str) and wert:
            return wert
        if isinstance(wert, dict) and wert.get('email'):
            return str(wert['email'])
    return ''


def _status_fuer(project_name: str, *, luecken_limit: int = 0) -> Dict[str, Any]:
    return build_status(load_questions(DB_PATH, project_name),
                        luecken_limit=luecken_limit)


@audit_bp.get('/<project_name>/status')
@jwt_required()
def audit_status(project_name: str):
    """Berechneter Compliance-Stand — ohne KI, jederzeit live abrufbar."""
    try:
        if not load_project(DB_PATH, project_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        return jsonify(_status_fuer(project_name)), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@audit_bp.put('/questions/<int:question_id>/erfuellung')
@jwt_required()
def set_question_erfuellung(question_id: int):
    """Kanonische Erfüllung einer Frage setzen (Basis der Stufenberechnung)."""
    try:
        body = request.get_json(silent=True) or {}
        wert = str(body.get('erfuellung') or '')
        if wert not in ERFUELLUNG:
            return {'error': 'Ungültige Erfüllung', 'erlaubt': list(ERFUELLUNG)}, 400
        if not audit_db.set_erfuellung(DB_PATH, question_id, wert):
            return {'error': 'Ungültige Erfüllung'}, 400
        return {'id': question_id, 'erfuellung': wert, 'saved': True}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@audit_bp.post('/<project_name>/erfuellung/backfill')
@jwt_required()
def backfill_erfuellung_endpoint(project_name: str):
    """Erfüllung aus der alten Freitext-Bewertung ableiten (Projekte vor v7.4.0).

    Überschreibt keine bereits gesetzten Werte.
    """
    try:
        if not load_project(DB_PATH, project_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        n = audit_db.backfill_erfuellung(DB_PATH, project_name)
        return {'uebernommen': n, 'status': _status_fuer(project_name)}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@audit_bp.post('/<project_name>/wasserstand/prompt')
@jwt_required()
def wasserstand_prompt(project_name: str):
    """Prompt für die Wasserstandsmeldung (Copy/Paste-Weg)."""
    try:
        projekt = load_project(DB_PATH, project_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        status = _status_fuer(project_name, luecken_limit=40)
        return {'prompt': build_status_prompt(projekt, status), 'status': status}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@audit_bp.post('/<project_name>/wasserstand/import')
@jwt_required()
def wasserstand_import(project_name: str):
    """KI-Antwort übernehmen und als Wasserstandsmeldung ablegen."""
    try:
        projekt = load_project(DB_PATH, project_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        body = request.get_json(silent=True) or {}
        roh = body.get('response') or body.get('text') or ''
        if not str(roh).strip():
            return {'error': 'Feld "response" fehlt'}, 400
        try:
            ki = parse_status_response(str(roh))
        except (ValueError, TypeError) as e:
            return {'error': f'Antwort nicht lesbar: {e}'}, 400
        # Neu rechnen statt dem Client zu glauben — die Stufe ist unsere Aussage.
        status = _status_fuer(project_name, luecken_limit=40)
        rid = audit_db.save_wasserstand(
            DB_PATH, project_name, status=status, ki=ki,
            provider=str(body.get('provider') or 'copy-paste'),
            erstellt_von=_aktueller_nutzer())
        return {'id': rid, 'status': status, 'ki': ki}, 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@audit_bp.post('/<project_name>/wasserstand/stream')
@jwt_required()
def wasserstand_stream(project_name: str):
    """Wasserstandsmeldung direkt über den KI-Provider (SSE, #1366/#1519)."""
    try:
        projekt = load_project(DB_PATH, project_name)
        if not projekt:
            return {'error': 'Projekt nicht gefunden'}, 404
        status = _status_fuer(project_name, luecken_limit=40)
        prompt = build_status_prompt(projekt, status)
        nutzer = _aktueller_nutzer()

        def _finalize(text: str, provider: str = '') -> Dict[str, Any]:
            try:
                ki = parse_status_response(text)
            except (ValueError, TypeError):
                return {'error': 'Antwort nicht lesbar', 'saved': False}
            rid = audit_db.save_wasserstand(
                DB_PATH, project_name, status=status, ki=ki,
                provider=provider or 'ki', erstellt_von=nutzer)
            return {'id': rid, 'status': status, 'ki': ki, 'saved': True}

        from compliance_audit.prompts import SYSTEM_PROMPT
        from shared.sse import stream_ai_sse
        return stream_ai_sse(SYSTEM_PROMPT, prompt, finalize=_finalize,
                             force_json=True, temperature=0.2, num_predict=4096)
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@audit_bp.get('/<project_name>/wasserstand')
@jwt_required()
def wasserstand_list(project_name: str):
    """Verlauf der Wasserstandsmeldungen (neueste zuerst)."""
    try:
        if not load_project(DB_PATH, project_name):
            return {'error': 'Projekt nicht gefunden'}, 404
        return jsonify(audit_db.list_wasserstand(DB_PATH, project_name)), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500


@audit_bp.get('/<project_name>/wasserstand/<int:report_id>')
@jwt_required()
def wasserstand_detail(project_name: str, report_id: int):
    """Eine Wasserstandsmeldung samt gerechnetem Stand und KI-Text."""
    try:
        w = audit_db.load_wasserstand(DB_PATH, report_id)
        if not w or w.get('project_name') != project_name:
            return {'error': 'Nicht gefunden'}, 404
        return jsonify(w), 200
    except Exception as e:
        current_app.logger.exception('%s %s — %s: %s', request.method, request.path, type(e).__name__, e)
        return {'error': 'Interner Serverfehler'}, 500
