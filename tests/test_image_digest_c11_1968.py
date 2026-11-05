"""Die laufende Anwendung kennt ihren eigenen Digest (C11, #1968).

**Dieselbe Klasse wie B6/#1966, und sie war genauso unsichtbar.**
``APP_IMAGE_DIGEST`` ist im ``Dockerfile`` deklariert und wird von
``server/api/admin.py`` ausgelesen — **gesetzt hat es nie etwas.** Die
Abweichung C11 trug die Begründung „der Digest steht erst nach dem Bau fest"
und las sich damit wie eine technische Unmöglichkeit. Für den *Bau* stimmt das;
beim **Deploy** ist der Digest längst bekannt — ``pruefe_quelle`` und
``pruefe_signatur`` arbeiten damit, bevor ein Dienst angefasst wird.

Was fehlte, war nicht die Information, sondern der Weg: niemand schrieb sie
dorthin, wo die Anwendung sie liest. Genau wie bei B6, wo der Schlüssel
setzbar, aber nicht umschlüsselbar war.

**Die zweite Hälfte ist die gefährlichere.** Eine Stack-Variable erreicht den
Container nur über eine ``environment:``-Zeile — Portainers Stack-Env ist die
``.env`` für die compose-Interpolation (#1951). Ohne die Zeile hätte der Deploy
den Digest gesetzt, der Redeploy mit HTTP 200 geantwortet und die Anwendung
weiterhin nichts gewusst. Das wäre C11 ein zweites Mal, nur mit mehr Code.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
PORTAINER = WURZEL / "shared" / "deploy" / "portainer.py"
COMPOSE = WURZEL / "docker-compose.yml"
DOCKERFILE = WURZEL / "Dockerfile"


def _programm(pfad: Path) -> str:
    """Quelltext ohne Docstrings und Kommentare — das Programm, nicht die Erzählung.

    Mit dem AST, weil ein Regex über dreifach angeführte Zeichenketten auch die
    SQL- und Shell-Abschnitte löscht (die Lehre aus #1966, dort selbst
    hineingelaufen).
    """
    quelle = pfad.read_text(encoding="utf-8")
    zeilen = quelle.splitlines()
    for knoten in ast.walk(ast.parse(quelle)):
        if not isinstance(knoten, (ast.Module, ast.FunctionDef,
                                   ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        koerper = getattr(knoten, "body", None) or []
        if (koerper and isinstance(koerper[0], ast.Expr)
                and isinstance(koerper[0].value, ast.Constant)
                and isinstance(koerper[0].value.value, str)):
            doc = koerper[0]
            for nr in range(doc.lineno - 1, (doc.end_lineno or doc.lineno)):
                zeilen[nr] = ""
    return re.sub(r"(?m)#.*$", "", "\n".join(zeilen))


# ── Der Deploy setzt ihn ────────────────────────────────────────────────────

def test_der_deploy_setzt_den_digest():
    programm = _programm(PORTAINER)
    assert "def image_digest" in programm, (
        "Der Digest wird nicht ermittelt — C11 bleibt offen.")
    assert re.search(r'_env_setzen\(\s*env\s*,\s*["\']APP_IMAGE_DIGEST["\']', programm), (
        "`APP_IMAGE_DIGEST` wird nicht in die Stack-Env geschrieben.")


def test_der_digest_gehoert_zum_angefragten_abbild():
    """``RepoDigests`` kann mehrere Einträge tragen.

    Irgendeinen zu nehmen hieße, einen Digest zu melden, der ein anderes
    Repository bezeichnet — in einer Vorfalldokumentation schlimmer als keine
    Angabe.
    """
    programm = _programm(PORTAINER)
    stelle = programm[programm.index("def image_digest"):]
    stelle = stelle[:stelle.index("def image_ziehen")]
    assert "RepoDigests" in stelle
    assert "repo == name" in stelle, (
        "Der Eintrag wird nicht gegen den angefragten Namen geprüft.")
    assert "sha256:" in stelle, "Der Digest wird nicht auf sha256 geprüft."


def test_ein_fehlender_digest_wird_gemeldet_nicht_verschwiegen():
    """Ein stilles Auslassen wäre genau die Fehlerklasse, die C11 erzeugt hat."""
    programm = _programm(PORTAINER)
    stelle = programm[programm.index("APP_IMAGE_DIGEST"):][:600]
    assert "nicht ermittelbar" in stelle or "nicht gesetzt" in stelle, (
        "Wird der Digest nicht ermittelt, sagt der Deploy nichts darüber.")


# ── Und er kommt im Container an ────────────────────────────────────────────

def test_compose_reicht_den_digest_durch():
    """Die Hälfte, die in #1951 Geld gekostet hat.

    Portainers Stack-Env ist die ``.env`` für die Interpolation; in den
    Container kommt ein Wert nur über eine ``environment:``-Zeile. Ohne sie
    setzt der Deploy den Digest, der Redeploy antwortet 200, und die Anwendung
    weiß weiter nichts.
    """
    text = COMPOSE.read_text(encoding="utf-8")
    ohne_kommentar = re.sub(r"(?m)^\s*#.*$", "", text)
    assert re.search(r"APP_IMAGE_DIGEST=\$\{APP_IMAGE_DIGEST", ohne_kommentar), (
        "docker-compose.yml reicht APP_IMAGE_DIGEST nicht durch — der Wert "
        "erreicht den Container nie (#1951).")


def test_die_anwendung_liest_ihn():
    """Ohne Leser wäre das Setzen Zierde."""
    admin = (WURZEL / "server" / "api" / "admin.py").read_text(encoding="utf-8")
    assert "APP_IMAGE_DIGEST" in re.sub(r"(?m)#.*$", "", admin)


def test_das_dockerfile_deklariert_ihn_weiter():
    """Der Bau kann ihn nicht füllen, aber die Variable muss existieren —
    sonst ist sie im Container nicht gesetzt und ``os.environ.get`` liefert
    nichts, auch wenn compose sie durchreicht."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "ARG APP_IMAGE_DIGEST" in text and "APP_IMAGE_DIGEST=${APP_IMAGE_DIGEST}" in text


# ── #1963: keine Windows-Programmdateien im Linux-Abbild ────────────────────

def test_keine_windows_startprogramme_im_abbild():
    """14 von 189 SBOM-Komponenten waren Windows-`.exe` aus pip und setuptools.

    Ohne purl bleiben sie nach #1773 `unbestimmt` und landen dauerhaft in der
    Gruppe „Einzelprüfung" — 14 begründete Einzelaussagen über den
    Versorgungsweg von Dateien, die das Produkt nicht ausführt.
    """
    text = DOCKERFILE.read_text(encoding="utf-8")
    ohne_kommentar = re.sub(r"(?m)^\s*#.*$", "", text)
    assert re.search(r"find\s+/usr/local/lib/python3\.11/site-packages.*-name\s+'\*\.exe'.*-delete",
                     ohne_kommentar, re.S), (
        "Das Abbild räumt die Windows-Startprogramme nicht weg (#1963).")
