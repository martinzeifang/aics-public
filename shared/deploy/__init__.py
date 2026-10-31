"""Deploy- und Release-Kanal-Logik, geteilt zwischen Webdienst und Skripten (#1908).

``scripts/`` liegt **nicht** im Laufzeit-Image (siehe ``Dockerfile``) — die
gemeinsame Logik gehört deshalb hierher, nicht in ``scripts/ops/``. Sonst
entstünde eine zweite Fassung im Webdienst, und beim nächsten Fund wäre sie nur
an einer Stelle behoben (#1731/#1735).
"""
