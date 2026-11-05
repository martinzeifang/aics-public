"""Was in welcher Vorlage steht (#1790).

Je Modul und Berichtstyp eine Bauanleitung. Die Variablennamen stammen aus den
Adaptern (``<modul>/template_context.py``) und sind **nicht** geraten — sie
wurden aus ``shared.templates.schema.get_variables`` und aus echten
Kontextaufbauten gegen die Entwicklungsdaten entnommen. Eine Vorlage, die einen
Namen erfindet, rendert stillschweigend leer; das fällt erst beim Kunden auf.

Aufbau einer Anleitung: ``(dokumentart, titel_ausdruck, zeile_unten,
untertitel, fuss_mitte, inhalt)``. ``inhalt`` ist eine Funktion, die die
Kapitel in das Dokument schreibt.

HOCH- ODER QUERFORMAT
Das Dokument ist hochformatig; breite Auflistungen stehen in einem eigenen
Querformat-Abschnitt (``with b.querformat(doc)``). Die Regel ist mechanisch,
damit sie später nachvollziehbar bleibt: **quer ab fünf Spalten, und bei vier
Spalten dann, wenn eine davon Freitext trägt** (Titel einer Schwachstelle,
Maßnahme, Begründung, Prüffrage). Alles Schmalere — Reifegrad je Kapitel,
Anhang-VII-Stand, Stammdaten — bleibt hoch; dort kostet Querformat nur Papier.

Eine Ausnahme von Hand: Die **EU-Konformitätserklärung** bleibt durchgehend
hochformatig. Ihr Aufbau folgt Anhang V; die Tabelle zur notifizierten Stelle
hat vier kurze Spalten und braucht die Breite nicht.
"""

from __future__ import annotations

from typing import Callable

from tools.vorlagen import cyberwoks_bausteine as b

#: Projektzeile, die fast jedes Modul gleich führt.
_PROJEKT = "{{ projekt.name }}"
_UNTERNEHMEN = "{{ projekt.unternehmen }}"


def _infos(modul: str, dokumentart: str, zusatz: list[tuple[str, str]] | None = None):
    grund = [
        ("Dokument", dokumentart),
        ("Projekt", _PROJEKT),
        ("Unternehmen", _UNTERNEHMEN),
    ]
    if modul == "cra":
        grund.append(("Produkt", "{{ projekt.produkt }}"))
    if modul == "compliance_audit":
        grund.append(("Prüfungsfokus", "{{ projekt.pruefungsfokus }}"))
    grund += (zusatz or [])
    grund.append(("Stand", "{{ meta.datum or meta.erstellt_am }}"))
    grund.append(("Vertraulichkeit", "Vertraulich — nur für den Empfänger bestimmt"))
    return grund


# ── Gemeinsame Kapitel ──────────────────────────────────────────────────────

def _kap_anforderungen(doc, *, liste: str, bezeichnung: str, nummer: int,
                       mit_kapitel_spalte: bool = True) -> int:
    """Sechs Spalten, eine davon Kommentar — quer."""
    spalten = [("ID", "{{ a.id }}")]
    if mit_kapitel_spalte:
        spalten.append(("Kapitel", "{{ a.kapitel }}"))
    spalten += [
        ("Anforderung", "{{ a.titel }}"),
        ("Fundstelle", "{{ a.ref }}"),
        ("Bewertung", "{{ a.bewertung_label or a.bewertung }}"),
        ("Kommentar", "{{ a.kommentar }}"),
    ]
    with b.querformat(doc):
        b.kapitel(doc, nummer, bezeichnung)
        b.datentabelle(doc, schleife=f"for a in {liste}", spalten=spalten,
                       bedingung=liste,
                       leer_hinweis="Zu diesem Projekt liegen noch keine "
                                    "Bewertungen vor.")
    return nummer + 1


def _kap_massnahmen(doc, *, liste: str, nummer: int, titel: str = "Maßnahmenplan",
                    felder: list[tuple[str, str]] | None = None) -> int:
    """Fünf Spalten mit Maßnahmentext — quer."""
    spalten = felder or [
        ("ID", "{{ m.id }}"),
        ("Gegenstand", "{{ m.titel }}"),
        ("Fundstelle", "{{ m.ref }}"),
        ("Stand", "{{ m.bewertung_label or m.bewertung }}"),
        ("Maßnahme", "{{ m.massnahme }}"),
    ]
    with b.querformat(doc):
        b.kapitel(doc, nummer, titel)
        b.fliesstext(doc,
                     "Die folgenden Punkte sind offen oder nur teilweise "
                     "erfüllt. Die Reihenfolge folgt dem Handlungsbedarf.")
        b.datentabelle(doc, schleife=f"for m in {liste}", spalten=spalten,
                       bedingung=liste,
                       leer_hinweis="Zum Berichtszeitpunkt ist kein Punkt offen.")
    return nummer + 1


def _kap_dokumente(doc, nummer: int) -> int:
    """Fünf Spalten mit Dokumenttitel — quer."""
    with b.querformat(doc):
        b.kapitel(doc, nummer, "Mitgeltende Unterlagen")
        b.datentabelle(
            doc, schleife="for d in dokumente",
            spalten=[("Dokument", "{{ d.titel }}"), ("Art", "{{ d.doc_type }}"),
                     ("Rechtsgrundlage", "{{ d.rechtsgrundlage }}"),
                     ("Fassung", "{{ d.version }}"), ("Stand", "{{ d.stand }}")],
            bedingung="dokumente",
            leer_hinweis="Es sind keine freigegebenen Dokumente hinterlegt.")
    return nummer + 1


def _schluss(doc) -> None:
    # ``layout_wechsel=False``: Die Notiz bleibt im laufenden Abschnitt. Steht
    # davor eine Querformat-Tabelle, wäre eine eigene Hochformat-Seite für eine
    # Zeile Kleindruck verschenkt.
    b.hinweiszeile(
        doc,
        "Dieser Bericht gibt den Stand zum angegebenen Datum wieder. Er ersetzt "
        "keine rechtliche Beratung und keine Konformitätsbewertung durch eine "
        "notifizierte Stelle, soweit eine solche vorgeschrieben ist.",
        layout_wechsel=False)


# ── CRA ─────────────────────────────────────────────────────────────────────

def cra_gesamt(doc):
    b.kapitel(doc, 1, "Management Summary")
    b.kennzahlen(doc, [("{{ meta.reifegrad_pct|round|int }} %", "Reifegrad"),
                       ("{{ meta.bewertete_count }}/{{ meta.gesamt_count }}", "bewertet"),
                       ("{{ meta.ampel|upper }}", "Gesamtampel")])
    b.zwischentitel(doc, "Produkt")
    b.fliesstext(doc, "{{ projekt.beschreibung }}")
    b.zwischentitel(doc, "Reifegrad je Kapitel")
    b.datentabelle(doc, schleife="for k in meta.kapitel",
                   spalten=[("Kapitel", "{{ k.titel }}"),
                            ("Fundstelle", "{{ k.referenz }}"),
                            ("Reifegrad", "{{ k.reifegrad_pct }} %")],
                   bedingung="meta.kapitel")
    n = 2
    b.kapitel(doc, n, "Rechtlicher Rahmen"); n += 1
    b.fliesstext(doc,
                 "Grundlage ist die Verordnung (EU) 2024/2847 (Cyber Resilience Act). "
                 "Das Produkt ist als „{{ projekt.produktklasse_label }}“ eingestuft "
                 "({{ projekt.referenz }}); daraus folgt das Konformitätsbewertungs"
                 "verfahren {{ projekt.konformitaet }}.")
    n = _kap_anforderungen(doc, liste="bewertungen", bezeichnung="Anforderungsbewertung",
                           nummer=n)
    with b.querformat(doc):
        b.kapitel(doc, n, "Schwachstellen"); n += 1
        b.datentabelle(
            doc, schleife="for v in meta.vulns",
            spalten=[("CVE", "{{ v.cve_id }}"), ("Titel", "{{ v.titel }}"),
                     ("Schwere", "{{ v.schwere }}"), ("Status", "{{ v.status }}")],
            bedingung="meta.vulns",
            leer_hinweis="Zum Berichtszeitpunkt sind keine Schwachstellen erfasst.")
    b.kapitel(doc, n, "Risiken aus der Risikobewertung"); n += 1
    b.datentabelle(doc, schleife="for r in risiken",
                   spalten=[("Risiko", "{{ r.name }}"), ("Einstufung", "{{ r.label }}"),
                            ("Wert", "{{ r.wert }}")],
                   bedingung="meta.risiko_verknuepft and risiken",
                   leer_hinweis="Mit diesem Projekt ist keine Risikobewertung verknüpft.")
    n = _kap_dokumente(doc, n)
    _schluss(doc)


def cra_anforderungen(doc):
    b.kapitel(doc, 1, "Lesehilfe")
    b.fliesstext(doc,
                 "Jede Anforderung aus Anhang I der Verordnung (EU) 2024/2847 wird auf "
                 "einer Skala von 0 bis 5 bewertet. Die Fundstelle verweist auf die "
                 "Stelle im Rechtstext.")
    b.kennzahlen(doc, [("{{ meta.bewertete_count }}", "bewertet"),
                       ("{{ meta.gesamt_count }}", "insgesamt"),
                       ("{{ meta.reifegrad_pct|round|int }} %", "Reifegrad")])
    _kap_anforderungen(doc, liste="bewertungen", bezeichnung="Anforderungen im Einzelnen",
                       nummer=2)
    _schluss(doc)


def cra_massnahmen(doc):
    b.kapitel(doc, 1, "Ausgangslage")
    b.fliesstext(doc,
                 "Der Maßnahmenplan führt die Anforderungen auf, die noch nicht "
                 "vollständig erfüllt sind. Grundlage sind Art. 13 und 14 der "
                 "Verordnung (EU) 2024/2847.")
    _kap_massnahmen(doc, liste="bewertungen|selectattr('bewertung','lt',4)|list",
                    nummer=2)
    _schluss(doc)


def cra_release(doc):
    b.kapitel(doc, 1, "Gegenstand")
    # Produkt über ``nachweis.produkt``: Die Pflichtprüfung erkennt an der
    # Variablenwurzel ``nachweis``, dass hier über ein Release geurteilt wird,
    # und verlangt dann Produkt UND Release (#1777). Das ist hier keine
    # Förmlichkeit — ein Vorgangsbericht ohne Produktangabe ist nicht zuordenbar.
    b.infotabelle(doc, [("Produkt", "{{ nachweis.produkt or projekt.produkt }}"),
                        ("Release", "{{ nachweis.version or '—' }}"),
                        ("Produktklasse", "{{ projekt.produktklasse_label }}"),
                        ("Bewertungsweg", "{{ nachweis.bewertungsweg_label }}")])
    b.kapitel(doc, 2, "Ergebnis der Release-Prüfung")
    b.kennzahlen(doc, [("{{ nachweis.ampel_label }}", "Gesamturteil"),
                       ("{{ nachweis.erfuellt }}", "erfüllt"),
                       ("{{ nachweis.offen }}", "offen")])
    b.kapitel(doc, 3, "Offene Punkte")
    b.datentabelle(doc, schleife="for nk in nachweis.nicht_konformitaeten",
                   spalten=[("Anforderung", "{{ nk.requirement_id }}"),
                            ("Gegenstand", "{{ nk.titel }}"),
                            ("Fundstelle", "{{ nk.ref }}")],
                   bedingung="nachweis.nicht_konformitaeten",
                   leer_hinweis="Für dieses Release ist keine Nicht-Konformität offen.")
    with b.querformat(doc):
        b.kapitel(doc, 4, "Begründete Abweichungen")
        b.datentabelle(
            doc, schleife="for a in nachweis.abweichungen_begruendet",
            spalten=[("Anforderung", "{{ a.requirement_id }}"),
                     ("Gegenstand", "{{ a.titel }}"),
                     ("Kategorie", "{{ a.kategorie }}"),
                     ("Begründung", "{{ a.grund }}"),
                     ("Entschieden von", "{{ a.von }}")],
            bedingung="nachweis.abweichungen_begruendet",
            leer_hinweis="Es sind keine Abweichungen begründet akzeptiert.")
    b.kapitel(doc, 5, "Technische Dokumentation (Anhang VII)")
    b.datentabelle(doc, schleife="for a in nachweis.annex_vii",
                   spalten=[("Baustein", "{{ a.label }}"),
                            ("Belegt", "{{ 'ja' if a.belegt else 'nein' }}"),
                            ("Nachweise", "{{ a.nachweis_count }}")],
                   bedingung="nachweis.annex_vii")
    _schluss(doc)


def cra_kundenfassung(doc):
    b.kapitel(doc, 1, "Worum es geht")
    b.fliesstext(doc,
                 "Dieses Dokument fasst den Stand der Cyber-Resilienz von "
                 "{{ projekt.produkt }} für Kundinnen und Kunden zusammen. Es ist "
                 "bewusst ohne interne Fundstellen gehalten.")
    b.kapitel(doc, 2, "Einordnung des Produkts")
    b.infotabelle(doc, [("Produkt", "{{ projekt.produkt }}"),
                        ("Hersteller", "{{ projekt.unternehmen }}"),
                        ("Produktklasse", "{{ projekt.produktklasse_label }}"),
                        ("Rechtsgrundlage", "Verordnung (EU) 2024/2847")])
    b.kapitel(doc, 3, "Stand der Umsetzung")
    b.kennzahlen(doc, [("{{ meta.reifegrad_pct|round|int }} %", "Umsetzungsgrad"),
                       ("{{ meta.bewertete_count }}", "geprüfte Anforderungen")])
    b.fliesstext(doc, "{{ projekt.beschreibung }}")
    b.kapitel(doc, 4, "Was das für den Betrieb bedeutet")
    b.aufzaehlung(doc, schleife="for k in meta.kapitel", ausdruck="{{ k.titel }}: {{ k.reifegrad_pct }} %",
                  bedingung="meta.kapitel")
    b.hinweiszeile(doc,
                   "Diese Kundenfassung gibt den Stand zum angegebenen Datum wieder "
                   "und enthält keine internen Prüfvermerke.")


def cra_konformitaetsnachweis(doc):
    """Pflichtdokument. Produkt **und** Release, Rechtsgrundlage, Gesamturteil
    müssen vorkommen — sonst weist die Prüfung die Vorlage zurück (#1777)."""
    b.kapitel(doc, 1, "Gegenstand des Nachweises")
    b.infotabelle(doc, [
        ("Hersteller", "{{ nachweis.hersteller }}"),
        ("Produkt", "{{ nachweis.produkt }}"),
        ("Release", "{{ nachweis.version }}"),
        ("Produktklasse", "{{ nachweis.produktklasse_label }} "
                          "({{ nachweis.produktklasse_referenz }})"),
        ("Bewertungsverfahren", "{{ nachweis.bewertungsweg_label }}"),
        ("Rechtsgrundlage", "{{ nachweis.rechtsgrundlage }}"),
        ("CE-Kennzeichnung", "{{ nachweis.ce_kennzeichnung }}"),
        ("Ausgestellt am", "{{ nachweis.datum }}"),
    ])
    b.kapitel(doc, 2, "Gesamturteil")
    b.kennzahlen(doc, [("{{ nachweis.ampel_label }}", "Gesamturteil"),
                       ("{{ nachweis.reifegrad_pct|round|int }} %", "Reifegrad"),
                       ("{{ nachweis.erfuellt }}/{{ nachweis.gesamt_anforderungen }}",
                        "erfüllt")])
    b.fliesstext(doc, "{{ nachweis.hinweis }}")
    with b.querformat(doc):
        b.kapitel(doc, 3, "Anforderungen mit Rechtsgrundlage")
        b.datentabelle(
            doc, schleife="for a in nachweis.anforderungen",
            spalten=[("ID", "{{ a.id }}"), ("Anforderung", "{{ a.titel }}"),
                     ("Rechtsgrundlage", "{{ a.rechtsgrundlage }}"),
                     ("Status", "{{ a.status_label }}"),
                     ("Hinweis", "{{ a.hinweis }}")],
            bedingung="nachweis.anforderungen")
        b.kapitel(doc, 4, "Begründete Abweichungen")
        b.datentabelle(
            doc, schleife="for a in nachweis.abweichungen_begruendet",
            spalten=[("Anforderung", "{{ a.requirement_id }}"),
                     ("Gegenstand", "{{ a.titel }}"),
                     ("Kategorie", "{{ a.kategorie }}"),
                     ("Begründung", "{{ a.grund }}"),
                     ("Rechtsgrundlage", "{{ a.rechtsgrundlage }}")],
            bedingung="nachweis.abweichungen_begruendet",
            leer_hinweis="Es sind keine Abweichungen begründet akzeptiert.")
    b.kapitel(doc, 5, "Offene Nicht-Konformitäten")
    b.datentabelle(doc, schleife="for nk in nachweis.nicht_konformitaeten",
                   spalten=[("Anforderung", "{{ nk.requirement_id }}"),
                            ("Gegenstand", "{{ nk.titel }}"),
                            ("Fundstelle", "{{ nk.ref }}")],
                   bedingung="nachweis.nicht_konformitaeten",
                   leer_hinweis="Zum Ausstellungszeitpunkt ist keine Nicht-Konformität offen.")
    with b.querformat(doc):
        b.kapitel(doc, 6, "Akzeptierte Restrisiken")
        b.datentabelle(
            doc, schleife="for r in nachweis.akzeptierte_restrisiken",
            spalten=[("Nr.", "{{ r.nr }}"), ("Risiko", "{{ r.name }}"),
                     ("Kategorie", "{{ r.kategorie }}"),
                     ("Begründung", "{{ r.grund }}"),
                     ("Entschieden von", "{{ r.von }}")],
            bedingung="nachweis.akzeptierte_restrisiken",
            leer_hinweis="Es sind keine Restrisiken formal akzeptiert.")
    b.kapitel(doc, 7, "Technische Dokumentation (Anhang VII)")
    b.datentabelle(doc, schleife="for a in nachweis.annex_vii",
                   spalten=[("Baustein", "{{ a.label }}"),
                            ("Belegt", "{{ 'ja' if a.belegt else 'nein' }}"),
                            ("Nachweise", "{{ a.nachweis_count }}")],
                   bedingung="nachweis.annex_vii")


def cra_konformitaetserklaerung(doc):
    """Pflichtdokument nach Art. 28 i.V.m. Anhang V.

    Der Aufbau folgt den Nummern des Anhangs; ihre Reihenfolge und Bezeichnung
    gehören dem Rechtstext, nicht uns.
    """
    b.fliesstext(doc, "{{ doc.fassung }}")
    b.kapitel(doc, 1, "Produkt mit digitalen Elementen")
    b.infotabelle(doc, [("Produktname", "{{ doc.produkt_name }}"),
                        ("Typ / Modell", "{{ doc.produkt_typ }}"),
                        ("Charge, Serie oder Version", "{{ doc.produkt_charge }}")])
    b.kapitel(doc, 2, "Hersteller")
    b.infotabelle(doc, [("Name", "{{ doc.hersteller }}"),
                        ("Anschrift", "{{ doc.hersteller_adresse }}"),
                        ("Bevollmächtigter", "{{ doc.bevollmaechtigter or '—' }}")])
    b.kapitel(doc, 3, "Verantwortung")
    b.fliesstext(doc, "{{ doc.verantwortungssatz }}")
    b.kapitel(doc, 4, "Gegenstand der Erklärung")
    b.fliesstext(doc, "{{ doc.gegenstand }}")
    b.kapitel(doc, 5, "Konformitätsaussage")
    b.fliesstext(doc, "{{ doc.konformitaetsaussage }}")
    b.fliesstext(doc, "{{ doc.weiteres_unionsrecht }}")
    b.kapitel(doc, 6, "Angewandte Normen und Spezifikationen")
    b.aufzaehlung(doc, schleife="for n in doc.normen", ausdruck="{{ n }}",
                  bedingung="doc.normen",
                  leer_hinweis="{{ doc.normen_text }}")
    b.kapitel(doc, 7, "Notifizierte Stelle")
    b.datentabelle(doc, schleife="for x in [doc]",
                   spalten=[("Name", "{{ x.nb_name }}"),
                            ("Kennnummer", "{{ x.nb_kennnummer }}"),
                            ("Zertifikat", "{{ x.nb_zertifikat }}"),
                            ("Verfahren", "{{ x.nb_verfahren }}")],
                   bedingung="doc.nb_erforderlich",
                   leer_hinweis="Für den gewählten Bewertungsweg ist keine "
                                "notifizierte Stelle erforderlich.")
    b.kapitel(doc, 8, "Zusatzangaben und Unterzeichnung")
    b.fliesstext(doc, "{{ doc.zusatzangaben }}")
    b.infotabelle(doc, [("Ort", "{{ doc.ort }}"), ("Datum", "{{ doc.datum }}"),
                        ("Unterzeichner", "{{ doc.unterzeichner_name }}"),
                        ("Funktion", "{{ doc.unterzeichner_funktion }}")])
    b.hinweiszeile(doc, "{{ doc.fehlende_pflichtfelder_text }}")
    b.fliesstext(doc, "")
    b.fliesstext(doc, "_____________________________________")
    b.hinweiszeile(doc, "{{ doc.unterzeichner_name }} · {{ doc.unterzeichner_funktion }}")


# ── Compliance-Audit ────────────────────────────────────────────────────────

def audit_gesamt(doc):
    b.kapitel(doc, 1, "Gesamtbewertung")
    b.datentabelle(doc, schleife="for f in frameworks",
                   spalten=[("Framework", "{{ f.framework }}"),
                            ("Stufe", "{{ f.stufe_label }}"),
                            ("Erfüllungsquote", "{{ f.quote_prozent }} %"),
                            ("Abdeckung", "{{ f.abdeckung_prozent }} %")],
                   bedingung="frameworks")
    b.kapitel(doc, 2, "Zusammenfassung")
    b.fliesstext(doc, "{{ bericht.zusammenfassung }}")
    b.kapitel(doc, 3, "Bewertung je Framework")
    b.aufzaehlung(doc, schleife="for fb in bericht.framework_bewertungen",
                  ausdruck="{{ fb.framework }}: {{ fb.bewertung }}",
                  bedingung="bericht.framework_bewertungen")
    with b.querformat(doc):
        b.kapitel(doc, 4, "Lücken")
        b.datentabelle(doc, schleife="for l in luecken",
                       spalten=[("Framework", "{{ l.framework }}"),
                                ("Fundstelle", "{{ l.fundstelle }}"),
                                ("Thema", "{{ l.thema }}"),
                                ("Frage", "{{ l.frage }}"),
                                ("Stand", "{{ l.erfuellung_label }}")],
                       bedingung="luecken",
                       leer_hinweis="Es wurden keine Lücken festgestellt.")
        b.kapitel(doc, 5, "Handlungsempfehlungen")
        b.datentabelle(doc, schleife="for h in bericht.handlungsempfehlungen",
                       spalten=[("Maßnahme", "{{ h.massnahme }}"),
                                ("Begründung", "{{ h.begruendung }}"),
                                ("Priorität", "{{ h.prioritaet }}"),
                                ("Aufwand", "{{ h.aufwand }}")],
                       bedingung="bericht.handlungsempfehlungen")
    _schluss(doc)


def audit_anforderungen(doc):
    b.kapitel(doc, 1, "Lesehilfe")
    b.fliesstext(doc,
                 "Aufgeführt sind alle Prüffragen mit dem erhobenen Stand. Offene "
                 "Fragen zählen wie nicht erfüllt — was nicht belegt ist, ist nicht "
                 "nachgewiesen.")
    with b.querformat(doc):
        b.kapitel(doc, 2, "Fragen im Einzelnen")
        b.datentabelle(doc, schleife="for f in fragen",
                       spalten=[("Nr.", "{{ f.nr }}"),
                                ("Framework", "{{ f.framework }}"),
                                ("Fundstelle", "{{ f.fundstelle }}"),
                                ("Frage", "{{ f.frage }}"),
                                ("Antwort", "{{ f.antwort }}"),
                                ("Stand", "{{ f.erfuellung_label }}")],
                       bedingung="fragen")
    _schluss(doc)


def audit_massnahmen(doc):
    b.kapitel(doc, 1, "Ausgangslage")
    b.fliesstext(doc,
                 "Der Maßnahmenplan folgt den festgestellten Lücken. Nicht erfüllte "
                 "Punkte stehen vor teilweise erfüllten.")
    with b.querformat(doc):
        b.kapitel(doc, 2, "Maßnahmen")
        b.datentabelle(
            doc, schleife="for h in bericht.handlungsempfehlungen",
            spalten=[("Maßnahme", "{{ h.massnahme }}"),
                     ("Begründung", "{{ h.begruendung }}"),
                     ("Priorität", "{{ h.prioritaet }}"),
                     ("Aufwand", "{{ h.aufwand }}")],
            bedingung="bericht.handlungsempfehlungen",
            leer_hinweis="Für dieses Audit liegt noch kein Maßnahmenentwurf vor.")
        b.kapitel(doc, 3, "Zugrunde liegende Lücken")
        b.datentabelle(doc, schleife="for l in luecken",
                       spalten=[("Framework", "{{ l.framework }}"),
                                ("Fundstelle", "{{ l.fundstelle }}"),
                                ("Frage", "{{ l.frage }}"),
                                ("Stand", "{{ l.erfuellung_label }}"),
                                ("Kommentar", "{{ l.kommentar }}")],
                       bedingung="luecken")
    _schluss(doc)


# ── NIS2 / AI Act / WiBA — gleiche Gestalt, eigene Felder ───────────────────

def nis2_gesamt(doc):
    b.kapitel(doc, 1, "Management Summary")
    b.kennzahlen(doc, [("{{ projekt.anzahl_bewertet }}/{{ projekt.anzahl_anforderungen }}",
                        "bewertet"),
                       ("{{ meta.anzahl_luecken }}", "Lücken")])
    b.fliesstext(doc, "{{ projekt.beschreibung }}")
    b.zwischentitel(doc, "Stand je Kapitel")
    b.datentabelle(doc, schleife="for k in kapitel",
                   spalten=[("Kapitel", "{{ k.titel }}"),
                            ("Fundstelle", "{{ k.referenz }}"),
                            ("Bewertet", "{{ k.bewertet }}/{{ k.anzahl }}"),
                            ("Stand", "{{ k.prozent }} %")],
                   bedingung="kapitel")
    b.kapitel(doc, 2, "Rechtlicher Rahmen")
    b.fliesstext(doc,
                 "Grundlage ist die Richtlinie (EU) 2022/2555 (NIS2). Die Einrichtung "
                 "ist als „{{ projekt.einrichtungsklasse_label }}“ eingestuft.")
    n = _kap_anforderungen(doc, liste="anforderungen", bezeichnung="Anforderungsbewertung",
                           nummer=3)
    n = _kap_massnahmen(doc, liste="luecken", nummer=n)
    _kap_dokumente(doc, n)
    _schluss(doc)


def nis2_anforderungen(doc):
    b.kapitel(doc, 1, "Lesehilfe")
    b.fliesstext(doc,
                 "Jede Anforderung aus Art. 21 der Richtlinie (EU) 2022/2555 wird auf "
                 "einer Skala von 0 bis 5 bewertet.")
    _kap_anforderungen(doc, liste="anforderungen", bezeichnung="Anforderungen im Einzelnen",
                       nummer=2)
    _schluss(doc)


def nis2_massnahmen(doc):
    b.kapitel(doc, 1, "Ausgangslage")
    b.fliesstext(doc, "Aufgeführt sind die Anforderungen mit Handlungsbedarf "
                      "(Bewertung 2 oder darunter).")
    _kap_massnahmen(doc, liste="luecken", nummer=2)
    _schluss(doc)


def aiact_gesamt(doc):
    b.kapitel(doc, 1, "Management Summary")
    b.fliesstext(doc, "{{ projekt.beschreibung }}")
    b.infotabelle(doc, [("Risikostufe", "{{ klassifizierung.risiko_stufe }}"),
                        ("Organisation", "{{ projekt.organisation }}"),
                        ("KI-System", "{{ projekt.produkt or projekt.name }}")])
    b.kapitel(doc, 2, "Rechtlicher Rahmen")
    b.fliesstext(doc,
                 "Grundlage ist die Verordnung (EU) 2024/1689 (KI-Verordnung). "
                 "Maßgeblich sind die Art. 8 bis 15 für Hochrisiko-KI-Systeme.")
    n = _kap_anforderungen(doc, liste="anforderungen", bezeichnung="Anforderungsbewertung",
                           nummer=3)
    _kap_dokumente(doc, n)
    _schluss(doc)


def aiact_anforderungen(doc):
    b.kapitel(doc, 1, "Lesehilfe")
    b.fliesstext(doc, "Bewertet werden die Anforderungen aus Art. 8–15 der "
                      "Verordnung (EU) 2024/1689.")
    _kap_anforderungen(doc, liste="anforderungen", bezeichnung="Anforderungen im Einzelnen",
                       nummer=2)
    _schluss(doc)


def aiact_massnahmen(doc):
    b.kapitel(doc, 1, "Ausgangslage")
    b.fliesstext(doc, "Der Maßnahmenplan folgt dem Risikomanagement nach Art. 9 "
                      "der Verordnung (EU) 2024/1689.")
    _kap_massnahmen(doc, liste="anforderungen|selectattr('bewertung','lt',4)|list",
                    nummer=2)
    _schluss(doc)


def wiba_gesamt(doc):
    b.kapitel(doc, 1, "Ergebnis")
    b.kennzahlen(doc, [("{{ meta.gesamt_pct }} %", "umgesetzt"),
                       ("{{ meta.beantwortet }}", "beantwortet"),
                       ("{{ meta.offen }}", "offen")])
    b.kapitel(doc, 2, "Themen")
    b.datentabelle(doc, schleife="for t in themen",
                   spalten=[("Thema", "{{ t.titel }}"),
                            ("Prüffragen", "{{ t.prueffragen }}"),
                            ("Umsetzung", "{{ t.pct }} %")],
                   bedingung="themen")
    with b.querformat(doc):
        b.kapitel(doc, 3, "Prüffragen")
        b.datentabelle(doc, schleife="for p in prueffragen",
                       spalten=[("ID", "{{ p.control_id }}"),
                                ("Thema", "{{ p.thema }}"),
                                ("Prüffrage", "{{ p.frage }}"),
                                ("Antwort", "{{ p.status }}"),
                                ("Notiz", "{{ p.notiz }}")],
                       bedingung="prueffragen")
    _kap_dokumente(doc, 4)
    _schluss(doc)


def wiba_anforderungen(doc):
    b.kapitel(doc, 1, "Lesehilfe")
    b.fliesstext(doc,
                 "Die Prüffragen stammen aus „Weg in die Basis-Absicherung“ (WiBA) "
                 "des BSI. Antwortwerte sind ja, nein, nicht relevant oder offen.")
    with b.querformat(doc):
        b.kapitel(doc, 2, "Prüffragen im Einzelnen")
        b.datentabelle(doc, schleife="for p in prueffragen",
                       spalten=[("ID", "{{ p.control_id }}"), ("Nr.", "{{ p.nr }}"),
                                ("Thema", "{{ p.thema }}"),
                                ("Prüffrage", "{{ p.frage }}"),
                                ("Antwort", "{{ p.status }}")],
                       bedingung="prueffragen")
    _schluss(doc)


def wiba_massnahmen(doc):
    b.kapitel(doc, 1, "Ausgangslage")
    b.fliesstext(doc, "Aufgeführt sind die Prüffragen, die nicht mit „ja“ "
                      "beantwortet sind.")
    with b.querformat(doc):
        b.kapitel(doc, 2, "Maßnahmen")
        b.datentabelle(
            doc, schleife="for p in offene_punkte",
            spalten=[("ID", "{{ p.control_id }}"), ("Thema", "{{ p.thema }}"),
                     ("Prüffrage", "{{ p.frage }}"),
                     ("Antwort", "{{ p.status }}"), ("Notiz", "{{ p.notiz }}")],
            bedingung="offene_punkte",
            leer_hinweis="Alle Prüffragen im Scope sind mit „ja“ beantwortet.")
    _schluss(doc)


# ── Risikobewertung ─────────────────────────────────────────────────────────

_RISIKO_SPALTEN = [("Nr.", "{{ r.nr }}"), ("Risiko", "{{ r.risk_name }}"),
                   ("Beschreibung", "{{ r.beschreibung }}"),
                   ("Bewertung", "{{ r.level or r.score }}"),
                   ("Status", "{{ r.status }}")]


def rb_gesamt(doc):
    b.kapitel(doc, 1, "Überblick")
    b.kennzahlen(doc, [("{{ meta.anzahl_risiken }}", "Risiken"),
                       ("{{ meta.anzahl_offen }}", "offen"),
                       ("{{ meta.anzahl_erledigt }}", "erledigt")])
    b.fliesstext(doc, "{{ projekt.beschreibung }}")
    b.kapitel(doc, 2, "Methodik")
    b.fliesstext(doc, "Bewertet wurde nach dem Framework {{ framework }}.")
    with b.querformat(doc):
        b.kapitel(doc, 3, "Risiken")
        b.datentabelle(
            doc, schleife="for r in risiken",
            spalten=_RISIKO_SPALTEN + [("Empfehlung", "{{ r.bewertung_text }}")],
            bedingung="risiken",
            leer_hinweis="In dieser Bewertung ist noch kein Risiko erfasst.")
    _schluss(doc)


def rb_register(doc):
    with b.querformat(doc):
        b.kapitel(doc, 1, "Risiko-Register")
        b.fliesstext(doc, "Reine Auflistung der Risiken ohne Empfehlungen, "
                          "Framework {{ framework }}.")
        b.datentabelle(doc, schleife="for r in risiken", spalten=_RISIKO_SPALTEN,
                       bedingung="risiken")
    _schluss(doc)


# ── DSGVO ───────────────────────────────────────────────────────────────────

def dsgvo_gesamt(doc):
    b.kapitel(doc, 1, "Überblick")
    b.kennzahlen(doc, [("{{ meta.anzahl_anforderungen }}", "Anforderungen"),
                       ("{{ meta.anzahl_vvt }}", "VVT-Einträge"),
                       ("{{ meta.anzahl_dpia }}", "DSFA")])
    b.fliesstext(doc, "{{ projekt.beschreibung }}")
    n = _kap_anforderungen(doc, liste="anforderungen", bezeichnung="Anforderungen",
                           nummer=2)
    with b.querformat(doc):
        b.kapitel(doc, n, "Technische und organisatorische Maßnahmen"); n += 1
        b.datentabelle(doc, schleife="for t in tom_katalog",
                       spalten=[("Schutzziel", "{{ t.ziel }}"),
                                ("Maßnahme", "{{ t.titel }}"),
                                ("Status", "{{ t.status }}"),
                                ("Soll", "{{ t.soll }}"),
                                ("Verantwortlich", "{{ t.verantwortlich }}")],
                       bedingung="tom_katalog")
    b.kapitel(doc, n, "Datenschutz-Folgenabschätzungen"); n += 1
    b.datentabelle(doc, schleife="for d in dpia",
                   spalten=[("ID", "{{ d.dpia_id }}"), ("Titel", "{{ d.titel }}"),
                            ("Bezug VVT", "{{ d.bezug_vvt }}")],
                   bedingung="dpia")
    _kap_dokumente(doc, n)
    _schluss(doc)


def _dsgvo_register(titel: str, einleitung: str, liste: str,
                    spalten: list[tuple[str, str]]) -> Callable:
    def bauen(doc):
        b.kapitel(doc, 1, "Gegenstand")
        b.fliesstext(doc, einleitung)
        # Register sind Auflistungen: vier bis sechs Spalten, darunter Zweck,
        # Grundlage oder Frist als Freitext — durchweg Querformat.
        with b.querformat(doc):
            b.kapitel(doc, 2, titel)
            b.datentabelle(
                doc, schleife=f"for e in {liste}", spalten=spalten,
                bedingung=liste,
                leer_hinweis="In diesem Register ist noch kein Eintrag erfasst.")
        _schluss(doc)
    return bauen


dsgvo_vvt = _dsgvo_register(
    "Verarbeitungstätigkeiten",
    "Das Verzeichnis nach Art. 30 DSGVO führt die Verarbeitungstätigkeiten der "
    "verantwortlichen Stelle.",
    "vvt",
    [("ID", "{{ e.vvt_id }}"), ("Bezeichnung", "{{ e.name }}"),
     ("Zweck", "{{ e.zweck }}"), ("Rechtsgrundlage", "{{ e.rechtsgrundlage }}"),
     ("Betroffene", "{{ e.betroffene_kategorien }}")])

dsgvo_tom = _dsgvo_register(
    "Maßnahmen nach Schutzzielen",
    "Die technischen und organisatorischen Maßnahmen nach Art. 32 DSGVO, "
    "gegliedert nach den Gewährleistungszielen des Standard-Datenschutzmodells.",
    "tom_katalog",
    [("Schutzziel", "{{ e.ziel }}"), ("Maßnahme", "{{ e.titel }}"),
     ("Status", "{{ e.status }}"), ("Soll", "{{ e.soll }}"),
     ("Umsetzung", "{{ e.umsetzung }}"), ("Verantwortlich", "{{ e.verantwortlich }}")])

dsgvo_loeschkonzept = _dsgvo_register(
    "Aufbewahrungs- und Löschregeln",
    "Das Löschkonzept nach Art. 17 DSGVO in Anlehnung an DIN 66398.",
    "loeschregeln",
    [("Regel", "{{ e.regel_id }}"), ("Datenkategorie", "{{ e.datenkategorie }}"),
     ("Aufbewahrungsfrist", "{{ e.aufbewahrungsfrist }}"),
     ("Bezug VVT", "{{ e.vvt_ref }}"), ("Status", "{{ e.status }}")])

dsgvo_betroffenenrechte = _dsgvo_register(
    "Anträge und Fristen",
    "Anträge betroffener Personen nach Art. 15 bis 22 DSGVO mit den Fristen "
    "aus Art. 12 Abs. 3.",
    "betroffenenrechte",
    [("Antrag", "{{ e.antrag_id }}"), ("Art", "{{ e.typ }}"),
     ("Eingang", "{{ e.eingang_datum }}"), ("Frist", "{{ e.frist_datum }}"),
     ("Status", "{{ e.status }}")])

dsgvo_transfer = _dsgvo_register(
    "Drittlandtransfers",
    "Übermittlungen in Drittländer nach Art. 44 bis 49 DSGVO mit dem Stand der "
    "Transfer-Folgenabschätzung.",
    "transfers",
    [("ID", "{{ e.transfer_id }}"), ("Empfänger", "{{ e.empfaenger }}"),
     ("Drittland", "{{ e.drittland }}"), ("Grundlage", "{{ e.grundlage }}"),
     ("TIA", "{{ e.tia_status }}")])

dsgvo_einwilligung = _dsgvo_register(
    "Einwilligungen",
    "Nachweise nach Art. 7 DSGVO: Wer hat wann und auf welchem Weg eingewilligt.",
    "einwilligungen",
    [("ID", "{{ e.einwilligung_id }}"), ("Zweck", "{{ e.zweck }}"),
     ("Zeitpunkt", "{{ e.zeitpunkt }}"), ("Kanal", "{{ e.kanal }}"),
     ("Status", "{{ e.status }}")])

dsgvo_dsfa = _dsgvo_register(
    "Folgenabschätzungen",
    "Datenschutz-Folgenabschätzungen nach Art. 35 DSGVO.",
    "dpia",
    [("ID", "{{ e.dpia_id }}"), ("Titel", "{{ e.titel }}"),
     ("Bezug VVT", "{{ e.bezug_vvt }}"),
     ("Notwendigkeit", "{{ e.notwendigkeit_grund }}")])


def dsgvo_dsb(doc):
    b.kapitel(doc, 1, "Bestellung")
    b.infotabelle(doc, [("Name", "{{ dsb.name }}"),
                        ("Bestellt am", "{{ dsb.bestelldatum }}"),
                        ("Kontakt", "{{ dsb.kontakt_email }}"),
                        ("Veröffentlicht", "{{ dsb.kontakt_veroeffentlicht }}"),
                        ("Der Aufsicht gemeldet", "{{ dsb.gemeldet_aufsicht }}")])
    b.kapitel(doc, 2, "Aufgaben nach Art. 39 DSGVO")
    b.fliesstext(doc, "{{ dsb.aufgaben_nachweis }}")
    _schluss(doc)


# ── Zuordnung ───────────────────────────────────────────────────────────────

#: (modul, typ) → (dokumentart, titel_ausdruck, zeile_unten, untertitel,
#:                 fuss_mitte, inhalt)
PLAENE: dict[tuple[str, str], tuple] = {
    ("cra", "gesamt"): (
        "CRA-Gesamtbericht", "{{ projekt.produkt or projekt.name }}", _UNTERNEHMEN,
        "Cyber Resilience Act · Verordnung (EU) 2024/2847", cra_gesamt),
    ("cra", "anforderungen"): (
        "CRA-Anforderungsstatus", "{{ projekt.produkt or projekt.name }}", _UNTERNEHMEN,
        "Anhang I · Verordnung (EU) 2024/2847", cra_anforderungen),
    ("cra", "massnahmen"): (
        "CRA-Maßnahmenplan", "{{ projekt.produkt or projekt.name }}", _UNTERNEHMEN,
        "Art. 13 und 14 · Verordnung (EU) 2024/2847", cra_massnahmen),
    ("cra", "release"): (
        "CRA-Release-Vorgang", "{{ projekt.produkt or projekt.name }}",
        "Release {{ nachweis.version or '—' }}",
        "Art. 3 Nr. 31 · Verordnung (EU) 2024/2847", cra_release),
    ("cra", "kundenfassung"): (
        "Cyber-Resilienz — Kundenfassung", "{{ projekt.produkt or projekt.name }}",
        _UNTERNEHMEN, "Verordnung (EU) 2024/2847", cra_kundenfassung),
    ("cra", "konformitaetsnachweis"): (
        "Konformitätsnachweis", "{{ nachweis.produkt }}",
        "Release {{ nachweis.version }}",
        "{{ nachweis.rechtsgrundlage }}", cra_konformitaetsnachweis),
    ("cra", "konformitaetserklaerung"): (
        "EU-Konformitätserklärung", "{{ doc.produkt_name }}",
        "{{ doc.produkt_typ }}",
        "Art. 28 i.V.m. Anhang V · Verordnung (EU) 2024/2847",
        cra_konformitaetserklaerung),

    ("compliance_audit", "gesamt"): (
        "Auditbericht", _PROJEKT, _UNTERNEHMEN,
        "{{ projekt.frameworks_text }}", audit_gesamt),
    ("compliance_audit", "anforderungen"): (
        "Audit — Fragenstatus", _PROJEKT, _UNTERNEHMEN,
        "{{ projekt.frameworks_text }}", audit_anforderungen),
    ("compliance_audit", "massnahmen"): (
        "Audit — Maßnahmenplan", _PROJEKT, _UNTERNEHMEN,
        "{{ projekt.frameworks_text }}", audit_massnahmen),

    ("nis2", "gesamt"): (
        "NIS2-Gesamtbericht", _PROJEKT, _UNTERNEHMEN,
        "Richtlinie (EU) 2022/2555", nis2_gesamt),
    ("nis2", "anforderungen"): (
        "NIS2-Anforderungsstatus", _PROJEKT, _UNTERNEHMEN,
        "Art. 21 · Richtlinie (EU) 2022/2555", nis2_anforderungen),
    ("nis2", "massnahmen"): (
        "NIS2-Maßnahmenplan", _PROJEKT, _UNTERNEHMEN,
        "Art. 21 und 23 · Richtlinie (EU) 2022/2555", nis2_massnahmen),

    ("aiact", "gesamt"): (
        "AI-Act-Gesamtbericht", "{{ projekt.produkt or projekt.name }}",
        "{{ projekt.organisation }}", "Verordnung (EU) 2024/1689", aiact_gesamt),
    ("aiact", "anforderungen"): (
        "AI-Act-Anforderungsstatus", "{{ projekt.produkt or projekt.name }}",
        "{{ projekt.organisation }}", "Art. 8–15 · Verordnung (EU) 2024/1689",
        aiact_anforderungen),
    ("aiact", "massnahmen"): (
        "AI-Act-Maßnahmenplan", "{{ projekt.produkt or projekt.name }}",
        "{{ projekt.organisation }}", "Art. 9 · Verordnung (EU) 2024/1689",
        aiact_massnahmen),

    ("wiba", "gesamt"): (
        "WiBA-Nachweisbericht", _PROJEKT, _UNTERNEHMEN,
        "BSI — Weg in die Basis-Absicherung", wiba_gesamt),
    ("wiba", "anforderungen"): (
        "WiBA-Prüffragenstatus", _PROJEKT, _UNTERNEHMEN,
        "BSI — Weg in die Basis-Absicherung", wiba_anforderungen),
    ("wiba", "massnahmen"): (
        "WiBA-Maßnahmenplan", _PROJEKT, _UNTERNEHMEN,
        "BSI — Weg in die Basis-Absicherung", wiba_massnahmen),

    ("risikobewertung", "gesamt"): (
        "Risikobericht", _PROJEKT, _UNTERNEHMEN,
        "Framework {{ framework }}", rb_gesamt),
    ("risikobewertung", "ohne_empfehlungen"): (
        "Risiko-Register", _PROJEKT, _UNTERNEHMEN,
        "Framework {{ framework }}", rb_register),

    ("dsgvo", "gesamt"): (
        "DSMS-Gesamtbericht", _PROJEKT, _UNTERNEHMEN,
        "Verordnung (EU) 2016/679", dsgvo_gesamt),
    ("dsgvo", "vvt"): (
        "Verzeichnis von Verarbeitungstätigkeiten", _PROJEKT, _UNTERNEHMEN,
        "Art. 30 DSGVO", dsgvo_vvt),
    ("dsgvo", "tom"): (
        "Technisch-organisatorische Maßnahmen", _PROJEKT, _UNTERNEHMEN,
        "Art. 32 DSGVO · Standard-Datenschutzmodell", dsgvo_tom),
    ("dsgvo", "loeschkonzept"): (
        "Löschkonzept", _PROJEKT, _UNTERNEHMEN,
        "Art. 17 DSGVO · DIN 66398", dsgvo_loeschkonzept),
    ("dsgvo", "betroffenenrechte"): (
        "Betroffenenrechte", _PROJEKT, _UNTERNEHMEN,
        "Art. 15–22 DSGVO", dsgvo_betroffenenrechte),
    ("dsgvo", "transfer"): (
        "Drittlandtransfers und TIA", _PROJEKT, _UNTERNEHMEN,
        "Art. 44–49 DSGVO", dsgvo_transfer),
    ("dsgvo", "einwilligung"): (
        "Einwilligungen", _PROJEKT, _UNTERNEHMEN,
        "Art. 7 DSGVO", dsgvo_einwilligung),
    ("dsgvo", "dsfa"): (
        "Datenschutz-Folgenabschätzungen", _PROJEKT, _UNTERNEHMEN,
        "Art. 35 DSGVO", dsgvo_dsfa),
    ("dsgvo", "dsb"): (
        "Datenschutzbeauftragte:r", _PROJEKT, _UNTERNEHMEN,
        "Art. 37–39 DSGVO", dsgvo_dsb),
}
