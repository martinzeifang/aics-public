"""Der Status-Abgleich wirkt immer — beide Provider, Kommentare, Marker (#1850).

Der Abgleich hat zwei Aufgaben: den Status nachholen (es gibt **keinen
Webhook**) und daraus die Neubewertungspflicht ableiten. Die zweite erfüllte
er an drei von sieben Wegen nicht, fünf von sieben übersprangen GitLab
stillschweigend, und neue Kommentare erkannte er gar nicht.

Geprüft wird hier der **Kern** (`shared/issue_abgleich`) — ohne Netz, ohne
Flask: Die Provider-Aufrufe werden ersetzt, damit die Entscheidungen prüfbar
sind und nicht die Erreichbarkeit von GitHub.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from shared import issue_abgleich as ia
from shared.issue_sync import SyncedIssue


def _link(**kw):
    """Ein Link, wie ihn `list_links` liefert (als dict — der Kern liest beides)."""
    basis = dict(id="L1", projekt_name="P", object_kind="requirement",
                 object_id="R-1", provider="github", repo="o/r",
                 issue_number=7, issue_iid=None, url="https://github.com/o/r/issues/7",
                 title="T", state="open", state_reason="", comments=2,
                 remote_updated_at="2026-10-01T00:00:00Z")
    basis.update(kw)
    return basis


def _antwort(**kw) -> SyncedIssue:
    basis = dict(provider="github", repo="o/r", number=7, iid=None,
                 url="https://github.com/o/r/issues/7", title="T",
                 state="open", state_reason="", labels=[], comments=2,
                 updated_at="2026-10-01T00:00:00Z")
    basis.update(kw)
    return SyncedIssue(**basis)


@pytest.fixture()
def db(tmp_path) -> Path:
    from shared.issue_links import ensure_tables
    p = tmp_path / "links.sqlite"
    ensure_tables(p)
    return p


@pytest.fixture()
def gh(monkeypatch):
    """GitHub-Abruf ersetzen; gibt die Liste der gelieferten Antworten zurück."""
    antworten: list[SyncedIssue] = []

    def _fake(*, repo, number):
        return antworten.pop(0)

    monkeypatch.setattr(ia, "__name__", ia.__name__)  # no-op, hält den Import wach
    import shared.issue_sync as sync
    monkeypatch.setattr(sync, "sync_github_issue", _fake)
    return antworten


# ── Der Anlass wird erkannt ────────────────────────────────────────────────

def test_geschlossenes_issue_loest_neubewertung_aus(db, gh):
    gh.append(_antwort(state="closed"))
    erg = ia.abgleiche_links(db, [_link(state="open")])
    assert erg.neubewertung_noetig
    assert ia.ANLASS_GESCHLOSSEN in erg.anlaesse


def test_geschlossen_ist_ein_zustand_kein_wechsel(db, gh):
    """Vorgabe: „Ist das Issue geschlossen" — **immer** markieren.

    Auf den Übergang zu prüfen wäre schwächer: Wer den vorherigen Stand nie
    erhoben hat (frische Installation, eingespielte Sicherung, von Hand
    angelegter Link), erfährt sonst nie, dass das Ticket längst zu ist.
    """
    gh.append(_antwort(state="closed"))
    erg = ia.abgleiche_links(db, [_link(state="closed")])   # vorher schon zu
    assert ia.ANLASS_GESCHLOSSEN in erg.anlaesse

    gh.append(_antwort(state="closed"))
    erg = ia.abgleiche_links(db, [_link(state="")])         # Stand unbekannt
    assert ia.ANLASS_GESCHLOSSEN in erg.anlaesse


def test_wieder_geoeffnetes_issue_ebenso(db, gh):
    """Ein wieder geöffnetes Ticket heißt: Die Sache ist doch nicht erledigt."""
    gh.append(_antwort(state="open"))
    erg = ia.abgleiche_links(db, [_link(state="closed")])
    assert ia.ANLASS_GEOEFFNET in erg.anlaesse


def test_neue_kommentare_loesen_neubewertung_aus(db, gh):
    """Der Fall, den die Suite vorher gar nicht sehen konnte."""
    gh.append(_antwort(comments=5))
    erg = ia.abgleiche_links(db, [_link(comments=2)])
    assert erg.neubewertung_noetig
    assert "3 neue Kommentare" in erg.anlaesse


def test_ein_einzelner_kommentar_wird_richtig_gebeugt(db, gh):
    gh.append(_antwort(comments=3))
    erg = ia.abgleiche_links(db, [_link(comments=2)])
    assert "1 neuer Kommentar" in erg.anlaesse


def test_ohne_aenderung_keine_neubewertung(db, gh):
    gh.append(_antwort())
    erg = ia.abgleiche_links(db, [_link()])
    assert not erg.neubewertung_noetig
    assert erg.synced == 1


def test_geloeschte_kommentare_loesen_nichts_aus(db, gh):
    """Weniger Kommentare sind kein Anlass — da wurde nichts hinzugefügt."""
    gh.append(_antwort(comments=1))
    erg = ia.abgleiche_links(db, [_link(comments=4)])
    assert not erg.neubewertung_noetig


def test_erstabgleich_lernt_nur(db, gh):
    """Sonst meldete der erste Abgleich nach dem Update alles auf einmal.

    Eine Markierung, die alle trifft, trifft niemanden.
    """
    gh.append(_antwort(comments=9))
    erg = ia.abgleiche_links(db, [_link(comments=None)])
    assert not erg.neubewertung_noetig
    assert erg.links[0].erstabgleich
    assert erg.links[0].comments == 9


# ── Beide Provider, und Fehler sind nie stumm ──────────────────────────────

def test_gitlab_wird_abgeglichen(db, monkeypatch):
    """Fünf von sieben Wegen übersprangen GitLab stillschweigend."""
    import shared.issue_sync as sync
    gerufen = {}

    def _fake_gl(*, base_url, token_env, project, iid):
        gerufen.update(project=project, iid=iid)
        return _antwort(provider="gitlab", state="closed", comments=2)

    monkeypatch.setattr(sync, "sync_gitlab_issue", _fake_gl)
    erg = ia.abgleiche_links(db, [_link(
        provider="gitlab", issue_number=None, issue_iid=3,
        url="https://gitlab.com/gruppe/projekt/-/issues/3", state="open")])
    assert gerufen["iid"] == 3
    assert erg.synced == 1
    assert ia.ANLASS_GESCHLOSSEN in erg.anlaesse


def test_unbekannter_provider_erzeugt_einen_benannten_fehler(db):
    """Vorher: `synced: 0`, keine Meldung — der Anwender sah „abgeglichen"."""
    erg = ia.abgleiche_links(db, [_link(provider="bitbucket",
                                        url="https://example.invalid/x/1")])
    assert erg.synced == 0 and erg.fehler == 1
    assert not erg.links[0].ok
    assert "Provider" in erg.links[0].fehler


def test_ein_fehler_stoppt_die_uebrigen_nicht(db, gh):
    gh.append(_antwort(state="closed"))
    erg = ia.abgleiche_links(db, [
        _link(id="kaputt", provider="bitbucket", url="https://example.invalid/x/1"),
        _link(id="gut", state="open"),
    ])
    assert erg.synced == 1 and erg.fehler == 1


# ── Der Marker ─────────────────────────────────────────────────────────────

def test_der_marker_nennt_den_anlass():
    """„verknüpftes Issue geändert" sagte nicht, ob man hinsehen muss."""
    text = ia.marker_text([ia.ANLASS_GESCHLOSSEN])
    assert text.startswith(ia.MARKER)
    assert "geschlossen" in text


def test_mehrere_anlaesse_stehen_zusammen():
    text = ia.marker_text([ia.ANLASS_GESCHLOSSEN, "2 neue Kommentare"])
    assert "geschlossen" in text and "2 neue Kommentare" in text


def test_marker_wird_vorangestellt_und_text_bleibt():
    neu, geaendert = ia.setze_marker("Bestehende Bewertung.", [ia.ANLASS_GESCHLOSSEN])
    assert geaendert
    assert neu.startswith(ia.MARKER)
    assert "Bestehende Bewertung." in neu


def test_zweiter_abgleich_haengt_keinen_zweiten_marker_an():
    """Sonst wüchse der Kommentar bei jedem Knopfdruck."""
    einmal, _ = ia.setze_marker("Text.", [ia.ANLASS_GESCHLOSSEN])
    zweimal, geaendert = ia.setze_marker(einmal, [ia.ANLASS_GESCHLOSSEN])
    assert zweimal.count(ia.MARKER) == 1
    assert not geaendert


def test_ein_neuer_anlass_ersetzt_den_alten_marker():
    """Zwei Markierungen untereinander sagen nicht mehr als eine."""
    alt, _ = ia.setze_marker("Text.", [ia.ANLASS_GESCHLOSSEN])
    neu, geaendert = ia.setze_marker(alt, ["2 neue Kommentare"])
    assert geaendert
    assert neu.count(ia.MARKER) == 1
    assert "2 neue Kommentare" in neu
    assert "geschlossen" not in neu
    assert "Text." in neu


def test_ohne_anlass_bleibt_der_text_unberuehrt():
    neu, geaendert = ia.setze_marker("Text.", [])
    assert neu == "Text." and not geaendert


def test_marker_ist_erkennbar():
    neu, _ = ia.setze_marker("", [ia.ANLASS_GESCHLOSSEN])
    assert ia.hat_marker(neu)
    assert not ia.hat_marker("Normale Bewertung.")


def test_der_marker_bleibt_zum_bestand_kompatibel():
    """Bestandstexte tragen den alten Wortlaut; die Oberfläche filtert darauf."""
    from shared.issue_completion import NEEDS_REASSESS_MARKER
    assert NEEDS_REASSESS_MARKER.startswith(ia.MARKER)


# ── Abgleich und Markierung in einem Schritt ───────────────────────────────

def test_abgleiche_und_markiere_schreibt_nur_bei_anlass(db, gh, monkeypatch):
    from shared.issue_links import add_link
    add_link(db, projekt_name="P", object_kind="requirement", object_id="R-1",
             provider="github", repo="o/r", url="https://github.com/o/r/issues/7",
             issue_number=7, title="T", state="open", comments=2)

    # Der Text muss zwischen den Läufen **wirklich** fortgeschrieben werden —
    # ein konstantes `lies_text` würde die Idempotenz nur vortäuschen.
    ablage = {"text": "Bewertung."}
    geschrieben: list[str] = []

    def _schreib(t: str) -> None:
        ablage["text"] = t
        geschrieben.append(t)

    gh.append(_antwort(state="closed"))
    ia.abgleiche_und_markiere(
        db, projekt_name="P", object_kind="requirement", object_id="R-1",
        lies_text=lambda: ablage["text"], schreib_text=_schreib)
    assert geschrieben and ia.hat_marker(geschrieben[0])
    assert "Bewertung." in ablage["text"]

    geschrieben.clear()
    gh.append(_antwort(state="closed"))   # unverändert geschlossen
    ia.abgleiche_und_markiere(
        db, projekt_name="P", object_kind="requirement", object_id="R-1",
        lies_text=lambda: ablage["text"], schreib_text=_schreib)
    assert not geschrieben, ("Ein zweiter Abgleich ohne Änderung darf nichts "
                             "schreiben — sonst wüchse der Kommentar bei jedem "
                             "Knopfdruck.")


def test_unbewertetes_objekt_bekommt_keinen_marker(db, gh):
    """`bewertet=False` schreibt nicht — meldet den Anlass aber trotzdem.

    Die Regel stammt aus #1508: Ein nie bewertetes Objekt kann nicht „neu"
    bewertet werden und steht ohnehin als offen in der Liste. Festgestellt
    ist die Sache trotzdem — deshalb bleibt `neubewertung` wahr und nur
    `markiert` falsch. Ein Zähler, der beides vermischt, meldet Markierungen,
    die es nicht gibt.
    """
    from shared.issue_links import add_link
    add_link(db, projekt_name="P", object_kind="requirement", object_id="R-1",
             provider="github", repo="o/r", url="https://github.com/o/r/issues/7",
             issue_number=7, title="T", state="open", comments=2)
    geschrieben: list[str] = []
    gh.append(_antwort(state="closed"))
    erg = ia.abgleiche_und_markiere(
        db, projekt_name="P", object_kind="requirement", object_id="R-1",
        lies_text=lambda: "", schreib_text=geschrieben.append, bewertet=False)
    assert erg.neubewertung_noetig and not erg.markiert
    assert not geschrieben


def test_der_marker_nennt_das_issue(db, gh):
    gh.append(_antwort(state="closed", number=7))
    erg = ia.abgleiche_links(db, [_link(state="open", issue_number=7)])
    assert erg.referenzen == ["#7"]
    assert "#7" in ia.marker_text(erg.anlaesse, erg.referenzen)


# ── Die Markierung ist auch in der Oberfläche eine Stelle ───────────────────

FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "src"
QUELLE = FRONTEND / "utils" / "neubewertung.ts"


def test_frontend_und_backend_meinen_dieselbe_zeichenkette():
    """Sonst sucht die Oberfläche nach einem Text, den niemand schreibt."""
    text = QUELLE.read_text(encoding="utf-8")
    assert "export const NEUBEWERTUNG_MARKER = 'Neubewertung erforderlich'" in text
    assert ia.MARKER.endswith("Neubewertung erforderlich"), (
        "Der Backend-Marker hat sich geändert — `utils/neubewertung.ts` muss "
        "mitgehen, sonst zeigt die Oberfläche die Markierung einfach nicht "
        "mehr an, ohne Fehler.")


def test_die_zeichenkette_steht_nur_an_einer_stelle():
    """Fünf Kopien waren fünf Gelegenheiten, eine zu vergessen (#1731/#1735).

    Erlaubt bleiben Fließtext-Vorkommen (Hilfeseiten, Erklärtexte, Tooltips):
    Dort ist es Prosa für den Leser, kein Vergleich im Code. Verboten ist das
    **Literal im Vergleich** — `includes('Neubewertung erforderlich')`.
    """
    treffer = []
    for datei in list(FRONTEND.rglob("*.ts")) + list(FRONTEND.rglob("*.vue")):
        if datei == QUELLE:
            continue
        for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if "includes('Neubewertung erforderlich')" in zeile.replace('"', "'"):
                treffer.append(f"{datei.relative_to(FRONTEND)}:{nr}")
    assert not treffer, (
        "Eigene Markererkennung statt `hatNeubewertung` aus "
        "`utils/neubewertung`:\n  " + "\n  ".join(treffer))


def test_die_markierung_steht_in_den_listen():
    """Im Editor sieht sie nur, wer das Objekt schon aufgeschlagen hat.

    Gesucht wird sie in der Liste: „Was hat sich getan, seit ich zuletzt
    hingesehen habe?" Deshalb muss der Badge dort stehen — in allen sechs
    Modulen.
    """
    erwartet = [
        "views/cra/CRAView.vue",                          # Anforderungen + OWASP
        "views/cra/PflichtDokuPanel.vue",                 # Risiken + Schwachstellen
        "views/nis2/NIS2View.vue",
        "views/aiact/AIActView.vue",
        "views/aiact/OwaspLlmPanel.vue",
        "views/dsgvo/DSGVOView.vue",
        "views/wiba/PrueffragenPanel.vue",
        "views/risikobewertung/RisikobewertungView.vue",
    ]
    for rel in erwartet:
        text = (FRONTEND / rel).read_text(encoding="utf-8")
        assert "<NeubewertungBadge" in text, f"{rel}: Badge fehlt in der Liste"
        assert "components/shared/NeubewertungBadge.vue" in text, \
            f"{rel}: Badge verwendet, aber nicht importiert — Vue löst den "\
            f"Bezeichner still zu undefined auf (#1830)"
