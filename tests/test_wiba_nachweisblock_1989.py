"""WiBA zieht den gemeinsamen Nachweis-Block (#1989).

DER BEFUND
Nach #1985 („freigegebene Nachweise erreichen keinen Prompt") sollte der
Anwender seine 91 freigegebenen WiBA-Zuordnungen wirksam sehen. Beim
Nachsehen, **bevor** er testete, stellte sich heraus: **WiBA ruft den
gemeinsamen Aggregator überhaupt nicht.**

``shared/evidence_context.evidence_block_for`` hat fünf Aufrufer — CRA, NIS2,
AI Act, DSGVO und die Risikobewertung. WiBA hat stattdessen
``_firma_evidence_texts(firma, max_docs=5)``: den **Volltext der ersten fünf
Firmendokumente**, ohne jeden Bezug zur Prüffrage. Damit erreichte **keine**
der folgenden Quellen den WiBA-Prompt:

- die von Hand **freigegebenen Zuordnungen** (``relevance=2.0``, die höchste
  Stufe) — also genau das, was der Anwender seit Stunden pflegte;
- die **TOM-Maßnahmen** und die **verknüpften Risiken**;
- die **freigegebenen Pflichtdokumente** (#1937).

Alle drei liefert ``wiba/evidence_provider.py`` seit #1483/#1937 — und diese
Datei wird **ausschließlich** von ``build_context`` gelesen. Sie lag Monate
ohne Wirkung im Baum, und nichts schlug fehl.

Der Fix aus #1985 saß damit in einem Weg, den dieses Modul nicht geht: Er war
richtig und für WiBA wirkungslos.
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
WIBA_API = WURZEL / "server" / "api" / "wiba" / "__init__.py"

#: Jedes Modul mit einem Nachweis-Provider muss den gemeinsamen Block auch
#: **ziehen** — sonst liegt der Provider ohne Wirkung im Baum. Wert: die
#: Datei, in der der Aufruf steht.
MODUL_ZIEHT_BLOCK = {
    "cra": "server/api/cra/__init__.py",
    "nis2": "server/api/nis2.py",
    "ai_act": "server/api/aiact.py",
    "dsgvo": "server/api/dsgvo.py",
    "wiba": "server/api/wiba/__init__.py",
    "risikobewertung": "server/api/risikobewertung.py",
}


def test_jedes_modul_mit_provider_zieht_den_block():
    """Die Spiegel-Liste: Provider und Aufruf gehören zusammen.

    Ein Provider ohne Aufrufer sieht wie eine Fähigkeit aus und ist keine —
    genau wie ``delete_approved_mapping`` in #1988.
    """
    from shared.evidence_context import _PROVIDER_MODULES

    # Aliase (aiact ↔ ai_act) zählen einmal.
    module = {m for m in _PROVIDER_MODULES if m != "aiact"}
    assert module == set(MODUL_ZIEHT_BLOCK), (
        "Die Provider-Liste und die Aufrufer-Liste laufen auseinander: "
        f"{module ^ set(MODUL_ZIEHT_BLOCK)}")

    for modul, datei in MODUL_ZIEHT_BLOCK.items():
        quelle = (WURZEL / datei).read_text(encoding="utf-8")
        assert "evidence_block_for" in quelle, (
            f"{modul}: {datei} ruft `evidence_block_for` nicht. Dann liegt "
            f"{modul}/evidence_provider.py ohne Wirkung im Baum — die "
            f"freigegebenen Zuordnungen, TOM-Maßnahmen und verknüpften "
            f"Risiken erreichen den Prompt nicht (#1989).")


def test_der_block_wird_mit_der_prueffrage_als_id_geholt():
    """``requirement["id"]`` — nicht ``control_id``.

    Der Aggregator **und** der Provider lesen ``requirement["id"]``; die
    WiBA-Zeilen heißen ``control_id``. Ein ``ctrl``-Dict direkt zu übergeben
    liefert eine leere Liste, ohne dass etwas fehlschlägt — der Defekt wäre
    derselbe, nur eine Ebene tiefer.
    """
    quelle = WIBA_API.read_text(encoding="utf-8")
    rumpf = quelle.split("def _nachweis_block", 1)[1].split("\ndef ", 1)[0]
    assert "'id': control_id" in rumpf, (
        "Der Nachweis-Block wird ohne `id` geholt — er bliebe leer (#1989).")
    assert "evidence_block_for('wiba'" in rumpf


def test_der_prompt_traegt_den_block_vor_den_volltexten():
    """Reihenfolge mit Grund, und kein Widerspruch im Prompt."""
    from wiba.prompts import build_prompt

    ctrl = {"control_id": "netze-18", "frage": "Ist das WLAN verschlüsselt?"}
    block = ("## Vorhandene Nachweise (aus der Anwendung)\n"
             "- Freigegebener Nachweis: WPA3 ist aktiv.")
    texte = [{"filename": "TOM-Nachweis-02.md", "text": "Langer Volltext."}]

    mit = build_prompt(ctrl, {}, texte, evidence_block=block)
    assert "WPA3 ist aktiv" in mit
    assert mit.index("WPA3 ist aktiv") < mit.index("TOM-Nachweis-02.md"), (
        "Der gemeinsame Block trägt die gezielte, von einem Menschen "
        "bestätigte Aussage und gehört vor das ungefilterte Material.")


def test_ohne_block_ist_der_prompt_byte_identisch():
    """Die Zusage aus #1485 — sonst ist jeder Bestandstest hinfällig."""
    from wiba.prompts import build_prompt

    ctrl = {"control_id": "netze-18", "frage": "Ist das WLAN verschlüsselt?"}
    texte = [{"filename": "a.md", "text": "Text."}]
    assert build_prompt(ctrl, {}, texte) == build_prompt(
        ctrl, {}, texte, evidence_block="")
    assert build_prompt(ctrl, {}, texte) == build_prompt(
        ctrl, {}, texte, evidence_block="   ")


def test_der_hinweis_keine_nachweise_widerspricht_dem_block_nicht():
    """Oben ein freigegebener Beleg, unten „es liegen keine vor" — das darf
    nicht zusammen im Prompt stehen.

    Vorher hing der Hinweis allein an ``evidence_texts``. Ohne Dokumente, aber
    mit freigegebener Zuordnung hätte der Prompt sich selbst widersprochen —
    und das Modell hätte konservativ geantwortet, obwohl ein Beleg dasteht.
    """
    from wiba.prompts import build_prompt

    ctrl = {"control_id": "netze-18", "frage": "Frage?"}
    block = "## Vorhandene Nachweise\n- Freigegebener Nachweis: belegt."

    ohne_alles = build_prompt(ctrl, {}, [])
    assert "keine hochgeladenen Nachweise" in ohne_alles

    nur_block = build_prompt(ctrl, {}, [], evidence_block=block)
    assert "belegt." in nur_block
    assert "keine hochgeladenen Nachweise" not in nur_block


def test_eine_nachweisgestuetzte_bewertung_steht_im_revisionspfad():
    """#1497 galt in fünf Modulen; WiBA konnte es nicht, weil es keine
    Quellen hatte."""
    quelle = WIBA_API.read_text(encoding="utf-8")
    assert "audit_assessment('wiba'" in quelle
    assert re.search(r"if\s+quellen:", quelle), (
        "Der Revisionseintrag darf nur bei tatsächlich genutzter App-Evidenz "
        "entstehen (#1497) — sonst steht er unter jeder Bewertung.")
