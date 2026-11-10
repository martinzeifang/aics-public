# Governance und Verantwortlichkeiten

Beantwortet die Anforderung **IMPL-01** der Eigenbewertung: ausdrücklich benannter
Verantwortlicher, Bekenntnis der Leitung, zugewiesene Mittel und regelmäßige
Berichterstattung. Fundstelle: Art. 13 Abs. 1 in Verbindung mit Erwägungsgrund 34.

!!! info "Ein Haus mit einer Person — und warum das hier so dasteht"
    Die AI Compliance Suite wird von einem Einzelunternehmen hergestellt. Die üblichen
    Governance-Bausteine — ein Gremium, eine Berichtslinie, getrennte Rollen — gibt es
    hier nicht, und sie zu behaupten wäre eine Falschangabe in einer Nachweisakte.

    Was bleibt, ist nicht weniger wert: Es muss **benannt** sein, wer entscheidet, es
    muss **festgehalten** sein, wann entschieden wurde, und es muss einen **Ersatzweg**
    geben, wenn diese Person nicht erreichbar ist. Genau das steht unten. Eine
    Organisation mit mehreren Personen würde dieses Dokument erweitern, nicht ersetzen.

## Benannte Verantwortung

| Rolle | Inhaber | Aufgabe |
|---|---|---|
| **Verantwortlicher für die Cybersicherheit des Produkts** (CRA-Verantwortlicher) | Martin Zeifang, Inhaber | Erfüllung der Pflichten aus Art. 13 und 14; Freigabe der EU-Konformitätserklärung; Einstufung und Abgabe von Meldungen; Annahme des Restrisikos |
| Zentrale Kontaktstelle für Schwachstellen | `security@cyberwoks.de` | Annahme, Eingangsbestätigung, Eskalation an den Verantwortlichen |
| Vertretung bei Abwesenheit | *noch zu benennen* | Annahme von Meldungen und Abgabe der Frühwarnung nach Art. 14 |

!!! warning "Die Vertretung ist offen — und das ist der härteste Punkt dieses Dokuments"
    Die 24-Stunden-Frist der Frühwarnung nach Art. 14 Abs. 1 kennt keinen Urlaub. Solange
    keine Vertretung benannt ist, hängt die Einhaltung an der Erreichbarkeit einer
    einzigen Person. Das ist ein bekanntes Risiko, kein Versäumnis aus Unkenntnis; es ist
    im Risikoregister des Produkts geführt und gehört zu den Punkten, die vor dem
    Geltungsbeginn am 11. Dezember 2027 zu schließen sind.

    Mögliche Formen: eine zweite Person mit Zugang zur Kontaktstelle und zur
    Meldeplattform, oder eine vertragliche Vertretung. Eine Abwesenheitsnotiz ist keine
    Vertretung.

## Bekenntnis der Leitung

Der Inhaber erklärt für die AI Compliance Suite:

1. **Die Anforderungen des Anhangs I gehen vor.** Ein Release wird nicht ausgeliefert,
   weil ein Termin drängt. Die Entscheidung darüber trifft der gerechnete Release-Check
   im CRA-Modul: Eine rote Ampel ist eine Nicht-Konformität und kein Hinweis, und sie
   wird nicht durch eine Bestätigung übergangen.
2. **Sicherheitsaktualisierungen sind unentgeltlich** und werden getrennt von
   Funktionsaktualisierungen bereitgestellt, soweit es technisch machbar ist
   (Anhang I Teil II Nr. 2 und 8).
3. **Was nicht belegt ist, gilt als nicht erfüllt.** Die Bewertung einer Anforderung
   stützt sich auf Nachweise in der Akte, nicht auf die Einschätzung, dass etwas
   umgesetzt sei. Offene Punkte bleiben sichtbar, auch wenn sie unbequem sind.
4. **Ein KI-Entwurf ist kein Nachweis.** Maschinell erzeugte Bewertungen bleiben als
   ungeprüfter Entwurf gekennzeichnet, bis eine Person sie geprüft hat, und gehen
   ungeprüft nicht in herausgehende Dokumente ein.

## Mittel

Was zugesagt ist, in nachprüfbarer Form — eine Zusage ohne Maß ist keine:

| Mittel | Zusage |
|---|---|
| Zeit für Sicherheitsarbeit | mindestens ein Arbeitstag je Woche, vorrangig gegenüber Funktionsarbeit |
| Behebung kritischer Schwachstellen | hat Vorrang vor jeder laufenden Arbeit (siehe [Offenlegung](schwachstellen-offenlegung.md) für die Fristen) |
| Werkzeuge | die automatisierten Prüfungen der Entwicklungsstrecke werden betrieben und nicht abgeschaltet, auch wenn sie einen Release blockieren |
| Externe Prüfung | mindestens ein Penetrationstest in 18 Monaten, als Nachweis nach Anhang I Teil II Nr. 3 |
| Fortbildung | siehe [Schulung und Awareness](../security/awareness.md) |

## Berichterstattung

In einem Einpersonenunternehmen gibt es niemanden, dem berichtet wird. Was es gibt, ist
die Pflicht, sich selbst Rechenschaft zu geben — und zwar **schriftlich und mit Datum**,
weil eine Erkenntnis ohne Vermerk nach vier Wochen nicht mehr überprüfbar ist.

| Was | Turnus | Wo |
|---|---|---|
| Stand der Konformität: gerechneter Release-Check, offene Punkte, Reifegrad | je Release | Release-Vorgang im CRA-Modul, Vorgangsbericht |
| Durchsicht der offenen Punkte und Entscheidung über Priorität | vierteljährlich | Vermerk am Produkt-Datensatz |
| Überprüfung der Produktklasse und des Bewertungswegs | jährlich und bei jeder wesentlichen Änderung | [Produktklassifizierung](produktklassifizierung.md) |
| Überprüfung dieses Dossiers | jährlich und bei Anlass | Fassungsangabe je Dokument |

Die vierteljährliche Durchsicht ist der einzige Termin, der nicht an einem Release hängt.
Sie ist bewusst so angelegt: Ohne sie werden nur die Punkte angesehen, die ein Release
blockieren — und die wichtigsten offenen Punkte blockieren oft nichts.

## Zwei Pflichten, die nur im Ereignisfall greifen

Sie stehen hier, weil sie sonst nirgends stehen: Der Anforderungskatalog des
CRA-Moduls führt sie (noch) nicht als Anforderung, und ein Prozess, der erst im
Ernstfall erfunden wird, ist keiner.

**Korrekturmaßnahmen bei Nicht-Konformität (Art. 13 Abs. 21).** Wird nach dem
Inverkehrbringen bekannt — oder besteht Grund zur Annahme —, dass das Produkt
oder die Verfahren zur Schwachstellenbehandlung den Anforderungen des
Anhangs I nicht entsprechen, werden unverzüglich Korrekturmaßnahmen ergriffen.
Für dieses Produkt heißt das in dieser Reihenfolge: korrigierte Fassung
bereitstellen · Betreiber unterrichten (siehe
[Offenlegung](schwachstellen-offenlegung.md)) · bei Gefährdung die Bereitstellung
der betroffenen Fassung einstellen. Ein „Rückruf" im Sinne der Rücknahme beim
Nutzer ist bei Software die **Aufforderung zum Wechsel der Fassung** samt
Einstellung der alten; ein Entfernen aus der Installation des Betreibers kann
der Hersteller nicht bewirken und verspricht es deshalb nicht.

**Einstellung der Betriebstätigkeit (Art. 13 Abs. 23).** Wer die Tätigkeit
einstellt und die Verordnung deshalb nicht mehr erfüllen kann, unterrichtet
**vor** dem Wirksamwerden die Marktüberwachungsbehörden und — mit allen
verfügbaren Mitteln — die Nutzer. Für ein Einzelunternehmen ist das der
unbequemste Satz dieses Dossiers und der, der am ehesten gebraucht wird:
Zugesagt wird eine Vorlauffrist von **drei Monaten** gegenüber den Betreibern,
die Benachrichtigung über die bei der Kontaktstelle eingetragenen Adressen und
ein Hinweis auf dieser Seite. Was danach mit dem Quellstand geschieht, ist
keine Pflicht der Verordnung — die Abwägung (Übergabe, Veröffentlichung,
Einstellung) wird dann getroffen und hier festgehalten.

## Verhältnis zur Rollentrennung im Produkt

Die Suite selbst erzwingt für ihre Nutzer ein Vier-Augen-Prinzip: Wer einen
Konformitätsnachweis einreicht, kann ihn nicht freigeben; wer einen DSGVO-Jahresbericht
freigibt, kann ihn nicht signieren. Verglichen wird die Benutzer-Kennung, nicht der
Anzeigename.

**Für das eigene Produkt lässt sich diese Trennung mit einer Person nicht herstellen.**
Das steht hier, weil es sonst jemandem auffällt, der die Werbeaussage neben die Praxis
legt: Die Trennung ist eine Funktion für Kunden mit mehreren Beteiligten. Im eigenen Haus
wird sie durch die Nachvollziehbarkeit ersetzt — jede Freigabe trägt Person und Zeitpunkt
im Revisionspfad, und der Pfad ist fortschreibungssicher. Das ist weniger als eine
Trennung und mehr als nichts, und es ist der Grund, warum die offene Vertretung oben als
Risiko geführt wird.

**Fassung 1.0, 2. November 2026.** Fundstellen: Art. 13 Abs. 1, Erwägungsgrund 34 der
Verordnung (EU) 2024/2847.
