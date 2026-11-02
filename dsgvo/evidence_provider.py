"""DSGVO-Evidenz-Provider (Sprint #40, #1491).

Mappt DSGVO-Anforderungen auf den operativen Zustand des DSGVO-Moduls (DSMS), damit die
KI-Bewertung anrechnet, was *durch die Software* bereits geführt wird: VVT (Art. 30),
TOM-Katalog (Art. 32), DSFA + verknüpfte Risikobewertung (Art. 35), Datenpannen
(Art. 33/34), Einwilligungen (Art. 7), Drittlandtransfer/TIA (Art. 44), Löschkonzept
(Art. 17), Datenschutzbeauftragter (Art. 37) sowie der Jahres-Kontrollplan. Wird über
``shared/evidence_context`` aufgerufen.

Vertrag: ``relevant_for(projekt, requirement) -> list[EvidenceItem]``. Best-effort — jeder
DB-Zugriff ist gekapselt; Fehler liefern keine Evidenz, brechen aber nie ab.

**PII-Schutz**: Register mit Personenbezug (Datenpannen, Betroffenenrechte) werden als
``sensitive=True`` markiert — der gemeinsame Aggregator redigiert ihren Inhalt für den
Cloud-Versand (``shared.evidence_context.redact_for_cloud``). Auch die nicht-sensiblen
Items enthalten bewusst nur Aggregat-/Statuszahlen, keine personenbezogenen Klartexte.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from shared.evidence_context import EvidenceItem, _clip

_DB = Path("data/db/dsgvo.sqlite")
_RB_DB = Path("data/db/risikobewertung.sqlite")

# DSFA-/DPIA-Status, die als abgeschlossen gelten.
_DPIA_DONE = {"abgeschlossen", "freigegeben"}
# Datenpannen-Status, die als erledigt gelten.
_PANNE_DONE = {"abgeschlossen", "geschlossen"}


def _articles(requirement: dict[str, Any]) -> set[int]:
    """Extrahiert die einschlägigen DSGVO-Artikelnummern aus einer Anforderung.

    Die DSGVO-Anforderungen tragen die Artikel im ``ref``-Feld (z. B. "Art. 32 Abs. 1
    lit. a DSGVO" oder "Art. 44–45 DSGVO"); ``kapitel`` ist nur GDS1–GDS6. Wir scannen
    ``ref`` + ``referenz`` + ``titel`` + ``beschreibung`` nach allen "Art. N"-Treffern,
    inkl. Bereiche wie "44–49" (Bindestrich/Gedankenstrich).
    """
    text = " ".join(str(requirement.get(k) or "") for k in
                    ("ref", "referenz", "titel", "beschreibung", "kapitel", "id"))
    arts: set[int] = set()
    # "Art. 44–49" / "Art. 33-34" → ganzen Bereich, sonst Einzelnummer.
    for m in re.finditer(r"Art\.?\s*(\d+)\s*(?:[–\-]\s*(\d+))?", text):
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else lo
        if hi < lo or hi - lo > 30:  # absurde Bereiche ignorieren
            hi = lo
        for n in range(lo, hi + 1):
            arts.add(n)
    return arts


# ── Register-Auswertungen ────────────────────────────────────────────────────


def _vvt_items(projekt: str) -> list[EvidenceItem]:
    try:
        from dsgvo.db import list_vvt
        rows = list_vvt(_DB, projekt)
    except Exception:  # noqa: BLE001
        return []
    if not rows:
        return []
    mit_rg = sum(1 for r in rows if str(r.get("rechtsgrundlage") or "").strip())
    return [EvidenceItem(
        "DSGVO VVT (Art. 30)", "register", "dsgvo_vvt:summary",
        _clip(f"Verarbeitungsverzeichnis geführt: {len(rows)} Verarbeitungstätigkeiten, "
              f"davon {mit_rg} mit dokumentierter Rechtsgrundlage (Art. 6)."),
        relevance=1.6)]


def _tom_items(projekt: str) -> list[EvidenceItem]:
    try:
        from dsgvo.tom_katalog import list_massnahmen
        rows = list_massnahmen(_DB, projekt)
    except Exception:  # noqa: BLE001
        return []
    if not rows:
        return []
    erfuellt = sum(1 for r in rows if int(r.get("status") or 0) >= int(r.get("soll") or 0)
                   and int(r.get("soll") or 0) > 0)
    geprueft = sum(1 for r in rows if str(r.get("wirksamkeit_datum") or "").strip())
    return [EvidenceItem(
        "DSGVO TOM-Katalog (Art. 32)", "register", "dsgvo_tom:summary",
        _clip(f"TOM-Katalog (SDM): {len(rows)} Maßnahmen, davon {erfuellt} auf Soll-Niveau; "
              f"{geprueft} mit dokumentierter Wirksamkeitsprüfung (Art. 32 Abs. 1 lit. d)."),
        relevance=1.7)]


def _dpia_items(projekt: str) -> list[EvidenceItem]:
    try:
        from dsgvo.db import list_dpia
        rows = list_dpia(_DB, projekt)
    except Exception:  # noqa: BLE001
        return []
    if not rows:
        return []
    fertig = sum(1 for r in rows if str(r.get("status") or "").lower() in _DPIA_DONE)
    items = [EvidenceItem(
        "DSGVO DSFA (Art. 35)", "register", "dsgvo_dpia:summary",
        _clip(f"{len(rows)} Datenschutz-Folgenabschätzung(en) angelegt, davon {fertig} "
              f"abgeschlossen/freigegeben."),
        relevance=1.6)]
    # Mit DSFA verknüpfte Risikobewertung (Art. 35 Abs. 7 c+d, #1084).
    for r in rows:
        rb_name = str(r.get("rb_projekt_id") or "").strip()
        if not rb_name:
            continue
        items += _linked_risk_items(rb_name, r.get("titel") or r.get("dpia_id"))
        break  # eine verknüpfte RB genügt als Nachweis
    return items


def _linked_risk_items(rb_name: str, dpia_label: Any) -> list[EvidenceItem]:
    try:
        from risikobewertung.db import load_risiken
        risiken = load_risiken(_RB_DB, rb_name)
    except Exception:  # noqa: BLE001
        return []
    if not risiken:
        return []
    bewertet = [r for r in risiken if r.get("risikowert") is not None]
    return [EvidenceItem(
        "Verknüpfte Risikobewertung (DSFA)", "risk", f"rb:{rb_name}",
        _clip(f"DSFA „{dpia_label}“ mit Risikobewertungs-Projekt '{rb_name}' verknüpft "
              f"({len(risiken)} Risiken, {len(bewertet)} bewertet) — Art. 35 Abs. 7 c+d."),
        relevance=1.5)]


def _datenpannen_items(projekt: str) -> list[EvidenceItem]:
    """Datenpannen — PII-haltig ⇒ sensitive=True (Cloud-Redaktion)."""
    try:
        from dsgvo.db import list_pannen
        rows = list_pannen(_DB, projekt)
    except Exception:  # noqa: BLE001
        return []
    if not rows:
        return []
    offen = [r for r in rows if str(r.get("status") or "offen").lower() not in _PANNE_DONE]
    gemeldet = sum(1 for r in rows if str(r.get("meldung_aufsicht_datum") or "").strip())
    return [EvidenceItem(
        "DSGVO Datenpannen (Art. 33/34)", "register", "dsgvo_datenpannen:summary",
        _clip(f"{len(rows)} Datenpanne(n) erfasst, davon {len(offen)} offen; {gemeldet} an die "
              f"Aufsicht gemeldet (Art. 33 — 72-h-Frist). Meldekette etabliert."),
        relevance=1.5, sensitive=True)]


def _betroffenenrechte_items(projekt: str) -> list[EvidenceItem]:
    """Betroffenenanträge — PII-haltig ⇒ sensitive=True (Cloud-Redaktion)."""
    try:
        from dsgvo.betroffenenrechte_db import list_antraege
        rows = list_antraege(_DB, projekt)
    except Exception:  # noqa: BLE001
        return []
    if not rows:
        return []
    offen = sum(1 for r in rows if str(r.get("status") or "") not in ("abgeschlossen", "abgelehnt"))
    ueberfaellig = sum(1 for r in rows if r.get("overdue"))
    return [EvidenceItem(
        "DSGVO Betroffenenrechte (Art. 15-22)", "register", "dsgvo_betroffenenrechte:summary",
        _clip(f"{len(rows)} Betroffenenantrag/-anträge bearbeitet, davon {offen} offen, "
              f"{ueberfaellig} überfällig (Frist Art. 12 Abs. 3). Prozess etabliert."),
        relevance=1.3, sensitive=True)]


def _einwilligung_items(projekt: str) -> list[EvidenceItem]:
    try:
        from dsgvo.einwilligung_db import list_einwilligungen
        rows = list_einwilligungen(_DB, projekt)
    except Exception:  # noqa: BLE001
        return []
    if not rows:
        return []
    aktiv = sum(1 for r in rows if str(r.get("status") or "") == "aktiv")
    return [EvidenceItem(
        "DSGVO Einwilligungen (Art. 7)", "register", "dsgvo_einwilligung:summary",
        _clip(f"{len(rows)} Einwilligungs-Tatbestand/-stände dokumentiert, davon {aktiv} aktiv "
              f"(Nachweisbarkeit Art. 7 Abs. 1, Widerruf Art. 7 Abs. 3)."),
        relevance=1.4)]


def _transfer_items(projekt: str) -> list[EvidenceItem]:
    try:
        from dsgvo.transfer_db import list_transfers
        rows = list_transfers(_DB, projekt)
    except Exception:  # noqa: BLE001
        return []
    if not rows:
        return []
    tia_ok = sum(1 for r in rows if str(r.get("tia_status") or "") == "abgeschlossen")
    return [EvidenceItem(
        "DSGVO Drittlandtransfer/TIA (Art. 44-49)", "register", "dsgvo_transfer:summary",
        _clip(f"{len(rows)} Drittlandtransfer(s) erfasst, davon {tia_ok} mit abgeschlossener "
              f"Transfer-Impact-Assessment (TIA, Art. 44-49)."),
        relevance=1.4)]


def _loeschkonzept_items(projekt: str) -> list[EvidenceItem]:
    try:
        from dsgvo.loeschkonzept_db import list_regeln
        rows = list_regeln(_DB, projekt)
    except Exception:  # noqa: BLE001
        return []
    if not rows:
        return []
    return [EvidenceItem(
        "DSGVO Löschkonzept (Art. 17)", "register", "dsgvo_loeschkonzept:summary",
        _clip(f"Löschkonzept nach DIN 66398: {len(rows)} Löschregel(n) für Datenkategorien "
              f"dokumentiert (Speicherbegrenzung Art. 5 Abs. 1 lit. e, Löschung Art. 17)."),
        relevance=1.4)]


def _dsb_items(projekt: str) -> list[EvidenceItem]:
    try:
        from dsgvo.dsb_db import get_dsb
        rec = get_dsb(_DB, projekt)
    except Exception:  # noqa: BLE001
        return []
    if not rec:
        return []
    veroeffentlicht = bool(rec.get("kontakt_veroeffentlicht"))
    gemeldet = bool(rec.get("gemeldet_aufsicht"))
    return [EvidenceItem(
        "DSGVO DSB (Art. 37-39)", "register", "dsgvo_dsb",
        _clip(f"Datenschutzbeauftragter benannt; Kontakt veröffentlicht: "
              f"{'ja' if veroeffentlicht else 'nein'}, der Aufsicht gemeldet: "
              f"{'ja' if gemeldet else 'nein'} (Art. 37 Abs. 7)."),
        relevance=1.4)]


def _kontrollen_items(projekt: str) -> list[EvidenceItem]:
    try:
        from dsgvo.kontrollen_db import list_kontrollen
        rows = list_kontrollen(_DB, projekt)
    except Exception:  # noqa: BLE001
        return []
    if not rows:
        return []
    abgeschlossen = sum(1 for r in rows if str(r.get("status") or "") == "abgeschlossen")
    return [EvidenceItem(
        "DSGVO Jahres-Kontrollplan (Art. 5 Abs. 2)", "register", "dsgvo_kontrollen:summary",
        _clip(f"Jährlicher Datenschutz-Kontrollplan: {len(rows)} Kontrolle(n), davon "
              f"{abgeschlossen} abgeschlossen (Rechenschaftspflicht Art. 5 Abs. 2)."),
        relevance=1.1)]


# ── Vertrag ──────────────────────────────────────────────────────────────────


def relevant_for(projekt: dict[str, Any], requirement: dict[str, Any]) -> list[EvidenceItem]:
    name = (projekt.get("name") or "").strip()
    if not name:
        return []
    arts = _articles(requirement)
    items: list[EvidenceItem] = []

    if 30 in arts:
        items += _vvt_items(name)
    if 32 in arts:
        items += _tom_items(name)
    if 35 in arts or 36 in arts:
        items += _dpia_items(name)
    if 33 in arts or 34 in arts:
        items += _datenpannen_items(name)
    if arts & {15, 16, 17, 18, 19, 20, 21, 22}:
        items += _betroffenenrechte_items(name)
    if 7 in arts:
        items += _einwilligung_items(name)
    if arts & {44, 45, 46, 47, 48, 49}:
        items += _transfer_items(name)
    if 17 in arts:
        items += _loeschkonzept_items(name)
    if arts & {37, 38, 39}:
        items += _dsb_items(name)
    # Jahres-Kontrollplan stützt die Rechenschaftspflicht (Art. 5 Abs. 2) breit.
    if 5 in arts or 24 in arts:
        items += _kontrollen_items(name)

    return items
