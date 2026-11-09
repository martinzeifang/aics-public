"""Eigene Hinweise des Bearbeiters an einen KI-Prompt anhängen (#1833).

Jeder KI-Prompt der Suite war bis v8.1.1 fertig: Der Server baut ihn, der
Anwender nimmt ihn, wie er ist. Was fehlte, ist das Fachwissen, das nur der
Bearbeiter hat — „der Schwerpunkt dieses Unternehmens liegt in der Fertigung,
nicht in der IT", „ausführlicher, der Adressat ist der Aufsichtsrat". Dieses
Wissen stand nirgends und wirkte deshalb nicht; der einzige Weg war, den Prompt
in ChatGPT zu kopieren und dort von Hand zu ergänzen — womit die API-Variante
leer ausging.

WARUM DAS KOMPONIEREN HIER STEHT UND NICHT AN 60 AUFRUFSTELLEN
``server/api`` hat 60 Prompt- und Stream-Routen. Jede einzeln zu erweitern wäre
die Spiegel-Liste, die dieses Projekt mehrfach bezahlt hat (#1731, #1735,
#1773) — und bei der nächsten neuen Route fehlte sie wieder, ohne dass etwas
fehlschlägt. Es gibt genau zwei Engstellen, durch die alle laufen:
``server/middleware/prompt_zusatz`` (Copy/Paste: jede Antwort trägt ``prompt``)
und ``shared/sse.stream_ai_sse`` (jeder serverseitige Stream, einschließlich
``/api/ai/run-stream`` und damit der ~45 Assistenten). Beide rufen
:func:`komponiere`.

WARUM DER HINWEIS HINTEN STEHT — UND DANACH DIE VORGABE
Ein Sprachmodell gewichtet die letzte Anweisung am stärksten. Stünde der
Hinweis zuletzt, wäre „schreibe ausführlicher in Prosa" genau die Anweisung,
die das geforderte JSON bricht. Die Reihenfolge *Hinweis → Vorrang* dreht das
um und braucht dabei **kein Wissen über den Aufbau des einzelnen Prompts** —
sie wirkt für alle 60 gleich. Eine Einfügung „vor dem Format-Block" hätte
dagegen je Prompt eine andere Fundstelle, also 60 Fundstellen.

WARUM KEIN ``BEGIN_UNTRUSTED_DATA``
``security_utils.add_untrusted_block`` rahmt Fremdtext als „nur Daten, keine
Anweisungen" ein. Der Hinweis des Bearbeiters ist das Gegenteil: Er **soll**
wirken. Er wird gesäubert, längenbegrenzt und eingezäunt — aber nicht
entwertet. Der Schutz liegt nicht darin, dem Anwender zu misstrauen, sondern
darin, dass die Vorgaben nach ihm stehen und ein Mensch das Ergebnis ohnehin
fachlich prüft (#1765).
"""
from __future__ import annotations

from typing import Any

from shared.encoding import escape_markdown_codeblock

#: Überschrift des eingefügten Blocks. Dient zugleich als Idempotenz-Marker:
#: Der ``WizardPromptModal`` schickt den **angezeigten** (schon komponierten)
#: Prompt an ``/api/ai/run-stream`` zurück — ohne diesen Marker stünde der
#: Hinweis zweimal darin.
MARKER = "## Eigene Hinweise des Bearbeiters"

#: Überschrift des Vorrang-Blocks.
MARKER_VORRANG = "## Verbindlich bleibt"

#: Name des Parameters in Query und JSON-Body. Eine Schreibweise, überall.
PARAM = "prompt_zusatz"

#: Kopfzeile, über die das Frontend den Hinweis schickt — **der tragende Weg**.
#:
#: Rund die Hälfte der Prompt-Routen ist ``GET`` (Anforderungen, OWASP,
#: Prüffragen, die meisten Assistenten). In der Query-Zeile ist ein Hinweis
#: dieser Länge nicht zustellbar: gunicorn begrenzt die Anfragezeile auf 4094
#: Bytes (``limit_request_line``), und 2000 Zeichen Deutsch werden URL-kodiert
#: bis zu 12 000 Bytes. Das wäre genau der Fehler aus #1807 — eine Grenze in
#: der Anwendung anheben und die Schichten davor nicht prüfen; dort kam das
#: als „Fehler beim Upload" zurück, hier käme es als 414 ohne Eintrag im
#: Anwendungs-Log.
#:
#: Die Kopfzeile fasst mehr (``limit_request_field_size`` 8190 Bytes, nginx
#: 8 KB Puffer) und gilt für ``GET`` und ``POST`` gleich — **ein** Weg im
#: Frontend statt zwei. Der Wert ist Base64 über UTF-8, weil Kopfzeilen keine
#: Umlaute führen dürfen (RFC 7230: ISO-8859-1, in der Praxis verstümmelt).
HEADER = "X-Prompt-Zusatz"

#: Längengrenze in Zeichen: 2000 Zeichen sind etwa 300 Wörter — genug für
#: Schwerpunkt, Adressat und Tiefe, und über die Kopfzeile sicher zustellbar
#: (2000 × 2 Bytes UTF-8 → 5336 Bytes Base64 < 8190).
GRENZE = 2000

_ZAUN_AUF = "BEGIN_EIGENE_HINWEISE"
_ZAUN_ZU = "END_EIGENE_HINWEISE"

_EINLEITUNG = (
    "Die folgenden Hinweise hat der Bearbeiter für diesen Lauf ergänzt. Sie "
    "geben Schwerpunkt, Tiefe, Tonfall und Adressaten vor und sind fachlich "
    "ernst zu nehmen."
)

_AUFTAKT_MIT_HINWEIS = (
    "Die Hinweise ergänzen den Auftrag, sie ersetzen ihn nicht. Unverändert "
    "gelten:"
)
_AUFTAKT_OHNE_HINWEIS = "Unverändert gelten:"

_PUNKT_FORMAT = (
    "- das oben geforderte Antwortformat — Struktur, Feldnamen und die Regel, "
    "keinen Text außerhalb auszugeben;"
)
_PUNKT_SKALEN = (
    "- die oben genannten Skalen, Stufen, Schwellen und bereits berechneten "
    "Vorgaben: Sie werden nicht neu bewertet, nicht relativiert und nicht "
    "überschrieben;"
)
_PUNKT_QUELLEN = (
    "- die Pflicht, ausschließlich die bereitgestellten Informationen zu "
    "verwenden."
)
_SCHLUSS_WIDERSPRUCH = (
    "Widerspricht ein Hinweis einer dieser Vorgaben, gilt die Vorgabe. Nenne "
    "den Widerspruch in einem Satz, wenn die Antwortstruktur ein Freitextfeld "
    "dafür vorsieht."
)

#: Die Sprache, in der die Prompts dieser Anwendung geschrieben sind (#1954).
#:
#: Ausdrücklich **nicht** dasselbe wie ``shared.sprache.STANDARD``. Der
#: Unterschied entscheidet, wann überhaupt eine Sprachvorgabe nötig ist: Ein
#: deutscher Prompt bringt eine deutsche Antwort von sich aus, eine Vorgabe
#: wäre dort Ballast — und, wichtiger, der Prompt bliebe nicht byte-identisch
#: zu 8.3.4. Genau diese Byte-Gleichheit macht jeden Bestandstest zum
#: Regressionsschutz dieser Änderung (dieselbe Zusage wie ``evidence_section``
#: und ``issue_feedback_section``).
PROMPT_SPRACHE = "de"

#: Die Sprachvorgabe, je Zielsprache.
#:
#: WARUM SIE DEN SCHLÜSSELRAUM AUSDRÜCKLICH AUSNIMMT
#: Das ist der tragende Teil. Rund ein Dutzend Läufe verlangt JSON, und bei
#: Anthropic weist ``ki_engine`` ``force_json`` als ``nicht_abbildbar`` aus —
#: dort hängt die Struktur **allein am Prompt**. Eine unachtsame Anweisung
#: „antworte auf Englisch" lässt ein Modell auch die Feldnamen übersetzen, und
#: dann scheitert der Parser an einer Antwort, die inhaltlich richtig ist. Das
#: ist dieselbe Falle, die #1832 schon einmal gestellt hat; die Lösung ist
#: dieselbe: Die Vorgabe sagt im selben Atemzug, was sie **nicht** betrifft.
#:
#: Die Anweisung steht zweisprachig, mit dem Zielsprachensatz in Klammern. Für
#: ein Sprachmodell ist eine Anweisung in der Zielsprache das deutlichste
#: Signal, und die deutsche Fassung hält den Block für einen menschlichen Leser
#: des angezeigten Prompts verständlich — er wird in der Maske gezeigt.
_PUNKT_SPRACHE: dict[str, str] = {
    "en": (
        "- die Antwortsprache ist **Englisch** (write the complete answer in "
        "English). Das gilt für Fließtext, Begründungen, Überschriften und "
        "Aufzählungen. **Unverändert** bleiben dagegen: Feldnamen und "
        "Schlüssel der Antwortstruktur, vorgegebene Auswahlwerte (Status-, "
        "Stufen- und Kategoriewerte wie `erfuellt` oder `nicht_relevant`), "
        "Eigennamen, Produkt- und Normbezeichnungen sowie Fundstellen — auch "
        "dann, wenn sie deutsch sind. Übersetze keinen Schlüssel."
    ),
    "de": (
        "- die Antwortsprache ist **Deutsch**. Das gilt für Fließtext, "
        "Begründungen, Überschriften und Aufzählungen. **Unverändert** "
        "bleiben dagegen: Feldnamen und Schlüssel der Antwortstruktur, "
        "vorgegebene Auswahlwerte, Eigennamen, Produkt- und "
        "Normbezeichnungen sowie Fundstellen. Übersetze keinen Schlüssel."
    ),
}


def _vorrang_text(*, mit_hinweis: bool, sprache: str) -> str:
    """Baut den Vorrang-Block.

    ``mit_hinweis=True, sprache=""`` ergibt **byte-genau** den Text von 8.3.4 —
    ``tests/test_sprache_ki_1954.py`` nagelt das fest.
    """
    zeilen = [_AUFTAKT_MIT_HINWEIS if mit_hinweis else _AUFTAKT_OHNE_HINWEIS]
    zeilen += [_PUNKT_FORMAT, _PUNKT_SKALEN, _PUNKT_QUELLEN]
    if sprache:
        zeilen.append(_PUNKT_SPRACHE[sprache])
    if mit_hinweis:
        zeilen.append(_SCHLUSS_WIDERSPRUCH)
    return "\n".join(zeilen)


#: Der Vorrang-Block, wie er bis 8.3.4 aussah. Bleibt als Konstante, weil
#: Bestandstests ihn lesen.
_VORRANG = _vorrang_text(mit_hinweis=True, sprache="")


def saeubere(text: Any) -> str:
    """Säubert einen Hinweis und begrenzt ihn auf :data:`GRENZE` Zeichen.

    Entfernt NUL und Steuerzeichen, vereinheitlicht Zeilenenden und entschärft
    Codefences (``escape_markdown_codeblock``), damit der Text die Einzäunung
    nicht aufbricht und von dort aus einen eigenen ``## Format``-Abschnitt
    vortäuschen kann.

    Gekürzt wird **sichtbar**, nie still — Muster ``_cap`` in
    ``server/services/anforderung_prompt.py``: Ein Anwender, der 3000 Zeichen
    hineinschreibt, soll im Prompt-Fenster sehen, dass die Hälfte fehlt.
    """
    s = str(text or "")
    s = s.replace("\x00", "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = "".join(ch for ch in s if ch in ("\n", "\t") or ord(ch) >= 32)
    s = s.strip()
    if len(s) > GRENZE:
        gekuerzt = len(s) - GRENZE
        s = (s[:GRENZE].rstrip()
             + f"\n[… {gekuerzt} Zeichen gekürzt — die Grenze liegt bei "
               f"{GRENZE} Zeichen]")
    # Erst nach der Längenprüfung escapen: Das Escape verlängert den Text und
    # würde die Grenze sonst unbemerkt verschieben.
    return escape_markdown_codeblock(s)


def ist_komponiert(prompt: Any) -> bool:
    """Trägt der Prompt schon einen angehängten Block?

    Geprüft werden **beide** Überschriften. Bis 8.3.4 genügte der
    Hinweis-Marker, weil ohne Hinweis nie etwas angehängt wurde. Seit #1954
    kann auch eine Sprachvorgabe allein einen Vorrang-Block erzeugen — stünde
    sie nicht in dieser Prüfung, hängte der Rückweg des ``WizardPromptModal``
    (es schickt den **angezeigten**, schon komponierten Prompt an
    ``/api/ai/run-stream`` zurück) sie ein zweites Mal an.
    """
    text = str(prompt or "")
    return MARKER in text or MARKER_VORRANG in text


def komponiere(prompt: Any, zusatz: Any, *, sprache: Any = "") -> str:
    """Hängt Hinweis-Block, Sprachvorgabe und Vorrang-Block an ``prompt``.

    Ohne Hinweis **und** ohne abweichende Sprache ist das Ergebnis
    byte-identisch zu ``prompt``. Das ist die Rückwärtskompatibilität, auf die
    sich ``evidence_section`` und ``issue_feedback_section`` schon stützen —
    und sie macht jeden Bestandstest zum Regressionstest dieser Änderung.

    ``sprache`` ist die **Inhaltssprache des Mandanten** (``firmen.sprache``,
    aufgelöst über ``shared/sprache.py``), nicht die Menüsprache des
    Bearbeiters. Sie landet im Vorrang-Block und damit **hinter** dem Hinweis:
    Ein Bearbeiter, der „antworte auf Englisch" schreibt, während der Mandant
    auf Deutsch steht, bekommt Deutsch — die Akte gehört dem Mandanten. Die
    Reihenfolge ist derselbe Mechanismus wie in #1832 und braucht wieder kein
    Wissen über den Aufbau des einzelnen Prompts.

    Stimmt die Zielsprache mit ``PROMPT_SPRACHE`` überein, wird **keine**
    Vorgabe gesetzt: Ein deutscher Prompt bringt eine deutsche Antwort von
    selbst, und der Prompt bleibt byte-identisch.

    Idempotent: Trägt ``prompt`` schon einen der Marker, wird nichts angehängt.
    """
    basis = str(prompt or "")
    sauber = saeubere(zusatz)

    from shared import sprache as _sp

    ziel = _sp.normalisiere(sprache)
    sprach_vorgabe = ziel if ziel and ziel != PROMPT_SPRACHE else ""

    if not sauber and not sprach_vorgabe:
        return basis
    if ist_komponiert(basis):
        return basis

    hinweis_block = ""
    if sauber:
        hinweis_block = (
            f"{MARKER}\n"
            f"{_EINLEITUNG}\n"
            "```text\n"
            f"{_ZAUN_AUF}\n"
            f"{sauber}\n"
            f"{_ZAUN_ZU}\n"
            "```\n\n"
        )
    vorrang = _vorrang_text(mit_hinweis=bool(sauber), sprache=sprach_vorgabe)
    return (
        f"{basis.rstrip()}\n\n"
        f"{hinweis_block}"
        f"{MARKER_VORRANG}\n"
        f"{vorrang}\n"
    )


def aus_request() -> str:
    """Liest den Hinweis aus dem laufenden Request.

    Drei Quellen, in dieser Reihenfolge: :data:`HEADER` (Base64 — der Weg des
    Frontends, für ``GET`` und ``POST`` gleich), JSON-Body und Query. Die
    beiden letzten bleiben für Aufrufe von Hand (curl, Tests) und für kurze
    Hinweise; **lang dürfen sie nicht werden** — siehe :data:`HEADER`.

    Ohne Request-Kontext und bei jedem Lesefehler: leerer String. Ein Hinweis,
    der sich nicht lesen lässt, darf keinen KI-Lauf zerreißen.
    """
    try:
        from flask import has_request_context, request
        if not has_request_context():
            return ""
        wert = _aus_header(request.headers.get(HEADER))
        if not wert:
            body = request.get_json(silent=True)
            if isinstance(body, dict):
                wert = body.get(PARAM)
        if not wert:
            wert = request.args.get(PARAM)
        return saeubere(wert)
    except Exception:  # noqa: BLE001 — nie den Lauf wegen eines Hinweises aufgeben
        return ""


def _aus_header(roh: Any) -> str:
    """Dekodiert den Base64-Kopfzeilenwert.

    Ein unlesbarer Wert ergibt einen leeren Hinweis, nicht Buchstabensalat im
    Prompt: Base64-Müll im Auftrag an die KI wäre schlimmer als ein fehlender
    Hinweis, weil er wie eine Anweisung aussieht.
    """
    s = str(roh or "").strip()
    if not s:
        return ""
    try:
        import base64
        fehlend = (-len(s)) % 4  # Padding, das ein Client weggelassen hat
        return base64.b64decode(s + "=" * fehlend, validate=True).decode("utf-8")
    except Exception:  # noqa: BLE001
        return ""


def modul_aus_pfad() -> str:
    """Modulschlüssel des laufenden Requests für den Revisionseintrag."""
    try:
        from flask import has_request_context, request
        if not has_request_context():
            return "ai"
        from shared.licensing.modules import module_for_path
        return module_for_path(request.path) or "ai"
    except Exception:  # noqa: BLE001
        return "ai"


def vermerke(zusatz: Any, *, modul: str = "ai", kontext: str = "") -> None:
    """Schreibt die Verwendung eines Hinweises in den Revisionspfad.

    Gerufen aus :func:`shared.sse.stream_ai_sse`, also dort, wo der Hinweis
    tatsächlich an einen Provider geht. Ein gespeicherter oder eingetippter
    Hinweis steuert eine KI-Bewertung, die anschließend in der Akte landet —
    wer so gesteuert hat, muss nachvollziehbar sein.

    **Je Request einmal.** ``/api/ai/run-stream`` komponiert selbst (damit der
    dort protokollierte Prompt-Hash den gesendeten Text abbildet) und ruft
    anschließend ``stream_ai_sse``, das es ebenfalls versucht. Die Sperre über
    ``flask.g`` macht die Reihenfolge gleichgültig — besser als ein Schalter,
    der durch drei Signaturen gereicht wird.

    ``user_id`` wird ausdrücklich mitgegeben: ``shared.audit.audit_event``
    liest den Akteur aus ``details['user_id']`` und schreibt sonst „irgendwer
    hat gehandelt" (#1784).

    **Bewusste Grenze:** Der Copy/Paste-Weg wird nicht vermerkt. Dort verlässt
    der Prompt die Anwendung über die Zwischenablage des Anwenders — das ist
    heute schon so und wird hierdurch nicht schlechter.
    """
    sauber = saeubere(zusatz)
    if not sauber:
        return
    try:
        from flask import g, has_request_context
        if has_request_context():
            if getattr(g, "_prompt_zusatz_vermerkt", False):
                return
            g._prompt_zusatz_vermerkt = True
    except Exception:  # noqa: BLE001
        pass
    try:
        import hashlib

        from shared.audit import audit_event

        nutzer = ""
        try:
            from flask_jwt_extended import get_jwt_identity
            nutzer = str(get_jwt_identity() or "")
        except Exception:  # noqa: BLE001
            nutzer = ""
        audit_event(
            "ai.prompt.zusatz",
            module=str(modul or "ai"),
            details={
                "user_id": nutzer,
                "kontext": str(kontext or "")[:200],
                "laenge": len(sauber),
                "sha256": hashlib.sha256(sauber.encode("utf-8")).hexdigest(),
                "text": sauber[:500],
            },
        )
    except Exception:  # noqa: BLE001
        try:
            from flask import current_app
            current_app.logger.warning("Audit ai.prompt.zusatz fehlgeschlagen",
                                       exc_info=True)
        except Exception:  # noqa: BLE001
            pass
