from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.config_io import safe_load_json_config, safe_save_json_config


DEFAULT_CONFIG_PATH = Path("gutachten.config.json")

# Vorschlag-Texte für den Prüfungsfokus je Framework
PRUEFUNGSFOKUS_VORSCHLAEGE: dict[str, str] = {
    "DORA": (
        "IKT-Risikomanagement und digitale Betriebsstabilität gemäß DORA (EU 2022/2554). "
        "Bewertung der Governance, Incident-Meldeprozesse, IKT-Drittparteiensteuerung "
        "und Testverfahren für Finanzunternehmen."
    ),
    "NIS2": (
        "Cybersicherheitsanforderungen gemäß NIS2-Richtlinie (EU 2022/2555 / BSIG 2025). "
        "Prüfung der Risikomaßnahmen, Meldepflichten, Lieferkettensteuerung und "
        "Business-Continuity-Maßnahmen für wesentliche und wichtige Einrichtungen."
    ),
    "CRA": (
        "Cyber Resilience Act (EU 2024/2847). Konformitätsbewertung von Produkten "
        "mit digitalen Elementen: Sicherheitsanforderungen in der Entwicklung, "
        "Schwachstellenmanagement und Marktüberwachungspflichten."
    ),
    "ISO27001": (
        "Informationssicherheits-Managementsystem gemäß ISO/IEC 27001:2022. "
        "Gap-Analyse der Annex-A-Controls, ISMS-Reife und Zertifizierungsbereitschaft."
    ),
    "DSGVO": (
        "Datenschutz-Grundverordnung (EU 2016/679). Prüfung der Rechtmäßigkeit der "
        "Datenverarbeitung, Betroffenenrechte, technische und organisatorische Maßnahmen (TOM), "
        "Datenschutz-Folgenabschätzung (DSFA) sowie Auftragsverarbeitungsverträge (AVV)."
    ),
    "AI_ACT": (
        "EU AI Act (EU 2024/1689). Konformitätsbewertung von KI-Systemen: Klassifizierung "
        "nach Risikoklassen, Anforderungen an Hochrisiko-KI-Systeme (Transparenz, Robustheit, "
        "menschliche Aufsicht), Registrierungspflichten und technische Dokumentation."
    ),
    "BSI": (
        "BSI IT-Grundschutz (BSI-Standard 200-2). Gap-Analyse der Sicherheitsmaßnahmen "
        "gemäß IT-Grundschutz-Kompendium: Basis-, Standard- und Kern-Absicherung, "
        "relevante Bausteine, Gefährdungen und Umsetzungsempfehlungen."
    ),
}

ALL_FRAMEWORKS = ["DORA", "NIS2", "CRA", "ISO27001", "DSGVO", "AI_ACT", "BSI"]


def default_config() -> dict[str, Any]:
    return {
        "paths": {
            "dora_dir": "data/dora_downloads",
            "cra_dir": "data/cra_resources",
            "nis2_dir": "data/nis2_resources",
            "iso_dir": "data/iso27001_questionnaires",
            "dsgvo_dir": "data/dsgvo_resources",
            "ai_act_dir": "data/ai_act_resources",
            "bsi_dir": "data/bsi_resources",
            "db_path": "data/db/gutachten.sqlite",
            "prompts_dir": "out/gutachten/prompts",
            "answers_dir": "out/gutachten/answers",
            "fragebogen_dir": "out/gutachten/fragebogen",
            "ausgefuellt_dir": "out/gutachten/ausgefuellt",
            "gutachten_dir": "out/gutachten/gutachten",
        },
        "ui": {
            "projekt_name": "Demoprojekt",
            "frameworks": ["DORA", "NIS2", "CRA", "ISO27001"],
            "pruefungsfokus": "",
            "debug_mode": False,
            "test_mode": False,
        },
        "prompt": {
            "fragen_header": (
                "Du bist ein erfahrener IT-Compliance-Auditor. Erstelle präzise, "
                "offene Interviewfragen für ein Compliance-Gutachten. Die Fragen sollen "
                "konkrete Nachweise und Prozesse erfragen, nicht nur Ja/Nein-Antworten "
                "ermöglichen. Beziehe dich auf die relevanten Artikel/Kapitel der "
                "Regulierungen. Formuliere auf Deutsch."
            ),
            "gutachten_header": (
                "Du bist ein erfahrener IT-Compliance-Auditor. Erstelle auf Basis der "
                "vorliegenden Interview-Antworten ein strukturiertes Compliance-Gutachten "
                "auf Deutsch. Bewerte den Erfüllungsgrad je Framework, identifiziere "
                "Lücken und formuliere konkrete Handlungsempfehlungen."
            ),
            "bewertung_skala": [
                "erfüllt",
                "teilweise erfüllt",
                "nicht erfüllt",
                "nicht anwendbar",
            ],
            "fragen_batch_size": 15,
        },
    }


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        cfg = default_config()
        save_config(cfg, path)
        return cfg
    data = safe_load_json_config(path)
    merged = default_config()
    _deep_update(merged, data)
    return merged


def _deep_update(dst: dict[str, Any], src: dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_update(dst[k], v)
        else:
            dst[k] = v


def save_config(cfg: dict[str, Any], path: Path | None = None) -> None:
    path = path or DEFAULT_CONFIG_PATH
    safe_save_json_config(path, cfg)


def cfg_get(cfg: dict[str, Any], dotted: str, default: Any) -> Any:
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def pruefungsfokus_vorschlag(frameworks: list[str]) -> str:
    """Erstellt einen kombinierten Vorschlagstext für die ausgewählten Frameworks."""
    parts = []
    for fw in frameworks:
        if fw in PRUEFUNGSFOKUS_VORSCHLAEGE:
            parts.append(PRUEFUNGSFOKUS_VORSCHLAEGE[fw])
    return "\n\n".join(parts)
