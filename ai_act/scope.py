"""AI Act — hybrides Projektmodell Organisation + KI-System (Epic #1540).

Bezugseinheit der Verordnung (EU) 2024/1689 ist das **KI-System**. Die meisten
Pflichten (Art. 6/9–15/27/43/49/72/73) gelten je System; einige gelten
**unternehmensweit** (Art. 4 AI-Literacy, Art. 17 QMS).

Modell (additiv, ohne Datenmigration):

- **Organisations-Projekt** — das bisherige Firmen-Projekt (Name = Firma, #430/#434).
  Alle Alt-Projekte gelten als Organisation.
- **KI-System-Projekt** — ``<Firma> – <Produkt>``, ``meta.scope='system'``,
  ``organisation`` = Firma, ``produkt`` = Produkt (analog CRA #435). Wird gezielt
  angelegt, nicht automatisch je Produkt: nicht jedes Produkt ist ein KI-System.

Firmenweite Bereiche werden in KI-System-Projekten über
:func:`org_projekt_name` auf das Organisations-Projekt aufgelöst.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_act.db import list_projekte, load_projekt, save_projekt

SCOPE_ORG = "organisation"
SCOPE_SYSTEM = "system"


def _meta(p: dict[str, Any] | None) -> dict[str, Any]:
    m = (p or {}).get("meta")
    return m if isinstance(m, dict) else {}


def scope_of(p: dict[str, Any] | None) -> str:
    """``system`` nur bei explizitem ``meta.scope`` — Alt-Projekte sind Organisation."""
    return SCOPE_SYSTEM if _meta(p).get("scope") == SCOPE_SYSTEM else SCOPE_ORG


def system_name(firma: str, produkt: str) -> str:
    """Projektname eines KI-Systems — gleiches Schema wie CRA (#435)."""
    return f"{firma.strip()} – {produkt.strip()}"


def _all(db_path: Path) -> list[dict[str, Any]]:
    return [p for p in (load_projekt(db_path, n) for n in list_projekte(db_path)) if p]


def org_projekt_name(db_path: Path, projekt_name: str) -> str | None:
    """Organisations-Projekt zu einem Projekt.

    Organisation → sich selbst. KI-System → Projekt der Firma (``organisation``):
    bevorzugt das gleichnamige Firmen-Projekt, sonst ein anderes Organisations-
    Projekt derselben Firma. ``None``, wenn das Projekt nicht existiert; fehlt das
    Organisations-Projekt, bleibt das KI-System bei sich selbst (kein Datenverlust).
    """
    p = load_projekt(db_path, projekt_name)
    if not p:
        return None
    if scope_of(p) == SCOPE_ORG:
        return projekt_name
    firma = (p.get("organisation") or "").strip()
    if not firma:
        return projekt_name
    direct = load_projekt(db_path, firma)
    if direct and scope_of(direct) == SCOPE_ORG:
        return firma
    for q in _all(db_path):
        if scope_of(q) == SCOPE_ORG and (q.get("organisation") or "").strip() == firma:
            return q["name"]
    return projekt_name


def list_systeme(db_path: Path, firma: str) -> list[dict[str, Any]]:
    """KI-System-Projekte einer Firma (nach Name sortiert)."""
    firma = (firma or "").strip()
    out = [p for p in _all(db_path)
           if scope_of(p) == SCOPE_SYSTEM and (p.get("organisation") or "").strip() == firma]
    return sorted(out, key=lambda p: p.get("name", ""))


def create_system(db_path: Path, org_projekt: str, produkt: str,
                  beschreibung: str = "", *, uebernehmen: bool = False) -> tuple[dict[str, Any], bool]:
    """KI-System-Projekt zur Firma eines Organisations-Projekts anlegen (idempotent).

    Returns ``(projekt, created)``. ``ValueError`` bei ungültiger Eingabe oder
    Namenskonflikt mit einem fremden Projekt.
    """
    org = load_projekt(db_path, org_projekt)
    if not org:
        raise LookupError("Projekt nicht gefunden")
    produkt = (produkt or "").strip()
    if not produkt:
        raise ValueError('Feld "produkt" ist Pflicht')
    firma = (org.get("organisation") or "").strip() or org_projekt
    name = system_name(firma, produkt)
    existing = load_projekt(db_path, name)
    if existing:
        if scope_of(existing) == SCOPE_SYSTEM and (existing.get("organisation") or "").strip() == firma:
            return existing, False
        raise ValueError(f'Projektname "{name}" ist bereits vergeben')
    erstes = not list_systeme(db_path, firma)
    save_projekt(db_path, name=name, organisation=firma, produkt=produkt,
                 beschreibung=(beschreibung or "").strip(),
                 meta={"scope": SCOPE_SYSTEM})
    # #1562: Beim ERSTEN KI-System optional die bisherigen Bewertungen der
    # Organisation übernehmen — danach führt die Organisation keine System-Controls.
    if uebernehmen and erstes:
        copy_org_data(db_path, org.get("name") or org_projekt, name)
    return load_projekt(db_path, name) or {}, True


# ─── #1562: Organisation führt keine System-Controls, sobald KI-Systeme existieren ──

# Systembezogene Register, die beim ersten KI-System aus der Organisation
# übernommen werden (Kopie — das Original bleibt unverändert erhalten). Bis dahin
# stand die Organisation stellvertretend für dieses eine System — daher auch die
# Vorfälle. Bewusst NICHT: AI-Literacy (firmenweit, #1542).
SYSTEM_TABLES = (
    "ai_act_bewertungen", "ai_act_overlay_checks", "aiact_owasp_llm_checks",
    "aiact_system_doku", "aiact_data_governance", "aiact_human_oversight",
    "aiact_post_market_monitoring", "aiact_art5_screening", "aiact_fria",
    "aiact_conformity", "aiact_gpai_klassifizierung", "aiact_gpai_checks",
    "aiact_incidents", "aiact_gpai_incidents",
)
# Verknüpfungen/Kontext im meta_json, die das KI-System von der Organisation erbt.
SYSTEM_META_KEYS = (
    "linked_risk_projekt", "linked_cra_projekt", "cra_link_override",
    "vcs_publish", "risiko_stufe", "risikostufe", "klassifizierung",
)

LOCKED_MESSAGE = ("Diese Organisation hat KI-Systeme — systembezogene Controls werden "
                  "je KI-System gepflegt, nicht in der Organisation (#1562).")


def org_controls_locked(db_path: Path, projekt_name: str) -> bool:
    """True, wenn ``projekt_name`` eine Organisation ist, zu deren Firma bereits
    mindestens ein KI-System existiert (dann keine System-Controls mehr dort)."""
    p = load_projekt(db_path, projekt_name)
    if not p or scope_of(p) != SCOPE_ORG:
        return False
    firma = (p.get("organisation") or "").strip() or projekt_name
    return bool(list_systeme(db_path, firma))


def has_org_data(db_path: Path, projekt_name: str) -> bool:
    """Gibt es in der Organisation bereits Bewertungen (Übernahme sinnvoll)?"""
    from ai_act.db import _connect
    con = _connect(db_path)
    try:
        row = con.execute("SELECT COUNT(*) FROM ai_act_bewertungen WHERE projekt_name=?",
                          (projekt_name,)).fetchone()
        return bool(row and row[0])
    except Exception:  # noqa: BLE001
        return False
    finally:
        con.close()


def copy_org_data(db_path: Path, org_projekt: str, system_projekt: str) -> dict[str, int]:
    """Systembezogene Daten der Organisation in ein KI-System kopieren (idempotent).

    Je Tabelle eigene Verbindung: eine fehlende Tabelle (Modul-Register noch nie
    benutzt) bricht unter Postgres sonst die ganze Transaktion ab.
    """
    from ai_act.db import _connect, update_projekt_meta
    copied: dict[str, int] = {}
    for table in SYSTEM_TABLES:
        con = _connect(db_path)
        try:
            rows = [dict(r) for r in con.execute(
                f"SELECT * FROM {table} WHERE projekt_name=?", (org_projekt,)).fetchall()]
            n = 0
            for row in rows:
                row.pop("id", None)
                row["projekt_name"] = system_projekt
                cols = list(row)
                con.execute(
                    f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
                    "ON CONFLICT DO NOTHING", tuple(row[c] for c in cols))
                n += 1
            con.commit()
            if n:
                copied[table] = n
        except Exception:  # noqa: BLE001 — Tabelle (noch) nicht vorhanden
            try:
                con.rollback()
            except Exception:  # noqa: BLE001
                pass
        finally:
            con.close()
    org = load_projekt(db_path, org_projekt) or {}
    sysp = load_projekt(db_path, system_projekt) or {}
    org_meta, sys_meta = _meta(org), dict(_meta(sysp))
    for k in SYSTEM_META_KEYS:
        if k in org_meta and k not in sys_meta:
            sys_meta[k] = org_meta[k]
    update_projekt_meta(db_path, system_projekt, sys_meta)
    return copied


def make_org_write_guard(db_path: Path, *, allowed_suffixes: tuple[str, ...] = ()):
    """``before_request``-Hook für AI-Act-Blueprints: blockt Schreibzugriffe auf
    System-Controls einer Organisation mit KI-Systemen (409).

    ``allowed_suffixes``: Pfad-Endungen hinter ``/projekte/<p>``, die erlaubt bleiben
    ("" = das Projekt selbst, z. B. Umbenennen/Firma zuordnen/Löschen)."""
    from flask import jsonify, request

    def _guard():
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        name = (request.view_args or {}).get("projekt_name")
        if not name:
            return None
        rule = str(request.url_rule or "")
        marker = "/projekte/<projekt_name>"
        suffix = rule.split(marker, 1)[1] if marker in rule else ""
        if suffix.lstrip("/") in allowed_suffixes:
            return None
        try:
            locked = org_controls_locked(db_path, name)
        except Exception:  # noqa: BLE001 — Guard darf nie selbst einen 500 erzeugen
            locked = False
        if locked:
            return jsonify({"error": LOCKED_MESSAGE, "code": "org_controls_locked"}), 409
        return None

    return _guard
