"""Eigene Befunde an der Fremdkomponente ausweisen (#1774).

Die Anwendung weiß zwei Dinge über dieselbe Abhängigkeit und bringt sie nicht
zusammen: In ``cra_sbom_komponenten`` steht die Komponente (#1761), in
``cra_vuln`` steht der Befund dazu — aus Dependabot, einem Advisory, einer
manuellen Erfassung oder einem **Pentest** (#1581). Wer nach Art. 13 Abs. 5
bewertet, sieht den Befund nicht; er müsste ihn im C3-Reiter nachsehen und sich
die Zuordnung selbst merken.

Die Verbindung gibt es schon — aber nur in **einer** Richtung:
``cra/upstream_meldung.fremdbezug`` findet zu einem Befund die Komponente, um
die Meldepflicht an deren Hersteller zu beurteilen (Art. 13 Abs. 6). Diese
Datei dreht dieselbe Zuordnung um, statt eine zweite zu erfinden: Eine zweite
Zuordnungslogik hieße zwei Wahrheiten über denselben Sachverhalt, und die
schlechtere wäre die, die irgendwann niemand mehr pflegt.

**Warum das für die Bewertung zählt.** „Diese Komponente berührt die
Sicherheitseigenschaften des Produkts nicht" ist eine zulässige Aussage — bis
ein offener Befund gegen genau diese Komponente vorliegt. Dann ist der Befund
selbst der Gegenbeweis. Dieser Widerspruch wird deshalb **gerechnet** und nicht
dem Auge des Prüfers überlassen (:func:`widersprueche`).

**Was hier bewusst nicht passiert.** Die Zuordnung bleibt **exakt**. Eine
Teilstring-Suche fände ``requests`` in ``requests-oauthlib`` und hängte den
Befund an die falsche Abhängigkeit — in einer Nachweisakte ist ein erfundener
Treffer schlimmer als ein fehlender. Pentest-Befunde tragen in
``affected_component`` meist das geprüfte **System** und kein Paket; sie werden
nur zugeordnet, wenn der Prüfer die Komponente benannt hat. Lieber kein Treffer
als ein ausgedachter.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from cra.upstream_meldung import fremdbezug, komponenten_index

DB_PATH = Path("data/db/cra.sqlite")

#: Status, in denen ein Befund **offen** ist — er steht also noch gegen das
#: Produkt. ``fixed``/``disclosed`` sind behandelt, ``wontfix`` ist eine
#: getroffene Entscheidung; beide widersprechen einer Bewertung nicht mehr.
OFFENE_STATUS = frozenset({"open", "triaging"})

#: Woher der Befund kommt — in der Sprache der Oberfläche. Der Unterschied ist
#: nicht Kosmetik: Ein Pentest-Befund ist ein **eigener** Fund (und löst damit
#: die Meldepflicht aus Art. 13 Abs. 6 aus), ein Dependabot-Befund nicht.
QUELLE_LABEL = {
    "manual": "manuell erfasst",
    "pentest": "Pentest",
    "github_advisory": "GitHub-Advisory",
    "github_dependabot": "Dependabot",
    "gitlab": "GitLab",
}

#: Schwere-Rangfolge für „der schwerste Befund dieser Komponente".
_RANG = {"critical": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}


def _offen(vuln: dict[str, Any]) -> bool:
    return str(vuln.get("status") or "open") in OFFENE_STATUS


def je_komponente(vulns: list[dict[str, Any]],
                  komponenten: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """``komponent_key`` → Befunde dieser Komponente (reine Funktion).

    Ein Befund ohne zuordenbare Komponente erscheint hier nicht. Das ist keine
    Nachlässigkeit, sondern dieselbe Regel wie in ``upstream_meldung``: Was in
    keiner SBOM steht, gilt als eigener Code, und dafür ist nicht die
    Sorgfaltspflicht bei Komponenten Dritter zuständig.
    """
    index = komponenten_index(komponenten)
    out: dict[str, list[dict[str, Any]]] = {}
    if not index:
        return out
    for v in vulns or []:
        key = fremdbezug(v, index)
        if not key:
            continue
        schwere = str(v.get("schwere") or "unknown").lower()
        out.setdefault(key, []).append({
            "id": v.get("id"),
            "cve_id": str(v.get("cve_id") or ""),
            "titel": str(v.get("titel") or ""),
            "schwere": schwere,
            "cvss_score": float(v.get("cvss_score") or 0.0),
            "status": str(v.get("status") or "open"),
            "offen": _offen(v),
            "quelle": str(v.get("source") or "manual"),
            "quelle_label": QUELLE_LABEL.get(str(v.get("source") or "manual"),
                                             str(v.get("source") or "manual")),
            "fixed_in_version": str(v.get("fixed_in_version") or ""),
        })
    for key in out:
        out[key].sort(key=lambda b: (-_RANG.get(b["schwere"], 0),
                                     not b["offen"], b["cve_id"]))
    return out


def fuer_projekt(db_path: Path, projekt_name: str,
                 komponenten: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """:func:`je_komponente` mit den Befunden des Projekts aus der Datenbank.

    Best effort: Fällt die Schwachstellen-Tabelle aus, bleibt die Zuordnung
    leer. Sie ist eine **Zusatzinformation** an der Bewertung; sie darf die
    Komponentenliste nicht mitnehmen.
    """
    try:
        from cra.db import list_vuln

        return je_komponente(list_vuln(db_path, projekt_name), komponenten)
    except Exception:  # noqa: BLE001
        return {}


def anreichern(komponenten: list[dict[str, Any]],
               befunde: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Komponentenzeilen um ihre Befunde ergänzen — additiv, ohne Umbau.

    Die Zeilen bekommen ``befunde`` (Liste), ``befunde_offen`` (Anzahl) und
    ``befund_schwere`` (die schwerste **offene** Schwere). Vorhandene Felder
    bleiben unberührt, damit Panel und Bericht unverändert lesen.
    """
    out: list[dict[str, Any]] = []
    for k in komponenten or []:
        zeile = dict(k)
        liste = befunde.get(str(k.get("komponent_key") or "")) or []
        offen = [b for b in liste if b.get("offen")]
        zeile["befunde"] = liste
        zeile["befunde_offen"] = len(offen)
        zeile["befund_schwere"] = max(
            (b["schwere"] for b in offen),
            key=lambda s: _RANG.get(s, 0), default="")
        out.append(zeile)
    return out


def hat_offenen_befund(komponente: dict[str, Any],
                       befunde: dict[str, list[dict[str, Any]]]) -> bool:
    """Steht gegen diese Komponente ein offener Befund?

    Das ist die Frage, die eine Komponente aus jeder Sammelbegründung
    heraushält (#1773): Sie ist nicht mehr einer von hundert gleichartigen
    Fällen, sondern ein eigener Sachverhalt.
    """
    key = str(komponente.get("komponent_key") or "")
    return any(b.get("offen") for b in (befunde.get(key) or []))


def widersprueche(komponenten: list[dict[str, Any]],
                  befunde: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Bewertungen, die dem eigenen Befund widersprechen (reine Funktion).

    Gemeint ist **ein** Fall, und zwar der eindeutige: ``nicht_relevant`` heißt
    „diese Komponente berührt die Sicherheitseigenschaften des Produkts nicht"
    (siehe ``sbom_komponenten.BEWERTUNG_STATUS``). Liegt gegen sie ein offener
    Befund vor, ist das Gegenteil belegt — durch die eigene Akte.

    **Warum nicht auch ``geprueft``?** Weil ein offener Befund an einer
    geprüften Komponente kein Widerspruch ist, sondern der normale Lauf der
    Dinge: Die Komponente ist angesehen, der Befund ist erfasst und wird in C3
    behandelt (``cra_vuln``, Art. 13 Abs. 8). Das als Mangel zu melden hieße,
    jede ordentlich geführte Akte rot zu färben — und ein Prüfpunkt, der bei
    richtigem Verhalten anschlägt, wird abgeschaltet.
    """
    out: list[dict[str, Any]] = []
    for k in komponenten or []:
        if str(k.get("bewertung_status") or "offen") != "nicht_relevant":
            continue
        offen = [b for b in (befunde.get(str(k.get("komponent_key") or "")) or [])
                 if b.get("offen")]
        if not offen:
            continue
        out.append({
            "id": k.get("id"),
            "komponent_key": str(k.get("komponent_key") or ""),
            "name": str(k.get("name") or ""),
            "version": str(k.get("version") or ""),
            "befunde": [b.get("cve_id") or b.get("titel") or "" for b in offen],
            "schwere": max((b["schwere"] for b in offen),
                           key=lambda s: _RANG.get(s, 0), default=""),
        })
    return out


def befund_fuer_release(db_path: Path, projekt_name: str,
                        version: str) -> dict[str, Any]:
    """Gerechneter Befund für das Release-Gate.

    Gezählt wird über **alle Artefakte** der Version (#1771) — ein Produkt aus
    Anwendung und Webserver hat zwei Komponentenlisten, und ein Widerspruch in
    der zweiten ist genauso einer.

    Rückgabe ``{'widersprueche': [...], 'komponenten_mit_befund': n,
    'ohne_komponentenliste': bool}``. ``ohne_komponentenliste`` trennt „nichts
    zu beanstanden" von „nicht prüfbar" — die Unterscheidung, die dieses Projekt
    an mehreren Stellen teuer gelernt hat.
    """
    from cra.db import list_sbom
    from cra.sbom_komponenten import _norm_version, list_komponenten

    ziel = _norm_version(version)
    sboms = [s for s in list_sbom(db_path, projekt_name)
             if _norm_version(s.get("release_version")) == ziel]
    alle: list[dict[str, Any]] = []
    for s in sboms:
        alle.extend(list_komponenten(db_path, projekt_name, int(s.get("id") or 0)))
    if not alle:
        return {"widersprueche": [], "komponenten_mit_befund": 0,
                "ohne_komponentenliste": True}
    bef = fuer_projekt(db_path, projekt_name, alle)
    mit_offenem = sum(1 for k in alle if hat_offenen_befund(k, bef))
    return {"widersprueche": widersprueche(alle, bef),
            "komponenten_mit_befund": mit_offenem,
            "ohne_komponentenliste": False}


__all__ = ["OFFENE_STATUS", "QUELLE_LABEL", "je_komponente", "fuer_projekt",
           "anreichern", "hat_offenen_befund", "widersprueche",
           "befund_fuer_release"]
