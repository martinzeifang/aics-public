# Aufbewahrung der Nachweise

Beantwortet die Anforderung **IMPL-05** der Eigenbewertung. Fundstellen: Art. 13 Abs. 9
und 13 — die technische Dokumentation und die EU-Konformitätserklärung sind
**zehn Jahre** nach dem Inverkehrbringen oder für die Dauer des Unterstützungszeitraums
aufzubewahren, je nachdem, welcher Zeitraum länger ist.

## Die Frist

| | |
|---|---|
| Inverkehrbringen | Oktober 2026 |
| Unterstützungszeitraum endet | Oktober 2031 |
| **Aufbewahrung bis mindestens** | **Oktober 2036** |

Zehn Jahre sind hier der längere Zeitraum und damit maßgeblich. Die Frist läuft je
Fassung ab deren Inverkehrbringen — eine Fassung von 2029 ist bis 2039 aufzubewahren. Für
die Planung gilt deshalb nicht „bis Oktober 2036", sondern „zehn Jahre ab der jeweils
letzten ausgelieferten Fassung".

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

Die Punkte 1 bis 4 sind mit den vorhandenen Mitteln umsetzbar: Die Anwendung erzeugt
Sicherungen mit Verzeichnis und Prüfsummen bereits und kann sie **herunterladen** — damit
lässt sich ein Archivstand erzeugen, ohne Neues zu bauen. Was fehlt, ist die Festlegung,
dass es geschieht, der zweite Ort und die Rückprobe.

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

**Fassung 1.0, 2. November 2026.** Fundstellen: Art. 13 Abs. 9 und 13, Anhang VII der
Verordnung (EU) 2024/2847.
