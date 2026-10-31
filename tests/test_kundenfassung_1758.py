"""Kundenfassung: zeigbar statt intern (#1758).

Rechtlich bekommt der Kunde zweierlei — die Informationen nach Anhang II
(Art. 13 Abs. 18) und die EU-Konformitätserklärung (Art. 28). Die
Risikoabschätzung gehört **nicht** dazu; sie geht in die technische
Dokumentation und von dort an die Marktaufsicht.

Der Fehler ist hier asymmetrisch: Eine zu knappe Kundenfassung kostet eine
Rückfrage, eine zu offene kostet Vertrauen oder liefert einem Angreifer
Vorarbeit. Deshalb wird **additiv** gebaut, und deshalb prüft der wichtigste
Test unten nicht, was drinsteht, sondern was nicht drinstehen darf.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from cra import db as cdb
from cra import konformitaet_db as kdb
from cra import kundenfassung

FIRMA = 'pytest-firma-1758'
VER = '7.0.0'


def _text(blob: bytes) -> str:
    from docx import Document
    return "\n".join(p.text for p in Document(io.BytesIO(blob)).paragraphs)


@pytest.fixture
def projekt(tmp_path, request):
    """Eigenes Projekt je Test — das Schema kommt aus dem Dateinamen, nicht
    aus dem Pfad (`shared/db.py`), alle Tests teilen sich also ``cra``."""
    name = f'pytest-1758-{request.node.name[:40]}'
    db = tmp_path / 'cra.sqlite'
    cdb.delete_projekt(db, name)
    cdb.save_projekt(db, name=name, unternehmen=FIRMA, produkt='Testprodukt',
                     beschreibung='Produkt mit digitalen Elementen')
    kdb.save_konformitaet(db, name, {'release_version': VER, 'bewertungsweg': 'A',
                                     'bewertung_abgeschlossen': True})
    yield name, db
    cdb.delete_projekt(db, name)


# ── Die Abgrenzung — der eigentliche Zweck ──────────────────────────────────
def test_keine_internen_begriffe_im_dokument(projekt):
    """Der wichtigste Test: Was nicht hineingehört, darf nicht hinein.

    Geprüft wird das **erzeugte Dokument**, nicht die Absicht des Renderers.
    """
    name, db = projekt
    cdb.upsert_vuln(db, name, {'cve_id': 'CVE-2026-9001', 'titel': 'Offener Befund',
                               'schwere': 'critical', 'status': 'open'})
    text = _text(kundenfassung.build_docx(name, db_path=db))
    for begriff in kundenfassung.VERBOTENE_BEGRIFFE:
        assert begriff.lower() not in text.lower(), f'„{begriff}" steht in der Kundenfassung'


def test_offene_schwachstellen_erscheinen_nicht(projekt):
    """Offene Befunde sind die Angriffsfläche von heute. Nur behobene mit
    veröffentlichtem Hinweis gehören hinein (Anhang I Teil II Nr. 4)."""
    name, db = projekt
    cdb.upsert_vuln(db, name, {'cve_id': 'CVE-2026-9001', 'titel': 'Offen',
                               'schwere': 'critical', 'status': 'open'})
    cdb.upsert_vuln(db, name, {'cve_id': 'CVE-2026-9002', 'titel': 'Behoben',
                               'schwere': 'high', 'status': 'fixed',
                               'fixed_in_version': VER,
                               'advisory_url': 'https://example.com/a/9002'})
    text = _text(kundenfassung.build_docx(name, db_path=db))
    assert 'CVE-2026-9002' in text
    assert 'CVE-2026-9001' not in text, 'offene Schwachstelle in der Kundenfassung'


def test_behobene_ohne_advisory_erscheinen_nicht(projekt):
    """Ohne veröffentlichten Hinweis gibt es nichts zu verweisen — und die
    bloße Existenz einer behobenen Lücke ist für den Kunden keine Information,
    sondern ein Hinweis auf ungeschützte Altversionen."""
    name, db = projekt
    cdb.upsert_vuln(db, name, {'cve_id': 'CVE-2026-9003', 'titel': 'Behoben, still',
                               'schwere': 'high', 'status': 'fixed',
                               'fixed_in_version': VER, 'advisory_url': ''})
    assert 'CVE-2026-9003' not in _text(kundenfassung.build_docx(name, db_path=db))


def test_sammeln_liefert_nur_erlaubte_bloecke(projekt):
    """Additiv heißt: Die Datensammlung kennt den internen Bericht gar nicht."""
    name, db = projekt
    d = kundenfassung.sammle(name, db_path=db)
    erlaubt = {'erstellt_am', 'projekt_name', 'produkt', 'konformitaet', '_record',
               'erklaerung_archiv', 'support', 'meldestelle', 'advisories',
               'sbom', 'risikomanagement',
               # #1824: Sicherheitstests. Erlaubt wird **Art und Zeitpunkt** —
               # und der erklärte Verzicht, weil ein Dokument, das ihn
               # verschweigt, den Empfänger in die Irre führt. Was ein Test
               # gefunden hat, bleibt draußen: Das ist die Angriffsfläche von
               # heute, wie bei den offenen Schwachstellen. Dass dieser Eintrag
               # hier von Hand dazukommen musste, ist der Zweck der Liste.
               'tests'}
    assert set(d) <= erlaubt, set(d) - erlaubt


# ── Der Inhalt ──────────────────────────────────────────────────────────────
def test_anhang_ii_angaben_stehen_drin(projekt):
    """Das ist, was der Kunde rechtlich bekommen muss."""
    name, db = projekt
    cdb.save_support_period(db, name, {'markteintritt_datum': '2026-01-01',
                                       'support_jahre': 5,
                                       'update_kanal': 'https://example.com/updates'})
    cdb.save_psirt(db, name, {'disclosure_policy_url': 'https://example.com/security',
                              'psirt_contacts': 'security@example.com'})
    text = _text(kundenfassung.build_docx(name, db_path=db))
    assert 'Unterstützungszeitraum' in text
    assert 'example.com/updates' in text
    assert 'security@example.com' in text
    assert 'Schwachstellen melden' in text


def test_ohne_erklaerung_kein_ce_und_klare_aussage(projekt):
    """Ohne ausgestellte Erklärung darf weder das CE-Zeichen noch eine
    Konformitätsaussage behauptet werden."""
    name, db = projekt
    text = _text(kundenfassung.build_docx(name, db_path=db))
    assert 'noch nicht ausgestellt' in text
    assert 'nicht ausweisbar' in text or 'nicht angebracht' in text


def test_risikoabschaetzung_wird_benannt_aber_nicht_gezeigt(projekt):
    """Der Kunde erfährt, dass es sie gibt — nicht, was darin steht."""
    name, db = projekt
    text = _text(kundenfassung.build_docx(name, db_path=db))
    assert 'Risikomanagement' in text
    assert 'nicht veröffentlicht' in text


def test_typ_ist_im_berichts_center_registriert():
    from cra.berichte_provider import CATALOG

    typen = {s.key for s in CATALOG}
    assert 'kundenfassung' in typen


def test_summary_context_hat_die_pflichtschluessel(projekt):
    """#1725: Ohne diese beiden Schlüssel berichtet die KI „keine Daten"."""
    name, db = projekt
    ctx = kundenfassung.summary_context(name, db_path=db)
    assert 'reifegrad' in ctx and 'offene' in ctx
    assert ctx['offene'] == [], 'offene Punkte gehören nicht in die Kundenfassung'
