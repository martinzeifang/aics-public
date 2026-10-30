"""Die amtlichen Verordnungstexte in die Installation holen (#1889/#1894).

WARUM DIESE DATEI EXISTIERT
---------------------------
Mehrere Module zitieren Fundstellen, die in ein unterschriebenes Dokument
gedruckt werden — Anhang V der CRA (``cra/doc_export``), Anhang V der KI-VO
(``ai_act/doc_export``), Artikel der DSGVO. Die Lehre aus #1763/#1792 ist, dass
eine erfundene Nummer dort schlimmer ist als keine Angabe, und deshalb steht in
beiden Modulen: Maßgeblich ist das Amtsblatt.

**Nur ließ sich der Text nicht beschaffen.** Herunterladen konnte ihn
ausschließlich der Tkinter-Dialog des Gutachten-Moduls
(``gutachten/_download_dialog.py``) — eine Desktop-Oberfläche, die der
Administrator einer gehosteten Installation nicht hat. Die Fähigkeit war da und
nicht bedienbar; dieselbe Form wie die SBOM, die sich holen aber nicht
herunterladen ließ (#1823), und wie die Hilfe, deren Handbuch nicht im Image
lag (#1878).

WAS HIER **NICHT** PASSIERT
---------------------------
Kein eigener Transport. Geholt wird über die vorhandenen Helfer in
``gutachten/file_download.py``: Die direkten PDF-Links auf eur-lex.europa.eu
stehen hinter einer AWS-WAF-Prüfung (HTTP 202 + HTML statt PDF); die
Publikationsstelle liefert dieselben Dokumente über SPARQL und stabile
Cellar-Item-URLs aus. Diesen Weg zweimal zu bauen hieße, ihn zweimal zu
pflegen — und der erste Anlauf scheiterte genau an der WAF.

**Die CELEX-Nummern sind eine Positivliste.** Sie kommen nicht aus einer
Eingabe: Ein Endpunkt, der eine beliebige Kennung annimmt, spricht am Ende mit
einem beliebigen Host (die Linie aus #1761/#1770). Erlaubt ist, was diese
Anwendung zitiert.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Zielsprache der amtlichen Fassung. Mehrsprachigkeit ist bewusst kein
#: Parameter aus dem Request: Die Module zitieren die deutsche Fassung.
SPRACHE = "DEU"


@dataclass(frozen=True)
class Verordnung:
    """Ein Rechtsakt, dessen Wortlaut diese Anwendung zitiert.

    ``verzeichnis`` ist **dasselbe**, das der Download-Dialog des
    Gutachten-Moduls benutzt — eine zweite Ablage für denselben Text wäre eine
    zweite Wahrheit darüber, welche Fassung gilt.
    """

    schluessel: str
    celex: str
    titel: str
    verzeichnis: Path
    #: Wo im Code auf diesen Text verwiesen wird (für die Oberfläche).
    zitiert_in: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"schluessel": self.schluessel, "celex": self.celex,
                "titel": self.titel, "verzeichnis": str(self.verzeichnis),
                "zitiert_in": self.zitiert_in}


#: Die Positivliste. Jeder Eintrag ist gegen ``gutachten/_download_dialog.py``
#: geprüft — CELEX und Verzeichnis sind dort dieselben.
VERORDNUNGEN: tuple[Verordnung, ...] = (
    Verordnung("cra", "32024R2847",
               "Verordnung (EU) 2024/2847 (Cyber Resilience Act)",
               Path("data/cra_resources"),
               "CRA: Anhang V (Konformitätserklärung), Anhang VII, "
               "Anhang I Teil II"),
    Verordnung("ki-vo", "32024R1689",
               "Verordnung (EU) 2024/1689 (KI-Verordnung)",
               Path("data/ai_act_resources"),
               "AI Act: Anhang V (Konformitätserklärung), Art. 43/47/48"),
    Verordnung("dsgvo", "32016R0679",
               "Verordnung (EU) 2016/679 (Datenschutz-Grundverordnung)",
               Path("data/dsgvo_resources"),
               "DSGVO: Art. 30 (VVT), Art. 33/34 (Datenpannen), Art. 35 (DSFA)"),
    Verordnung("nis2", "32022L2555",
               "Richtlinie (EU) 2022/2555 (NIS-2)",
               Path("data/nis2_resources"),
               "NIS2: Art. 23 (Meldepflichten)"),
)

_NACH_SCHLUESSEL: dict[str, Verordnung] = {v.schluessel: v for v in VERORDNUNGEN}


def nach_schluessel(schluessel: str) -> Verordnung | None:
    return _NACH_SCHLUESSEL.get(str(schluessel or "").strip().lower())


def _dateien(verzeichnis: Path, celex: str) -> list[dict[str, Any]]:
    """Was zu diesem Rechtsakt im Verzeichnis liegt.

    Gesucht wird nach der CELEX-Nummer im Dateinamen — so wie der
    Download-Dialog sie schreibt (``<celex>_<lang>.pdf``) und so, wie eine von
    Hand hingelegte Datei sie üblicherweise trägt. Eine Datei **ohne** CELEX im
    Namen zählt bewusst nicht: Sie könnte alles sein, und „liegt vor" wäre dann
    eine Behauptung.
    """
    out: list[dict[str, Any]] = []
    if not verzeichnis.is_dir():
        return out
    for datei in sorted(verzeichnis.iterdir()):
        if not datei.is_file() or celex.lower() not in datei.name.lower():
            continue
        try:
            roh = datei.read_bytes()
        except Exception as e:  # noqa: BLE001 — unlesbar ist nicht vorhanden
            logging.getLogger(__name__).debug(
                "%s nicht lesbar: %s", datei, e)
            continue
        out.append({
            "name": datei.name,
            "bytes": len(roh),
            "sha256": hashlib.sha256(roh).hexdigest(),
            # Ein PDF fängt mit %PDF- an. Ohne diese Prüfung hätte eine
            # WAF-Antwort (HTML mit PDF-Dateiendung) als amtliche Fassung
            # gezählt — genau der Fehler, den der Downloader umgeht.
            "ist_pdf": roh[:5] == b"%PDF-",
        })
    return out


def status(nur: str = "") -> list[dict[str, Any]]:
    """Welcher Text liegt vor, welcher nicht.

    ``vorhanden`` ist **nur** wahr, wenn eine Datei mit der CELEX-Nummer im
    Namen da ist **und** wie ein PDF beginnt. „Da, aber keine amtliche
    Fassung" ist der Zustand, der sonst als erfüllt durchgeht.
    """
    out: list[dict[str, Any]] = []
    for v in VERORDNUNGEN:
        if nur and v.schluessel != nur:
            continue
        dateien = _dateien(v.verzeichnis, v.celex)
        out.append({
            **v.as_dict(),
            "dateien": dateien,
            "vorhanden": any(d["ist_pdf"] for d in dateien),
            "nur_fragment": bool(dateien) and not any(d["ist_pdf"] for d in dateien),
        })
    return out


class DownloadFehlgeschlagen(RuntimeError):
    """Der Text ließ sich nicht holen — mit dem Grund, nicht nur „Fehler".

    Erbt von ``RuntimeError``, damit bestehende Aufrufer sie fangen können.
    Der Grund wird mitgegeben, weil der häufigste Fall nicht ein Defekt ist:
    kein Netz auf der Installation, oder die Publikationsstelle antwortet nicht.
    Dann liegt die Lösung beim Menschen — Datei von Hand ablegen —, und dafür
    muss er wissen, woran es lag.
    """


def hole(schluessel: str, *, sprache: str = SPRACHE,
         force: bool = False) -> dict[str, Any]:
    """Den amtlichen Text holen und im vorgesehenen Verzeichnis ablegen.

    Kein eigener Transport: ``gutachten/file_download`` kennt den Weg über die
    Publikationsstelle (SPARQL + Cellar), der an der WAF von eur-lex vorbei
    führt. ``force=False`` lädt nicht erneut, wenn der Text schon vorliegt —
    eine amtliche Fassung ändert sich nicht.
    """
    v = nach_schluessel(schluessel)
    if v is None:
        raise DownloadFehlgeschlagen(
            f"Unbekannter Rechtsakt „{schluessel}“. Erlaubt sind: "
            + ", ".join(x.schluessel for x in VERORDNUNGEN))

    vorher = status(v.schluessel)[0]
    if vorher["vorhanden"] and not force:
        return {**vorher, "geholt": False,
                "hinweis": "Der Text liegt schon vor; eine amtliche Fassung "
                           "ändert sich nicht."}

    try:
        from gutachten.file_download import (Doc, build_requests_session,
                                             download_doc, safe_filename)
    except Exception as e:  # noqa: BLE001 — Modul nicht verfügbar
        raise DownloadFehlgeschlagen(
            f"Der Download-Weg ist nicht verfügbar ({type(e).__name__}). "
            f"Lege die amtliche Fassung von {v.titel} als PDF mit "
            f"„{v.celex}“ im Dateinamen unter {v.verzeichnis} ab.") from e

    v.verzeichnis.mkdir(parents=True, exist_ok=True)
    ziel = v.verzeichnis / safe_filename(f"{v.celex}_{sprache}.pdf")
    try:
        sitzung = build_requests_session()
        doc = Doc(title=f"CELEX {v.celex}", celex=v.celex,
                  kind=v.schluessel.upper(), lang=sprache)
        download_doc(sitzung, doc, ziel)
    except Exception as e:  # noqa: BLE001 — Netz, WAF, Gegenstelle
        raise DownloadFehlgeschlagen(
            f"{v.titel} konnte nicht geholt werden ({type(e).__name__}: {e}). "
            f"Lege die amtliche Fassung als PDF mit „{v.celex}“ im Dateinamen "
            f"unter {v.verzeichnis} ab.") from e

    nachher = status(v.schluessel)[0]
    if not nachher["vorhanden"]:
        raise DownloadFehlgeschlagen(
            f"Die geholte Datei ist keine amtliche Fassung (kein PDF). "
            f"Lege {v.titel} von Hand unter {v.verzeichnis} ab.")
    return {**nachher, "geholt": True, "datei": str(ziel)}


def liegt_vor(schluessel: str) -> bool:
    """Kurzauskunft für die Module — ohne Dateiinhalte in der Antwort."""
    eintraege = status(schluessel)
    return bool(eintraege and eintraege[0]["vorhanden"])


__all__ = ["SPRACHE", "Verordnung", "VERORDNUNGEN", "nach_schluessel",
           "status", "hole", "liegt_vor", "DownloadFehlgeschlagen"]
