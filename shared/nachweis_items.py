"""Verknüpfte Nachweisdokumente als Evidenz für die KI-Bewertung (#1937).

DER BEFUND
Am 02.11.2026 wurden die Dokumente des CRA-Dossiers als Nachweise an die
Anforderungen gehängt (``cra_dokumente`` mit ``anforderung_id``, 20 Zeilen auf
Produktiv). Die Massenbewertung danach hat sie **nicht angerechnet** — und
zwar nicht teilweise, sondern gar nicht: ``cra/evidence_provider.py`` hatte
vier Sammelfunktionen, und **keine** las ``cra_dokumente``.

Die Folge sind Bewertungen, die vorhandene Nachweise als fehlend melden. Aus
dem Lauf vom 02.11.: „keine ausdrückliche, dokumentierte Benennung eines
CRA-Verantwortlichen" für IMPL-01 — die Benennung steht namentlich in
``docs/cra/governance.md``, in einer Tabelle, die genau so heißt.

Dieselbe Klasse wie #1735 (die Vorlage wirkte nur im Test-Export), #1840
(``confirmed`` wurde gesetzt und nie gelesen) und #1841 (das Budget kam beim
Anbieter nie an): **Es schlägt nichts fehl, es wirkt nur nicht.** Für Kunden
heißt das: Wer seine Nachweise sorgfältig verknüpft, bekommt dieselbe
Bewertung wie jemand, der es nicht tut.

WARUM DAS HIER UND NICHT IM CRA-PROVIDER STEHT
Alle sechs Module führen dieselbe Beziehung — CRA über ``cra_dokumente``, die
übrigen über ``<modul>_managed_docs`` (#1149). Eine Lösung nur für CRA wäre die
Spiegel-Liste aus #1731/#1735, und bei der zweiten Kopie fehlt die
Zusammenführung oder der Volltext.

WAS BEWUSST NICHT PASSIERT
**Die Adresse wird nicht abgerufen.** Ein ``doc_path``, der mit ``http``
beginnt, ist eine Eingabe des Anwenders; ihn serverseitig zu holen wäre die
SSRF-Lücke, die #1761 ausdrücklich ausgeschlossen hat. Name, Typ, Baustein und
Zuordnung stehen in der eigenen Datenbank und kosten nichts.

**Und der Titel wird nicht als Inhalt ausgegeben.** Der Block sagt „es liegt
ein Dokument *mit diesem Titel* vor", nicht „der Nachweis ist erbracht". Der
Unterschied gehört in den Text, sonst rechnet das Modell einen Dateinamen als
Erfüllung an — und das wäre schlimmer als die Lücke, die hier behoben wird.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.evidence_context import EvidenceItem, _clip

#: Wie viele Zeichen Volltext je Datei höchstens in den Block gehen. Mehr
#: verdrängt in `rank_and_truncate` andere Nachweise, und ein Modell, dem man
#: ein ganzes Dokument vorlegt, antwortet schlechter (die Erfahrung aus #1878).
_VOLLTEXT_JE_DATEI = 1200


def _dateikennung(zeile: dict[str, Any]) -> str | None:
    """Die Datei hinter einer Nachweiszeile, falls es eine gibt.

    ``doc_path='evidence:<id>'`` adressiert eine Datei im Nachweis-Store.
    Darüber führt #1824 Mehrfachnennungen zusammen — **über die Kennung, nicht
    über den Namen**: Gleiche Namen sind ein Indiz, keine Identität.
    """
    pfad = str(zeile.get("doc_path") or "").strip()
    return pfad if pfad.startswith("evidence:") else None


def _zusammenfuehren(zeilen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Denselben Nachweis nur einmal.

    Auf Produktiv lag derselbe Pentest-Bericht **achtmal** in
    ``cra_dokumente`` (#1824). Acht „Nachweise" für einen Test im Prompt sind
    keine acht Nachweise — sie sehen nur so aus, und genau das soll ein
    Nachweisblock nicht tun.

    Zusammengeführt wird über die Datei-Kennung; innerhalb einer Quelle
    zusätzlich die exakte Wiederholung (Name + Typ). Über Quellen hinweg wird
    **nicht** nach Namen zusammengeführt.
    """
    gesehen_datei: set[str] = set()
    gesehen_exakt: set[tuple[str, str]] = set()
    raus: list[dict[str, Any]] = []
    for z in zeilen:
        kennung = _dateikennung(z)
        if kennung:
            if kennung in gesehen_datei:
                continue
            gesehen_datei.add(kennung)
        else:
            schluessel = (str(z.get("doc_name") or "").strip().lower(),
                          str(z.get("doc_type") or "").strip().lower())
            if schluessel in gesehen_exakt:
                continue
            gesehen_exakt.add(schluessel)
        raus.append(z)
    return raus


def _volltext(kennung: str) -> str:
    """Volltext einer Datei aus dem Nachweis-Store, soweit erschlossen (#1861).

    Für diese Dateien gibt es den Text bereits — ihn nicht mitzugeben hieße,
    den Nachweis auf seinen Dateinamen zu reduzieren. Best effort: Ist nichts
    erschlossen (etwa ein Scan ohne Texterkennung), bleibt es beim Titel, und
    das ist eine ehrliche Aussage über die Akte.
    """
    doc_id = kennung.split("evidence:", 1)[1].strip()
    if not doc_id:
        return ""
    try:
        from evidence.db import DEFAULT_DB_PATH as _EV_DB, get_document, list_chunks
        dok = get_document(_EV_DB, doc_id)
        if not dok:
            return ""
        text = " ".join(str(getattr(c, "text", "") or "")
                        for c in (list_chunks(_EV_DB, doc_id) or []))
        if not text.strip():
            text = str(getattr(dok, "extracted_text", "") or "")
        return _clip(" ".join(text.split()), _VOLLTEXT_JE_DATEI)
    except Exception:  # noqa: BLE001
        return ""


def _text(zeile: dict[str, Any], requirement_id: str) -> str:
    """Was im Block über diesen Nachweis steht.

    Die Reihenfolge ist Absicht: erst **was es ist**, dann der Volltext. Und
    der Vorsatz „verknüpfter Nachweis" bleibt stehen, auch wenn Volltext
    dabei ist — er sagt dem Modell, dass hier ein Beleg *zugeordnet* wurde und
    nicht, dass jemand die Erfüllung festgestellt hat.
    """
    typ = str(zeile.get("doc_type") or "").strip() or "Dokument"
    baustein = str(zeile.get("annex_baustein") or "").strip()
    teile = [f"verknüpfter Nachweis zu {requirement_id}: „{zeile.get('doc_name') or '(ohne Titel)'}“",
             f"Art: {typ}"]
    if baustein:
        teile.append(f"Anhang-VII-Baustein: {baustein}")
    kennung = _dateikennung(zeile)
    if kennung:
        inhalt = _volltext(kennung)
        if inhalt:
            teile.append(f"Inhalt (Auszug): {inhalt}")
        else:
            teile.append("Datei in der Nachweisablage, Text nicht erschlossen")
    return " · ".join(teile)


def cra_dokument_items(projekt_name: str, requirement_id: str,
                       db_path: Path) -> list[EvidenceItem]:
    """Nachweise aus ``cra_dokumente``, die an dieser Anforderung hängen."""
    rid = str(requirement_id or "").strip()
    if not rid:
        return []
    try:
        from cra.traceability_db import list_dokumente
        zeilen = [z for z in list_dokumente(db_path, projekt_name)
                  if str(z.get("anforderung_id") or "").strip().upper() == rid.upper()]
    except Exception:  # noqa: BLE001
        return []
    return [
        EvidenceItem(
            "Verknüpfter Nachweis", "document",
            f"cra_dokumente:{z.get('id')}", _text(z, rid),
            # Höher als der Schwachstellen-Sync (1,8): Ein ausdrücklich an
            # **diese** Anforderung gehängter Nachweis ist die zielgenaueste
            # Evidenz, die die Akte hat.
            relevance=2.0)
        for z in _zusammenfuehren(zeilen)
    ]


def managed_doc_items(modul: str, projekt_name: str, requirement_id: str,
                      db_path: Path) -> list[EvidenceItem]:
    """Dasselbe für die fünf Module mit ``<modul>_managed_docs`` (#1149).

    Dort hängt ein Dokument nicht an einer Anforderung, sondern an einem
    Katalog-Eintrag (``doc_key``). Angerechnet wird deshalb, was **freigegeben
    oder finalisiert** ist — der Zustand, den die Berichte ebenfalls verlangen.
    Ein Entwurf erscheint bewusst nicht: Er ist kein Nachweis, und ihn als
    einen auszugeben wäre genau die Falschaussage, die #1765 beim
    KI-Entwurf verhindert.
    """
    if not projekt_name:
        return []
    try:
        from shared.documents.db import list_documents
        # #2087/2: Gebraucht werden Status und Titel — nicht der Volltext.
        # Diese Funktion läuft im Nachweis-Aufbau **je Anforderung** (#2086);
        # bei 130 Anforderungen und 6 Dokumenten à 100 kB waren das ≈ 78 MB.
        zeilen = list_documents(db_path, modul, projekt_name, mit_inhalt=False)
    except Exception:  # noqa: BLE001
        return []
    freigegeben = [z for z in zeilen
                   if str(z.get("status") or "").lower() in ("freigegeben", "finalisiert")]
    if not freigegeben:
        return []
    namen = ", ".join(f"„{z.get('titel') or z.get('doc_key') or '?'}“"
                      for z in freigegeben[:8])
    return [EvidenceItem(
        "Freigegebene Pflichtdokumente", "document",
        f"{modul}_managed_docs:{projekt_name}",
        _clip(f"{len(freigegeben)} freigegebene(s) bzw. finalisierte(s) Dokument(e) "
              f"im Register: {namen}"),
        relevance=1.6)]
