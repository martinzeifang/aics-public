# Aufbewahrung der Nachweise

Beantwortet die Anforderung **IMPL-05** der Eigenbewertung.

## Drei Fristen, nicht eine

Der Verordnungstext verlangt an drei Stellen zehn Jahre, und die drei meinen
**verschiedene Gegenstände**. Das ist bisher vermischt worden und ist der Grund,
warum dieses Dokument eine Fassung 1.1 hat:

| Fundstelle | Was zehn Jahre halten muss | Gegenüber wem |
|---|---|---|
| **Art. 13 Abs. 13** | technische Dokumentation und EU-Konformitätserklärung | den Marktüberwachungsbehörden |
| **Art. 13 Abs. 18** | die Informationen und Anleitungen nach Anhang II — und zwar *zugänglich*, bei Online-Bereitstellung „zugänglich, benutzerfreundlich und online verfügbar" | den Nutzern |
| **Art. 13 Abs. 9** | **jede bereitgestellte Sicherheitsaktualisierung selbst** — also das Artefakt, nicht die Unterlage dazu | den Nutzern |

Jeweils zehn Jahre **oder** für die Dauer des Unterstützungszeitraums, je
nachdem, welcher Zeitraum länger ist.

!!! warning "Abs. 9 betrifft das Abbild, nicht das Papier"
    Bis zur Fassung 1.0 dieses Dokuments war Abs. 9 als Aufbewahrungspflicht für
    Unterlagen zitiert. Er verlangt etwas anderes und Handfesteres: Die
    **Sicherheitsaktualisierung bleibt verfügbar**. Für dieses Produkt heißt
    das, dass die Container-Abbilder jeder Fassung, die eine
    Sicherheitsaktualisierung getragen hat, zehn Jahre abrufbar sein müssen.

    Heute liegen sie im öffentlichen Paketverzeichnis, unbefristet — aber das
    ist das Versprechen einer Plattform und nicht unser Nachweis. Daraus folgt
    Festlegung 7 unten: Eine Kopie der ausgelieferten Abbilder gehört in den
    Archivstand.

## Die Frist für dieses Produkt

| | |
|---|---|
| Inverkehrbringen | Oktober 2026 |
| Unterstützungszeitraum endet | Oktober 2031 |
| **Aufbewahrung bis mindestens** | **Oktober 2036** |

Zehn Jahre sind hier der längere Zeitraum und damit maßgeblich. Die Frist läuft je
Fassung ab deren Inverkehrbringen — eine Fassung von 2029 ist bis 2039 aufzubewahren. Für
die Planung gilt deshalb nicht „bis Oktober 2036", sondern „zehn Jahre ab der jeweils
letzten ausgelieferten Fassung".

**Die Pflichten enden nicht mit der Betriebstätigkeit.** Sie treffen den
Hersteller, nicht den laufenden Betrieb — siehe
[Einstellung der Betriebstätigkeit](einstellung-betriebstaetigkeit.md). Deshalb
ist der zweite Aufbewahrungsort bewusst außerhalb des Betriebs gewählt.

## Was aufzubewahren ist

| Gegenstand | Wo es entsteht | Wo es liegt |
|---|---|---|
| EU-Konformitätserklärung je Fassung | CRA-Modul, Ausstellung | Archiv im Dateibestand der Installation, mit SHA-256 je Fassung |
| Technische Dokumentation nach Anhang VII | CRA-Modul: Anforderungsregister, Bedrohungsmodell, Risikobewertung, Schwachstellenregister, Stückliste je Artefakt, Testnachweise | Datenbank der Installation |
| Konformitätsnachweis je Release | CRA-Modul, Freigabe | Archiv mit SHA-256 |
| Software-Stückliste je Fassung | Bauprozess | als Attestation am Abbild im öffentlichen Paketverzeichnis **und** als Zeile im CRA-Modul |
| Testnachweise (Penetrationstests, automatisierte Prüfungen mit Protokoll) | Nachweis-Ablage der Firma, Pentest-Modul | Dateibestand der Installation, mit Prüfsumme |
| Revisionspfad (wer hat wann was freigegeben) | gesamte Anwendung | Datenbank, fortschreibungssicher |
| Freigabehinweise und Sicherheitshinweise | Quellverzeichnis, Produktseite | öffentlich |

## Wie die Aufbewahrung getragen wird

| Träger | Deckt | Hält |
|---|---|---|
| Datenbank der Produktivinstallation | alles aus der Akte | solange die Installation besteht |
| Nächtliche Sicherung (Datenbank, Dateibestand, Konfiguration) | alles | **nur die letzten fünf Sicherungen** |
| Öffentliches Paketverzeichnis | Abbilder, Signaturen, Stücklisten-Attestationen | unbefristet, solange das Verzeichnis geführt wird |
| Quellverzeichnis | Quellstand je Fassung, Freigabehinweise, Advisories | unbefristet |
| Artefakte der Entwicklungsstrecke (Nachweispakete, Risiko-Export) | Zwischenergebnisse je Lauf | **90 Tage** (Voreinstellung der Plattform) |

!!! danger "Die Frist ist heute nicht erfüllt"
    Keiner der Träger oben hält zehn Jahre zu:

    * Die Sicherung behält **fünf** Stände. Nach fünf Nächten ist der Stand von
      vorgestern weg — das ist richtig für den **Wiederanlauf**, wofür die Sicherung
      gebaut ist, und falsch für die **Aufbewahrung**, die etwas anderes ist.
    * Die Artefakte der Entwicklungsstrecke verfallen nach 90 Tagen.
    * Die Datenbank der Installation hält alles, aber sie ist ein laufendes System und
      kein Archiv: Ein Datenverlust, eine Migration oder eine Außerbetriebnahme nimmt
      die Akte mit.

    Ein Archivierungskonzept fehlt damit. Es ist der größte offene Punkt dieses Dossiers,
    weil er sich nicht durch Sorgfalt auffangen lässt: Was nach fünf Nächten gelöscht
    ist, lässt sich im Jahr 2034 nicht mehr vorlegen.

## Das Konzept, das daraus folgt

Festgelegt, noch nicht vollständig umgesetzt:

| Nr. | Festlegung |
|---|---|
| 1 | **Je Fassung ein Archivstand.** Mit jeder ausgelieferten Fassung wird ein Abzug der Akte erzeugt — EU-Konformitätserklärung, Konformitätsnachweis, Stückliste, Testnachweise, Gate-Ergebnis — und als ein Paket mit Prüfsumme abgelegt. Das ist ein eigener Vorgang, nicht die nächtliche Sicherung. |
| 2 | **Zwei Orte, davon einer außerhalb des Betriebs.** Ein Archivstand, der nur auf demselben Datenträgerverbund liegt wie die laufende Anwendung, überlebt dessen Verlust nicht. |
| 3 | **Unveränderlich ab der Ablage.** Der Archivstand wird nicht fortgeschrieben; eine Korrektur erzeugt einen neuen Stand und lässt den alten stehen. |
| 4 | **Prüfbar ohne die Anwendung.** Prüfsummen und ein Verzeichnis liegen im Klartext daneben. Ein Archiv, das nur die Anwendung lesen kann, ist in zehn Jahren wertlos. |
| 5 | **Verschlüsselt, mit getrennt verwahrtem Schlüssel.** Ein Archivstand ist ein vollständiger Abzug des Datenbestands mehrerer Mandanten. Ein verlorener Schlüssel ist dabei dasselbe wie ein verlorenes Archiv — die Verwahrung gehört ausdrücklich dazu und nicht in dieselbe Ablage. |
| 6 | **Einmal im Jahr eine Rückprobe.** Ein Archivstand wird stichprobenweise wieder lesbar gemacht. Ein Archiv, aus dem nie etwas zurückgeholt wurde, ist eine Annahme. |
| 7 | **Die ausgelieferten Abbilder gehören dazu.** Art. 13 Abs. 9 verlangt die Verfügbarkeit der Sicherheitsaktualisierung selbst. Der Archivstand trägt deshalb die beiden Abbilder der Fassung als Datei samt Digest — nicht nur den Verweis auf das Paketverzeichnis. |
| 8 | **Der Archivstand zählt nicht gegen die Aufbewahrungsgrenze der Sicherungen.** Sonst räumt der Zeitplan ihn weg, und zwar genau dann, wenn über Jahre viele entstehen. Vorbild sind die Sicherheitskopien vor einem Einspielen, die aus demselben Grund ausgenommen sind. |

Die Punkte 1 bis 4 und 7 sind mit den vorhandenen Mitteln umsetzbar: Die Anwendung erzeugt
Sicherungen mit Verzeichnis und Prüfsummen bereits und kann sie **herunterladen** — damit
lässt sich ein Archivstand erzeugen, ohne Neues zu bauen. Was fehlt, ist die Festlegung,
dass es geschieht, der zweite Ort und die Rückprobe.

## Das Verfahren je Fassung

Auszuführen **nach** dem Deploy einer Fassung auf die Produktivinstanz und vor
dem Abschluss des Release-Vorgangs. Vorbereitet in
`~/werkzeuge/archivstand-erzeugen.sh`.

| Schritt | Was | Woher |
|---|---|---|
| 1 | Konformitätsnachweis der Fassung erzeugen und ablegen | CRA-Modul, Releases-Tab |
| 2 | EU-Konformitätserklärung der Fassung erzeugen und ablegen | CRA-Modul, Konformität |
| 3 | Kundenfassung des Nachweises erzeugen | CRA-Modul |
| 4 | Gate-Ergebnis und Vorgangsbericht der Fassung ablegen | CRA-Modul, Releases-Tab |
| 5 | Stückliste je Artefakt aus der Attestierung am Digest holen | Paketverzeichnis |
| 6 | Die beiden Abbilder als Datei sichern, mit Digest | Paketverzeichnis |
| 7 | Vollständige Sicherung erzeugen und herunterladen | Administration → Sicherung |
| 8 | Verzeichnis im Klartext erzeugen: was liegt drin, welche Fassung, welches Datum, welche Prüfsumme | Skript |
| 9 | Prüfsummen über alle Dateien bilden und in das Verzeichnis schreiben | Skript |
| 10 | Paket an **beide** Orte legen | Betrieb |
| 11 | Ablage im Release-Vorgang vermerken: Datum, Prüfsumme des Pakets, beide Orte | CRA-Modul |

Schritt 8 ist der, den man am ehesten weglässt, und der, der in zehn Jahren den
Unterschied macht: Ein Verzeichnis im Klartext sagt einem Leser, der die
Anwendung nicht hat, was er vor sich hat.

## Verantwortung und Turnus

| Was | Wer | Wann |
|---|---|---|
| Archivstand erzeugen und ablegen | Inhaber | je ausgelieferter Fassung |
| Vollständigkeit prüfen: trägt jeder Stand die elf Positionen oben? | Inhaber | jährlich |
| Rückprobe: einen Stand stichprobenweise lesbar machen und gegen die Prüfsummen halten | Inhaber | jährlich |
| Zweiten Ort prüfen: erreichbar, lesbar, vollständig | Inhaber | jährlich |
| Fristen prüfen: steht ein Stand zur Löschung an? | Inhaber | jährlich |

Der jährliche Termin ist derselbe wie die Durchsicht nach
[Governance](governance.md) — vier Prüfungen an einem Tag, statt vier Termine,
die einzeln vergessen werden.

### Nachweis der Durchführung

| Jahr | Vollständigkeit geprüft | Rückprobe erfolgreich | Zweiter Ort geprüft | Durchgeführt von |
|---|---|---|---|---|
| _(noch nicht durchgeführt)_ | | | | |

!!! warning "Dieser Punkt ist offen"
    Das Konzept steht, das Verfahren steht, das Skript liegt bereit. Es gibt
    **keinen Archivstand** und **keinen zweiten Ort**. Solange die Tabelle oben
    leer ist, ist IMPL-05 nicht erfüllt — und zwar nicht teilweise, sondern
    nicht: Was nach fünf Nächten gelöscht ist, lässt sich 2034 nicht vorlegen.

    Geführt als **C2** in [Abweichungen](abweichungen.md), fällig 31. März 2027.
    Der zweite Ort hängt an der Verschlüsselung (**B2**) — ein unverschlüsselter
    vollständiger Abzug des Mandantenbestands an einem zweiten Ort wäre ein
    neues Risiko und keine Verbesserung.

## Abgrenzung: Sicherung ist nicht Archivierung

Die Unterscheidung ist der eigentliche Inhalt dieses Dokuments:

| | Sicherung | Archivstand |
|---|---|---|
| Zweck | Wiederanlauf nach einem Verlust | Nachweis gegenüber Behörde und Kunde |
| Inhalt | der **aktuelle** Stand | der Stand **zum Zeitpunkt einer Fassung** |
| Lebensdauer | Tage | zehn Jahre |
| Einspielen | überschreibt den Bestand | wird nie eingespielt, nur gelesen |
| Zahl | fünf | einer je ausgelieferter Fassung |

Dass die Anwendung beides kann — Wiederherstellen **und** Übernehmen —, hilft hier nicht
weiter: Beides sind Wege *in* ein laufendes System. Ein Archivstand geht nicht hinein.

## Löschung nach Fristablauf

Ein Archivstand wird nach Ablauf der zehn Jahre gelöscht, nicht unbegrenzt gehalten. Er
enthält personenbezogene Daten aus Mandantenbeständen; eine Aufbewahrung „für alle Fälle"
hätte dafür keine Grundlage. Die Löschung wird vermerkt — mit Angabe, welcher Stand
gelöscht wurde und wann.

| Gelöscht am | Archivstand (Fassung) | Frist lief ab | Gelöscht von |
|---|---|---|---|
| _(noch keine Löschung fällig — die erste Frist endet Oktober 2036)_ | | | |

Dass diese Tabelle auf Jahre leer bleibt, ist kein Grund, sie weglassen: Wer sie
2036 anlegt, hat bis dahin keinen Ort, an dem die Frist auffällt.

**Fassung 1.1, 2. November 2026.** Fundstellen: Art. 13 Abs. 9 (Verfügbarkeit der
Sicherheitsaktualisierungen), Abs. 13 (technische Dokumentation und
EU-Konformitätserklärung), Abs. 18 (Zugänglichkeit der Nutzerinformationen),
Abs. 23 (Einstellung der Betriebstätigkeit), Anhang II, Anhang VII der
Verordnung (EU) 2024/2847. Gegen die amtliche deutsche Fassung geprüft
(ABl. L vom 20.11.2024).
