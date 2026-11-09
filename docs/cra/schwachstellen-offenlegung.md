# Offenlegung und Austausch zu Schwachstellen

Beantwortet die Anforderungen **AI2-06** (Veröffentlichung von Hinweisen zu behobenen
Schwachstellen) und **AI2-08** (Informationsaustausch zu Schwachstellen in
Fremdkomponenten). Fundstellen: Anhang I Teil II Nr. 4 und Nr. 6, Art. 13 Abs. 6.

Das **Konzept für die koordinierte Offenlegung** — wie eine Meldung von außen
entgegengenommen und behandelt wird — ist öffentlich unter
[Sicherheit und Meldung von Schwachstellen](https://cyberwoks.de/sicherheit.html).
Dieses Dokument regelt die Gegenrichtung: was **wir** veröffentlichen und wen **wir**
unterrichten.

## Verpflichtung zur Veröffentlichung

Für jede Schwachstelle im eigenen Programmcode der AI Compliance Suite, für die eine
Korrekturmaßnahme bereitgestellt wird, wird ein Hinweis veröffentlicht. Das ist eine
Verpflichtung und keine Möglichkeit — Anhang I Teil II Nr. 4 sieht sie vor, und sie wird
hier ausdrücklich übernommen.

| | |
|---|---|
| **Wo** | [Sicherheitshinweise](https://cyberwoks.de/hinweise.html) als maßgebliche Liste; zusätzlich als Security Advisory des öffentlichen Quellverzeichnisses und in den Freigabehinweisen der Fassung |
| **Wann** | mit der Bereitstellung der korrigierten Fassung, nicht danach |
| **Was** | Beschreibung, betroffene Fassungen, behoben in, Auswirkung und Schwere, Behebungshinweis, Kennung (CVE oder GHSA), soweit vergeben |
| **Form** | strukturiert, maschinenlesbar abrufbar über die Advisory-Schnittstelle des Quellverzeichnisses |

**Die Kennung wird beantragt, nicht abgewartet.** Für eine Schwachstelle im eigenen Code,
die mehr als eine Installation betrifft, wird über das Quellverzeichnis eine
GHSA-Kennung erzeugt und, soweit die Voraussetzungen vorliegen, eine CVE-Kennung
beantragt. Ein Hinweis ohne Kennung ist für Kunden, die ihre eigenen Register führen,
schwer zuzuordnen — und genau diese Kunden sind die Zielgruppe dieses Produkts.

### Wann die Veröffentlichung aufgeschoben wird

Anhang I Teil II Nr. 4 lässt zu, die Veröffentlichung aufzuschieben, wenn das
Sicherheitsrisiko den Nutzen überwiegt. Davon wird Gebrauch gemacht, wenn

* die Korrekturmaßnahme noch nicht in allen bekannten Installationen eingespielt sein
  kann und die Angaben die Ausnutzung erheblich erleichtern würden, **oder**
* eine koordinierte Veröffentlichung mit einem Dritten vereinbart ist (etwa dem
  Hersteller einer Fremdkomponente oder einem CSIRT).

Der Aufschub wird im Schwachstellenregister des Produkts mit **Grund und Datum**
festgehalten und endet mit einem benannten Termin. Ein Aufschub ohne Termin ist eine
Nichtveröffentlichung.

## Was nicht veröffentlicht wird

| Fall | Behandlung |
|---|---|
| Schwachstelle in einer **Fremdkomponente**, vom Hersteller bereits veröffentlicht | **Kein eigener Hinweis.** Genannt wird die aktualisierte Komponente in den Freigabehinweisen, mit Verweis auf den Hinweis des Herstellers. |
| Befund aus eigenen Prüfungen, der keine Schwachstelle im ausgelieferten Produkt ist (Härtungsempfehlung, Befund an der Betriebsumgebung) | kein Hinweis; behandelt als Verbesserung |
| Befund, der nur eine nicht ausgelieferte Entwicklungsfassung betrifft | kein Hinweis; vor der Auslieferung behoben |

**Warum kein zweiter Hinweis zu einer Fremdkomponente:** Es wäre dieselbe Angabe in einer
zweiten, womöglich abweichenden Fassung. Wer zwei Beschreibungen derselben Schwachstelle
in Umlauf bringt, erzeugt die Frage, welche gilt — und diese Frage stellt sich im
ungünstigsten Moment. Benannt wird deshalb die Komponente samt Fassung; die Beschreibung
bleibt beim Hersteller.

## Fristen für die Behebung

| Schwere | Korrekturmaßnahme bereitgestellt innerhalb von |
|---|---|
| kritisch | 7 Tagen |
| hoch | 30 Tagen |
| mittel | 90 Tagen |
| niedrig | mit der nächsten Fassung |

Gerechnet ab der **Bestätigung** der Schwachstelle, nicht ab der Meldung — die Prüfung,
ob ein Bericht zutrifft, ist Teil der Arbeit und keine Verzögerung. Die Fristen sind
dieselben, die im PSIRT-Register des Produkts erfasst sind; zwei Stellen mit zwei Zahlen
wären zwei Zusagen.

Wird eine Frist nicht gehalten, wird das im Register mit Grund vermerkt. Eine
überschrittene Frist ist ein Befund über uns, nicht über die Schwachstelle.

## Austausch mit Herstellern von Fremdkomponenten (Art. 13 Abs. 6)

Stellen **wir** eine Schwachstelle in einer Komponente Dritter fest, wird deren Hersteller
unterrichtet, **bevor** wir darüber informieren. Das ist der Kern des Art. 13 Abs. 6, und
es ist die Richtung, die bisher am schwächsten belegt war.

| Schritt | Vorgehen |
|---|---|
| 1. Zuordnung | Der Befund wird **exakt** der Komponente zugeordnet — `requests-oauthlib` ist nicht `requests`. Eine Zuordnung über Teilzeichenketten findet nicht statt. |
| 2. Meldeweg bestimmen | Der Weg des Herstellers hat Vorrang: dessen Sicherheitsrichtlinie, dessen `security.txt`, dessen Advisory-Schnittstelle. Fehlt beides, die allgemeine Kontaktadresse des Projekts. |
| 3. Unterrichten | mit denselben Angaben, die wir selbst von einem Melder erwarten: nachvollziehbare Beschreibung, betroffene Fassungen, Auswirkung, möglichst ein Nachstellweg |
| 4. Festhalten | Datum, Kanal und Referenz der Meldung werden am Befund im Schwachstellenregister vermerkt |
| 5. Koordinieren | Veröffentlichung erst nach Abstimmung, Rückfall auf 90 Tage nach der Meldung, wenn keine Rückmeldung kommt |

**Der Fall, auf den es ankommt:** Eine Schwachstelle in Fremdcode, die **wir** gefunden
haben und die **wir** veröffentlichen wollen, ohne dass der Hersteller informiert ist. Das
ist die Konstellation, die Art. 13 Abs. 6 verhindern soll, und sie wird in der Akte
gerechnet: Steht ein eigener Befund an einer Fremdkomponente auf „offengelegt" oder trägt
er eine Advisory-Adresse, ohne dass eine Upstream-Meldung vermerkt ist, erscheint das als
offener Punkt im Release-Check — mit roter Wirkung, weil dann über fremden Code informiert
wurde, ohne dessen Hersteller zu unterrichten.

Für **übernommene** Befunde (Dependabot, OSV, Schwachstellenabgleich) greift die Pflicht
nicht: Diese Schwachstellen hat der Hersteller selbst veröffentlicht. Würde die Prüfung
auch sie erfassen, wäre sie nach dem ersten Abgleich dauerhaft rot und damit wirkungslos.

## Unterrichtung der Betreiber

Betreiber erfahren von einer behobenen Schwachstelle über die
[Sicherheitshinweise](https://cyberwoks.de/hinweise.html), die Freigabehinweise und — auf
Wunsch — per E-Mail. Für den Eintrag in die Liste genügt eine Nachricht an
`security@cyberwoks.de`; der Versand erfolgt von Hand an die eingetragenen Adressen.

**Es gibt bewusst kein Verteilersystem.** Ein Dienstleister für den Versand wäre ein
Auftragsverarbeiter mit Zugang zu einer Liste der Betreiber dieser Software — also zu
einer Angabe, die für einen Angreifer wertvoll ist. Bei der erwarteten Zahl von Betreibern
ist der Versand von Hand tragfähig; wird sie größer, ist das eine Entscheidung mit eigener
Abwägung.

Bei einer **aktiv ausgenutzten** Schwachstelle gilt zusätzlich der Weg aus
[Meldewege nach Art. 14](meldewege-art14.md): Dort ist die Unterrichtung der Nutzer Teil
der Meldepflicht und keine freiwillige Leistung.

## Den Austausch erleichtern (Anhang I Teil II Nr. 6)

Nr. 6 verlangt mehr als eine Kontaktadresse. Der Wortlaut:

> Maßnahmen ergreifen, um den Austausch von Informationen über mögliche
> Schwachstellen in ihrem Produkt mit digitalen Elementen und darin enthaltenen
> Komponenten Dritter zu erleichtern, und dazu u. a. eine Kontaktadresse für die
> Meldung der in dem Produkt mit digitalen Elementen entdeckten Schwachstellen
> angeben

Die Kontaktadresse ist das Mindeste („u. a."), nicht das Ganze. Was darüber
hinaus getan wird:

| Maßnahme | Stand |
|---|---|
| Kontaktadresse veröffentlicht, auffindbar und maschinenlesbar (RFC 9116) | erledigt |
| Verbindliche Richtlinie mit Fristen und Pflichtangaben, öffentlich | erledigt — `SECURITY.md` Fassung 2.0 |
| Stückliste je Fassung und Artefakt, maschinenlesbar und am Digest signiert | erledigt — damit kann **jeder** prüfen, ob eine fremde Schwachstelle dieses Produkt betrifft, ohne uns zu fragen |
| Hinweise strukturiert nach einer veröffentlichten Vorlage | erledigt — `.github/ADVISORY_VORLAGE.md` im öffentlichen Quellverzeichnis, mit der nächsten Fassung dort abrufbar |
| Hinweise maschinenlesbar über die Advisory-Schnittstelle des Quellverzeichnisses | **offen** — Advisories sind dort nicht aktiviert, geführt als **C5** in [Abweichungen](abweichungen.md) |
| Aussage „nicht betroffen" mit Begründung auf Anfrage | erledigt als Zusage, siehe unten |
| Teilnahme an einem Austauschformat | **offen** — geführt als **C6** in [Abweichungen](abweichungen.md) |

### „Nicht betroffen" ist eine Aussage, die wir abgeben

Der häufigste Fall im Betrieb eines Kunden ist nicht eine Schwachstelle in
diesem Produkt, sondern ein **Treffer seines Prüfwerkzeugs** gegen eine
Komponente in der Stückliste. Er muss dann erklären, ob er handeln muss.

Zugesagt wird: Auf Anfrage geben wir zu einer Schwachstelle einer gelisteten
Komponente eine Aussage mit **Begründung** ab — welcher Code nicht erreicht,
welche Funktion nicht benutzt, welche Voraussetzung nicht erfüllt ist. „Nicht
betroffen" ohne Begründung ist eine Behauptung und räumt einen Fehlalarm nicht
aus.

Form und Pflichtfelder: der zweite Teil von `.github/ADVISORY_VORLAGE.md` im
Quellverzeichnis.

!!! info "Warum kein VEX-Dokument je Komponente"
    Der naheliegende Weg wäre, zu jeder Komponente der Stückliste und jeder
    bekannten Schwachstelle ein maschinenlesbares VEX-Dokument zu führen. Bei
    184 Komponenten und einem laufenden Abgleich sind das Hunderte Aussagen, von
    denen jede eine **fachliche Entscheidung** ist.

    Hunderte Aussagen, die niemand einzeln getroffen hat, sind schlechter als
    keine: Sie sehen wie Feststellungen aus. Deshalb gilt die Aussage auf
    Anfrage, mit Begründung, und die Begründung wird am Befund im
    Schwachstellenregister festgehalten — damit die zweite Anfrage zur selben
    Komponente ohne neue Entscheidung beantwortet werden kann.

    Wird die Zahl der Anfragen groß, ist die maschinenlesbare Form die richtige
    Antwort darauf. Dann ist sie der Abschluss von Entscheidungen, die getroffen
    wurden — und nicht ihr Ersatz.

### Welches Austauschformat

Geprüft und zu entscheiden (**C6**), in dieser Reihenfolge:

| Weg | Was er bringt | Aufwand |
|---|---|---|
| Meldeplattform des nationalen CSIRT | derselbe Kanal, der nach Art. 14 ohnehin gebraucht wird — die Anmeldung dort ist doppelt nützlich | gering; der Meldezugang selbst besteht seit dem 5. November 2026 (**C4**, erste Hälfte) |
| Allianz für Cyber-Sicherheit | Lagebild und Austausch, geringe Einstiegshürde für ein Einzelunternehmen | gering |
| CNA-Programm des Quellverzeichnisses | eigene Kennungen vergeben statt beantragen | mittel, setzt **C5** voraus |
| Branchenbezogener Austauschkreis | für ein Werkzeug ohne Branchenbindung wenig passend | hoch |

**Entschieden wird die erste Zeile zuerst**, weil sie mit dem Zugang zur
Meldeplattform zusammenfällt. Eine Teilnahme, die neben dem ohnehin nötigen
Weg ein zweites Konto verlangt, wird nicht gepflegt.

**Fassung 1.1, 2. November 2026.** Fundstellen: Anhang I Teil II Nr. 4
(Offenlegung behobener Schwachstellen), Nr. 5 (Strategie für die koordinierte
Offenlegung), Nr. 6 (Austausch und Kontaktadresse), Art. 13 Abs. 6 (Meldung an
den Hersteller der Komponente) der Verordnung (EU) 2024/2847. Gegen die
amtliche deutsche Fassung geprüft (ABl. L vom 20.11.2024).
