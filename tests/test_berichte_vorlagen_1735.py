"""Berichts-Center rendert die hochgeladene Word-Vorlage (#1735).

Vorher nutzte **kein** Modul-Export die Vorlage: ``shared.templates.engine`` hatte in
der ganzen Anwendung genau einen Aufrufer, den Test-Export im Admin-UI. Der Anwender
lud eine Vorlage hoch, setzte sie als Standard — und im Modul kam weiter der
programmatische Bericht. Nichts schlug fehl, es passierte nur nicht.

Geprüft werden hier die Stellen, an denen die Brücke falsch liegen kann:
Modulschlüssel (``ai_act`` ↔ ``aiact``), Module ohne Adapter (``firmen``),
Vorlagen fremder Module, und dass der Weg ohne ``template_id`` unverändert bleibt.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from shared.reports import vorlagen as vb
from shared.templates import schema


# ── Modulschlüssel ──────────────────────────────────────────────────────────
def test_ai_act_findet_seine_vorlagen():
    """Das Berichts-Center registriert ``ai_act``, die Engine kennt ``aiact``.

    Ohne Normalisierung sucht AI Act unter einem Schlüssel, den die Engine nicht hat,
    und bekäme nie eine Vorlage angeboten.
    """
    assert vb.engine_modul("ai_act") == "aiact"
    assert vb.modul_hat_adapter("ai_act")


def test_uebrige_module_bleiben_unveraendert():
    for modul in ("cra", "nis2", "dsgvo", "wiba", "risikobewertung", "soc",
                  "compliance_audit"):
        assert vb.engine_modul(modul) == modul, modul
        assert vb.modul_hat_adapter(modul), modul


def test_modul_ohne_adapter_bietet_keine_vorlagen():
    """``firmen`` hat ein Berichts-Center, aber keinen Adapter.

    Würde das Frontend dort eine Auswahl zeigen, endete sie in einem 501.
    """
    assert not vb.modul_hat_adapter("firmen")
    assert vb.vorlagen("firmen") == []


def test_jeder_adapter_hat_eine_datenbank():
    """Ein fehlender Eintrag wäre ein KeyError mitten im Export."""
    fehlend = [m for m in schema.MODULE if m not in schema.MODULE_DB]
    assert not fehlend, f"ohne DB-Zuordnung: {fehlend}"


def test_rest_schicht_nutzt_dieselbe_zuordnung():
    """Die Zuordnung lag in der REST-Schicht; eine Kopie wäre die sechste
    Spiegel-Liste derselben Information (#1731)."""
    import server.api.templates as rest
    assert rest._MODULE_DB is schema.MODULE_DB


# ── Rendern ─────────────────────────────────────────────────────────────────
class _FakeDB:
    """Minimale Vorlagen-Registry im Speicher."""

    def __init__(self, rec: dict | None) -> None:
        self.rec = rec
        self.DEFAULT_DB_PATH = Path("/dev/null")

    def get_template(self, _db, tid):  # noqa: ANN001
        return self.rec if self.rec and self.rec["id"] == int(tid) else None

    def list_templates(self, _db, modul=None):  # noqa: ANN001
        if not self.rec or (modul and self.rec["modul"] != modul):
            return []
        return [self.rec]


def _rec(**kw):
    basis = {"id": 7, "modul": "compliance_audit", "name": "Kundenbericht",
             "version": 2, "ist_default": 1, "aktiv": 1}
    basis.update(kw)
    return basis


def test_vorlage_wird_gerendert(monkeypatch):
    """Der eigentliche Fehlerfall: DOCX muss durch die Engine laufen."""
    monkeypatch.setattr(vb, "tdb", _FakeDB(_rec()))
    monkeypatch.setattr(schema, "get_context_builder",
                        lambda m: (lambda db, p: {"projekt": {"name": p}}))
    gesehen: dict = {}

    def _render(db_path, tid, context):  # noqa: ANN001
        gesehen.update({"tid": tid, "context": context})
        return b"PK-DOCX"

    monkeypatch.setattr(vb.engine, "render_docx", _render)

    out = vb.render_vorlage("compliance_audit", 7, projekt="Cyberwoks",
                            typ="gesamt", fmt="docx")
    assert out == b"PK-DOCX"
    assert gesehen["tid"] == 7
    # Die Vorlage darf auf den gewählten Berichtstyp verzweigen.
    assert gesehen["context"]["bericht_typ"] == "gesamt"
    assert gesehen["context"]["projekt"] == {"name": "Cyberwoks"}


def test_pdf_laeuft_ueber_denselben_konverter(monkeypatch):
    """Der Anwender berichtete DOCX *und* PDF — beide Wege müssen die Vorlage nutzen."""
    monkeypatch.setattr(vb, "tdb", _FakeDB(_rec()))
    monkeypatch.setattr(schema, "get_context_builder", lambda m: (lambda db, p: {}))
    monkeypatch.setattr(vb.engine, "render_docx", lambda *a, **k: b"PK-DOCX")
    import shared.templates.pdf_converter as pc
    monkeypatch.setattr(pc, "convert_docx_to_pdf", lambda b: b"%PDF-" + b)

    assert vb.render_vorlage("compliance_audit", 7, fmt="pdf") == b"%PDF-PK-DOCX"


def test_fremde_vorlage_wird_abgewiesen(monkeypatch):
    """Sonst käme man über ein Modul mit schwächeren Rechten an fremde Berichte.

    Die Berichts-Routen hängen an den Permissions **ihres** Moduls; die Vorlage
    bestimmt, welcher Kontext-Builder und welche Datenbank gelesen werden.
    """
    monkeypatch.setattr(vb, "tdb", _FakeDB(_rec(modul="dsgvo")))
    with pytest.raises(vb.VorlageFehlt, match="dsgvo"):
        vb.render_vorlage("compliance_audit", 7)


def test_geloeschte_vorlage_wird_abgewiesen(monkeypatch):
    monkeypatch.setattr(vb, "tdb", _FakeDB(_rec(aktiv=0)))
    with pytest.raises(vb.VorlageFehlt):
        vb.render_vorlage("compliance_audit", 7)
    assert vb.vorlagen("compliance_audit") == []


def test_unbekannte_vorlage_wird_abgewiesen(monkeypatch):
    monkeypatch.setattr(vb, "tdb", _FakeDB(None))
    with pytest.raises(vb.VorlageFehlt):
        vb.render_vorlage("compliance_audit", 99)


def test_vorlagen_liste_fuer_die_auswahl(monkeypatch):
    monkeypatch.setattr(vb, "tdb", _FakeDB(_rec()))
    assert vb.vorlagen("compliance_audit") == [
        {"id": 7, "name": "Kundenbericht", "version": 2, "ist_default": True}]
    # Fremdes Modul sieht sie nicht.
    assert vb.vorlagen("dsgvo") == []


def test_defekte_registry_bricht_das_berichts_center_nicht(monkeypatch):
    """Frische Installation ohne Vorlagen-DB: Auswahl leer, Modul nutzbar."""
    class _Kaputt(_FakeDB):
        def list_templates(self, *a, **k):
            raise RuntimeError("keine DB")

    monkeypatch.setattr(vb, "tdb", _Kaputt(_rec()))
    assert vb.vorlagen("compliance_audit") == []


def test_render_callable_passt_zum_berichts_center(monkeypatch):
    """``core.generate_and_store`` ruft ``render(typ, fmt, projekt=, von=, bis=)``."""
    monkeypatch.setattr(vb, "tdb", _FakeDB(_rec()))
    monkeypatch.setattr(schema, "get_context_builder", lambda m: (lambda db, p: {}))
    monkeypatch.setattr(vb.engine, "render_docx", lambda *a, **k: b"PK")

    fn = vb.render_callable("compliance_audit", 7)
    assert fn("gesamt", "docx", projekt="X", von="2026-01-01", bis="2026-12-31") == b"PK"


def test_vorlage_name_fuer_das_protokoll(monkeypatch):
    monkeypatch.setattr(vb, "tdb", _FakeDB(_rec()))
    assert vb.vorlage_name("compliance_audit", 7) == "Kundenbericht v2"
    # Nicht ermittelbar → leer, nie ein Fehler im Erzeugungsweg.
    monkeypatch.setattr(vb, "tdb", _FakeDB(None))
    assert vb.vorlage_name("compliance_audit", 7) == ""


# ── Unveraenderter Standard-Weg ─────────────────────────────────────────────
def test_template_id_parser():
    """Ohne/mit unbrauchbarer Angabe bleibt es beim programmatischen Bericht."""
    from shared.reports.api import _template_id

    assert _template_id(None) == 0
    assert _template_id("") == 0
    assert _template_id("abc") == 0
    assert _template_id(0) == 0
    assert _template_id(-3) == 0
    assert _template_id("7") == 7


def test_historie_haelt_die_vorlage_fest():
    """Die Spalte muss auch auf einer **bestehenden** Tabelle entstehen.

    In jeder laufenden Installation existiert ``*_bericht_runs`` schon; ohne den
    idempotenten ``ADD COLUMN IF NOT EXISTS`` scheitert jedes Ablegen nach dem
    Update. Und ohne den Eintrag ist nicht nachvollziehbar, warum zwei Berichte
    desselben Typs verschieden aussehen.
    """
    from shared.reports import core

    db = Path("data/db/gutachten.sqlite")
    core.ensure_history(db)
    core.ensure_history(db)  # zweimal: idempotent

    res = core.generate_and_store(db, "compliance_audit", "gesamt",
                                  lambda typ, fmt, **kw: b"PK-DOCX",
                                  projekt="VorlagenTest1735", fmt="docx",
                                  vorlage="Kundenbericht v2")
    assert res["ok"], res
    lauf = next(r for r in core.list_runs(db, projekt="VorlagenTest1735")
                if r["id"] == res["id"])
    assert lauf["vorlage"] == "Kundenbericht v2"

    # Standard-Weg: leer, nicht NULL (das Frontend zeigt „—").
    ohne = core.generate_and_store(db, "compliance_audit", "gesamt",
                                   lambda typ, fmt, **kw: b"PK-DOCX",
                                   projekt="VorlagenTest1735", fmt="docx")
    lauf2 = next(r for r in core.list_runs(db, projekt="VorlagenTest1735")
                 if r["id"] == ohne["id"])
    assert lauf2["vorlage"] == ""


def test_generate_and_store_reicht_vorlage_nicht_an_den_renderer(monkeypatch):
    """``generate_and_store(**ctx)`` reicht Unbekanntes an ``render`` weiter.

    Wäre ``vorlage`` nur ein ``**ctx``-Eintrag, bekäme jeder programmatische
    Renderer ein Schlüsselwort, das er nicht kennt — TypeError beim Ablegen.
    """
    import inspect

    from shared.reports import core

    assert "vorlage" in inspect.signature(core.generate_and_store).parameters
    assert "vorlage" in inspect.signature(core.record_run).parameters
