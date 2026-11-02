"""Nur ein Publisher für die Release-Images, und der Deploy merkt es (#1738, #1719/E4).

Ab 7.4.8 baut und veröffentlicht ``aics-public`` die Release-Images; das private
Repo pusht nur noch Dev-Tags. Zwei Publisher für denselben Tag wären schlimmer als
einer am falschen Ort: dann entscheidet die Reihenfolge, welches Artefakt unter
``7.4.8`` liegt, und der Deploy startet, sobald der erste fertig ist.

Die Umstellung hat eine Eigenschaft, die sie ohne Prüfung unsichtbar macht: Beide
Workflows schreiben in **dieselben** GHCR-Pakete, und am Tag ist nicht zu erkennen,
wer ihn gesetzt hat. Ein versehentlich privat gebautes Image deployt sich genauso
klaglos — nur testen wir dann wieder ein anderes Artefakt als der Kunde bekommt.
Deshalb hier zwei Gruppen: die Workflow-Dateien als Text, und der Riegel im
Deploy-Weg.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PRIVAT = REPO / '.github/workflows/docker-publish.yml'
VORLAGE = REPO / '.public-templates/.github-workflows-public/docker-publish.yml'


# ── Wer veröffentlicht ──────────────────────────────────────────────────────
def test_privat_hat_keinen_tag_trigger():
    """Ein Tag-Push darf im privaten Repo keinen Release-Build mehr auslösen."""
    text = PRIVAT.read_text()
    trigger = text.split('jobs:', 1)[0]
    assert "tags:" not in trigger, (
        'Der private Workflow reagiert noch auf Tags — damit pushen zwei '
        'Workflows denselben Semver-Tag und es ist Zufall, welcher gewinnt.')


def test_privat_vergibt_weder_semver_noch_latest():
    """``latest`` hing an jedem main-Push, zeigte also auf ungetesteten Stand.

    Öffentlich gebaut entsteht es nur beim Release-Mirror und bedeutet dann
    wirklich „letzte veröffentlichte Version".
    """
    text = PRIVAT.read_text()
    assert 'type=semver' not in text, 'privater Workflow vergibt noch Semver-Tags'
    assert 'value=latest' not in text, 'privater Workflow vergibt noch `latest`'


def test_privat_behaelt_den_notweg():
    """Dev-Image + Dockerfile-Check je Merge bleiben — ``:sha-`` ist der Notweg,
    wenn der öffentliche Build einmal klemmt (``AICS_IMAGE_TAG=sha-abc1234``)."""
    text = PRIVAT.read_text()
    assert 'type=sha,prefix=sha-' in text, 'ohne sha-Tag gibt es keinen Notweg'
    assert 'branches: [main]' in text, 'der Dockerfile-Check je Merge fehlt'


def test_oeffentliche_vorlage_vergibt_die_release_tags():
    """Was privat wegfällt, muss öffentlich entstehen — sonst gibt es zum
    Release gar kein Image."""
    text = VORLAGE.read_text()
    assert 'type=semver,pattern={{version}}' in text
    assert 'type=raw,value=latest' in text
    assert "tags: ['v*.*.*']" in text, 'ohne Tag-Trigger kein Semver-Tag'


def test_oeffentliche_laeufe_serialisieren_sich():
    """Der Mirror pusht ``main`` und den Tag gleichzeitig → zwei Läufe, die
    beide ``sha-<kurz>`` pushen und signieren.

    Abbrechen darf sich dabei keiner: dann fehlt am Ende entweder der
    Semver-Tag oder ``latest``.
    """
    text = VORLAGE.read_text()
    assert 'concurrency:' in text, 'keine Serialisierung der beiden Läufe'
    assert 'cancel-in-progress: false' in text, (
        'cancel-in-progress würde den zweiten Lauf abwürgen und damit einen '
        'der Release-Tags verlieren')


# ── Der Riegel im Deploy ────────────────────────────────────────────────────
def test_deploy_erwartet_das_oeffentliche_repo():
    from scripts.ops.portainer_redeploy import ERWARTETE_QUELLE, QUELL_LABEL

    assert ERWARTETE_QUELLE == 'https://github.com/martinzeifang/aics-public'
    assert QUELL_LABEL == 'org.opencontainers.image.source'


class _FakePortainer:
    """Portainer-Doppel: liefert je Image-Ref ein Label."""

    def __init__(self, labels: dict[str, str | None]) -> None:
        self.labels = labels

    def image_quelle(self, endpoint: int, ref: str) -> str:  # noqa: ARG002
        return self.labels.get(ref) or ''


_WEB = 'ghcr.io/martinzeifang/ai_compliance_suite:7.4.8'
_NGINX = 'ghcr.io/martinzeifang/aics-nginx:7.4.8'
_PUBLIC = 'https://github.com/martinzeifang/aics-public'
_PRIVAT = 'https://github.com/martinzeifang/AI_Compliance_Suite'


def test_oeffentliches_image_wird_durchgelassen():
    from scripts.ops.portainer_redeploy import pruefe_quelle

    p = _FakePortainer({_WEB: _PUBLIC, _NGINX: _PUBLIC})
    quellen = pruefe_quelle(p, 2, [_WEB, _NGINX])  # type: ignore[arg-type]
    assert len(quellen) == 2 and all(_PUBLIC in z for z in quellen)


def test_privat_gebautes_image_wird_abgewiesen():
    """Der eigentliche Zweck: nach der Umstellung soll ein privat gebautes
    Image nicht mehr unbemerkt auf einem Stack landen."""
    from scripts.ops.portainer_redeploy import DeployFehler, pruefe_quelle

    p = _FakePortainer({_WEB: _PRIVAT, _NGINX: _PUBLIC})
    with pytest.raises(DeployFehler, match='PUBLISH_IMAGES'):
        pruefe_quelle(p, 2, [_WEB, _NGINX])  # type: ignore[arg-type]


def test_image_ohne_label_wird_abgewiesen():
    """Ein Image ohne Herkunftsangabe ist genau das, was hier nicht deployt
    werden soll — fail-closed wie überall sonst."""
    from scripts.ops.portainer_redeploy import DeployFehler, pruefe_quelle

    p = _FakePortainer({_WEB: None, _NGINX: _PUBLIC})
    with pytest.raises(DeployFehler, match='kein Label'):
        pruefe_quelle(p, 2, [_WEB, _NGINX])  # type: ignore[arg-type]


def test_pruefung_ist_abschaltbar_aber_standard():
    """Default-Verhalten ist die Prüfung; ``--quelle beliebig`` ist die
    bewusste Ausnahme (z. B. Dev-Image auf dem Test-Stack)."""
    import inspect

    from scripts.ops.portainer_redeploy import ERWARTETE_QUELLE, main, redeploy

    assert inspect.signature(redeploy).parameters['quelle'].default == ERWARTETE_QUELLE
    quelle = re.search(r'--quelle', inspect.getsource(main))
    assert quelle, 'kein --quelle-Schalter in der Kommandozeile'
    assert '"beliebig"' in inspect.getsource(main)


def test_env_setzen_laesst_alles_andere_in_ruhe():
    """``AICS_LICENSE_SERVER_URL`` muss in die Stacks, ohne deren übrige Env
    anzufassen — dort stehen Datenbank-Passwort, JWT-Secret und Pool-Grenzen."""
    from scripts.ops.portainer_redeploy import DeployFehler, _env_setzen, parse_env

    assert parse_env(['A=1', 'B=https://x:8444']) == {'A': '1', 'B': 'https://x:8444'}
    assert parse_env(None) == {}
    assert parse_env(['LEER=']) == {'LEER': ''}
    with pytest.raises(DeployFehler, match='NAME=WERT'):
        parse_env(['kein_gleichheitszeichen'])

    env = [{'name': 'POSTGRES_PASSWORD', 'value': 'geheim'},
           {'name': 'AICS_IMAGE_TAG', 'value': '7.4.7'}]
    assert _env_setzen(env, 'AICS_LICENSE_SERVER_URL', 'https://x:8444') is None
    assert _env_setzen(env, 'AICS_IMAGE_TAG', '7.4.8') == '7.4.7'
    assert {e['name']: e['value'] for e in env} == {
        'POSTGRES_PASSWORD': 'geheim',
        'AICS_IMAGE_TAG': '7.4.8',
        'AICS_LICENSE_SERVER_URL': 'https://x:8444'}


# ── Das öffentliche Image ist nicht byte-gleich ─────────────────────────────
def test_nur_die_lizenz_url_wird_in_code_umgeschrieben():
    """``sanitize-public.sh`` ersetzt die interne IP per ``sed`` im **ganzen**
    Baum — auch in Python-Dateien.

    Damit unterscheidet sich das öffentlich gebaute Image im Code vom privaten,
    und zwar unsichtbar: Der Build läuft, die Datei ist nur anders. Beim
    Vergleich der beiden 7.4.7-Images war genau eine Python-Datei betroffen
    (`shared/licensing/config.py`, zwei Zeilen). Kommt eine weitere hinzu, soll
    das eine Entscheidung sein und kein Nebeneffekt — eine Adresse der eigenen
    Umgebung gehört ohnehin nicht in den Code, sondern in die Installation.
    """
    ip = '192.168.20' + '.10'          # nicht als Literal, sonst findet der Test sich selbst
    erlaubt = {'shared/licensing/config.py'}
    kopiert = [z.split()[-2] for z in (REPO / 'Dockerfile').read_text().splitlines()
               if z.startswith('COPY --chown=aics:aics') and z.rstrip().endswith('/')]
    treffer = set()
    for eintrag in kopiert:
        basis = REPO / eintrag.rstrip('/')
        if not basis.is_dir():
            continue
        for pfad in basis.rglob('*.py'):
            if ip in pfad.read_text(encoding='utf-8', errors='replace'):
                treffer.add(str(pfad.relative_to(REPO)))
    assert treffer <= erlaubt, (
        f'Diese Dateien landen im Image und tragen die interne Adresse: '
        f'{sorted(treffer - erlaubt)}. sanitize-public.sh schreibt sie beim '
        f'Spiegeln um — das oeffentlich gebaute Image weicht dann dort ab.')


def test_warnung_wenn_der_eingebaute_default_greift(monkeypatch, caplog):
    """Prod lief auf dem eingebauten Default (``license_server.json`` ohne
    ``server_url``, keine Env) — im öffentlichen Image wäre das eine
    Platzhalter-Adresse und das fail-closed Lizenz-Gate hätte Schreibsperren
    daraus gemacht. Still darf dieser Rückfall deshalb nicht sein.
    """
    import logging

    from shared.licensing import config as lic

    monkeypatch.setattr(lic, 'load_settings', lambda: {})
    monkeypatch.delenv('AICS_LICENSE_SERVER_URL', raising=False)
    monkeypatch.setattr(lic, '_default_gewarnt', False)

    with caplog.at_level(logging.WARNING):
        cfg = lic.get_client_config()

    assert cfg.server_url == lic._DEFAULT_SERVER_URL.rstrip('/')
    assert any('Kein Lizenzserver konfiguriert' in r.message for r in caplog.records), \
        'der Rueckfall auf den eingebauten Default erscheint nicht im Log'

    # Zweiter Aufruf schweigt — die Funktion laeuft bei jedem Heartbeat.
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        lic.get_client_config()
    assert not [r for r in caplog.records
                if 'Kein Lizenzserver konfiguriert' in r.message]


def test_konfigurierte_url_schlaegt_den_default(monkeypatch):
    """Env und Datei müssen weiter greifen — sonst wäre der Fix die Störung."""
    from shared.licensing import config as lic

    monkeypatch.setattr(lic, 'load_settings', lambda: {})
    monkeypatch.setenv('AICS_LICENSE_SERVER_URL', 'https://lic.example.test:8444')
    assert lic.get_client_config().server_url == 'https://lic.example.test:8444'

    monkeypatch.setattr(lic, 'load_settings',
                        lambda: {'server_url': 'https://aus.datei:8444'})
    assert lic.get_client_config().server_url == 'https://aus.datei:8444'


# ── Der Quellbaum muss das Produkt tragen ───────────────────────────────────
def test_sync_exclude_nimmt_nichts_weg_was_der_webserver_importiert():
    """``.sync-exclude`` wird durch die Umstellung tragend: Was dort steht,
    fehlt dann wirklich im Produkt.

    Geprüft wird die Richtung, die beim Build nicht auffällt — ein Modul, das
    der Webserver importiert, aber der öffentliche Baum nicht enthält. Das ist
    die Fehlerklasse von #1505 (fehlende ``normen.json`` → Build grün, Laufzeit
    500), hier für Python-Module und ohne Netz oder Container.
    """
    import ast

    muster = [z.strip() for z in (REPO / '.sync-exclude').read_text().splitlines()
              if z.strip() and not z.startswith('#')]

    def ausgeschlossen(rel: str) -> bool:
        for m in muster:
            if m.startswith('/'):
                if rel == m[1:] or rel.startswith(m[1:]):
                    return True
            elif m.endswith('/'):
                if rel == m[:-1] or rel.startswith(m) or f'/{m}' in f'/{rel}':
                    return True
            elif m.startswith('*/'):
                if rel.endswith(m[1:]) and '/' in rel:
                    return True
            elif m.startswith('*'):
                if rel.endswith(m[1:]):
                    return True
            elif m.endswith('*'):
                if Path(rel).name.startswith(m[:-1]):
                    return True
            elif rel == m or Path(rel).name == m:
                return True
        return False

    pakete = {p.name for p in REPO.iterdir()
              if p.is_dir() and (p / '__init__.py').exists()}

    def datei(modul: str) -> Path | None:
        teil = modul.replace('.', '/')
        for k in (REPO / f'{teil}.py', REPO / teil / '__init__.py'):
            if k.exists():
                return k
        return None

    gesehen: set[str] = set()
    offen = [(str(p.relative_to(REPO)).replace('/', '.')[:-3], p)
             for p in (REPO / 'server').rglob('*.py')]
    offen.append(('wsgi', REPO / 'wsgi.py'))
    verloren: dict[str, str] = {}

    while offen:
        modul, pfad = offen.pop()
        if modul in gesehen:
            continue
        gesehen.add(modul)
        try:
            baum = ast.parse(pfad.read_text(encoding='utf-8', errors='replace'))
        except SyntaxError:
            continue
        ziele: set[str] = set()
        paket = modul.rsplit('.', 1)[0] if '.' in modul else ''
        for n in ast.walk(baum):
            if isinstance(n, ast.Import):
                ziele |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                basis = n.module or ''
                if n.level:
                    vor = paket
                    for _ in range(n.level - 1):
                        vor = vor.rsplit('.', 1)[0] if '.' in vor else ''
                    basis = f'{vor}.{n.module}' if n.module else vor
                if basis:
                    ziele.add(basis)
                    ziele |= {f'{basis}.{a.name}' for a in n.names}
        for ziel in ziele:
            if ziel.split('.')[0] not in pakete:
                continue
            quelle = datei(ziel)
            if quelle is None:
                continue          # Funktion/Klasse, kein Modul
            rel = str(quelle.relative_to(REPO))
            if ausgeschlossen(rel):
                verloren[rel] = modul
                continue
            offen.append((ziel, quelle))

    assert not verloren, (
        'Diese Module importiert der Webserver, .sync-exclude nimmt sie aber '
        f'aus dem oeffentlichen Baum: {verloren}')
    assert len(gesehen) > 300, f'nur {len(gesehen)} Module erfasst — Scan defekt?'
