"""Die amtlichen Verordnungstexte in die Installation holen (#1889/#1894).

WARUM DIESE DATEI EXISTIERT
---------------------------
Mehrere Module zitieren Fundstellen, die in ein unterschriebenes Dokument
gedruckt werden — Anhang V der CRA (``cra/doc_export``), Anhang V der KI-VO
(``ai_act/doc_export``), Artikel der DSGVO. Die Lehre aus #1763/#1792 ist, dass
eine erfundene Nummer dort schlimmer ist als keine Angabe, und deshalb steht in
beiden Modulen: Maßgeblich ist das Amtsblatt.

**Nur ließ sich der Text nicht beschaffen.** Herunterladen konnte ihn
ausschließlich der Tkinter-Dialog des Gutachten-Moduls — eine
Desktop-Oberfläche, die der Administrator einer gehosteten Installation nicht
hat. Die Fähigkeit war da und nicht bedienbar; dieselbe Form wie die SBOM, die
sich holen aber nicht herunterladen ließ (#1823), und wie die Hilfe, deren
Handbuch nicht im Image lag (#1878).

**Seit #1955 ist diese Datei der einzige Weg.** Der Desktop ist
zurückgebaut, der Dialog (``gutachten/_download_dialog.py``) ist entfernt —
der Transport darunter (``gutachten/file_download.py``) bleibt und wird hier
und von ``server/api/compliance_audit.py`` benutzt. Damit ist die
Positivliste unten nicht mehr gegen eine zweite Liste geprüft, sondern **ist**
die Liste; die CELEX-Nummern sind entsprechend festgenagelt (siehe
``tests/test_verordnungstexte_1894.py``). Ein zweiter CELEX wäre ein anderer
Rechtsakt, und ein falscher wird in ein unterschriebenes Dokument gedruckt
(#1763/#1792).

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

    ``verzeichnis`` ist **dasselbe**, das der entfernte Download-Dialog des
    Gutachten-Moduls benutzte (#1955) und das die Module zum Nachschlagen
    erwarten (``ai_act/doc_export.VERORDNUNG_VERZEICHNIS``) — eine zweite
    Ablage für denselben Text wäre eine zweite Wahrheit darüber, welche
    Fassung gilt.
    """

    schluessel: str
    celex: str
    titel: str
    verzeichnis: Path
    #: Wo im Code auf diesen Text verwiesen wird (für die Oberfläche).
    zitiert_in: str = ""
    #: Direkte Quelle für einen Rechtsakt **ohne** CELEX (#2061). Leer heißt:
    #: über die Publikationsstelle, wie bisher.
    quelle: str = ""
    #: Der kanonische Dateiname. Nur für die direkte Quelle gesetzt; dort wird
    #: **exakt** verglichen und nicht als Teilzeichenkette. Ein ``in``-Vergleich
    #: auf „ao" trifft jeden Dateinamen, in dem diese zwei Buchstaben
    #: vorkommen, und „liegt vor" wäre dann eine Behauptung.
    dateiname: str = ""

    @property
    def kennung(self) -> str:
        """Woran diese Anwendung den Text im Verzeichnis erkennt.

        Bei einem EU-Rechtsakt die CELEX-Nummer, bei einem nationalen Gesetz
        der kanonische Dateiname. Die Meldungen nennen sie, damit der
        Administrator weiß, wie die Datei heißen muss, wenn er sie von Hand
        ablegt.
        """
        return self.celex or self.dateiname

    def as_dict(self) -> dict[str, Any]:
        return {"schluessel": self.schluessel, "celex": self.celex,
                "titel": self.titel, "verzeichnis": str(self.verzeichnis),
                "zitiert_in": self.zitiert_in, "quelle": self.quelle,
                "dateiname": self.dateiname, "kennung": self.kennung}


#: Die Positivliste. Bis #1955 gegen ``gutachten/_download_dialog.py``
#: geprüft; seit dessen Entfernung ist sie die einzige Quelle — die
#: CELEX-Nummern stehen deshalb im Test fest.
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
    # --- Nationale Gesetze (#2061) ---------------------------------------
    # Dieselbe Begründung wie oben, nur für deutsches Recht: Die Suite
    # zitiert § 406/§ 407a ZPO in jedem Gerichtsgutachten, § 38 BDSG in der
    # DSB-Pflichtprüfung, § 147 AO und das HGB in den Aufbewahrungsfristen
    # des Löschkonzepts, § 11 EnWG im NIS2-Assistenten und das BSIG als
    # nationale Umsetzung der NIS-2-Richtlinie. Nachlesen ließ sich keiner
    # davon — die Positivliste kannte nur EUR-Lex.
    Verordnung("zpo", "", "Zivilprozessordnung (ZPO)",
               Path("data/de_resources"),
               "Gutachten: § 406 (Befangenheit), § 407a (Pflichten des "
               "Sachverständigen)",
               quelle="https://www.gesetze-im-internet.de/zpo/ZPO.pdf",
               dateiname="DE_ZPO.pdf"),
    Verordnung("bdsg", "", "Bundesdatenschutzgesetz (BDSG)",
               Path("data/de_resources"),
               "DSGVO: § 38 (DSB-Pflicht), § 26 (Beschäftigtendaten)",
               quelle="https://www.gesetze-im-internet.de/bdsg_2018/BDSG.pdf",
               dateiname="DE_BDSG.pdf"),
    Verordnung("ao", "", "Abgabenordnung (AO)",
               Path("data/de_resources"),
               "DSGVO: § 147 (Aufbewahrungsfristen im Löschkonzept)",
               quelle="https://www.gesetze-im-internet.de/ao_1977/AO.pdf",
               dateiname="DE_AO.pdf"),
    Verordnung("hgb", "", "Handelsgesetzbuch (HGB)",
               Path("data/de_resources"),
               "DSGVO: gesetzliche Aufbewahrungspflichten (§ 257)",
               quelle="https://www.gesetze-im-internet.de/hgb/HGB.pdf",
               dateiname="DE_HGB.pdf"),
    Verordnung("enwg", "", "Energiewirtschaftsgesetz (EnWG)",
               Path("data/de_resources"),
               "NIS2: IT-Sicherheitskatalog § 11 EnWG",
               quelle="https://www.gesetze-im-internet.de/enwg_2005/EnWG.pdf",
               dateiname="DE_EnWG.pdf"),
    # Das BSIG liegt bei den NIS-2-Texten und trägt **denselben** Dateinamen
    # wie der Weg in ``gutachten/file_download`` (Zeile 1051 ff.) — zwei
    # Ablagen für dasselbe Gesetz wären zwei Wahrheiten darüber, welche
    # Fassung gilt.
    Verordnung("bsig", "", "BSI-Gesetz (BSIG, NIS-2-Umsetzung)",
               Path("data/nis2_resources"),
               "NIS2: nationale Umsetzung der Richtlinie (EU) 2022/2555",
               quelle="https://www.gesetze-im-internet.de/bsig_2025/BSIG.pdf",
               dateiname="DE_BSIG_2025.pdf"),
)

_NACH_SCHLUESSEL: dict[str, Verordnung] = {v.schluessel: v for v in VERORDNUNGEN}


def nach_schluessel(schluessel: str) -> Verordnung | None:
    return _NACH_SCHLUESSEL.get(str(schluessel or "").strip().lower())


def _dateien(verzeichnis: Path, celex: str, *,
             exakt: bool = False) -> list[dict[str, Any]]:
    """Was zu diesem Rechtsakt im Verzeichnis liegt.

    Gesucht wird nach der CELEX-Nummer im Dateinamen — so wie :func:`hole`
    sie schreibt (``<celex>_<lang>.pdf``) und so, wie eine von
    Hand hingelegte Datei sie üblicherweise trägt. Eine Datei **ohne** CELEX im
    Namen zählt bewusst nicht: Sie könnte alles sein, und „liegt vor" wäre dann
    eine Behauptung.
    """
    out: list[dict[str, Any]] = []
    if not verzeichnis.is_dir():
        return out
    for datei in sorted(verzeichnis.iterdir()):
        if not datei.is_file():
            continue
        if exakt:
            # Nationale Gesetze tragen keine CELEX-Nummer; verglichen wird der
            # kanonische Dateiname. Ein ``in``-Vergleich auf „AO" oder „ZPO"
            # träfe beliebige Dateien, und das Ergebnis hieße „liegt vor".
            if datei.name.lower() != celex.lower():
                continue
        elif celex.lower() not in datei.name.lower():
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
        dateien = _dateien(v.verzeichnis, v.kennung,
                           exakt=bool(v.quelle))
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
        from gutachten.file_download import (Doc, ExtraResource,
                                             build_requests_session,
                                             download_doc,
                                             download_extra_resource,
                                             safe_filename)
    except Exception as e:  # noqa: BLE001 — Modul nicht verfügbar
        raise DownloadFehlgeschlagen(
            f"Der Download-Weg ist nicht verfügbar ({type(e).__name__}). "
            f"Lege die amtliche Fassung von {v.titel} als PDF mit "
            f"\u201e{v.kennung}\u201c im Dateinamen unter {v.verzeichnis} ab."
        ) from e

    v.verzeichnis.mkdir(parents=True, exist_ok=True)
    ziel = (v.verzeichnis / safe_filename(v.dateiname) if v.quelle
            else v.verzeichnis / safe_filename(f"{v.celex}_{sprache}.pdf"))
    try:
        sitzung = build_requests_session()
        if v.quelle:
            # Nationale Gesetze (#2061): kein CELEX, also keine
            # Publikationsstelle. Geholt wird über **denselben** Helfer, den
            # der Gutachten-Download für das BSIG schon benutzt — ein
            # zweiter Transport wäre der sechste eigene HTTP-Weg im Haus,
            # und ``download_extra_resource`` prüft die Magic Bytes selbst.
            erg = download_extra_resource(
                sitzung,
                ExtraResource(name=v.titel, url=v.quelle,
                              filename=v.dateiname),
                v.verzeichnis, force=True)
            if not erg.ok:
                raise RuntimeError(erg.error or "unbekannter Fehler")
        else:
            doc = Doc(title=f"CELEX {v.celex}", celex=v.celex,
                      kind=v.schluessel.upper(), lang=sprache)
            download_doc(sitzung, doc, ziel)
    except Exception as e:  # noqa: BLE001 — Netz, WAF, Gegenstelle
        raise DownloadFehlgeschlagen(
            f"{v.titel} konnte nicht geholt werden ({type(e).__name__}: {e}). "
            f"Lege die amtliche Fassung als PDF mit \u201e{v.kennung}\u201c im "
            f"Dateinamen unter {v.verzeichnis} ab.") from e

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
