"""Eine Fabrik für alle Issue-Routen (#1846).

Die Issue-Verknüpfung stand als ~76 Einzelrouten in sechs Modulen, deren
Handler dieselben sieben Schritte ausführen: Projekt laden → Objekt laden →
Repo auflösen → Titel/Body vorbelegen → Issue erzeugen →
``issue_links.add_link`` → Audit. Fachlich eigen ist davon **ein** Schritt.

Die Erhebung vor dem Umbau hat drei Dinge gezeigt, die mehr als Dopplung sind:

1. **Der GitLab-Weg kann nie funktioniert haben.**
   ``vcs.gitlab_issues.create_issue`` verlangt ``description=``; CRA (6
   Stellen), NIS2 (2) und AI Act (3) rufen mit ``body=``, WiBA zusätzlich mit
   ``repo=`` statt ``project=`` und **ohne** ``base_url``/``token_env``. Das
   ergibt ``TypeError`` → 500. Nur DSGVO ruft korrekt.
2. **Der projektgebundene Token kam nirgends außer CRA und WiBA an.** NIS2,
   AI Act und DSGVO legen ihn nicht in die Umgebung; ``gh_create`` liest dann
   nur ``GH_TOKEN``/``GITHUB_TOKEN``.
3. **Acht Fähigkeitslücken**, die niemand entschieden hat — darunter zwei
   sichtbare Knöpfe ohne Route (DSGVO-Sync, DSGVO-Entknüpfen).

WAS DIE FABRIK **NICHT** ÜBERNIMMT
Das Zurückschreiben. Fünf Module haben fünf unvereinbare Verträge
(``save_bewertung`` positional mit acht Parametern · keyword-only ohne
``verantwortlich``/``zieldatum`` · ``upsert_owasp_check`` mit
Teil-Update-Falle · ``save_antwort`` mit String-Status ·
``save_risiko(db, risk_dict)`` mit dem ganzen Objekt). Zusammen mit der
Teil-Update-Falle aus #1805/#1771/#1540 heißt das: Schreiben bleibt im
Adapter. Eine Fabrik, die es übernähme, würde Felder leeren, die sie nicht
kennt.

ANTWORTFORMEN
Die Fabrik liefert bewusst eine **Obermenge** der heutigen Schlüssel. Drei
Frontend-Stellen hängen an Schlüsseln, die nur ein Modul liefert
(``created``/``linked`` als Tor, ``resolved`` in der CRA-Pflicht-Doku,
``ok`` + ``bewertung_text`` im Risiko-Editor) und würden **stumm** brechen —
ein Feld wird ``undefined``, der ``if``-Block fällt aus, keine Meldung. Die
Obermenge kostet ein paar Bytes und spart diese Fehlerklasse.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator


# ── Beschreibung einer Objektart ────────────────────────────────────────────

@dataclass(frozen=True)
class ObjektArt:
    """Was die Fabrik über eine Objektart wissen muss.

    ``pfad`` und ``art`` sind **getrennt** anzugeben: Das AI-Act-Register
    heißt im URL-Segment ``owasp-llm`` (Bindestrich) und als ``object_kind``
    ``owasp_llm`` (Unterstrich). Eine Fabrik, die das eine aus dem anderen
    ableitet, bricht genau dort.
    """

    #: ``object_kind`` in ``linked_issues``.
    art: str
    #: URL-Segment, z. B. ``anforderungen`` · ``owasp-llm`` · ``controls``.
    pfad: str
    #: Flask-Parameter inklusive Konverter, z. B. ``<req_id>``, ``<int:risk_id>``.
    param: str
    #: Datenbank, in der die Verknüpfungen dieses Moduls liegen.
    db_path: Path
    #: ``(projekt_name, objekt_id) -> dict | None``. ``None`` ergibt 404.
    lade: Callable[[str, Any], dict | None]
    #: ``(objekt_id, objekt, stand) -> (titel, body)`` — der fachliche Teil.
    inhalt: Callable[[Any, dict, dict], tuple[str, str]]
    #: Freitext des Objekts lesen — für den Neubewertungs-Marker (#1850).
    lies_text: Callable[[str, Any], str]
    #: Freitext zurückschreiben. **Muss** ein Teil-Update sein (#1805).
    schreib_text: Callable[[str, Any, str], None]
    #: Aktueller Stand (Score/Antwort/Risikowert) für den Issue-Body.
    stand: Callable[[str, Any], dict] | None = None
    #: Menschenlesbarer Name für Fehlermeldungen („Anforderung", „Prüffrage").
    bezeichnung: str = "Objekt"
    #: Muss das Objekt im Katalog existieren?
    #:
    #: ``True`` für alle Objektarten mit eingebautem oder eigenem Katalog.
    #: ``False`` für WiBA: Der BSI-Katalog wird **zur Laufzeit** geladen und
    #: ist nicht eingecheckt (Copyright BSI). Auf einer Installation ohne
    #: geladenen Katalog liefert `list_prueffragen` nichts — ein 404 nähme
    #: dem Anwender dann den Zugriff auf seine **eigenen** Antworten. Genau
    #: dieses Fehlerbild war #1817. Der Bestand prüfte dort nie, und das war
    #: richtig.
    pflicht_objekt: bool = True
    # ── Alt-URLs, die weiter auflösen müssen ──────────────────────────────
    # Drei Bestandsrouten sind unregelmäßig. Sie bleiben als Alias, damit
    # dieser Umbau **allein** auslieferbar und allein zurücknehmbar ist; ein
    # Umbau, der nur zusammen mit dem Frontend läuft, lässt sich auch nur
    # zusammen zurücknehmen. Die Aliasse entfallen, wenn kein Aufrufer mehr
    # auf sie zeigt — nachweisbar über das Routen-Inventar.

    #: ``DELETE …/<pfad>/issues/<link_id>`` **ohne** Objekt-ID im Pfad.
    #: Betrifft ``cra/vulns`` und ``aiact/owasp-llm``.
    alias_entknuepfen_ohne_id: bool = False
    #: Hat dieses Objekt schon eine Bewertung? Wenn ja, bekommt es den
    #: Neubewertungs-Marker; ``None`` heißt „immer markieren". Siehe
    #: `abgleiche_und_markiere` — die Regel stammt aus #1508/#1526.
    ist_bewertet: Callable[[str, Any], bool] | None = None
    #: Zweiter Pfad fürs Anlegen, z. B. ``issue`` im Singular
    #: (Risikobewertung: ``POST …/risiken/<id>/issue``).
    alias_anlegen_pfad: str = ""
    #: Zweiter Pfad für die Liste, z. B. ``linked-issues`` (Risikobewertung).
    alias_liste_pfad: str = ""
    #: Hülle der Alias-Liste: ``{"items": [...], "total": n}`` statt nackter
    #: Liste. Die Risikobewertung liest ``res.data?.items``.
    alias_liste_huelle: bool = False
    # ── Stapel-Anlage (#1851) ─────────────────────────────────────────────
    #: ``(projekt_name) -> [(objekt_id, objekt), …]`` — **alle** Objekte dieser
    #: Art. Setzt nur die Art, die der projektweite Stapel bedient; sonst legte
    #: „🐙 Issues anlegen" in CRA mit einem Klick Issues für Anforderungen,
    #: OWASP-Kontrollen, Risiken **und** Schwachstellen an. Das wäre keine
    #: Vereinheitlichung, sondern eine Überraschung mit Nebenwirkung im
    #: fremden Repository.
    alle: Callable[[str], list[tuple[Any, dict]]] | None = None
    #: ``(projekt_name, objekt_id, objekt) -> bool`` — ist das ein offener
    #: Punkt? Der Stapel legt ohne ``alle_objekte`` nur für diese Issues an.
    ist_offen: Callable[[str, Any, dict], bool] | None = None


# ── Repo, Provider, Token — eine Stelle für alle ────────────────────────────

def loese_repo(projekt: dict[str, Any], data: dict[str, Any]) -> tuple[str, str, dict]:
    """Provider, Repo und die vcs-Konfiguration bestimmen.

    Reihenfolge: ``repo``/``provider`` aus dem Request gewinnen (Override),
    sonst die pro Projekt gespeicherte ``vcs_publish``-Konfiguration. Das war
    CRAs Verhalten; die Risikobewertung kannte den Override **nicht** und
    verlangte ``vcs['repo']``.
    """
    from shared.vcs_repo_config import resolve_repo

    meta = projekt.get("meta") or {}
    if isinstance(meta, str):
        import json
        try:
            meta = json.loads(meta) or {}
        except Exception:  # noqa: BLE001
            meta = {}
    vcs = dict((meta.get("vcs_publish") or {}) if isinstance(meta, dict) else {})
    repo = resolve_repo(vcs, data.get("repo"))
    provider = str(data.get("provider") or vcs.get("provider") or "github").strip().lower()
    return provider, repo, vcs


def massnahme_abschnitt(stand: dict[str, Any] | None,
                        ueberschrift: str = "### Geplante Maßnahme") -> str:
    """Der Maßnahmen-Block für den Text eines Issues (#1875).

    Das Issue ist der Arbeitsauftrag an die Entwicklung. Genau die Maßnahme
    ist das, was dort getan werden soll; der Kommentar beschreibt nur den
    Stand. Wer das Issue bearbeitet, sah bisher die Lücke, aber nicht den
    schon festgelegten Weg heraus — und erfand ihn neu oder fragte zurück.

    Die Rückrichtung gab es längst: „Issue-Feedback übernehmen" schreibt den
    Inhalt in den Freitext zurück (#1521). Nur der Hinweg ließ die Maßnahme
    liegen — in CRA, NIS2 und AI Act. DSGVO machte es von Anfang an richtig
    und ist hier das Vorbild.

    **Leer, wenn nichts erfasst ist** — kein leerer Abschnitt im Issue. Damit
    ist der Text ohne Maßnahme byte-identisch zu vorher; dieselbe Zusage wie
    bei ``evidence_section`` (#1483) und ``prompt_zusatz`` (#1832), und sie
    macht jeden Bestandstest zum Regressionsschutz.
    """
    text = str((stand or {}).get("massnahme") or "").strip()
    return f"\n{ueberschrift}\n{text}\n" if text else ""


@contextmanager
def token_umgebung(provider: str, vcs: dict[str, Any],
                   gitlab_token_env: str = "GITLAB_TOKEN") -> Iterator[None]:
    """Projektgebundenen Token temporär in die Umgebung legen.

    Die ``create_issue``-Helfer lesen den Token aus der Umgebung. Ihn dort
    hineinzulegen statt ihre Signatur zu ändern, war CRAs Lösung (#862) — nur
    taten es NIS2, AI Act und DSGVO nicht, weshalb der verschlüsselte
    Projekt-Token dort nie zum Einsatz kam.
    """
    from shared.vcs_repo_config import vcs_token

    token = vcs_token(vcs)
    namen = [gitlab_token_env or "GITLAB_TOKEN"] if provider == "gitlab" \
        else ["GH_TOKEN", "GITHUB_TOKEN"]
    gesichert: dict[str, str | None] = {}
    try:
        if token:
            for n in namen:
                gesichert[n] = os.environ.get(n)
                os.environ[n] = token
        yield
    finally:
        for n, alt in gesichert.items():
            if alt is None:
                os.environ.pop(n, None)
            else:
                os.environ[n] = alt


def erzeuge_issue(provider: str, repo: str, titel: str, body: str,
                  vcs: dict[str, Any]) -> tuple[str, int | None, int | None]:
    """Ein Issue beim Anbieter anlegen. Liefert (url, number, iid).

    **Hier wird der GitLab-Aufruf endlich richtig gemacht:** ``description=``,
    nicht ``body=``; ``project=``, nicht ``repo=``; mit ``base_url`` und
    ``token_env``. Vier Module riefen das falsch auf und bekamen jedes Mal
    einen ``TypeError`` → 500.
    """
    with token_umgebung(provider, vcs):
        if provider == "gitlab":
            from vcs.gitlab_issues import create_issue as gl_create
            ci = gl_create(
                base_url=str(vcs.get("base_url") or "https://gitlab.com"),
                token_env=str(vcs.get("token_env") or "GITLAB_TOKEN"),
                project=repo, title=titel, description=body,
            )
            return (str(getattr(ci, "url", "") or ""), None,
                    getattr(ci, "iid", None))
        if provider == "github":
            from vcs.github_issues import create_issue as gh_create
            ci = gh_create(repo=repo, title=titel, body=body)
            return (str(getattr(ci, "url", "") or ""),
                    getattr(ci, "number", None), None)
        raise ValueError(f"Unbekannter Provider: {provider}")


# ── Wer welche Objektarten hat ──────────────────────────────────────────────
#
# `register_routes` schreibt die Objektarten je Modul hierher. Damit kann der
# **projektweite** Abgleich (`abgleiche_projekt`) dieselben Lese-/Schreibwege
# benutzen wie der Abgleich am einzelnen Objekt — vorher hatte jedes Modul
# dafür eine eigene `_complete_all_resolved_*`-Schleife, die die Kommentarzahl
# nicht kannte und deshalb neue Kommentare nicht markierte.

_ARTEN: dict[str, list[ObjektArt]] = {}


def arten_fuer(modul: str) -> list[ObjektArt]:
    """Die registrierten Objektarten eines Moduls (leer, wenn keine)."""
    return list(_ARTEN.get(modul) or [])


def abgleiche_projekt(modul: str, projekt_name: str, *,
                      gitlab_token_env: str = "GITLAB_TOKEN") -> dict[str, Any]:
    """Alle verknüpften Issues eines Projekts abgleichen **und markieren**.

    Antwortform bleibt die von `sync_project_links` (`synced`/`errors`/
    `total`/`items`), damit die Oberfläche unverändert liest; dazu kommt
    `markiert` (wie viele Objekte eine Neubewertungs-Markierung bekamen) und
    `je_art`.

    Links einer **nicht registrierten** Objektart (z. B. CRAs `cra_doc`)
    werden trotzdem abgeglichen — nur nicht markiert: Wo kein Freitext ist,
    kann keine Markierung hin. Sie stillschweigend zu überspringen hieße, den
    Status nicht nachzuholen, und genau das war der Mangel aus #1850.
    """
    from shared import issue_abgleich as ia
    from shared.issue_links import list_project_links

    arten = {a.art: a for a in arten_fuer(modul)}
    if not arten:
        return {"synced": 0, "errors": 0, "total": 0, "items": [],
                "markiert": 0, "auto_completed": 0, "je_art": {}}

    # Über **alle** Datenbanken der Objektarten. Heute teilen die Objektarten
    # eines Moduls eine Datei; eine Objektart mit eigener Datenbank wäre sonst
    # stillschweigend nicht dabei.
    alle: list[Any] = []
    nach_objekt: dict[tuple[str, str], tuple[Path, list[Any]]] = {}
    for db_path in {a.db_path for a in arten.values()}:
        for li in list_project_links(db_path, projekt_name=projekt_name):
            alle.append(li)
            schluessel = (li.object_kind, str(li.object_id))
            nach_objekt.setdefault(schluessel, (db_path, []))[1].append(li)

    items: list[dict[str, Any]] = []
    synced = fehler = markiert = 0
    je_art: dict[str, int] = {}
    for (kind, objekt_id), (db_path, links) in nach_objekt.items():
        art = arten.get(kind)
        if art is not None:
            erg = ia.abgleiche_und_markiere(
                art.db_path, projekt_name=projekt_name, object_kind=kind,
                object_id=objekt_id,
                lies_text=lambda a=art, o=objekt_id: a.lies_text(projekt_name, o),
                schreib_text=lambda t, a=art, o=objekt_id: a.schreib_text(
                    projekt_name, o, t),
                gitlab_token_env=gitlab_token_env,
                bewertet=(art.ist_bewertet(projekt_name, objekt_id)
                          if art.ist_bewertet else None))
        else:
            erg = ia.abgleiche_links(db_path, links,
                                     gitlab_token_env=gitlab_token_env)
        synced += erg.synced
        fehler += erg.fehler
        if erg.markiert:
            markiert += 1
            je_art[kind] = je_art.get(kind, 0) + 1
        for l in erg.links:
            eintrag = l.als_dict()
            eintrag.update(object_kind=kind, object_id=objekt_id)
            items.append(eintrag)

    return {"synced": synced, "errors": fehler, "total": len(alle),
            "items": items, "markiert": markiert,
            # Bestandsschlüssel: Die Oberfläche zeigt ihn seit #833 an. Er
            # zählt jetzt Markierungen — erledigt wird nichts mehr (#1526).
            "auto_completed": markiert, "je_art": je_art}


# ── Die Routen ──────────────────────────────────────────────────────────────

def register_routes(bp, modul: str, arten: list[ObjektArt], *,
                    lade_projekt: Callable[[str], dict | None],
                    projekt_abgleich: bool = True,
                    projekt_uebernahme: bool = True,
                    projekt_stapel_route: bool = True) -> None:
    """Hängt je Objektart die Sechserform an ``bp``.

    ```
    GET    /projekte/<projekt_name>/<pfad>/<param>/issues
    POST   /projekte/<projekt_name>/<pfad>/<param>/issues
    POST   /projekte/<projekt_name>/<pfad>/<param>/issues/link
    POST   /projekte/<projekt_name>/<pfad>/<param>/issues/sync
    POST   /projekte/<projekt_name>/<pfad>/<param>/import-issue
    DELETE /projekte/<projekt_name>/<pfad>/<param>/issues/<link_id>
    ```

    **Unter dem Modul-Prefix**, weil ``server/middleware/authz.py`` Modul und
    Aktion aus dem URL-Prefix ableitet und die Firmen-ACL die Firma über
    ``view_args['projekt_name']`` auflöst — der Pfad-Parameter **muss** so
    heißen (die Lehre aus #1765).
    """
    import datetime as _datetime

    from flask import jsonify, request
    from flask_jwt_extended import get_jwt_identity, jwt_required

    from shared import issue_abgleich as ia
    from shared.issue_links import (add_link, delete_link, ensure_tables,
                                    list_links)

    def _audit(aktion: str, projekt: str, art: ObjektArt, objekt_id: Any, **rest):
        try:
            from shared.audit import audit_event
            audit_event(f"{modul}.{art.art}_issue.{aktion}", module=modul, details={
                "user_id": str(get_jwt_identity() or ""),
                "projekt": str(projekt)[:120],
                "objekt_art": art.art,
                "objekt_id": str(objekt_id),
                **rest,
            })
        except Exception:  # noqa: BLE001
            pass

    def _link_dict(li) -> dict[str, Any]:
        """Die Form, die das Frontend liest — eine Obermenge der Bestandsformen."""
        return {
            "id": li.id, "link_id": li.id,   # WiBA las `link_id`
            "url": li.url, "title": li.title,
            "state": li.state, "state_reason": li.state_reason,
            "provider": li.provider, "repo": li.repo,
            "issue_number": li.issue_number, "issue_iid": li.issue_iid,
            "comments": li.comments,
        }

    def _bau(art: ObjektArt):
        """Erzeugt die sechs Handler für **eine** Objektart."""

        def _vorbereiten(projekt_name: str, objekt_id: Any):
            projekt = lade_projekt(projekt_name)
            if not projekt:
                return None, None, ({"error": "Projekt nicht gefunden"}, 404)
            objekt = art.lade(projekt_name, objekt_id)
            if not objekt:
                if art.pflicht_objekt:
                    return None, None, (
                        {"error": f"{art.bezeichnung} nicht gefunden: {objekt_id}"}, 404)
                objekt = {}   # Katalog nicht geladen — siehe `pflicht_objekt`
            return projekt, objekt, None

        def liste(projekt_name: str, **kw):
            objekt_id = next(iter(kw.values()))
            ensure_tables(art.db_path)
            links = list_links(art.db_path, projekt_name=projekt_name,
                               object_kind=art.art, object_id=str(objekt_id))
            return jsonify([_link_dict(li) for li in links]), 200

        def anlegen(projekt_name: str, **kw):
            objekt_id = next(iter(kw.values()))
            projekt, objekt, fehler = _vorbereiten(projekt_name, objekt_id)
            if fehler:
                return fehler
            data = request.get_json(silent=True) or {}
            provider, repo, vcs = loese_repo(projekt, data)
            if not repo:
                return {"error": "Kein Repository für dieses Projekt konfiguriert "
                                 "(Projekt-Einstellungen → VCS)."}, 400
            stand = art.stand(projekt_name, objekt_id) if art.stand else {}
            vorgabe_titel, vorgabe_body = art.inhalt(objekt_id, objekt, stand)
            titel = str(data.get("title") or vorgabe_titel)
            body = str(data.get("body") or vorgabe_body)
            try:
                url, nummer, iid = erzeuge_issue(provider, repo, titel, body, vcs)
            except Exception as e:  # noqa: BLE001
                from vcs.errors import IssueBackendFehlt
                if isinstance(e, IssueBackendFehlt):
                    raise           # #1815: zentraler errorhandler → 412
                return {"error": f"Issue konnte nicht angelegt werden: {e}"}, 502
            ensure_tables(art.db_path)
            link_id = add_link(art.db_path, projekt_name=projekt_name,
                               object_kind=art.art, object_id=str(objekt_id),
                               provider=provider, repo=repo, url=url,
                               issue_number=nummer, issue_iid=iid, title=titel,
                               state="open")
            _audit("created", projekt_name, art, objekt_id, url=url, repo=repo)
            return {"created": True, "ok": True, "url": url, "link_id": link_id,
                    "id": link_id, "provider": provider,
                    # `number`/`iid` sind die Schlüssel der Risikobewertung,
                    # `issue_number`/`issue_iid` die der übrigen Module. Beide
                    # stehen hier, weil ein fehlender Schlüssel im Frontend
                    # **still** zu `undefined` wird (die Lehre aus #1830).
                    "number": nummer, "iid": iid,
                    "issue_number": nummer, "issue_iid": iid, "title": titel}, 201

        def verknuepfen(projekt_name: str, **kw):
            objekt_id = next(iter(kw.values()))
            _, _, fehler = _vorbereiten(projekt_name, objekt_id)
            if fehler:
                return fehler
            data = request.get_json(silent=True) or {}
            url = str(data.get("url") or "").strip()
            if not url:
                return {"error": 'Feld "url" ist Pflicht'}, 400
            from shared.issue_sync import _parse_issue_url
            # `_parse_issue_url` **wirft nicht**, es liefert
            # `(None, None, None, None, None)` — ein `try/except` darum
            # greift deshalb nie. Ohne die Prüfung läuft eine Eingabe wie
            # „kein-issue" bis `add_link` durch und endet in 500 statt 400.
            provider, pfad, nummer, iid, _basis = _parse_issue_url(url)
            if provider not in ("github", "gitlab"):
                return {"error": "Keine gültige GitHub-/GitLab-Issue-URL"}, 400
            ensure_tables(art.db_path)
            link_id = add_link(art.db_path, projekt_name=projekt_name,
                               object_kind=art.art, object_id=str(objekt_id),
                               provider=provider, repo=pfad or "", url=url,
                               issue_number=nummer, issue_iid=iid)
            _audit("linked", projekt_name, art, objekt_id, url=url)
            return {"linked": True, "ok": True, "url": url, "link_id": link_id,
                    "id": link_id, "provider": provider}, 201

        def abgleichen(projekt_name: str, **kw):
            objekt_id = next(iter(kw.values()))
            _, _, fehler = _vorbereiten(projekt_name, objekt_id)
            if fehler:
                return fehler
            data = request.get_json(silent=True) or {}
            erg = ia.abgleiche_und_markiere(
                art.db_path, projekt_name=projekt_name, object_kind=art.art,
                object_id=str(objekt_id),
                lies_text=lambda: art.lies_text(projekt_name, objekt_id),
                schreib_text=lambda t: art.schreib_text(projekt_name, objekt_id, t),
                gitlab_token_env=str(data.get("gitlab_token_env") or "GITLAB_TOKEN"),
                bewertet=(art.ist_bewertet(projekt_name, objekt_id)
                          if art.ist_bewertet else None))
            antwort = erg.als_dict()
            # `resolved` bleibt als **Information** („das Issue ist zu"), nicht
            # mehr als Auftrag: Seit der Entscheidung zu #1526 für alle Module
            # erledigt der Abgleich nichts von selbst — er markiert.
            antwort["resolved"] = any(
                not ia.ist_offen(l.state) for l in erg.links if l.ok and l.state)
            _audit("synced", projekt_name, art, objekt_id,
                   synced=erg.synced, fehler=erg.fehler, anlaesse=erg.anlaesse)
            return antwort, 200

        def uebernehmen(projekt_name: str, **kw):
            objekt_id = next(iter(kw.values()))
            _, _, fehler = _vorbereiten(projekt_name, objekt_id)
            if fehler:
                return fehler
            data = request.get_json(silent=True) or {}
            text = str(data.get("issue_context") or "").strip()
            quellen: list[dict] = []
            if not text:
                ensure_tables(art.db_path)
                links = list_links(art.db_path, projekt_name=projekt_name,
                                   object_kind=art.art, object_id=str(objekt_id))
                if not links:
                    return {"error": "Keine verknüpften Issues für dieses "
                                     f"{art.bezeichnung}"}, 400
                from shared.issue_feedback import collect_issue_feedback
                from shared.vcs_repo_config import vcs_fuer_projekt
                # #1871: mit dem Token DIESES Projekts holen, nicht mit dem
                # globalen aus der Umgebung — sonst ist eine Installation mit
                # mehreren GitHub-Zielen auf genau einen Zugang festgelegt.
                text, quellen = collect_issue_feedback(
                    links,
                    vcs=vcs_fuer_projekt(art.db_path, projekt_name),
                    gitlab_token_env=str(data.get("gitlab_token_env") or "GITLAB_TOKEN"))
                if not text:
                    gruende = "; ".join(q.get("error", "") for q in quellen
                                        if not q.get("ok"))
                    return {"error": "Issue-Inhalt konnte nicht geladen werden: "
                                     f"{gruende}"}, 502
            from shared.issue_feedback import merge_feedback_into_comment
            alt = art.lies_text(projekt_name, objekt_id) or ""
            neu = merge_feedback_into_comment(alt, text)
            art.schreib_text(projekt_name, objekt_id, neu)
            _audit("imported", projekt_name, art, objekt_id,
                   quellen=len(quellen),
                   fehlgeschlagen=sum(1 for q in quellen if not q.get("ok")))
            # Obermenge: `ok`+`bewertung_text` liest der Risiko-Editor,
            # `imported`+`kommentar` alle anderen. Keiner bricht.
            return {"imported": True, "ok": True, "kommentar": neu,
                    "notiz": neu, "bewertung_text": neu,
                    "id": str(objekt_id), "sources": quellen}, 200

        def entknuepfen(projekt_name: str, link_id: str, **kw):
            delete_link(art.db_path, link_id)
            _audit("unlinked", projekt_name, art, next(iter(kw.values()), ""),
                   link_id=link_id)
            return {"deleted": True, "ok": True}, 200

        def bestaetigen(projekt_name: str, **kw):
            """#1868: „angesehen, passt weiterhin" — die Markierung quittieren.

            Der Fall, für den es bis #1868 keinen Weg gab. Wer nichts ändern
            wollte, musste eine Bewertung neu abschicken (ein Vorgang, den es
            nicht gab) oder die Zeile von Hand aus dem Freitext löschen (ohne
            jede Spur). Dass jemand hingesehen und die Bewertung bestätigt
            hat, ist in einer Nachweisakte die interessantere Aussage als die
            Markierung selbst.

            **Score, Antwort und Risikowert bleiben unberührt** (#1526).
            """
            objekt_id = next(iter(kw.values()))
            _, _, fehler = _vorbereiten(projekt_name, objekt_id)
            if fehler:
                return fehler
            alt = art.lies_text(projekt_name, objekt_id) or ""
            if not ia.hat_marker(alt):
                # Etwas zu bestätigen, das nicht zur Neubewertung ansteht,
                # wäre eine Aussage über einen Vorgang, den es nicht gab.
                return {"error": f"Dieses {art.bezeichnung} ist nicht zur "
                                 "Neubewertung markiert.",
                        "code": "nicht-markiert"}, 409

            from shared.ki_herkunft_api import _person
            ident = str(get_jwt_identity() or "")
            person = _person(ident)
            data = request.get_json(silent=True) or {}
            heute = _datetime.date.today().strftime("%d.%m.%Y")
            neu, _ = ia.bestaetige_marker(
                alt, von=person, am=heute,
                notiz=str(data.get("notiz") or "")[:400])
            art.schreib_text(projekt_name, objekt_id, neu)

            # Hinsehen und bestätigen **ist** die fachliche Prüfung (dieselbe
            # Überlegung wie bei der Gruppenübernahme in #1773). `pruefen` ist
            # ein UPDATE und legt keine Zeile an — eine von Hand erstellte
            # Bewertung ohne KI-Herkunft bleibt also unberührt, und das ist
            # richtig: Dort gibt es keinen Entwurf zu prüfen.
            try:
                from shared import ki_herkunft
                ki_herkunft.pruefen(modul, projekt_name, art.art,
                                    str(objekt_id), von=person)
            except Exception:  # noqa: BLE001 — die Bestätigung steht schon
                import logging
                logging.getLogger("aics.issues").warning(
                    "KI-Prüfvermerk nicht gesetzt (%s/%s/%s)",
                    projekt_name, art.art, objekt_id, exc_info=True)

            _audit("bestaetigt", projekt_name, art, objekt_id, person=person)
            # Obermenge der Freitext-Schlüssel wie bei `uebernehmen` — ein
            # fehlender Schlüssel wird im Frontend still zu `undefined` (#1830).
            return {"bestaetigt": True, "ok": True, "von": person, "am": heute,
                    "kommentar": neu, "notiz": neu, "bewertung_text": neu,
                    "id": str(objekt_id)}, 200

        return (liste, anlegen, verknuepfen, abgleichen, uebernehmen,
                entknuepfen, bestaetigen)

    _ARTEN[modul] = list(arten)

    if projekt_abgleich or projekt_uebernahme:
        def projekt_abgleichen(projekt_name: str):
            if not lade_projekt(projekt_name):
                return {"error": "Projekt nicht gefunden"}, 404
            data = request.get_json(silent=True) or {}
            erg = abgleiche_projekt(
                modul, projekt_name,
                gitlab_token_env=str(data.get("gitlab_token_env") or "GITLAB_TOKEN"))
            try:
                from shared.audit import audit_event
                audit_event(f"{modul}.issues.synced", module=modul, details={
                    "user_id": str(get_jwt_identity() or ""),
                    "projekt": str(projekt_name)[:120],
                    "synced": erg["synced"], "markiert": erg["markiert"]})
            except Exception:  # noqa: BLE001
                pass
            return erg, 200

        def projekt_uebernehmen(projekt_name: str):
            """Inhalt **aller** verknüpften Issues in die jeweiligen Freitexte.

            Vorher sah dieser Weg in CRA, NIS2 und AI Act nur Anforderungen —
            OWASP-Kontrollen, Risiken und Schwachstellen blieben außen vor,
            obwohl man an jedem davon ein Issue verknüpfen kann.
            """
            if not lade_projekt(projekt_name):
                return {"error": "Projekt nicht gefunden"}, 404
            data = request.get_json(silent=True) or {}
            gitlab_token_env = str(data.get("gitlab_token_env") or "GITLAB_TOKEN")
            # `risk_ids`/`req_ids` sind die Bestandsnamen derselben Auswahl.
            auswahl = {str(x) for x in (data.get("object_ids")
                                        or data.get("risk_ids")
                                        or data.get("req_ids") or [])}
            from shared.issue_feedback import (collect_issue_feedback,
                                               merge_feedback_into_comment)
            from shared.issue_links import list_project_links
            from shared.vcs_repo_config import vcs_fuer_projekt

            arten_map = {a.art: a for a in arten}
            # #1871: Einmal je Lauf auflösen, nicht je Objekt — die
            # Konfiguration hängt am Projekt, nicht an der Anforderung. Alle
            # Objektarten eines Moduls teilen sich dieselbe Projekt-DB.
            vcs_projekt = vcs_fuer_projekt(arten[0].db_path, projekt_name) if arten else {}
            uebernommen = fehlgeschlagen = 0
            items: list[dict[str, Any]] = []
            gruppen: dict[tuple[str, str], list[Any]] = {}
            for db_path in {a.db_path for a in arten}:
                for li in list_project_links(db_path, projekt_name=projekt_name):
                    if li.object_kind not in arten_map:
                        continue
                    if auswahl and str(li.object_id) not in auswahl:
                        continue
                    gruppen.setdefault(
                        (li.object_kind, str(li.object_id)), []).append(li)

            for (kind, objekt_id), links in gruppen.items():
                art = arten_map[kind]
                eintrag: dict[str, Any] = {"object_kind": kind,
                                           "object_id": objekt_id,
                                           # Bestandsschlüssel der Oberflächen
                                           "anforderung_id": objekt_id,
                                           "risk_id": objekt_id}
                text, quellen = collect_issue_feedback(
                    links, vcs=vcs_projekt, gitlab_token_env=gitlab_token_env)
                eintrag["sources"] = quellen
                if not text:
                    fehlgeschlagen += 1
                    eintrag["ok"] = False
                    items.append(eintrag)
                    continue
                try:
                    alt_text = art.lies_text(projekt_name, objekt_id) or ""
                    art.schreib_text(projekt_name, objekt_id,
                                     merge_feedback_into_comment(alt_text, text))
                except Exception as e:  # noqa: BLE001
                    fehlgeschlagen += 1
                    eintrag["ok"] = False
                    eintrag["error"] = str(e)
                    items.append(eintrag)
                    continue
                uebernommen += 1
                eintrag["ok"] = True
                items.append(eintrag)

            try:
                from shared.audit import audit_event
                audit_event(f"{modul}.issues.imported", module=modul, details={
                    "user_id": str(get_jwt_identity() or ""),
                    "projekt": str(projekt_name)[:120],
                    "imported": uebernommen, "failed": fehlgeschlagen})
            except Exception:  # noqa: BLE001
                pass
            return {"imported": uebernommen, "failed": fehlgeschlagen,
                    "total": len(gruppen), "items": items}, 200

        def projekt_stapel(projekt_name: str):
            """Für die offenen Punkte des Projekts Issues im Stapel anlegen.

            Vorher stand dieser Weg fünfmal einzeln da (~90 Zeilen je Modul)
            und WiBA hatte ihn gar nicht — der Knopf fehlte, weil die Route
            fehlte. Drei der fünf Fassungen trugen dabei **denselben Defekt,
            den #1846 an der Einzelanlage beseitigt hat**: ``gl_create(…,
            body=body)`` gegen eine Signatur, die ``description=`` verlangt
            (CRA, NIS2, AI Act) — die Stapel-Anlage über GitLab endete dort in
            einem ``TypeError`` und damit in einem 500. Ein Defekt, der in
            einer Kopie behoben wird, bleibt in den anderen vier.

            Body: ``{repo?, provider?, gitlab_base_url?, gitlab_token_env?,
            only_gaps?=true, skip_linked?=true, object_ids?}``.
            ``only_open`` und ``req_ids``/``risk_ids``/``control_ids`` sind die
            Bestandsnamen derselben Schalter.
            """
            projekt = lade_projekt(projekt_name)
            if not projekt:
                return {"error": "Projekt nicht gefunden"}, 404
            quelle = next((a for a in arten if a.alle is not None), None)
            if quelle is None:
                return {"error": "Für dieses Modul gibt es keine Stapel-Anlage"}, 501

            data = request.get_json(silent=True) or {}
            provider, repo, vcs = loese_repo(projekt, data)
            if not repo:
                return {"error": "Kein Repository für dieses Projekt konfiguriert "
                                 "(Repo-Konfig speichern oder repo übergeben)"}, 400
            # Die Overrides des Requests wandern **in** die vcs-Konfiguration:
            # `erzeuge_issue` liest Basis-URL und Token-Variable von dort, und
            # ein Override, den nur diese Funktion kennt, käme nicht an.
            vcs = {**vcs,
                   "base_url": str(data.get("gitlab_base_url")
                                   or vcs.get("base_url") or "https://gitlab.com"),
                   "token_env": str(data.get("gitlab_token_env")
                                    or vcs.get("token_env") or "GITLAB_TOKEN")}
            nur_offene = data.get("only_gaps", data.get("only_open", True))
            ohne_verknuepfte = data.get("skip_linked", True)
            auswahl_roh = (data.get("object_ids") or data.get("req_ids")
                           or data.get("risk_ids") or data.get("control_ids"))
            auswahl = ({str(x) for x in auswahl_roh}
                       if isinstance(auswahl_roh, list) else None)

            from shared.issue_links import ensure_tables, list_links
            ensure_tables(quelle.db_path)

            angelegt: list[dict[str, Any]] = []
            uebersprungen: list[dict[str, Any]] = []
            fehlgeschlagen: list[dict[str, Any]] = []

            # Den Token setzt `erzeuge_issue` selbst (es öffnet
            # `token_umgebung`) — ein zweiter Rahmen hier wäre dieselbe
            # Variable zweimal, und genau diese Doppelung war in drei Modulen
            # der Grund, dass der projektgebundene Token nie ankam (#1846).
            for objekt_id, objekt in (quelle.alle(projekt_name) or []):
                kennung = str(objekt_id)
                eintrag = {"object_id": kennung,
                           # Bestandsschlüssel der Oberflächen (#1830): ein
                           # fehlender Schlüssel wird dort still `undefined`.
                           "req_id": kennung, "risk_id": kennung,
                           "control_id": kennung}
                if auswahl is not None and kennung not in auswahl:
                    continue
                if (auswahl is None and nur_offene and quelle.ist_offen is not None
                        and not quelle.ist_offen(projekt_name, objekt_id, objekt)):
                    continue
                if ohne_verknuepfte and list_links(
                        quelle.db_path, projekt_name=projekt_name,
                        object_kind=quelle.art, object_id=kennung):
                    uebersprungen.append({**eintrag, "reason": "bereits verknüpft",
                                          "grund": "bereits verknüpft"})
                    continue
                stand = quelle.stand(projekt_name, objekt_id) if quelle.stand else {}
                titel, body = quelle.inhalt(objekt_id, objekt, stand or {})
                try:
                    url, nummer, iid = erzeuge_issue(provider, repo, titel, body, vcs)
                except Exception as e:  # noqa: BLE001
                    fehlgeschlagen.append({**eintrag, "error": str(e)})
                    continue
                try:
                    from shared.issue_links import add_link
                    add_link(quelle.db_path, projekt_name=projekt_name,
                             object_kind=quelle.art, object_id=kennung,
                             provider=provider, repo=repo, url=url,
                             issue_number=nummer, issue_iid=iid, title=titel)
                except Exception as e:  # noqa: BLE001
                    # Das Issue steht bereits im fremden Repository. Es als
                    # Fehlschlag zu melden ist richtig; es stillschweigend als
                    # Erfolg zu zählen wäre falsch — beim nächsten Lauf
                    # entstünde ein zweites.
                    fehlgeschlagen.append({**eintrag, "url": url,
                                           "error": f"Issue angelegt, "
                                                    f"Verknüpfung fehlgeschlagen: {e}"})
                    continue
                angelegt.append({**eintrag, "url": url, "title": titel,
                                 "issue_number": nummer, "issue_iid": iid,
                                 "number": nummer, "iid": iid})

            try:
                from shared.audit import audit_event
                audit_event(f"{modul}.issues.bulk_created", module=modul, details={
                    "user_id": str(get_jwt_identity() or ""),
                    "projekt": str(projekt_name)[:120], "repo": repo,
                    "created": len(angelegt), "skipped": len(uebersprungen),
                    "failed": len(fehlgeschlagen)})
            except Exception:  # noqa: BLE001
                pass

            return {"ok": True, "created": angelegt, "skipped": uebersprungen,
                    "failed": fehlgeschlagen,
                    # DSGVO las die Zahlen bisher direkt unter `created`; dort
                    # stehen jetzt — wie in den vier übrigen Modulen — die
                    # Einträge. Die Zahlen stehen in `summary`.
                    "created_items": angelegt, "skipped_items": uebersprungen,
                    "failed_items": fehlgeschlagen,
                    "summary": {"created": len(angelegt),
                                "skipped": len(uebersprungen),
                                "failed": len(fehlgeschlagen),
                                "total": len(angelegt) + len(uebersprungen)
                                + len(fehlgeschlagen)}}, 200

        def projekt_neubewertung(projekt_name: str):
            """Was die verknüpften Issues über dieses Projekt sagen — **lesend**.

            Die siebte Handlung der Werkzeugleiste („🧪 Neubewertung aus
            Issues", #1851) gab es nur in der Risikobewertung, dort als
            `…/issue-sync` mit einem ``refresh``-Schalter, der GitHub live
            abfragte (GitLab nur im Nebenzweig) — in einem POST, der nichts
            schrieb.

            Hier ist es ein **GET ohne Netzaufruf**: Gezeigt wird der
            gespeicherte Stand aus ``linked_issues``, je Objekt mit seinem
            Wert, der aktuellen Markierung und dem Zeitpunkt des letzten
            Abgleichs. Den Stand **frisch holen** ist die andere Handlung
            („Status abgleichen"); zwei Wege, dasselbe von der Gegenstelle zu
            holen, wären zwei Wahrheiten über denselben Sachverhalt — und der
            eine davon kannte nur einen der beiden Anbieter.
            """
            if not lade_projekt(projekt_name):
                return {"error": "Projekt nicht gefunden"}, 404
            from shared.issue_abgleich import hat_marker, ist_offen
            from shared.issue_links import list_project_links

            arten_map = {a.art: a for a in arten}
            gruppen: dict[tuple[str, str], list[Any]] = {}
            for db_path in {a.db_path for a in arten}:
                for li in list_project_links(db_path, projekt_name=projekt_name):
                    if li.object_kind in arten_map:
                        gruppen.setdefault(
                            (li.object_kind, str(li.object_id)), []).append(li)

            eintraege: list[dict[str, Any]] = []
            for (kind, objekt_id), links in sorted(gruppen.items()):
                art = arten_map[kind]
                text = ""
                stand: dict[str, Any] = {}
                try:
                    text = art.lies_text(projekt_name, objekt_id) or ""
                    stand = (art.stand(projekt_name, objekt_id) or {}) if art.stand else {}
                except Exception:  # noqa: BLE001 — ein unlesbares Objekt darf
                    pass           # die Übersicht nicht nehmen
                eintraege.append({
                    "object_kind": kind, "object_id": objekt_id,
                    # Bestandsschlüssel der Oberflächen (#1830).
                    "risk_id": objekt_id, "req_id": objekt_id,
                    "control_id": objekt_id,
                    "bezeichnung": art.bezeichnung,
                    # #1868: Das URL-Segment liefert der Server mit. Eine
                    # Tabelle `object_kind -> pfad` im Frontend wäre die
                    # Spiegel-Liste aus #1731/#1735 — und sie bräche genau
                    # dort, wo Art und Pfad auseinanderfallen (`owasp_llm`
                    # gegen `owasp-llm`).
                    "pfad": art.pfad,
                    "titel": str(stand.get("titel") or stand.get("risk_name")
                                 or stand.get("frage") or ""),
                    "wert": stand.get("bewertung", stand.get("status",
                                      stand.get("risiko_label"))),
                    "markiert": hat_marker(text),
                    "issues": [{
                        "id": getattr(li, "link_id", None) or getattr(li, "id", ""),
                        "url": getattr(li, "url", ""),
                        "provider": getattr(li, "provider", ""),
                        "title": getattr(li, "title", "") or "",
                        "state": getattr(li, "state", "") or "",
                        "offen": ist_offen(getattr(li, "state", "") or ""),
                        "comments": getattr(li, "comments", None),
                        "issue_number": getattr(li, "issue_number", None),
                        "issue_iid": getattr(li, "issue_iid", None),
                        "updated_at": getattr(li, "updated_at", None),
                    } for li in links],
                })

            offene = sum(1 for e in eintraege
                         if any(i["offen"] for i in e["issues"]))
            return {"items": eintraege, "total": len(eintraege),
                    "markiert": sum(1 for e in eintraege if e["markiert"]),
                    "mit_offenen_issues": offene}, 200

        gewaehlt = []
        if projekt_stapel_route:
            gewaehlt.append(("/projekte/<projekt_name>/issues/bulk",
                             f"issue_{modul}_projekt_stapel", projekt_stapel))
        if projekt_abgleich:
            gewaehlt.append(("/projekte/<projekt_name>/issues/sync",
                             f"issue_{modul}_projekt_abgleich", projekt_abgleichen))
        if projekt_uebernahme:
            gewaehlt.append(("/projekte/<projekt_name>/issues/import",
                             f"issue_{modul}_projekt_uebernahme", projekt_uebernehmen))
        for regel, name, fn in gewaehlt:
            fn.__name__ = name
            bp.add_url_rule(regel, name, jwt_required()(fn), methods=["POST"])

        # Lesend und deshalb GET — ein POST, der nichts schreibt, lädt zum
        # Schreiben ein (die Lehre aus `GET /releases/<version>` in #1748).
        projekt_neubewertung.__name__ = f"issue_{modul}_projekt_neubewertung"
        bp.add_url_rule("/projekte/<projekt_name>/issues/neubewertung",
                        projekt_neubewertung.__name__,
                        jwt_required()(projekt_neubewertung), methods=["GET"])

    for art in arten:
        (liste, anlegen, verknuepfen, abgleichen, uebernehmen, entknuepfen,
         bestaetigen) = _bau(art)
        basis = f"/projekte/<projekt_name>/{art.pfad}/{art.param}"
        ep = f"issue_{modul}_{art.art}"
        paare = (
            (f"{basis}/issues", f"{ep}_liste", liste, ["GET"]),
            (f"{basis}/issues", f"{ep}_anlegen", anlegen, ["POST"]),
            (f"{basis}/issues/link", f"{ep}_verknuepfen", verknuepfen, ["POST"]),
            (f"{basis}/issues/sync", f"{ep}_abgleichen", abgleichen, ["POST"]),
            (f"{basis}/import-issue", f"{ep}_uebernehmen", uebernehmen, ["POST"]),
            (f"{basis}/issues/<link_id>", f"{ep}_entknuepfen", entknuepfen, ["DELETE"]),
            # #1868: „angesehen, passt weiterhin". Kommt aus derselben Fabrik,
            # weil `ObjektArt` den Freitext schon kennt — eine zweite
            # Zuordnung wäre die Spiegel-Liste aus #1731/#1735.
            (f"{basis}/neubewertung/bestaetigen", f"{ep}_bestaetigen",
             bestaetigen, ["POST"]),
        )
        for regel, name, fn, methoden in paare:
            fn.__name__ = name
            bp.add_url_rule(regel, name, jwt_required()(fn), methods=methoden)

        # ── Alt-URLs ──────────────────────────────────────────────────────
        if art.alias_entknuepfen_ohne_id:
            def _entknuepfen_ohne_id(projekt_name: str, link_id: str, _a=art):
                from shared.issue_links import delete_link as _del
                _del(_a.db_path, link_id)
                _audit("unlinked", projekt_name, _a, "", link_id=link_id)
                return {"deleted": True, "ok": True}, 200

            name = f"{ep}_entknuepfen_alt"
            _entknuepfen_ohne_id.__name__ = name
            bp.add_url_rule(f"/projekte/<projekt_name>/{art.pfad}/issues/<link_id>",
                            name, jwt_required()(_entknuepfen_ohne_id),
                            methods=["DELETE"])

        if art.alias_anlegen_pfad:
            name = f"{ep}_anlegen_alt"
            _anlegen_alt = (lambda _a=anlegen: _a)()
            bp.add_url_rule(
                f"/projekte/<projekt_name>/{art.pfad}/{art.param}/{art.alias_anlegen_pfad}",
                name, jwt_required()(_anlegen_alt), methods=["POST"])

        if art.alias_liste_pfad:
            def _liste_alt(projekt_name: str, _a=art, _l=liste, **kw):
                antwort, status = _l(projekt_name, **kw)
                if not _a.alias_liste_huelle:
                    return antwort, status
                eintraege = antwort.get_json() if hasattr(antwort, "get_json") else antwort
                return jsonify({"items": eintraege,
                                "total": len(eintraege or [])}), status

            name = f"{ep}_liste_alt"
            _liste_alt.__name__ = name
            bp.add_url_rule(
                f"/projekte/<projekt_name>/{art.pfad}/{art.param}/{art.alias_liste_pfad}",
                name, jwt_required()(_liste_alt), methods=["GET"])


__all__ = ["ObjektArt", "abgleiche_projekt", "arten_fuer", "erzeuge_issue",
           "loese_repo", "massnahme_abschnitt", "register_routes",
           "token_umgebung"]
