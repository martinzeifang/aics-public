"""Ein durchgereichter Name ist in dieser Datei nicht vorhanden (#1854).

DER BEFUND
`stores/risikobewertung.ts` holte den Neubewertungs-Marker so:

    export { NEUBEWERTUNG_MARKER as REASSESS_MARKER } from '../utils/neubewertung'

Das ist ein **Durchreichen**, kein Import: Die Bindung wird nach außen
weitergegeben, in der Datei selbst aber **nicht angelegt**.
`aktualisiereRisikoStats` benutzte den Namen trotzdem und bekam zur Laufzeit
einen ``ReferenceError``. Weil der Aufruf im ``try`` von ``fetchRisiken()``
steht, wurde daraus die Meldung „Fehler beim Laden" — für Daten, die geladen
waren. Auf allen vier Instanzen, bei jedem Öffnen des Moduls.

WARUM DAS EIN TEST IST UND KEINE FRAGE DER SORGFALT
**Der Build bleibt grün.** Rolldown/Vite behandelt den Fall nicht als Fehler,
``vue-tsc`` ist in diesem Repo defekt (zeigt nur die Hilfe), und der CI-Job
``typecheck`` läuft mit ``continue-on-error: true`` — er kann gar nicht rot
werden. Für diese Fehlerklasse gab es damit **keinen** Prüfer, und das ist
dieselbe Lücke wie bei #1830 (unbekannter Bezeichner im Template → still
``undefined``).

Der Test prüft das Programm, nicht die Erzählung: Kommentare und der
``from '…'``-Teil werden vorher entfernt — sonst schlägt er auf jeden
Kommentar an, der den Namen erklärt (das war der erste Fehlalarm beim
Schreiben).
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SRC = WURZEL / "frontend" / "src"

#: Zeile der Form ``export { A, B as C } from '…'`` — das reine Durchreichen.
_DURCHREICHEN = re.compile(r"^export\s*\{([^}]*)\}\s*from\s*['\"][^'\"]+['\"]\s*;?\s*$",
                           re.M)


def _ohne_kommentare(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(z for z in text.split("\n") if not z.lstrip().startswith("//"))


def _dateien() -> list[Path]:
    return sorted(list(SRC.rglob("*.ts")) + list(SRC.rglob("*.vue")))


def test_kein_durchgereichter_name_wird_lokal_benutzt():
    """Wer den Namen braucht, muss ihn **importieren**.

    Das Muster bleibt erlaubt — ein Sammel-Modul, das nur weiterreicht, ist
    genau das Richtige. Verboten ist nur die Mischung: durchreichen **und**
    selbst benutzen.
    """
    verstoesse: list[str] = []
    for pfad in _dateien():
        roh = pfad.read_text(encoding="utf-8")
        code = _ohne_kommentare(roh)
        for m in _DURCHREICHEN.finditer(code):
            # Den `from '…'`-Teil mitentfernen, sonst zählt der Modulpfad als
            # Fundstelle (`./docsUrl` enthält „docsUrl").
            rest = code.replace(m.group(0), "")
            for teil in m.group(1).split(","):
                name = teil.split(" as ")[-1].strip()
                if not name or name == "default":
                    continue
                # Ein Typ-Export kann nicht zur Laufzeit fehlen.
                if teil.strip().startswith("type "):
                    continue
                if re.search(r"\b" + re.escape(name) + r"\b", rest):
                    verstoesse.append(
                        f"{pfad.relative_to(SRC)}: „{name}“ wird durchgereicht "
                        f"(`export {{ … }} from`) und in derselben Datei benutzt "
                        f"— zur Laufzeit ein ReferenceError")
    assert not verstoesse, (
        "Durchgereichte Namen ohne lokale Bindung:\n  " + "\n  ".join(verstoesse)
        + "\n\nRichtig ist: `import { X } from '…'` und daneben "
          "`export { X as Y }` — dann gibt es die Bindung auch hier.")


def test_der_marker_ist_importiert_nicht_nur_durchgereicht():
    """Die Stelle, an der #1854 hing — ausdrücklich festgehalten.

    Der allgemeine Wächter oben fängt den Fall schon. Dieser Test nennt ihn
    beim Namen, damit beim nächsten Lesen klar ist, **welche** Zeile das war:
    Die Risikobewertung zählt mit diesem Marker die Objekte, die eine
    Neubewertung brauchen (#1764) — ohne lokale Bindung bricht das Zählen ab,
    und der Anwender bekommt einen Ladefehler für geladene Daten zu sehen.
    """
    quelle = (SRC / "stores" / "risikobewertung.ts").read_text(encoding="utf-8")
    assert "import { NEUBEWERTUNG_MARKER }" in quelle, (
        "Der Marker muss importiert sein, nicht nur durchgereicht (#1854).")
    assert "includes(NEUBEWERTUNG_MARKER)" in quelle, (
        "Die Zählung muss den importierten Namen benutzen.")
