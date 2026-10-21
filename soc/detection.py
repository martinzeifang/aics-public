"""SOC — Detection-Use-Case-Register + MITRE-ATT&CK-Coverage (#1321).

Register der Detektions-Use-Cases (welche Bedrohung erkennt welche Wazuh-Regel),
gemappt auf MITRE ATT&CK, mit Status und einer Coverage-Heatmap (Tactic×Technique
mit abgedeckt/teilweise/Lücke) plus Lücken-Report.

Normbezug: BSI DER.1 (Detektion) · NIST CSF Detect · SOC-CMM Services/Technology.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from soc.attack import TACTICS, TECHNIQUES, normalize_technique
from soc.db import _connect, ensure_db, list_rules

# Coverage-Quellen für die Heatmap (#1349):
#   alarme    – nur Techniken, die real in synchronisierten Alarmen auftauchten
#   regelwerk – nur Techniken, die durch das installierte Wazuh-Regelwerk abgedeckt sind
#   beides    – beide Signale + aktive Use-Cases (Default, abwärtskompatibel zu #1321)
COVERAGE_SOURCES = ("alarme", "regelwerk", "beides")


def _to_dict(r) -> dict[str, Any]:
    d = dict(r)
    d["attack_techniques"] = json.loads(d.get("attack_techniques") or "[]")
    return d


def list_usecases(db_path: Path) -> list[dict[str, Any]]:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        return [_to_dict(r) for r in con.execute(
            "SELECT * FROM soc_detection_usecases ORDER BY name").fetchall()]
    finally:
        con.close()


def save_usecase(db_path: Path, *, id: int | None = None, name: str, bedrohung: str = "",
                 attack_techniques: list[str] | None = None, wazuh_rules: str = "",
                 status: str = "geplant", datenquelle: str = "", notizen: str = "") -> int:
    ensure_db(db_path)
    techs = json.dumps([normalize_technique(t) for t in (attack_techniques or []) if t])
    con = _connect(db_path)
    try:
        if id:
            con.execute("""UPDATE soc_detection_usecases SET name=?, bedrohung=?,
                           attack_techniques=?, wazuh_rules=?, status=?, datenquelle=?,
                           notizen=?, updated_at=aics_now() WHERE id=?""",
                        (name, bedrohung, techs, wazuh_rules, status, datenquelle, notizen, id))
            uid = id
        else:
            cur = con.execute("""INSERT INTO soc_detection_usecases(name, bedrohung,
                                 attack_techniques, wazuh_rules, status, datenquelle, notizen)
                                 VALUES(?,?,?,?,?,?,?)""",
                              (name, bedrohung, techs, wazuh_rules, status, datenquelle, notizen))
            uid = int(cur.lastrowid)
        con.commit()
        return uid
    finally:
        con.close()


def delete_usecase(db_path: Path, usecase_id: int) -> None:
    ensure_db(db_path)
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM soc_detection_usecases WHERE id=?", (usecase_id,))
        con.commit()
    finally:
        con.close()


def _techniques_from_alerts(db_path: Path) -> set[str]:
    """Welche ATT&CK-Techniken sind real in Alarmen aufgetaucht (rule.mitre)."""
    con = _connect(db_path)
    seen: set[str] = set()
    try:
        for r in con.execute("SELECT mitre FROM soc_alerts WHERE mitre != '{}'").fetchall():
            try:
                m = json.loads(r["mitre"] or "{}")
            except (ValueError, TypeError):
                continue
            for t in (m.get("id") or []) + (m.get("technique") or []):
                tid = normalize_technique(str(t))
                if tid.startswith("T"):
                    seen.add(tid)
    finally:
        con.close()
    return seen


def techniques_from_ruleset(db_path: Path) -> dict[str, list[int]]:
    """ATT&CK-Technik → sortierte Rule-IDs, die sie laut Regelwerk abdecken (#1349).

    Quelle ist der Regelwerk-Cache aus #1348 (``soc_rules``, gespeist aus der
    Manager-API ``GET /rules``). „Capability"-Sicht: unabhängig davon, ob je ein
    Alarm gefeuert hat. Sub-Techniken (``T1566.001``) werden auf die Basistechnik
    abgebildet.
    """
    out: dict[str, set[int]] = {}
    data = list_rules(db_path, limit=100000)
    for rule in data.get("rules", []):
        rid = rule.get("id")
        try:
            rid = int(rid)
        except (TypeError, ValueError):
            continue
        for t in rule.get("mitre") or []:
            tid = normalize_technique(str(t))
            if tid.startswith("T"):
                out.setdefault(tid, set()).add(rid)
    return {tid: sorted(rids) for tid, rids in out.items()}


def _normalize_source(source: str | None) -> str:
    s = (source or "beides").strip().lower()
    return s if s in COVERAGE_SOURCES else "beides"


def attack_coverage(db_path: Path, *, source: str = "beides") -> dict[str, Any]:
    """Coverage-Heatmap: je Referenz-Technik abgedeckt/teilweise/Lücke.

    Drei orthogonale Detektions-Signale je Technik (#1349):
      - aktiver Use-Case (kuratiert, ``status='aktiv'``)
      - reale Alarme (``by_alerts``) — Technik tauchte in synchronisierten Alarmen auf
      - Regelwerk-Abdeckung (``by_rules`` = Rule-IDs) — Capability aus ``soc_rules``

    Der ``source``-Schalter steuert, welche Signale als „covered" zählen:
      - ``alarme``    → nur reale Alarme + aktive Use-Cases
      - ``regelwerk`` → nur Regelwerk-Abdeckung + aktive Use-Cases
      - ``beides``    → alle drei (Default)
    In jedem Fall gilt: Use-Case in Tuning/geplant ⇒ ``partial``; sonst ``gap``.
    """
    source = _normalize_source(source)
    usecases = list_usecases(db_path)
    active, planned = set(), set()
    for uc in usecases:
        target = active if uc["status"] == "aktiv" else planned
        for t in uc["attack_techniques"]:
            target.add(normalize_technique(t))
    alert_techs = _techniques_from_alerts(db_path)
    rule_map = techniques_from_ruleset(db_path)
    rule_techs = set(rule_map.keys())

    use_alerts = source in ("alarme", "beides")
    use_rules = source in ("regelwerk", "beides")

    def _status(tid: str) -> str:
        if tid in active:
            return "covered"
        if use_alerts and tid in alert_techs:
            return "covered"
        if use_rules and tid in rule_techs:
            return "covered"
        if tid in planned:
            return "partial"
        return "gap"

    by_tactic: dict[str, list[dict[str, Any]]] = {name: [] for _, name in TACTICS}
    counts = {"covered": 0, "partial": 0, "gap": 0}
    # Union aus kuratierter Referenz + ALLEN real im Regelwerk/in Alarmen/in Use-Cases
    # gefundenen Techniken → die tatsächliche (oft breite) Wazuh-Abdeckung wird sichtbar,
    # statt nur eine 39er-Teilmenge zu zeigen (#1358-Fix). Unbekannte Technik-Namen
    # fallen auf die ID + Taktik „Sonstige" zurück.
    all_tids = (set(TECHNIQUES) | rule_techs | alert_techs | active | planned)
    all_tids.discard("")
    for tid in sorted(all_tids):
        meta = TECHNIQUES.get(tid)
        tname, tactic = (meta[0], meta[1]) if meta else (tid, "Sonstige")
        st = _status(tid)
        counts[st] += 1
        by_tactic.setdefault(tactic, []).append({
            "id": tid, "name": tname, "status": st,
            "by_alerts": tid in alert_techs,
            "by_rules": rule_map.get(tid, []),
        })
    total = sum(counts.values()) or 1
    return {
        "source": source,
        "sources": list(COVERAGE_SOURCES),
        "tactics": [{"id": tid, "name": name, "techniques": by_tactic.get(name, [])}
                    for tid, name in TACTICS],
        "counts": counts,
        "coverage_pct": round((counts["covered"] + 0.5 * counts["partial"]) / total, 3),
        "alert_techniques": sorted(alert_techs),
        "rule_techniques": sorted(rule_techs),
    }


def coverage_gaps(db_path: Path, *, source: str = "beides") -> list[dict[str, str]]:
    """Referenz-Techniken ohne jede Detektion (Lücken-Report)."""
    cov = attack_coverage(db_path, source=source)
    out = []
    for tac in cov["tactics"]:
        for t in tac["techniques"]:
            if t["status"] == "gap":
                out.append({"id": t["id"], "name": t["name"], "tactic": tac["name"]})
    return out


def suggestions_from_alerts(db_path: Path) -> list[dict[str, str]]:
    """Techniken aus realen Alarmen, die noch in keinem Use-Case gepflegt sind."""
    mapped = set()
    for uc in list_usecases(db_path):
        mapped.update(normalize_technique(t) for t in uc["attack_techniques"])
    out = []
    for tid in sorted(_techniques_from_alerts(db_path) - mapped):
        meta = TECHNIQUES.get(tid)
        out.append({"id": tid, "name": meta[0] if meta else tid, "tactic": meta[1] if meta else "—"})
    return out


def usecase_candidates_from_rules(db_path: Path) -> list[dict[str, Any]]:
    """Auto-Vorschläge: durch Regelwerk abgedeckte Techniken ohne aktiven Use-Case (#1349).

    Pro Referenz-Technik, die laut Regelwerk (``soc_rules``) abgedeckt ist, aber
    noch in keinem **aktiven** Use-Case gepflegt wird, ein Kandidat mit den
    verknüpften Rule-IDs. Per 1-Klick (:func:`confirm_usecase`) bestätigbar.
    Bereits *aktive* Techniken werden übersprungen; ``existing_usecase_id`` weist
    auf einen vorhandenen, noch nicht aktiven Use-Case hin (→ Aktivierung statt Neuanlage).
    """
    rule_map = techniques_from_ruleset(db_path)
    usecases = list_usecases(db_path)
    active_techs: set[str] = set()
    existing_by_tech: dict[str, dict[str, Any]] = {}
    for uc in usecases:
        techs = [normalize_technique(t) for t in uc["attack_techniques"]]
        if uc["status"] == "aktiv":
            active_techs.update(techs)
        for t in techs:
            existing_by_tech.setdefault(t, uc)
    out: list[dict[str, Any]] = []
    for tid in sorted(rule_map):
        if tid in active_techs:
            continue
        meta = TECHNIQUES.get(tid)
        name, tactic = (meta[0], meta[1]) if meta else (tid, "Sonstige")
        rule_ids = rule_map[tid]
        existing = existing_by_tech.get(tid)
        out.append({
            "technique": tid,
            "name": name,
            "tactic": tactic,
            "rule_ids": rule_ids,
            "rule_count": len(rule_ids),
            "existing_usecase_id": existing["id"] if existing else None,
        })
    return out


def _rules_label(rule_ids: list[int]) -> str:
    return ", ".join(str(r) for r in rule_ids)


def confirm_usecase(db_path: Path, *, technique: str, rule_ids: list[int] | None = None,
                    existing_usecase_id: int | None = None, name: str = "",
                    bedrohung: str = "") -> int:
    """1-Klick-Bestätigung eines Regelwerk-Kandidaten → Use-Case ``aktiv`` (#1349).

    Legt einen neuen Use-Case (``status='aktiv'``) für die Technik an bzw.
    aktiviert einen vorhandenen, und verknüpft die abdeckenden Rule-IDs im
    bestehenden ``wazuh_rules``-Freitextfeld (kein neues Schema nötig). Returns
    die Use-Case-ID.
    """
    tid = normalize_technique(technique)
    rule_ids = sorted({int(r) for r in (rule_ids or [])})
    meta = TECHNIQUES.get(tid)
    label = name or (f"{tid} {meta[0]}" if meta else tid)
    threat = bedrohung or (meta[1] if meta else "")
    rules_txt = _rules_label(rule_ids)
    if existing_usecase_id:
        # Vorhandenen Use-Case aktivieren, Rule-IDs ergänzen (idempotent).
        for uc in list_usecases(db_path):
            if uc["id"] == int(existing_usecase_id):
                techs = uc["attack_techniques"]
                if tid not in [normalize_technique(t) for t in techs]:
                    techs = techs + [tid]
                merged = _merge_rule_label(uc.get("wazuh_rules", ""), rule_ids)
                return save_usecase(
                    db_path, id=uc["id"], name=uc["name"] or label,
                    bedrohung=uc.get("bedrohung", "") or threat,
                    attack_techniques=techs, wazuh_rules=merged, status="aktiv",
                    datenquelle=uc.get("datenquelle", ""), notizen=uc.get("notizen", ""))
    return save_usecase(
        db_path, name=label, bedrohung=threat, attack_techniques=[tid],
        wazuh_rules=rules_txt, status="aktiv", datenquelle="Wazuh-Regelwerk (#1349)",
        notizen=f"Auto-bestätigt aus Regelwerk-Abdeckung — Regeln: {rules_txt or '—'}")


def _merge_rule_label(existing: str, rule_ids: list[int]) -> str:
    """Bestehendes ``wazuh_rules``-Freitextfeld um Rule-IDs ergänzen (dedupliziert numerisch)."""
    have: set[str] = set()
    for tok in (existing or "").replace(";", ",").split(","):
        tok = tok.strip()
        if tok:
            have.add(tok)
    for r in rule_ids:
        have.add(str(int(r)))
    # numerische Tokens sortiert voran, Rest (Gruppen) hintendran
    nums = sorted((t for t in have if t.isdigit()), key=int)
    rest = sorted(t for t in have if not t.isdigit())
    return ", ".join([*nums, *rest])
