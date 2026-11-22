"""#1917 — der Archivstand darf nicht gegen die Aufbewahrungsgrenze zählen.

Art. 13 Abs. 13 verlangt die technische Dokumentation und die
EU-Konformitätserklärung **zehn Jahre** nach dem Inverkehrbringen — oder für
die Dauer des Unterstützungszeitraums, je nachdem, welcher Zeitraum länger
ist. Für dieses Produkt: bis mindestens Oktober 2036, je Fassung ab deren
Inverkehrbringen.

Die nächtliche Sicherung hält **fünf** Stände (``backup_retention_count``).
Nach fünf Nächten ist der Stand von vorgestern weg. Das ist richtig für den
Wiederanlauf, wofür sie gebaut ist, und falsch für die Aufbewahrung — die
Unterscheidung ist der eigentliche Inhalt von ``docs/cra/aufbewahrung.md``,
Festlegung 8.

**Nebenbefund, der hier mit auffiel:** Die Positivliste ``_BACKUP_ID`` kannte
nur ``backup_``. Damit ließ sich eine ``pre_restore_``-Kopie auflisten, aber
**nicht herunterladen und nicht zurückspielen** — also genau der Rückweg
nicht, den #1785 für den misslungenen Restore versprochen hat.
"""

from __future__ import annotations

import re
from pathlib import Path

_ADMIN = Path(__file__).resolve().parents[1] / "server" / "api" / "admin.py"


def _quelle() -> str:
    return _ADMIN.read_text(encoding="utf-8")


def _ohne_kommentare(text: str) -> str:
    return re.sub(r"#.*", "", text)


def test_positivliste_kennt_alle_drei_arten() -> None:
    from server.api.admin import _BACKUP_ARTEN, _BACKUP_ID
    assert set(_BACKUP_ARTEN) == {"backup", "pre_restore", "archiv"}
    for erlaubt in ("backup_20261102_010000", "pre_restore_20261102_010000",
                    "archiv_8.3.1_20261102_204500"):
        assert _BACKUP_ID.match(erlaubt), erlaubt


def test_positivliste_bleibt_eine_positivliste() -> None:
    """Was nicht ausdrücklich erlaubt ist, fällt durch — auch in einer
    Schreibweise, an die eine Negativliste nicht gedacht hätte (#1784)."""
    from server.api.admin import _BACKUP_ID
    for abgelehnt in ("../etc/passwd", "archiv_../x", "fremd_1", "backup",
                      "/absolut", "archiv_x/y"):
        assert not _BACKUP_ID.match(abgelehnt), abgelehnt


def test_archivstand_wird_nicht_rotiert() -> None:
    """Geprüft wird das Programm, nicht die Erzählung: Die Rotation darf
    ausschließlich ``backup_*`` einsammeln."""
    quelle = _ohne_kommentare(_quelle())
    start = quelle.index("def _aufraeumen_nach_aufbewahrung")
    rumpf = quelle[start:start + 1400]
    globs = re.findall(r"BACKUP_DIR\.glob\('([^']+)'\)", rumpf)
    assert globs == ["backup_*.zip"], (
        "Die Rotation darf nur turnusmäßige Sicherungen einsammeln. Gefunden: "
        f"{globs}. `archiv_*` ist der Nachweis, den sie sonst genau dann "
        "wegräumt, wenn über Jahre viele entstehen."
    )


def test_anlegen_ueberspringt_die_rotation_beim_archivstand() -> None:
    quelle = _ohne_kommentare(_quelle())
    start = quelle.index("def create_backup")
    rumpf = quelle[start:start + 2200]
    assert "if not ist_archiv:" in rumpf and "_aufraeumen_nach_aufbewahrung()" in rumpf, (
        "Ein Archivstand darf beim Anlegen keine turnusmäßige Sicherung "
        "verdrängen — die Rotation gehört hinter die Fallunterscheidung."
    )


def test_archivstand_verlangt_die_fassung() -> None:
    """Aufbewahrt wird **je Fassung** (Art. 13 Abs. 13). Ein Archivstand ohne
    Fassungsangabe ließe sich später keinem Inverkehrbringen zuordnen."""
    quelle = _quelle()
    start = quelle.index("def create_backup")
    rumpf = quelle[start:start + 2200]
    assert "ist die Fassung anzugeben" in rumpf
    assert "archiv_{fassung}_" in rumpf


def test_liste_zeigt_archivstaende_und_ob_rotiert_wird() -> None:
    quelle = _ohne_kommentare(_quelle())
    start = quelle.index("def list_backups")
    rumpf = quelle[start:start + 1800]
    assert "archiv_*.zip" in rumpf, (
        "Ein Archiv, das die Anwendung nicht anzeigt, ist für die jährliche "
        "Rückprobe unerreichbar (Festlegung 6 in aufbewahrung.md)."
    )
    assert "'rotiert'" in rumpf, (
        "Ohne diese Angabe sieht ein Archivstand in der Liste aus wie eine "
        "Sicherung, die bald weggeräumt wird."
    )
