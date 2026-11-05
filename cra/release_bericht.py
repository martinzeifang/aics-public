"""Vorgangsbericht je Release — für Management und Ablage (#1748).

**Abgrenzung, die diese Datei trägt.** Der juristische Konformitätsnachweis ist
:mod:`cra.konformitaet_report` (Anforderungen mit Rechtsgrundlage, Verfahren nach
Anhang VIII, begründete Abweichungen, Anhang VII). Dieser Bericht hier ist das
andere Stück: Er beschreibt den **Vorgang** — wer hat was wann festgestellt,
geprüft, freigegeben, und worauf stützt sich das. Er **zitiert** den Nachweis
(Archivverweis mit SHA-256) und erzeugt ihn nicht neu. Zwei Renderer für dasselbe
Dokument wären zwei Wahrheiten; genau das war die Lehre aus #1727.

Drei Entscheidungen, die den Inhalt prägen:

* **Gerechnet und erklärt bleiben getrennt.** Die gerechneten Prüfpunkte kommen
  aus :func:`cra.konformitaet_gate.evaluate`, die Entscheidungen aus der
  Release-Checkliste des Vorgangs. Der Bericht rechnet nichts selbst nach.
* **Der eingefrorene Stand hat Vorrang.** Ist der Vorgang eingereicht, wurde
  gegen den damals eingefrorenen Rechenstand (``gate_json``) geprüft. Genau der
  steht im Bericht; der heutige Stand wird daneben genannt, wenn er abweicht.
  Andernfalls behauptete der Bericht, es sei etwas geprüft worden, was heute
  anders aussieht.
* **Nicht geprüft ist nicht erfüllt.** Ein Befund, den die Anwendung nicht
  ermitteln konnte (``None``), erscheint als „nicht geprüft" und nie als Haken.
  Ein stiller Rückfall auf 0/„ok" wäre in einem Nachweis der gefährlichste
  Fehler, weil er wie ein gutes Ergebnis aussieht (#1741/#1751).

Ein Vorgang **ohne** Freigabe ist der Normalfall im Tagesgeschäft — man braucht
den Bericht, um ihn prüfen zu lassen. Er wird deshalb erzeugt und sichtbar als
**Entwurf** gekennzeichnet, nicht verweigert.

DIE SPRACHE GEHÖRT DEM MANDANTEN (#1954)
Die Prosa dieses Berichts steht in :data:`TEXTE` und wird in der Sprache des
Mandanten gedruckt (``firmen.sprache``, aufgelöst über
:func:`shared.reports.texte.aufloesen`; ein ausdrücklich übergebenes ``sprache``
hat Vorrang, fail-open auf Deutsch).

**Nicht** übersetzt wird, was aus anderen Quellen durchläuft: die Beschriftung
und der ``rechtsbezug`` der Prüfpunkte aus :mod:`cra.release_checkliste`, die
Titel und Hinweise der offenen Punkte aus :mod:`cra.konformitaet_gate`, die
Bezeichnungen aus :mod:`cra.release_art` und die Angaben des Mandanten selbst.
Sie erscheinen deutsch, auch im englischen Dokument — ihre Übersetzung ist ein
eigener Vorgang in den Dateien, in denen sie entstehen. Ein halb übersetzter
Prüfpunkt wäre der schlechtere Ausgang: Er sähe aus wie eine eigene Aussage
dieses Berichts.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

from shared.reports import texte as _rt

DB_PATH = Path("data/db/cra.sqlite")
RB_DB = Path("data/db/risikobewertung.sqlite")

#: Die Prosa des Vorgangsberichts je Sprache (#1954).
#:
#: **Nummern und Fundstellen bleiben unangetastet**, nur die Bezeichnung der
#: Anlage folgt dem englischen Amtsblatt (``Anhang VII`` → ``Annex VII``,
#: ``Nr. 6`` → ``No. 6``, ``Art. 13 Abs. 2`` → ``Art. 13(2)``). Die Ziffern
#: werden nicht angerührt — die Lehre aus #1763/#1792, wo geratene Fundstellen
#: in Dokumente gedruckt wurden, die ein Prüfer liest.
#:
#: Die englischen Begriffe sind die der amtlichen englischen Fassung der
#: Verordnung (EU) 2024/2847: *substantial modification*, *functionality
#: update*, *security update*, *support period*, *placing on the market*,
#: *market surveillance authority*, *conformity assessment*, *product with
#: digital elements*.
#:
#: Die Schlüssel der gerechneten Prüfpunkte folgen einer Regel statt einer
#: zweiten Liste: ``g_<gate-quelle>_ok`` und ``g_<gate-quelle>_fehl``. Eine
#: Zuordnungstabelle daneben wäre die Spiegel-Liste aus #1731/#1735 — und
#: zwar eine, die niemandem auffällt, weil ein fehlender Eintrag im Dokument
#: nur als Schlüsselname erscheint.
TEXTE: dict[str, dict[str, str]] = {
    "de": {
        "regulation": "Verordnung (EU) 2024/2847 (Cyber Resilience Act)",

        "ampel_gruen": "KONFORM",
        "ampel_bedingt": "BEDINGT KONFORM",
        "ampel_rot": "NICHT KONFORM",
        "ampel_unbewertet": "NICHT BEWERTET",

        "status_entwurf": "Entwurf",
        "status_in_pruefung": "in Prüfung",
        "status_freigegeben": "freigegeben",
        "status_zurueckgewiesen": "zurückgewiesen",
        "status_veroeffentlicht": "veröffentlicht",

        "art_gerechnet": "Gerechnete Prüfpunkte",
        "art_entscheidung": "Entscheidungen (mit Begründung und Person)",
        "art_gleichbleibend": "Gleichbleibende Angaben (je Release bestätigt)",

        "entwurf_marker": "ENTWURF — nicht freigegeben",

        "leer": "—",
        "person_am": "{person} am {datum}",

        # ── Gerechnete Prüfpunkte ──────────────────────────────────────────
        "nicht_geprueft": "nicht geprüft",
        "nicht_auswertbar": "nicht auswertbar ({wert})",
        "kein_rechenergebnis": "kein Rechenergebnis zur Quelle '{quelle}'",
        "kein_rechenstand": "nicht geprüft (kein Rechenstand vorhanden)",

        "g_offene_kritische_schwachstellen_ok":
            "keine offenen kritischen oder hohen Befunde",
        "g_offene_kritische_schwachstellen_fehl":
            "{n} offene kritische/hohe Schwachstelle(n)",
        "g_behobene_ohne_advisory_ok":
            "alle in dieser Version behobenen Schwachstellen sind veröffentlicht",
        "g_behobene_ohne_advisory_fehl":
            "{n} behobene Schwachstelle(n) ohne Advisory",
        "g_sbom_version_fehlt_ok": "SBOM zur Release-Version vorhanden",
        "g_sbom_version_fehlt_fehl": "keine SBOM zu dieser Release-Version",
        "g_support_ueberschritten_ok":
            "Release liegt im zugesagten Support-Zeitraum",
        "g_support_ueberschritten_fehl": "Release liegt nach dem Support-Ende",
        "g_ueberfaellige_meldungen_ok": "keine überfällige Meldefrist",
        "g_ueberfaellige_meldungen_fehl": "{n} überfällige Meldefrist(en)",
        "g_annex_vollstaendig_ok": "technische Dokumentation vollständig belegt",
        "g_annex_vollstaendig_fehl":
            "Nachweise der technischen Dokumentation fehlen",
        "g_doc_ausgestellt_ok":
            "EU-Konformitätserklärung ausgestellt bzw. freigegeben",
        "g_doc_ausgestellt_fehl": "EU-Konformitätserklärung nicht ausgestellt",
        "g_bewertungsweg_unzulaessig_ok":
            "Konformitätsbewertungsweg für die Produktklasse zulässig",
        "g_bewertungsweg_unzulaessig_fehl":
            "Konformitätsbewertungsweg ist für diese Produktklasse NICHT zulässig",
        "g_fremdkomponenten_unbewertet_ok":
            "neue und angehobene Fremdkomponenten sind bewertet",
        "g_fremdkomponenten_unbewertet_fehl":
            "{n} neu aufgenommene oder angehobene Fremdkomponente(n) ohne "
            "dokumentierte Bewertung",
        "g_komponenten_befund_widerspruch_ok":
            "keine Bewertung widerspricht einem offenen Befund",
        "g_komponenten_befund_widerspruch_fehl":
            "{n} Fremdkomponente(n) als „nicht relevant“ bewertet trotz "
            "offenem Befund",
        "g_release_art_widersprueche_ok":
            "die erklärte Art des Releases passt zur Akte",
        "g_release_art_widersprueche_fehl":
            "{n} Widerspruch/Widersprüche zwischen erklärter Release-Art und "
            "dem, was in der Akte steht",
        "g_upstream_meldung_offen_ok":
            "eigene Funde in Fremdkomponenten sind dem jeweiligen "
            "Hersteller gemeldet",
        "g_upstream_meldung_offen_fehl":
            "{n} Schwachstelle(n) in Fremdkomponenten ohne dokumentierte "
            "Meldung an deren Hersteller",
        "g_update_zusagen_fehlen_ok":
            "Sicherheitsupdates kostenlos und über einen getrennten Kanal "
            "zugesagt",
        "g_update_zusagen_fehlen_fehl":
            "Update-Zusagen nicht vollständig dokumentiert",
        "g_kaufhinweis_fehlt_ok": "Support-Ende ist vor dem Kauf zugänglich",
        "g_kaufhinweis_fehlt_fehl":
            "kein Hinweis auf das Support-Ende beim Kauf",
        "g_aufbewahrungsfristen_unbestimmbar_ok":
            "Aufbewahrungs- und Update-Fristen sind bestimmbar",
        "g_aufbewahrungsfristen_unbestimmbar_fehl":
            "Aufbewahrungs-/Update-Fristen nicht bestimmbar (Bezugsdaten fehlen)",
        "g_marktaufsicht_versaeumt_ok":
            "keine versäumte Frist gegenüber der Marktüberwachung",
        "g_marktaufsicht_versaeumt_fehl":
            "{n} versäumte Frist(en) gegenüber der Marktüberwachung",
        "g_sicherheitstests_mangel_ok":
            "Sicherheitstests belegen den ausgelieferten Stand",
        "g_sicherheitstests_mangel_fehl":
            "{n} Feststellung(en) zum regelmäßigen und wirksamen Testen",
        "g_normen_widerspruch_ok":
            "Anhang V Nr. 6 ist erklärt und passt zum Bewertungsweg",
        "g_normen_widerspruch_fehl":
            "{n} Feststellung(en) zu den angewandten Normen (Anhang V Nr. 6)",

        # ── Entscheidungen ─────────────────────────────────────────────────
        "ohne_begruendung": "ohne Begründung — nicht nachgewiesen",
        "person_nicht_erfasst": "— (nicht erfasst)",
        "beantwortet": "beantwortet: {wert}",
        "label_offen": "offen",
        "label_erledigt": "erledigt",
        "label_nicht_anwendbar": "nicht anwendbar",
        "antwort_ja": "ja",
        "antwort_nein": "nein",
        "nicht_beantwortet": "nicht beantwortet",

        # ── Gleichbleibende Angaben ────────────────────────────────────────
        "stand_unbekannt": "Stand nicht ausgewiesen",
        "eol_nicht_festgelegt": "nicht festgelegt",
        "support_ende": "Support-Ende {eol}",
        "support_jahre": ", zugesagt {jahre} Jahr(e)",
        "support_markteintritt": ", Markteintritt {am}",
        "kanal_nicht_dokumentiert": "nicht dokumentiert",
        "psirt_stand": "{n} Kontakt(e), Offenlegungs-Richtlinie {policy}",
        "psirt_hinterlegt": "hinterlegt",
        "psirt_fehlt": "fehlt",

        # ── Kopf ───────────────────────────────────────────────────────────
        "titel": "CRA-Vorgangsbericht je Release",
        "titel_entwurf": " (Entwurf)",
        "kopfzeile": "{regulation} · Berichtsdatum {datum}",
        "band_entwurf": ("Vorgangsstatus: {status} — dieser Bericht dient der "
                         "Prüfung und ist kein freigegebener Nachweis."),
        "band_ampel": "Ampel: {label}",
        "band_grundlage": "Grundlage: {quelle}",
        "band_reifegrad": " · Reifegrad {pct} %",

        "kopf_angabe": "Angabe",
        "kopf_wert": "Wert",
        "kopf_hersteller": "Hersteller",
        "kopf_produkt": "Produkt",
        "kopf_projekt": "CRA-Projekt",
        "kopf_release": "Release-Version",
        "kopf_release_leer": "— (kein Release-Vorgang erfasst)",
        "kopf_status": "Vorgangsstatus",
        "kopf_status_entwurf": " — {marker}",
        "kopf_bewertungsweg": "Bewertungsweg (Anhang VIII)",
        "kopf_berichtsdatum": "Berichtsdatum",
        "kein_vorgang": ("Für dieses Projekt ist noch kein Release-Vorgang "
                         "erfasst. Der Bericht zeigt deshalb nur den gerechneten "
                         "Stand; Checkliste, Prüfung und Freigabe sind leer."),

        # ── Rechenstand ────────────────────────────────────────────────────
        "basis_eingefroren": "eingefroren bei Einreichung",
        "basis_heute": "heutiger Rechenstand",
        "hinweis_kein_eingefrorener": (
            "Hinweis: Für diesen Vorgang ist kein bei der Einreichung "
            "eingefrorener Rechenstand hinterlegt. Der Bericht zeigt daher den "
            "heutigen Stand; worauf die Prüfung sich stützte, ist aus den Daten "
            "nicht belegbar."),
        "hinweis_abweichung": (
            "Hinweis: Geprüft wurde gegen den bei der Einreichung eingefrorenen "
            "Stand ({eingefroren}). Der heutige Rechenstand lautet {heute} — die "
            "Abweichung ist zu bewerten, bevor das Release weiterverwendet wird."),

        # ── Phase 1 ────────────────────────────────────────────────────────
        "h_phase1": "Phase 1 — CRA-Ready (Produktzustand)",
        "phase1_festgestellt": "Festgestellt: {person}.",
        "phase1_ueberholt": (
            "Die Feststellung ist durch den heutigen Produktstand überholt — die "
            "Phase-1-Ampel ist nicht mehr grün. Sie wurde nicht gelöscht (eine "
            "menschliche Aussage entfernt kein Rechenlauf), gilt aber nicht als "
            "aktueller Nachweis."),
        "phase1_entzogen": ("Feststellung entzogen ({person}). "
                            "Begründung: {grund}"),
        "phase1_entzug_grund_fehlt": "— (nicht dokumentiert)",
        "phase1_nicht": ("Nicht festgestellt. Für dieses Produkt liegt keine "
                         "ausdrückliche CRA-Ready-Feststellung vor."),
        "phase1_heute": ("Heutiger Produktstand: {ampel} · erfüllt {erfuellt}, "
                         "begründet akzeptiert {akzeptiert}, offen {offen} von "
                         "{gesamt} Anforderungen."),

        # ── Wesentliche Änderung ───────────────────────────────────────────
        "release_art_nicht": "Art des Releases: nicht erklärt.",
        "release_art": "Art des Releases: {label} — {erklaerung}",
        "h_wesentlich": "Wesentliche Änderung (Art. 3 Nr. 30)",
        "wesentlich_offen": (
            "Nicht beantwortet. Die Frage ist offen — sie wird hier ausdrücklich "
            "nicht als „nein“ gelesen, weil „nein“ eine Aussage mit Folgen ist "
            "(keine neue Konformitätsbewertung, keine neue "
            "Konformitätserklärung)."),
        "wesentlich_antwort": "Antwort: {wert}",
        "wesentlich_grund": "Begründung: {grund}",
        "wesentlich_grund_fehlt": ("— (fehlt — ohne Begründung ist die Antwort "
                                   "nicht nachgewiesen)"),
        "wesentlich_folge": ("Folge: neue Konformitätsbewertung, neue "
                            "EU-Konformitätserklärung und aktualisierte "
                            "technische Dokumentation."),
        "wesentlich_umfang": "Neu bewertete grundlegende Anforderungen: {text}",
        "nicht_dokumentiert": "nicht dokumentiert",

        # ── Checkliste ─────────────────────────────────────────────────────
        "h_checkliste": "Release-Checkliste",
        "checkliste_intro": (
            "Gerechnete Punkte stammen aus dem Konformitäts-Gate ({quelle}); "
            "Entscheidungen und Bestätigungen von Personen. Die Trennung bleibt "
            "sichtbar, weil eine Liste, die sich selbst abhaken ließe, als "
            "Nachweis wertlos wäre."),
        "sp_pruefpunkt": "Prüfpunkt",
        "sp_rechtsbezug": "Rechtsbezug",
        "sp_ergebnis": "Ergebnis",
        "sp_begruendung": "Begründung",
        "sp_person": "Person",
        "sp_angabe": "Angabe",
        "sp_stand": "Stand",
        "sp_bestaetigung": "Bestätigung",
        "optional": " (optional)",
        "bestaetigt": "bestätigt — {person}",
        "nicht_bestaetigt": "nicht bestätigt",

        # ── Offene Punkte ──────────────────────────────────────────────────
        "h_offene": "Offene Punkte",
        "offene_keine": "Keine offenen Punkte im zugrunde gelegten Rechenstand.",
        "sp_phase": "Phase",
        "sp_art": "Art",
        "sp_punkt": "Punkt",
        "sp_hinweis": "Hinweis",
        "phase_release": "Release",
        "phase_produkt": "Produkt",
        "ungeprueft_zusatz": " [nicht geprüft — gilt als nicht erfüllt]",

        # ── Restrisiken ────────────────────────────────────────────────────
        "h_restrisiken": "Akzeptierte Restrisiken",
        "restrisiken_intro": (
            "Abweichungen von grundlegenden Anforderungen, die über ein begründet "
            "akzeptiertes Restrisiko getragen werden (Anhang I Teil I)."),
        "sp_anforderung": "Anforderung",
        "sp_rechtsgrundlage": "Rechtsgrundlage",
        "sp_kategorie": "Kategorie",
        "sp_akzeptiert_von": "akzeptiert von",
        "restrisiken_keine": ("Keine begründet akzeptierte Abweichung von "
                             "grundlegenden Anforderungen."),
        "restrisiken_offen": (
            "{n} Anforderung(en) sind weder erfüllt noch begründet akzeptiert. "
            "Sie stehen oben unter „Offene Punkte“ und schließen eine konforme "
            "Ausweisung dieses Releases aus."),
        "h_weitere_risiken": ("Weitere akzeptierte Risiken der Risikobewertung "
                              "„{projekt}“"),
        "weitere_risiken_intro": (
            "Diese Risiken hängen an keiner grundlegenden Anforderung. Sie sind "
            "Teil der Risikolage, aber nicht Grundlage der Konformitätsaussage."),
        "sp_nr": "Nr.",
        "sp_risiko": "Risiko",
        "sp_stufe": "Stufe",

        # ── Prüfung und Freigabe ───────────────────────────────────────────
        "h_vier_augen": "Prüfung und Freigabe",
        "va_erstellt": "Erstellt / eingereicht von",
        "va_geprueft": "Geprüft von",
        "va_freigegeben": "Freigegeben von",
        "va_veroeffentlicht": "Veröffentlicht am",
        "sp_rolle": "Rolle",
        "sp_person_zeitpunkt": "Person und Zeitpunkt",
        "zurueckgewiesen_grund": "Zurückgewiesen mit der Begründung: {grund}",
        "va_entwurf": ("{marker}. Solange keine Freigabe durch eine zweite "
                       "Person vorliegt, belegt dieser Bericht den Arbeitsstand "
                       "und keine geprüfte Konformität."),

        # ── Archiv ─────────────────────────────────────────────────────────
        "h_archiv": "Archivierte Nachweise (Verweis mit SHA-256)",
        "archiv_intro": (
            "Der Konformitätsnachweis liegt nach der Freigabe unveränderlich im "
            "Archiv. Dieser Bericht verweist darauf; die Beweislast trägt die "
            "archivierte Datei mit ihrem Hash, nicht dieser Bericht."),
        "archiv_keines": (
            "Für dieses Projekt ist noch kein Nachweis archiviert — es gibt also "
            "keinen unveränderlichen Stand, auf den verwiesen werden kann."),
        "archiv_keine_version": (
            "Kein Archivstück zur Version {version}; aufgeführt sind die übrigen "
            "Nachweise dieses Projekts."),
        "sp_version": "Version",
        "sp_ampel": "Ampel",
        "sp_sha": "SHA-256",
        "sp_freigegeben": "Freigegeben",

        # ── Weitere Vorgänge ───────────────────────────────────────────────
        "h_weitere_vorgaenge": "Weitere Release-Vorgänge dieses Projekts",
        "sp_status": "Status",
        "sp_wesentliche_aenderung": "wesentliche Änderung",

        # ── Datenlage und Abgrenzung ───────────────────────────────────────
        "q_projekt": "Projekt-Stammdaten",
        "q_vorgaenge": "Release-Vorgänge",
        "q_gate": "Konformitäts-Gate",
        "q_gate_produkt": "Konformitäts-Gate (Produktsicht)",
        "q_phase1": "Phase-1-Feststellung",
        "q_archiv": "Nachweis-Archiv",
        "quelle_fehler": "{name} konnte nicht geladen werden ({fehler})",
        "rb_nicht_lesbar": ("Verknüpfte Risikobewertung '{projekt}' nicht lesbar "
                            "({fehler})"),
        "h_datenlage": "Hinweise zur Datenlage",
        "datenlage_intro": (
            "Die folgenden Quellen waren beim Erzeugen nicht lesbar. Was sie "
            "belegen sollten, ist damit nicht nachgewiesen — nicht erfüllt."),
        "abgrenzung": (
            "Abgrenzung: Dieser Bericht beschreibt den Release-Vorgang. Der "
            "juristische Konformitätsnachweis (Anforderungen mit "
            "Rechtsgrundlage, Verfahren nach Anhang VIII, begründete "
            "Abweichungen, Anhang VII) ist ein eigenes Dokument; er wird oben "
            "über das Archiv mit seinem SHA-256-Wert zitiert und hier nicht "
            "erneut erzeugt."),
    },
    "en": {
        "regulation": "Regulation (EU) 2024/2847 (Cyber Resilience Act)",

        "ampel_gruen": "COMPLIANT",
        "ampel_bedingt": "CONDITIONALLY COMPLIANT",
        "ampel_rot": "NOT COMPLIANT",
        "ampel_unbewertet": "NOT ASSESSED",

        "status_entwurf": "draft",
        "status_in_pruefung": "under review",
        "status_freigegeben": "approved",
        "status_zurueckgewiesen": "rejected",
        "status_veroeffentlicht": "published",

        "art_gerechnet": "Calculated check items",
        "art_entscheidung": "Decisions (with justification and person)",
        "art_gleichbleibend": "Unchanging particulars (confirmed per release)",

        "entwurf_marker": "DRAFT — not approved",

        "leer": "—",
        "person_am": "{person} on {datum}",

        # ── Gerechnete Prüfpunkte ──────────────────────────────────────────
        "nicht_geprueft": "not verified",
        "nicht_auswertbar": "not evaluable ({wert})",
        "kein_rechenergebnis": "no calculated result for source '{quelle}'",
        "kein_rechenstand": "not verified (no calculated state available)",

        "g_offene_kritische_schwachstellen_ok":
            "no open critical or high-severity findings",
        "g_offene_kritische_schwachstellen_fehl":
            "{n} open critical/high-severity vulnerability(ies)",
        "g_behobene_ohne_advisory_ok":
            "all vulnerabilities remediated in this version have been published",
        "g_behobene_ohne_advisory_fehl":
            "{n} remediated vulnerability(ies) without an advisory",
        "g_sbom_version_fehlt_ok": "SBOM available for the release version",
        "g_sbom_version_fehlt_fehl": "no SBOM for this release version",
        "g_support_ueberschritten_ok":
            "release falls within the committed support period",
        "g_support_ueberschritten_fehl":
            "release falls after the end of the support period",
        "g_ueberfaellige_meldungen_ok": "no overdue reporting deadline",
        "g_ueberfaellige_meldungen_fehl": "{n} overdue reporting deadline(s)",
        "g_annex_vollstaendig_ok": "technical documentation fully evidenced",
        "g_annex_vollstaendig_fehl":
            "evidence for the technical documentation is missing",
        "g_doc_ausgestellt_ok":
            "EU declaration of conformity issued or approved",
        "g_doc_ausgestellt_fehl": "EU declaration of conformity not issued",
        "g_bewertungsweg_unzulaessig_ok":
            "conformity assessment route permissible for the product class",
        "g_bewertungsweg_unzulaessig_fehl":
            "conformity assessment route is NOT permissible for this product "
            "class",
        "g_fremdkomponenten_unbewertet_ok":
            "new and upgraded third-party components have been assessed",
        "g_fremdkomponenten_unbewertet_fehl":
            "{n} newly integrated or upgraded third-party component(s) without "
            "a documented assessment",
        "g_komponenten_befund_widerspruch_ok":
            "no assessment contradicts an open finding",
        "g_komponenten_befund_widerspruch_fehl":
            "{n} third-party component(s) assessed as “not relevant” despite "
            "an open finding",
        "g_release_art_widersprueche_ok":
            "the declared type of this release matches the file",
        "g_release_art_widersprueche_fehl":
            "{n} contradiction(s) between the declared type of release and "
            "what the file states",
        "g_upstream_meldung_offen_ok":
            "own findings in third-party components have been reported to the "
            "respective manufacturer",
        "g_upstream_meldung_offen_fehl":
            "{n} vulnerability(ies) in third-party components without a "
            "documented report to their manufacturer",
        "g_update_zusagen_fehlen_ok":
            "security updates committed free of charge and through a separate "
            "channel",
        "g_update_zusagen_fehlen_fehl":
            "update commitments not fully documented",
        "g_kaufhinweis_fehlt_ok":
            "the end of the support period is accessible before purchase",
        "g_kaufhinweis_fehlt_fehl":
            "no indication of the end of the support period at the point of "
            "purchase",
        "g_aufbewahrungsfristen_unbestimmbar_ok":
            "retention and update periods can be determined",
        "g_aufbewahrungsfristen_unbestimmbar_fehl":
            "retention/update periods cannot be determined (reference dates "
            "missing)",
        "g_marktaufsicht_versaeumt_ok":
            "no missed deadline towards the market surveillance authority",
        "g_marktaufsicht_versaeumt_fehl":
            "{n} missed deadline(s) towards the market surveillance authority",
        "g_sicherheitstests_mangel_ok":
            "security testing evidences the state as delivered",
        "g_sicherheitstests_mangel_fehl":
            "{n} finding(s) on regular and effective testing",
        "g_normen_widerspruch_ok":
            "Annex V No. 6 is declared and matches the assessment route",
        "g_normen_widerspruch_fehl":
            "{n} finding(s) on the standards applied (Annex V No. 6)",

        # ── Entscheidungen ─────────────────────────────────────────────────
        "ohne_begruendung": "without justification — not evidenced",
        "person_nicht_erfasst": "— (not recorded)",
        "beantwortet": "answered: {wert}",
        "label_offen": "open",
        "label_erledigt": "done",
        "label_nicht_anwendbar": "not applicable",
        "antwort_ja": "yes",
        "antwort_nein": "no",
        "nicht_beantwortet": "not answered",

        # ── Gleichbleibende Angaben ────────────────────────────────────────
        "stand_unbekannt": "state not stated",
        "eol_nicht_festgelegt": "not determined",
        "support_ende": "End of support {eol}",
        "support_jahre": ", {jahre} year(s) committed",
        "support_markteintritt": ", placed on the market {am}",
        "kanal_nicht_dokumentiert": "not documented",
        "psirt_stand": "{n} contact(s), disclosure policy {policy}",
        "psirt_hinterlegt": "on file",
        "psirt_fehlt": "missing",

        # ── Kopf ───────────────────────────────────────────────────────────
        "titel": "CRA release record report",
        "titel_entwurf": " (draft)",
        "kopfzeile": "{regulation} · Report date {datum}",
        "band_entwurf": ("Record status: {status} — this report serves the "
                         "review and is not an approved record of conformity."),
        "band_ampel": "Traffic light: {label}",
        "band_grundlage": "Basis: {quelle}",
        "band_reifegrad": " · maturity {pct} %",

        "kopf_angabe": "Particular",
        "kopf_wert": "Value",
        "kopf_hersteller": "Manufacturer",
        "kopf_produkt": "Product",
        "kopf_projekt": "CRA project",
        "kopf_release": "Release version",
        "kopf_release_leer": "— (no release record on file)",
        "kopf_status": "Record status",
        "kopf_status_entwurf": " — {marker}",
        "kopf_bewertungsweg": "Assessment route (Annex VIII)",
        "kopf_berichtsdatum": "Report date",
        "kein_vorgang": ("No release record has been created for this project "
                         "yet. The report therefore shows only the calculated "
                         "state; checklist, review and approval are empty."),

        # ── Rechenstand ────────────────────────────────────────────────────
        "basis_eingefroren": "frozen upon submission",
        "basis_heute": "today's calculated state",
        "hinweis_kein_eingefrorener": (
            "Note: no calculated state frozen upon submission is on file for "
            "this record. The report therefore shows today's state; what the "
            "review relied on cannot be evidenced from the data."),
        "hinweis_abweichung": (
            "Note: the review was carried out against the state frozen upon "
            "submission ({eingefroren}). Today's calculated state reads {heute} "
            "— the divergence is to be assessed before this release is used "
            "further."),

        # ── Phase 1 ────────────────────────────────────────────────────────
        "h_phase1": "Phase 1 — CRA-ready (state of the product)",
        "phase1_festgestellt": "Determined: {person}.",
        "phase1_ueberholt": (
            "The determination has been superseded by today's state of the "
            "product — the phase 1 traffic light is no longer green. It was not "
            "deleted (no calculation removes a human statement), but it does "
            "not count as current evidence."),
        "phase1_entzogen": ("Determination withdrawn ({person}). "
                            "Justification: {grund}"),
        "phase1_entzug_grund_fehlt": "— (not documented)",
        "phase1_nicht": ("Not determined. There is no express CRA-ready "
                         "determination for this product."),
        "phase1_heute": ("Today's state of the product: {ampel} · {erfuellt} "
                         "fulfilled, {akzeptiert} accepted with justification, "
                         "{offen} open out of {gesamt} requirements."),

        # ── Wesentliche Änderung ───────────────────────────────────────────
        "release_art_nicht": "Type of this release: not declared.",
        "release_art": "Type of this release: {label} — {erklaerung}",
        "h_wesentlich": "Substantial modification (Art. 3 No. 30)",
        "wesentlich_offen": (
            "Not answered. The question is open — it is expressly not read as "
            "“no” here, because “no” is a statement with consequences (no new "
            "conformity assessment, no new declaration of conformity)."),
        "wesentlich_antwort": "Answer: {wert}",
        "wesentlich_grund": "Justification: {grund}",
        "wesentlich_grund_fehlt": ("— (missing — without a justification the "
                                   "answer is not evidenced)"),
        "wesentlich_folge": ("Consequence: new conformity assessment, new EU "
                            "declaration of conformity and updated technical "
                            "documentation."),
        "wesentlich_umfang": "Essential requirements reassessed: {text}",
        "nicht_dokumentiert": "not documented",

        # ── Checkliste ─────────────────────────────────────────────────────
        "h_checkliste": "Release checklist",
        "checkliste_intro": (
            "Calculated items come from the conformity gate ({quelle}); "
            "decisions and confirmations come from people. The separation "
            "remains visible, because a list that could tick itself off would "
            "be worthless as evidence."),
        "sp_pruefpunkt": "Check item",
        "sp_rechtsbezug": "Legal reference",
        "sp_ergebnis": "Result",
        "sp_begruendung": "Justification",
        "sp_person": "Person",
        "sp_angabe": "Particular",
        "sp_stand": "State",
        "sp_bestaetigung": "Confirmation",
        "optional": " (optional)",
        "bestaetigt": "confirmed — {person}",
        "nicht_bestaetigt": "not confirmed",

        # ── Offene Punkte ──────────────────────────────────────────────────
        "h_offene": "Open items",
        "offene_keine": "No open items in the calculated state relied upon.",
        "sp_phase": "Phase",
        "sp_art": "Type",
        "sp_punkt": "Item",
        "sp_hinweis": "Note",
        "phase_release": "Release",
        "phase_produkt": "Product",
        "ungeprueft_zusatz": " [not verified — counts as not fulfilled]",

        # ── Restrisiken ────────────────────────────────────────────────────
        "h_restrisiken": "Accepted residual risks",
        "restrisiken_intro": (
            "Deviations from essential requirements that are carried by a "
            "residual risk accepted with justification (Annex I Part I)."),
        "sp_anforderung": "Requirement",
        "sp_rechtsgrundlage": "Legal basis",
        "sp_kategorie": "Category",
        "sp_akzeptiert_von": "accepted by",
        "restrisiken_keine": ("No deviation from essential requirements has "
                             "been accepted with justification."),
        "restrisiken_offen": (
            "{n} requirement(s) are neither fulfilled nor accepted with "
            "justification. They appear above under “Open items” and preclude "
            "declaring this release compliant."),
        "h_weitere_risiken": ("Further accepted risks of the risk assessment "
                              "“{projekt}”"),
        "weitere_risiken_intro": (
            "These risks are not attached to any essential requirement. They "
            "are part of the risk situation, but not a basis of the statement "
            "on conformity."),
        "sp_nr": "No.",
        "sp_risiko": "Risk",
        "sp_stufe": "Level",

        # ── Prüfung und Freigabe ───────────────────────────────────────────
        "h_vier_augen": "Review and approval",
        "va_erstellt": "Created / submitted by",
        "va_geprueft": "Reviewed by",
        "va_freigegeben": "Approved by",
        "va_veroeffentlicht": "Published on",
        "sp_rolle": "Role",
        "sp_person_zeitpunkt": "Person and point in time",
        "zurueckgewiesen_grund": "Rejected with the justification: {grund}",
        "va_entwurf": ("{marker}. As long as there is no approval by a second "
                       "person, this report evidences the state of work and no "
                       "reviewed conformity."),

        # ── Archiv ─────────────────────────────────────────────────────────
        "h_archiv": "Archived records (reference with SHA-256)",
        "archiv_intro": (
            "After approval, the record of conformity is held unalterably in "
            "the archive. This report refers to it; the burden of proof is "
            "borne by the archived file with its hash, not by this report."),
        "archiv_keines": (
            "No record has been archived for this project yet — there is "
            "therefore no unalterable state to refer to."),
        "archiv_keine_version": (
            "No archived item for version {version}; the remaining records of "
            "this project are listed instead."),
        "sp_version": "Version",
        "sp_ampel": "Traffic light",
        "sp_sha": "SHA-256",
        "sp_freigegeben": "Approved",

        # ── Weitere Vorgänge ───────────────────────────────────────────────
        "h_weitere_vorgaenge": "Further release records of this project",
        "sp_status": "Status",
        "sp_wesentliche_aenderung": "substantial modification",

        # ── Datenlage und Abgrenzung ───────────────────────────────────────
        "q_projekt": "Project master data",
        "q_vorgaenge": "Release records",
        "q_gate": "Conformity gate",
        "q_gate_produkt": "Conformity gate (product view)",
        "q_phase1": "Phase 1 determination",
        "q_archiv": "Record archive",
        "quelle_fehler": "{name} could not be loaded ({fehler})",
        "rb_nicht_lesbar": ("Linked risk assessment '{projekt}' not readable "
                            "({fehler})"),
        "h_datenlage": "Notes on the state of the data",
        "datenlage_intro": (
            "The following sources could not be read when this report was "
            "produced. What they were to evidence is therefore not evidenced — "
            "not fulfilled."),
        "abgrenzung": (
            "Scope: this report describes the release record. The legal record "
            "of conformity (requirements with their legal basis, the procedure "
            "under Annex VIII, deviations with justification, Annex VII) is a "
            "document of its own; it is cited above through the archive with "
            "its SHA-256 value and is not produced again here."),
    },
}

_t = _rt.macher(TEXTE)

_REGULATION = TEXTE["de"]["regulation"]

#: Die deutschen Bezeichnungen bleiben als Zuordnung bestehen — sie sind der
#: Rückfall und die Menge der bekannten Werte (``_ampel``/``_status`` fragen
#: sie, damit ein unbekannter Wert nicht als Schlüsselname im Dokument landet).
#: Abgeleitet aus :data:`TEXTE`, damit der deutsche Text **eine** Quelle hat.
AMPEL_LABEL = {k: TEXTE["de"][f"ampel_{k}"] for k in ("gruen", "bedingt", "rot")}
STATUS_LABEL = {k: TEXTE["de"][f"status_{k}"]
                for k in ("entwurf", "in_pruefung", "freigegeben",
                          "zurueckgewiesen", "veroeffentlicht")}
ART_LABEL = {k: TEXTE["de"][f"art_{k}"]
             for k in ("gerechnet", "entscheidung", "gleichbleibend")}

#: Zustände, in denen der Vorgang kein Entwurf mehr ist.
FREIGEGEBEN = ("freigegeben", "veroeffentlicht")

#: Kennzeichnung eines nicht freigegebenen Vorgangs — sie steht im Titel, im Band
#: und in der Kopftabelle. Ein Entwurf, der wie ein Nachweis aussieht, ist der
#: Grund, warum später niemand mehr weiß, welche Fassung gilt.
ENTWURF_MARKER = TEXTE["de"]["entwurf_marker"]


def _ampel(sp: str, ampel: Any, rueckfall: str = "") -> str:
    """Ampel-Bezeichnung in der Sprache des Dokuments.

    Ein unbekannter Wert liefert ``rueckfall`` — so war es vorher
    (``AMPEL_LABEL.get(ampel, …)``), und es ist richtig: Ein Rechenstand ohne
    Ampel soll nicht als „bewertet" erscheinen.
    """
    a = str(ampel or "")
    return _t(sp, f"ampel_{a}") if a in AMPEL_LABEL else rueckfall


def _status(sp: str, status: Any) -> str:
    """Vorgangsstatus in der Sprache des Dokuments; Unbekanntes bleibt stehen."""
    s = str(status or "")
    return _t(sp, f"status_{s}") if s in STATUS_LABEL else s


def _antwort(sp: str, wert: Any) -> str:
    """„ja"/„nein" als **Wort des Dokuments**, nicht als Datenwert.

    Verglichen wird weiterhin der gespeicherte Wert (``wert == "ja"``);
    gedruckt wird die Sprache des Mandanten. Ein englisches Dokument, in dem
    die Antwort auf die Kernfrage „ja" lautet, wäre für seinen Leser nicht
    auswertbar.
    """
    w = str(wert or "")
    if w in ("ja", "nein"):
        return _t(sp, f"antwort_{w}")
    return w

# ── Farben (#1727: Farbe folgt dem Erfüllungsgrad, nicht der Dekoration) ────
FARBEN = {
    "kopf": "1565C0",
    "gruen": "2E7D32",
    "bedingt": "F9A825",
    "rot": "C62828",
    "unbekannt": "90A4AE",
}

#: Zellenhintergrund je Ergebnis — hell, damit der Text lesbar bleibt.
ERG_FARBE = {
    "erfuellt": "E8F5E9",
    "bestaetigt": "E8F5E9",
    "offen": "FFEBEE",
    "maengel": "FFF3E0",
    "ungeprueft": "ECEFF1",
    "nicht_anwendbar": "F5F5F5",
}


# ── DOCX-Kleinteile ─────────────────────────────────────────────────────────
# Dieselben Helfer stehen in ``compliance_audit/berichte_provider.py``. Sie
# gehören fachlich nach ``shared/reports/docx_pdf.py``; das ist in diesem Vorgang
# fremder Arbeitsbereich, deshalb hier lokal (siehe Bericht zu #1748).

def _schattieren(zelle, hex_farbe: str) -> None:
    """Zellenhintergrund setzen — python-docx kann das nur über w:shd."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_farbe)
    zelle._tc.get_or_add_tcPr().append(shd)


def _weiss_fett(zelle, text: str) -> None:
    from docx.shared import RGBColor

    run = zelle.paragraphs[0].add_run(text)
    run.bold = True
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def _tabelle(doc, kopf: list[str], zeilen: int):
    tbl = doc.add_table(rows=zeilen + 1, cols=len(kopf))
    tbl.style = "Table Grid"
    for ci, titel in enumerate(kopf):
        z = tbl.cell(0, ci)
        _schattieren(z, FARBEN["kopf"])
        _weiss_fett(z, titel)
    return tbl


def _ueberschrift(doc, text: str, level: int = 1):
    from docx.shared import RGBColor

    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x0D, 0x47, 0xA1)
    return h


def _band(doc, farbe: str, zeile1: str, zeile2: str = "") -> None:
    """Farbiges Band — das Erste, was man sehen soll: Ampel bzw. Entwurfs-Hinweis."""
    from docx.shared import Pt, RGBColor

    tbl = doc.add_table(rows=1, cols=1)
    tbl.style = "Table Grid"
    z = tbl.cell(0, 0)
    _schattieren(z, farbe)
    r = z.paragraphs[0].add_run(zeile1)
    r.bold = True
    r.font.size = Pt(15)
    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    if zeile2:
        r2 = z.add_paragraph().add_run(zeile2)
        r2.font.size = Pt(10)
        r2.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    doc.add_paragraph()


def _datum(wert: Any) -> str:
    """Zeitstempel kurz und lesbar; leer bleibt leer (nie „None")."""
    s = str(wert or "").strip()
    return s[:19].replace("T", " ") if s else ""


def _person_am(von: Any, am: Any, sp: str = _rt.STANDARD) -> str:
    """„von X am Y" — der Satz, den ein Nachweis braucht."""
    p = str(von or "").strip()
    d = _datum(am)
    if p and d:
        return _t(sp, "person_am", person=p, datum=d)
    return p or d or _t(sp, "leer")


# ── Daten sammeln ───────────────────────────────────────────────────────────

def _aktivitaet(v: dict[str, Any]) -> str:
    """Zeitpunkt der letzten Bewegung eines Vorgangs (für „der jüngste")."""
    return max(str(v.get(k) or "") for k in (
        "veroeffentlicht_am", "freigegeben_am", "geprueft_am", "eingereicht_am",
        "updated_at", "created_at"))


def waehle_vorgang(vorgaenge: list[dict[str, Any]],
                   version: str | None = None) -> dict[str, Any] | None:
    """Welcher Release-Vorgang wird berichtet?

    Das Berichts-Center kennt nur Modul, Typ und Projekt — eine Release-Version
    reicht es nicht durch. Die Auswahl muss also hier fallen, und sie muss
    vorhersagbar sein: der **jüngste** versionierte Vorgang, also der, an dem
    gerade gearbeitet wird.

    Der Datensatz mit **leerer** Version ist bewusst außen vor: Das ist der
    Produkt-Datensatz (Bewertungsweg, Notified Body, CE) aus Phase 1 und kein
    Release-Vorgang.
    """
    versioniert = [v for v in vorgaenge if str(v.get("release_version") or "").strip()]
    if version:
        ziel = str(version).strip()
        return next((v for v in versioniert
                     if str(v.get("release_version") or "").strip() == ziel), None)
    if not versioniert:
        return None
    return max(versioniert, key=_aktivitaet)


def sammeln(projekt: str, version: str | None = None,
            db_path: Path = DB_PATH, sprache: str | None = None) -> dict[str, Any]:
    """Alle Angaben des Vorgangsberichts aus den vorhandenen Quellen holen.

    Jede Quelle ist einzeln gekapselt: Fällt eine aus, fehlt ihr Abschnitt mit
    einem lesbaren Hinweis, statt den ganzen Bericht zu verhindern. Erfunden
    wird nichts — fehlt ein Wert, steht das im Bericht.

    ``sprache`` gilt für die **Texte**, die hier schon entstehen (Hinweise zur
    Datenlage, Bezeichnung des Rechenstands). Sie steht als ``sprache`` im
    Ergebnis — das beantwortet die Frage, warum dieser Bericht englisch ist.
    """
    from cra import konformitaet_db as kdb
    from cra import konformitaet_final_db as fdb
    from cra import release_db as rdb
    from cra.konformitaet_gate import evaluate

    sp = _rt.aufloesen("cra", projekt, sprache)
    daten: dict[str, Any] = {"projekt_name": projekt, "hinweise": [],
                             "sprache": sp}

    def _quelle(name: str, fn: Callable[[], Any], default: Any = None) -> Any:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — Nebenquelle darf den Bericht nicht kippen
            daten["hinweise"].append(_t(
                sp, "quelle_fehler", name=name,
                fehler=f"{type(exc).__name__}: {exc}"))
            return default

    from cra.db import load_projekt
    proj = _quelle(_t(sp, "q_projekt"),
                   lambda: load_projekt(db_path, projekt)) or {}
    daten["projekt"] = proj
    meta = proj.get("meta") if isinstance(proj.get("meta"), dict) else {}

    vorgaenge = _quelle(_t(sp, "q_vorgaenge"),
                        lambda: kdb.list_konformitaet(db_path, projekt), []) or []
    vorgang = waehle_vorgang(vorgaenge, version)
    daten["vorgaenge"] = vorgaenge
    daten["vorgang"] = vorgang
    rv = str((vorgang or {}).get("release_version") or version or "")
    daten["release_version"] = rv
    status = str((vorgang or {}).get("freigabe_status") or "entwurf")
    daten["status"] = status
    # Ohne Freigabe ist es ein Entwurf — auch wenn gar kein Vorgang erfasst ist.
    daten["ist_entwurf"] = status not in FREIGEGEBEN

    # Heutiger Rechenstand: Release-Sicht (mit Version) und Produkt-Sicht.
    # Die Produkt-Sicht wird getrennt gebraucht, weil ``bereit_ueberholt`` die
    # Phase-1-Feststellung bewertet — ein offener Release-Punkt würde sie sonst
    # fälschlich als überholt ausweisen.
    daten["gate_heute"] = _quelle(
        _t(sp, "q_gate"), lambda: evaluate(projekt, version=rv or None), {}) or {}
    daten["gate_produkt"] = _quelle(
        _t(sp, "q_gate_produkt"), lambda: evaluate(projekt), {}) or {}

    # Eingefrorener Stand bei Einreichung — er ist die Grundlage der Prüfung.
    eingefroren = (vorgang or {}).get("gate") or {}
    daten["gate_eingefroren"] = eingefroren if isinstance(eingefroren, dict) else {}
    nutze_eingefroren = bool(daten["gate_eingefroren"]) and status != "entwurf"
    daten["gate_basis"] = (daten["gate_eingefroren"] if nutze_eingefroren
                           else daten["gate_heute"])
    daten["gate_basis_quelle"] = _t(sp, "basis_eingefroren" if nutze_eingefroren
                                    else "basis_heute")

    # Phase 1 — CRA-Ready als ausdrückliche Feststellung (#1746).
    phase1 = _quelle(_t(sp, "q_phase1"), lambda: rdb.get_release(db_path, projekt))
    daten["phase1"] = phase1 or {}
    daten["phase1_ueberholt"] = bool(_quelle(
        _t(sp, "q_phase1"), lambda: rdb.bereit_ueberholt(phase1, daten["gate_produkt"]),
        False))

    # Archivierte Nachweise (SHA-256) — der Bericht zeigt darauf, er ersetzt sie nicht.
    archiv = _quelle(_t(sp, "q_archiv"), lambda: fdb.list_final(db_path, projekt), []) or []
    daten["archiv_alle"] = archiv
    daten["archiv"] = [a for a in archiv
                       if not rv or str(a.get("version") or "") == rv] if archiv else []

    daten["restrisiken"] = _restrisiken(daten["gate_basis"], meta, daten["hinweise"],
                                        sp=sp)
    return daten


def _restrisiken(gate: dict[str, Any], meta: dict[str, Any],
                 hinweise: list[str], sp: str = _rt.STANDARD) -> dict[str, Any]:
    """Akzeptierte Restrisiken — zwei Herkünfte, bewusst getrennt gehalten.

    Maßgeblich für die Konformität sind die **Abweichungen** aus dem Gate: eine
    nicht erfüllte Anforderung gilt nur dann als konform, wenn das verknüpfte
    Nichterfüllungs-Risiko begründet akzeptiert ist (#1613). Daneben kann die
    verknüpfte Risikobewertung weitere akzeptierte Risiken führen, die an keiner
    Anforderung hängen; die stehen als eigener Block, damit nicht der Eindruck
    entsteht, sie hätten dieselbe Wirkung.
    """
    abw = [a for a in (gate.get("abweichungen") or [])
           if str(a.get("art")) == "begruendet"]
    offen = [a for a in (gate.get("abweichungen") or []) if str(a.get("art")) == "offen"]
    weitere: list[dict[str, Any]] = []
    rb_name = str((meta or {}).get("linked_risk_projekt") or "").strip()
    if rb_name:
        try:
            from risikobewertung.db import load_risiken
            belegt = {f"cra:requirement:{a.get('requirement_id')}" for a in abw}
            for r in load_risiken(RB_DB, rb_name):
                if str(r.get("behandlung") or "") != "akzeptiert":
                    continue
                felder = r.get("felder") or {}
                if str(felder.get("_source_id") or "") in belegt:
                    continue   # steht schon als Abweichung — keine Dublette
                weitere.append({
                    "nr": r.get("nr"), "titel": r.get("risk_name"),
                    "kategorie": r.get("akzeptanz_kategorie"),
                    "grund": r.get("akzeptanz_grund"), "von": r.get("akzeptanz_von"),
                    "am": r.get("akzeptanz_am"), "review": r.get("akzeptanz_review"),
                    "rechtsgrundlage": r.get("rechtsgrundlage"),
                    "level": r.get("risk_level")})
        except Exception as exc:  # noqa: BLE001
            hinweise.append(_t(sp, "rb_nicht_lesbar", projekt=rb_name,
                               fehler=f"{type(exc).__name__}: {exc}"))
    return {"abweichungen": abw, "offene_abweichungen": offen, "weitere": weitere,
            "rb_projekt": rb_name}


# ── Gerechnete Prüfpunkte auswerten ─────────────────────────────────────────
# Die Zuordnung Katalog-``quelle`` → Gate-Schlüssel steht im Katalog (#1744);
# hier wird der **Wert** nur in eine Aussage übersetzt. ``None`` heißt überall
# „nicht geprüft" und wird nie zu „erfüllt".

def _aus_zahl(wert: Any, *, sp: str, ok: str, fehl: str) -> tuple[str, str]:
    if wert is None:
        return "ungeprueft", _t(sp, "nicht_geprueft")
    try:
        n = int(wert)
    except (TypeError, ValueError):
        return "ungeprueft", _t(sp, "nicht_auswertbar", wert=repr(wert))
    return (("erfuellt", _t(sp, ok)) if n == 0
            else ("offen", _t(sp, fehl, n=n)))


def _aus_liste(wert: Any, *, sp: str, ok: str, fehl: str) -> tuple[str, str]:
    if wert is None:
        return "ungeprueft", _t(sp, "nicht_geprueft")
    if isinstance(wert, (list, tuple)):
        return (("erfuellt", _t(sp, ok)) if not wert
                else ("offen", _t(sp, fehl, n=len(wert))))
    return _aus_zahl(wert, sp=sp, ok=ok, fehl=fehl)


def _aus_mangel_flag(wert: Any, *, sp: str, ok: str, fehl: str) -> tuple[str, str]:
    """Flag, bei dem ``True`` den **Mangel** meldet (``sbom_version_fehlt``)."""
    if wert is None:
        return "ungeprueft", _t(sp, "nicht_geprueft")
    return ("offen", _t(sp, fehl)) if bool(wert) else ("erfuellt", _t(sp, ok))


def _aus_ok_flag(wert: Any, *, sp: str, ok: str, fehl: str) -> tuple[str, str]:
    """Flag, bei dem ``True`` die **Erfüllung** meldet (``annex_vollstaendig``)."""
    if wert is None:
        return "ungeprueft", _t(sp, "nicht_geprueft")
    return ("erfuellt", _t(sp, ok)) if bool(wert) else ("offen", _t(sp, fehl))


#: Gate-Quelle → **wie** ihr Wert zu lesen ist. Die Texte dazu stehen in
#: :data:`TEXTE` unter ``g_<quelle>_ok`` und ``g_<quelle>_fehl`` (#1954); vorher
#: standen sie hier im Lambda. Die Zuordnung bleibt, was sie war — eine Stelle,
#: an der ein neuer gerechneter Katalogpunkt auftauchen muss, sonst meldet der
#: Bericht „nicht geprüft", obwohl gerechnet wurde (die Falle aus
#: #1762/#1773/#1799/#1824).
_GERECHNET_AUSWERTUNG: dict[str, Callable[..., tuple[str, str]]] = {
    "offene_kritische_schwachstellen": _aus_zahl,
    "behobene_ohne_advisory": _aus_liste,
    "sbom_version_fehlt": _aus_mangel_flag,
    "support_ueberschritten": _aus_mangel_flag,
    "ueberfaellige_meldungen": _aus_liste,
    "annex_vollstaendig": _aus_ok_flag,
    "doc_ausgestellt": _aus_ok_flag,
    # #1759: Der Bewertungsweg muss zur Produktklasse passen. Ein unzulässiger
    # Weg ist keine Lücke in der Akte, sondern eine Nicht-Konformität — im
    # Bericht darf er deshalb nicht als bloß „offener Punkt" erscheinen.
    "bewertungsweg_unzulaessig": _aus_mangel_flag,
    # #1761: Sorgfaltspflicht bei Komponenten Dritter und die Meldung an deren
    # Hersteller. Beide Punkte waren vorher keine Rechenwerte — der eine ein
    # Sammelhaken, der andere gar nicht vorhanden. ``None`` heißt hier wie
    # überall „nicht geprüft": keine SBOM, keine Komponentenliste, oder die
    # Quelle fiel aus. Ein ``0`` an dieser Stelle wäre die Aussage, es sei
    # geprüft und in Ordnung.
    "fremdkomponenten_unbewertet": _aus_liste,
    # #1774: Der Widerspruch zwischen Bewertung und eigenem Befund. ``None``
    # heißt auch hier „nicht geprüft" — ohne Komponentenliste ist nichts zu
    # vergleichen, und ein „0" wäre die Aussage, es sei geprüft und sauber.
    "komponenten_befund_widerspruch": _aus_liste,
    # #1793: Der Abgleich der erklärten Release-Art mit der Akte. ``None`` =
    # nicht geprüft (Phase 1 oder Quellenausfall), leere Liste = geprüft und
    # widerspruchsfrei. Eine nicht erklärte Art erzeugt keinen Widerspruch —
    # dass sie fehlt, steht im Abschnitt zur wesentlichen Änderung.
    "release_art_widersprueche": _aus_liste,
    "upstream_meldung_offen": _aus_liste,
    # #1762: Vier gerechnete Befunde, die bis v8.0.1 hier fehlten. Ohne Eintrag
    # liefert ``gerechnetes_ergebnis`` „nicht geprüft" — ein Punkt, der gerechnet
    # wurde, sähe im Bericht aus wie einer, den niemand angesehen hat.
    "update_zusagen_fehlen": _aus_mangel_flag,
    "kaufhinweis_fehlt": _aus_mangel_flag,
    "aufbewahrungsfristen_unbestimmbar": _aus_mangel_flag,
    "marktaufsicht_versaeumt": _aus_zahl,
    # #1824: Anhang I Teil II Nr. 3. ``None`` = nicht geprüft, leere Liste =
    # ein Testnachweis liegt vor und belegt den ausgelieferten Stand. Der
    # erklärte Verzicht erscheint hier als **offener** Punkt, und das ist der
    # Zweck: Er ist eine Entscheidung des Herstellers, die der Nachweis nennen
    # muss, und keine erfüllte Pflicht.
    "sicherheitstests_mangel": _aus_liste,
    # #1884: Anhang V Nr. 6. ``None`` = nicht geprüft, leere Liste = die
    # Erklärung trifft eine Aussage und sie passt zum Bewertungsweg.
    "normen_widerspruch": _aus_liste,
}


def gerechnetes_ergebnis(quelle: str, gate: dict[str, Any],
                         sprache: str | None = None) -> tuple[str, str]:
    """(Ergebnis-Schlüssel, Klartext) eines gerechneten Punktes.

    Eine ``quelle``, die das Gate nicht kennt, ist ein Fehler im Katalog und
    wird als solcher gezeigt — nicht als erfüllter Punkt.
    """
    sp = sprache or _rt.STANDARD
    auswerten = _GERECHNET_AUSWERTUNG.get(quelle)
    if auswerten is None:
        return "ungeprueft", _t(sp, "kein_rechenergebnis", quelle=quelle)
    if quelle not in gate:
        return "ungeprueft", _t(sp, "kein_rechenstand")
    return auswerten(gate.get(quelle), sp=sp,
                     ok=f"g_{quelle}_ok", fehl=f"g_{quelle}_fehl")


def wesentliche_zeile(vorgang: dict[str, Any], eintrag: dict[str, Any],
                      item, sprache: str | None = None) -> tuple[str, str, str, str]:
    """(Ergebnis, Label, Begründung, Person) der Kernfrage nach Art. 3 Nr. 30.

    Dieser Punkt steht im Katalog wie jede andere Entscheidung, wird aber über
    **eigene Spalten** gepflegt (``set_wesentliche_aenderung``, #1744). Wer nur
    den Checklisten-Eintrag liest, zeigt die Frage als „offen“, obwohl sie
    beantwortet und begründet ist — genau die Verwechslung, die ein Prüfer dem
    Bericht anlasten würde.

    Die Spalten halten **keine Person und keinen Zeitpunkt** fest. Das wird hier
    benannt und nicht ersetzt: eine erfundene Person wäre schlimmer als eine
    fehlende.
    """
    sp = sprache or _rt.STANDARD
    leer = _t(sp, "leer")
    wert = str(vorgang.get("wesentliche_aenderung") or "").strip()
    grund = (str(vorgang.get("wesentliche_aenderung_grund") or "").strip()
             or str((eintrag or {}).get("begruendung") or "").strip())
    person = _person_am((eintrag or {}).get("von"), (eintrag or {}).get("am"), sp)
    if not wert:
        erg, label = entscheidungs_ergebnis(item, eintrag, sp)
        return erg, label, grund or leer, person
    if not grund:
        return "maengel", _t(sp, "ohne_begruendung"), leer, person
    if person == leer:
        person = _t(sp, "person_nicht_erfasst")
    return "erfuellt", _t(sp, "beantwortet", wert=_antwort(sp, wert)), grund, person


def entscheidungs_ergebnis(item, stand: dict[str, Any],
                           sprache: str | None = None) -> tuple[str, str]:
    """(Ergebnis-Schlüssel, Klartext) einer Entscheidung.

    Der wichtigste Fall ist der dritte: Ein „erledigt" **ohne** Begründung darf
    im Bericht nicht als erledigt erscheinen. Sonst trägt der Nachweis einen
    Haken, hinter dem keine Aussage steht — und genau das soll die Trennung in
    drei Arten (#1744) verhindern.
    """
    from cra import release_checkliste as rc

    sp = sprache or _rt.STANDARD
    status = str((stand or {}).get("status") or "offen")
    begruendung = str((stand or {}).get("begruendung") or "").strip()
    if status == "offen":
        return "offen", _t(sp, "label_offen")
    braucht_grund = item.id in rc.BEGRUENDUNG_PFLICHT
    if braucht_grund and not begruendung:
        return "maengel", _t(sp, "ohne_begruendung")
    label = _t(sp, "label_erledigt" if status == "erledigt"
               else "label_nicht_anwendbar")
    return ("erfuellt" if status == "erledigt" else "nicht_anwendbar"), label


# ── Gleichbleibende Angaben: Stand aus dem Gate ─────────────────────────────

def _stand_support(gate: dict[str, Any], sp: str = _rt.STANDARD) -> str:
    sup = (gate.get("release_befunde") or {}).get("support")
    if not isinstance(sup, dict):
        return _t(sp, "stand_unbekannt")
    eol = sup.get("eol") or _t(sp, "eol_nicht_festgelegt")
    jahre = sup.get("support_jahre")
    return (_t(sp, "support_ende", eol=eol)
            + (_t(sp, "support_jahre", jahre=jahre) if jahre else "")
            + (_t(sp, "support_markteintritt", am=sup.get("markteintritt"))
               if sup.get("markteintritt") else ""))


def _stand_kanal(gate: dict[str, Any], sp: str = _rt.STANDARD) -> str:
    sup = (gate.get("release_befunde") or {}).get("support")
    if not isinstance(sup, dict):
        return _t(sp, "stand_unbekannt")
    return sup.get("update_kanal") or _t(sp, "kanal_nicht_dokumentiert")


def _stand_psirt(gate: dict[str, Any], sp: str = _rt.STANDARD) -> str:
    vh = (gate.get("release_befunde") or {}).get("vuln_handling")
    if not isinstance(vh, dict):
        return _t(sp, "stand_unbekannt")
    return _t(sp, "psirt_stand", n=vh.get("psirt_kontakte", 0),
              policy=_t(sp, "psirt_hinterlegt" if vh.get("policy_url")
                        else "psirt_fehlt"))


_GLEICHBLEIBEND_STAND: dict[str, Callable[..., str]] = {
    "support_zeitraum": _stand_support,
    "update_kanal": _stand_kanal,
    "psirt_kontakt": _stand_psirt,
    "disclosure_policy": _stand_psirt,
}


# ── Dokument ────────────────────────────────────────────────────────────────

def build_docx(projekt: str, *, version: str | None = None,
               db_path: Path = DB_PATH, sprache: str | None = None) -> bytes:
    """Vorgangsbericht als DOCX-Bytes. Erzeugt auch für einen Entwurf.

    ``sprache`` übersteuert die Sprache des Mandanten für diesen einen Lauf
    (#1954); ohne Angabe entscheidet ``firmen.sprache``, fail-open auf Deutsch.
    """
    from docx import Document

    from shared.reports.docx_pdf import apply_base_font, fit_tables, set_a4

    from cra import release_checkliste as rc

    d = sammeln(projekt, version, db_path=db_path, sprache=sprache)
    sp = d["sprache"]
    gate = d["gate_basis"]
    vorgang = d["vorgang"] or {}
    proj = d["projekt"]
    rv = d["release_version"]

    doc = Document()
    set_a4(doc, sprache=sp)
    apply_base_font(doc)

    titel = _t(sp, "titel")
    if d["ist_entwurf"]:
        titel += _t(sp, "titel_entwurf")
    _ueberschrift(doc, titel, level=0)
    doc.add_paragraph(_t(sp, "kopfzeile", regulation=_t(sp, "regulation"),
                         datum=date.today().strftime("%d.%m.%Y")))

    # Entwurf zuerst sagen, dann die Ampel: Wer das Band liest, muss wissen,
    # dass noch niemand freigegeben hat, bevor er die Farbe deutet.
    if d["ist_entwurf"]:
        _band(doc, FARBEN["unbekannt"], _t(sp, "entwurf_marker"),
              _t(sp, "band_entwurf", status=_status(sp, d["status"])))
    ampel = str(gate.get("ampel") or "")
    _band(doc, FARBEN.get(ampel, FARBEN["unbekannt"]),
          _t(sp, "band_ampel",
             label=_ampel(sp, ampel, _t(sp, "ampel_unbewertet"))),
          _t(sp, "band_grundlage", quelle=d["gate_basis_quelle"])
          + (_t(sp, "band_reifegrad", pct=gate.get("reifegrad_pct"))
             if gate.get("reifegrad_pct") is not None else ""))

    _kopf_tabelle(doc, d, proj, vorgang, rv, sp)
    _rechenstand_hinweis(doc, d, sp)
    _phase1(doc, d, sp)
    _wesentliche_aenderung(doc, d, vorgang, sp)
    _checkliste(doc, d, gate, vorgang, rc, sp)
    _offene_punkte(doc, gate, sp)
    _restrisiken_abschnitt(doc, d, sp)
    _vier_augen(doc, d, vorgang, sp)
    _archiv(doc, d, sp)
    _weitere_vorgaenge(doc, d, sp)

    if d["hinweise"]:
        _ueberschrift(doc, _t(sp, "h_datenlage"), level=1)
        doc.add_paragraph(_t(sp, "datenlage_intro"))
        for h in d["hinweise"]:
            doc.add_paragraph(str(h), style="List Bullet")

    doc.add_paragraph()
    doc.add_paragraph(_t(sp, "abgrenzung")).italic = True

    fit_tables(doc)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _kopf_tabelle(doc, d: dict[str, Any], proj: dict[str, Any],
                  vorgang: dict[str, Any], rv: str,
                  sp: str = _rt.STANDARD) -> None:
    leer = _t(sp, "leer")
    zeilen = [
        (_t(sp, "kopf_hersteller"), proj.get("unternehmen") or leer),
        (_t(sp, "kopf_produkt"), proj.get("produkt") or d["projekt_name"]),
        (_t(sp, "kopf_projekt"), d["projekt_name"]),
        (_t(sp, "kopf_release"), rv or _t(sp, "kopf_release_leer")),
        (_t(sp, "kopf_status"), _status(sp, d["status"])
         + (_t(sp, "kopf_status_entwurf", marker=_t(sp, "entwurf_marker"))
            if d["ist_entwurf"] else "")),
        (_t(sp, "kopf_bewertungsweg"), vorgang.get("bewertungsweg") or leer),
        (_t(sp, "kopf_berichtsdatum"), date.today().isoformat()),
    ]
    tbl = _tabelle(doc, [_t(sp, "kopf_angabe"), _t(sp, "kopf_wert")], len(zeilen))
    for ri, (k, v) in enumerate(zeilen, start=1):
        tbl.cell(ri, 0).paragraphs[0].add_run(k).bold = True
        tbl.cell(ri, 1).text = str(v)
    doc.add_paragraph()
    if not vorgang:
        doc.add_paragraph(_t(sp, "kein_vorgang"))


def _rechenstand_hinweis(doc, d: dict[str, Any], sp: str = _rt.STANDARD) -> None:
    """Auf welchem Rechenstand der Bericht steht — und wo er vom heutigen abweicht."""
    if d["gate_basis"] is not d["gate_eingefroren"]:
        if d["status"] != "entwurf" and not d["gate_eingefroren"]:
            # Ein eingereichter Vorgang *soll* seinen Stand mitgebracht haben
            # (``einreichen(..., gate=…)``). Fehlt er, ist nicht belegbar, gegen
            # welche Zahlen geprüft wurde — das gehört in den Bericht.
            doc.add_paragraph(_t(sp, "hinweis_kein_eingefrorener"))
        return
    heute = str((d["gate_heute"] or {}).get("ampel") or "")
    eingefroren = str((d["gate_eingefroren"] or {}).get("ampel") or "")
    if not heute or heute == eingefroren:
        return
    doc.add_paragraph(_t(sp, "hinweis_abweichung",
                         eingefroren=_ampel(sp, eingefroren, eingefroren),
                         heute=_ampel(sp, heute, heute)))


def _phase1(doc, d: dict[str, Any], sp: str = _rt.STANDARD) -> None:
    """Phase 1 — CRA-Ready: ausdrückliche Feststellung oder nicht festgestellt."""
    _ueberschrift(doc, _t(sp, "h_phase1"), level=1)
    p1 = d["phase1"] or {}
    status = str(p1.get("bereit_status") or "offen")
    if status == "bereit":
        doc.add_paragraph(_t(
            sp, "phase1_festgestellt",
            person=_person_am(p1.get("bereit_von"), p1.get("bereit_am"), sp)))
        if d["phase1_ueberholt"]:
            doc.add_paragraph(_t(sp, "phase1_ueberholt"))
    elif status == "entzogen":
        doc.add_paragraph(_t(
            sp, "phase1_entzogen",
            person=_person_am(p1.get("bereit_von"), p1.get("bereit_am"), sp),
            grund=(p1.get("bereit_entzug_grund")
                   or _t(sp, "phase1_entzug_grund_fehlt"))))
    else:
        doc.add_paragraph(_t(sp, "phase1_nicht"))
    gp = d["gate_produkt"] or {}
    if gp:
        doc.add_paragraph(_t(
            sp, "phase1_heute",
            ampel=_ampel(sp, gp.get("ampel"), _t(sp, "leer")),
            erfuellt=gp.get("erfuellt"),
            akzeptiert=gp.get("begruendet_akzeptiert"),
            offen=gp.get("offen"), gesamt=gp.get("gesamt_anforderungen")))


def _release_art(doc, vorgang: dict[str, Any], sp: str = _rt.STANDARD) -> None:
    """#1793: Welcher Art war dieses Release?

    Steht **vor** der Antwort auf die Kernfrage, weil die Einstufung sie
    erklärt: Ein Sicherheitsupdate, das die Zweckbestimmung nicht verändert,
    ist nach Erwägungsgrund 39 keine wesentliche Änderung. Wer den Vorgang
    später liest, sieht damit nicht nur die Antwort, sondern wovon sie
    ausgeht.
    """
    from cra import release_art as ra

    art = str((vorgang or {}).get("release_art") or "")
    if not art:
        # Bestandsvorgänge führen die Angabe nicht. Das als „unbestimmt" zu
        # drucken wäre ehrlicher als sie wegzulassen — und schweigen hieße,
        # der Leser müsste raten, ob die Frage gestellt wurde.
        doc.add_paragraph(_t(sp, "release_art_nicht"))
        return
    # Bezeichnung und Erklärung kommen aus ``cra.release_art`` und bleiben
    # deutsch (#1954): Sie gehören nicht diesem Renderer. Ihre Übersetzung ist
    # ein eigener Vorgang in der Datei, in der sie stehen.
    doc.add_paragraph(_t(sp, "release_art", label=ra.label(art),
                         erklaerung=ra.ERKLAERUNG[art]))


def _wesentliche_aenderung(doc, d: dict[str, Any], vorgang: dict[str, Any],
                           sp: str = _rt.STANDARD) -> None:
    """Art. 3 Nr. 30 — die Verzweigung, die alles Weitere auslöst."""
    _ueberschrift(doc, _t(sp, "h_wesentlich"), level=1)
    _release_art(doc, vorgang, sp)
    wert = str(vorgang.get("wesentliche_aenderung") or "").strip()
    grund = str(vorgang.get("wesentliche_aenderung_grund") or "").strip()
    if not wert:
        doc.add_paragraph(_t(sp, "wesentlich_offen"))
    else:
        doc.add_paragraph(_t(sp, "wesentlich_antwort",
                             wert=_antwort(sp, "ja" if wert == "ja" else "nein")))
        # Ohne Begründung bleibt die Antwort stehen, gilt aber nicht als Nachweis —
        # die Datenbank verlangt sie (#1744), Altbestand kann sie vermissen lassen.
        fehlt = _t(sp, "wesentlich_grund_fehlt")
        doc.add_paragraph(_t(sp, "wesentlich_grund", grund=grund or fehlt))
        if wert == "ja":
            doc.add_paragraph(_t(sp, "wesentlich_folge"))
    # Umfang der Neubewertung — eigener Prüfpunkt des Katalogs.
    umfang = ((vorgang.get("release_checkliste") or {}).get("neubewertung_umfang") or {})
    text = str(umfang.get("begruendung") or "").strip()
    doc.add_paragraph(_t(sp, "wesentlich_umfang",
                         text=text if text else _t(sp, "nicht_dokumentiert")))


def _checkliste(doc, d: dict[str, Any], gate: dict[str, Any],
                vorgang: dict[str, Any], rc, sp: str = _rt.STANDARD) -> None:
    """Die Checkliste in ihren drei Arten — getrennt, weil sie unterschiedlich
    zustande kommen (gerechnet / entschieden / bestätigt)."""
    _ueberschrift(doc, _t(sp, "h_checkliste"), level=1)
    stand = vorgang.get("release_checkliste") or {}
    doc.add_paragraph(_t(sp, "checkliste_intro", quelle=d["gate_basis_quelle"]))

    for art in ("gerechnet", "entscheidung", "gleichbleibend"):
        items = [i for i in rc.KATALOG if i.art == art]
        if not items:
            continue
        _ueberschrift(doc, _t(sp, f"art_{art}"), level=2)
        # ``item.label`` und ``item.rechtsbezug`` kommen aus
        # ``cra.release_checkliste`` und bleiben deutsch (#1954) — sie gehören
        # nicht diesem Renderer.
        if art == "gerechnet":
            kopf = [_t(sp, "sp_pruefpunkt"), _t(sp, "sp_rechtsbezug"),
                    _t(sp, "sp_ergebnis")]
        elif art == "entscheidung":
            kopf = [_t(sp, "sp_pruefpunkt"), _t(sp, "sp_rechtsbezug"),
                    _t(sp, "sp_ergebnis"), _t(sp, "sp_begruendung"),
                    _t(sp, "sp_person")]
        else:
            kopf = [_t(sp, "sp_angabe"), _t(sp, "sp_rechtsbezug"),
                    _t(sp, "sp_stand"), _t(sp, "sp_bestaetigung")]
        tbl = _tabelle(doc, kopf, len(items))
        for ri, item in enumerate(items, start=1):
            tbl.cell(ri, 0).text = item.label + ("" if item.pflicht
                                                 else _t(sp, "optional"))
            tbl.cell(ri, 1).text = item.rechtsbezug
            if art == "gerechnet":
                erg, text = gerechnetes_ergebnis(item.quelle, gate, sp)
                z = tbl.cell(ri, 2)
                _schattieren(z, ERG_FARBE.get(erg, "FFFFFF"))
                z.text = text
            elif art == "entscheidung":
                eintrag = stand.get(item.id) or {}
                if item.id == "wesentliche_aenderung":
                    erg, label, grund, person = wesentliche_zeile(
                        vorgang, eintrag, item, sp)
                else:
                    erg, label = entscheidungs_ergebnis(item, eintrag, sp)
                    grund = (str(eintrag.get("begruendung") or "").strip()
                             or _t(sp, "leer"))
                    person = _person_am(eintrag.get("von"), eintrag.get("am"), sp)
                z = tbl.cell(ri, 2)
                _schattieren(z, ERG_FARBE.get(erg, "FFFFFF"))
                z.text = label
                tbl.cell(ri, 3).text = grund
                tbl.cell(ri, 4).text = person
            else:
                tbl.cell(ri, 2).text = _GLEICHBLEIBEND_STAND.get(
                    item.id,
                    lambda _g, _sp=_rt.STANDARD: _t(_sp, "stand_unbekannt"))(gate, sp)
                eintrag = stand.get(item.id) or {}
                bestaetigt = str(eintrag.get("status") or "offen") != "offen"
                z = tbl.cell(ri, 3)
                _schattieren(z, ERG_FARBE["bestaetigt" if bestaetigt else "offen"])
                z.text = (_t(sp, "bestaetigt",
                             person=_person_am(eintrag.get("von"),
                                               eintrag.get("am"), sp))
                          if bestaetigt else _t(sp, "nicht_bestaetigt"))
        doc.add_paragraph()


def _offene_punkte(doc, gate: dict[str, Any], sp: str = _rt.STANDARD) -> None:
    _ueberschrift(doc, _t(sp, "h_offene"), level=1)
    punkte = gate.get("offene_punkte") or []
    if not punkte:
        doc.add_paragraph(_t(sp, "offene_keine"))
        return
    tbl = _tabelle(doc, [_t(sp, "sp_phase"), _t(sp, "sp_art"), _t(sp, "sp_punkt"),
                         _t(sp, "sp_hinweis")], len(punkte))
    for ri, p in enumerate(punkte, start=1):
        z = tbl.cell(ri, 0)
        _schattieren(z, ERG_FARBE["ungeprueft" if p.get("ungeprueft") else "offen"])
        z.text = _t(sp, "phase_release" if str(p.get("phase")) == "release"
                    else "phase_produkt")
        # ``typ``, ``titel`` und ``hinweis`` stammen aus
        # ``cra.konformitaet_gate`` und bleiben deutsch (#1954).
        tbl.cell(ri, 1).text = str(p.get("typ") or "")
        tbl.cell(ri, 2).text = str(p.get("titel") or "")
        hinweis = str(p.get("hinweis") or "")
        if p.get("ungeprueft"):
            hinweis = f"{hinweis}{_t(sp, 'ungeprueft_zusatz')}"
        tbl.cell(ri, 3).text = hinweis
    doc.add_paragraph()


def _restrisiken_abschnitt(doc, d: dict[str, Any], sp: str = _rt.STANDARD) -> None:
    _ueberschrift(doc, _t(sp, "h_restrisiken"), level=1)
    leer = _t(sp, "leer")
    rr = d["restrisiken"]
    abw = rr["abweichungen"]
    if abw:
        doc.add_paragraph(_t(sp, "restrisiken_intro"))
        tbl = _tabelle(doc, [_t(sp, "sp_anforderung"), _t(sp, "sp_rechtsgrundlage"),
                             _t(sp, "sp_kategorie"), _t(sp, "sp_begruendung"),
                             _t(sp, "sp_akzeptiert_von")], len(abw))
        for ri, a in enumerate(abw, start=1):
            tbl.cell(ri, 0).text = f"{a.get('requirement_id')} — {a.get('titel') or ''}"
            tbl.cell(ri, 1).text = str(a.get("rechtsgrundlage") or a.get("ref") or "")
            z = tbl.cell(ri, 2)
            _schattieren(z, ERG_FARBE["maengel"])
            z.text = str(a.get("kategorie") or "")
            tbl.cell(ri, 3).text = str(a.get("grund") or leer)
            tbl.cell(ri, 4).text = str(a.get("von") or leer)
        doc.add_paragraph()
    else:
        doc.add_paragraph(_t(sp, "restrisiken_keine"))

    if rr["offene_abweichungen"]:
        doc.add_paragraph(_t(sp, "restrisiken_offen",
                             n=len(rr["offene_abweichungen"])))

    if rr["weitere"]:
        _ueberschrift(doc, _t(sp, "h_weitere_risiken", projekt=rr["rb_projekt"]),
                      level=2)
        doc.add_paragraph(_t(sp, "weitere_risiken_intro"))
        tbl = _tabelle(doc, [_t(sp, "sp_nr"), _t(sp, "sp_risiko"), _t(sp, "sp_stufe"),
                             _t(sp, "sp_kategorie"), _t(sp, "sp_begruendung"),
                             _t(sp, "sp_akzeptiert_von")], len(rr["weitere"]))
        for ri, r in enumerate(rr["weitere"], start=1):
            tbl.cell(ri, 0).text = str(r.get("nr") or "")
            tbl.cell(ri, 1).text = str(r.get("titel") or "")
            tbl.cell(ri, 2).text = str(r.get("level") or "")
            tbl.cell(ri, 3).text = str(r.get("kategorie") or "")
            tbl.cell(ri, 4).text = str(r.get("grund") or leer)
            tbl.cell(ri, 5).text = _person_am(r.get("von"), r.get("am"), sp)
        doc.add_paragraph()


def _vier_augen(doc, d: dict[str, Any], vorgang: dict[str, Any],
                sp: str = _rt.STANDARD) -> None:
    """Wer eingereicht, geprüft, freigegeben und veröffentlicht hat."""
    _ueberschrift(doc, _t(sp, "h_vier_augen"), level=1)
    leer = _t(sp, "leer")
    zeilen = [
        (_t(sp, "va_erstellt"), _person_am(vorgang.get("erstellt_von"),
                                           vorgang.get("eingereicht_am"), sp)),
        (_t(sp, "va_geprueft"), _person_am(vorgang.get("geprueft_von"),
                                           vorgang.get("geprueft_am"), sp)),
        (_t(sp, "va_freigegeben"), _person_am(vorgang.get("freigegeben_von"),
                                              vorgang.get("freigegeben_am"), sp)),
        (_t(sp, "va_veroeffentlicht"),
         _datum(vorgang.get("veroeffentlicht_am")) or leer),
    ]
    tbl = _tabelle(doc, [_t(sp, "sp_rolle"), _t(sp, "sp_person_zeitpunkt")],
                   len(zeilen))
    for ri, (k, v) in enumerate(zeilen, start=1):
        tbl.cell(ri, 0).paragraphs[0].add_run(k).bold = True
        tbl.cell(ri, 1).text = v
    doc.add_paragraph()
    grund = str(vorgang.get("zurueckweisung_grund") or "").strip()
    if grund:
        doc.add_paragraph(_t(sp, "zurueckgewiesen_grund", grund=grund))
    if d["ist_entwurf"]:
        doc.add_paragraph(_t(sp, "va_entwurf", marker=_t(sp, "entwurf_marker")))


def _archiv(doc, d: dict[str, Any], sp: str = _rt.STANDARD) -> None:
    """Verweis auf die unveränderlichen Nachweise — mit SHA-256."""
    _ueberschrift(doc, _t(sp, "h_archiv"), level=1)
    leer = _t(sp, "leer")
    doc.add_paragraph(_t(sp, "archiv_intro"))
    archiv = d["archiv"] or d["archiv_alle"]
    if not archiv:
        doc.add_paragraph(_t(sp, "archiv_keines"))
        return
    if not d["archiv"] and d["archiv_alle"]:
        doc.add_paragraph(_t(sp, "archiv_keine_version",
                             version=d["release_version"] or leer))
    tbl = _tabelle(doc, [_t(sp, "sp_version"), _t(sp, "sp_ampel"), _t(sp, "sp_sha"),
                         _t(sp, "sp_freigegeben")], len(archiv))
    for ri, a in enumerate(archiv, start=1):
        tbl.cell(ri, 0).text = str(a.get("version") or leer)
        z = tbl.cell(ri, 1)
        ampel = str(a.get("ampel") or "")
        _schattieren(z, ERG_FARBE["erfuellt" if ampel == "gruen" else "maengel"])
        z.text = _ampel(sp, ampel, ampel or leer)
        tbl.cell(ri, 2).text = str(a.get("sha256") or leer)
        tbl.cell(ri, 3).text = _person_am(a.get("freigegeben_von"),
                                          a.get("freigegeben_am"), sp)
    doc.add_paragraph()


def _weitere_vorgaenge(doc, d: dict[str, Any], sp: str = _rt.STANDARD) -> None:
    """Kurze Reihe der übrigen Release-Vorgänge — für die Ablage, nicht als Bewertung."""
    andere = [v for v in (d["vorgaenge"] or [])
              if str(v.get("release_version") or "").strip()
              and v is not d["vorgang"]]
    if not andere:
        return
    _ueberschrift(doc, _t(sp, "h_weitere_vorgaenge"), level=1)
    tbl = _tabelle(doc, [_t(sp, "sp_version"), _t(sp, "sp_status"),
                         _t(sp, "sp_wesentliche_aenderung"),
                         _t(sp, "sp_freigegeben")], len(andere))
    for ri, v in enumerate(andere, start=1):
        tbl.cell(ri, 0).text = str(v.get("release_version") or "")
        tbl.cell(ri, 1).text = _status(sp, v.get("freigabe_status"))
        tbl.cell(ri, 2).text = (_antwort(sp, v.get("wesentliche_aenderung"))
                                or _t(sp, "nicht_beantwortet"))
        tbl.cell(ri, 3).text = _person_am(v.get("freigegeben_von"),
                                          v.get("freigegeben_am"), sp)
    doc.add_paragraph()


def build_pdf(projekt: str, *, version: str | None = None,
              db_path: Path = DB_PATH, sprache: str | None = None) -> bytes:
    """PDF über denselben DOCX-Weg (#1614) — kein zweiter Renderer."""
    from shared.reports.docx_pdf import docx_bytes_to_pdf

    return docx_bytes_to_pdf(build_docx(projekt, version=version, db_path=db_path,
                                        sprache=sprache))


def build(projekt: str, *, fmt: str = "docx", version: str | None = None,
          db_path: Path = DB_PATH, sprache: str | None = None) -> bytes:
    if (fmt or "docx").lower() == "pdf":
        return build_pdf(projekt, version=version, db_path=db_path,
                         sprache=sprache)
    return build_docx(projekt, version=version, db_path=db_path, sprache=sprache)


# ── Kontext für die KI-Zusammenfassung ──────────────────────────────────────

def summary_kontext(projekt: str, version: str | None = None,
                    db_path: Path = DB_PATH,
                    sprache: str | None = None) -> dict[str, Any]:
    """Zusatzschlüssel zum Vertrag von :mod:`shared.reports.summary`.

    ``reifegrad``/``offene`` liefert der CRA-Adapter; was hier dazukommt, ist der
    **Vorgang**. Zusatzschlüssel gehen als JSON-Block in den Prompt (#1725) —
    vorher verwarf der Prompt-Bauer alles außer den zwei Pflichtschlüsseln, und
    die KI berichtete „keine Daten vorhanden".

    Die Sprache wird mitgeführt, damit nicht in einer englischen
    Zusammenfassung eine deutsche Statusbezeichnung steht (#1954). Die
    **Antwort** selbst stellt der Vorrang-Block um — das ist eine andere Stelle
    und bleibt es.

    Best effort: Ohne Vorgang bleibt ``release_vorgang`` leer, die
    Zusammenfassung läuft trotzdem.
    """
    try:
        d = sammeln(projekt, version, db_path=db_path, sprache=sprache)
    except Exception:  # noqa: BLE001
        return {}
    if not d.get("vorgang"):
        return {}
    sp = d["sprache"]
    gate = d["gate_basis"]
    vorgang = d["vorgang"]
    return {"release_vorgang": {
        "release_version": d["release_version"],
        "status": _status(sp, d["status"]),
        "ist_entwurf": d["ist_entwurf"],
        "ampel": gate.get("ampel"),
        "rechenstand": d["gate_basis_quelle"],
        # Der gespeicherte Wert bleibt der gespeicherte Wert — die KI
        # bekommt „ja"/„nein" als Datenwert, nicht als übersetzte Prosa.
        "wesentliche_aenderung": vorgang.get("wesentliche_aenderung")
        or _t(sp, "nicht_beantwortet"),
        "wesentliche_aenderung_grund": vorgang.get("wesentliche_aenderung_grund") or "",
        "phase1_festgestellt": (d["phase1"] or {}).get("bereit_status") == "bereit",
        "phase1_ueberholt": d["phase1_ueberholt"],
        "geprueft_von": vorgang.get("geprueft_von") or "",
        "freigegeben_von": vorgang.get("freigegeben_von") or "",
        "offene_punkte_anzahl": len(gate.get("offene_punkte") or []),
        "akzeptierte_restrisiken": len(d["restrisiken"]["abweichungen"]),
        "archivierte_nachweise": len(d["archiv"]),
        "datenlage_hinweise": d["hinweise"],
    }}
