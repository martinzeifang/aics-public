"""Die eine Funktion für jede KI-Anfrage (#1841, aus #1836/E4).

Die Bestandsaufnahme #1836 fand **87 KI-Wege**, von denen **47 selbst mit der
KI sprechen** — verteilt auf 21 Dateien, mit eigenen Budgets, eigenen Parsern,
eigenen Audit-Entscheidungen und fünf eigenen Ollama-Clients. Nicht weil
jemand nachlässig war, sondern weil es keine Stelle gab, an der diese Fragen
einmal beantwortet sind. Das Ergebnis liest sich an der Zählung ab: Der
Herkunftsvermerk fehlt in ≥ 36 Wegen, das Ausgabebudget kommt auf dem
Standard-Provider in 25 Wegen gar nicht an, und die eigenen Hinweise des
Bearbeiters (#1833) erreichen 28 Wege nicht.

Hier steht, was **immer** gilt:

1. Verfügbarkeit prüfen — kein Stream, der sofort mit ``done {ok:false}`` endet.
2. Egress-Bestätigung auswerten und auditieren (mit ``user_id``, #1784).
3. **Eigene Hinweise einsetzen** (#1833) und vermerken.
4. Transport mit Parametern, die ankommen — und mit einer Meldung darüber,
   was der Provider nicht kann.
5. Ergebnis in einem Stück: Parser, Abschneide-Erkennung, Herkunftsvermerk,
   **ein** Audit-Ereignis mit Lauf-Kennung.

WAS HIER AUSDRÜCKLICH NICHT GELEISTET WIRD
Drei Pflichten aus #1836 gehören zum **Prompt-Bauer**, nicht zum Transport:
die Säuberung von Fremdtext (``security_utils``), der Nachweis-Block (#1485)
und das Issue-Feedback (#1521). Die Engine bekommt einen fertigen Prompt;
nachträglich lässt sich nicht mehr trennen, was darin Fremdtext war. Sie hier
zu versprechen hieße, eine Lücke mit einer Zusicherung zuzudecken.

WARUM EIN AUFTRAGS-OBJEKT UND KEINE ZWÖLF SCHLÜSSELWORTE
Die Unterschiede zwischen den Wegen sind **fachlich** (Antwortform,
Vertraulichkeit, Mengengerüst) und gehören benannt. Als Schlüsselwort-Flut
wären sie wieder Literale an der Aufrufstelle — also genau der Zustand, der
die Streuung erzeugt hat.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal

from shared import prompt_zusatz as _pz

# ── Antwortformen ───────────────────────────────────────────────────────────

#: Wie die Antwort aussehen soll. Das ist **kein** Stilwunsch: Parser,
#: ``format=json`` und das Budget hängen daran, und Prosa durch einen
#: JSON-Parser zu schicken wäre falsch.
ANTWORTFORMEN = ("json", "json_array", "prosa")

_SYSTEM_JSON = (
    "Du bist ein erfahrener Compliance-Experte. Antworte ausschließlich mit "
    "validem JSON im geforderten Format. Verwende keinerlei Erläuterungen "
    "außerhalb des JSON."
)
_SYSTEM_PROSA = (
    "Du bist ein erfahrener Compliance-Experte. Antworte präzise, sachlich und "
    "genau im geforderten Format."
)

#: Temperatur je Antwortform. Die Staffelung im Bestand (0.0 Diagnose · 0.1
#: Extraktion · 0.2 Bewertung · 0.3 Formulierung) ist bewusst — Extraktion will
#: Reproduzierbarkeit, Formulierung will Sprache. Sie stand nur zwölfmal als
#: Literal da.
_TEMP_JE_FORM = {"json": 0.2, "json_array": 0.2, "prosa": 0.3}

# ── Budget ──────────────────────────────────────────────────────────────────

#: Grundbudget je Aufgabenart (Ausgabe-Tokens). Abgeleitet aus den Werten, die
#: #1419/#1588 gegen abgeschnittene Antworten gesetzt haben.
_BUDGET_JE_AUFGABE = {
    "bewertung": 4096,        # reiches Format: Kommentar + Maßnahmen + Normbezug
    "massenbewertung": 16384,  # ein Sammel-Prompt über viele Objekte
    "extraktion": 12000,      # Pentest-Bericht in Scheiben
    #: #1861: ein Dokument gegen einen Anforderungskatalog. Die Antwort ist eine
    #: Liste von Zuordnungen mit Zitat und Begründung — bei einem reichhaltigen
    #: Dokument sind das leicht 30 Einträge, und eine abgeschnittene Liste ist
    #: hier besonders tückisch: Sie sieht aus wie ein mager belegtes Dokument.
    "erschliessung": 8192,
    #: #1864: die eigene Akte gegen die Rückfragen eines Prüfers lesen.
    "aktenpruefung": 8192,
    "pruefung": 4096,         # Dokument-Vollständigkeit
    "analyse": 2048,         # Alarm-/Vorfallanalyse (SOC)
    "zusammenfassung": 2048,
    "entwurf": 4096,          # Wasserstand, Berichtsentwürfe
    "assistent": 16384,       # Prompt kommt vom Client, Länge unbekannt
    "diagnose": 512,
    "sonstiges": 1024,
}


def budget_fuer(aufgabe: str, menge: int = 1) -> int:
    """Ausgabebudget aus **Aufgabenart und Mengengerüst**, nicht aus Gewohnheit.

    Ein Sammel-Prompt über 80 Anforderungen braucht wirklich mehr als eine
    Einzelbewertung — bisher wurde das je Route geraten (1024 · 2048 · 4096 ·
    12000 · 16384, ohne erkennbare Regel). Das Ergebnis wird gegen
    ``ai.max_output_tokens`` gedeckelt (``dispatch.output_budget``).
    """
    grund = _BUDGET_JE_AUFGABE.get(str(aufgabe or ""), _BUDGET_JE_AUFGABE["sonstiges"])
    if menge and menge > 1:
        # Je Objekt ein Zuschlag, aber nicht linear — die Modelle fassen sich
        # in einer Liste kürzer als in Einzelantworten.
        grund = int(grund + min(int(menge) - 1, 60) * 400)
    try:
        from ai_compliance_suite.ai.dispatch import output_budget
        return int(output_budget(grund))
    except Exception:  # noqa: BLE001 — ohne Konfiguration gilt der Grundwert
        return int(grund)


# ── Herkunft ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Herkunft:
    """Welches Fachobjekt die KI-Antwort bekommt (#1765)."""

    art: str          # shared.ki_herkunft_api.ARTEN
    objekt_id: str


class _OhneObjekt:
    """Sentinel: Diese Anfrage erzeugt keinen Inhalt an einem Fachobjekt.

    Gilt für Zusammenfassungen, Assistenten-Entwürfe und Diagnose. Das ist
    eine **Aussage**, kein fehlender Parameter — deshalb ein eigener Wert und
    kein ``None``-Default. Die Lücke aus #1765 (zwei von acht Objektarten
    wurden nie geschrieben) entstand genau daraus, dass das Weglassen nichts
    kostete.
    """

    def __repr__(self) -> str:  # pragma: no cover — nur für Fehlermeldungen
        return "OHNE_OBJEKT"


OHNE_OBJEKT = _OhneObjekt()


# ── Auftrag und Ergebnis ────────────────────────────────────────────────────

@dataclass
class KiAuftrag:
    """Eine KI-Anfrage, vollständig beschrieben.

    ``prompt`` und ``herkunft`` haben **keinen** Vorgabewert: Beides ist eine
    Entscheidung, die der Aufrufer treffen muss.
    """

    prompt: str
    herkunft: "Herkunft | _OhneObjekt"

    #: json · json_array · prosa — bestimmt Parser, ``format=json`` und System-Prompt.
    antwortform: Literal["json", "json_array", "prosa"] = "prosa"
    #: Siehe :data:`_BUDGET_JE_AUFGABE`; steuert Budget und Audit-Kontext.
    aufgabe: str = "sonstiges"
    #: Mengengerüst (Objekte im Sammel-Prompt) — geht ins Budget ein.
    menge: int = 1

    system: str = ""                 # leer → Standard je Antwortform
    temperatur: float | None = None  # None → Standard je Antwortform
    budget: int | None = None        # None → budget_fuer(aufgabe, menge)
    num_ctx: int | None = None

    modul: str = "ai"
    projekt: str = ""

    #: ``normal`` | ``sensibel`` — aus der Einstufung folgt die Egress-Pflicht,
    #: statt sie je Route zu entscheiden.
    vertraulichkeit: str = "normal"
    #: ``server`` (Prompt serverseitig gebaut) | ``client`` (mitgeschickt).
    #: Beim Client-Prompt kann die Engine Nachweise, Säuberung und Objektbezug
    #: nicht beitragen — das ist die ehrliche Grenze und soll sichtbar sein.
    quelle: Literal["server", "client"] = "server"

    #: Ohne Bestätigung abweisen (428). Heute nur dort gesetzt, wo es schon
    #: galt — das Umlegen für alle ist #1836/E2.
    egress_pflicht: bool = False
    #: Eigene Hinweise des Bearbeiters zulassen (#1833).
    zusatz_erlaubt: bool = True

    #: Abbruch für lange Läufe (die Risikobewertung braucht es).
    cancel_event: Any = None

    #: Nur für Protokoll/Diagnose — nie Inhalte.
    kontext: str = ""

    lauf_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass
class KiErgebnis:
    """Was dabei herauskam — und was nicht ging."""

    ok: bool
    text: str = ""
    parsed: Any = None
    provider: str = ""
    tokens: int = 0
    dauer_s: float = 0.0
    abgeschnitten: bool = False
    fehler: str = ""
    lauf_id: str = ""
    #: Parameter, die der gewählte Provider **nicht** abbilden konnte. Ein
    #: Budget, das still verfällt, ist schlimmer als keines (#1836).
    nicht_abbildbar: list[str] = field(default_factory=list)


class KiNichtVerfuegbar(RuntimeError):
    """Kein KI-Provider nutzbar (→ HTTP 409). Kein stiller Rückfall."""


class EgressNichtBestaetigt(RuntimeError):
    """Übermittlung nicht bestätigt (→ HTTP 428, #1519)."""


# ── Die gemeinsame Vorbereitung ─────────────────────────────────────────────

def _system_prompt(a: KiAuftrag) -> str:
    if a.system.strip():
        return a.system
    return _SYSTEM_JSON if a.antwortform in ("json", "json_array") else _SYSTEM_PROSA


def _temperatur(a: KiAuftrag) -> float:
    if a.temperatur is not None:
        return float(a.temperatur)
    return _TEMP_JE_FORM.get(a.antwortform, 0.2)


def _budget(a: KiAuftrag) -> int:
    if a.budget is not None:
        return int(a.budget)
    return budget_fuer(a.aufgabe, a.menge)


def _nicht_abbildbar(a: KiAuftrag, *, streaming: bool) -> list[str]:
    """Welche Parameter der gewählte Weg nicht durchreichen kann.

    Das wird **gemeldet**, nicht verschwiegen: ``force_json`` gibt es nur im
    Ollama-Streaming-Zweig (``streaming.py``), und die synchrone
    Provider-Schnittstelle (``AITextRequest``) kennt es überhaupt nicht. Wer
    sich im Code auf ``format=json`` verlässt, soll es im Ergebnis sehen statt
    es zu glauben.
    """
    offen: list[str] = []
    if a.antwortform in ("json", "json_array") and _nur_per_prompt_json():
        offen.append("force_json")
    return offen


def _nur_per_prompt_json() -> bool:
    """Kann der eingestellte Provider ein JSON-Format **nicht** erzwingen?

    Seit #1841/E3 können es beide Wege: Ollama über ``format: json`` (synchron
    **und** streamend), OpenAI-kompatible Endpunkte über ``response_format``.
    Übrig bleibt **Anthropic** — dort gibt es keinen entsprechenden Modus (nur
    Tool-Use), und dann hängt die Struktur allein am Prompt. Das wird
    gemeldet, nicht verschwiegen: Wer sich im Code darauf verlässt, soll es im
    Ergebnis sehen statt es zu glauben.
    """
    try:
        from ai_compliance_suite.ai.dispatch import is_cloud_provider
        if not is_cloud_provider():
            return False
        from ai_compliance_suite.ai.dispatch import _load_ai_config
        cfg = (_load_ai_config() or {}).get("ai") or {}
        basis = str(((cfg.get("cloud") or {}).get("base_url")) or "").lower()
        return "anthropic.com" in basis
    except Exception:  # noqa: BLE001 — im Zweifel nichts behaupten
        return False


def _vorbereiten(a: KiAuftrag) -> str:
    """Schritte 1–3: Verfügbarkeit, Egress, eigene Hinweise. Liefert den Prompt."""
    # 1) Verfügbarkeit — eine Fehlermeldung ist besser als ein leerer Stream.
    from server.services.prefill import is_ai_available
    ok, grund = is_ai_available()
    if not ok:
        raise KiNichtVerfuegbar(grund or "KI-Provider nicht verfügbar.")

    # 2) Egress. Die Bestätigung kommt aus dem Request (das Frontend schickt
    #    `confirmed`); auditiert wird mit Akteur (#1784) — ohne `user_id`
    #    stünde im Revisionspfad „irgendwer hat gehandelt".
    bestaetigt = _egress_bestaetigt()
    if a.egress_pflicht and not bestaetigt:
        raise EgressNichtBestaetigt(
            "Bestätigung der Datenübermittlung erforderlich (confirmed=true).")
    if bestaetigt:
        _audit_egress(a)

    # 3) Eigene Hinweise des Bearbeiters (#1833). `komponiere` ist idempotent,
    #    deshalb schadet es nicht, wenn ein Aufrufer schon komponiert hat.
    prompt = a.prompt
    if a.zusatz_erlaubt:
        zusatz = _pz.aus_request()
        if zusatz:
            prompt = _pz.komponiere(prompt, zusatz)
            _pz.vermerke(zusatz, modul=a.modul or _pz.modul_aus_pfad(),
                         kontext=a.aufgabe or a.kontext)
    return prompt


def _egress_bestaetigt() -> bool:
    try:
        from flask import has_request_context, request
        if not has_request_context():
            return False
        body = request.get_json(silent=True)
        if isinstance(body, dict) and body.get("confirmed"):
            return True
        return bool(request.args.get("confirmed"))
    except Exception:  # noqa: BLE001
        return False


def _nutzer() -> str:
    try:
        from flask_jwt_extended import get_jwt_identity
        return str(get_jwt_identity() or "")
    except Exception:  # noqa: BLE001
        return ""


def _audit_egress(a: KiAuftrag) -> None:
    try:
        import hashlib

        from shared.audit import audit_event
        from ai_compliance_suite.ai.dispatch import current_provider_name
        audit_event("ai.egress.confirmed", module=a.modul or "ai", details={
            "user_id": _nutzer(),
            "lauf_id": a.lauf_id,
            "provider": current_provider_name(),
            "kontext": (a.kontext or a.aufgabe)[:200],
            "prompt_laenge": len(a.prompt),
            "prompt_sha256": hashlib.sha256(a.prompt.encode("utf-8")).hexdigest(),
        })
    except Exception:  # noqa: BLE001
        pass


def _audit_lauf(a: KiAuftrag, erg: KiErgebnis) -> None:
    """**Ein** Ereignis je fachlichem Lauf, mit Lauf-Kennung.

    Die Provider-Schicht protokolliert darunter ``ai.cloud.request`` bzw.
    ``ai.on_prem.{request,stream}``. Bisher war aus dem Revisionspfad nicht
    herstellbar, welcher fachliche Vorgang zu welchem Provider-Aufruf gehört —
    es fehlte die Klammer.
    """
    try:
        from shared.audit import audit_event
        herkunft = a.herkunft
        audit_event("ai.lauf", module=a.modul or "ai",
                    outcome="success" if erg.ok else "fail",
                    details={
                        "user_id": _nutzer(),
                        "lauf_id": a.lauf_id,
                        "aufgabe": a.aufgabe,
                        "antwortform": a.antwortform,
                        "projekt": a.projekt[:120],
                        "objekt_art": getattr(herkunft, "art", ""),
                        "objekt_id": str(getattr(herkunft, "objekt_id", "")),
                        "provider": erg.provider,
                        "quelle": a.quelle,
                        "budget": _budget(a),
                        "tokens": erg.tokens,
                        "abgeschnitten": erg.abgeschnitten,
                        "nicht_abbildbar": erg.nicht_abbildbar,
                        "fehler": erg.fehler[:200],
                    })
    except Exception:  # noqa: BLE001
        pass


def _vermerke_herkunft(a: KiAuftrag, provider: str) -> None:
    """Herkunftsvermerk (#1765) — best effort, aber **immer versucht**.

    Bisher entschied das jede Aufrufstelle für sich, und ≥ 36 Wege entschieden
    es gar nicht. Ein Fehler hier darf die eben erzeugte Antwort nicht
    verwerfen, deshalb best effort mit Protokoll.
    """
    h = a.herkunft
    if not isinstance(h, Herkunft):
        return
    try:
        from shared.ki_herkunft import vermerken
        vermerken(a.modul, a.projekt, h.art, str(h.objekt_id), provider=provider)
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger("aics.ki").warning(
            "KI-Herkunft nicht vermerkt (%s/%s/%s)", a.modul, a.projekt, h.objekt_id,
            exc_info=True)


def _parse(a: KiAuftrag, text: str) -> Any:
    """Parser je Antwortform — nicht je Modul."""
    if a.antwortform == "json":
        from server.services.anforderung_prompt import parse_chatgpt_json
        return parse_chatgpt_json(text)
    if a.antwortform == "json_array":
        from server.services.anforderung_prompt import parse_mass_response
        return parse_mass_response(text)
    return text


# ── Betriebsart 1: synchron ─────────────────────────────────────────────────

def ki_lauf(a: KiAuftrag) -> KiErgebnis:
    """Eine KI-Anfrage, blockierend. Für Diagnose und kurze Aufgaben.

    Raises:
      KiNichtVerfuegbar: kein Provider (→ 409).
      EgressNichtBestaetigt: Übermittlung nicht bestätigt (→ 428).
    """
    prompt = _vorbereiten(a)
    offen = _nicht_abbildbar(a, streaming=False)
    begonnen = time.monotonic()

    from ai_compliance_suite.ai.dispatch import current_provider_name, generate_text
    try:
        resp = generate_text(system=_system_prompt(a), prompt=prompt,
                             temperature=_temperatur(a), max_output_tokens=_budget(a),
                             force_json=a.antwortform in ("json", "json_array"))
    except Exception as e:  # noqa: BLE001 — Provider, Netz, Egress
        erg = KiErgebnis(ok=False, fehler=f"KI-Aufruf fehlgeschlagen: {e}",
                         lauf_id=a.lauf_id, nicht_abbildbar=offen,
                         dauer_s=round(time.monotonic() - begonnen, 1))
        _audit_lauf(a, erg)
        return erg

    text = getattr(resp, "text", "") or ""
    provider = current_provider_name()
    erg = KiErgebnis(ok=True, text=text, provider=provider, lauf_id=a.lauf_id,
                     nicht_abbildbar=offen,
                     dauer_s=round(time.monotonic() - begonnen, 1))
    try:
        erg.parsed = _parse(a, text)
    except Exception as e:  # noqa: BLE001
        erg.ok = False
        erg.fehler = f"KI-Antwort nicht verwertbar: {e}"
        _audit_lauf(a, erg)
        return erg

    _vermerke_herkunft(a, provider)
    _audit_lauf(a, erg)
    return erg


# ── Betriebsart 2: Live (SSE) ───────────────────────────────────────────────

def ki_ereignisse(a: KiAuftrag) -> Iterable[dict]:
    """Roher Ereignisstrom (``chunk``/``stats``/``done``/``error``).

    Für Aufrufer mit **eigener** Ereignisform — die Risikobewertung hat eine.
    Sie bekommen damit Vorbereitung, Budget und Abbruch der Engine, ohne ihre
    Oberfläche anfassen zu müssen.
    """
    prompt = _vorbereiten(a)
    from ai_compliance_suite.ai.streaming import stream_generate
    zusatz: dict[str, Any] = {}
    if a.num_ctx:
        zusatz["num_ctx"] = a.num_ctx
    for ev in stream_generate(_system_prompt(a), prompt, temperature=_temperatur(a),
                              num_predict=_budget(a),
                              force_json=a.antwortform in ("json", "json_array"),
                              **zusatz):
        if a.cancel_event is not None and a.cancel_event.is_set():
            return
        yield ev


def ki_lauf_sse(a: KiAuftrag, *, finalize: Callable[[str], dict] | None = None):
    """Eine KI-Anfrage als Flask-SSE-Response (Live-Ansicht im Browser).

    Ereignisse: ``phase`` · ``chunk`` {text} · ``progress`` {tokens, elapsed_s,
    t_per_s} · ``done`` {ok, …}. ``finalize(volltext) -> dict`` parst und
    speichert am Ende; sein Ergebnis wird ins ``done`` gemischt.
    """
    import json

    from flask import Response, stream_with_context

    offen = _nicht_abbildbar(a, streaming=True)

    @stream_with_context
    def _gen():
        def _ev(name: str, daten: dict) -> str:
            return (f"event: {name}\ndata: "
                    f"{json.dumps(daten, ensure_ascii=False, default=str)}\n\n")

        stuecke: list[str] = []
        provider = ""
        schluss: dict[str, Any] = {}
        begonnen = time.monotonic()
        try:
            yield _ev("phase", {"phase": "connect", "message": "Verbinde mit KI …"})
            for ev in ki_ereignisse(a):
                art = ev.get("kind")
                if art == "chunk":
                    stuecke.append(ev["text"])
                    yield _ev("chunk", {"text": ev["text"]})
                elif art == "stats":
                    yield _ev("progress", {"tokens": ev.get("tokens", 0),
                                           "elapsed_s": ev.get("elapsed_s", 0),
                                           "t_per_s": ev.get("t_per_s", 0)})
                elif art == "done":
                    provider = ev.get("provider", "")
                    schluss = ev
                elif art == "error":
                    erg = KiErgebnis(ok=False, fehler=str(ev.get("error", "KI-Fehler")),
                                     provider=ev.get("provider", ""), lauf_id=a.lauf_id,
                                     nicht_abbildbar=offen)
                    _audit_lauf(a, erg)
                    yield _ev("done", {"ok": False, "error": erg.fehler,
                                       "provider": erg.provider, "lauf_id": a.lauf_id})
                    return

            voll = "".join(stuecke)
            dauer = round(time.monotonic() - begonnen, 1)

            if schluss.get("truncated"):
                # #1588: am Budget abgeschnitten → klar melden statt
                # „Antwort nicht verwertbar" (unvollständiges JSON).
                grenze = schluss.get("num_predict") or _budget(a)
                erg = KiErgebnis(ok=False, text=voll, provider=provider, dauer_s=dauer,
                                 abgeschnitten=True, lauf_id=a.lauf_id,
                                 nicht_abbildbar=offen,
                                 fehler=(f"Die KI-Antwort wurde am Ausgabelimit "
                                         f"({grenze} Tokens) abgeschnitten und ist "
                                         "unvollständig. Bitte weniger Einträge auf "
                                         "einmal bewerten oder das Limit "
                                         "(ai.max_output_tokens) erhöhen."))
                _audit_lauf(a, erg)
                yield _ev("done", {"ok": False, "truncated": True, "provider": provider,
                                   "text": voll, "error": erg.fehler,
                                   "lauf_id": a.lauf_id})
                return

            nutzlast: dict[str, Any] = {
                "ok": True, "provider": provider, "lauf_id": a.lauf_id,
                "tokens": schluss.get("total_tokens", 0),
                "elapsed_s": schluss.get("elapsed_s", 0),
            }
            if offen:
                nutzlast["nicht_abbildbar"] = offen
            erg = KiErgebnis(ok=True, text=voll, provider=provider, dauer_s=dauer,
                             tokens=int(schluss.get("total_tokens", 0) or 0),
                             lauf_id=a.lauf_id, nicht_abbildbar=offen)

            if finalize is not None:
                try:
                    nutzlast.update(finalize(voll) or {})
                except Exception as e:  # noqa: BLE001
                    erg.ok = False
                    erg.fehler = f"Antwort nicht verwertbar: {e}"
                    _audit_lauf(a, erg)
                    yield _ev("done", {"ok": False, "error": erg.fehler,
                                       "raw_preview": voll[:400], "lauf_id": a.lauf_id})
                    return
            else:
                nutzlast["text"] = voll

            _vermerke_herkunft(a, provider)
            _audit_lauf(a, erg)
            yield _ev("done", nutzlast)
        except (KiNichtVerfuegbar, EgressNichtBestaetigt) as e:
            # Diese beiden gehören eigentlich vor den Stream (409/428). Kommen
            # sie hier an, hat ein Aufrufer die Prüfung nicht vorgezogen — dann
            # ist eine klare Meldung im Stream besser als ein Abbruch.
            yield _ev("done", {"ok": False, "error": str(e), "lauf_id": a.lauf_id})
        except Exception as e:  # noqa: BLE001
            erg = KiErgebnis(ok=False, fehler=f"{type(e).__name__}: {e}",
                             lauf_id=a.lauf_id)
            _audit_lauf(a, erg)
            yield _ev("done", {"ok": False, "error": erg.fehler, "lauf_id": a.lauf_id})

    return Response(_gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


__all__ = [
    "ANTWORTFORMEN",
    "EgressNichtBestaetigt",
    "Herkunft",
    "KiAuftrag",
    "KiErgebnis",
    "KiNichtVerfuegbar",
    "OHNE_OBJEKT",
    "budget_fuer",
    "ki_ereignisse",
    "ki_lauf",
    "ki_lauf_sse",
]
