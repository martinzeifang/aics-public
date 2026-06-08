"""#1000 — Export-Dateiname enthält Datum, Projektname und PG/GG."""
import re
from datetime import datetime

from gutachten import gerichtsgutachten_gen as gen


def test_basename_privat_pg():
    base = gen.export_basename({'name': 'PG-2026-007', 'gutachten_art': 'privat'})
    assert base == f"{datetime.now():%Y-%m-%d}_PG-2026-007_PG"


def test_basename_gericht_gg():
    base = gen.export_basename({'name': 'Müller ./. Meier', 'gutachten_art': 'gericht'})
    assert base.endswith('_GG')
    assert datetime.now().strftime('%Y-%m-%d') in base
    # Sonderzeichen datei-sicher ersetzt
    assert re.fullmatch(r'[A-Za-z0-9._-]+', base)


def test_basename_defaults():
    # Fehlende Felder → Default-Name + GG
    base = gen.export_basename({})
    assert base == f"{datetime.now():%Y-%m-%d}_Gutachten_GG"
