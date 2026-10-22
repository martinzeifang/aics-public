"""#1517 — SOC-Netz-Entkopplung: dediziertes DB-Netz, SOC-web nicht im Suite-App-Netz.

Regressions-Guard für die Compose-/Generator-Quelle (kein Docker nötig)."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_compose_has_dedicated_db_network():
    d = yaml.safe_load((ROOT / 'docker-compose.yml').read_text(encoding='utf-8'))
    assert 'db-network' in (d.get('networks') or {}), 'db-network fehlt im Suite-Compose'
    pg_nets = d['services']['postgres']['networks']
    assert 'app-network' in pg_nets, 'postgres muss am app-network bleiben'
    assert 'db-network' in pg_nets, 'postgres muss zusätzlich am db-network hängen'


def test_soc_generator_defaults_to_db_network_not_app_network():
    src = (ROOT / 'scripts' / 'create_soc_stack.py').read_text(encoding='utf-8')
    # Der Default für das externe Netz ist jetzt das DB-Netz (nicht das App-Netz).
    assert 'or "ai-compliance-suite_db-network"' in src
    # Der frühere App-Netz-Default darf NICHT mehr der aktive Default sein.
    assert 'or "ai-compliance-suite_app-network"' not in src
