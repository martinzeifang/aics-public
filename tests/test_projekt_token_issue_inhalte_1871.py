"""#1871: Issue-Inhalte werden mit dem Token DES PROJEKTS geholt.

Der projektgebundene, verschlüsselte Token (#862) wirkte nur beim **Anlegen**
von Issues — `token_umgebung` hatte im ganzen Baum genau einen Aufrufer. Alle
lesenden Wege (Übernahme einzeln, Übernahme projektweit, Status-Abgleich,
Neubewertung mit Issue-Feedback) fielen auf `GH_TOKEN` aus dem Prozess-Umfeld
zurück. Ein globaler Token ist genau **ein** Zugang; eine Installation mit
Mandanten in verschiedenen GitHub-Organisationen kann ihn nicht setzen.

WARUM VERHALTENSTESTS UND KEIN QUELLTEXT-GREP
Ein Wächter, der `"token_umgebung" in getsource(...)` prüft, bleibt grün, wenn
die Zeile durch `pass` ersetzt wird — das Wort steht noch im Kommentar darüber
(die Lehre aus #1834, dort zweimal erlebt). Hier wird deshalb der Abruf
abgefangen und festgehalten, **welcher Token im Umfeld ankam**.
"""
from __future__ import annotations

import os

import pytest

from shared import issue_feedback as fb


class _Link:
    """Minimale Verknüpfung, wie sie `list_links` liefert."""

    def __init__(self, url: str, provider: str = "github") -> None:
        self.url = url
        self.provider = provider


@pytest.fixture()
def gesehener_token(monkeypatch):
    """Fängt den Abruf ab und merkt sich GH_TOKEN zum Zeitpunkt des Aufrufs."""
    gesehen: dict[str, str | None] = {}

    def _fake(url, **_kw):
        gesehen["GH_TOKEN"] = os.environ.get("GH_TOKEN")
        gesehen["GITHUB_TOKEN"] = os.environ.get("GITHUB_TOKEN")
        return {"combined": f"Inhalt zu {url}"}

    monkeypatch.setattr(fb, "fetch_issue_content_by_url", _fake)
    # Verdichtung aus: sie würde einen KI-Lauf anstoßen.
    monkeypatch.setattr(fb, "condense_feedback", lambda t: t)
    return gesehen


def _vcs_mit_token(token: str) -> dict:
    """vcs_publish-Konfiguration mit verschlüsseltem Token, wie gespeichert."""
    from shared.vcs_repo_config import sanitize_vcs
    return sanitize_vcs({"provider": "github", "repo": "kunde/repo",
                         "token": token})


def test_projekt_token_schlaegt_globalen(gesehener_token, monkeypatch):
    """Der Kern: Liegt ein Projekt-Token an, wird NICHT der globale genutzt."""
    monkeypatch.setenv("GH_TOKEN", "GLOBALER-TOKEN")
    vcs = _vcs_mit_token("PROJEKT-TOKEN")

    text, quellen = fb.collect_issue_feedback(
        [_Link("https://github.com/kunde/repo/issues/7")], vcs=vcs)

    assert quellen and quellen[0]["ok"], quellen
    assert text
    assert gesehener_token["GH_TOKEN"] == "PROJEKT-TOKEN", (
        "Der Abruf lief mit dem globalen Token statt mit dem des Projekts — "
        "genau der Defekt aus #1871.")
    assert gesehener_token["GITHUB_TOKEN"] == "PROJEKT-TOKEN"


def test_umgebung_wird_danach_wiederhergestellt(gesehener_token, monkeypatch):
    """Der Projekt-Token darf nicht im Prozess zurückbleiben.

    Sonst benutzte der nächste Mandant im selben Worker den Token des
    vorherigen — in einer mandantenfähigen Installation die schlimmere Hälfte
    des Fehlers.
    """
    monkeypatch.setenv("GH_TOKEN", "GLOBALER-TOKEN")
    fb.collect_issue_feedback([_Link("https://github.com/kunde/repo/issues/7")],
                              vcs=_vcs_mit_token("PROJEKT-TOKEN"))
    assert os.environ.get("GH_TOKEN") == "GLOBALER-TOKEN"


def test_ohne_projekt_token_bleibt_der_globale(gesehener_token, monkeypatch):
    """Rückfall: Ohne hinterlegten Token zählt weiter die Umgebung.

    Bestandsinstallationen mit genau einem GitHub-Konto sollen sich nicht
    ändern — das ist dieselbe Zusage wie bei `evidence_section` (#1483) und
    `prompt_zusatz` (#1832): ohne Zutat byte-identisches Verhalten.
    """
    monkeypatch.setenv("GH_TOKEN", "GLOBALER-TOKEN")
    fb.collect_issue_feedback([_Link("https://github.com/kunde/repo/issues/7")])
    assert gesehener_token["GH_TOKEN"] == "GLOBALER-TOKEN"


def test_provider_wird_je_verknuepfung_bestimmt():
    """Ein Projekt darf Verknüpfungen zu beiden Anbietern tragen."""
    assert fb._provider_von(_Link("x", "gitlab"), "x") == "gitlab"
    assert fb._provider_von(_Link("x", ""), "https://gitlab.com/a/b/issues/1") == "gitlab"
    assert fb._provider_von(_Link("x", ""), "https://github.com/a/b/issues/1") == "github"
    # Dict-Form, wie sie manche Aufrufer liefern
    assert fb._provider_von({"provider": "gitlab"}, "x") == "gitlab"


def test_collect_object_feedback_loest_selbst_auf(monkeypatch):
    """Die sechs Modul-Aufrufer brauchen keine Änderung.

    `collect_object_feedback` kennt Modul und Projektname und holt sich die
    Konfiguration selbst. Den Token an jeder Aufrufstelle durchzureichen wäre
    die Spiegel-Liste aus #1731/#1735.
    """
    gerufen: dict = {}

    monkeypatch.setattr(fb, "collect_issue_feedback",
                        lambda links, **kw: (gerufen.update(kw) or ("T", [])))
    monkeypatch.setattr("shared.issue_links.ensure_tables", lambda *a, **k: None)
    monkeypatch.setattr("shared.issue_links.list_links",
                        lambda *a, **k: [_Link("https://github.com/a/b/issues/1")])
    monkeypatch.setattr("shared.vcs_repo_config.vcs_fuer_projekt",
                        lambda db, p: {"provider": "github", "token_enc": "X"})

    fb.collect_object_feedback("cra.sqlite", "Projekt", "requirement", "R-1")
    assert gerufen.get("vcs") == {"provider": "github", "token_enc": "X"}, (
        "collect_object_feedback hat die Projekt-Konfiguration nicht aufgelöst")


def test_resolver_ist_fail_open():
    """Unbekanntes Modul oder leerer Projektname → {} statt Ausnahme.

    Dieselbe Entscheidung wie bei `projekt_firmen_id`: Ist nichts bestimmbar,
    bleibt der Aufrufer beim bisherigen Verhalten statt abzubrechen.
    """
    from shared.vcs_repo_config import vcs_fuer_projekt
    assert vcs_fuer_projekt("gibtsnicht.sqlite", "Projekt") == {}
    assert vcs_fuer_projekt("cra.sqlite", "") == {}
