"""#2129: Gutachter sehen nur Gutachten, bei denen sie eingetragen sind."""
from pathlib import Path

import gutachten.gerichts_db as g

DB = Path("data/db/gutachten.sqlite")


def _setup():
    g.ensure_db(DB)
    pid_a = g.save_gutachter(DB, name="Dr. Alice 2129", benutzer_id="u-alice")
    pid_b = g.save_gutachter(DB, name="Bob SV 2129", benutzer_id="u-bob")
    g.save_gerichts_projekt(DB, name="2129-Alice", gutachter_profil_id=pid_a, sv_name="Dr. Alice 2129")
    g.save_gerichts_projekt(DB, name="2129-Bob", gutachter_profil_id=pid_b, sv_name="Bob SV 2129")
    g.save_gerichts_projekt(DB, name="2129-Fremd", sv_name="Niemand 2129")
    g.save_pruefer(DB, projekt_name="2129-Bob", gutachter_profil_id=pid_a,
                   name="Dr. Alice 2129", rolle="zweitpruefer")
    g.save_pruefer(DB, projekt_name="2129-Fremd", name="Gast", rolle="weiterer",
                   benutzer_id="u-konto7")
    return pid_a, pid_b


def _namen(uid):
    return {p["name"] for p in g.list_gerichts_projekte(DB, nur_benutzer=uid)}


def test_primaer_und_pruefer_sichtbar():
    _setup()
    # Alice: primärer SV + Zweitprüferin bei Bob
    assert _namen("u-alice") == {"2129-Alice", "2129-Bob"}


def test_nur_eigenes():
    _setup()
    assert _namen("u-bob") == {"2129-Bob"}


def test_direkter_pruefer_ohne_profil():
    _setup()
    assert _namen("u-konto7") == {"2129-Fremd"}


def test_unbekanntes_konto_sieht_nichts():
    _setup()
    assert _namen("u-niemand") == set()


def test_ohne_scope_alle():
    _setup()
    alle = {p["name"] for p in g.list_gerichts_projekte(DB)}
    assert {"2129-Alice", "2129-Bob", "2129-Fremd"} <= alle


def test_projekt_sichtbar():
    _setup()
    assert g.projekt_sichtbar(DB, "2129-Bob", "u-alice")
    assert not g.projekt_sichtbar(DB, "2129-Fremd", "u-alice")
