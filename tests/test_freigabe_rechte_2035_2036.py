"""Nachweisintegrität und das Recht am rohen Tabellen-Dump — #2035/#2036.

Zwei Fundstellen aus dem Prüflauf 09.11.2026. Beide sind keine Datenpreisgabe
durch einen Defekt, sondern ein **Maßstab**, der an zwei Stellen verschieden
gesetzt war — und in beiden Fällen kam eine Fachrolle durch, die es nicht
sollte.

#2035 — Der Zustandsautomat aus #1743 blieb unversehrt, das **Artefakt**, das
er schützen soll, entstand daneben: ``add_final`` prüfte nichts. Für einen
Prüfer ist das archivierte PDF der Nachweis, nicht der Datenbankzustand des
Vorgangs.

#2036 — ``admin:audit`` ist das Recht auf den Revisionspfad und hängt an
``RoleEnum.AUDITOR``. Daran hing ein rohes ``SELECT *`` über zehn Schemata,
einschließlich der Benutzertabelle.

Geprüft wird das Programm, nicht die Erzählung (#1834): Die Decorator-Prüfung
läuft über den Syntaxbaum, die Rollen-Zusagen über die echten
Permission-Mengen, die Vorbedingung im Rundlauf gegen die Datenbank.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJ = "pytest-freigabe-2035"
VERSION = "9.0.0"
DB = Path("data/db/cra.sqlite")

EINREICHER = "editor@example.com"
APPROVER = "compliance@example.com"


# ── Werkzeug ─────────────────────────────────────────────────────────────────

def _dekorator_argumente(pfad: str, funktion: str) -> list[str]:
    """Die Literal-Argumente aller Dekoratoren einer Funktion (ohne Kommentare)."""
    baum = ast.parse(Path(pfad).read_text(encoding="utf-8"))
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.FunctionDef) and knoten.name == funktion:
            werte: list[str] = []
            for deko in knoten.decorator_list:
                if not isinstance(deko, ast.Call):
                    continue
                for arg in deko.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        werte.append(arg.value)
                    elif isinstance(arg, ast.Attribute):
                        werte.append(arg.attr)
            return werte
    raise AssertionError(f"{funktion}() nicht in {pfad}")


@pytest.fixture
def vorgang():
    """Release-Vorgang im Zustand ``entwurf``, bewertungsfähig."""
    from cra import konformitaet_db as kdb
    from cra.db import save_projekt

    save_projekt(DB, PROJ, unternehmen="Pytest AG", produkt="Prüfling")
    kdb.save_konformitaet(DB, PROJ, {"release_version": VERSION,
                                     "bewertungsweg": "A",
                                     "bewertung_abgeschlossen": True})
    return DB


# ══════════════════════════════════════════════════════════════════════════════
# #2035 — die Vorbedingung liegt in der Speicherfunktion
# ══════════════════════════════════════════════════════════════════════════════

def test_ohne_vorgang_kein_nachweis():
    """Ein Nachweis ohne Release-Vorgang wäre nicht zuordenbar."""
    from cra import konformitaet_final_db as fdb

    with pytest.raises(ValueError) as fehler:
        fdb.add_final(DB, "pytest-gibt-es-nicht-2035", version="1.0.0",
                      pdf_bytes=b"%PDF-1.7", ampel="gruen",
                      freigegeben_von=APPROVER)
    assert "Vorgang" in str(fehler.value)


@pytest.mark.parametrize("status", ["entwurf", "in_pruefung", "zurueckgewiesen"])
def test_nachweis_erst_nach_der_freigabe(vorgang, status):
    """Das Szenario aus #2035: Ein Konto mit Rolle ``cra_editor`` reicht ein,
    scheitert an der Freigabe (409 Vier-Augen) — und archivierte anschließend
    über diesen Weg einen unveränderlichen, SHA-256-gesicherten
    Konformitätsnachweis mit sich selbst als Freigeber.
    """
    from cra import konformitaet_db as kdb
    from cra import konformitaet_final_db as fdb

    if status in ("in_pruefung", "zurueckgewiesen"):
        kdb.einreichen(DB, PROJ, VERSION, von=EINREICHER)
    if status == "zurueckgewiesen":
        kdb.zurueckweisen(DB, PROJ, VERSION, von=APPROVER, grund="Unterlagen fehlen")

    with pytest.raises(ValueError) as fehler:
        fdb.add_final(DB, PROJ, version=VERSION, pdf_bytes=b"%PDF-1.7",
                      ampel="rot", freigegeben_von=EINREICHER)
    assert status in str(fehler.value) or "Freigabe" in str(fehler.value)

    # Und es liegt nichts im Archiv — das ist die Zusage, auf die es ankommt.
    assert fdb.list_final(DB, PROJ) == []


def test_nach_der_freigabe_wird_archiviert(vorgang):
    """Der vorgesehene Ablauf bleibt möglich — sonst wäre die Reparatur eine Sperre."""
    from cra import konformitaet_db as kdb
    from cra import konformitaet_final_db as fdb

    kdb.einreichen(DB, PROJ, VERSION, von=EINREICHER)
    kdb.freigeben(DB, PROJ, VERSION, von=APPROVER)
    rec = fdb.add_final(DB, PROJ, version=VERSION, pdf_bytes=b"%PDF-1.7 nachweis",
                        ampel="bedingt", freigegeben_von=APPROVER)
    assert rec["sha256"] and rec["version"] == VERSION
    assert len(fdb.list_final(DB, PROJ)) == 1


def test_der_einreicher_archiviert_nicht(vorgang):
    """Vier-Augen auch am Artefakt: Der Archiveintrag trägt ``freigegeben_von``.

    Ist das der Einreicher, behauptet das Archiv eine Freigabe durch ihn,
    obwohl ein anderer sie erteilt hat.
    """
    from cra import konformitaet_db as kdb
    from cra import konformitaet_final_db as fdb
    from shared.vier_augen import VierAugenVerletzt

    kdb.einreichen(DB, PROJ, VERSION, von=EINREICHER)
    kdb.freigeben(DB, PROJ, VERSION, von=APPROVER)
    with pytest.raises(VierAugenVerletzt):
        fdb.add_final(DB, PROJ, version=VERSION, pdf_bytes=b"%PDF-1.7",
                      ampel="gruen", freigegeben_von=EINREICHER)


def test_die_pruefung_steht_in_der_speicherfunktion():
    """Nicht im Endpunkt — die Lehre aus #1760 und #1780.

    Stünde sie nur im Endpunkt, wäre jeder zweite Aufrufer (Skript, Migration,
    künftige Route) wieder ungeschützt.
    """
    baum = ast.parse(Path("cra/konformitaet_final_db.py").read_text(encoding="utf-8"))
    fn = next(k for k in ast.walk(baum)
              if isinstance(k, ast.FunctionDef) and k.name == "add_final")
    gerufen = {n.func.id for n in ast.walk(fn)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_pruefe_vorbedingung" in gerufen


def test_nachweis_freigeben_verlangt_approve():
    """Zwei Freigabe-Routen in einer Datei hatten zwei Maßstäbe (#2035)."""
    args = _dekorator_argumente("server/api/cra_konformitaet.py",
                                "konformitaet_nachweis_freigeben")
    assert "CRA_APPROVE" in args, f"Dekoratoren: {args}"
    assert "CRA_EXPORT" not in args


def test_cra_editor_hat_kein_approve():
    """Die Rolle, die im gemeldeten Szenario durchkam.

    ``_ohne_signoff`` entfernt ``CRA_APPROVE`` und lässt ``CRA_WRITE`` und
    ``CRA_EXPORT`` stehen — deshalb genügte Exportrecht nicht als Schranke.
    """
    from server.models.permission import Permission, RoleEnum, ROLE_PERMISSIONS

    editor = set(ROLE_PERMISSIONS[RoleEnum.CRA_EDITOR])
    assert Permission.CRA_EXPORT in editor, "Exportrecht hat die Rolle weiterhin"
    assert Permission.CRA_APPROVE not in editor, (
        "cra_editor darf nicht freigeben — sonst ist die Rollentrennung "
        "aus #1743 dekorativ")


# ══════════════════════════════════════════════════════════════════════════════
# #2036 — der rohe Tabellen-Dump
# ══════════════════════════════════════════════════════════════════════════════

def test_die_benutzertabelle_ist_nicht_mehr_erreichbar():
    """``SELECT *`` auf ``users`` gab ``password_hash``, ``totp_secret``,
    ``totp_backup_codes_json``, ``roles_json`` und ``allowed_firmen_json``
    unverändert heraus — ``_serialize_user`` streift den Hash ab, dieser Weg
    nicht."""
    from server.api.admin import ALLOWED_DBS

    assert "users" not in ALLOWED_DBS


def test_keine_datenbank_mit_zugangsdaten_in_der_positivliste():
    """Breiter als der Einzelfall: Nichts, was nach Konten klingt, gehört hier hin."""
    from server.api.admin import ALLOWED_DBS

    verdaechtig = {k for k in ALLOWED_DBS
                   if any(w in k.lower() for w in ("user", "benutzer", "auth",
                                                   "login", "credential", "secret"))}
    assert not verdaechtig, f"Zugangsdaten im DB-Viewer: {sorted(verdaechtig)}"


@pytest.mark.parametrize("funktion", ["list_dbs", "list_db_tables", "query_db_table"])
def test_db_viewer_verlangt_admin_config(funktion):
    """``admin:audit`` ist das Recht auf den Revisionspfad, nicht auf Rohdaten."""
    args = _dekorator_argumente("server/api/admin.py", funktion)
    assert "admin:config" in args, f"{funktion}: {args}"
    assert "admin:audit" not in args


def test_auditor_kommt_nicht_mehr_an_die_rohdaten():
    """Der gemeldete Fall: Rolle ``auditor`` + ``allowed_firmen=[1]`` — genau so
    eingerichtet, damit ein externer Prüfer EINEN Mandanten begutachtet.

    ``admin:audit`` muss die Rolle behalten (das ist ihr Zweck), ``admin:config``
    darf sie nicht haben.
    """
    from server.models.permission import Permission, RoleEnum, ROLE_PERMISSIONS

    auditor = set(ROLE_PERMISSIONS[RoleEnum.AUDITOR])
    assert Permission.ADMIN_AUDIT in auditor, (
        "der Revisionspfad bleibt der Zweck dieser Rolle")
    assert Permission.ADMIN_CONFIG not in auditor, (
        "auditor käme sonst weiter an den rohen Tabellen-Dump")


def test_der_vergleich_im_eigenen_haus_stimmt_jetzt():
    """Backup-Download (#1784) und Support-Bundle (#1509) verlangen längst
    ``admin:config`` — der DB-Viewer ist vergleichbar und war schwächer."""
    for funktion in ("download_backup", "support_bundle"):
        try:
            args = _dekorator_argumente("server/api/admin.py", funktion)
        except AssertionError:
            continue  # Funktion anders benannt — dann trägt dieser Test nichts
        assert "admin:config" in args, f"{funktion}: {args}"
