# Meldewege nach Art. 14

**Dieses Dokument gilt bereits.** Die Meldepflichten des Art. 14 sind nach Art. 71 Abs. 2
seit dem **11. September 2026** anwendbar — anders als der übrige CRA, der erst ab dem
11. Dezember 2027 gilt. Es ist deshalb das einzige Dokument dieses Dossiers, dessen
Inhalt nicht auf einen Termin hinarbeitet, sondern im Ernstfall heute greifen muss.

Beantwortet die Anforderungen **ART14-01** (aktiv ausgenutzte Schwachstellen),
**ART14-02** (schwerwiegende Vorfälle) und **ART14-03** (Zusammenarbeit mit CSIRT und
Behörden) der Eigenbewertung.

## Was gemeldet werden muss

Art. 14 unterscheidet zwei Anlässe. Sie werden hier getrennt geführt, weil die Kriterien
verschieden sind und die Verwechslung im Ernstfall Zeit kostet.

| Anlass | Was | Fundstelle |
|---|---|---|
| **A — aktiv ausgenutzte Schwachstelle** | Eine Schwachstelle *dieses Produkts*, die nachweislich ausgenutzt wird | Art. 14 Abs. 1 und 2 |
| **B — schwerwiegender Vorfall** | Ein Vorfall mit Auswirkung auf die Sicherheit des Produkts | Art. 14 Abs. 3 und 4 |

Beide Wege melden **gleichzeitig an zwei Empfänger**: den CSIRT, der als Koordinator
benannt ist, und die ENISA. Die Gleichzeitigkeit ist nicht Höflichkeit, sondern
Tatbestand — das CRA-Modul der Suite rechnet eine Abweichung von mehr als einer Stunde
zwischen beiden Meldezeitpunkten als offenen Punkt aus.

## Kriterien: wann ist eine Schwachstelle „aktiv ausgenutzt"?

Die Einstufung ist eine Entscheidung, keine Messung. Sie wird getroffen, wenn
**mindestens eines** der folgenden Merkmale vorliegt und sich auf **diese** Software
bezieht:

1. ein Angriffsversuch, der die Schwachstelle gezielt anspricht, ist in Protokollen
   einer Installation belegt;
2. ein Dritter berichtet glaubhaft von einer Ausnutzung — auch ohne eigene Beobachtung,
   sobald die Angabe nachvollziehbar ist;
3. es existiert öffentlich ein funktionierender Ausnutzungscode **und** es gibt Anzeichen
   für seinen Einsatz;
4. eine Behörde oder ein CSIRT teilt die Ausnutzung mit.

**Nicht ausreichend** ist: eine hohe CVSS-Bewertung, ein Eintrag in einem
Schwachstellenkatalog, ein Nachweis der Ausnutzbarkeit im Labor, oder die Ausnutzung
einer Fremdkomponente in einem *anderen* Produkt. Ein CVE in einer mitgelieferten
Bibliothek ist für sich kein Meldeanlass; er wird es, sobald eines der vier Merkmale
oben auf die AI Compliance Suite zutrifft.

Die Abgrenzung ist bewusst eng gefasst. Ein weiter Begriff führt dazu, dass gemeldet
wird, was keine Meldung ist — und das entwertet die Meldungen, auf die es ankommt.

## Kriterien: wann ist ein Vorfall „schwerwiegend"?

Art. 14 Abs. 5 nennt zwei Fälle, und zwar abschließend. Ein Vorfall ist schwerwiegend,
wenn er

* **a)** sich negativ auf die Fähigkeit des Produkts auswirkt — oder auswirken kann —,
  die Verfügbarkeit, Authentizität, Integrität oder Vertraulichkeit sensibler oder
  wichtiger Daten oder Funktionen zu schützen, **oder**
* **b)** zur Einführung oder Ausführung von **bösartigem Code** im Produkt oder im Netz
  und Informationssystem eines Nutzers geführt hat oder dazu führen kann.

Buchstabe b wird leicht übersehen und ist für dieses Produkt der ernstere Fall: Ein
verändertes Container-Abbild erfüllt ihn, auch wenn noch keine Daten abgeflossen sind.
Gemessen am Wortlaut genügt dabei, dass es dazu **führen kann** — die Meldepflicht hängt
nicht am Nachweis eines Schadens.

In der Praxis dieses Produkts heißt das:

* unbefugter Zugriff auf die Nachweisdaten einer Installation;
* ein Abfluss von Mandantendaten, auch über einen KI-Anbieter;
* ein Eingriff in die Lieferkette — ein verändertes Container-Abbild, ein kompromittiertes
  Veröffentlichungskonto, eine unterschobene Abhängigkeit;
* der Verlust der Integrität des Revisionspfads oder der Signaturschlüssel.

Ein Ausfall ohne Sicherheitsbezug ist kein Vorfall im Sinne des Art. 14. Eine
Fehlfunktion, die zu einer falschen Compliance-Aussage führt, ist es ebenfalls nicht —
sie geht den Weg der Marktbeobachtung und, soweit KI-Funktionen betroffen sind, den des
[AI-Act-Dossiers](../ai/aiact-dossier/marktbeobachtung-vorfaelle.md).

## Fristen

| Stufe | Frist | Inhalt |
|---|---|---|
| **Frühwarnung** | 24 Stunden ab Kenntnis | dass es einen Anlass gibt; Mitgliedstaaten, soweit bekannt |
| **Meldung** | 72 Stunden ab Kenntnis | Art und Umfang, verfügbare Korrekturmaßnahmen, Angaben zur Verbreitung |
| **Abschlussbericht** | bei Schwachstellen: 14 Tage nach Verfügbarkeit einer Korrekturmaßnahme · bei Vorfällen: ein Monat nach der Meldung | Beschreibung, Ursache, getroffene Maßnahmen |

„Unverzüglich" wird für dieses Haus so festgelegt: **Kenntnis beginnt, sobald eine Person
mit Zugriff auf dieses Dossier den Anlass erkennt** — nicht, sobald eine Analyse
abgeschlossen ist. Die Frühwarnung ist ausdrücklich keine Analyse; sie wird abgegeben,
auch wenn Ursache und Umfang noch offen sind. Eine Frühwarnung mit Lücken ist zulässig,
eine späte ist es nicht.

Dazu kann der als Koordinator benannte CSIRT nach Art. 14 Abs. 6 einen
**Zwischenbericht** über den Stand verlangen. Er ist keine eigene Frist, sondern eine
Aufforderung, die jederzeit kommen kann — wer seinen Vorgang nur zu den drei Stufen oben
fortschreibt, kann sie nicht beantworten.

Die Monatsfrist wird als **Kalendermonat** gerechnet, nicht als 30 Tage. Die Uhr für den
Abschlussbericht bei Schwachstellen läuft ab der **Verfügbarkeit der Korrekturmaßnahme**,
nicht ab der Erkennung; das ist der Anker, den die Suite in ihrem eigenen Meldewesen
führt.

## Meldeweg

Gemeldet wird über die **Single Reporting Platform** nach Art. 16, die die ENISA
bereitstellt. Der Zugang dorthin ist Voraussetzung und keine Nebensache: Er wird **vor
jedem Release** als Teil des Release-Vorgangs geprüft und nach jeder Änderung an den
Zugangsdaten erneut. Ein Zugang, der im Ernstfall erst beschafft werden muss, kostet die
24-Stunden-Frist.

**Der Zugang besteht seit dem 5. November 2026, und ein Meldeentwurf ließ sich darin
anlegen und speichern.** Der Hersteller ist auf der deutschen
Instanz der Plattform als **Hersteller** registriert — nicht als Bevollmächtigter
(Art. 18, der für einen *anderen* Hersteller handelt) und nicht als CSIRT-Vertreter
(das ist die Behördenseite und damit der Empfänger). Die Rolle ist keine Formalie: Sie
entscheidet, welche Meldewege das Konto überhaupt öffnet.

**Eingereicht wurde dabei nichts, und das ist Absicht.** Das Formular ist erreichbar und
ausfüllbar — belegt durch einen gespeicherten Entwurf. Eine *abgeschickte* Probemeldung
wäre keine Übung, sondern eine Meldung: Sie löst beim CSIRT-Koordinator und bei der
ENISA einen Vorgang aus, und eine Meldung ohne dazugehörigen Sachverhalt ist gegenüber
einer Behörde schlechter als keine. Der Trockenlauf unten läuft deshalb **im eigenen
Register** bis zur Stufe „Meldung" und nicht in das Postfach der Behörde.

Die Zugangsdaten und die Kennungen der Registrierung stehen **nicht in diesem
Dokument** — es ist öffentlich. Sie liegen im Kennwortverwalter und im Betriebsvermerk;
die Einreichungsreferenz einer *einzelnen* Meldung wird dort geführt, wo der Vorgang
geführt wird: im CRA-Modul unter Meldewesen, je Stufe und Empfänger.

**Rückfallweg, falls die Plattform nicht erreichbar ist:** Meldung per E-Mail an den
benannten CSIRT-Koordinator und an die ENISA, mit demselben Inhalt, und Nachreichen über
die Plattform, sobald sie wieder erreichbar ist. Der Rückfall wird im Vorgang
protokolliert — eine Meldung, deren Weg nicht nachvollziehbar ist, ist später nicht
beweisbar.

## Zuständigkeit und Kontaktregister

| Rolle | Wer | Aufgabe |
|---|---|---|
| Meldepflichtiger | der Hersteller (Inhaber, siehe [Governance](governance.md)) | entscheidet über die Einstufung, gibt die Meldung ab, verantwortet die Frist |
| Erstkontakt für Meldungen von außen | zentrale Kontaktstelle `security@cyberwoks.de` | nimmt an, bestätigt, eskaliert |
| Vertretung | siehe [Governance](governance.md) | handelt bei Abwesenheit des Inhabers |

**Welcher CSIRT zuständig ist, folgt aus Art. 14 Abs. 7:** der des Mitgliedstaats, in dem
der Hersteller seine Hauptniederlassung in der Union hat — und als solche gilt der
Mitgliedstaat, in dem die Entscheidungen zur Cybersicherheit der Produkte überwiegend
getroffen werden. Das ist hier **Deutschland**; zuständig ist damit der als Koordinator
benannte CSIRT Deutschlands, und die Meldung geht über dessen Endpunkt der einheitlichen
Meldeplattform ein, gleichzeitig zugänglich für die ENISA. Die Ersatzreihenfolge des
Abs. 7 (Bevollmächtigter, Einführer, Händler, Nutzer) greift nur ohne Hauptniederlassung
in der Union und ist hier ohne Bedeutung.

Die Kontaktdaten des zuständigen CSIRT, der ENISA und der nationalen
Marktüberwachungsbehörde werden **in der Installation** geführt, nicht in diesem
Dokument: im CRA-Modul unter Meldewesen (Empfänger je Stufe mit Mitgliedstaat und
Einreichungsreferenz) und im Register der Marktüberwachung. Dort stehen sie dort, wo sie
im Ernstfall gebraucht werden — in der Akte, die den Vorgang führt —, und sie veralten
nicht in einer zweiten Kopie.

!!! warning "Was hier bewusst nicht steht"
    Dieses Dokument nennt **keine** Namen und Durchwahlen von Ansprechpartnern bei
    Behörden. Es ist öffentlich; solche Angaben veralten, und eine veraltete Durchwahl in
    einem öffentlichen Dokument ist im Ernstfall ein Umweg. Die gepflegten Daten stehen
    in der Installation.

## Zusammenarbeit im Vorgang: was übergeben wird

Art. 14 Abs. 6 erlaubt dem als Koordinator benannten CSIRT, einen
Zwischenbericht zu verlangen; Abs. 8 betrifft die Unterrichtung der Nutzer. In
beiden Fällen und bei jeder Rückfrage einer Behörde geht es um dasselbe: **welche
technischen Angaben wir herausgeben, und zwar vollständig beim ersten Mal.**

Eine Übergabe in drei Nachträgen kostet im Ernstfall mehr Zeit als die
Zusammenstellung. Deshalb diese Liste — sie wird abgearbeitet, nicht aus dem
Gedächtnis beantwortet:

| Nr. | Angabe | Woher |
|---|---|---|
| 1 | Betroffene Fassungen, genau: von/bis, und die zugehörigen Digests | CRA-Modul, Fassungstabelle |
| 2 | Betroffene Komponente — eigenes Modul oder Fremdkomponente samt Fassung | Schwachstellenregister, Stückliste |
| 3 | Schwere mit Vektor (CVSS v3.1 oder v4.0), nicht nur der Punktwert | Schwachstellenregister |
| 4 | Angriffsweg und Voraussetzungen: Netzzugang, Anmeldung, Rolle, Mitwirkung eines Nutzers | Befund |
| 5 | **Anzeichen einer Ausnutzung** — Protokollmuster, Einträge im Revisionspfad, Dateinamen, Netzadressen, Dateiprüfsummen | Protokolle der betroffenen Installation |
| 6 | Zeitlinie: Kenntnis, Analyse, Korrektur verfügbar, Unterrichtung — mit Zeitstempeln in UTC | Vorgang im Meldewesen |
| 7 | Zahl und, soweit bekannt, Mitgliedstaaten der erreichten Installationen | Lizenzbestand |
| 8 | Ergriffene Korrektur- und Risikominderungsmaßnahmen | Vorgang |
| 9 | Was Nutzer selbst tun können — wörtlich so, wie es an sie herausgeht | Hinweisliste |
| 10 | Wie empfindlich wir die Angaben einschätzen (Art. 14 Abs. 2 Buchst. b nennt das ausdrücklich) | Einschätzung des Herstellers |
| 11 | Soweit bekannt: Angaben zu dem Akteur, der ausnutzt (Abs. 2 Buchst. c Ziff. ii) | Analyse |

!!! info "Zu Nr. 5 — was wir liefern können und was nicht"
    Die Anwendung läuft in der Umgebung des Betreibers. Protokolle einer
    Installation liegen **bei ihm**, nicht bei uns; wir haben keinen Fernzugriff.
    Was wir beitragen, ist die Angabe, **wonach** zu suchen ist — welches Muster
    im Zugriffsprotokoll, welcher Eintrag im Revisionspfad, welcher Pfad.

    Angaben aus einer konkreten Installation geben wir nur mit Zustimmung des
    Betreibers heraus; sie sind seine Daten. Das ist kein Vorbehalt gegenüber
    der Behörde, sondern die Rechtslage — und die Angabe, von wem die Daten zu
    erlangen sind, gehört in die Übergabe.

    Strukturierte Austauschformate für Kompromittierungsindikatoren (STIX,
    MISP) werden **nicht** vorgehalten: Dafür bräuchte es eine eigene
    Telemetrie, die es bei selbst betriebener Software nicht gibt und die ein
    neues Datenschutzproblem wäre. Geliefert wird die Beschreibung in Klartext.

## Nachweis, dass der Weg trägt

Eine Meldekette, die nie durchlaufen wurde, ist eine Behauptung. Deshalb:

| Prüfung | Turnus | Nachweis |
|---|---|---|
| Zugang zur Single Reporting Platform erreichbar und Zugangsdaten gültig | vor jedem Release | Vermerk im Release-Vorgang |
| Trockenlauf der Meldekette (Anlass A **und** B) mit einem fiktiven Vorgang im CRA-Modul, bis zur Stufe „Meldung" | jährlich | Vorgang im Meldewesen, als Übung gekennzeichnet |
| Übergabeliste oben an einem erfundenen Fall durchgespielt: sind alle elf Angaben beschaffbar? | jährlich, im selben Termin | Vermerk am Übungsvorgang |
| Kontaktdaten CSIRT/ENISA/Marktüberwachung gegengelesen | jährlich und nach jeder Behördenmitteilung | Änderungsdatum im Register |

Der Trockenlauf wird **im echten Register** geführt und als Übung gekennzeichnet, nicht
in einer Testinstanz: Was im Ernstfall benutzt wird, soll vorher einmal benutzt worden
sein.

### Durchführung

| Datum | Anlass A durchgespielt | Anlass B durchgespielt | Übergabeliste vollständig? | Zugang zur Plattform geprüft | Durchgeführt von |
|---|---|---|---|---|---|
| 5. November 2026 | nein | nein | nicht geprüft | **ja — Registrierung als Hersteller, Meldeentwurf angelegt und gespeichert** | Inhaber |

!!! warning "Das Formular ist erreichbar, der Trockenlauf fehlt"
    Seit dem **5. November 2026** ist der Zugang zur einheitlichen
    Meldeplattform eingerichtet, und ein Meldeentwurf ließ sich darin anlegen und
    speichern. Das ist der Teil, der sich im Ernstfall **nicht nachholen** lässt:
    Die 24-Stunden-Frist läuft ab Kenntnis und nicht ab Einsatzbereitschaft.

    **Offen bleibt der Trockenlauf** — und das ist keine Fußnote. Ein
    gespeicherter Entwurf belegt, dass das Formular erreichbar und ausfüllbar
    ist. Er belegt nicht die Kette, auf die es ankommt: **Einstufung** nach den Kriterien oben →
    **Vorgang** im Meldewesen mit laufender Frist → **gleichzeitige** Einreichung
    an CSIRT-Koordinator und ENISA → **Einreichungsreferenz zurück in den
    Vorgang** → Übergabeliste. Für jede andere Anforderung dieses Dossiers liegt
    der Geltungsbeginn im Dezember 2027; diese gilt **seit dem 11. September
    2026**.

    Geführt als **C4** in [Abweichungen](abweichungen.md), fällig
    31. Dezember 2026. Zusammen mit der offenen Vertretung (**B1**) bleibt das
    das Paar, das vor allem anderen zu schließen ist — **B1 wiegt jetzt
    schwerer**: Hängt der einzige Plattformzugang an einer Person, ist die
    Vertretung kein Formalpunkt, sondern der Unterschied zwischen fristgerechter
    und versäumter Meldung.

## Verhältnis zu anderen Meldepflichten

Eine Meldung nach Art. 14 CRA ersetzt keine andere und wird durch keine ersetzt:

* **Art. 33 DSGVO** — Datenschutzverletzung, 72 Stunden, an die Aufsichtsbehörde. Betrifft
  bei einem Datenabfluss in einer Installation in der Regel den **Betreiber** als
  Verantwortlichen; der Hersteller unterrichtet ihn.
* **NIS-2 / Art. 23** — betrifft den Betreiber, soweit er in den Anwendungsbereich fällt.
* **Art. 73 KI-VO** — gilt für Hochrisiko-KI-Systeme; die Suite ist keines (siehe
  [AI-Act-Dossier](../ai/aiact-dossier/index.md)).

Dass mehrere Pflichten denselben Sachverhalt treffen können, ist der Normalfall. Die
Suite führt sie deshalb in getrennten Registern mit je eigener Fristenuhr — eine
gemeinsame Meldung mit einer Frist wäre für mindestens eine der Pflichten falsch.

**Fassung 1.3, 5. November 2026.** Gegenüber Fassung 1.2 ist der **Zugang zur
einheitlichen Meldeplattform als eingerichtet** eingetragen (Registrierung als
Hersteller auf der deutschen Instanz, 5. November 2026) sowie der Befund, dass sich dort
ein Meldeentwurf anlegen und speichern lässt. **Eingereicht wurde nichts**, und der
Trockenlauf bleibt offen.
Fundstellen: Art. 14 Abs. 1 und 2 (aktiv ausgenutzte
Schwachstelle), Abs. 3 und 4 (schwerwiegender Sicherheitsvorfall), Abs. 5 (Definition
„schwerwiegend"), Abs. 6 (Zwischenbericht), Abs. 7 (zuständiger CSIRT), Abs. 8
(Unterrichtung der Nutzer); Art. 16 (einheitliche Meldeplattform); Art. 71 Abs. 2
(Geltungsbeginn). Gegen die amtliche deutsche Fassung geprüft (ABl. L vom 20.11.2024).
