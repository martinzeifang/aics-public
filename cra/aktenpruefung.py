"""Die eigene Akte gegen die Rückfragen eines Prüfers lesen (#1864/B).

DER GEDANKE
Das Gate rechnet, ob die Akte **vollständig** ist (#1612/#1745): Haken gesetzt,
Nachweise vorhanden, Fristen gehalten. Was es nicht kann, ist die Frage, die
eine Marktüberwachungsbehörde zuerst stellt: *Hält diese Aussage der ersten
Rückfrage stand?* Ein Haken an „Risikoabschätzung vorhanden“ sagt nichts
darüber, ob die Abschätzung zum ausgelieferten Stand passt oder sich an anderer
Stelle der Akte selbst widerspricht.

Dieser Lauf liest die Akte als Ganzes und benennt, was auffällt — **vor** der
Freigabe statt in der Rückfrage danach.

WAS ER AUSDRÜCKLICH NICHT TUT
- **Keine Ampel, keine Zahl, kein zweites Urteil.** Das Gate rechnet, die KI
  liest. Zwei Urteile über dieselbe Akte wären zwei Wahrheiten — dieselbe
  Regel, die in #1726/#1727/#1776 die zwei Berichts-Renderer zu einem gemacht
  hat. Würde hier eine Konformitätsaussage entstehen, stünde sie irgendwann
  neben der gerechneten, und niemand könnte die Abweichung erklären.
- **Nichts wird gespeichert, was wie eine Bewertung aussieht.** Das Ergebnis
  ist Anzeige und Export; der Lauf selbst steht als ``ai.lauf`` im
  Revisionspfad (#1841).
- **Kein Fachurteil über das Produkt.** Die Fragen betreffen die *Akte*: ihre
  Widersprüche, ihre Lücken, ihre Belegtiefe.

DER GEGENSTAND KOMMT ÜBER EINEN ADAPTER
``sammle`` baut die Beschreibung aus dem, was CRA schon rechnet. Ein zweites
Modul (Compliance-Audit wäre der nächste Kandidat) würde einen eigenen
Sammler mitbringen — aber **ohne** zweiten Fall bleibt es bei einer
Implementierung: Abstraktion auf Verdacht ist in diesem Repo mehrfach teuer
geworden.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

DB_PATH = Path("data/db/cra.sqlite")

_AUFTRAG = """Du liest die technische Akte eines Produkts, das unter die
EU-Cyberresilienzverordnung (2024/2847) fällt, mit den Augen einer
Marktüberwachungsbehörde.

AUFGABE
Benenne, was in dieser Akte der ersten Rückfrage **nicht** standhalten würde.
Drei Arten von Befunden interessieren:
1. **Widerspruch** — zwei Angaben in der Akte passen nicht zusammen.
2. **Belegtiefe** — eine Aussage ist formal vorhanden, aber nicht belegt oder
   der Beleg passt zeitlich/sachlich nicht zum erklärten Stand.
3. **Lücke mit Folge** — etwas fehlt, und zwar so, dass eine Pflicht der
   Verordnung dadurch nicht erfüllbar ist.

REGELN
- Beziehe dich **nur** auf die Angaben unten. Erfinde keine Dokumente, keine
  Daten und keine Artikelnummern.
- Nenne keine Gesamtnote, keine Ampel und keinen Prozentwert. Der
  Konformitätsstand wird von der Anwendung gerechnet, nicht hier.
- Wo die Akte in Ordnung ist, schreibe nichts. Eine kurze Liste echter Funde
  ist wertvoller als eine lange Liste mit Füllmaterial.
- `stelle` benennt den Ort in der Akte (z. B. „Anhang VII, Testberichte“ oder
  „Release 8.2.0, Art der Änderung“).
- `rueckfrage` ist die Frage, die ein Prüfer stellen würde — wörtlich.
"""

_FORMAT = """ANTWORTFORMAT
Antworte ausschließlich mit JSON in genau dieser Form:
{"befunde": [
  {"art": "widerspruch|belegtiefe|luecke",
   "stelle": "<Ort in der Akte>",
   "befund": "<was auffällt, ein Satz>",
   "rueckfrage": "<die Frage, die ein Prüfer stellen würde>",
   "schwere": "hoch|mittel|niedrig"}
]}
Ist nichts zu beanstanden: {"befunde": []}
"""


def sammle(projekt_name: str, version: str = "") -> dict[str, Any]:
    """Die Akte in der Form, in der sie dem Modell vorgelegt wird.

    Alles hier ist **gerechnet oder gespeichert** — es wird nichts erhoben, was
    nicht schon in der Anwendung steht. Best effort je Quelle: Eine fehlende
    Quelle macht den Lauf ärmer, nicht unmöglich.
    """
    akte: dict[str, Any] = {"projekt": projekt_name, "version": version}

    try:
        from cra.konformitaet_gate import evaluate
        gate = evaluate(projekt_name, version=version or None) or {}
        akte["ampel"] = gate.get("ampel")
        akte["phase"] = gate.get("phase")
        akte["offene_punkte"] = [
            {"titel": p.get("titel") or p.get("label"),
             "wirkung": p.get("wirkung"), "text": p.get("text")}
            for p in (gate.get("offene_punkte") or [])][:40]
        akte["abweichungen"] = gate.get("abweichungen") or []
        akte["annex_vollstaendig"] = gate.get("annex_vollstaendig")
    except Exception:  # noqa: BLE001
        akte["gate_fehlt"] = True

    try:
        from cra.traceability_db import annex_vii_status
        st = annex_vii_status(DB_PATH, projekt_name) or {}
        akte["annex_vii"] = [
            {"baustein": b.get("label"), "belegt": b.get("ampel") == "belegt",
             "nachweise": [n.get("doc_name") for n in (b.get("nachweise") or [])][:6]}
            for b in (st.get("bausteine") or [])]
    except Exception:  # noqa: BLE001
        pass

    try:
        from cra.sicherheitstests import nachweise as test_nachweise
        akte["sicherheitstests"] = (test_nachweise(DB_PATH, projekt_name) or [])[:10]
    except Exception:  # noqa: BLE001
        pass

    try:
        from cra.konformitaet_db import get_konformitaet
        k = get_konformitaet(DB_PATH, projekt_name, version or "") or {}
        akte["konformitaet"] = {
            "bewertungsweg": k.get("bewertungsweg"),
            "bewertung_abgeschlossen": bool(k.get("bewertung_abgeschlossen")),
            "doc_ausgestellt": bool(k.get("doc_ausgestellt")),
            "release_art": k.get("release_art"),
            "status": k.get("status"),
        }
    except Exception:  # noqa: BLE001
        pass

    return akte


def _als_text(akte: dict[str, Any]) -> str:
    """Die Akte als lesbarer Block.

    Bewusst kein rohes JSON: Das Modell soll die Akte **lesen**, und eine
    verschachtelte JSON-Struktur lädt dazu ein, Felder zu zitieren statt
    Zusammenhänge zu sehen.
    """
    z: list[str] = [f"PRODUKT: {akte.get('projekt')}"]
    if akte.get("version"):
        z.append(f"RELEASE: {akte['version']}")
    k = akte.get("konformitaet") or {}
    if k:
        z.append("")
        z.append("KONFORMITÄTSBEWERTUNG")
        z.append(f"- Weg: {k.get('bewertungsweg') or '(nicht gesetzt)'}")
        z.append(f"- Bewertung abgeschlossen: {'ja' if k.get('bewertung_abgeschlossen') else 'nein'}")
        z.append(f"- EU-Konformitätserklärung ausgestellt: {'ja' if k.get('doc_ausgestellt') else 'nein'}")
        z.append(f"- Art des Releases: {k.get('release_art') or '(unbestimmt)'}")
        z.append(f"- Freigabestand: {k.get('status') or '(entwurf)'}")
    if akte.get("offene_punkte"):
        z.append("")
        z.append("OFFENE PUNKTE (von der Anwendung gerechnet)")
        for p in akte["offene_punkte"]:
            z.append(f"- [{p.get('wirkung')}] {p.get('titel')}: {p.get('text') or ''}")
    if akte.get("abweichungen"):
        z.append("")
        z.append("ABWEICHUNGEN")
        for a in akte["abweichungen"]:
            z.append(f"- {a}")
    if akte.get("annex_vii"):
        z.append("")
        z.append("ANHANG VII — BELEGE")
        for b in akte["annex_vii"]:
            nw = ", ".join(n for n in (b.get("nachweise") or []) if n) or "—"
            z.append(f"- {b.get('baustein')}: "
                     f"{'belegt' if b.get('belegt') else 'offen'} ({nw})")
    if akte.get("sicherheitstests"):
        z.append("")
        z.append("SICHERHEITSTESTS (Anhang I Teil II Nr. 3)")
        for t in akte["sicherheitstests"]:
            if isinstance(t, dict):
                z.append(f"- {t.get('art') or t.get('quelle')}: "
                         f"{t.get('name') or ''} ({t.get('datum') or 'ohne Datum'})")
    return "\n".join(z)


def baue_prompt(projekt_name: str, version: str = "") -> str:
    """Der Prompt — auch für den Weg zum Kopieren.

    Serverseitig zusammengesetzt, mit demselben Code wie der Sendeweg (#1832).
    Die Akte ist **eigener** Bestand, kein Fremdtext: Sie wird nicht als
    ``BEGIN_UNTRUSTED_DATA`` gerahmt, denn genau sie soll beurteilt werden.
    """
    akte = sammle(projekt_name, version)
    return "\n".join([_AUFTRAG, "", "DIE AKTE", _als_text(akte), "", _FORMAT])


def parse_antwort(roh: Any) -> list[dict[str, Any]]:
    """Befunde aus der Antwort — ohne Gesamturteil.

    Felder, die wie ein zweites Urteil aussehen (``ampel``, ``score``,
    ``konform``), werden **verworfen**, auch wenn das Modell sie liefert. Eine
    Zahl in dieser Antwort würde früher oder später neben der gerechneten
    stehen.
    """
    daten = roh
    if isinstance(roh, str):
        from server.services.anforderung_prompt import parse_chatgpt_json
        daten = parse_chatgpt_json(roh)
    liste = None
    if isinstance(daten, dict):
        liste = daten.get("befunde") or daten.get("findings")
    elif isinstance(daten, list):
        liste = daten
    if not isinstance(liste, list):
        return []

    erlaubte_arten = {"widerspruch", "belegtiefe", "luecke"}
    erlaubte_schwere = {"hoch", "mittel", "niedrig"}
    out: list[dict[str, Any]] = []
    for b in liste:
        if not isinstance(b, dict):
            continue
        befund = str(b.get("befund") or "").strip()
        if not befund:
            continue
        art = str(b.get("art") or "").strip().lower()
        schwere = str(b.get("schwere") or "").strip().lower()
        out.append({
            "art": art if art in erlaubte_arten else "luecke",
            "stelle": str(b.get("stelle") or "").strip(),
            "befund": befund,
            "rueckfrage": str(b.get("rueckfrage") or "").strip(),
            "schwere": schwere if schwere in erlaubte_schwere else "mittel",
        })
    rang = {"hoch": 0, "mittel": 1, "niedrig": 2}
    return sorted(out, key=lambda b: rang.get(b["schwere"], 1))


def pruefe(projekt_name: str, version: str = "") -> dict[str, Any]:
    """Ein Aktenprüfungslauf über die gemeinsame Engine (#1841)."""
    from shared.ki_engine import (OHNE_OBJEKT, KiAuftrag, KiNichtVerfuegbar,
                                  ki_lauf)

    prompt = baue_prompt(projekt_name, version)
    try:
        erg = ki_lauf(KiAuftrag(
            prompt=prompt,
            # Kein Inhalt an einem Fachobjekt: Das Ergebnis ist eine
            # Mängelliste, keine Bewertung.
            herkunft=OHNE_OBJEKT,
            antwortform="json",
            aufgabe="aktenpruefung",
            modul="cra",
            projekt=projekt_name,
            egress_pflicht=True,
            kontext=f"aktenpruefung:{projekt_name}:{version or 'produkt'}",
        ))
    except KiNichtVerfuegbar as e:
        raise RuntimeError(str(e)) from e
    if not erg.ok:
        raise RuntimeError(erg.fehler or "KI-Aufruf fehlgeschlagen")
    return {"befunde": parse_antwort(erg.parsed), "provider": erg.provider,
            "lauf_id": erg.lauf_id}


__all__ = ["baue_prompt", "parse_antwort", "pruefe", "sammle"]
