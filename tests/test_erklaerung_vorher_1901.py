"""Die Befunde der Erklärung stehen VOR dem KI-Lauf (#1898/#1899/#1901/#1902).

Aus dem Betrieb kam ein Entwurf der EU-Konformitätserklärung zurück, in dem
das Sprachmodell drei Dinge bemerkte: Nr. 1 und Nr. 4 nennen verschiedene
Releases, Nr. 6 nennt Spezifikationen, die die Akte nicht belegt, und
Pflichtangaben fehlen. „Es ist besser, aber die KI generiert noch immer
Erklärungen und weist Fehler aus. Das muss vorher sicher passen."

**Alle drei sind rechenbar** — das war schon die Lehre aus #1885. Dass zwei
davon trotzdem als Bemerkung zurückkamen, hatte zwei Ursachen, und beide
prüft diese Datei:

* ``fp.version_befunde`` fragt jedes Feld **gegen die Akte** („kennt die Akte
  diese Version?"). Im gemeldeten Fall kannte sie **beide** — 8.0.1 und
  8.0.11 sind echte Releases. Jede Angabe war einzeln plausibel, zusammen
  widersprüchlich. Es fehlte der Abgleich der Felder **gegeneinander**.
* Nr. 6 wurde nur auf „leer" geprüft. Dass die Liste Unbelegtes nennt,
  rechnete niemand, obwohl ``normen_kandidaten`` genau weiß, was belegt ist.

Dazu der Lauf selbst: Er darf nicht starten, solange die Akte ihn nicht
trägt. Was das Modell nur benennen, aber nicht beheben kann, soll es nicht
für einen Lauf vorlesen.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from cra import doc_pruefung as dp
from cra import normen_katalog as nk
from shared import formular_pruefung as fp

REPO = Path(__file__).resolve().parents[1]
CRA_FORM = REPO / "frontend/src/components/cra/KonformitaetserklaerungForm.vue"
AIACT_FORM = REPO / "frontend/src/components/aiact/KonformitaetserklaerungForm.vue"
PANEL = REPO / "frontend/src/views/cra/AssistentenPanel.vue"

KATALOG = {n.bezeichnung for n in nk.ALLE}


def _gemeldeter_fall() -> dict:
    """Genau der Datensatz aus der Betriebsmeldung."""
    return {
        "produkt_charge": "8.0.11",
        "gegenstand": ("AI Compliance Suite, Release 8.0.1 — Software zur "
                       "Compliance-Verwaltung, ausgeliefert als Container-Image."),
        "normen": ["CycloneDX", "SLSA", "Sigstore/cosign", "OWASP Top 10"],
    }


# ── Nr. 1 gegen Nr. 4 ───────────────────────────────────────────────────────

def test_der_gemeldete_widerspruch_wird_gerechnet():
    """Der Kern der Meldung — und er blockiert."""
    b = dp.pruefe(_gemeldeter_fall(), version="8.0.1",
                  erlaubte_versionen={"8.0.1", "8.0.11", "8.2.3"},
                  belegte_normen={"OWASP Proactive Controls", "SPDX"},
                  katalog_normen=KATALOG)
    treffer = [x for x in b if x["id"] == "versionen_widersprechen"]
    assert treffer, [x["id"] for x in b]
    assert treffer[0]["wirkung"] == fp.WIRKUNG_BLOCKIERT
    # Beide Versionen müssen im Text stehen — eine Meldung, die nur sagt
    # „widersprüchlich", schickt den Anwender auf die Suche (#1805).
    assert "8.0.11" in treffer[0]["text"] and "8.0.1" in treffer[0]["text"]
    assert dp.blockierend(b), "ein Versions-Widerspruch darf nicht durchgehen"


def test_die_alte_pruefung_allein_haette_ihn_nie_gefunden():
    """Belegt, warum es die zweite Prüfung braucht.

    Beide Versionen sind der Akte bekannt, also schlägt der Abgleich gegen
    die Akte nicht an. Dieser Test ist der Grund für die neue Funktion — er
    hält fest, dass die vorhandene Prüfung hier *richtig* schweigt.
    """
    doc = _gemeldeter_fall()
    assert fp.version_befunde(
        doc, ("gegenstand", "produkt_charge", "zusatzangaben"),
        {"8.0.1", "8.0.11", "8.2.3"},
        lambda f: f, lambda _f: 0) == []


def test_dieselbe_version_in_beiden_feldern_ist_kein_befund():
    """Der Normalfall bekommt nichts — sonst wird der Prüfer abgeschaltet."""
    doc = {"produkt_charge": "8.2.3",
           "gegenstand": "AI Compliance Suite, Release 8.2.3 — Software."}
    b = dp.pruefe(doc, version="8.2.3", erlaubte_versionen={"8.2.3"})
    assert [x for x in b if x["id"] == "versionen_widersprechen"] == []


def test_eine_zweite_version_im_gegenstand_ist_erlaubt():
    """„ersetzt Release 8.0.1" ist kein Widerspruch.

    Beanstandet wird nur, wenn zwei Felder **keine** gemeinsame Version
    haben. Ein Gegenstandstext darf einen Vorgänger nennen.
    """
    doc = {"produkt_charge": "8.2.3",
           "gegenstand": "Release 8.2.3, ersetzt Release 8.0.1."}
    b = dp.pruefe(doc, version="8.2.3", erlaubte_versionen={"8.2.3", "8.0.1"})
    assert [x for x in b if x["id"] == "versionen_widersprechen"] == []


def test_keine_fehlalarme_auf_fremden_zahlen():
    """„TLS 1.3" und „SPDX 2.3" sind keine Produktversionen.

    Die Lehre aus #1885 wörtlich: Ein blockierender Fehlalarm macht die
    Anwendung unbenutzbar, und ein Regex auf jede Zahlenfolge hätte genau
    diese Angaben getroffen.
    """
    doc = {"produkt_charge": "8.2.3",
           "gegenstand": "Release 8.2.3 mit TLS 1.3 und SBOM nach SPDX 2.3, "
                         "geprüft gegen ISO/IEC 27001:2022."}
    b = dp.pruefe(doc, version="8.2.3", erlaubte_versionen={"8.2.3"})
    assert [x for x in b if x["id"] == "versionen_widersprechen"] == []


# ── Nr. 6 ───────────────────────────────────────────────────────────────────

def test_unbelegte_spezifikationen_werden_benannt():
    b = dp.pruefe(_gemeldeter_fall(), version="8.0.1",
                  erlaubte_versionen={"8.0.1", "8.0.11"},
                  belegte_normen={"OWASP Proactive Controls", "SPDX"},
                  katalog_normen=KATALOG)
    treffer = [x for x in b if x["id"] == "normen_unbelegt"]
    assert treffer, [x["id"] for x in b]
    text = treffer[0]["text"]
    for genannt in ("CycloneDX", "SLSA", "Sigstore/cosign", "OWASP Top 10"):
        assert genannt in text, genannt
    # Was nicht einmal im Katalog steht, wird eigens genannt — das ist der
    # Unterschied zwischen „nicht belegt" und „frei getippt".
    assert "SLSA" in text.split("Nicht aus der Auswahlliste gewählt:")[-1]


def test_unbelegte_spezifikationen_blockieren_nicht():
    """Ein Haus darf eine Spezifikation anwenden, die die Akte nicht führt.

    Dann ist die Angabe richtig und die Akte unvollständig. Ein blockierender
    Befund würde das Formular gegen den Anwender wenden (#1814/#1751).
    """
    b = dp.pruefe(_gemeldeter_fall(), belegte_normen={"SPDX"},
                  katalog_normen=KATALOG)
    assert all(x["wirkung"] != fp.WIRKUNG_BLOCKIERT
               for x in b if x["id"] == "normen_unbelegt")


def test_belegte_spezifikationen_sind_kein_befund():
    b = dp.pruefe({"normen": ["SPDX", "OWASP Proactive Controls"]},
                  belegte_normen={"SPDX", "OWASP Proactive Controls"},
                  katalog_normen=KATALOG)
    assert [x for x in b if x["id"] == "normen_unbelegt"] == []


def test_ohne_kenntnis_der_belege_kein_befund():
    """Ohne Vergleichsmaßstab wird nicht beanstandet.

    Dieselbe Regel wie bei ``version_befunde``: Ein Prüfer, der immer
    anschlägt, wird abgeschaltet. Fällt die Belegquelle aus, schweigt er.
    """
    b = dp.pruefe({"normen": ["SLSA"]}, belegte_normen=set(),
                  katalog_normen=KATALOG)
    treffer = [x for x in b if x["id"] == "normen_unbelegt"]
    # Ohne Belege ist jede Angabe „unbelegt" — gemeldet wird sie, aber nie
    # blockierend, und der Text nennt, dass die Akte nichts hergibt.
    assert all(x["wirkung"] == fp.WIRKUNG_HINWEIS for x in treffer)


# ── Eine Quelle für „was ist belegt" ────────────────────────────────────────

def test_belege_kommen_aus_einer_zusammenstellung():
    """``vorschlag`` und ``doc_pruefung`` dürfen nicht verschieden rechnen.

    Sonst wäre „belegt" zweimal definiert, und die Abweichung fiele erst auf,
    wenn jemand einen Befund nicht erklären kann (#1726/#1727).
    """
    from cra import doc_vorschlag as dv

    quelle = Path(dv.__file__).read_text(encoding="utf-8")
    # `vorschlag()` ruft die gemeinsame Zusammenstellung, nicht `normen_kandidaten`
    # mit eigenen Argumenten.
    assert "_normen_aus_quellen(" in quelle
    assert quelle.count("normen_kandidaten(") == 2, (
        "normen_kandidaten darf nur in der Definition und in "
        "_normen_aus_quellen vorkommen")
    assert "belegte_normen" in Path(dp.__file__).read_text(encoding="utf-8")


# ── Der Lauf startet nicht, wenn die Akte ihn nicht trägt ───────────────────

def test_die_sperre_ist_eine_funktion_und_wird_zweimal_benutzt():
    """Prompt-Endpunkt und Vollständigkeitsanzeige fällen dasselbe Urteil.

    Die Regel im Frontend nachzubauen wäre die zweite Wahrheit (#1703/S9);
    sie zweimal im Server zu haben wäre dieselbe Falle eine Ebene tiefer.
    """
    quelle = (REPO / "server/api/cra/__init__.py").read_text(encoding="utf-8")
    assert "def _eu_doc_sperre(" in quelle
    # Einmal definiert, zweimal gerufen.
    assert quelle.count("_eu_doc_sperre(") == 3, quelle.count("_eu_doc_sperre(")


def test_nur_ki_felder_leer_sperrt_nicht():
    """Die Sperre darf dem Assistenten nicht seinen Zweck nehmen.

    ``KI_FELDER`` ist abschließend (#1887). Ist nur ein solches Feld leer,
    ist das Füllen genau die Aufgabe des Assistenten.
    """
    from cra.doc_vorschlag import KI_FELDER

    assert KI_FELDER, "ohne KI-Felder wäre die Unterscheidung sinnlos"
    quelle = (REPO / "server/api/cra/__init__.py").read_text(encoding="utf-8")
    sperre = quelle.split("def _eu_doc_sperre(")[1].split("\n@")[0]
    assert "KI_FELDER" in sperre, (
        "die Sperre muss die KI-Felder ausnehmen, sonst sperrt sie genau den "
        "Fall, für den der Assistent da ist")


def test_die_sperre_faellt_nicht_closed():
    """Eine unlesbare Teilquelle darf den Assistenten nicht stilllegen."""
    quelle = (REPO / "server/api/cra/__init__.py").read_text(encoding="utf-8")
    sperre = quelle.split("def _eu_doc_sperre(")[1].split("\n@")[0]
    assert "return None" in sperre.split("except Exception")[1]


# ── Die Oberfläche: kein Knopf ohne Grund, kein Fenster ohne Ausgang ───────

def _ohne_kommentare(pfad: Path) -> str:
    """HTML- und JS-Kommentare heraus — geprüft wird das Programm.

    Zweimal ist in diesem Haus ein Wächter grün geblieben, weil er die
    Erzählung statt des Programms gelesen hat (#1834, #1867), und einmal rot
    aus demselben Grund (#1878).
    """
    text = pfad.read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)


@pytest.mark.parametrize("form", [CRA_FORM, AIACT_FORM], ids=["cra", "aiact"])
def test_kein_entwurfs_versprechen_mehr(form):
    """#1898: Der Satz versprach einen Entwurf, den es beim Ausstellen nicht gibt.

    Den Entwurfsvermerk setzt der **Download**; ausstellen geht mit Lücken
    gar nicht (#1814), und der Knopf ist deshalb gesperrt. Der Anwender las
    „dann eben ein Entwurf", klickte, und nichts passierte.
    """
    text = _ohne_kommentare(form)
    assert "es entsteht nur ein als ENTWURF" not in text
    assert "ausstellen ist damit nicht möglich" in text


@pytest.mark.parametrize("form", [CRA_FORM, AIACT_FORM], ids=["cra", "aiact"])
def test_der_gesperrte_knopf_nennt_den_grund(form):
    """#1898: `disabled` allein ist „tut nichts".

    Der Grund steht im `title` **und** in einer Zeile unmittelbar über den
    Aktionen — der Hinweis zum Bewertungsweg liegt am Anfang einer Maske mit
    achtzehn Feldern, und wer unten klickt, sieht ihn nicht.
    """
    text = _ohne_kommentare(form)
    assert "sperrgruende" in text
    # Der Knopf selbst, nicht die Hinweiszeile darüber (die den Wortlaut
    # ebenfalls zitiert — daran ist dieser Test beim ersten Anlauf gescheitert).
    # Ohne Regex: `[^>]*` schneidet das Tag mitten im Attribut ab, weil dort
    # `sperrgruende.length > 0` steht (die Falle aus #1805), und `.*?` mit
    # DOTALL greift über frühere Knöpfe hinweg. Also schlicht vom Vorkommen
    # der Beschriftung zurück zum öffnenden Tag.
    stellen = [m.start() for m in re.finditer(
        r">\s*Erklärung ausstellen\s*</button>", text)]
    assert len(stellen) == 1, f"{len(stellen)} Knöpfe gefunden"
    knopf = text[text.rindex("<button", 0, stellen[0]):stellen[0] + 1]
    assert ':disabled="sperrgruende.length > 0"' in knopf, knopf
    assert ":title=" in knopf and "sperrgruende" in knopf.split(":title=")[1], (
        "der gesperrte Knopf muss seinen Grund als title tragen")


@pytest.mark.parametrize("form", [CRA_FORM, AIACT_FORM], ids=["cra", "aiact"])
def test_die_sperrbedingung_steht_nur_einmal(form):
    """Knopf, title und Hinweiszeile lesen dieselbe Rechnung.

    Drei Fassungen davon wären drei Gelegenheiten, sie unterschiedlich falsch
    zu machen — und genau so entstand #1898.
    """
    text = _ohne_kommentare(form)
    assert text.count("const sperrgruende") == 1
    # Die alte, im Template ausgeschriebene Bedingung ist weg.
    assert "fehlendePflicht.length > 0\n" not in text.split("<script")[0]


@pytest.mark.parametrize("datei", [
    REPO / "frontend/src/components/cra/DocAssistentModal.vue",
    REPO / "frontend/src/components/aiact/DocAssistentModal.vue",
], ids=["cra", "aiact"])
def test_der_assistent_hat_einen_ausgang(datei):
    """#1899: Das Fenster blieb nach der Übernahme offen.

    Gibt es nichts zu lesen, geht es zu; gibt es etwas zu lesen, zeigt der
    Fuß „Fertig — schließen" statt „Abbrechen"/„Übernehmen" — wer gerade
    übernommen hat, liest „Abbrechen" als „mein Ergebnis verwerfen".
    """
    text = _ohne_kommentare(datei)
    assert "emit('close')" in text.split("async function anwenden")[1], (
        "nach der Übernahme muss das Fenster schließen können")
    assert ':erledigt="fertig"' in text


def test_der_erledigt_zustand_liegt_im_gemeinsamen_modal():
    """Alle sechs Aufrufer erben den Ausgang, nicht nur die beiden."""
    text = _ohne_kommentare(REPO / "frontend/src/components/shared/WizardPromptModal.vue")
    assert "erledigt" in text
    assert "Fertig — schließen" in text


@pytest.mark.parametrize("panel", [
    PANEL,
    REPO / "frontend/src/views/nis2/AssistentenPanel.vue",
    REPO / "frontend/src/views/wiba/AssistentenPanel.vue",
], ids=["cra", "nis2", "wiba"])
def test_der_direktlauf_parst(panel):
    """#1902: Der Direktlauf legte die Antwort nur ins Feld.

    Damit blieb `parsed` null, und der ganze Ergebnisblock — Markdown-Kasten,
    „📋 Markdown kopieren", der Text für „📄 Als Dokument speichern" — hing
    daran. Beobachtet bei der Konformitätserklärung und der SBOM-Doku.
    """
    text = _ohne_kommentare(panel)
    lauf = text.split("const onWizardRunDone")[1].split("const onWizardRunError")[0]
    assert "parseOnly()" in lauf, "beide Wege müssen im selben Zustand enden"
    assert "parseAndApply" not in lauf, (
        "geparst, nicht angewendet — ein Direktlauf ist keine Zustimmung zum "
        "Speichern (#1773)")


def test_der_assistent_zeigt_die_sperre_statt_eines_prompts():
    """#1901: Kein Prompt, solange die Akte den Lauf nicht trägt.

    Das Urteil kommt vom Server (`bereit`), und der Prompt wird dann gar
    nicht geholt — das Modell soll nicht für Geld vorlesen, was die Anwendung
    schon gerechnet hat.
    """
    text = _ohne_kommentare(PANEL)
    assert "nichtBereit" in text
    assert "bereit === false" in text
    oeffnen = text.split("const openPromptWizard")[1].split("const closeWizard")[0]
    assert oeffnen.index("docVollstaendigkeit") < oeffnen.index("getWizardPrompt"), (
        "erst prüfen, dann den Prompt holen")


def test_die_neuen_befunde_tragen_eigene_schluessel():
    """Flache Schlüssel, damit Anzeige und Bericht sie auseinanderhalten."""
    quelle = Path(dp.__file__).read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    texte = {n.value for n in ast.walk(baum)
             if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "normen_unbelegt" in texte
    assert "versionen_widersprechen" in {
        n.value for n in ast.walk(ast.parse(
            Path(fp.__file__).read_text(encoding="utf-8")))
        if isinstance(n, ast.Constant) and isinstance(n.value, str)}
