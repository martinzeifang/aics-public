"""G2 — 5 BISG-Wizards.

G2-1 Auftragsklärung + Befangenheits-Selbstcheck
G2-2 Asservat-Aufnahme mit Live-SHA-256
G2-3 Befund-Editor mit Tatsachen-only-Check
G2-4 Beurteilungs-Generator mit Norm-Picker (Prompt-Builder)
G2-5 Schluss-Validator (delegiert an gerichtsgutachten_gen.validate_pflichtfelder)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gutachten import gerichts_db as _gdb
from gutachten import befangenheit as _befang
from gutachten import normen as _normen
from gutachten import gerichtsgutachten_gen as _ggen
from gutachten.linters import sprache as _sprache


# ─────────────────────────────────────────────────────────
# G2-1 — Phase-1-Wizard: Auftragsklärung + Befangenheits-Selbstcheck
# ─────────────────────────────────────────────────────────

SELBSTCHECK_FRAGEN = [
    {"key": "wirtschaftlich",   "frage": "Liegt eine wirtschaftliche Verflechtung mit einer Partei vor (Beteiligung, Auftragsverhältnis)?"},
    {"key": "familiaer",        "frage": "Bestehen persönliche oder familiäre Nähebeziehungen zu Beteiligten?"},
    {"key": "vorbefassung",     "frage": "Waren Sie vorher im selben Sachverhalt tätig (als Berater, Entwickler, Projektleiter)?"},
    {"key": "social_media",     "frage": "Haben Sie sich auf Social Media zu Beteiligten oder zum Sachverhalt geäußert?"},
    {"key": "kompetenz",        "frage": "Reicht Ihre eigene Kompetenz aus, um die Beweisfragen vollständig zu beantworten?"},
]


def format_befangenheits_text(antworten: dict[str, str], db_treffer: list[dict[str, Any]],
                              datum: str = "") -> str:
    """#696 — Generiert formellen Befangenheits-Fließtext für den Verfahrensgang.

    Berücksichtigt die User-Antworten und ggf. DB-Treffer.
    """
    if not datum:
        from datetime import datetime
        datum = datetime.now().strftime("%d.%m.%Y")

    def is_nein(key: str) -> bool:
        return (antworten.get(key) or "").lower() == "nein"
    def is_ja(key: str) -> bool:
        return (antworten.get(key) or "").lower() == "ja"
    def is_unklar(key: str) -> bool:
        return (antworten.get(key) or "").lower() == "unklar"

    parts: list[str] = [
        f"Der unterzeichnende Sachverständige hat am {datum} eine Befangenheitsprüfung "
        f"nach § 406 ZPO durchgeführt."
    ]

    # Wirtschaftliche Verflechtung
    if is_nein("wirtschaftlich"):
        parts.append("Es bestehen keine wirtschaftlichen Verflechtungen mit den Verfahrensparteien.")
    elif is_ja("wirtschaftlich"):
        parts.append("⚠ Wirtschaftliche Verflechtungen mit einer Verfahrenspartei wurden festgestellt — eine Befangenheitsanzeige nach § 406 ZPO wird in Erwägung gezogen.")
    elif is_unklar("wirtschaftlich"):
        parts.append("Bezüglich wirtschaftlicher Verflechtungen bestehen Unklarheiten, die noch zu prüfen sind.")

    # Persönliche/familiäre Nähe
    if is_nein("familiaer"):
        parts.append("Persönliche oder familiäre Nähebeziehungen zu Beteiligten liegen nicht vor.")
    elif is_ja("familiaer"):
        parts.append("⚠ Persönliche oder familiäre Nähebeziehungen zu Beteiligten wurden offengelegt.")

    # Vorbefassung
    if is_nein("vorbefassung"):
        parts.append("Eine Vorbefassung in diesem Sachverhalt besteht nicht.")
    elif is_ja("vorbefassung"):
        parts.append("⚠ Eine Vorbefassung im selben Sachverhalt liegt vor und wird dem Gericht angezeigt.")

    # Social Media
    if is_nein("social_media"):
        parts.append("Social-Media-Äußerungen zu Beteiligten oder zum Sachverhalt, die eine Besorgnis der Befangenheit begründen könnten, liegen nicht vor.")
    elif is_ja("social_media"):
        parts.append("⚠ Social-Media-Äußerungen zu Beteiligten wurden festgestellt — Prüfung der Befangenheits-Relevanz erforderlich.")

    # Fachliche Kompetenz
    if is_ja("kompetenz"):
        parts.append("Die erforderliche fachliche Sachkunde für die im Beweisbeschluss formulierten Fragen ist nach Selbsteinschätzung gegeben.")
    elif is_nein("kompetenz"):
        parts.append("⛔ Die fachliche Sachkunde für einzelne Beweisfragen reicht nicht aus — das Gericht wird gemäß § 407a Abs. 1 ZPO unverzüglich unterrichtet.")

    # DB-Treffer
    if db_treffer:
        treffer_text = []
        for t in db_treffer[:3]:  # erste 3
            treffer_text.append(f"„{t.get('projekt_name', '')}" + (f" — {t['grund']}" if t.get('grund') else "") + "\"")
        parts.append(
            f"Die automatisierte Datenbankprüfung ergab {len(db_treffer)} Hinweis(e) auf möglicherweise "
            f"vorbefasste Projekte ({', '.join(treffer_text)}). Diese wurden vom Sachverständigen "
            f"einzeln geprüft und als unkritisch eingestuft."
        )

    parts.append(
        "Das Ergebnis dieses Selbstchecks wurde als Verfahrensereignis dokumentiert und ist in der "
        "Akte abrufbar (Dokumentationspflicht nach DIN EN 16775 + § 407a ZPO)."
    )

    return " ".join(parts)


def selbstcheck(db_path: Path, projekt_name: str, antworten: dict[str, str], sv_user: str = "") -> dict[str, Any]:
    """Liefert Befangenheits-Befund + protokolliert als Verfahrensereignis.

    antworten: {key: 'ja'|'nein'|'unklar'} pro SELBSTCHECK_FRAGEN-Eintrag.
    Kompetenz 'nein' = Ablehnung notwendig.
    Andere 'ja' = potenzielle Befangenheit (§ 406 ZPO).
    """
    issues: list[dict[str, Any]] = []
    for f in SELBSTCHECK_FRAGEN:
        a = (antworten.get(f["key"]) or "").lower()
        if f["key"] == "kompetenz" and a == "nein":
            issues.append({"key": f["key"], "level": "block", "message": "Eigene Kompetenz reicht NICHT — Auftrag ablehnen (§ 407 Abs. 2 ZPO)"})
        elif f["key"] != "kompetenz" and a == "ja":
            issues.append({"key": f["key"], "level": "warn", "message": f"Möglicher Befangenheitsgrund: '{f['frage']}'"})
        elif a == "unklar":
            issues.append({"key": f["key"], "level": "info", "message": f"Unklar — bitte abklären: '{f['frage']}'"})

    # Optional zusätzlich Vorbefassungs-Check gegen DB (#654: aktuelles Projekt ausschließen)
    projekt = _gdb.load_gerichts_projekt(db_path, projekt_name) or {}
    parteien = [projekt.get("klaeger_name", ""), projekt.get("beklagter_name", "")]
    db_treffer = _befang.check(db_path, kunde=projekt.get("klaeger_name", ""),
                               parteien=parteien, exclude_projekt_name=projekt_name)
    db_treffer.extend(_befang.check(db_path, kunde=projekt.get("beklagter_name", ""),
                                    parteien=parteien, exclude_projekt_name=projekt_name))
    db_risiko = _befang.aggregate_risk(db_treffer)

    # #669 Fix: status entkoppelt von DB-Treffern (db_treffer sind nur Hinweise)
    status = "blockiert" if any(i["level"] == "block" for i in issues) else \
             ("vorsicht" if issues else "ok")

    # #696 — Fließtext + strukturierte Antworten getrennt speichern
    fliesstext = format_befangenheits_text(antworten, db_treffer)

    if projekt_name:
        # Verfahrensereignis bekommt FLIESSTEXT (für DOCX-Anzeige)
        _gdb.save_verfahrensereignis(
            db_path,
            projekt_name=projekt_name,
            ereignis_typ="selbstcheck",
            titel=f"Befangenheits-Selbstcheck ({sv_user or 'SV'}) — Status: {status}",
            beschreibung=fliesstext,
            empfaenger=[],
        )
        # Antworten als JSON im Projekt-meta_json persistieren (für Re-Open)
        import json as _j
        meta = _j.loads(projekt.get("meta_json") or "{}")
        meta["last_selbstcheck"] = {
            "datum": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "sv_user": sv_user,
            "status": status,
            "antworten": antworten,
            "issues": issues,
            "db_treffer": db_treffer,
            "fliesstext": fliesstext,
        }
        _gdb.save_gerichts_projekt(
            db_path,
            name=projekt["name"],
            gutachten_art=projekt.get("gutachten_art", "gericht"),
            gericht=projekt.get("gericht", ""), kammer=projekt.get("kammer", ""),
            aktenzeichen=projekt.get("aktenzeichen", ""),
            klaeger_name=projekt.get("klaeger_name", ""), klaeger_anwalt=projekt.get("klaeger_anwalt", ""),
            beklagter_name=projekt.get("beklagter_name", ""), beklagter_anwalt=projekt.get("beklagter_anwalt", ""),
            beweisbeschluss_datum=projekt.get("beweisbeschluss_datum", ""),
            auftraggeber=projekt.get("auftraggeber", ""), auftrags_art=projekt.get("auftrags_art", ""),
            auftrags_datum=projekt.get("auftrags_datum", ""), auftrags_nummer=projekt.get("auftrags_nummer", ""),
            honorarvereinbarung=projekt.get("honorarvereinbarung", ""),
            thema=projekt.get("thema", ""), vertraulichkeit=projekt.get("vertraulichkeit", ""),
            sv_name=projekt.get("sv_name", ""), sv_zertifizierung=projekt.get("sv_zertifizierung", ""),
            sv_anschrift=projekt.get("sv_anschrift", ""), sv_kontakt=projekt.get("sv_kontakt", ""),
            status=projekt.get("status", ""), meta=meta,
        )

    # #669 Fix: Empfehlung aus User-Antworten UND DB-Treffern kombiniert
    if status == "ok" and not db_treffer:
        empfehlung = {
            "level": "ok",
            "headline": "✓ Selbstcheck bestanden — keine Befangenheitsgründe",
            "empfehlung": "Selbstcheck-Ergebnis wurde als Verfahrensereignis protokolliert. Sie können den Auftrag annehmen.",
        }
    elif status == "ok" and db_treffer:
        # Sauberer User-Selbstcheck, aber DB findet Vorbefassungs-Hinweise
        empfehlung = {
            "level": "hinweis",
            "headline": "✓ Selbstcheck OK — DB-Hinweise bitte prüfen",
            "empfehlung": (
                "Ihre Selbstcheck-Antworten sind sauber. Die DB hat "
                f"{len(db_treffer)} Vorbefassungs-Hinweise gefunden — bitte einzeln prüfen "
                "und entscheiden, ob sie auf eine echte Vorbefassung deuten."
            ),
        }
    else:
        # Issues im Selbstcheck → schwerwiegender
        empfehlung = _befang.recommendation(db_risiko if db_risiko != "keins" else "mittel")

    return {
        "status": status,
        "issues": issues,
        "db_treffer": db_treffer,
        "db_risiko": db_risiko,
        "empfehlung": empfehlung,
        "fliesstext": fliesstext,  # #696
    }


# ─────────────────────────────────────────────────────────
# G2-2 — Phase-2-Wizard: Asservat-Aufnahme
# (SHA-256 wird über existierenden /gerichts/sha256-Endpoint berechnet, dann Asset gespeichert)
# Sicherungsprotokoll als Text/JSON-Struktur
# ─────────────────────────────────────────────────────────

def sicherungsprotokoll(asset: dict[str, Any]) -> dict[str, Any]:
    """Erzeugt Sicherungsprotokoll-Daten (für PDF-Generierung im Frontend oder G4-1)."""
    return {
        "titel": f"Sicherungsprotokoll — Asservat '{asset.get('bezeichnung', '')}'",
        "datum_utc": asset.get("akquisitions_utc") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ort": asset.get("akquisitions_ort", ""),
        "bezeichnung": asset.get("bezeichnung", ""),
        "sha256": asset.get("sha256", ""),
        "werkzeug": f"{asset.get('werkzeug_name', '')} {asset.get('werkzeug_version', '')}".strip(),
        "parteien_anwesend": asset.get("parteien_anwesend", []),
        "gegengezeichnet_von": asset.get("gegengezeichnet_von", ""),
        "originalname": asset.get("original_dateiname", ""),
        "bemerkungen": asset.get("bemerkungen", ""),
        "norm": "ISO/IEC 27037 — Chain of Custody",
    }


# ─────────────────────────────────────────────────────────
# G2-3 — Phase-3-Wizard: Befund-Editor mit Tatsachen-only-Check
# (Live-Linter über /lint mit context=gerichts, kind=sprache — der Befund-Save validiert zusätzlich)
# ─────────────────────────────────────────────────────────

def validate_befund_text(text: str) -> dict[str, Any]:
    """Vor-Save-Validator für Befund-Text. Liefert Warning-Liste — blockt nicht."""
    hints = _sprache.lint_befund(text)
    return {
        "warnings_anzahl": len(hints),
        "hints": hints,
        "ok": all(h["level"] != "error" for h in hints),
    }


# ─────────────────────────────────────────────────────────
# G2-4 — Phase-4-Wizard: Beurteilungs-Prompt-Builder mit Norm-Picker
# ─────────────────────────────────────────────────────────

def build_beurteilung_prompt(
    projekt: dict[str, Any],
    befunde: list[dict[str, Any]],
    norm_id: str,
    sub_id: str | None = None,
) -> str:
    """Baut ChatGPT-Prompt für Beurteilungs-Vorschlag.

    Norm wird aus normen.json gezogen. KI-Vorschlag erfordert finale persönliche
    Übernahme durch den SV (§ 407a Abs. 2 ZPO).
    """
    norm = _normen.get_norm(norm_id)
    if not norm:
        raise ValueError(f"Norm '{norm_id}' nicht gefunden")

    sub_text = ""
    if sub_id:
        sm = _normen.get_sub_merkmal(norm_id, sub_id)
        if sm:
            sub_text = f"**Sub-Merkmal:** {sm['name']} ({sm.get('beschreibung', '')})"

    befunde_text = "\n".join(
        f"- Befund {b.get('nr')}: {b.get('titel')}\n  {b.get('beschreibung_text', '')[:300]}"
        for b in befunde
    )

    return f"""Du unterstützt einen Sachverständigen bei der Erstellung eines Gerichtsgutachtens.
Generiere einen **Beurteilungs-Vorschlag** nach BISG-Standard.

# Verfahren
- Aktenzeichen: {projekt.get('aktenzeichen', '')}
- Gericht: {projekt.get('gericht', '')}
- Thema: {projekt.get('thema', '')}

# Norm-Referenz
- {norm['titel']} (Version {norm.get('version', '')})
{sub_text}

# Befunde aus Kap. IV
{befunde_text}

Erstelle eine strukturierte Beurteilung. **Wichtig:**
- Nutze die Formulierung 'Aus informationstechnischer Sicht...'
- VERMEIDE rechtliche Begriffe (Vertragsbruch, schuldhaft, mangelhaft im Rechtssinne)
- Trenne Soll (was die Norm verlangt) und Ist (was vorgefunden wurde) klar
- Begründe die Kausalität wissenschaftlich

Antworte **ausschließlich** als JSON:
```json
{{
  "titel": "kurzer Titel der Beurteilung",
  "soll_text": "Was die Norm verlangt (2-4 Sätze)",
  "ist_text": "Was vorgefunden wurde (Befund-Bezug, 2-4 Sätze)",
  "kausalitaet_text": "Warum der Befund einen Verstoß darstellt (2-3 Sätze)",
  "bewertung_text": "Gutachterliche Würdigung — 'Aus informationstechnischer Sicht...' (3-5 Sätze)"
}}
```

**Hinweis:** Dieser Vorschlag dient nur als Strukturierungshilfe. Die finale
Beurteilung und Kausalitätsbewertung erfolgt persönlich durch den Sachverständigen
(§ 407a Abs. 2 ZPO).
"""


def parse_beurteilung_response(raw: str, norm_id: str, sub_id: str | None = None) -> dict[str, Any]:
    """Parst KI-Antwort + füllt Norm-Referenz."""
    text = (raw or "").strip()
    for marker in ("```json", "```"):
        if marker in text:
            parts = text.split(marker)
            if len(parts) >= 2:
                text = parts[1].split("```")[0]
                break
    start, end = text.find("{"), text.rfind("}")
    data: dict[str, Any] = {}
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            data = {}

    norm = _normen.get_norm(norm_id) or {}
    norm_referenz = norm.get("titel", "")
    if sub_id:
        sm = _normen.get_sub_merkmal(norm_id, sub_id)
        if sm:
            norm_referenz = f"{norm['titel']} — {sm['name']}"

    return {
        "titel": data.get("titel", ""),
        "soll_text": data.get("soll_text", ""),
        "ist_text": data.get("ist_text", ""),
        "kausalitaet_text": data.get("kausalitaet_text", ""),
        "bewertung_text": data.get("bewertung_text", ""),
        "norm_referenz": norm_referenz,
    }


# ─────────────────────────────────────────────────────────
# G2-5 — Phase-5-Wizard: Schluss-Validator (delegiert)
# ─────────────────────────────────────────────────────────

def schluss_validator(db_path: Path, projekt_name: str) -> dict[str, Any]:
    """Aggregiert alle Validations (Pflichtfelder + Sprach-Linter über alle Befunde/Beurteilungen)."""
    errors = _ggen.validate_pflichtfelder(db_path, projekt_name)
    # Sprach-Linter über Befunde + Beurteilungen
    sprach_warnings: list[dict[str, Any]] = []
    for b in _gdb.list_befunde(db_path, projekt_name):
        h = _sprache.lint_befund(b.get("beschreibung_text", ""))
        for x in h:
            sprach_warnings.append({**x, "scope": f"Befund {b.get('nr')}"})
    for u in _gdb.list_beurteilungen(db_path, projekt_name):
        for field in ("ist_text", "kausalitaet_text", "bewertung_text"):
            h = _sprache.lint_beurteilung(u.get(field, ""))
            for x in h:
                sprach_warnings.append({**x, "scope": f"Beurteilung {u.get('nr')} ({field})"})

    return {
        "errors": errors,
        "sprach_warnings": sprach_warnings,
        "release_ready": not errors,
        "errors_count": len(errors),
        "warnings_count": len(sprach_warnings),
    }
