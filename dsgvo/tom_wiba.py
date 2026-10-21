"""#1575 — DSGVO-TOM ↔ BSI-WiBA: Verknüpfung, Status-Ableitung, Formulierung.

Die WiBA-Prüffragen einer Firma (Basis-Absicherung) belegen die Umsetzung der
technischen und organisatorischen Maßnahmen nach Art. 32 DSGVO / SDM. Das Mapping
ist kuratiert und enthält **nur IDs** (keine BSI-Texte im Repo — Copyright BSI;
die Fragetexte kommen zur Laufzeit aus dem geladenen WiBA-Katalog).

Ableitung: Status (0–5) einer TOM = Anteil „Ja" an den verknüpften Prüffragen im
Scope (``nicht_relevant`` zählt nicht). Nur TOM mit ``status_quelle='wiba'`` werden
automatisch nachgezogen — manuell bewertete TOM bleiben unangetastet.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# TOM-massnahme_key → WiBA control_ids (``<theme_key>-<nr>``, siehe wiba/io_source).
TOM_WIBA_MAPPING: dict[str, list[str]] = {
    # ── Datenminimierung ─────────────────────────────────────────────
    'DM-01': ['arbeitaußerhalbderinstitution-3'],
    'DM-03': ['umgangmitinformationen-3', 'umgangmitinformationen-4', 'umgangmitinformationen-5',
              'backup-4', 'client-11', 'client-12', 'arbeitaußerhalbderinstitution-8',
              'arbeitaußerhalbderinstitution-9', 'druckerundmultifunktionsgeräte-5'],
    # ── Verfügbarkeit ────────────────────────────────────────────────
    'VF-01': ['backup-1', 'backup-2', 'backup-3', 'backup-4', 'backup-5', 'backup-6', 'backup-7'],
    'VF-02': ['serverraumunddatenträgerarchiv-2', 'serverraumunddatenträgerarchiv-3',
              'serverraumunddatenträgerarchiv-4', 'serverraumunddatenträgerarchiv-6',
              'serverraumunddatenträgerarchiv-7', 'serverraumunddatenträgerarchiv-9',
              'serverraumunddatenträgerarchiv-11', 'serversysteme-5',
              'arbeitinnerhalbderinstitutionhaustechnik-7',
              'itadministration-1'],
    'VF-03': ['vorbereitungfürsicherheitsvorfälle-1', 'vorbereitungfürsicherheitsvorfälle-2',
              'vorbereitungfürsicherheitsvorfälle-3', 'vorbereitungfürsicherheitsvorfälle-4',
              'vorbereitungfürsicherheitsvorfälle-5', 'vorbereitungfürsicherheitsvorfälle-6',
              'vorbereitungfürsicherheitsvorfälle-7', 'itadministration-2', 'organisationundpersonal-6',
              'umgangmitinformationen-6', 'mobileendgeräte-3', 'mobileendgeräte-4'],
    # ── Integrität ───────────────────────────────────────────────────
    'IN-01': ['sicherheitsmechanismen-8', 'sicherheitsmechanismen-9', 'sicherheitsmechanismen-10',
              'netze-12', 'netze-13', 'webserverundwebanwendungen-9'],
    'IN-02': ['backup-6', 'sicherheitsmechanismen-10'],
    'IN-03': ['sicherheitsmechanismen-1', 'sicherheitsmechanismen-2', 'sicherheitsmechanismen-3',
              'sicherheitsmechanismen-4', 'sicherheitsmechanismen-6', 'sicherheitsmechanismen-7',
              'client-4', 'client-8', 'client-10', 'itadministration-10', 'itadministration-11',
              'itadministration-12', 'itadministration-13', 'itadministration-14',
              'itadministration-15', 'bürosoftware-2', 'bürosoftware-5', 'bürosoftware-6',
              'bürosoftware-10', 'bürosoftware-16', 'bürosoftware-17', 'mobileendgeräte-12',
              'mobileendgeräte-18', 'serversysteme-14', 'serversysteme-15', 'serversysteme-16',
              'serversysteme-25', 'webserverundwebanwendungen-8'],
    # Härtung: nur datenschutzrelevante Punkte (keine reine Infrastruktur-Härtung wie
    # DNS-/Server-Core-/Fax-Details — diese bleiben bewusst ohne TOM-Bezug).
    'IN-04': ['client-7', 'client-9', 'serversysteme-4', 'serversysteme-12', 'netze-4', 'netze-8',
              'netze-22', 'bürosoftware-3', 'bürosoftware-4', 'bürosoftware-18', 'mobileendgeräte-2',
              'mobileendgeräte-8', 'mobileendgeräte-11', 'mobileendgeräte-13', 'mobileendgeräte-14',
              'webserverundwebanwendungen-3', 'webserverundwebanwendungen-7', 'itadministration-17',
              'itadministration-18'],
    # ── Vertraulichkeit ──────────────────────────────────────────────
    'VT-01': ['rollenberechtigungenauthentisierung-1', 'rollenberechtigungenauthentisierung-2',
              'rollenberechtigungenauthentisierung-3', 'rollenberechtigungenauthentisierung-4',
              'rollenberechtigungenauthentisierung-5', 'rollenberechtigungenauthentisierung-6',
              'rollenberechtigungenauthentisierung-7', 'rollenberechtigungenauthentisierung-9',
              'rollenberechtigungenauthentisierung-11', 'rollenberechtigungenauthentisierung-13',
              'rollenberechtigungenauthentisierung-14', 'rollenberechtigungenauthentisierung-15',
              'rollenberechtigungenauthentisierung-16', 'client-1', 'client-2', 'client-3',
              'itadministration-3', 'itadministration-5', 'itadministration-6', 'itadministration-7',
              'mobileendgeräte-9', 'mobileendgeräte-10', 'webserverundwebanwendungen-12',
              'webserverundwebanwendungen-13', 'druckerundmultifunktionsgeräte-2',
              'druckerundmultifunktionsgeräte-4', 'serversysteme-8', 'serversysteme-22',
              'serversysteme-28', 'organisationundpersonal-12'],
    'VT-02': ['client-13', 'mobileendgeräte-17', 'netze-18', 'netze-25', 'netze-26',
              'itadministration-21', 'bürosoftware-12', 'bürosoftware-19', 'serversysteme-10',
              'serversysteme-11', 'serversysteme-27', 'webserverundwebanwendungen-10',
              'webserverundwebanwendungen-11', 'arbeitaußerhalbderinstitution-2'],
    'VT-03': ['serverraumunddatenträgerarchiv-1', 'serverraumunddatenträgerarchiv-5',
              'serverraumunddatenträgerarchiv-8', 'serverraumunddatenträgerarchiv-10',
              'serversysteme-1', 'arbeitinnerhalbderinstitutionhaustechnik-1',
              'arbeitinnerhalbderinstitutionhaustechnik-2', 'arbeitinnerhalbderinstitutionhaustechnik-4',
              'arbeitinnerhalbderinstitutionhaustechnik-5', 'rollenberechtigungenauthentisierung-8',
              'rollenberechtigungenauthentisierung-10', 'rollenberechtigungenauthentisierung-12',
              'netze-19', 'netze-21', 'organisationundpersonal-11', 'telefonieundfax-1',
              'telefonieundfax-3', 'druckerundmultifunktionsgeräte-3'],
    'VT-04': ['organisationundpersonal-4', 'organisationundpersonal-5', 'organisationundpersonal-10',
              'organisationundpersonal-14', 'organisationundpersonal-15', 'organisationundpersonal-16',
              'organisationundpersonal-17', 'organisationundpersonal-18', 'mobileendgeräte-1',
              'mobileendgeräte-5', 'mobileendgeräte-6', 'netze-16', 'umgangmitinformationen-1',
              'umgangmitinformationen-2', 'arbeitaußerhalbderinstitution-1',
              'arbeitaußerhalbderinstitution-4', 'arbeitaußerhalbderinstitution-5',
              'arbeitaußerhalbderinstitution-6', 'arbeitaußerhalbderinstitution-7'],
    # ── Nichtverkettung ──────────────────────────────────────────────
    'NV-01': ['netze-3', 'netze-5', 'netze-6', 'netze-7', 'netze-9', 'serversysteme-2',
              'serversysteme-3', 'serversysteme-18', 'bürosoftware-9'],
    'NV-02': ['serversysteme-7', 'serversysteme-20', 'webserverundwebanwendungen-2',
              'webserverundwebanwendungen-4', 'webserverundwebanwendungen-5'],
    # ── Transparenz ──────────────────────────────────────────────────
    'TR-01': ['bürosoftware-1', 'netze-1', 'netze-2'],
    'TR-03': ['itadministration-4', 'sicherheitsmechanismen-8', 'netze-12'],
    'TR-04': ['outsourcingundcloud-1', 'outsourcingundcloud-2', 'outsourcingundcloud-3',
              'outsourcingundcloud-4', 'outsourcingundcloud-5', 'outsourcingundcloud-6',
              'bürosoftware-8', 'sicherheitsmechanismen-5', 'itadministration-22'],
    'TR-05': ['organisationundpersonal-1', 'organisationundpersonal-2', 'organisationundpersonal-3',
              'organisationundpersonal-6', 'organisationundpersonal-7', 'organisationundpersonal-8',
              'organisationundpersonal-9', 'organisationundpersonal-13', 'itadministration-8'],
}

# Zusätzliche Standard-TOM, die die WiBA-Basis-Absicherung stark abdeckt (Seed-Ergänzung).
ZUSATZ_SEEDS: list[dict[str, str]] = [
    {'ziel': 'Integrität', 'massnahme_key': 'IN-04',
     'titel': 'Sichere Konfiguration und Härtung von IT-Systemen',
     'beschreibung': 'Nicht benötigte Dienste/Funktionen deaktivieren, sichere Standardkonfigurationen, '
                     'Netzsegmentierung und Fernwartung absichern (Art. 25 Abs. 1, Art. 32).'},
    {'ziel': 'Vertraulichkeit', 'massnahme_key': 'VT-04',
     'titel': 'Sensibilisierung und Verpflichtung der Beschäftigten',
     'beschreibung': 'Regelungen zur sicheren IT-Nutzung, Schulung/Sensibilisierung und Verpflichtung '
                     'auf Vertraulichkeit (Art. 29, Art. 32 Abs. 4).'},
    {'ziel': 'Transparenz', 'massnahme_key': 'TR-04',
     'titel': 'Steuerung von Auftragsverarbeitern und Cloud-Diensten',
     'beschreibung': 'Dienstleister dokumentieren, vertraglich verpflichten und Leistungserbringung '
                     '(Standort, Schnittstellen) prüfen (Art. 28).'},
    {'ziel': 'Transparenz', 'massnahme_key': 'TR-05',
     'titel': 'Zuständigkeiten und Sicherheitsorganisation',
     'beschreibung': 'Verantwortlichkeiten, Vertretungen und Ansprechpersonen für Informationssicherheit '
                     'und Datenschutz festlegen und bekannt machen (Art. 24, Art. 32).'},
]

ANTWORT_LABEL = {'ja': 'Ja', 'nein': 'Nein', 'offen': 'Offen', 'nicht_relevant': 'Nicht relevant'}

_WIBA_DB = Path('data/db/wiba.sqlite')


def tom_keys_for_control(control_id: str) -> list[str]:
    """Inverse Sicht: welche TOM belegt eine WiBA-Prüffrage?"""
    return [k for k, ids in TOM_WIBA_MAPPING.items() if control_id in ids]


def control_index() -> dict[str, list[str]]:
    """control_id → [TOM-Keys] (für den WiBA-Filter „TOM-relevant")."""
    idx: dict[str, list[str]] = {}
    for key, ids in TOM_WIBA_MAPPING.items():
        for cid in ids:
            idx.setdefault(cid, []).append(key)
    return idx


def status_from_answers(answers: list[str]) -> int | None:
    """0–5 aus WiBA-Antworten: Anteil „ja" im Scope (``nicht_relevant`` außen vor).

    ``None`` = nichts im Scope (keine Ableitung möglich)."""
    in_scope = [a for a in answers if a != 'nicht_relevant']
    if not in_scope:
        return None
    ja = sum(1 for a in in_scope if a == 'ja')
    return int(5 * ja / len(in_scope) + 0.5)  # kaufmännisch runden (round() rundet 2,5 → 2)


def _norm(s: str) -> str:
    return ' '.join(str(s or '').lower().split())


def resolve_wiba_projekt(dsgvo_projekt: dict[str, Any], wiba_db: Path = _WIBA_DB) -> str | None:
    """WiBA-Instanz eines DSGVO-Projekts: explizite Verknüpfung (meta.linked_wiba_projekt)
    oder dieselbe Firma (``unternehmen``; bei mehreren die zuletzt geänderte)."""
    from wiba import db as wdb
    meta = dsgvo_projekt.get('meta') if isinstance(dsgvo_projekt.get('meta'), dict) else {}
    projekte = wdb.list_projekte(wiba_db)
    linked = str(meta.get('linked_wiba_projekt') or '').strip()
    if linked and any(p.get('name') == linked for p in projekte):
        return linked
    firma = _norm(dsgvo_projekt.get('unternehmen', ''))
    if not firma:
        return None
    treffer = [p for p in projekte if _norm(p.get('unternehmen', '')) == firma]
    if not treffer:
        return None
    treffer.sort(key=lambda p: str(p.get('updated_at') or ''), reverse=True)
    return treffer[0].get('name')


def wiba_kandidaten(wiba_db: Path = _WIBA_DB) -> list[dict[str, str]]:
    from wiba import db as wdb
    return [{'name': p.get('name', ''), 'unternehmen': p.get('unternehmen', '')}
            for p in wdb.list_projekte(wiba_db)]


def ableitung(dsgvo_projekt: dict[str, Any], wiba_db: Path = _WIBA_DB) -> dict[str, Any]:
    """Je TOM: verknüpfte Prüffragen inkl. Antwort/Notiz, Zählung und abgeleiteter Status."""
    from wiba import db as wdb
    wiba_name = resolve_wiba_projekt(dsgvo_projekt, wiba_db)
    katalog = {f['control_id']: f for f in wdb.list_prueffragen(wiba_db)}
    antworten = wdb.load_antworten(wiba_db, wiba_name) if wiba_name else {}
    items: dict[str, Any] = {}
    for key, ids in TOM_WIBA_MAPPING.items():
        fragen = []
        for cid in ids:
            if cid not in katalog:  # Katalog nicht geladen / Frage entfallen
                continue
            a = antworten.get(cid, {})
            st = str(a.get('status') or 'offen')
            fragen.append({'control_id': cid, 'nr': katalog[cid].get('nr'),
                           'theme_key': katalog[cid].get('theme_key', ''),
                           'frage': katalog[cid].get('frage', ''),
                           'status': st, 'notiz': a.get('notiz', '') or ''})
        counts = {s: sum(1 for f in fragen if f['status'] == s) for s in ANTWORT_LABEL}
        items[key] = {
            'fragen': fragen,
            'counts': counts,
            'in_scope': len(fragen) - counts['nicht_relevant'],
            'status_abgeleitet': status_from_answers([f['status'] for f in fragen]) if wiba_name else None,
        }
    return {'wiba_projekt': wiba_name, 'katalog_geladen': bool(katalog), 'items': items}


def effektive_quelle(massnahme: dict[str, Any]) -> str:
    """``wiba`` | ``manuell``. Unbelegt (Bestand): manuell, sobald bewertet; sonst WiBA,
    falls die TOM verknüpfte Prüffragen hat."""
    q = massnahme.get('status_quelle')
    if q in ('wiba', 'manuell'):
        return q
    if int(massnahme.get('status') or 0) > 0:
        return 'manuell'
    return 'wiba' if massnahme.get('massnahme_key') in TOM_WIBA_MAPPING else 'manuell'


def sync_projekt(dsgvo_db: Path, projekt_name: str, wiba_db: Path = _WIBA_DB) -> dict[str, Any]:
    """Status aller TOM mit Quelle WiBA aus den WiBA-Antworten nachziehen (idempotent)."""
    from dsgvo.db import load_projekt
    from dsgvo import tom_katalog as tk
    projekt = load_projekt(dsgvo_db, projekt_name)
    if not projekt:
        return {'updated': [], 'wiba_projekt': None}
    abl = ableitung(projekt, wiba_db)
    if not abl['wiba_projekt']:
        return {'updated': [], 'wiba_projekt': None}
    updated = []
    for m in tk.list_massnahmen(dsgvo_db, projekt_name):
        key = m['massnahme_key']
        it = abl['items'].get(key)
        if not it or effektive_quelle(m) != 'wiba':
            continue
        neu = it['status_abgeleitet']
        if neu is None:
            continue
        if int(m.get('status') or 0) != neu or m.get('status_quelle') != 'wiba':
            tk.set_status_wiba(dsgvo_db, projekt_name, key, neu)
            updated.append({'massnahme_key': key, 'alt': int(m.get('status') or 0), 'neu': neu})
    return {'updated': updated, 'wiba_projekt': abl['wiba_projekt']}


def sync_for_wiba_projekt(wiba_projekt: str, dsgvo_db: Path = Path('data/db/dsgvo.sqlite'),
                          wiba_db: Path = _WIBA_DB) -> list[dict[str, Any]]:
    """Nach einer WiBA-Änderung: alle DSGVO-Projekte nachziehen, die diese WiBA-Instanz nutzen."""
    from dsgvo.db import list_projekte, load_projekt
    out = []
    for name in list_projekte(dsgvo_db):
        p = load_projekt(dsgvo_db, name)
        if p and resolve_wiba_projekt(p, wiba_db) == wiba_projekt:
            res = sync_projekt(dsgvo_db, name, wiba_db)
            if res['updated']:
                out.append({'projekt': name, **res})
    return out


def entwurf_umsetzung(massnahme: dict[str, Any], fragen: list[dict[str, Any]],
                      wiba_projekt: str = '') -> str:
    """Deterministischer Entwurf der Umsetzungsbeschreibung aus den WiBA-Antworten."""
    ja = [f for f in fragen if f['status'] == 'ja']
    nein = [f for f in fragen if f['status'] == 'nein']
    offen = [f for f in fragen if f['status'] == 'offen']
    zeilen = [f"{massnahme.get('titel') or massnahme.get('massnahme_key')} — Umsetzungsstand laut "
              f"BSI-WiBA-Basis-Absicherung{f' ({wiba_projekt})' if wiba_projekt else ''}:"]
    if ja:
        zeilen.append('')
        zeilen.append('Umgesetzt:')
        for f in ja:
            notiz = f" — {f['notiz'].strip()}" if f.get('notiz', '').strip() else ''
            zeilen.append(f"• {f['frage']} (Ja){notiz}")
    if nein:
        zeilen.append('')
        zeilen.append('Noch nicht umgesetzt (Handlungsbedarf):')
        for f in nein:
            zeilen.append(f"• {f['frage']}")
    if offen:
        zeilen.append('')
        zeilen.append(f"Noch nicht geprüft: {len(offen)} Prüffrage(n).")
    if not fragen:
        zeilen.append('Keine verknüpften WiBA-Prüffragen vorhanden.')
    return '\n'.join(zeilen)


def build_formulierung_prompt(massnahme: dict[str, Any], fragen: list[dict[str, Any]],
                              firma: str = '') -> str:
    """KI-Prompt: TOM-Umsetzungsbeschreibung (Art. 30 Abs. 1 lit. g / Art. 32) aus WiBA."""
    lines = [
        'Du bist Datenschutz-Experte (DSGVO Art. 32, Standard-Datenschutzmodell).',
        'Formuliere für die folgende technische und organisatorische Maßnahme (TOM) eine '
        'prüffähige Umsetzungsbeschreibung für die TOM-Dokumentation (Art. 30 Abs. 1 lit. g DSGVO).',
        'Nutze AUSSCHLIESSLICH die unten stehenden Antworten aus der BSI-WiBA-Basis-Absicherung. '
        'Erfinde keine Maßnahmen. Mit „Nein" beantwortete Punkte als offene Lücken benennen.',
        '',
        f"## Organisation: {firma or '(nicht angegeben)'}",
        f"## TOM: {massnahme.get('massnahme_key')} — {massnahme.get('titel', '')}",
        f"Gewährleistungsziel (SDM): {massnahme.get('ziel', '')}",
        f"Beschreibung: {massnahme.get('beschreibung', '')}",
        '',
        '## WiBA-Prüffragen und Antworten',
    ]
    for f in fragen:
        notiz = f" | Notiz: {f['notiz'].strip()}" if f.get('notiz', '').strip() else ''
        lines.append(f"- [{ANTWORT_LABEL.get(f['status'], f['status'])}] {f['frage']}{notiz}")
    if not fragen:
        lines.append('- (keine verknüpften Prüffragen)')
    lines += [
        '',
        'Antworte ausschließlich als JSON:',
        '{"umsetzung": "Fließtext, 3–8 Sätze, sachlich, im Präsens", '
        '"luecken": ["offene Punkte …"]}',
    ]
    return '\n'.join(lines)
