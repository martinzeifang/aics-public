# Korrekturmaßnahmen bei Nicht-Konformität

Beantwortet die Anforderung **ART13-08** der Eigenbewertung. Fundstelle:
Art. 13 Abs. 21 der Verordnung (EU) 2024/2847.

Der Wortlaut ist kurz und streng:

> Ab dem Inverkehrbringen und während des Unterstützungszeitraums ergreifen die
> Hersteller, denen bekannt ist oder die Grund zu der Annahme haben, dass das
> Produkt mit digitalen Elementen oder die vom Hersteller festgelegten Verfahren
> den grundlegenden Cybersicherheitsanforderungen in Anhang I nicht genügen,
> unverzüglich die erforderlichen Korrekturmaßnahmen, um die Konformität dieses
> Produkts mit digitalen Elementen oder der Prozesse des Herstellers
> herzustellen oder um gegebenenfalls das Produkt vom Markt zu nehmen oder
> zurückzurufen.

Drei Dinge daran bestimmen dieses Dokument:

1. **„oder Grund zu der Annahme haben"** — die Pflicht beginnt vor dem Beweis.
   Ein begründeter Verdacht löst sie aus, nicht erst ein belegter Mangel.
2. **„oder die vom Hersteller festgelegten Verfahren"** — nicht nur das Produkt.
   Ein Verfahren, das auf dem Papier steht und nicht gelebt wird, ist selbst
   eine Nicht-Konformität.
3. **„vom Markt nehmen oder zurückrufen"** — die Verordnung nennt das Äußerste
   ausdrücklich. Ein Verfahren, das diesen Schritt nicht vorsieht, hält den
   Absatz nicht ein.

## Abgrenzung: was hier hineingehört und was nicht

Dies ist **nicht** der Weg für eine Schwachstelle. Eine Schwachstelle ist der
erwartete Fall und wird nach
[Offenlegung und Austausch](schwachstellen-offenlegung.md) behandelt; der
Umstand, dass sie gefunden wurde, belegt, dass die Verfahren wirken.

Dieser Weg greift, wenn **die Konformität selbst** in Frage steht:

| Anlass | Beispiel aus diesem Produkt |
|---|---|
| Eine Eigenschaft aus Anhang I Teil I fehlt oder wirkt nicht | eine Prüfung, die gesetzt war und nie gelaufen ist — die Fehlerklasse, die dieses Projekt mehrfach getroffen hat (ein Zustand, den niemand liest; ein Budget, das nicht ankommt) |
| Ein festgelegtes Verfahren wird nicht durchgeführt | ein Abgleich, der laut Zeitplan läuft und seit Monaten nicht gelaufen ist |
| Die technische Dokumentation gibt etwas Unrichtiges an | ein Unterstützungszeitraum, der sechs Monate zu kurz ausgewiesen war |
| Die EU-Konformitätserklärung bezeichnet nicht das Ausgelieferte | die Erklärung nennt eine Fassung, die nicht die in Verkehr gebrachte ist |
| Eine Zusage wird nicht eingelöst | zugesagte getrennte Kanäle für Sicherheits- und Funktionsaktualisierungen, die zusammengelegt wurden |

**Die Unterscheidung ist nicht akademisch.** Eine Schwachstelle wird behoben und
öffentlich gemacht. Eine Nicht-Konformität verlangt zusätzlich die Frage, ob die
Erklärung noch trägt und ob eine Behörde zu unterrichten ist.

## Zuständigkeit

| Rolle | Wer |
|---|---|
| Feststellung und Einstufung | Martin Zeifang, Inhaber (siehe [Governance](governance.md)) |
| Entscheidung über Einstellung der Bereitstellung | derselbe — sie ist nicht delegierbar |
| Durchführung der Unterrichtung | zentrale Anlaufstelle `security@cyberwoks.de` |
| Vertretung bei Abwesenheit | siehe [Governance](governance.md) — **offen**, als Risiko geführt |

Es gibt keine Eskalationsstufe über dem Inhaber. Was es gibt, ist die Pflicht,
die Feststellung **schriftlich mit Datum** festzuhalten, bevor über sie
entschieden wird — sonst ist später nicht unterscheidbar, ob spät entschieden
oder spät erkannt wurde.

## Der Ablauf

### Stufe 0 — Feststellung (sofort)

Ein Vorgang wird angelegt, sobald der Verdacht benannt werden kann. Er trägt:
Datum und Uhrzeit der Kenntnis, wer sie hatte, woraus sie folgt, welche
Anforderung des Anhangs I betroffen ist, und welche Fassungen in Verkehr sind.

**Der Vorgang wird angelegt, bevor geprüft wird.** Wer erst prüft und dann
anlegt, verliert den Zeitpunkt der Kenntnis — und an ihm hängen alle Fristen.

### Stufe 1 — Einstufung (innerhalb von 2 Werktagen)

Zwei Fragen, in dieser Reihenfolge:

**Besteht ein Cybersicherheitsrisiko für die Nutzer?**

| Antwort | Folge |
|---|---|
| ja, erheblich | weiter mit Stufe 2 **und** Stufe 4 (Behörde) parallel |
| ja, begrenzt | weiter mit Stufe 2 |
| nein — die Nicht-Konformität ist formal (eine Angabe ist unrichtig, ohne dass daraus ein Risiko folgt) | Stufe 2 mit der Frist der nächsten planmäßigen Fassung; Stufe 4 entfällt, die Begründung wird festgehalten |

**Ist die Schwachstelle aktiv ausgenutzt oder liegt ein schwerwiegender Vorfall
vor?** Dann greift **zusätzlich** [Art. 14](meldewege-art14.md) mit der
24-Stunden-Frist. Die Meldung nach Art. 14 und die Korrekturmaßnahme nach
Art. 13 Abs. 21 sind zwei Pflichten über denselben Sachverhalt; keine ersetzt
die andere.

### Stufe 2 — Konformität herstellen

In dieser Reihenfolge, und die Reihenfolge ist der Inhalt:

1. **Korrigierte Fassung bereitstellen.** Ist der Mangel ein Verfahren und kein
   Code, wird das Verfahren geändert und die Änderung in diesem Dossier
   festgehalten — mit Fassungsangabe, damit die Änderung nachweisbar ist.
2. **Betreiber unterrichten** — über die Hinweisliste und, bei erheblichem
   Risiko, zusätzlich unmittelbar an die bei der Anlaufstelle bekannten
   Adressen. Die Unterrichtung nennt: was nicht stimmt, was zu tun ist, bis
   wann, und was passiert, wenn nichts getan wird.
3. **Technische Dokumentation nachziehen.** Betrifft der Mangel eine Angabe in
   Anhang VII oder in der EU-Konformitätserklärung, wird sie berichtigt und die
   Erklärung neu ausgestellt. Eine berichtigte Angabe ohne neue Erklärung lässt
   die alte Erklärung als unrichtige Aussage im Verkehr.

### Stufe 3 — Bereitstellung einstellen (wenn Stufe 2 nicht genügt)

Greift, wenn eine Gefährdung besteht und keine korrigierte Fassung in
angemessener Zeit bereitsteht.

Bei Software heißt „vom Markt nehmen" konkret:

| Maßnahme | Machbar? |
|---|---|
| Die betroffenen Abbilder im öffentlichen Paketverzeichnis als zurückgezogen kennzeichnen und von den beweglichen Zeigern (`latest`, Nebenfassung) abhängen | ja, sofort |
| Die Fassung in der Hinweisliste und in den Freigabehinweisen als „nicht betreiben" kennzeichnen | ja, sofort |
| Betreiber unmittelbar zum Wechsel auffordern | ja, über die bekannten Adressen |
| Das Abbild aus dem Paketverzeichnis **löschen** | ja — aber nur nach Abwägung, s. u. |
| Die Fassung aus der Installation eines Betreibers **entfernen** | **nein** |

!!! warning "Was wir nicht zusagen — und warum das hier steht"
    Ein Entfernen aus der Installation des Betreibers kann der Hersteller nicht
    bewirken. Die Suite wird selbst betrieben, in der Regel hinter der Firewall
    des Betreibers; es gibt keinen Fernzugriff und soll keinen geben. Ein
    „Rückruf" im Sinne der Rücknahme beim Nutzer ist hier technisch
    unmöglich — und eine Zusage, die man nicht halten kann, ist in einer
    Nachweisakte schlimmer als eine benannte Grenze.

    Das Löschen des Abbilds ist **nicht** immer die sicherere Wahl: Es nimmt
    einem Betreiber, der gerade zurückrollen muss, auch die funktionierende
    Vorfassung. Abgewogen und festgehalten wird je Fall; der Regelfall ist
    Kennzeichnen und Abhängen, nicht Löschen.

### Stufe 4 — Marktüberwachungsbehörde unterrichten

**Wann:** sobald die Nicht-Konformität ein Cybersicherheitsrisiko begründet.
Ohne Risiko gibt es keine Unterrichtungspflicht aus Art. 13 Abs. 21 — die
Pflicht aus Art. 13 Abs. 22, auf begründetes Verlangen Unterlagen vorzulegen,
bleibt davon unberührt.

**Was in die Unterrichtung gehört:** die betroffene Fassung, die Anforderung
des Anhangs I, die nicht erfüllt ist, das Risiko für die Nutzer, die ergriffene
Maßnahme samt Datum, und die Zahl der erreichbaren Betreiber.

Weg und Ansprechstelle: [Marktüberwachung](marktueberwachung.md).

### Stufe 5 — Abschluss und Nachschau

Der Vorgang wird erst geschlossen, wenn vier Fragen beantwortet sind:

1. Ist die Konformität hergestellt — nachweisbar, nicht vermutlich?
2. Sind alle Unterrichteten unterrichtet?
3. **Woran hat es gelegen, dass es nicht auffiel?** Eine Nicht-Konformität, die
   erst nach dem Inverkehrbringen bemerkt wird, ist immer auch eine Lücke in der
   Prüfung davor.
4. Welche Prüfung fängt diesen Fall künftig ab? Sie wird eingerichtet, bevor der
   Vorgang geschlossen wird.

Frage 3 und 4 sind der Teil, der verhindert, dass dasselbe zweimal passiert. In
diesem Projekt gibt es dafür eine belegte Praxis: Jede dieser Lücken bekommt
einen Prüfer, und der Prüfer wird **rot gesehen**, bevor er geglaubt wird.

## Fristen

| Schritt | Frist |
|---|---|
| Vorgang angelegt | sofort bei Kenntnis |
| Einstufung | 2 Werktage |
| Unterrichtung bei erheblichem Risiko | unverzüglich, spätestens 3 Werktage |
| Unterrichtung der Behörde bei erheblichem Risiko | unverzüglich, spätestens 3 Werktage |
| Korrigierte Fassung bei erheblichem Risiko | 7 Tage (wie die Frist für kritische Schwachstellen) |
| Korrigierte Fassung bei begrenztem Risiko | 30 Tage |
| Korrigierte Angabe bei formaler Nicht-Konformität | mit der nächsten planmäßigen Fassung |
| Abschluss mit Nachschau | 30 Tage nach Herstellung der Konformität |

**Die Verordnung beziffert nur „unverzüglich".** Alle Zahlen hier sind eigene
Festlegungen; sie stehen so, weil „unverzüglich" ohne Maß im Nachhinein nicht
überprüfbar ist. Sie sind an den Fristen für Schwachstellen ausgerichtet, damit
nicht zwei Uhren mit verschiedenem Takt für denselben Sachverhalt laufen.

## Wo der Vorgang geführt wird

Im CRA-Modul der Installation, nicht in diesem Dokument: dort hängt er am
Produkt und an der Fassung, trägt Person und Zeitpunkt im Revisionspfad, und er
erscheint im Vorgangsbericht des Releases. Ein Vorgang in einer Textdatei
daneben ist später nicht zuzuordnen.

## Nachweis, dass dieser Weg trägt

| Prüfung | Turnus | Nachweis |
|---|---|---|
| Durchsicht: ist seit dem letzten Release etwas bekannt geworden, das diesen Weg auslöst? | je Release | Vermerk im Release-Vorgang |
| Trockenlauf mit einem erfundenen Fall bis Stufe 2 | jährlich, zusammen mit dem Trockenlauf nach [Art. 14](meldewege-art14.md) | Vorgang im CRA-Modul, als Übung gekennzeichnet |
| Dieses Dokument gegen den Verordnungstext gegengelesen | jährlich | Fassungsangabe unten |

Der gemeinsame Termin mit dem Art.-14-Trockenlauf ist Absicht: Im Ernstfall
treffen beide Wege oft zusammen, und wer sie getrennt übt, übt die
Reihenfolge nicht.

**Fassung 1.0, 2. November 2026.** Fundstellen: Art. 13 Abs. 21 (Korrektur\-
maßnahmen), Abs. 22 (Vorlage von Unterlagen und Zusammenarbeit), Art. 14
(Meldepflichten), Anhang I Teil I und Teil II der Verordnung (EU) 2024/2847.
Gegen die amtliche deutsche Fassung geprüft (ABl. L vom 20.11.2024).
