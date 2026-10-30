"""Prompt hinaus, Antwort herein — überall gleich (#1867).

Der Copy/Paste-Weg ist der **Vorgabeweg** der Suite (CLAUDE.md: „Semi-automated
workflow where prompts are pasted into ChatGPT"). Trotzdem sah er in 19 Masken
verschieden aus: drei hatten gar keinen Kopier-Knopf, die übrigen kopierten
jede für sich — mit „✓ Kopiert", mit `alert()`, mit verschlucktem Fehler und
einmal ganz ohne Rückmeldung. **Einfügen** konnte keine einzige:
`navigator.clipboard.readText` kam im ganzen Baum 0× vor.

WARUM DAS EIN TEST IST UND KEINE FRAGE DER SORGFALT
Beim nächsten Dialog schreibt jemand die naheliegende Variante hin, und es
fällt niemandem auf, weil **nichts fehlschlägt** — die Oberfläche sieht nur an
einer Stelle anders aus. Dieselbe Fehlerklasse wie #1731/#1735, und derselbe
Grund für einen Wächter wie bei #1851 (Beschriftungen) und #1849 (Modale).
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "frontend" / "src"
HELFER = FRONTEND / "utils" / "zwischenablage.ts"
BAUSTEIN = FRONTEND / "components" / "shared" / "PromptAustausch.vue"

#: Wo `navigator.clipboard` **außerhalb** des Helfers stehen darf — je mit Grund.
#:
#: Beide kopieren keinen Prompt. Sie sind etwas anderes als der
#: Prompt-Austausch und würden durch dieselbe Bedienung nicht klarer.
CLIPBOARD_ERLAUBT = {
    "views/account/SecurityView.vue":
        "TOTP-Geheimnis und Wiederherstellungs-Codes. Kein Prompt, und die "
        "Rückmeldung gehört dort an den Einrichtungs-Ablauf.",
    "views/admin/AdminTemplatesView.vue":
        "Vorlagen-Token (`[projekt.aktenzeichen]`) aus der Variablen-Hilfe. "
        "Kein Prompt, sondern ein Textbaustein für die Word-Vorlage.",
}


def _vue_dateien() -> list[Path]:
    return sorted(FRONTEND.rglob("*.vue"))


def _ohne_kommentare(text: str) -> str:
    """Kommentare heraus — geprüft wird das Programm, nicht die Erzählung.

    Die Lehre aus #1834: Ein Wächter, der auf eine Zeichenkette im Quelltext
    schaut, bleibt grün, wenn der Code weg ist und das Wort noch im Kommentar
    darüber steht — und wird **rot**, wenn ein Kommentar den alten Zustand
    zitiert. Beides ist falsch; beim ersten Anlauf von #1867 trat der zweite
    Fall ein, weil ein Dateikopf „📋 Prompt erzeugen" als Fundstelle nennt.
    """
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)   # HTML/Vue
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)    # /* … */
    return re.sub(r"^\s*(//|\*|\#:)\s.*$", "", text, flags=re.M)


# ── Der Helfer ist die eine Stelle ─────────────────────────────────────────

def test_die_mechanik_liegt_an_einer_stelle():
    """`navigator.clipboard` nur noch im Helfer — und in zwei begründeten Fällen."""
    fehler: list[str] = []
    for p in list(_vue_dateien()) + sorted(FRONTEND.rglob("*.ts")):
        rel = str(p.relative_to(FRONTEND))
        if p == HELFER or rel in CLIPBOARD_ERLAUBT:
            continue
        if "navigator.clipboard" in _ohne_kommentare(p.read_text(encoding="utf-8")):
            fehler.append(rel)
    assert not fehler, (
        "eigene Zwischenablage-Nutzung statt `utils/zwischenablage`: "
        + ", ".join(fehler)
        + " — entweder den Helfer benutzen oder in CLIPBOARD_ERLAUBT begründen")


def test_der_helfer_wertet_den_misserfolg_aus():
    """Beide Richtungen müssen scheitern **können**.

    Der Bestand verschluckte den Fehlschlag (`catch { /* ignore */ }`): Der
    Knopf tat dann nichts und sagte nichts. Genau das ist ein Knopf ohne
    Wirkung (#1805/#1830).
    """
    quelle = HELFER.read_text(encoding="utf-8")
    assert "export async function kopiere" in quelle
    assert "Promise<boolean>" in quelle, "`kopiere` muss den Erfolg melden"
    assert "export async function einfuegen" in quelle
    assert "EinfuegeFehler" in quelle, "`einfuegen` muss den Grund benennen"
    assert "EINFUEGE_HINWEIS" in quelle, "der Satz zum Fehler gehört an eine Stelle"


def test_einfuegen_hat_keinen_trick_als_rueckfall():
    """Beim Lesen gibt es bewusst **keinen** Rückfall.

    Der Browser schützt den Inhalt der Zwischenablage; an diesem Schutz führt
    kein Weg vorbei, der nicht selbst einer wäre. `execCommand('paste')` ist
    genau so ein Weg und hat hier nichts zu suchen.
    """
    quelle = HELFER.read_text(encoding="utf-8")
    assert "execCommand('paste')" not in quelle
    assert 'execCommand("paste")' not in quelle


# ── Der Baustein ist überall derselbe ──────────────────────────────────────

def test_der_baustein_hat_beide_knoepfe():
    quelle = BAUSTEIN.read_text(encoding="utf-8")
    assert "📋 Kopieren" in quelle, "Kopier-Knopf fehlt"
    assert "📥 Einfügen" in quelle, "Einfüge-Knopf fehlt"
    assert "✓ Kopiert" in quelle, "die Rückmeldung fehlt"
    # Der Fokus gehört ins Feld, wenn das Einfügen nicht geht — sonst bliebe
    # nur eine Bedienanleitung, und die ist keine Funktion.
    assert ".focus()" in quelle


def test_jede_maske_mit_prompt_und_antwort_nutzt_den_baustein():
    """Prompt-Anzeige **und** Antwortfeld in einer Maske → `PromptAustausch`.

    Erkannt wird die Form, die der Anwender bedient: ein schreibgeschützt
    angezeigter Prompt und ein Feld, in das die Antwort kommt. Wer beides
    selbst zeichnet, baut die zwanzigste Fassung.
    """
    fehler: list[str] = []
    for p in _vue_dateien():
        rel = str(p.relative_to(FRONTEND))
        if p == BAUSTEIN:
            continue
        t = _ohne_kommentare(p.read_text(encoding="utf-8"))
        zeigt_prompt = re.search(
            r'readonly[^>]*:value="[^"]*[Pp]rompt'
            r'|<pre[^>]*>\s*\{\{\s*[\w.?]*[Pp]rompt', t)
        antwortfelder = [a for a in re.findall(r'<textarea[^>]*v-model="([^"]+)"', t)
                         if "prompt" not in a.lower()]
        if zeigt_prompt and antwortfelder and "PromptAustausch" not in t:
            fehler.append(rel)
    assert not fehler, (
        "eigener Prompt/Antwort-Block statt `PromptAustausch`: " + ", ".join(fehler))


def test_das_klemmbrett_steht_nicht_am_falschen_knopf():
    """📋 gehört dem Kopieren, nicht dem Erzeugen.

    In „🔎 Akte prüfen lassen" und „🔍 Nachweise erschließen" hieß der Knopf
    „📋 Prompt erzeugen". Das Symbol versprach die Zwischenablage, die
    Handlung holte den Text vom Server — und einen Weg in die Ablage gab es
    gar nicht. Genau daraus entstand die Meldung zu #1867.
    """
    fehler: list[str] = []
    for p in _vue_dateien():
        for zeile in _ohne_kommentare(p.read_text(encoding="utf-8")).splitlines():
            if "📋" in zeile and "erzeugen" in zeile:
                fehler.append(f"{p.relative_to(FRONTEND)}: {zeile.strip()[:80]}")
    assert not fehler, "📋 an einem Knopf, der nichts kopiert:\n  " + "\n  ".join(fehler)


def test_kein_alert_fuer_eine_erfolgreiche_kopie():
    """`alert('Kopiert.')` war die einzige Stelle im Haus, die so quittierte.

    Ein Fenster, das man wegklicken muss, für „hat geklappt" — und in einer
    Maske, während neunzehn andere es still taten.
    """
    fehler: list[str] = []
    for p in _vue_dateien():
        t = _ohne_kommentare(p.read_text(encoding="utf-8"))
        for treffer in re.findall(r"alert\((['\"])[^'\"]*[Kk]opier[^'\"]*\1\)", t):
            fehler.append(str(p.relative_to(FRONTEND)))
    assert not fehler, "alert() als Kopier-Rückmeldung: " + ", ".join(sorted(set(fehler)))
