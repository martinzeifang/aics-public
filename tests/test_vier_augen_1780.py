"""Niemand leistet beide Unterschriften (#1780).

Die Trennung gehört an die **Handlung**, nicht an die Rechtevergabe: Wer beide
Rechte hält, ist in kleinen Häusern der Normalfall — unzulässig ist, dass
dieselbe Person beide Unterschriften unter denselben Vorgang setzt.

Die Regel stand an zwei Stellen im Code (CRA #1743, AI Act #1756) und fehlte an
der dritten: Im **DSGVO-Jahresbericht** konnte dieselbe Person als
Geschäftsführung freigeben und als Datenschutzbeauftragte:r signieren. Ein
Bericht, der zwei Verantwortliche nennt und von einer Person stammt, belegt das
Gegenteil dessen, was er behauptet.

Diese Tests halten beides fest: die gemeinsame Regel und jede Stelle, an der
unterschrieben wird. Kommt eine vierte dazu, soll hier sichtbar werden, dass
sie fehlt.
"""
from __future__ import annotations

import pytest

from shared import vier_augen

PROJ = 'pytest-vier-augen-1780'


# ── Die Regel selbst ────────────────────────────────────────────────────────
def test_dieselbe_person_erkennt_schreibweisen():
    assert vier_augen.dieselbe_person('user-001', 'USER-001')
    assert vier_augen.dieselbe_person(' user-001 ', 'user-001')
    assert not vier_augen.dieselbe_person('user-001', 'user-002')


def test_unbekannte_erste_person_blockiert_nicht():
    """Altbestand ohne zugeordnete erste Unterschrift.

    Lässt sich nicht zeigen, dass es dieselbe Person ist, darf die zweite
    Unterschrift nicht dauerhaft blockiert sein — sonst wäre jeder Vorgang aus
    der Zeit vor den Spalten unabschließbar.
    """
    assert not vier_augen.dieselbe_person('', 'user-001')
    assert not vier_augen.dieselbe_person(None, 'user-001')
    vier_augen.pruefe('', 'user-001', erste_handlung='einreicht',
                      zweite_handlung='freigeben')


def test_pruefe_nennt_die_handlungen():
    with pytest.raises(vier_augen.VierAugenVerletzt) as fehler:
        vier_augen.pruefe('u1', 'u1', erste_handlung='freigibt',
                          zweite_handlung='signieren',
                          rechtsgrundlage='Art. 5 Abs. 2 DSGVO')
    text = str(fehler.value)
    assert 'freigibt' in text and 'signieren' in text
    assert 'zweite Person' in text and 'Art. 5 Abs. 2' in text
    assert fehler.value.as_dict()['code'] == 'vier_augen'


def test_verletzung_ist_ein_fachfehler():
    """``ValueError`` — die Endpunkte liefern Fachfehler bereits als 409 aus.

    Als eigener Fehlertyp ohne diese Verwandtschaft käme beim Anwender ein
    HTTP 500 an: „Interner Serverfehler" statt „holen Sie eine zweite Person".
    """
    assert issubclass(vier_augen.VierAugenVerletzt, ValueError)


# ── Stelle 1: CRA-Release-Vorgang (#1743) ───────────────────────────────────
@pytest.fixture
def cra_vorgang(tmp_path):
    from cra import konformitaet_db as kdb

    db = tmp_path / 'cra.sqlite'
    kdb.save_konformitaet(db, PROJ, {'release_version': '1.0.0', 'bewertungsweg': 'A',
                                     'bewertung_abgeschlossen': True})
    return db


def test_cra_einreicher_darf_nicht_freigeben(cra_vorgang):
    from cra import konformitaet_db as kdb

    kdb.einreichen(cra_vorgang, PROJ, '1.0.0', von='user-dev')
    with pytest.raises(vier_augen.VierAugenVerletzt, match='zweite Person'):
        kdb.freigeben(cra_vorgang, PROJ, '1.0.0', von='user-dev')
    rec = kdb.freigeben(cra_vorgang, PROJ, '1.0.0', von='user-compliance')
    assert rec['freigabe_status'] == 'freigegeben'


def test_cra_erneutes_einreichen_macht_niemanden_zum_freigeber(cra_vorgang):
    """Der Weg um die Regel herum: zurückweisen lassen, selbst neu einreichen.

    ``erstellt_von`` wird deshalb nur beim ersten Mal gesetzt.
    """
    from cra import konformitaet_db as kdb

    kdb.einreichen(cra_vorgang, PROJ, '1.0.0', von='user-dev')
    kdb.zurueckweisen(cra_vorgang, PROJ, '1.0.0', von='user-compliance',
                      grund='Bitte die SBOM nachreichen, sie fehlt noch.')
    kdb.einreichen(cra_vorgang, PROJ, '1.0.0', von='user-compliance')
    with pytest.raises(vier_augen.VierAugenVerletzt):
        kdb.freigeben(cra_vorgang, PROJ, '1.0.0', von='user-dev')


# ── Stelle 2: AI-Act-Änderungsvorgang (#1756) ───────────────────────────────
@pytest.fixture
def aiact_vorgang(pg):
    from ai_act import aenderungen_db as adb

    db = adb.DB_PATH
    adb.ensure_table(db)
    adb.create_aenderung(db, PROJ, {'stand': '2026-A', 'grund_art': 'nachtraining',
                                    'beschreibung': 'Nachtraining mit neuen Daten'})
    # Ohne beantwortete Kernfrage (Art. 43 Abs. 4) lässt sich nicht einreichen.
    adb.set_wesentlich(db, PROJ, '2026-A', 'ja',
                       grund='Nachtraining mit neuen Trainingsdaten, Leistung ändert sich.',
                       von='user-dev')
    return db


def test_aiact_einreicher_darf_nicht_freigeben(aiact_vorgang):
    from ai_act import aenderungen_db as adb

    adb.einreichen(aiact_vorgang, PROJ, '2026-A', von='user-dev')
    with pytest.raises(vier_augen.VierAugenVerletzt, match='zweite Person'):
        adb.freigeben(aiact_vorgang, PROJ, '2026-A', von='user-dev')
    rec = adb.freigeben(aiact_vorgang, PROJ, '2026-A', von='user-compliance')
    assert rec['status'] == 'freigegeben'


# ── Stelle 3: DSGVO-Jahresbericht — hier fehlte die Regel ───────────────────
@pytest.fixture
def jahresbericht(pg):
    from dsgvo import jahresbericht_db as jdb

    jdb.ensure_table(jdb.DB_PATH)
    return jdb.DB_PATH


def test_dsgvo_freigeber_darf_nicht_signieren(jahresbericht):
    """Der Befund: Geschäftsführung und DSB waren dieselbe Person.

    #1128 hat die beiden Rollen eingeführt, damit zwei Verantwortliche
    unterschreiben. Ohne diese Prüfung war die Trennung dekorativ.
    """
    from dsgvo import jahresbericht_db as jdb

    jdb.freigeben(jahresbericht, PROJ, 2026, von='user-gf')
    with pytest.raises(vier_augen.VierAugenVerletzt, match='zweite Person'):
        jdb.signieren(jahresbericht, PROJ, 2026, von='user-gf',
                      name='Gf Person', pdf_bytes=b'%PDF-1.4 test')
    rec = jdb.signieren(jahresbericht, PROJ, 2026, von='user-dsb',
                        name='DSB Person', pdf_bytes=b'%PDF-1.4 test')
    assert rec['status'] == 'signiert'
    assert rec['freigabe_von'] == 'user-gf' and rec['signatur_von'] == 'user-dsb'


def test_dsgvo_signatur_ohne_freigabe_abgelehnt(jahresbericht):
    """Stand bisher nur im Endpunkt — eine Prüfung im Formular ist keine
    Eigenschaft der Anwendung (Lehre aus #1760)."""
    from dsgvo import jahresbericht_db as jdb

    with pytest.raises(ValueError, match='Freigabe'):
        jdb.signieren(jahresbericht, PROJ, 2026, von='user-dsb',
                      name='DSB', pdf_bytes=b'%PDF-1.4 test')


# ── Alle Stellen benutzen dieselbe Regel ────────────────────────────────────
def test_jede_unterschriftsstrecke_nutzt_den_gemeinsamen_pruefer():
    """Drei Kopien derselben Aussage sind drei Gelegenheiten, dass eine fehlt.

    Genau das war der Befund: zwei Formulierungen im Code, eine Lücke. Dieser
    Test wird rot, wenn eine Strecke wieder eigene Logik bekommt.
    """
    import inspect

    from ai_act import aenderungen_db
    from cra import konformitaet_db
    from dsgvo import jahresbericht_db

    strecken = {
        'cra.konformitaet_db.freigeben': konformitaet_db.freigeben,
        'ai_act.aenderungen_db.freigeben': aenderungen_db.freigeben,
        'dsgvo.jahresbericht_db.signieren': jahresbericht_db.signieren,
    }
    for name, fn in strecken.items():
        quelle = inspect.getsource(fn)
        assert 'vier_augen.pruefe' in quelle, (
            f'{name} prüft nicht über shared/vier_augen — eine eigene Kopie der '
            f'Regel ist die Fehlerklasse, die #1780 ausgelöst hat')
