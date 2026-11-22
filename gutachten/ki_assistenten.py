"""#2114 — KI-Assistenten fürs Gutachten (Recherche, Formulierung, Beweisfragen).

LEITPLANKEN (Sachverständigenvorgaben)
- Alles ist **Vorschlag**; der SV wählt, bearbeitet und verantwortet den Endtext.
- Beim Gerichtsgutachten bleibt der § 407a-Hinweis; beim Privatgutachten ohne
  ZPO-Bezug (#2113) — dort tragen die Normen (DIN EN 16775 …) die Grundlage.
- **Keine erfundenen Fundstellen**: zu ISO/BSI (nicht im Volltext vorhanden) gibt
  die KI nur Orientierung mit Prüfhinweis; Klausel-/Abschnittsnummern nur, wenn im
  bereitgestellten Dokument belegt.
- Die KI **formuliert/struktur­iert/recherchiert** — sie entscheidet nicht; sie
  erfindet keine Befunde und keine Würdigung.

Dieses Modul baut nur **Prompts** (und wählt den Kontext). Ausgeführt wird über den
gemeinsamen Streaming-Weg (`/api/ai/run-stream`) mit Egress-Bestätigung, oder per
Copy/Paste. Parsen der Beweisfragen über `shared.json_io`.
"""
from __future__ import annotations

import re
from typing import Any

from gutachten import normen as _normen
from shared import json_io as _json_io


def _is_privat(projekt: dict[str, Any]) -> bool:
    return (projekt.get("gutachten_art") or "gericht") == "privat"


def _sv_hinweis(projekt: dict[str, Any]) -> str:
    """Art-abhängiger Schlusshinweis (#2113)."""
    if _is_privat(projekt):
        return ("Dies ist ein Vorschlag als Recherche-/Strukturierungshilfe. Die "
                "fachliche Aussage verantwortet der Sachverständige persönlich; "
                "maßgeblich sind die einschlägigen Normen (z. B. DIN EN 16775).")
    return ("Dies ist ein Vorschlag als Strukturierungshilfe. Die finale Beurteilung "
            "erfolgt persönlich durch den Sachverständigen (§ 407a Abs. 2 ZPO).")


# ── Kontext-Auswahl (Wort-Überdeckung, kein Vektorindex — Muster shared/hilfe) ──

_WORT = re.compile(r"[A-Za-zÄÖÜäöüß0-9]{4,}")
_STOPP = {"oder", "und", "eine", "einer", "eines", "dass", "wird", "sind", "mit",
          "für", "der", "die", "das", "den", "dem", "von", "auf", "bei", "ist",
          "wie", "was", "nach", "über", "zur", "zum", "aus", "diese", "dieser"}


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORT.findall(text or "") if w.lower() not in _STOPP}


def _abschnitte(text: str, groesse: int = 700) -> list[str]:
    """Teilt einen Dokumenttext in Absatz-nahe Abschnitte."""
    roh = re.split(r"\n\s*\n", text or "")
    out: list[str] = []
    for teil in roh:
        teil = teil.strip()
        if not teil:
            continue
        while len(teil) > groesse:
            out.append(teil[:groesse])
            teil = teil[groesse:]
        out.append(teil)
    return out


def waehle_dokument_treffer(frage: str, dokumente: list[dict[str, Any]], *,
                            max_treffer: int = 4, auszug_zeichen: int = 700) -> list[dict[str, Any]]:
    """Beste Dokument-Abschnitte zur Frage (belegbar, mit Dateiname)."""
    ft = _tokens(frage)
    if not ft:
        return []
    kandidaten: list[tuple[int, dict[str, Any]]] = []
    for d in dokumente:
        for ab in _abschnitte(d.get("text", "")):
            score = len(ft & _tokens(ab))
            if score:
                kandidaten.append((score, {
                    "dok_id": d.get("id"),
                    "dateiname": d.get("dateiname", ""),
                    "auszug": ab[:auszug_zeichen],
                }))
    kandidaten.sort(key=lambda x: x[0], reverse=True)
    return [k for _s, k in kandidaten[:max_treffer]]


_VERORDNUNG_TEXT: dict[str, tuple[float, str]] = {}


def verordnung_text(schluessel: str) -> str:
    """#2122: Volltext eines schon eingelesenen Rechtstexts (CRA/DSGVO/ZPO/BSIG …).

    Quelle ist ``shared.verordnungen`` (``data/*_resources``); extrahiert und je
    (Schlüssel, mtime) gecacht, damit die großen PDFs nicht je Frage neu gelesen
    werden. Liefert "" wenn der Text nicht vorliegt.
    """
    try:
        from shared import verordnungen as _vo
        v = _vo.nach_schluessel(schluessel)
        if not v:
            return ""
        # Nur bereits abgelegte Dateien lesen — **kein** Download (Netz).
        st = _vo.status(schluessel)
        if not st:
            return ""
        pdf = next((d for d in st[0].get("dateien", []) if d.get("ist_pdf")), None)
        if not pdf:
            return ""
        p = v.verzeichnis / pdf["name"]
        if not p.exists():
            return ""
        mtime = p.stat().st_mtime
        cached = _VERORDNUNG_TEXT.get(schluessel)
        if cached and cached[0] == mtime:
            return cached[1]
        from evidence.extract import extract_text
        text = extract_text(p) or ""
        _VERORDNUNG_TEXT[schluessel] = (mtime, text)
        return text
    except Exception:
        return ""


def waehle_verordnung_treffer(frage: str, schluessel_liste: list[str], *,
                              max_treffer: int = 4, auszug_zeichen: int = 700) -> list[dict[str, Any]]:
    """#2122: Beste Abschnitte aus den ausgewählten Rechtstexten (belegbar)."""
    ft = _tokens(frage)
    if not ft or not schluessel_liste:
        return []
    try:
        from shared import verordnungen as _vo
        titel = {v.schluessel: v.titel for v in _vo.VERORDNUNGEN}
    except Exception:
        titel = {}
    kandidaten: list[tuple[int, dict[str, Any]]] = []
    for sch in schluessel_liste:
        text = verordnung_text(sch)
        if not text:
            continue
        for ab in _abschnitte(text):
            score = len(ft & _tokens(ab))
            if score:
                kandidaten.append((score, {
                    "schluessel": sch,
                    "titel": titel.get(sch, sch),
                    "auszug": ab[:auszug_zeichen],
                }))
    kandidaten.sort(key=lambda x: x[0], reverse=True)
    return [k for _s, k in kandidaten[:max_treffer]]


def waehle_normen_treffer(frage: str, projekt_normen: list[dict[str, Any]], *,
                          max_treffer: int = 5) -> list[dict[str, Any]]:
    """Relevante Normen: hinterlegte Projekt-Normen zuerst, dann Katalog-Suche.

    Jeder Treffer trägt – wo bekannt – ``norm_id`` und ``framework`` (die
    Framework-Bibliothek-Kennung, z. B. ``ISO27037``), damit der Aufrufer dazu
    einen **hinterlegten lizenzierten Normtext** (``framework_sections``) laden
    kann (#2128).
    """
    treffer: list[dict[str, Any]] = []
    gesehen: set[str] = set()
    for n in projekt_normen:
        norm_id = n.get("norm_id") or ""
        kat = _normen.get_norm(norm_id) or {}
        titel = n.get("norm_titel") or kat.get("titel") or norm_id or ""
        if titel and titel not in gesehen:
            gesehen.add(titel)
            treffer.append({"titel": titel, "quelle": "hinterlegt",
                            "soll_kurz": kat.get("soll_kurz", ""),
                            "norm_id": norm_id,
                            "framework": kat.get("framework", "")})
    for t in _normen.search_normen(frage):
        n = _normen.get_norm(t.get("norm_id", "")) or {}
        titel = n.get("titel") or t.get("titel", "")
        if titel and titel not in gesehen:
            gesehen.add(titel)
            treffer.append({"titel": titel, "quelle": "katalog",
                            "soll_kurz": n.get("soll_kurz", ""),
                            "norm_id": n.get("id", ""),
                            "framework": n.get("framework", "")})
        if len(treffer) >= max_treffer:
            break
    return treffer[:max_treffer]


def norm_volltext_treffer(frage: str, normen_treffer: list[dict[str, Any]],
                          db_path: Any, *, max_treffer: int = 4,
                          auszug_zeichen: int = 700) -> list[dict[str, Any]]:
    """#2128: Beste Abschnitte aus **hinterlegten lizenzierten Normtexten**.

    Quelle sind die über die Framework-Bibliothek (Admin → Einstellungen)
    hochgeladenen und eingelesenen Normen-PDFs in ``framework_sections`` — genau
    derselbe Weg wie bei ISO 27001. Liefert nur für Normen, deren ``framework``
    im Katalog gesetzt ist und für die tatsächlich Abschnitte vorliegen; sonst
    leer (dann greift im Prompt der „kein Volltext"-Hinweis).
    """
    ft = _tokens(frage)
    frameworks = {t.get("framework") for t in (normen_treffer or []) if t.get("framework")}
    if not ft or not frameworks:
        return []
    try:
        from gutachten.db import fetch_sections
        rows = fetch_sections(db_path, sorted(frameworks))
    except Exception:
        return []
    # Titel je Framework aus dem Katalog (für belegbare Quelle-Angabe).
    fw_titel: dict[str, str] = {}
    for t in normen_treffer:
        if t.get("framework"):
            fw_titel[t["framework"]] = t.get("titel", t["framework"])
    kandidaten: list[tuple[int, dict[str, Any]]] = []
    for r in rows:
        fw = r.get("framework", "")
        text = r.get("text", "") or ""
        score = len(ft & _tokens(text))
        if not score:
            continue
        ref = " · ".join(filter(None, [r.get("doc_name", ""), r.get("section_ref", "")]))
        kandidaten.append((score, {
            "framework": fw,
            "titel": fw_titel.get(fw, fw),
            "fundstelle": ref,
            "auszug": text[:auszug_zeichen],
        }))
    kandidaten.sort(key=lambda x: x[0], reverse=True)
    return [k for _s, k in kandidaten[:max_treffer]]


# ── Prompt: Intelligente Recherche (#2116) ──

def build_recherche_prompt(frage: str, projekt: dict[str, Any],
                           dok_treffer: list[dict[str, Any]],
                           normen_treffer: list[dict[str, Any]],
                           verordnung_treffer: list[dict[str, Any]] | None = None,
                           verlauf: list[dict[str, Any]] | None = None,
                           norm_text_treffer: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    verordnung_treffer = verordnung_treffer or []
    norm_text_treffer = norm_text_treffer or []
    verlauf = verlauf or []
    dok_block = "\n\n".join(
        f"[Dokument: {t['dateiname']}]\n{t['auszug']}" for t in dok_treffer
    ) or "(keine passenden Projekt-Dokumente gefunden)"
    norm_block = "\n".join(
        f"- {t['titel']}" + (f" — {t['soll_kurz']}" if t.get("soll_kurz") else "")
        for t in normen_treffer
    ) or "(keine einschlägige Norm im Katalog/hinterlegt)"
    vo_block = "\n\n".join(
        f"[Rechtstext: {t['titel']}]\n{t['auszug']}" for t in verordnung_treffer
    ) or "(keine Auswahl / keine passende Stelle in den gewählten Rechtstexten)"
    # #2128 Hinterlegte lizenzierte Normtexte (Volltext-Auszüge aus hochgeladenen PDFs)
    normtext_block = "\n\n".join(
        f"[Normtext: {t['titel']}" + (f" · {t['fundstelle']}" if t.get("fundstelle") else "") + f"]\n{t['auszug']}"
        for t in norm_text_treffer
    )
    # Normtitel, zu denen hier echter Volltext vorliegt — der „kein Volltext"-
    # Hinweis gilt dann nur noch für die übrigen Normen.
    mit_volltext = {t.get("titel") for t in norm_text_treffer}
    # #2122 Chat-Verlauf (nur die letzten Runden, damit der Prompt nicht ausufert)
    verlauf_block = ""
    if verlauf:
        zeilen = []
        for m in verlauf[-6:]:
            rolle = "Frage" if (m.get("rolle") == "user") else "Antwort"
            zeilen.append(f"{rolle}: {(m.get('text') or '').strip()}")
        verlauf_block = "\n".join(zeilen)

    prompt = """Du unterstützt einen Sachverständigen bei der **Recherche** zu einem
Gutachten, im Dialog. Beantworte die aktuelle Frage **nur** anhand der unten
bereitgestellten Quellen; der bisherige Gesprächsverlauf dient dem Zusammenhang.
"""
    if verlauf_block:
        prompt += f"""
# Bisheriger Gesprächsverlauf
{verlauf_block}
"""
    prompt += f"""
# Aktuelle Frage
{frage.strip()}

# Projekt-Dokumente (Auszüge — belegbar)
{dok_block}

# Ausgewählte Rechtstexte (Auszüge — belegbar)
{vo_block}
"""
    if normtext_block:
        prompt += f"""
# Hinterlegte Normtexte (lizenziert — belegbar)
{normtext_block}
"""
    prompt += f"""
# Einschlägige Normen (Katalog/hinterlegt)
{norm_block}

# Regeln
- Stütze dich auf die bereitgestellten Quellen. Nenne, **worauf** du dich stützt
  (Dateiname, Normtitel bzw. Fundstelle).
"""
    if normtext_block:
        prompt += """- Für die oben unter „Hinterlegte Normtexte" bereitgestellten Auszüge darfst
  du dich auf den **Wortlaut** stützen und die Fundstelle benennen — zitiere nur
  das, was dort wirklich steht.
"""
    prompt += """- Zu Normen **ohne** hinterlegten Volltext (nur unter „Einschlägige Normen"
  gelistet) liegt hier **kein** Normtext vor. Gib dazu nur Orientierung und weise
  ausdrücklich darauf hin: „Maßgeblich ist der amtliche bzw. lizenzierte
  Normtext." **Erfinde keine Klausel-/Abschnittsnummern.**
- Steht in den Quellen nichts zur Frage, sage das ehrlich („Dazu liegt in den
  bereitgestellten Quellen nichts vor") statt zu spekulieren.
- **Keine Rechtsberatung.** Keine rechtliche Würdigung.

""" + _sv_hinweis(projekt) + "\n"
    quellen = ([{"art": "dokument", "dateiname": t["dateiname"]} for t in dok_treffer]
               + [{"art": "rechtstext", "titel": t["titel"]} for t in verordnung_treffer]
               + [{"art": "normtext", "titel": t["titel"], "fundstelle": t.get("fundstelle", "")}
                  for t in norm_text_treffer]
               + [{"art": "norm", "titel": t["titel"],
                   "volltext": t["titel"] in mit_volltext} for t in normen_treffer])
    return {"prompt": prompt, "quellen": quellen}


# ── Prompt: Formulierungshilfe (#2117) ──

_FELD_REGEL = {
    "befund": ("ein Befund (Tatsachen). Formuliere **nur Tatsachen**, kein Urteil, "
               "keine Bewertung."),
    "soll": ("der Soll-Teil einer Beurteilung: was die Norm/der Stand der Technik "
             "verlangt. Sachlich, ohne Bewertung des Einzelfalls."),
    "ist": ("der Ist-Teil einer Beurteilung: was im Befund vorgefunden wurde. "
            "Nur Tatsachen mit Befundbezug."),
    "kausalitaet": ("die Kausalität: warum der Befund technisch die Abweichung "
                    "bewirkt. Technisch-nachvollziehbar, **keine** rechtlichen Begriffe."),
    "wuerdigung": ("die gutachterliche Würdigung. Beginne mit „Aus "
                   "informationstechnischer Sicht …“. Keine rechtlichen Begriffe "
                   "(kein mangelhaft/schuldhaft/Vertragsbruch im Rechtssinne). Die "
                   "Bewertung bleibt die des Sachverständigen — erfinde nichts hinzu."),
    "antwort": ("die Antwort auf eine Beweisfrage. Sachlich, aus "
                "informationstechnischer Sicht."),
}


def build_formulierung_prompt(stichworte: str, feld: str,
                              projekt: dict[str, Any]) -> str:
    regel = _FELD_REGEL.get(feld, _FELD_REGEL["befund"])
    return f"""Formuliere die folgenden **Stichworte eines Sachverständigen** zu
klarem, sachlichem Fachdeutsch aus. Der Zieltext ist {regel}

# Stichworte des Sachverständigen
{stichworte.strip()}

# Regeln
- Formuliere **ausschließlich** das Gegebene aus. **Füge keine neuen Tatsachen,
  Befunde, Normen oder Schlussfolgerungen hinzu.**
- Keine Füllsätze, keine Wiederholung der Aufgabenstellung. Nur der fertige Text.
- Schreibe in der dritten Person / unpersönlich, präzise, nüchtern.

{_sv_hinweis(projekt)}
"""


# ── Prompt + Parser: Beweisfragen-Assistent (#2118) ──

def build_beweisfragen_prompt(fliesstext: str, projekt: dict[str, Any]) -> str:
    return f"""Du unterstützt einen Sachverständigen. Leite aus der folgenden
Fall-/Auftragsbeschreibung **Vorschläge für Beweisfragen** (Untersuchungsfragen)
ab, die der Sachverständige aus **informationstechnischer Sicht** beantworten kann.

# Fall-/Auftragsbeschreibung
{fliesstext.strip()}

# Regeln
- Präzise, einzeln beantwortbare Untersuchungsfragen. Keine Mehrfachfragen.
- **Keine rechtlichen Fragen** (Verschulden, Haftung, Vertragsauslegung) — nur
  technisch klärbare Sachfragen.
- Vorschläge; der Sachverständige wählt aus und formuliert final.

Antworte **ausschließlich** als JSON:
```json
{{"fragen": ["Frage 1 …", "Frage 2 …"]}}
```

{_sv_hinweis(projekt)}
"""


def parse_beweisfragen(raw: str) -> list[str]:
    """Robustes Parsen (abgeschnittene/fenced Antworten) → Liste von Fragetexten."""
    try:
        data, _berichte = _json_io.lade_mit_bericht(raw or "", context="gutachten.beweisfragen")
    except ValueError:
        data = {}
    fragen: list[str] = []
    if isinstance(data, dict):
        roh = data.get("fragen") or data.get("beweisfragen") or []
    elif isinstance(data, list):
        roh = data
    else:
        roh = []
    for f in roh:
        if isinstance(f, str) and f.strip():
            fragen.append(f.strip())
        elif isinstance(f, dict):
            t = f.get("frage") or f.get("frage_text") or f.get("text") or ""
            if t.strip():
                fragen.append(t.strip())
    return fragen
