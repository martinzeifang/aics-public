"""CRA-Konformitäts-Gate je Release (#1612/#1613).

Entscheidet maschinell, ob ein Produkt-Release als CRA-konform ausgewiesen werden darf.
Grundsatz (CRA): essenzielle Anforderungen (Annex I) sind verpflichtend. Eine Abweichung
gilt nur dann als konform, wenn sie **risikobasiert begründet** ist — das verknüpfte
Nichterfüllungs-Risiko ist als Restrisiko **akzeptiert** (Kategorie nicht_anwendbar /
restrisiko / kompensierend, #1613). Eine offene Nicht-Konformität einer anwendbaren
Anforderung verhindert die grüne Ampel.

Ampel:
- ``gruen``   — alle anwendbaren Anforderungen erfüllt oder begründet, keine offenen
               kritischen/hohen Schwachstellen, Annex VII vollständig, DoC ausgestellt.
- ``bedingt`` — nur noch begründete Abweichungen mit Auflagen / kleinere offene Punkte.
- ``rot``     — offene Nicht-Konformitäten / offene kritische Schwachstellen.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

CRA_DB = Path("data/db/cra.sqlite")
RB_DB = Path("data/db/risikobewertung.sqlite")

# Bewertung >= 4 (überwiegend/vollständig umgesetzt) gilt als erfüllt.
_ERFUELLT_AB = 4


def _accepted_gap_for(rb_name: str, requirement_id: str,
                      risks_by_src: dict[str, list[dict]]) -> dict | None:
    """Liefert ein akzeptiertes Nichterfüllungs-Risiko für die Anforderung, falls vorhanden."""
    src_id = f"cra:requirement:{requirement_id}"
    for r in risks_by_src.get(src_id, []):
        if (r.get("behandlung") or "") == "akzeptiert" and (r.get("akzeptanz_kategorie") or ""):
            return r
    return None


def evaluate(projekt_name: str, *, version: str | None = None) -> dict[str, Any]:
    """Bewertet die Konformität eines Projekts/Release. Best effort, nie Exception nach außen."""
    from cra.db import load_bewertungen, load_projekt, list_vuln
    from cra.requirements import CRA_ANFORDERUNGEN, berechne_reifegrad
    from cra.traceability_db import annex_vii_status

    projekt = load_projekt(CRA_DB, projekt_name) or {}
    meta = projekt.get("meta") if isinstance(projekt.get("meta"), dict) else {}
    rb_name = (meta.get("linked_risk_projekt") or "").strip()

    bewertungen_raw = load_bewertungen(CRA_DB, projekt_name)
    bewertungen = {rid: d.get("bewertung", 0) for rid, d in bewertungen_raw.items()}

    # akzeptierte Nichterfüllungs-Risiken je Quelle einsammeln
    risks_by_src: dict[str, list[dict]] = {}
    if rb_name:
        try:
            from risikobewertung.db import load_risiken
            for r in load_risiken(RB_DB, rb_name):
                fe = r.get("felder") or {}
                sid = str(fe.get("_source_id") or "")
                if sid:
                    risks_by_src.setdefault(sid, []).append(r)
        except Exception:  # noqa: BLE001
            pass

    erfuellt = begruendet = offen = 0
    offene_punkte: list[dict[str, Any]] = []
    abweichungen: list[dict[str, Any]] = []
    for req in CRA_ANFORDERUNGEN:
        rid = req["id"]
        bew = int(bewertungen.get(rid, 0) or 0)
        if bew >= _ERFUELLT_AB:
            erfuellt += 1
            continue
        acc = _accepted_gap_for(rb_name, rid, risks_by_src) if rb_name else None
        if acc:
            begruendet += 1
            abweichungen.append({"requirement_id": rid, "titel": req.get("titel"),
                                 "ref": req.get("ref"), "art": "begruendet",
                                 "kategorie": acc.get("akzeptanz_kategorie"),
                                 "grund": acc.get("akzeptanz_grund"),
                                 "von": acc.get("akzeptanz_von"),
                                 "rechtsgrundlage": acc.get("rechtsgrundlage")})
        else:
            offen += 1
            offene_punkte.append({"typ": "anforderung", "requirement_id": rid,
                                  "titel": req.get("titel"), "ref": req.get("ref"),
                                  "hinweis": "nicht erfüllt und nicht begründet akzeptiert",
                                  "link": "anforderungen"})
            abweichungen.append({"requirement_id": rid, "titel": req.get("titel"),
                                 "ref": req.get("ref"), "art": "offen"})

    # Schwachstellen
    offene_krit = 0
    try:
        for v in list_vuln(CRA_DB, projekt_name):
            if str(v.get("status") or "open") in ("open", "triaging") \
               and str(v.get("schwere") or "").lower() in ("critical", "high"):
                offene_krit += 1
    except Exception:  # noqa: BLE001
        pass
    if offene_krit:
        offene_punkte.append({"typ": "schwachstelle", "titel": f"{offene_krit} offene kritische/hohe Schwachstelle(n)",
                              "hinweis": "beheben oder als Risiko akzeptieren", "link": "schwachstellen"})

    # Annex VII
    annex_ok = False
    try:
        annex = annex_vii_status(CRA_DB, projekt_name)
        annex_ok = bool(annex.get("vollstaendig"))
        for b in annex.get("bausteine", []):
            if b.get("ampel") != "belegt":
                offene_punkte.append({"typ": "annex", "titel": f"Annex VII: {b.get('label')} fehlt",
                                      "hinweis": "Nachweis ergänzen", "link": "traceability"})
    except Exception:  # noqa: BLE001
        pass

    # DoC
    doc_ok = False
    try:
        from cra import konformitaet_db as kdb
        for k in kdb.list_konformitaet(CRA_DB, projekt_name):
            if version and str(k.get("release_version") or "") != str(version):
                continue
            if k.get("doc_ausgestellt") or k.get("freigabe_status") == "freigegeben":
                doc_ok = True
                break
    except Exception:  # noqa: BLE001
        pass
    if not doc_ok:
        offene_punkte.append({"typ": "doc", "titel": "EU-Konformitätserklärung (DoC) nicht ausgestellt",
                              "hinweis": "DoC ausstellen/freigeben", "link": "konformitaet"})

    reife = berechne_reifegrad(bewertungen)

    # Ampel
    if offen == 0 and offene_krit == 0 and annex_ok and doc_ok:
        ampel = "gruen"
    elif offen == 0 and offene_krit == 0:
        ampel = "bedingt"   # inhaltlich konform, aber Akte/DoC noch unvollständig
    else:
        ampel = "rot"

    konform = ampel == "gruen"
    return {
        "projekt_name": projekt_name,
        "version": version,
        "ampel": ampel,
        "konform": konform,
        "erfuellt": erfuellt,
        "begruendet_akzeptiert": begruendet,
        "offen": offen,
        "gesamt_anforderungen": len(CRA_ANFORDERUNGEN),
        "offene_kritische_schwachstellen": offene_krit,
        "annex_vollstaendig": annex_ok,
        "doc_ausgestellt": doc_ok,
        "reifegrad_pct": reife.get("gesamt_pct"),
        "offene_punkte": offene_punkte,
        "abweichungen": abweichungen,
    }
