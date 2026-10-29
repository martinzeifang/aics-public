"""Der Status-Abgleich — ein Verhalten für alle Objektarten (#1850).

WOFÜR DER ABGLEICH DA IST
Die Suite fragt GitHub/GitLab nicht laufend — **es gibt keinen Webhook**. Was
in ``linked_issues`` steht, ist der Stand des letzten Abgleichs. Der Knopf hat
deshalb zwei Aufgaben, und die zweite ist die eigentliche:

1. Den gespeicherten Status nachholen (Titel, offen/geschlossen).
2. Daraus die fachliche Folge ziehen: Hat sich am Issue etwas getan, ist die
   Bewertung **neu zu prüfen** — score-neutral markiert (#1526/#1520). Die
   frühere Auto-Erfüllung auf 5/„ja" wurde entfernt, weil eine
   Compliance-Bewertung sich nicht ändern darf, nur weil ein Ticket zu ist.

WAS ER VORHER TAT
Bei Anforderungen — dem häufigsten Fall — setzte er den Marker **nicht**; nur
die OWASP-Wege und der projektweite Abgleich taten es. Fünf von sieben Wegen
übersprangen GitLab stillschweigend (``if li.provider == 'github'``, kein
Fehler, ``synced: 0``), und neue Kommentare erkannte die Suite überhaupt
nicht. Dieselbe Handlung tat je nach Knopf etwas anderes — und genau das ist
der Grund, warum die Beschriftungen vereinheitlicht werden *nachdem* das
Verhalten es ist: Gleicher Name für Verschiedenes wäre schlimmer als
verschiedene Namen.

DER ERSTABGLEICH MARKIERT NICHT
Ohne gespeicherte Kommentarzahl wird sie nur gelernt. Sonst meldete der erste
Abgleich nach dem Update jedes Objekt mit Kommentaren als „neu zu bewerten" —
und eine Markierung, die alle trifft, trifft niemanden.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

#: Anlässe, aus denen eine Neubewertung folgt. Der Marker nennt sie beim
#: Namen: Wer ihn sieht, soll ohne Klick wissen, ob jemand das Ticket
#: geschlossen oder nur etwas dazugeschrieben hat — das entscheidet, ob man
#: hinsehen muss.
ANLASS_GESCHLOSSEN = "Issue geschlossen"
ANLASS_GEOEFFNET = "Issue wieder geöffnet"


def anlass_kommentare(anzahl: int) -> str:
    return f"{anzahl} neue{'r' if anzahl == 1 else ''} Kommentar{'' if anzahl == 1 else 'e'}"


@dataclass
class LinkErgebnis:
    """Was der Abgleich an **einem** verknüpften Issue festgestellt hat."""

    link_id: str
    url: str
    ok: bool
    state: str = ""
    state_reason: str = ""
    title: str = ""
    comments: int = 0
    #: Anlässe für eine Neubewertung (leer = nichts hat sich getan).
    anlaesse: list[str] = field(default_factory=list)
    #: Erstabgleich: Kommentarzahl war noch nie erhoben, nur gelernt.
    erstabgleich: bool = False
    #: Wie das Issue im Marker genannt wird (``#101`` bzw. die URL).
    referenz: str = ""
    fehler: str = ""

    def als_dict(self) -> dict[str, Any]:
        d = {
            "id": self.link_id, "url": self.url, "ok": self.ok,
            "state": self.state, "state_reason": self.state_reason,
            "title": self.title, "comments": self.comments,
            "anlaesse": self.anlaesse,
        }
        if self.fehler:
            d["error"] = self.fehler
        return d


@dataclass
class AbgleichErgebnis:
    """Das Ergebnis über alle Links eines Objekts."""

    synced: int = 0
    fehler: int = 0
    links: list[LinkErgebnis] = field(default_factory=list)
    #: Alle Anlässe über alle Links — die Grundlage für den Marker.
    anlaesse: list[str] = field(default_factory=list)
    #: Die Issues, aus denen die Anlässe stammen (``#101``) — für den Marker.
    referenzen: list[str] = field(default_factory=list)
    #: Trägt der Freitext des Objekts die Markierung jetzt? **Nicht** dasselbe
    #: wie `neubewertung_noetig`: Ein nie bewertetes Objekt bekommt keinen
    #: Marker (siehe `abgleiche_und_markiere`), und ein zweiter Abgleich
    #: schreibt nichts, obwohl der Marker steht.
    markiert: bool = False

    @property
    def neubewertung_noetig(self) -> bool:
        return bool(self.anlaesse)

    def als_dict(self) -> dict[str, Any]:
        return {
            "synced": self.synced,
            "errors": self.fehler,
            "links": [l.als_dict() for l in self.links],
            "anlaesse": self.anlaesse,
            "neubewertung": self.neubewertung_noetig,
            "markiert": self.markiert,
        }


def _hole(li: Any, feld: str, vorgabe: Any = None) -> Any:
    if isinstance(li, dict):
        return li.get(feld, vorgabe)
    return getattr(li, feld, vorgabe)


def ist_offen(state: str) -> bool:
    return str(state or "").lower() in ("open", "opened", "reopened")


def abgleiche_links(db_path: Path, links: list[Any], *,
                    gitlab_token_env: str = "GITLAB_TOKEN") -> AbgleichErgebnis:
    """Gleicht **alle** übergebenen Links ab — beide Provider, ohne Ausnahme.

    Ein Link, der sich nicht abgleichen lässt, erzeugt einen **benannten
    Fehler** im Ergebnis. Stilles Überspringen war der Zustand vorher: Der
    Anwender sah „abgeglichen", und nichts war passiert.
    """
    from shared.issue_links import add_link
    from shared.issue_sync import sync_github_issue, sync_gitlab_issue, _parse_issue_url

    erg = AbgleichErgebnis()
    for li in links or []:
        link_id = str(_hole(li, "id", "") or "")
        url = str(_hole(li, "url", "") or "")
        provider = str(_hole(li, "provider", "") or "")
        repo = str(_hole(li, "repo", "") or "")
        nummer = _hole(li, "issue_number")
        iid = _hole(li, "issue_iid")
        alt_state = str(_hole(li, "state", "") or "")
        alt_comments = _hole(li, "comments")
        objekt_kind = str(_hole(li, "object_kind", "") or "")
        objekt_id = str(_hole(li, "object_id", "") or "")
        projekt = str(_hole(li, "projekt_name", "") or "")

        ergebnis = LinkErgebnis(link_id=link_id, url=url, ok=True,
                                referenz=_referenz(nummer, iid, url))
        try:
            p2, pfad2, num2, iid2, basis = _parse_issue_url(url)
            prov = provider or p2 or ""
            if prov == "github":
                neu = sync_github_issue(repo=(repo or pfad2 or ""),
                                        number=int(nummer or num2 or 0))
            elif prov == "gitlab":
                neu = sync_gitlab_issue(base_url=(basis or ""),
                                        token_env=gitlab_token_env,
                                        project=(pfad2 or repo or ""),
                                        iid=int(iid or iid2 or 0))
            else:
                raise ValueError(
                    f"Unbekannter Provider für {url or '(ohne URL)'} — weder "
                    "GitHub noch GitLab erkannt.")

            # Anlässe bestimmen, BEVOR der neue Stand geschrieben wird.
            # **Geschlossen ist ein Zustand, kein Wechsel.** Die Vorgabe
            # lautet: „Ist das Issue geschlossen, muss die Markierung
            # angebracht werden — immer." Auf den Übergang zu prüfen wäre
            # schwächer: Wer den vorherigen Stand nie erhoben hat (frische
            # Installation, eingespielte Sicherung, von Hand angelegter
            # Link), erfährt sonst nie, dass das Ticket längst zu ist.
            # `setze_marker` ist idempotent — die Markierung wächst nicht.
            #
            # Die lokale Variable darf NICHT `ist_offen` heißen: Eine
            # Zuweisung an diesen Namen macht ihn im ganzen Funktionsrumpf
            # lokal, und der Aufruf der Funktion darüber wirft
            # `UnboundLocalError`. Von den Tests gefunden.
            nun_offen = ist_offen(neu.state)
            if not nun_offen and neu.state:
                ergebnis.anlaesse.append(ANLASS_GESCHLOSSEN)
            elif alt_state and not ist_offen(alt_state) and nun_offen:
                # Wiedereröffnung ist dagegen nur als Übergang erkennbar:
                # „offen" allein ist der Normalzustand und kein Anlass.
                ergebnis.anlaesse.append(ANLASS_GEOEFFNET)
            if alt_comments is None:
                ergebnis.erstabgleich = True   # nur lernen, nicht markieren
            elif int(neu.comments) > int(alt_comments):
                ergebnis.anlaesse.append(
                    anlass_kommentare(int(neu.comments) - int(alt_comments)))

            add_link(db_path, projekt_name=projekt, object_kind=objekt_kind,
                     object_id=objekt_id, provider=prov, repo=(neu.repo or repo),
                     url=url, issue_number=(neu.number or nummer),
                     issue_iid=(neu.iid or iid), title=neu.title,
                     state=neu.state, state_reason=neu.state_reason,
                     comments=int(neu.comments), remote_updated_at=neu.updated_at)

            ergebnis.state = neu.state
            ergebnis.state_reason = neu.state_reason
            ergebnis.title = neu.title
            ergebnis.comments = int(neu.comments)
            erg.synced += 1
        except Exception as e:  # noqa: BLE001 — je Link tolerant, aber nie stumm
            ergebnis.ok = False
            ergebnis.fehler = f"{type(e).__name__}: {e}"
            erg.fehler += 1
            # **Der Anlass folgt notfalls aus dem gespeicherten Stand.** Ist
            # die Gegenstelle nicht erreichbar, bleibt die Tatsache bestehen,
            # dass das Issue beim letzten Abgleich geschlossen war — sie zu
            # verschweigen, weil GitHub gerade nicht antwortet, wäre die
            # schlechtere Hälfte. Die Kommentarzahl lässt sich dann nicht
            # vergleichen; dafür gibt es keine neuen Daten.
            ergebnis.state = alt_state
            if alt_state and not ist_offen(alt_state):
                ergebnis.anlaesse.append(ANLASS_GESCHLOSSEN)
        erg.links.append(ergebnis)
        erg.anlaesse.extend(ergebnis.anlaesse)
        if ergebnis.anlaesse and ergebnis.referenz:
            erg.referenzen.append(ergebnis.referenz)
    return erg


def _referenz(nummer: Any, iid: Any, url: str) -> str:
    """Wie das Issue im Marker genannt wird.

    Die Nummer steht drin, weil der Marker sonst nicht sagt, **welches**
    Ticket gemeint ist — bei mehreren verknüpften Issues ist das die halbe
    Auskunft. Ohne Nummer die URL: lieber lang als nichtssagend.
    """
    for wert in (nummer, iid):
        try:
            if wert is not None and int(wert) > 0:
                return f"#{int(wert)}"
        except (TypeError, ValueError):
            continue
    return str(url or "")


# ── Der Marker ──────────────────────────────────────────────────────────────

#: Stabiler Marker, an dem die Oberfläche die Markierung erkennt. Der Wortlaut
#: bis #1850 lautete „⚠️ Neubewertung erforderlich – verknüpftes Issue
#: geändert"; der Präfix bleibt gleich, damit Bestandstexte weiter erkannt
#: werden (`NEEDS_REASSESS_MARKER` in shared/issue_completion).
MARKER = "⚠️ Neubewertung erforderlich"
#: Stabiler Präfix der **Bestätigung** (#1868). Die Oberfläche erkennt sie
#: daran, deshalb darf sich der Wortlaut dahinter ändern, dieser Anfang nicht.
BESTAETIGT = "✅ Neubewertung bestätigt"


def _eindeutig(werte: list[str]) -> list[str]:
    raus: list[str] = []
    for w in werte or []:
        if w and w not in raus:
            raus.append(w)
    return raus


def marker_text(anlaesse: list[str], referenzen: list[str] | None = None) -> str:
    """Der Markertext, der den **Anlass** und das **Issue** nennt.

    „verknüpftes Issue geändert" sagte nicht, ob jemand das Ticket geschlossen
    oder nur etwas dazugeschrieben hat — und genau das entscheidet, ob man
    hinsehen muss. Die Issue-Referenz stand im alten Wortlaut und bleibt: ohne
    sie weiß der Leser bei mehreren Verknüpfungen nicht, wohin er klicken soll.
    """
    grund = ", ".join(_eindeutig(anlaesse))
    if not grund:
        return ""
    refs = _eindeutig(list(referenzen or []))
    return f"{MARKER} – {grund}" + (f" ({', '.join(refs)})" if refs else "")


def setze_marker(text: str, anlaesse: list[str],
                 referenzen: list[str] | None = None) -> tuple[str, bool]:
    """Hängt den Marker an einen Kommentar/eine Notiz. Liefert (text, geändert).

    **Score-, antwort- und risikowert-neutral** (#1526): Diese Funktion rührt
    nur den Freitext an. Ein zweiter Abgleich ohne Änderung am Issue ändert
    nichts — sonst wüchse der Kommentar bei jedem Knopfdruck.
    """
    neuer_marker = marker_text(anlaesse, referenzen)
    if not neuer_marker:
        return (text or "", False)
    bestand = str(text or "")
    # Einen vorhandenen Marker ersetzen statt anzuhängen: Zwei Markierungen
    # untereinander sagen nicht mehr als eine, und die ältere ist überholt.
    #
    # #1868: Eine frühere **Bestätigung** fällt genauso weg. Tut sich am Issue
    # wieder etwas, gilt „angesehen, passt weiterhin" nicht mehr — stünde die
    # Zeile weiter da, hätte der Text zwei widersprechende Aussagen und der
    # Leser müsste raten, welche die jüngere ist.
    zeilen = [z for z in bestand.split("\n")
              if not z.strip().startswith(MARKER)
              and not z.strip().startswith(BESTAETIGT)]
    # `strip()`, nicht `rstrip()`: Nach dem Entfernen der Markerzeile bleibt
    # die Leerzeile darunter stehen. Mit `rstrip()` entstünde bei jedem
    # Abgleich eine zusätzliche Leerzeile, der Text gälte als geändert, und
    # der Kommentar wüchse bei jedem Knopfdruck.
    rumpf = "\n".join(zeilen).strip()
    neu = f"{neuer_marker}\n\n{rumpf}".strip() if rumpf else neuer_marker
    return (neu, neu != bestand)


def hat_marker(text: Any) -> bool:
    return MARKER in str(text or "")



def bestaetige_marker(text: str, *, von: str, am: str,
                      notiz: str = "") -> tuple[str, bool]:
    """Die Markierung durch eine Bestätigung ersetzen. Liefert (text, geändert).

    Der Fall, den `setze_marker` offen ließ: **angesehen, passt weiterhin**.
    Bis #1868 verschwand die Markierung nur, wenn eine *neue* Bewertung
    übernommen wurde (`issue_completion.clear_markers`) — oder von Hand aus dem
    Freitext. Wer nichts ändern wollte, musste also eine Bewertung neu
    abschicken, und das erzeugt einen Vorgang, den es nicht gab.

    **Es wird ersetzt, nicht gestapelt.** Zwei Bestätigungen untereinander
    sagen nicht mehr als eine, und die ältere ist überholt — dieselbe
    Überlegung wie bei der Markerzeile selbst.

    **Score, Antwort und Risikowert rührt diese Funktion nicht an.** Bestätigt
    wird, dass die Bewertung weiter gilt, nicht welche sie ist (#1526).
    """
    if not str(von or "").strip():
        raise ValueError("Eine Bestätigung braucht die Person, die sie gegeben hat")
    bestand = str(text or "")
    zeile = f"{BESTAETIGT} am {am} durch {von} – Bewertung unverändert gültig."
    if str(notiz or "").strip():
        zeile += f" {str(notiz).strip()}"
    # Markerzeile **und** eine frühere Bestätigung fallen weg. `strip()` wie in
    # `setze_marker`: sonst bleibt die Leerzeile darunter stehen und der Text
    # gilt bei jedem Klick als geändert.
    zeilen = [z for z in bestand.split("\n")
              if not z.strip().startswith(MARKER)
              and not z.strip().startswith(BESTAETIGT)]
    rumpf = "\n".join(zeilen).strip()
    neu = f"{zeile}\n\n{rumpf}".strip() if rumpf else zeile
    return (neu, neu != bestand)


def ist_bestaetigt(text: Any) -> bool:
    return BESTAETIGT in str(text or "")


# ── Verdrahtung in die Module ───────────────────────────────────────────────

def abgleiche_und_markiere(db_path: Path, *, projekt_name: str, object_kind: str,
                           object_id: str, lies_text: Callable[[], str],
                           schreib_text: Callable[[str], None],
                           gitlab_token_env: str = "GITLAB_TOKEN",
                           bewertet: bool | None = None) -> AbgleichErgebnis:
    """Abgleich **und** Markierung in einem Schritt — für jede Objektart gleich.

    ``lies_text``/``schreib_text`` sind die einzigen modul-eigenen Teile: Wo
    der Freitext steht, weiß nur das Modul (Kommentar einer Anforderung, Notiz
    einer Prüffrage, Bewertungstext eines Risikos). Alles andere ist hier.

    ``bewertet=False`` schreibt **keinen** Marker: Ein Objekt, das noch
    niemand bewertet hat, kann nicht „neu" bewertet werden, und es steht in
    jeder Liste ohnehin als offen. Diese Regel gilt seit #1508/#1526 für
    Anforderungen und OWASP-Kontrollen; WiBA-Prüffragen kannten sie bewusst
    nicht und bekommen den Marker immer (``bewertet=None``). Das Ergebnis
    nennt die Anlässe trotzdem — festgestellt ist festgestellt, auch wenn
    nichts geschrieben wird.
    """
    from shared.issue_links import list_links

    links = list_links(db_path, projekt_name=projekt_name,
                       object_kind=object_kind, object_id=object_id)
    erg = abgleiche_links(db_path, links, gitlab_token_env=gitlab_token_env)
    if erg.neubewertung_noetig and bewertet is not False:
        try:
            alt = lies_text() or ""
            neu, geaendert = setze_marker(alt, erg.anlaesse, erg.referenzen)
            if geaendert:
                schreib_text(neu)
            # `markiert` heißt „der Text trägt die Markierung jetzt" — auch
            # beim zweiten Abgleich, der nichts mehr zu schreiben hat. Der
            # Zähler im projektweiten Abgleich zählt genau das; an
            # `neubewertung_noetig` gehängt hätte er auch die Objekte
            # mitgezählt, bei denen bewusst nichts geschrieben wurde.
            erg.markiert = hat_marker(neu)
        except Exception:  # noqa: BLE001 — der Abgleich selbst bleibt gültig
            import logging
            logging.getLogger("aics.issues").warning(
                "Neubewertungs-Marker nicht gesetzt (%s/%s/%s)",
                projekt_name, object_kind, object_id, exc_info=True)
    return erg


__all__ = [
    "ANLASS_GEOEFFNET", "ANLASS_GESCHLOSSEN", "BESTAETIGT", "AbgleichErgebnis",
    "LinkErgebnis", "MARKER", "abgleiche_links", "abgleiche_und_markiere",
    "anlass_kommentare", "bestaetige_marker", "hat_marker", "ist_bestaetigt",
    "ist_offen", "marker_text", "setze_marker",
]
