"""Automatische Annex-VII-Nachweise (#1606).

Die Annex-VII-Vollständigkeitsmatrix (``traceability_db.annex_vii_status``) prüfte
bisher nur manuell erfasste ``cra_dokumente``. Vorhandene Nachweise in CRA (SBOM,
Threat-Model, Schwachstellen, DoC), in den verwalteten Dokumenten (📄-Tab) und
modulübergreifend (verknüpfte Risikobewertung, firmenweiter Nachweis-Store) wurden
nicht angerechnet.

Dieses Modul sammelt solche Nachweise **nur zur Anzeige** (keine ``cra_dokumente``-
Dubletten). Jeder Eintrag: ``{label, quelle, modul, herkunft='auto', open_url?}``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

CRA_DB = Path("data/db/cra.sqlite")
RB_DB = Path("data/db/risikobewertung.sqlite")
EVIDENCE_DB = Path("data/db/evidence.sqlite")

# Managed-Doc-Typ (DocSpec-key) → Annex-VII-Baustein.
_MANAGED_DOC_BAUSTEIN: dict[str, str] = {
    "technische_doku_annex_vii": "produktbeschreibung",
    "konformitaetserklaerung": "doc",
    "benutzeranleitung_annex_ii": "anleitung",
    "sbom_begleitdoc": "sbom",
    "vuln_disclosure_policy": "vuln_handling",
    "update_policy": "vuln_handling",
}

# Firmen-Nachweis doc_type/Tag-Stichwort → Baustein (Stufe 2, modulübergreifend).
_FIRMA_DOC_BAUSTEIN: dict[str, str] = {
    "pentest": "testberichte",
    "sbom": "sbom",
    "risikobewertung": "risikobewertung",
    "risk": "risikobewertung",
    "testbericht": "testberichte",
    "architektur": "design",
    "design": "design",
    "anleitung": "anleitung",
    "manual": "anleitung",
}


def _eintrag(baustein: str, label: str, quelle: str, modul: str,
             open_url: str | None = None) -> dict[str, Any]:
    e = {"baustein": baustein, "label": label, "quelle": quelle, "modul": modul,
         "herkunft": "auto"}
    if open_url:
        e["open_url"] = open_url
    return e


def auto_nachweise(db_path: Path, projekt_name: str) -> dict[str, list[dict[str, Any]]]:
    """Automatisch erkannte Nachweise je Baustein. Best effort — Fehler je Quelle
    werden verschluckt, nie wird der Aufruf abgebrochen."""
    out: dict[str, list[dict[str, Any]]] = {}

    def add(e: dict[str, Any]) -> None:
        out.setdefault(e["baustein"], []).append(e)

    projekt = None
    try:
        from cra.db import load_projekt
        projekt = load_projekt(db_path, projekt_name)
    except Exception:  # noqa: BLE001
        projekt = None

    # ── Stufe 1: CRA-interne strukturierte Quellen ─────────────────────────────
    # Produktbeschreibung aus Projekt-Stammdaten
    try:
        if projekt and (str(projekt.get("beschreibung") or "").strip()
                        or str(projekt.get("produkt") or "").strip()):
            add(_eintrag("produktbeschreibung", "Projekt-Stammdaten (Produkt/Beschreibung)",
                         "🏷️ CRA-Stammdaten", "cra"))
    except Exception:  # noqa: BLE001
        pass

    # SBOM
    try:
        from cra.db import list_sbom
        sboms = list_sbom(db_path, projekt_name)
        if sboms:
            s = sboms[0]
            add(_eintrag("sbom", f"SBOM erfasst (Format {s.get('sbom_format') or '—'}, "
                         f"Release {s.get('release_version') or '—'})", "🧩 CRA-SBOM", "cra"))
    except Exception:  # noqa: BLE001
        pass

    # Threat-Model → Design + Risikobewertung
    try:
        from cra.db import load_threatmodel
        tm = load_threatmodel(db_path, projekt_name)
        if tm:
            fw = tm.get("framework") or "—"
            add(_eintrag("design", f"Threat-Model (Framework {fw})", "🧵 CRA-Threat-Model", "cra"))
            add(_eintrag("risikobewertung", f"Threat-Model (Framework {fw})",
                         "🧵 CRA-Threat-Model", "cra"))
    except Exception:  # noqa: BLE001
        pass

    # Verknüpfte Risikobewertung (Cybersicherheits-Risikobewertung)
    try:
        meta = projekt.get("meta") if isinstance(projekt, dict) and isinstance(projekt.get("meta"), dict) else {}
        rb_name = (meta.get("linked_risk_projekt") or "").strip()
        if rb_name:
            from risikobewertung.db import load_risiken
            risiken = load_risiken(RB_DB, rb_name)
            if risiken:
                bewertet = sum(1 for r in risiken if r.get("risikowert") is not None)
                add(_eintrag("risikobewertung",
                             f"Verknüpfte Risikobewertung {rb_name!r} ({len(risiken)} Risiken, {bewertet} bewertet)", "📊 Risikobewertung", "risikobewertung"))
    except Exception:  # noqa: BLE001
        pass

    # Vulnerability-Handling: Schwachstellen + Sync-Status
    try:
        from cra.db import list_vuln, load_sync_state
        vulns = list_vuln(db_path, projekt_name)
        if vulns:
            add(_eintrag("vuln_handling", f"{len(vulns)} Schwachstelle(n) im Register",
                         "🐞 CRA-Schwachstellen", "cra"))
        st = load_sync_state(db_path, projekt_name)
        if st:
            add(_eintrag("vuln_handling", "Automatischer Schwachstellen-Sync konfiguriert",
                         "🔄 CRA-Vuln-Sync", "cra"))
    except Exception:  # noqa: BLE001
        pass

    # EU-Konformitätserklärung (DoC)
    try:
        from cra import konformitaet_db as kdb
        for k in kdb.list_konformitaet(db_path, projekt_name):
            if k.get("doc_ausgestellt") or k.get("freigabe_status") == "freigegeben":
                ver = k.get("release_version") or "—"
                add(_eintrag("doc", f"EU-Konformitätserklärung ausgestellt (Release {ver})",
                             "📜 CRA-Konformität", "cra"))
                break
    except Exception:  # noqa: BLE001
        pass

    # Verwaltete Dokumente (📄-Tab) → Baustein
    try:
        from shared.documents.db import list_documents as list_managed
        for d in list_managed(db_path, "cra", projekt_name):
            bt = _MANAGED_DOC_BAUSTEIN.get(str(d.get("doc_type") or ""))
            if bt:
                add(_eintrag(bt, f"Dokument {d.get('titel') or d.get('doc_type')!r} ({d.get('status') or 'entwurf'})", "📄 Dokument", "cra"))
    except Exception:  # noqa: BLE001
        pass

    # ── Stufe 2: modulübergreifend — firmenweiter Nachweis-Store ────────────────
    try:
        fid = projekt.get("firmen_id") if isinstance(projekt, dict) else None
        if fid:
            from evidence.db import list_documents as list_ev
            for ev in list_ev(EVIDENCE_DB, firmen_id=str(fid)):
                hint = str(ev.doc_type or "").lower()
                tags = " ".join(str(t).lower() for t in (ev.tags or []))
                bt = None
                for key, b in _FIRMA_DOC_BAUSTEIN.items():
                    if key in hint or key in tags:
                        bt = b
                        break
                if bt:
                    add(_eintrag(bt, f"Firmen-Nachweis {ev.filename!r}", "🏢 Firmen-Nachweis", "firma"))
    except Exception:  # noqa: BLE001
        pass

    # ── #1763: Punkte ohne eigene Dokumentart ─────────────────────────────────
    # „Bewertung der grundlegenden Anforderungen", „Unterstützungszeitraum" und
    # „angewandte Normen" standen bisher **gar nicht** in der Beleg-Matrix — die
    # zeigte acht Bausteine, die Inhalts-Checkliste zehn, und damit zwei
    # Vollständigkeitsquoten für dieselbe Akte. Ihr Nachweis liegt nicht in einem
    # hochgeladenen Dokument, sondern in den Registern der Anwendung; genau dort
    # wird er jetzt abgeholt.
    try:
        from cra.db import load_bewertungen

        bew = load_bewertungen(db_path, projekt_name) or {}
        bewertet = sum(1 for v in bew.values()
                       if isinstance(v, dict) and (v.get("bewertung") or 0) > 0)
        if bewertet:
            add(_eintrag("essentielle_anforderungen",
                         f"{bewertet} bewertete Anforderungen im Register",
                         "✅ CRA-Anforderungen", "cra"))
    except Exception:  # noqa: BLE001
        pass

    try:
        from cra.db import load_support_period

        sp = load_support_period(db_path, projekt_name) or {}
        if sp.get("markteintritt_datum") and sp.get("support_jahre"):
            add(_eintrag("support_zeitraum",
                         f"Unterstützungszeitraum bis {str(sp.get('eol_datum') or '')[:10]}",
                         "🗓️ Support-Zeitraum", "cra"))
    except Exception:  # noqa: BLE001
        pass

    try:
        from cra import konformitaet_db as _kdb

        for k in _kdb.list_konformitaet(db_path, projekt_name) or []:
            normen = str(((k.get("doc") or {}).get("normen_text")
                          or (k.get("doc") or {}).get("normen") or "")).strip()
            if normen:
                add(_eintrag("normen", "Angewandte Normen in der Konformitätsakte",
                             "📏 Konformität", "cra"))
                break
    except Exception:  # noqa: BLE001
        pass

    return out
