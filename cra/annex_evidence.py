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

def _firma_doc_baustein() -> dict[str, str]:
    """Firmen-Nachweis ``doc_type``/Tag-Stichwort → Anhang-VII-Baustein.

    **Abgeleitet aus ``annex_vii.PUNKTE``, nicht von Hand geführt (#2003).**
    Vorher stand hier eine Liste mit **9** Dokumentarten, während der
    Anhang-VII-Katalog **17** erklärt. Die acht fehlenden —
    ``produktbeschreibung``, ``description``, ``psirt``, ``vuln``,
    ``advisory``, ``doc``, ``konformitaetserklaerung``, ``test`` — wurden im
    firmenweiten Store **nie angerechnet**, während dieselbe Angabe über
    ``cra_dokumente`` zählte. Getroffen waren ausgerechnet zwei Pflichtinhalte:
    die Produktbeschreibung (Anhang VII Nr. 1) und der PSIRT-Prozess
    (Nr. 2 Buchst. b).

    Nichts schlug fehl — der Nachweis lag in der Akte und wurde nur nicht
    gezählt. Das ist die Spiegel-Liste aus #1731/#1735 in ihrer leisen Form und
    die Fehlerklasse aus #1870: eine Zuordnungstabelle über Zeichenketten, die
    anderswo entstehen, ohne Prüfer, der beide Seiten gegeneinander hält.
    Abgeleitet kann sie nicht mehr auseinanderlaufen.

    Reihenfolge: lange Stichwörter zuerst. ``risk`` ist ein Teilstring von
    ``risikobewertung`` und ``test`` einer von ``testbericht`` und ``pentest``
    — hier führen beide zum selben Baustein, aber die Regel soll nicht vom
    Zufall der Dict-Reihenfolge abhängen.
    """
    from cra.annex_vii import PUNKTE

    aus: dict[str, str] = {}
    for p in PUNKTE:
        baustein = str(getattr(p, "baustein_key", "") or getattr(p, "key", "") or "")
        if not baustein:
            continue
        for dt in (getattr(p, "doc_types", None) or []):
            aus.setdefault(str(dt), baustein)
    return {k: aus[k] for k in sorted(aus, key=len, reverse=True)}


_FIRMA_DOC_BAUSTEIN: dict[str, str] = _firma_doc_baustein()

#: Stichwörter, die **nur genau** passen dürfen, nicht als Teilstring.
#: ``doc`` steckt in „dokumentation", „docx" und „doc_id" — als Teilstring
#: würde ein beliebiges Dokument als Beleg der EU-Konformitätserklärung
#: gezählt. Eine falsche Anrechnung ist schlimmer als eine fehlende: Sie sieht
#: aus wie ein Nachweis.
_NUR_GENAU: frozenset[str] = frozenset({"doc", "test", "risk"})


def _eintrag(baustein: str, label: str, quelle: str, modul: str,
             open_url: str | None = None, datei_fehlt: bool = False) -> dict[str, Any]:
    e = {"baustein": baustein, "label": label, "quelle": quelle, "modul": modul,
         "herkunft": "auto"}
    if open_url:
        e["open_url"] = open_url
    if datei_fehlt:
        # #1974: Der Beleg steht in der Akte, die Datei liegt nicht mehr da.
        # Beides gehört in die Matrix — die Zeile ist der Hinweis, dass das
        # Dokument einmal da war, und das Fehlen ist der Mangel. Die **Zählung
        # bleibt unverändert**: Diesen Eintrag wegzulassen würde den
        # Vollständigkeitsstand verändern, und das ist eine fachliche
        # Entscheidung über die Akte, nicht ein Nebenbefund dieses Vorgangs.
        e["datei_fehlt"] = True
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
            from evidence.db import DATEI_FEHLT, dateistand
            from evidence.db import list_documents as list_ev
            evs = list_ev(EVIDENCE_DB, firmen_id=str(fid))
            stand = dateistand(evs)
            for ev in evs:
                hint = str(ev.doc_type or "").lower()
                tag_liste = [str(t).lower().strip() for t in (ev.tags or [])]
                tags = " ".join(tag_liste)
                bt = None
                for key, b in _FIRMA_DOC_BAUSTEIN.items():
                    # #2003: Kurze Stichwörter nur genau — `doc` als Teilstring
                    # fände „dokumentation" und zählte ein beliebiges Dokument
                    # als Beleg der EU-Konformitätserklärung.
                    if key in _NUR_GENAU:
                        if hint == key or key in tag_liste:
                            bt = b
                            break
                        continue
                    if key in hint or key in tags:
                        bt = b
                        break
                if bt:
                    fehlt = stand.get(ev.id) == DATEI_FEHLT
                    label = f"Firmen-Nachweis {ev.filename!r}"
                    if fehlt:
                        # Im Label, nicht nur im Datenfeld: Diese Matrix wird
                        # gelesen, nicht ausgewertet — ein Haken, der nur
                        # programmatisch einen Mangel trägt, ist für den
                        # Anwender kein Mangel.
                        label += " — Datei fehlt (nur in der Akte verzeichnet)"
                    add(_eintrag(bt, label, "🏢 Firmen-Nachweis", "firma",
                                 datei_fehlt=fehlt))
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
