"""#1516 — App-Version-Fallback-Kette (ENV → /app/VERSION → package.json → unknown)."""
import server.api.admin as adm


def test_version_from_env(monkeypatch):
    monkeypatch.setenv('APP_VERSION', '9.9.9')
    assert adm._app_version() == '9.9.9'


def test_env_unknown_falls_through_to_packagejson(monkeypatch):
    # 'unknown' in der ENV soll NICHT als Version durchgereicht werden (Dockerfile-Default).
    monkeypatch.setenv('APP_VERSION', 'unknown')
    v = adm._app_version()
    # Im Dev-Repo existiert frontend/package.json → echte Version, nicht 'unknown'.
    assert v and v != 'unknown'


def test_empty_env_falls_through(monkeypatch):
    monkeypatch.delenv('APP_VERSION', raising=False)
    v = adm._app_version()
    assert v  # liefert package.json-Version oder 'unknown', nie leer
