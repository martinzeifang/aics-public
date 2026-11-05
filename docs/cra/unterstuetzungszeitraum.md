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

!!! info "Diese Regel steht so in der Verordnung — Art. 13 Abs. 10"
    Sie ist keine Hausregel und kein Entgegenkommen des Herstellers an sich
    selbst. Abs. 10 lässt die Beschränkung auf die zuletzt in Verkehr gebrachte
    Fassung ausdrücklich zu:

    > Hat ein Hersteller nachfolgende wesentlich geänderte Versionen eines
    > Softwareprodukts in den Verkehr gebracht, so kann er die Sicherstellung
    > der Einhaltung der in Anhang I Teil II Nummer 2 festgelegten
    > grundlegenden Cybersicherheitsanforderung auf die Version beschränken, die
    > der Hersteller zuletzt in den Verkehr gebracht hat, sofern die Nutzer der
    > zuvor in den Verkehr gebrachten Version **kostenlos Zugang** zu der
    > zuletzt in den Verkehr gebrachten Version haben und ihnen **keine
    > zusätzlichen Kosten für die Anpassung der Hardware- und
    > Softwareumgebung** entstehen.

    Die beiden Bedingungen sind erfüllt und werden hier zugesagt: Der Wechsel
    auf die neueste Fassung ist innerhalb des Unterstützungszeitraums
    **unentgeltlich**, und die Betriebsvoraussetzungen (Container-Laufzeit,
    PostgreSQL, die gepinnten Fremddienste) ändern sich innerhalb einer
    Hauptversion nicht. Ändern sie sich bei einem Wechsel der Hauptversion, wird
    das in den Freigabehinweisen vorher benannt — sonst trägt die Beschränkung
    oben nicht.

## Tabelle der Fassungen

Art. 13 Abs. 9 verlangt, dass **jede bereitgestellte Sicherheitsaktualisierung**
nach ihrer Bereitstellung mindestens zehn Jahre verfügbar bleibt. Die Tabelle ist
deshalb nicht nur eine Übersicht, sondern der Nachweis, welche Artefakte wie lange
vorzuhalten sind:

| Fassung | In Verkehr gebracht | Sicherheitsaktualisierungen bis | Abbilder verfügbar bis (Abs. 9) | Unterlagen aufzubewahren bis (Abs. 13) |
|---|---|---|---|---|
| 8.0.x | Oktober 2026 | abgelöst durch 8.3.x | Oktober 2036 | Oktober 2036 |
| 8.3.x | Oktober 2026 | bis zur nächsten Nebenversion | Oktober 2036 | Oktober 2036 |
| ⟨nächste⟩ | | | | |

Gepflegt wird sie je Release, zusammen mit dem Archivstand nach
[Aufbewahrung](aufbewahrung.md). Die vierte und fünfte Spalte laufen **ab dem
Inverkehrbringen der jeweiligen Fassung** und nicht ab dem Ende des
Unterstützungszeitraums — eine Fassung von 2030 ist bis 2040 vorzuhalten,
also neun Jahre nach dem Ende der Unterstützung.

## Hinweis bei nicht mehr unterstützten Fassungen

Die älteren Abbilder bleiben im öffentlichen Paketverzeichnis abrufbar. Das ist
nach Art. 13 Abs. 11 zulässig und für einen Betreiber, der zurückrollen muss,
notwendig — es löst aber eine eigene Pflicht aus:

> Die Hersteller können öffentliche Softwarearchive unterhalten, die den Nutzern
> den Zugang zu historischen Versionen erleichtern. In diesen Fällen werden die
> Nutzer klar und in leicht zugänglicher Form über die Risiken im Zusammenhang
> mit der Verwendung nicht unterstützter Software informiert.

Der Hinweis steht in `SECURITY.md`, in den
[CRA-Informationen](https://cyberwoks.de/cra.html) und in den
Softwarebestimmungen: **Der Betrieb einer Fassung, die nicht mehr unterstützt
wird, erfolgt ohne Sicherheitsaktualisierungen und auf eigenes Risiko.**

## Wo die Angabe erscheinen muss

Art. 13 Abs. 19 verlangt die Angabe des Endes **zum Zeitpunkt des Kaufs**, „leicht
zugänglich, klar und verständlich". Das ist mehr als eine Seite im Netz:

| Ort | Stand |
|---|---|
| Produktseite, Anhang II Nr. 7 | erledigt — [CRA-Informationen](https://cyberwoks.de/cra.html) |
| Vertrag / Softwarebestimmungen | erledigt — § 6 der [Softwarebestimmungen](https://cyberwoks.de/software.html) nennt Monat und Jahr |
| Angebot | muss die Angabe tragen — **offen**, gehört in die Angebotsvorlage. Geführt als **C7** in [Abweichungen](abweichungen.md) |
| In der Anwendung | der Unterstützungszeitraum ist im CRA-Modul des Produkts erfasst und wird im Konformitätsnachweis ausgewiesen |

Der offene Punkt ist keine Formsache: Ein Enddatum, das nur auf der Website
steht und nicht im Angebot, erfüllt „zum Zeitpunkt des Kaufs" nicht.

## Mitteilung bei Erreichen des Endes

Art. 13 Abs. 19 hat einen zweiten Satz, der leicht überlesen wird:

> Sofern dies angesichts der Art des Produkts mit digitalen Elementen technisch
> machbar ist, zeigen die Hersteller den Nutzern eine Mitteilung an, um sie
> darüber zu unterrichten, dass das Ende des Unterstützungszeitraums ihres
> Produkts mit digitalen Elementen erreicht ist.

Bei einer Webanwendung mit eigener Oberfläche ist das **technisch machbar** —
die Einschränkung greift hier also nicht, und die Pflicht gilt. Verlangt ist die
Mitteilung bei **Erreichen** des Endes, nicht vorher.

| | |
|---|---|
| **Stand** | nicht umgesetzt — geführt als **C8** in [Abweichungen](abweichungen.md) |
| **Fällig** | vor Oktober 2031, geplant mit der Fassung, die den Zeitraum verlängert oder beendet |
| **Zusätzlich zugesagt** | ein Hinweis **12 und 6 Monate vor** dem Ende, über die Kontaktadressen der Lizenznehmer und in den Freigabehinweisen. Das verlangt die Verordnung nicht; es ist zugesagt, weil ein Betreiber, der am Tag des Ablaufs davon erfährt, keine Zeit zum Handeln hat |

**Fassung 1.1, 2. November 2026.** Fundstellen: Art. 13 Abs. 8 (Festlegung des
Zeitraums), Abs. 9 (Verfügbarkeit der Sicherheitsaktualisierungen), Abs. 10
(Beschränkung auf die zuletzt in Verkehr gebrachte Fassung), Abs. 11 (Hinweis
bei nicht unterstützten Fassungen), Abs. 19 (Angabe zum Zeitpunkt des Kaufs und
Mitteilung bei Erreichen des Endes), Anhang II Nr. 7, Anhang I Teil II Nr. 2
und 8 der Verordnung (EU) 2024/2847. Gegen die amtliche deutsche Fassung
geprüft (ABl. L vom 20.11.2024).
