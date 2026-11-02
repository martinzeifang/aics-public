# Unterstützungszeitraum

Beantwortet die Anforderung **ART13-03** der Eigenbewertung. Fundstellen: Art. 13
Abs. 8 (Dauer), Art. 13 Abs. 19 (Angabe zum Zeitpunkt des Kaufs), Anhang II Nr. 7
(Angabe gegenüber dem Nutzer).

## Die Angabe

| | |
|---|---|
| **Beginn** | Oktober 2026 |
| **Ende** | **Oktober 2031** |
| Dauer | fünf Jahre |

Öffentlich genannt unter [CRA-Informationen Nr. 7](https://cyberwoks.de/cra.html) mit
Monat und Jahr, so wie Art. 13 Abs. 19 es verlangt.

## Herleitung

Art. 13 Abs. 8 verlangt, den Unterstützungszeitraum danach zu bemessen, wie lange das
Produkt **voraussichtlich genutzt** wird, und setzt dabei eine Untergrenze von fünf
Jahren — kürzer ist nur zulässig, wenn die erwartete Nutzungsdauer kürzer ist. Die
Herleitung für dieses Produkt:

| Erwägung | Befund |
|---|---|
| Art des Produkts | Compliance-Software, die Nachweisakten über Jahre führt. Solche Software wird nicht saisonal ausgetauscht. |
| Erwartete Nutzungsdauer beim Kunden | Der CRA selbst gilt ab 11. Dezember 2027 und verlangt Aufbewahrung über zehn Jahre; ein Kunde, der das Werkzeug dafür einsetzt, nutzt es über mehrere Jahre. **Die erwartete Nutzungsdauer ist damit länger als fünf Jahre.** |
| Folge | Fünf Jahre sind hier **keine** Ableitung aus der erwarteten Nutzungsdauer, sondern die gesetzliche Untergrenze. Eine Verlängerung ist absehbar nötig und wird vor dem Ablauf entschieden. |
| Technische Tragfähigkeit | Die Auslieferung erfolgt als Container-Abbild; Sicherheitsaktualisierungen erfordern den Austausch des Abbilds, nicht eine Migration beim Kunden. Fünf Jahre sind damit mit den vorhandenen Mitteln leistbar. |

!!! info "Die Untergrenze ist nicht das Ziel"
    Die Angabe „fünf Jahre" ist eine Zusage, die eingehalten werden muss, und keine
    Schätzung. Sie wurde deshalb auf die Untergrenze gesetzt — ein Einzelunternehmen, das
    zehn Jahre zusagt, sagt etwas zu, das es über diesen Zeitraum tatsächlich leisten
    muss. Eine Verlängerung ist jederzeit möglich und wird dann öffentlich nachgetragen;
    eine Verkürzung ist es nicht.

## Wie der Beginn bestimmt ist

Der Unterstützungszeitraum läuft ab dem **Inverkehrbringen**, nicht ab dem Beginn der
Entwicklung und nicht ab der Anlage des Quellverzeichnisses. Als Inverkehrbringen gilt
hier die erste entgeltliche Bereitstellung an einen Kunden; in der Akte des Produkts
steht dafür der **23. Oktober 2026**, öffentlich genannt wird monatsgenau *Oktober 2026*.

!!! warning "Ein Fehler, der genau hier entstand"
    Die Akte wies das Ende des Unterstützungszeitraums zunächst mit **April 2031** aus.
    Der Wert war automatisch aus dem Anlagedatum des Quellverzeichnisses abgeleitet
    (29. April 2026) und wurde beim Eintragen des Inverkehrbringens nicht nachgezogen.
    Er lag damit **sechs Monate zu früh** — und das ist die Zahl, die in Angebote,
    Verträge und auf die Produktseite geht.

    Die Prüfung in der Anwendung hat das nicht bemerkt, weil sie die *Anzahl der Jahre*
    prüft (fünf, also zulässig) und nicht, ob Endtermin und Inverkehrbringen zueinander
    passen. Die Lücke ist als Befund erfasst; bis sie geschlossen ist, gehört der
    Abgleich „Inverkehrbringen + Dauer = Enddatum" in die Durchsicht vor jedem Release.

## Was die Unterstützung umfasst

| Leistung | Zusage |
|---|---|
| Behebung von Schwachstellen | gemeldete und selbst festgestellte, nach den Fristen in [Offenlegung und Austausch](schwachstellen-offenlegung.md) |
| Bereitstellung | als neues Container-Abbild über das öffentliche Paketverzeichnis |
| Trennung der Kanäle | Sicherheitsaktualisierungen getrennt von Funktionsaktualisierungen, soweit technisch machbar (Anhang I Teil II Nr. 2 und 8) |
| Entgelt | Sicherheitsaktualisierungen sind **unentgeltlich** |
| Hinweise | Veröffentlichung zu behobenen Schwachstellen unter [Sicherheitshinweise](https://cyberwoks.de/hinweise.html) |
| Unterstützung beim Einspielen | per E-Mail an `kontakt@cyberwoks.de`, Rückmeldung innerhalb von fünf Werktagen |

Das **Einspielen selbst** nimmt der Betreiber vor. Es gibt keine automatische Installation
von Sicherheitsaktualisierungen — eine bewusste Entscheidung: Die Anwendung führt
Nachweisakten, und ein unangekündigter Versionswechsel wäre dort nicht vertretbar.
Dadurch trägt der Betreiber die Verantwortung für die Aktualität seiner Installation; der
Umstand ist als Risiko in den
[CRA-Informationen Nr. 5](https://cyberwoks.de/cra.html) benannt.

## Zusagen je Fassung (End-of-Life-Politik)

Der Unterstützungszeitraum gilt für das **Produkt**, nicht für die einzelne Fassung. Für
die Fassungen gilt:

| Regel | |
|---|---|
| Sicherheitsaktualisierungen gibt es für die **jeweils aktuelle Nebenversion** | Beispiel: Erscheint 8.4.x, erhält 8.3.x keine weiteren Sicherheitsaktualisierungen. |
| Der Weg zur Aktualität ist der Austausch des Abbilds | Es gibt keine Rückportierung in ältere Nebenversionen. |
| Eine Hauptversion wird nicht ohne Vorlauf abgelöst | Vor einem Wechsel der Hauptversion wird in den Freigabehinweisen auf den Umstieg hingewiesen. |
| Ein Rücksprung auf eine ältere Fassung ist nicht vorgesehen | Das Schema der Datenbank wird beim Start fortgeschrieben, aber nicht zurückgebaut. Die Anwendung verweigert einen solchen Rücksprung mit Begründung, statt ihn stillschweigend zuzulassen. |

**Was das für den Kunden heißt:** Wer eine Sicherheitsaktualisierung einspielen will, muss
auf der aktuellen Nebenversion sein. Diese Regel ist streng, aber ehrlich — die
Alternative wäre die Zusage von Rückportierungen, die ein Einzelunternehmen über fünf
Jahre nicht halten kann.

## Wo die Angabe erscheinen muss

Art. 13 Abs. 19 verlangt die Angabe des Endes **zum Zeitpunkt des Kaufs**, „leicht
zugänglich, klar und verständlich". Das ist mehr als eine Seite im Netz:

| Ort | Stand |
|---|---|
| Produktseite, Anhang II Nr. 7 | erledigt — [CRA-Informationen](https://cyberwoks.de/cra.html) |
| Angebot | muss die Angabe tragen — **offen**, gehört in die Angebotsvorlage |
| Vertrag / Softwarebestimmungen | muss die Angabe tragen — **offen** |
| In der Anwendung | der Unterstützungszeitraum ist im CRA-Modul des Produkts erfasst und wird im Konformitätsnachweis ausgewiesen |

Die beiden offenen Punkte sind keine Formsache: Ein Enddatum, das nur auf der Website
steht und nicht im Angebot, erfüllt „zum Zeitpunkt des Kaufs" nicht.

**Fassung 1.0, 2. November 2026.** Fundstellen: Art. 13 Abs. 8 und 19, Anhang II Nr. 7,
Anhang I Teil II Nr. 2 und 8 der Verordnung (EU) 2024/2847.
