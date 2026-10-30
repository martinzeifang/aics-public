"""Die Hilfe fragbar machen (#1878) — geerdet auf Handbuch und Anwendungsstand.

WUNSCH AUS DEM BETRIEB
„Ich will überall, wo Hilfe steht, die Möglichkeit, wie in einem LLM-Chat die
KI fragen zu können, was mein Problem ist. Bei der Lösung soll immer die API
verwendet werden und das Handbuch und die Infos herangezogen werden, sodass
die Lösung möglichst gut ist."

Die Hilfe war ein Nachschlagewerk: `ModuleHelpDialog` zeigt
`frontend/src/help/<modul>.ts`. Der Bestand ist gut strukturiert und
umfangreich — wer aber nicht weiß, wonach er suchen soll, findet nichts.

WORAUF DIE ANTWORT STEHT
1. **Das Handbuch** (`docs/modules/*.md`). Dieselbe Quelle, aus der auch die
   öffentliche Doku-Site und das Wiki entstehen — also keine zweite Wahrheit.
   Die Dateien liegen seit #1878 im Image; vorher kopierte das Dockerfile
   `docs/` nicht, der Server konnte sie also gar nicht lesen.
2. **Die In-App-Hilfe** des gerade offenen Bereichs. Sie liegt im
   Frontend-Bundle, nicht serverseitig — der Client schickt den Abschnitt mit,
   den der Anwender offen hat. Sie hier ein zweites Mal zu führen wäre die
   Spiegel-Liste aus #1731/#1735.
3. **Der Stand der Anwendung** (Modul, Projekt, Tab), damit „warum ist mein
   Release rot?" beantwortbar wird und nicht allgemein bleibt.

WAS DIESES MODUL BEWUSST NICHT TUT
Es ruft die KI nicht selbst. Es baut nur den Prompt; ausgeführt wird über
`shared.ki_engine` (#1841), damit Verfügbarkeitsprüfung, Egress-Bestätigung
samt Revisionseintrag (#1519/#1840), die eigenen Hinweise des Bearbeiters
(#1832) und das Budget nach Aufgabenart automatisch gelten. Ein eigener
Transport wäre der sechste (#1841).

Und es beantwortet **Bedienfragen**. Rechtsfragen beantwortet es nicht —
derselbe Vorbehalt, der in den Softwarebestimmungen steht.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

#: Die Modul-Dokumentation im Image. Ein eigener Pfad statt eines Imports aus
#: dem Doku-Generator: Das Handbuch ist Inhalt, kein Code.
DOKU_VERZEICHNIS = Path(__file__).resolve().parent.parent / "docs" / "modules"

#: Modulschlüssel → Datei. Die Namen weichen an zwei Stellen ab (`aiact` heißt
#: in der Doku `ai-act`, `compliance_audit` trägt einen Bindestrich); eine
#: Ableitung aus dem Schlüssel bräche genau dort — dieselbe Falle wie
#: `owasp_llm` gegen `owasp-llm` in #1846.
MODUL_DATEI: dict[str, str] = {
    "cra": "cra.md",
    "nis2": "nis2.md",
    "aiact": "ai-act.md",
    "ai_act": "ai-act.md",
    "dsgvo": "dsgvo.md",
    "wiba": "wiba.md",
    "risikobewertung": "risikobewertung.md",
    "firmen": "firmen.md",
    "gutachten": "gutachten.md",
    "soc": "soc.md",
    "compliance_audit": "compliance-audit.md",
    "compliance": "compliance.md",
    "compliance_db": "compliance-db.md",
    "baso": "baso.md",
    "ict": "ict.md",
}

#: Obergrenzen. Der Prompt darf nicht beliebig wachsen: Ein Modell, dem man
#: das halbe Handbuch vorlegt, antwortet schlechter, nicht besser — und das
#: Budget aus #1841 schneidet sonst mitten im Material ab.
MAX_ABSCHNITTE = 6
MAX_ZEICHEN_HANDBUCH = 12000
MAX_ZEICHEN_HILFE = 4000
MAX_FRAGE = 1000


def _abschnitte(text: str) -> list[tuple[str, str]]:
    """Markdown an seinen Überschriften teilen — (Überschrift, Inhalt).

    Keine zweite Zerlegungsmechanik: Überschriften sind die Gliederung, die
    der Autor selbst gewählt hat. Ein Zeichen-Fenster zu schneiden träfe
    mitten in Tabellen und Codeblöcke.
    """
    teile: list[tuple[str, str]] = []
    aktuell_titel, puffer = "", []
    for zeile in text.splitlines():
        if re.match(r"^#{1,4}\s+\S", zeile):
            if puffer:
                teile.append((aktuell_titel, "\n".join(puffer).strip()))
            aktuell_titel = zeile.lstrip("#").strip()
            puffer = []
        else:
            puffer.append(zeile)
    if puffer:
        teile.append((aktuell_titel, "\n".join(puffer).strip()))
    return [(t, i) for t, i in teile if i]


#: Die modulunabhängige Bedienanleitung. Sie wird **immer** mitgelesen, weil
#: hier Bedienfragen gestellt werden und die häufigsten davon nicht modul-
#: spezifisch sind („wo finde ich die Massenbewertung?", „was heißt
#: ⚠️ Neubewertung erforderlich?"). Sie steht hinter der Modul-Doku: Ist eine
#: Frage modulspezifisch, soll die genauere Quelle vorn stehen.
ALLGEMEIN_DATEI = "bedienung.md"


def _lies(datei: str) -> list[tuple[str, str]]:
    try:
        return _abschnitte((DOKU_VERZEICHNIS / datei).read_text(encoding="utf-8"))
    except OSError:
        # Eine fehlende Doku darf die Hilfe nicht abstürzen lassen — sie
        # antwortet dann aus der In-App-Hilfe allein.
        return []


def handbuch(modul: str) -> list[tuple[str, str]]:
    """Die Abschnitte der Modul-Doku plus die allgemeine Bedienanleitung.

    Ohne Modul (oder bei unbekanntem Modul) bleibt die Bedienanleitung — eine
    Bedienfrage ist auch dann beantwortbar.
    """
    datei = MODUL_DATEI.get(str(modul or "").strip().lower())
    return (_lies(datei) if datei else []) + _lies(ALLGEMEIN_DATEI)


def _woerter(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zä-ü0-9]{4,}", (text or "").lower())}


def passende_abschnitte(frage: str, abschnitte: list[tuple[str, str]],
                        *, hoechstens: int = MAX_ABSCHNITTE) -> list[tuple[str, str]]:
    """Die Abschnitte, die zur Frage passen — nach Wortüberdeckung.

    Bewusst einfach und ohne Index: Bei 16 Dateien mit zusammen 139 kB ist
    jede Trefferliste in Millisekunden da. Ein Vektorindex wäre ein zweiter
    Datenbestand, der mit dem Handbuch auseinanderlaufen kann.

    Die Überschrift zählt doppelt — sie benennt das Thema, der Fließtext
    streift es nur.
    """
    fw = _woerter(frage)
    if not fw:
        return abschnitte[:hoechstens]
    bewertet = []
    for titel, inhalt in abschnitte:
        punkte = 2 * len(fw & _woerter(titel)) + len(fw & _woerter(inhalt))
        if punkte:
            bewertet.append((punkte, titel, inhalt))
    bewertet.sort(key=lambda t: t[0], reverse=True)
    treffer = [(t, i) for _p, t, i in bewertet[:hoechstens]]
    # Ohne jeden Treffer lieber den Anfang der Doku als gar nichts: Dort steht
    # Zweck und Einstieg, und eine Antwort „dazu finde ich nichts" ist auch
    # eine Antwort, die das Modell geben können muss.
    return treffer or abschnitte[:2]


def _gekuerzt(text: str, grenze: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= grenze else text[:grenze].rstrip() + "\n…(gekürzt)"


def baue_prompt(frage: str, *, modul: str = "", bereich: str = "",
                hilfe_text: str = "", stand: dict[str, Any] | None = None,
                ) -> tuple[str, list[str]]:
    """Den Hilfe-Prompt bauen. Liefert (prompt, fundstellen).

    ``fundstellen`` sind die Überschriften, die eingeflossen sind — sie werden
    in der Oberfläche ausgewiesen. Eine Antwort, deren Grundlage man nicht
    nachsehen kann, ist in diesem Werkzeug wenig wert.
    """
    frage = _gekuerzt(frage, MAX_FRAGE)
    teile = passende_abschnitte(frage, handbuch(modul))
    fundstellen = [t for t, _ in teile if t]

    hb, rest = [], MAX_ZEICHEN_HANDBUCH
    for titel, inhalt in teile:
        stueck = f"### {titel}\n{inhalt}" if titel else inhalt
        stueck = _gekuerzt(stueck, max(rest, 0))
        if not stueck:
            break
        hb.append(stueck)
        rest -= len(stueck)
    handbuch_block = "\n\n".join(hb) or "(keine Handbuch-Abschnitte gefunden)"

    stand = stand or {}
    stand_zeilen = [f"- {k}: {v}" for k, v in stand.items()
                    if v not in (None, "", [], {})]
    stand_block = "\n".join(stand_zeilen) or "- (kein weiterer Stand übergeben)"

    hilfe_block = _gekuerzt(hilfe_text, MAX_ZEICHEN_HILFE) \
        or "(kein Hilfe-Abschnitt übergeben)"

    return (f"""Du beantwortest eine **Bedienfrage** zur AI Compliance Suite.

ANTWORTE AUSSCHLIESSLICH AUS DEM UNTEN STEHENDEN MATERIAL.
Was dort nicht steht, sagst du ausdrücklich: „Dazu steht nichts in der
Dokumentation." Erfinde keine Menüpunkte, keine Schaltflächen und keine
Feldnamen — eine erfundene Wegbeschreibung ist schlechter als keine.

Nenne am Ende die Überschriften, auf die du dich stützt.

Du gibst **keine Rechtsberatung**. Wird nach der Auslegung einer Vorschrift
gefragt, beschreibe, was die Anwendung dazu vorsieht, und verweise für die
Bewertung auf fachliche Prüfung.

Antworte knapp, auf Deutsch, in ganzen Sätzen. Nenne konkrete Wege in der
Oberfläche, wenn sie im Material stehen.

## Frage des Anwenders
{frage}

## Wo der Anwender gerade ist
- Modul: {modul or "(nicht angegeben)"}
- Bereich: {bereich or "(nicht angegeben)"}
{stand_block}

## Hilfe-Abschnitt dieses Bereichs (aus der Anwendung)
{hilfe_block}

## Handbuch
{handbuch_block}
""", fundstellen)
