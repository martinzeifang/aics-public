"""Welche Bewertungen sind überholt? (#1864/A) — **ohne einen KI-Lauf.**

DER BEFUND
Eine Bewertung ist eine Aussage über einen Zeitpunkt. Danach kommen ein neuer
Nachweis, eine neue SBOM, ein Pentest-Bericht, ein CVE — und die Aussage gilt
weiter, ohne dass irgendwo steht, dass sie alt ist. Auffallen konnte das bisher
nur über den Issue-Weg (#1526, Marker „⚠️ Neubewertung erforderlich“); alles
andere blieb stumm.

WARUM GERECHNET UND NICHT GEFRAGT
Der Vergleich „Bewertung älter als Ereignis“ ist Arithmetik. Eine KI danach zu
fragen wäre teuer, langsam und eine zweite Wahrheit über denselben Sachverhalt
— dieselbe Regel wie bei den Prüfhinweisen in #1862 und den zwei
Berichts-Renderern in #1726/#1727. Dieses Modul kostet nichts und läuft in
Millisekunden.

WOHER DIE EREIGNISSE KOMMEN
Aus dem **Revisionspfad**, nicht aus sechs modul-eigenen Abfragen. Jedes
relevante Ereignis schreibt dort seit #1338 ohnehin mit, und `audit_db.
projekt_ereignisse` liest es seit #1851 projektbezogen. Eine eigene Sammlung je
Modul wäre die Spiegel-Liste aus #1731/#1735 — und beim siebten Ereignis fehlte
sie wieder.

WAS DAS BEWUSST NICHT TUT
Es bewertet nicht neu. Die Liste ist ein Vorschlag an den Menschen, der sie in
die vorhandene Massenbewertung schicken kann (#1573) — oder eben nicht. Ein
automatisches Nachziehen wäre eine Bewertung, die niemand bestellt hat.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

#: Welche Revisions-Ereignisse eine Bewertung **überholen** können — mit dem
#: Satz, der dem Anwender gesagt wird.
#:
#: Die Liste ist kurz und benannt, nicht „alles was im Pfad steht“: Ein
#: Speichervorgang an der Bewertung selbst überholt sie nicht, und ein
#: Anmeldevorgang schon gar nicht. Wer bei allem anschlägt, wird abgeschaltet
#: (#1774).
#: **Die Namen sind belegt, nicht abgeschrieben (#1870).** In der ersten
#: Fassung waren fünf von neun erfunden — `cra.sbom.imported` statt
#: `cra.sbom.eingelesen`, `pentest.bericht.uploaded` statt
#: `pentest.bericht.created`, und `cra.vuln.synced` gab es überhaupt nicht.
#: Gemerkt hat es niemand, weil der Test seine Ereignisse selbst mitbrachte.
#: `tests/test_nachziehen_aktenpruefung_1864.py` hält jeden Schlüssel jetzt
#: gegen die schreibenden Stellen im Produktionscode.
EREIGNISSE: dict[str, str] = {
    # ── firmenweit (module='firmen'/'pentest') — s. FIRMENWEIT ────────────
    "evidence.mapping.approved":
        "ein neuer Nachweis wurde der Akte zugeordnet",
    "pentest.bericht.created":
        "ein Pentest-Bericht ist eingegangen",
    "pentest.findings.imported":
        "Pentest-Befunde wurden übernommen",
    "pentest.cra.applied":
        "Pentest-Befunde wurden nach CRA übernommen",
    "pentest.dsgvo.applied":
        "Pentest-Befunde wurden in die TOM-Wirksamkeit übernommen",
    "pentest.wiba.applied":
        "Pentest-Befunde wurden an WiBA-Prüffragen vermerkt",
    # ── projektbezogen ────────────────────────────────────────────────────
    "cra.sbom.eingelesen":
        "eine neue SBOM wurde eingelesen",
    "cra.sbom.aus_registry":
        "eine SBOM wurde vom Image geholt",
    "cra.sbom_komponenten.importiert":
        "die Komponentenliste hat sich geändert",
    "cra.vuln.sync":
        "der Schwachstellen-Abgleich ist gelaufen",
    "cra.vuln.upstream_gemeldet":
        "eine Schwachstelle wurde dem Komponenten-Hersteller gemeldet",
    "cra.release.art":
        "die Art des Releases wurde festgelegt oder geändert",
    "cra.release.wesentliche_aenderung":
        "eine wesentliche Änderung wurde erklärt",
    "risikobewertung.framework_changed":
        "das Framework der verknüpften Risikobewertung wurde gewechselt",
    "dsgvo.tom.wiba_sync":
        "die TOM-Ableitung aus WiBA wurde nachgezogen",
}

#: Ereignisse, die der **Firma** gehören und nicht einem Modulprojekt (#1870).
#:
#: Ein Nachweis und ein Pentest-Bericht gelten für den Mandanten, nicht für
#: eines seiner sechs Modulprojekte — `evidence.mapping.approved` schreibt
#: deshalb mit ``module='firmen'`` und ``details={firma, …}``, die
#: Pentest-Ereignisse mit ``module='pentest'``. `projekt_ereignisse(modul,
#: projekt)` filtert auf ``module == modul`` **und** ``details.projekt ==
#: projekt`` und sah sie damit nie. Genau diese zwei nennt der Dateikopf
#: oben als Begründung für das ganze Modul.
#:
#: Die Brücke lässt sich **nicht** beim Schreiben schlagen: Welche
#: Modulprojekte eine Firma hat, weiß die schreibende Stelle nicht, und sie
#: soll es nicht wissen müssen. Also wird beim Lesen zugeordnet.
FIRMENWEIT: dict[str, str] = {
    "firmen": "firma",
    "pentest": "firma",
}


#: Modul → (DB-Datei, Tabelle, ID-Spalte, Bedingung „ist bewertet“).
#:
#: **Warum diese Tabelle sein muss:** Der Vergleich darf nicht nur
#: ``ki_herkunft`` lesen. Dort steht ausschließlich, was eine **KI** erzeugt
#: hat — wer 130 Anforderungen von Hand bewertet und danach einen
#: Pentest-Bericht bekommt, hätte nie einen Hinweis erhalten. Genau diese
#: Bewertungen sind aber die, auf die sich ein Prüfer verlässt.
#:
#: Die Namen der sechs Tabellen sind historisch verschieden, die Struktur ist
#: dieselbe (``projekt_name``, eine ID-Spalte, ``updated_at``). Damit die
#: Liste nicht zur stillen Spiegel-Liste wird (#1731/#1735), hält
#: ``tests/test_nachziehen_aktenpruefung_1864.py`` sie gegen die sechs Module.
BEWERTUNGEN: dict[str, tuple[str, str, str, str]] = {
    "cra": ("data/db/cra.sqlite", "cra_bewertungen", "anforderung_id",
            "COALESCE(bewertung, 0) > 0"),
    "nis2": ("data/db/nis2.sqlite", "nis2_bewertungen", "anforderung_id",
             "COALESCE(bewertung, 0) > 0"),
    "aiact": ("data/db/ai_act.sqlite", "ai_act_bewertungen", "anforderung_id",
              "COALESCE(bewertung, 0) > 0"),
    "dsgvo": ("data/db/dsgvo.sqlite", "dsgvo_bewertungen", "anforderung_id",
              "COALESCE(bewertung, 0) > 0"),
    # WiBA: „offen“ ist keine Bewertung, sondern ihr Fehlen (#1118).
    "wiba": ("data/db/wiba.sqlite", "wiba_antworten", "control_id",
             "COALESCE(status, 'offen') <> 'offen'"),
    # Risikobewertung: unbewertete Risiken haben keinen Wert.
    "risikobewertung": ("data/db/risikobewertung.sqlite", "rb_risiken", "id",
                        "risikowert IS NOT NULL"),
}


def bewertungsstaende(modul: str, projekt: str) -> dict[str, str]:
    """Je Objekt-ID der Zeitpunkt der **letzten Änderung** seiner Bewertung.

    Best effort: Fehlt die Tabelle (Teilinstallation, Modul nie benutzt), ist
    das Ergebnis leer — der Vergleich fällt dann auf die KI-Herkunft zurück.
    """
    eintrag = BEWERTUNGEN.get((modul or "").strip().lower())
    if not eintrag:
        return {}
    db, tabelle, id_spalte, bedingung = eintrag
    try:
        from pathlib import Path

        from shared import db as _sdb
        con = _sdb.connect(Path(db))
        try:
            rows = con.execute(
                f"SELECT {id_spalte} AS oid, updated_at FROM {tabelle} "  # nosec B608 - Bezeichner aus BEWERTUNGEN, nicht aus Eingaben
                f"WHERE projekt_name=? AND ({bedingung})",
                (projekt,)).fetchall()
        finally:
            con.close()
    except Exception:  # noqa: BLE001
        return {}
    return {str(dict(r).get("oid")): str(dict(r).get("updated_at") or "")
            for r in rows}


@dataclass
class Ueberholt:
    """Eine Bewertung, die älter ist als ein Ereignis in derselben Akte."""

    objekt_art: str
    objekt_id: str
    bewertet_am: str
    anlass: str
    anlass_am: str
    #: Wurde die KI-Bewertung von einem Menschen geprüft? Eine geprüfte
    #: Bewertung ist nicht „falsch“, aber die Prüfung galt für den alten Stand.
    geprueft: bool = False
    #: Stammt die Bewertung (auch) aus einer KI? Sonst ist sie von Hand
    #: entstanden — die Anzeige sagt das, weil es den Umgang damit ändert.
    ki: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"objekt_art": self.objekt_art, "objekt_id": self.objekt_id,
                "bewertet_am": self.bewertet_am, "anlass": self.anlass,
                "anlass_am": self.anlass_am, "geprueft": self.geprueft,
                "ki": self.ki}


def _als_zeit(wert: Any) -> datetime | None:
    """ISO-Zeichenkette → datetime; alles Unverständliche → ``None``.

    ``None`` heißt „nicht vergleichbar“ und führt dazu, dass **kein** Befund
    entsteht. Die andere Richtung — im Zweifel melden — würde für jeden
    Bestandsdatensatz ohne Zeitstempel eine Überholung behaupten, und die Liste
    wäre beim ersten Aufruf unbenutzbar.
    """
    if not wert:
        return None
    s = str(wert).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def anlaesse(ereignisse: Iterable[dict[str, Any]]) -> list[tuple[datetime, str, str]]:
    """Aus Revisions-Einträgen die **überholenden** heraussuchen.

    Liefert ``(zeit, aktion, satz)``, jüngste zuerst. Reine Funktion — ohne
    Datenbank testbar.
    """
    out: list[tuple[datetime, str, str]] = []
    for e in ereignisse or []:
        aktion = str((e or {}).get("action") or "")
        satz = EREIGNISSE.get(aktion)
        if not satz:
            continue
        zeit = _als_zeit((e or {}).get("created_at") or (e or {}).get("ts"))
        if zeit is None:
            continue
        out.append((zeit, aktion, satz))
    return sorted(out, key=lambda t: t[0], reverse=True)


def vergleiche(herkunft: dict[str, dict[str, Any]],
               anlass_liste: list[tuple[datetime, str, str]],
               *, objekt_art: str = "",
               bewertet: dict[str, str] | None = None) -> list[Ueberholt]:
    """Bewertungen gegen die Anlässe halten.

    Args:
      herkunft: ``ki_herkunft.fuer_projekt(...)`` — je Objekt-ID der Eintrag
        mit ``erzeugt_am`` und ``geprueft_am``.
      anlass_liste: Ergebnis von :func:`anlaesse`.
      bewertet: Ergebnis von :func:`bewertungsstaende` — je Objekt-ID der
        Zeitpunkt der letzten Bewertungsänderung, **unabhängig davon, ob eine
        KI beteiligt war**. Ohne diese Quelle sähe die Liste nur
        KI-Bewertungen, und wer von Hand bewertet hat, bekäme nie einen
        Hinweis — ausgerechnet für die Bewertungen, auf die sich ein Prüfer
        verlässt.

    Maßgeblich ist der **jüngste** bekannte Zeitpunkt je Objekt: Hat ein
    Mensch die Bewertung nach ihrer Erzeugung geprüft, zählt die Prüfung. Sonst
    stünde eine eben geprüfte Bewertung wegen eines alten Ereignisses auf der
    Liste, und der Anwender hätte dieselbe Arbeit zweimal.
    """
    if not anlass_liste:
        return []
    bewertet = bewertet or {}
    # Vereinigung beider Quellen: Ein Objekt kann in genau einer von beiden
    # stehen — von Hand bewertet (nur `bewertet`) oder KI-bewertet und noch
    # nie gespeichert (nur `herkunft`).
    out: list[Ueberholt] = []
    for objekt_id in set(herkunft or {}) | set(bewertet):
        eintrag = (herkunft or {}).get(objekt_id) or {}
        erzeugt = _als_zeit(eintrag.get("erzeugt_am"))
        geprueft = _als_zeit(eintrag.get("geprueft_am"))
        gespeichert = _als_zeit(bewertet.get(objekt_id))
        stand = max([z for z in (erzeugt, geprueft, gespeichert) if z],
                    default=None)
        if stand is None:
            continue
        for zeit, _aktion, satz in anlass_liste:
            if zeit > stand:
                out.append(Ueberholt(
                    objekt_art=str(eintrag.get("objekt_art") or objekt_art),
                    objekt_id=str(objekt_id),
                    bewertet_am=stand.isoformat(),
                    anlass=satz, anlass_am=zeit.isoformat(),
                    geprueft=bool(geprueft), ki=bool(erzeugt)))
                break  # der jüngste Anlass genügt; eine Liste von Gründen je
                       # Objekt wäre für die Entscheidung „nochmal ansehen?“
                       # ohne Wert.
    return sorted(out, key=lambda u: (u.objekt_art, u.objekt_id))


def ueberholte(modul: str, projekt: str, *, objekt_art: str = "",
               fenster: int = 2000) -> dict[str, Any]:
    """Die Liste für ein Projekt — Einstieg für den Endpunkt.

    Best effort: Fehlt der Revisionspfad oder das Herkunftsregister, ist die
    Liste leer und das Ergebnis sagt es (``vollstaendig: False``). Eine leere
    Liste, die sich als vollständig ausgibt, wäre die falsche Richtung — sie
    liest sich wie „alles aktuell“.
    """
    vollstaendig = True
    try:
        from shared.audit_db import projekt_ereignisse
        roh = projekt_ereignisse(modul, projekt, limit=fenster, fenster=fenster)
        # #1870: `events` — und nur das. Die erste Fassung las
        # `roh.get("revisionspfad") or roh.get("items")`; beide Schlüssel gibt
        # es nicht, `anlaesse` bekam **immer** eine leere Liste, und
        # `vergleiche` kehrte sofort um. Der Dialog war damit seit #1864 in
        # jedem Modul auf jeder Instanz leer — und meldete `vollstaendig`.
        liste = anlaesse(roh.get("events") or [])
    except Exception:  # noqa: BLE001
        liste, vollstaendig = [], False

    # #1870: Nachweise und Pentest-Berichte gehören der **Firma**. Ohne diesen
    # Zweig fehlen genau die zwei Anlässe, die dieses Modul begründen.
    try:
        liste = sorted(liste + _firmenweite_anlaesse(modul, projekt, fenster),
                       key=lambda x: x[0], reverse=True)
    except Exception:  # noqa: BLE001
        vollstaendig = False

    try:
        from shared.ki_herkunft import fuer_projekt
        herkunft = fuer_projekt(modul, projekt, objekt_art)
    except Exception:  # noqa: BLE001
        herkunft, vollstaendig = {}, False

    # Alle Bewertungen, nicht nur die KI-generierten (s. `vergleiche`).
    bewertet = bewertungsstaende(modul, projekt)
    treffer = vergleiche(herkunft, liste, objekt_art=objekt_art,
                         bewertet=bewertet)
    return {
        "items": [u.as_dict() for u in treffer],
        "anlass": liste[0][2] if liste else "",
        "anlass_am": liste[0][0].isoformat() if liste else "",
        "bewertungen": len(set(herkunft) | set(bewertet)),
        "bewertungen_ki": len(herkunft),
        # #1870: „keine Ereignisse in der Akte" und „nichts überholt" sind
        # zwei Sachverhalte. Die Leermeldung behauptete den zweiten, obwohl
        # der erste vorlag — ein Satz, auf den sich ein Prüfer verlässt.
        "anlaesse": len(liste),
        "vollstaendig": vollstaendig,
    }


def _firma_von(modul: str, projekt: str) -> str:
    """Firmenname des Modulprojekts — oder leer.

    **Leer heißt: firmenweite Ereignisse zählen nicht mit.** Das ist die
    ruhige Richtung: Ein Pentest-Bericht, der sich keiner Firma zuordnen
    lässt, würde sonst allen Mandanten eine Überholung anhängen, und eine
    Liste, die bei allen anschlägt, wird abgeschaltet (#1774).
    """
    eintrag = BEWERTUNGEN.get((modul or "").strip().lower())
    if not eintrag:
        return ""
    try:
        from pathlib import Path

        from firmen import db as _fdb
        from shared.firmen_link import firmen_db_path, projekt_firmen_id
        modul_db = Path(eintrag[0])
        fid = projekt_firmen_id(modul_db, projekt)
        if fid is None:
            return ""
        for row in _fdb.list_firmen_rows(firmen_db_path(modul_db)):
            if int(row.get("id") or 0) == int(fid):
                return str(row.get("name") or "")
    except Exception:  # noqa: BLE001
        return ""
    return ""


def _firmenweite_anlaesse(modul: str, projekt: str,
                          fenster: int) -> list[tuple[datetime, str, str]]:
    """Anlässe aus den firmenweiten Spuren (``firmen``, ``pentest``)."""
    firma = _firma_von(modul, projekt)
    if not firma:
        return []
    from shared.audit_db import ereignisse_nach_detail
    out: list[tuple[datetime, str, str]] = []
    for audit_modul, schluessel in FIRMENWEIT.items():
        roh = ereignisse_nach_detail(audit_modul, schluessel, firma,
                                     limit=fenster, fenster=fenster)
        out += anlaesse(roh.get("events") or [])
    return out




def register_routes(bp, modul: str, *, objekt_art: str = "") -> None:
    """Hängt ``GET /projekte/<projekt_name>/ueberholt`` an ``bp`` (#1864/A).

    Unter dem **Modul-Prefix** und mit dem Pfad-Parameter ``projekt_name`` —
    wörtlich die Lehre aus #1765/#1835/#1851: ``server/middleware/authz.py``
    leitet Modul und Aktion aus dem URL-Prefix ab, und die Firmen-ACL löst die
    Firma über ``view_args['projekt_name']`` auf. Ein eigener Prefix wäre kein
    Modul-Pfad, und jeder angemeldete Nutzer könnte fremde Mandanten lesen.
    """
    from flask import current_app, jsonify, request
    from flask_jwt_extended import jwt_required

    ep = f"ueberholt_{modul}"

    def lesen(projekt_name: str):
        art = (request.args.get("art") or objekt_art or "").strip()
        try:
            return jsonify(ueberholte(modul, projekt_name, objekt_art=art))
        except Exception as e:  # noqa: BLE001
            current_app.logger.exception("%s %s — %s", request.method,
                                         request.path, e)
            return jsonify({"error": "Interner Serverfehler"}), 500

    lesen.__name__ = f"{ep}_lesen"
    bp.add_url_rule("/projekte/<projekt_name>/ueberholt", f"{ep}_lesen",
                    jwt_required()(lesen), methods=["GET"])


__all__ = ["BEWERTUNGEN", "EREIGNISSE", "Ueberholt", "anlaesse",
           "bewertungsstaende", "register_routes", "ueberholte",
           "vergleiche"]
