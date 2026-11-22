# Marktüberwachung — Unterlagen und Zusammenarbeit

Beantwortet die Anforderung **ART13-05** der Eigenbewertung. Fundstelle:
Art. 13 Abs. 22 der Verordnung (EU) 2024/2847.

> Die Hersteller übermitteln der Marktüberwachungsbehörde auf deren begründetes
> Verlangen in Papierform oder in elektronischer Form in einer für diese Behörde
> leicht verständlichen Sprache alle Informationen und Unterlagen, die für den
> Nachweis der Konformität des Produkts mit digitalen Elementen und der vom
> Hersteller festgelegten Verfahren mit den grundlegenden Cybersicherheits\-
> anforderungen in Anhang I erforderlich sind. Die Hersteller arbeiten mit dieser
> Behörde auf deren Verlangen bei allen Maßnahmen zur Abwendung der Cybersicher\-
> heitsrisiken zusammen, die mit dem von ihnen in den Verkehr gebrachten Produkt
> mit digitalen Elementen verbunden sind.

!!! warning "Eine Frist steht hier nicht im Gesetz"
    Art. 13 Abs. 22 nennt **keine** Frist — nur „auf deren begründetes
    Verlangen". Die Zahlen unten sind eigene Festlegungen und als solche
    gekennzeichnet. Sie stehen hier, weil „auf Verlangen" ohne Maß im
    Nachhinein nicht überprüfbar ist.

    Das ist kein Nebensatz: Eine erfundene Rechtsfrist in einer Nachweisakte ist
    eine Falschangabe, und sie fällt genau der Behörde auf, an die sie sich
    richtet.

## Zwei Pflichten, nicht eine

| Pflicht | Was sie verlangt | Auslöser |
|---|---|---|
| **Vorlage** | alle Informationen und Unterlagen, die die Konformität des Produkts **und der Verfahren** mit Anhang I belegen | begründetes Verlangen der Behörde |
| **Zusammenarbeit** | Mitwirkung bei Maßnahmen zur Abwendung von Cybersicherheitsrisiken | Verlangen der Behörde |

Die zweite wird leicht überlesen und ist die weitergehende: Sie endet nicht mit
dem Übersenden von Unterlagen, sondern verlangt Mitwirkung an einer Maßnahme —
und sie kennt keine Grenze „soweit zumutbar".

## Ansprechstelle

| Rolle | Wer | Erreichbar |
|---|---|---|
| **Ansprechpartner für Behörden** | Martin Zeifang, Inhaber | `kontakt@cyberwoks.de`, postalisch Finkenweg 42, 89150 Laichingen |
| In Sicherheitsfragen zusätzlich | zentrale Anlaufstelle `security@cyberwoks.de` | wird arbeitstäglich gelesen |
| Vertretung | siehe [Governance](governance.md) — **offen**, als Risiko geführt |

Eine behördliche Anfrage geht an **eine** benannte Person und nicht an ein
Postfach, das jemand irgendwann liest. Dass dieselbe Person auch der Hersteller
ist, ist bei einem Einzelunternehmen der Normalfall und wird nicht als Trennung
dargestellt, die es nicht gibt.

**Postalisch zugehende Anfragen** werden arbeitstäglich erfasst. Das ist der
Weg, auf dem Behörden regelmäßig schreiben, und er hängt nicht an einem
Postfach, das elektronisch überwacht wird.

## Was vorzulegen ist — die Soll-Liste

Die Behörde fragt nach dem, was Anhang I belegt. Das ist die technische
Dokumentation nach Art. 31 und Anhang VII. Sie liegt vollständig in der
Installation; die Liste sagt, **wo**, damit im Ernstfall nicht gesucht wird:

| Unterlage | Fundstelle in der Akte | Anhang VII |
|---|---|---|
| Beschreibung des Produkts, Zweckbestimmung, Fassungen | CRA-Modul, Projektstammdaten und Erklärung | Nr. 1 |
| Bewertung der Cybersicherheitsrisiken | verknüpfte Risikobewertung | Nr. 3 |
| Unterstützungszeitraum samt Herleitung | CRA-Modul, Unterstützungszeitraum | Nr. 2 Buchst. a |
| Grundlegende Anforderungen und wie sie erfüllt werden | CRA-Modul, Anforderungen — 36 Einzelbewertungen mit Nachweisen | Nr. 3 |
| Angewandte Normen und Spezifikationen | EU-Konformitätserklärung Nr. 6 | Nr. 4 |
| Berichte über Prüfungen des Produkts | Nachweisablage, Pentest-Berichte | Nr. 6 |
| EU-Konformitätserklärung | CRA-Modul, Erklärung samt Archiv | Nr. 7 |
| Software-Stückliste | CRA-Modul, Stückliste je Fassung und Artefakt | Nr. 8; Anhang I Teil II Nr. 1 |
| Verfahren zur Behandlung von Schwachstellen | [Offenlegung und Austausch](schwachstellen-offenlegung.md), Schwachstellenregister | Nr. 5 |
| Nachweis der Herkunft und Signatur der Abbilder | öffentliches Paketverzeichnis, ohne unsere Mitwirkung prüfbar | — |

**Zur Vorlage wird exportiert, nicht Zugriff gegeben.** Die Suite erzeugt den
Konformitätsnachweis und die Kundenfassung als Dokument; die Behörde bekommt
Dateien mit Prüfsummen, keinen Zugang zu einer Installation, in der die Akten
anderer Mandanten liegen.

## Eigene Fristen

| Schritt | Frist |
|---|---|
| Eingang bestätigt, Ansprechpartner genannt | 3 Werktage |
| Vollständige Unterlagen übermittelt | **10 Werktage** |
| Teilantwort mit Zeitplan, falls 10 Werktage nicht reichen | innerhalb derselben 10 Werktage |
| Mitwirkung an einer Maßnahme zur Risikoabwendung | unverzüglich, nach Absprache mit der Behörde |
| Unterrichtung über eine Nicht-Konformität mit Risiko (Art. 13 Abs. 21) | 3 Werktage, siehe [Korrekturmaßnahmen](korrekturmassnahmen.md) |

Die zehn Werktage sind so gewählt, dass sie ohne Vorbereitung einzuhalten
sind — die Unterlagen entstehen im laufenden Betrieb und werden nicht für den
Anlass erstellt. Reicht die Zeit im Einzelfall nicht, geht eine **Teilantwort
mit Zeitplan** heraus. Eine überschrittene Frist ohne Nachricht ist der Fehler,
den dieses Verfahren verhindern soll.

## Ablage der Behördenkommunikation

| Grundsatz | |
|---|---|
| **Wo** | Register der Marktüberwachung im CRA-Modul — ein Vorgang je Anfrage, am Produkt und, soweit zuordenbar, an der Fassung |
| **Was** | Eingang (Datum, Behörde, Aktenzeichen, Gegenstand), Ausgang (Datum, übermittelte Unterlagen samt Prüfsumme), Fristen, Abschluss |
| **Revisionssicher** | jede Handlung trägt Person und Zeitpunkt im fortschreibungssicheren Revisionspfad |
| **Beleg Pflicht** | der Status „beantwortet" ist ohne hinterlegten Beleg nicht speicherbar — serverseitig erzwungen, nicht nur im Formular |
| **Aufbewahrung** | mit dem Archivstand der Fassung, siehe [Aufbewahrung](aufbewahrung.md) |

Der letzte Punkt der vierten Zeile ist der, auf den es ankommt: Würde ein
Statuswechsel ohne Beleg durchgehen, wäre er der bequeme Weg um die
Dokumentation herum.

!!! info "Welche Behörde zuständig ist"
    Die Marktüberwachung nach dem CRA obliegt den Mitgliedstaaten; welche
    nationale Stelle sie in Deutschland wahrnimmt, wird zum Geltungsbeginn am
    11. Dezember 2027 benannt. **Hier steht deshalb kein Behördenname** — eine
    geratene Zuständigkeit in einem öffentlichen Dokument ist ein Umweg im
    Ernstfall.

    Die Zuordnung wird eingetragen, sobald sie amtlich ist; sie steht dann im
    Register der Installation und nicht in diesem Dokument, damit sie nicht in
    einer zweiten Kopie veraltet. Bis dahin gilt: Eine eingehende Anfrage wird
    nach diesem Verfahren behandelt, unabhängig davon, von welcher Stelle sie
    kommt.

    Für die **Meldewege nach Art. 14** ist die Zuständigkeit dagegen geklärt —
    sie folgt aus Art. 14 Abs. 7 und ist in [Meldewege](meldewege-art14.md)
    bestimmt.

## Verhältnis zu den Meldewegen

Dieses Dokument regelt die **Behördenanfrage**. Die eigene **Meldung** an CSIRT
und ENISA ist etwas anderes und steht in [Meldewege](meldewege-art14.md); die
eigene Feststellung einer Nicht-Konformität steht in
[Korrekturmaßnahmen](korrekturmassnahmen.md). Alle drei können denselben
Sachverhalt betreffen und laufen mit eigenen Fristen — eine gemeinsame Frist
wäre für mindestens zwei von ihnen falsch.

## Nachweis, dass dieser Weg trägt

| Prüfung | Turnus | Nachweis |
|---|---|---|
| Soll-Liste oben gegen die Akte gehalten: ist jede Unterlage auffindbar und aktuell? | jährlich und vor jedem Release | Vermerk im Release-Vorgang |
| Trockenlauf: eine erfundene Anfrage im Register anlegen und bis zur Übermittlung durchführen | jährlich | Vorgang im Register, als Übung gekennzeichnet |
| Postanschrift und Kontaktadressen gegengelesen | jährlich | Fassungsangabe unten |

Der Trockenlauf ist hier besonders wenig Aufwand und besonders aussagekräftig:
Er besteht darin, den Konformitätsnachweis einmal zu erzeugen und zu lesen. Wer
das nie getan hat, weiß nicht, ob das Dokument, das er einer Behörde schicken
würde, vollständig ist.

**Fassung 1.0, 2. November 2026.** Fundstellen: Art. 13 Abs. 22 (Vorlage von
Unterlagen und Zusammenarbeit), Abs. 21 (Korrekturmaßnahmen), Art. 14 Abs. 7
(zuständiger CSIRT), Art. 31 und Anhang VII (technische Dokumentation) der
Verordnung (EU) 2024/2847. Gegen die amtliche deutsche Fassung geprüft
(ABl. L vom 20.11.2024).
