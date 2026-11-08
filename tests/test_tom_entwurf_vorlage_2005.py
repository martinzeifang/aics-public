"""Der TOM-Entwurf ist ein Berichtstyp und trägt eine Word-Vorlage (#2005).

Der Befund aus dem Betrieb: Der Knopf „📝 TOM-Entwurf herunterladen (DOCX)" im
DSGVO-Reiter 🔒 TOM-Generator erzeugte ein Word-Dokument, für das sich **keine
Vorlage hinterlegen** ließ — ``GET /tom/export`` kannte keinen
``template_id``-Parameter. Gleichzeitig führte das Berichts-Center desselben
Moduls den Bereichsbericht ``tom``, und dort wirken Vorlagen seit #1735.

Es sind **zwei Dokumente** über dieselbe Sache: ``tom`` weist den erreichten
Stand nach (Katalog, Status, SDM-Ziele), ``tom_entwurf`` ist die
Arbeitsgrundlage, aus der ein Mensch das TOM-Dokument schreibt. Richtig ist
deshalb ein Renderer **je Dokument** und eine Vorlage für jedes von beiden —
nicht ein Dokument mit zwei Erzeugungswegen (#1727).

Vier Zusagen, für jede ein Test:

1. **Ohne ``template_id`` ändert sich nichts.** Der Datenweg ist aus dem
   Endpunkt nach ``dsgvo.tom`` gezogen; der Entwurf muss Absatz für Absatz
   derselbe sein wie der, den die alte Inline-Fassung erzeugt hat. Diese Zusage
   macht jeden Bestandstest zum Regressionsschutz (dasselbe Versprechen wie
   ``evidence_section`` und ``prompt_zusatz``).
2. **Mit Vorlage steht deren Rahmen im Dokument** — und die Entwurfsdaten sind
   darin druckbar. Ohne ``tom_entwurf`` im Kontext könnte eine Vorlage sie
   nicht setzen, und ohne Eintrag in ``DSGVO_VARIABLES`` würde die Prüfung aus
   #1741 die Vorlage schon beim Hochladen abweisen.
3. **Eine Vorlage eines anderen Berichts wird mit Klartext abgewiesen**, nicht
   als 500 (#1741) — und zwar mit **derselben** Antwort wie im
   Berichts-Center. Zwei Antworten auf dieselbe Ursache im selben Modul wären
   zwei Wahrheiten; deshalb hält ein Test beide Endpunkte gegeneinander.
4. **Generator und Berichts-Center erzeugen dasselbe Dokument**, verglichen
   Absatz für Absatz (Muster ``test_vorlagen_typ_firma_1777``).

Die DB-abhängigen Tests hängen am ``pg``-Fixture (tests/conftest.py).
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest
from docx import Document

from dsgvo import berichte_provider as bp
from dsgvo import tom as dtom
from shared.reports import vorlagen as bruecke
from shared.templates import db as tdb
from shared.templates import schema, validate

# Der Entwurf, den die Tests einspielen. Er deckt alle drei Listen ab, denn nur
# dann lässt sich zeigen, dass eine Vorlage sie **getrennt** setzen kann.
ENTWURF = {
    "abschnitte": {
        "TOM-A": {
            "vorhandene_massnahmen": ["Chipkarten-Zutrittssystem im Serverraum"],
            "luecken": ["Besucherregistrierung fehlt"],
            "empfehlungen": ["Besucherbuch einführen"],
        },
        "TOM-C": {
            "vorhandene_massnahmen": ["Rollen- und Rechtekonzept dokumentiert"],
            "luecken": [],
            "empfehlungen": [],
        },
    },
    "fazit": "Zutritt und Zugriff sind überwiegend geregelt.",
}


# ──────────────────────────────────────────────────────────────────────────────
# Hilfsmittel
# ──────────────────────────────────────────────────────────────────────────────
def _absaetze(daten: bytes) -> list[str]:
    """Der sichtbare Text eines DOCX — das, was der Anwender liest.

    Tabellen gehören dazu: Der programmatische TOM-Entwurf setzt **jede**
    Maßnahme in eine Tabelle, und ein Vergleich nur über die Absätze hätte von
    seinem Inhalt kein Wort gesehen.
    """
    doc = Document(io.BytesIO(daten))
    out = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for tb in doc.tables:
        for row in tb.rows:
            out.extend(c.text.strip() for c in row.cells if c.text.strip())
    return out


def _vorlagendatei(pfad: Path, zeilen: list[str]) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    d = Document()
    for z in zeilen:
        d.add_paragraph(z)
    d.save(str(pfad))
    return pfad


@pytest.fixture
def rest(pg, request):
    """Testclient + Admin-Header, aber erst nach dem Postgres-Check (wie #1741)."""
    return request.getfixturevalue("client"), request.getfixturevalue("auth_headers")


@pytest.fixture
def projekt(pg):
    """Ein DSGVO-Projekt mit gespeichertem KI-Entwurf."""
    from dsgvo.db import ensure_db, save_ai_draft, save_projekt

    ensure_db(bp.DB_PATH)
    name = f"pytest-2005-{uuid.uuid4().hex[:8]}"
    save_projekt(bp.DB_PATH, name, unternehmen="Nordlicht GmbH",
                 berater="pytest")
    save_ai_draft(bp.DB_PATH, name, "tom", ENTWURF)
    return name


@pytest.fixture
def upload(rest, tmp_path):
    """Lädt eine DSGVO-Vorlage hoch; liefert den Antwort-Body."""
    client, headers = rest

    def _tun(zeilen: list[str], **form) -> dict:
        pfad = _vorlagendatei(tmp_path / f"{uuid.uuid4().hex}.docx", zeilen)
        daten = {"file": (io.BytesIO(pfad.read_bytes()), "v.docx"),
                 "modul": "dsgvo", "name": f"pytest-2005-{uuid.uuid4().hex[:8]}"}
        daten.update({k: str(v) for k, v in form.items()})
        res = client.post("/api/templates", data=daten,
                          content_type="multipart/form-data", headers=headers)
        assert res.status_code == 201, res.get_data(as_text=True)
        return res.get_json()

    return _tun


# ──────────────────────────────────────────────────────────────────────────────
# 1 · Der Entwurf ist ein Berichtstyp — nur so kann er eine Vorlage tragen
# ──────────────────────────────────────────────────────────────────────────────
def test_entwurf_steht_im_katalog_und_ist_nicht_vorgeschrieben():
    spec = next((s for s in bp.CATALOG if s.key == dtom.ENTWURF_TYP), None)
    assert spec is not None, "tom_entwurf fehlt im DSGVO-Berichts-Center"
    # Art. 32 DSGVO schreibt für ein TOM-Dokument keine Gliederung vor; die
    # Abschnitte TOM-A…TOM-J sind unsere. ``vorgeschrieben`` gilt Dokumenten,
    # deren Aufbau dem Rechtstext gehört (#1777) — es hier zu setzen, würde die
    # Bedeutung des Kennzeichens verschieben.
    assert spec.vorgeschrieben is False
    # Und er ist etwas anderes als der Bereichsbericht ``tom`` (der Stand).
    assert any(s.key == "tom" for s in bp.CATALOG)
    assert spec.titel_en, "ohne englischen Titel eine Kachel ohne Namen (#1954)"


def test_admin_ui_kann_eine_vorlage_fuer_den_entwurf_annehmen():
    """Das ist der Mechanismus, der gefehlt hat.

    ``server/api/templates._bericht_typ_ok`` prüft den Geltungsbereich einer
    Vorlage gegen ``schema.berichte_typen`` — ein Dokument, das dort nicht
    steht, kann keine eigene Vorlage tragen.
    """
    schluessel = {s["key"] for s in schema.berichte_typen("dsgvo")}
    assert dtom.ENTWURF_TYP in schluessel


def test_entwurfsvariablen_sind_deklariert_und_aufloesbar(pg, projekt):
    """Ohne Deklaration weist #1741 jede Vorlage ab, die sie benutzt."""
    from dsgvo.template_context import DSGVO_VARIABLES, build_dsgvo_context

    keys = {v["key"] for v in DSGVO_VARIABLES}
    assert "tom_entwurf.abschnitte" in keys
    # Geprüft wird das **erste** Pfadsegment (#1741) — genau das muss tragen.
    erg = validate.pruefe_namen("dsgvo", ["tom_entwurf"])
    assert erg.ok, erg.unbekannt

    ctx = build_dsgvo_context(bp.DB_PATH, projekt)
    assert ctx["tom_entwurf"]["vorhanden"] is True
    assert ctx["tom_entwurf"]["anzahl_luecken"] == 1
    a = {x["id"]: x for x in ctx["tom_entwurf"]["abschnitte"]}
    assert a["TOM-A"]["luecken"] == ["Besucherregistrierung fehlt"]
    assert a["TOM-A"]["empfehlungen"] == ["Besucherbuch einführen"]
    assert a["TOM-B"]["hat_entwurf"] is False


def test_der_entwurf_bleibt_aus_toms_heraus(pg, projekt):
    """Eigene Wurzel, nicht in ``toms`` — sonst druckt jede bestehende Vorlage,
    die über ``toms`` iteriert, plötzlich Entwurfstext (#1540/#1771/#1805)."""
    from dsgvo.template_context import build_dsgvo_context

    ctx = build_dsgvo_context(bp.DB_PATH, projekt)
    assert ctx["toms"] == []
    assert ctx["meta"]["anzahl_toms"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# 2 · (a) Ohne template_id ist das Ergebnis unverändert
# ──────────────────────────────────────────────────────────────────────────────
def _mappings_wie_vor_2005(payload: dict) -> dict:
    """Die Inline-Fassung aus ``server/api/dsgvo.export_tom`` bis v8.6.x.

    Absichtlich abgeschrieben und nicht importiert: Der Test ist nur dann ein
    Regressionsschutz, wenn er den **alten** Stand mitbringt. Würde er die neue
    Funktion rufen, prüfte er sie gegen sich selbst.
    """
    abschnitte = payload.get("abschnitte") or {}
    approved: dict = {}
    for tom_id, content in abschnitte.items():
        items = []
        for m in (content.get("vorhandene_massnahmen") or []):
            items.append({"text": str(m), "doc_id": "ai", "doc_name": "KI-Entwurf"})
        for g in (content.get("luecken") or []):
            items.append({"text": f"⚠ Lücke: {g}", "doc_id": "ai", "doc_name": "KI-Entwurf"})
        for r in (content.get("empfehlungen") or []):
            items.append({"text": f"→ Empfehlung: {r}", "doc_id": "ai", "doc_name": "KI-Entwurf"})
        if items:
            approved[tom_id] = items
    return approved


def test_die_umgezogene_zuordnung_ist_wortgleich():
    assert dtom.entwurf_mappings(ENTWURF) == _mappings_wie_vor_2005(ENTWURF)
    # Ohne Entwurf gab es früher ``None``, jetzt ``{}`` — ``export_tom_docx``
    # macht daraus beides Mal ``{}``, also ändert sich das Dokument nicht.
    assert dtom.entwurf_mappings(None) == {}
    assert dtom.entwurf_mappings({"abschnitte": {"TOM-A": {}}}) == {}


def test_export_ohne_vorlage_ist_unveraendert(rest, projekt, tmp_path):
    """(a) Derselbe Entwurf wie vor #2005 — Absatz für Absatz."""
    from dsgvo.db import load_bewertungen, load_projekt

    client, headers = rest
    res = client.get(
        f"/api/dsgvo/projekte/{projekt}/tom/export", headers=headers)
    assert res.status_code == 200, res.get_data(as_text=True)

    p = load_projekt(bp.DB_PATH, projekt) or {}
    bestand = dtom.export_tom_docx(
        out_dir=tmp_path / "bestand",
        projekt_name=projekt,
        unternehmen=p.get("unternehmen", ""),
        berater=p.get("berater", ""),
        bewertungen=load_bewertungen(bp.DB_PATH, projekt),
        approved_mappings=_mappings_wie_vor_2005(ENTWURF),
    )
    zeilen = _absaetze(res.data)
    assert zeilen == _absaetze(Path(bestand).read_bytes())
    # Und es ist wirklich der Entwurf — sonst verglichen wir zwei leere Dateien.
    assert any("TOM-A – Zutrittskontrolle" in z for z in zeilen)
    assert any("ENTWURF" in z for z in zeilen)


# ──────────────────────────────────────────────────────────────────────────────
# 3 · (b) Mit Vorlage: deren Rahmen plus die Entwurfsdaten
# ──────────────────────────────────────────────────────────────────────────────
VORLAGE_ZEILEN = [
    "Hausrahmen Nordlicht — TOM-Entwurf",
    "Projekt: {{ projekt.name }}",
    "Entwurf vorhanden: {{ tom_entwurf.vorhanden }} · Lücken: {{ tom_entwurf.anzahl_luecken }}",
    "Fazit: {{ tom_entwurf.fazit }}",
    "{%p for a in tom_entwurf.abschnitte %}",
    "{{ a.id }} {{ a.titel }}: {{ a.vorhandene_massnahmen|join('; ') }}"
    " | Lücken: {{ a.luecken|join('; ') }}"
    " | Empfehlungen: {{ a.empfehlungen|join('; ') }}",
    "{%p endfor %}",
]


def test_vorlage_druckt_rahmen_und_entwurfsdaten(rest, projekt, upload):
    """(b) Die eigentliche Fehlanzeige: Es ließ sich keine Vorlage hinterlegen."""
    client, headers = rest
    body = upload(VORLAGE_ZEILEN, bericht_typ=dtom.ENTWURF_TYP)

    res = client.get(
        f"/api/dsgvo/projekte/{projekt}/tom/export?template_id={body['id']}",
        headers=headers)
    assert res.status_code == 200, res.get_data(as_text=True)
    zeilen = _absaetze(res.data)
    text = "\n".join(zeilen)

    # Der Rahmen der Vorlage …
    assert "Hausrahmen Nordlicht — TOM-Entwurf" in zeilen
    assert f"Projekt: {projekt}" in zeilen
    # … und die Entwurfsdaten, getrennt nach Maßnahmen, Lücken, Empfehlungen.
    assert "Chipkarten-Zutrittssystem im Serverraum" in text
    assert "Besucherregistrierung fehlt" in text
    assert "Besucherbuch einführen" in text
    assert "Zutritt und Zugriff sind überwiegend geregelt." in text
    assert "TOM-C Zugriffskontrolle" in text
    # Und es ist nicht der programmatische Entwurf — dessen Banner fehlt.
    assert not any("ENTWURF" in z and "Hausrahmen" not in z for z in zeilen)


def test_der_generator_waehlt_die_vorlage_serverseitig_vor(rest, projekt, upload):
    """Die Vorauswahl rechnet der Server; der Generator liest sie (#1703/S9)."""
    client, headers = rest
    body = upload(VORLAGE_ZEILEN, bericht_typ=dtom.ENTWURF_TYP)
    tdb.set_default(tdb.DEFAULT_DB_PATH, int(body["id"]))

    res = client.get(f"/api/dsgvo/projekte/{projekt}/berichte", headers=headers)
    assert res.status_code == 200, res.get_data(as_text=True)
    daten = res.get_json()
    karte = next(r for r in daten["reports"] if r["key"] == dtom.ENTWURF_TYP)
    assert karte["vorlage_id"] == body["id"]
    # Und sie steht in der Liste, aus der die Maske das Auswahlfeld füllt.
    assert body["id"] in [v["id"] for v in daten["vorlagen"]]


# ──────────────────────────────────────────────────────────────────────────────
# 4 · (c) Eine fremde Vorlage wird mit Klartext abgewiesen — und zwar gleich
# ──────────────────────────────────────────────────────────────────────────────
def test_vorlage_eines_anderen_berichts_wird_abgelehnt(pg, upload):
    body = upload(["{{ projekt.name }}"], bericht_typ="gesamt")
    with pytest.raises(bruecke.VorlageFehlt) as fehler:
        bruecke.pruefe("dsgvo", body["id"], typ=dtom.ENTWURF_TYP)
    # Klartext: welcher Bericht ist hinterlegt, welcher wurde angefordert.
    assert "gesamt" in str(fehler.value)
    assert dtom.ENTWURF_TYP in str(fehler.value)
    # Für ihren eigenen Bericht bleibt sie gültig.
    assert bruecke.pruefe("dsgvo", body["id"], typ="gesamt")


def test_generator_und_berichts_center_weisen_dieselbe_vorlage_gleich_ab(
        rest, projekt, upload):
    """(c) Eine Ursache, eine Antwort.

    Der Status ist bewusst der des Berichts-Centers (404 mit Klartext, so
    entschieden in ``test_export_mit_falscher_vorlage_antwortet_404_statt_500``,
    #1777) und nicht ein eigener. Geprüft wird hier, dass beide Endpunkte
    **nicht auseinanderlaufen** — und dass es in keinem Fall ein 500 ist, denn
    das war der Fehler von #1741.
    """
    client, headers = rest
    body = upload(["{{ projekt.name }}"], bericht_typ="gesamt")

    generator = client.get(
        f"/api/dsgvo/projekte/{projekt}/tom/export?template_id={body['id']}",
        headers=headers)
    zentrum = client.get(
        f"/api/dsgvo/projekte/{projekt}/berichte/{dtom.ENTWURF_TYP}"
        f"?format=docx&template_id={body['id']}", headers=headers)

    # Die Meldung nimmt die Bytes abgeschnitten: Wird die Vorlage fälschlich
    # **angenommen**, ist die Antwort ein DOCX, und ``as_text`` scheiterte dann
    # mit einem UnicodeDecodeError statt den Fund zu nennen.
    assert generator.status_code == zentrum.status_code, (
        generator.status_code, generator.get_data()[:200])
    assert generator.status_code < 500
    assert generator.get_json()["error"] == zentrum.get_json()["error"]
    assert "gesamt" in generator.get_json()["error"]


def test_vorlage_mit_fremden_variablen_antwortet_422(rest, projekt, monkeypatch):
    """Ein Vorlagenfehler ist kein Serverfehler (#1741) — auch am Generator.

    Hochladen würde die Prüfung aus #1741 schon abweisen; einen solchen
    Altbestand gibt es nur in Installationen, die älter als #1741 sind. Deshalb
    derselbe Zuschnitt wie dort: der Abbruch wird eingesetzt, geprüft wird die
    **Übersetzung** in eine Antwort (Muster
    ``test_berichts_center_antwortet_422_nicht_500``).
    """
    client, headers = rest
    from shared.reports import vorlagen as _v
    from shared.templates import engine

    fehler = engine.RenderFehler(
        "Die Vorlage passt nicht zum Modul DSGVO: wasserstand wird dort nicht "
        "geliefert (wasserstand gehört zu Compliance-Audit).",
        modul="dsgvo", unbekannt=[{"name": "wasserstand", "wurzel": "wasserstand",
                                   "bekannt_in": ["compliance_audit"],
                                   "bekannt_in_labels": ["Compliance-Audit"]}],
        zeile=1, urspruenglich="TypeError: …")

    monkeypatch.setattr(_v, "pruefe", lambda *a, **k: {"id": 1})
    monkeypatch.setattr(_v, "render_vorlage",
                        lambda *a, **k: (_ for _ in ()).throw(fehler))

    res = client.get(
        f"/api/dsgvo/projekte/{projekt}/tom/export?template_id=1",
        headers=headers)
    assert res.status_code == 422, res.get_data(as_text=True)
    body = res.get_json()
    assert "wasserstand" in body["error"]
    assert body["unbekannt"][0]["name"] == "wasserstand"


# ──────────────────────────────────────────────────────────────────────────────
# 5 · (d) Ein Renderer: Generator == Berichts-Center
# ──────────────────────────────────────────────────────────────────────────────
def test_generator_und_berichts_center_erzeugen_dasselbe_dokument(rest, projekt):
    """(d) Zwei Erzeugungswege für ein Dokument wären zwei Wahrheiten (#1727)."""
    client, headers = rest
    generator = client.get(
        f"/api/dsgvo/projekte/{projekt}/tom/export", headers=headers)
    assert generator.status_code == 200, generator.get_data(as_text=True)

    zentrum = bp.render(dtom.ENTWURF_TYP, "docx", projekt=projekt)
    zeilen = _absaetze(zentrum)
    assert _absaetze(generator.data) == zeilen
    # Nicht zwei leere Dateien: der Entwurf trägt alle zehn Abschnitte.
    assert sum(1 for z in zeilen if z.startswith("2.") and "TOM-" in z) == 10


def test_der_entwurf_laeuft_ueber_dieselbe_funktion_wie_der_knopf(pg, projekt,
                                                                 tmp_path):
    """Dieselbe Funktion, nicht nur dasselbe Ergebnis — sonst driftet es."""
    direkt = dtom.export_entwurf_docx(bp.DB_PATH, projekt, out_dir=tmp_path)
    assert _absaetze(Path(direkt).read_bytes()) == \
        _absaetze(bp.render(dtom.ENTWURF_TYP, "docx", projekt=projekt))


def test_jeder_katalog_typ_erzeugt_ein_eigenes_dokument(pg, projekt):
    """Der Entwurf ist nicht der Bereichsbericht ``tom`` (Stand gegen Entwurf)."""
    stand = _absaetze(bp.render("tom", "docx", projekt=projekt))
    entwurf = _absaetze(bp.render(dtom.ENTWURF_TYP, "docx", projekt=projekt))
    assert stand and entwurf
    assert stand[0] != entwurf[0], (stand[0], entwurf[0])


# ──────────────────────────────────────────────────────────────────────────────
# 6 · Die Beschriftung ist übersetzt (#1954)
# ──────────────────────────────────────────────────────────────────────────────
def test_die_beschriftung_steht_in_beiden_sprachen():
    """Sie war ein deutsches Literal im Template und blieb auf Englisch deutsch.

    Geprüft wird über ``vue_text``, also die **Oberfläche** mit aufgelösten
    Schlüsseln — nicht die Benennung des Schlüssels (tests/i18n_text.py).
    """
    from tests.i18n_text import vue_text

    pfad = "frontend/src/views/dsgvo/DSGVOView.vue"
    de = vue_text(pfad)
    en = vue_text(pfad, sprache="en")
    assert "TOM-Entwurf herunterladen (DOCX)" in de
    assert "Download TOM draft (DOCX)" in en
    # Kein hart kodiertes Literal mehr im Template.
    quelle = Path(pfad).read_text(encoding="utf-8")
    assert 'label="📝 TOM-Entwurf herunterladen (DOCX)"' not in quelle


def test_die_maske_meint_denselben_berichtstyp():
    """Der Schlüssel steht in der Maske noch einmal — also wird er geprüft.

    Die Maske muss wissen, **welche** Karte des Berichts-Centers ihre Vorlage
    trägt; das ist eine Zeichenkette in zwei Dateien, und eine Zuordnung über
    Zeichenketten, die anderswo entstehen, braucht einen Prüfer, der beide
    Seiten gegeneinander hält (die Lehre aus #1870).
    """
    quelle = Path("frontend/src/views/dsgvo/DSGVOView.vue").read_text(encoding="utf-8")
    assert f"const TOM_ENTWURF_TYP = '{dtom.ENTWURF_TYP}'" in quelle
