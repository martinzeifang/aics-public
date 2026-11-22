# Kennzeichnung und Herstellerangaben

Beantwortet die Anforderungen **ART13-06** (Kennzeichen zur Identifikation) und
**ART13-07** (Herstellerangaben) der Eigenbewertung. Fundstellen: Art. 13
Abs. 15 und 16 der Verordnung (EU) 2024/2847.

Beide Absätze verlangen dasselbe Muster: Die Angabe steht **auf dem Produkt**
oder, wenn das nicht möglich ist, auf der Verpackung oder **in den beigefügten
Unterlagen**. Für eine serverseitige Webanwendung ohne Verpackung heißt das: in
der Anwendung selbst und in den Informationen und Anleitungen nach Anhang II.

Dieses Dokument sagt, wo genau — und hält die Stellen gegeneinander. Die
Gefahr liegt nicht im Fehlen der Angaben, sondern darin, dass sie an drei Orten
stehen und auseinanderlaufen.

## Kennzeichen zur Identifikation (Art. 13 Abs. 15)

> Die Hersteller gewährleisten, dass ihre Produkte mit digitalen Elementen eine
> Typen-, Chargen- oder Seriennummer oder ein anderes Kennzeichen zu ihrer
> Identifikation tragen, oder, falls dies nicht möglich ist, dass die diese
> Informationen auf der Verpackung oder in den dem Produkt mit digitalen
> Elementen beigefügten Unterlagen angegeben werden.

Das Kennzeichen dieses Produkts ist **zweistufig**, und die Unterscheidung ist
der Inhalt dieses Abschnitts:

| | Angabe | Was sie leistet |
|---|---|---|
| **Fassungsangabe** | `HAUPT.NEBEN.KORREKTUR`, z. B. `8.3.1` | benennt den Stand für Menschen — in Hinweisen, in der Erklärung, in einer Behördenanfrage |
| **Eindeutige technische Kennung** | `sha256`-Digest des Container-Abbilds | benennt **das Artefakt** — eindeutig, unveränderlich, ohne unsere Mitwirkung prüfbar |

**Maßgeblich für die Identifikation ist der Digest, nicht die Fassungsangabe.**
Ein Fassungsname ist ein Zeiger und kann auf verschiedene Artefakte zeigen; ein
Digest kann das nicht. Deshalb bezeichnet die EU-Konformitätserklärung nach
Anhang V Nr. 4 den Digest und nicht nur die Zahl.

### Wo das Kennzeichen am Produkt selbst steht

| Ort | Angabe | Nachgemessen am 2.11.2026 (Produktiv) |
|---|---|---|
| Fußzeile jeder Seite der Anwendung | Fassung, dazu eine Kennzeichnung bei Vorab- oder Entwicklungsständen | — |
| *Administration → Version & Updates* | Fassung, Herkunft, Fassungszeiger, Stand gegenüber der neuesten verfügbaren Fassung | — |
| `GET /api/auth/profile` | die Fassung maschinenlesbar, für Betriebsüberwachung | — |
| Umgebung des Abbilds | `APP_VERSION` | `8.3.1` |
| | `APP_IMAGE_SOURCE` | `https://github.com/martinzeifang/aics-public` |
| | `APP_IMAGE_TAG` | `8.3.1` |
| | `APP_IMAGE_DIGEST` | **leer** — siehe unten |
| Kennungen des Abbilds (`org.opencontainers.image.*`) | Herkunft, Fassung, Quellstand | — |

Die **Fassung** ist damit ohne Rückfrage beim Hersteller auffindbar — in der
Oberfläche, über die Schnittstelle und am Artefakt. Damit ist Abs. 15 erfüllt:
Verlangt ist „eine Typen-, Chargen- oder Seriennummer oder ein anderes
Kennzeichen zu ihrer Identifikation", und die Fassungsangabe ist eines.

!!! warning "Die laufende Anwendung kennt ihren eigenen Digest nicht"
    `APP_IMAGE_DIGEST` ist im Baurezept deklariert und wird von **keinem**
    Baulauf gesetzt — nachgemessen: auf Produktiv leer. Das ist kein
    Versäumnis, sondern ein Henne-Ei-Problem: Der Digest eines Abbilds steht
    erst **nach** dem Bau fest und lässt sich deshalb nicht als Bauargument
    hineingeben.

    Folge: *Administration → Version & Updates* gibt den Digest des laufenden
    Abbilds **nicht** aus. Für einen Betreiber, der einen Vorfall dokumentieren
    muss, ist das die Angabe, die am genauesten wäre und die er nicht aus der
    Anwendung bekommt.

    **Woher er ihn bekommt:** aus der Registry zum Fassungszeiger
    (`docker-content-digest`), aus der Laufzeitumgebung seines Wirtssystems,
    oder aus der Ausgabe des Betriebsskripts, das den Zeiger vor dem Deploy
    auflöst. Alle drei gehen ohne uns.

    **Woher die Akte ihn nimmt:** `cra_sbom.image_digest`, gefüllt beim Holen
    der Stückliste vom Abbild. Von dort nennt ihn die EU-Konformitätserklärung
    nach Anhang V Nr. 4. Der Digest steht also im **Nachweis** und nicht im
    laufenden Dienst — und das ist die richtige Ebene, weil er zum
    *Auslieferungsvorgang* gehört und nicht zum Code.

    Geführt als **C11** in [Abweichungen](abweichungen.md). Abs. 15 ist davon
    nicht berührt; die Angabe ist eine Verbesserung über das Verlangte hinaus.

!!! info "Eine Zahl, die aus der falschen Quelle kam"
    Bis Fassung 8.3.0 zeigte die Fußzeile den Wert aus der Baudatei des
    Oberflächenteils statt den Stand der laufenden Installation. Bei einem
    Nothilfe-Deploy mit einem Entwicklungsabbild stand dort deshalb eine
    Release-Nummer, die die Installation nicht trug.

    Das steht hier, weil es genau der Fall ist, den Abs. 15 verhindern soll: Wer
    einen Befund dokumentiert, muss den Stand benennen können. Behoben; die
    Angabe kommt jetzt aus der laufenden Anwendung und trägt eine Kennzeichnung,
    wenn der Stand kein Release ist.

## Herstellerangaben (Art. 13 Abs. 16)

> Die Hersteller geben den Namen, den eingetragenen Handelsnamen oder die
> eingetragene Handelsmarke des Herstellers, die Postanschrift, die
> E-Mail-Adresse oder andere digitale Kontaktangaben sowie, soweit vorhanden, die
> Website, unter der der Hersteller zu erreichen ist, entweder auf dem Produkt
> mit digitalen Elementen selbst oder, wenn dies nicht möglich ist, auf der
> Verpackung oder in den dem Produkt mit digitalen Elementen beigefügten
> Unterlagen an. Diese Informationen werden auch in die in Informationen und
> Anleitungen für den Nutzer gemäß Anhang II aufgenommen.

Die Angaben:

| Pflichtangabe | Wert |
|---|---|
| Name | **Martin Zeifang** |
| Postanschrift | **Finkenweg 42, 89150 Laichingen, Deutschland** |
| E-Mail-Adresse | **kontakt@cyberwoks.de** |
| Website | **https://cyberwoks.de** |

Der zweite Satz des Absatzes ist keine Wiederholung, sondern eine zusätzliche
Pflicht: Die Angaben gehören **auch** in die Informationen nach Anhang II. Sie
stehen dort unter Nr. 1.

Eine **Postanschrift** ist Pflicht; ein Postfach genügt nicht. Die Anschrift
oben ist eine ladungsfähige Anschrift.

## Die drei Stellen und ihr Gleichstand

Hier liegt die eigentliche Arbeit. Eine Abweichung zwischen diesen Stellen
fällt einer Behörde auf, und sie wiegt schwerer als eine fehlende Angabe —
eine Lücke ist ein Versäumnis, ein Widerspruch sieht nach einer Falschangabe aus.

| Angabe | Anhang-II-Informationen (`cyberwoks.de/cra.html`) | EU-Konformitätserklärung | In der Anwendung |
|---|---|---|---|
| Name | Martin Zeifang | Martin Zeifang | — |
| Anschrift | Finkenweg 42, 89150 Laichingen | Finkenweg 42, 89150 Laichingen | — |
| E-Mail | kontakt@cyberwoks.de | — (Erklärung verlangt sie nicht) | — |
| Anlaufstelle Schwachstellen | security@cyberwoks.de | — | — |
| Website | https://cyberwoks.de | — | — |
| Fassung | Versionsschema und Fundort | Nr. 1 und Nr. 4 | Fußzeile, *Version & Updates* |
| Digest | als maßgebliche Kennung benannt | Nr. 4, konkret | **nicht verfügbar** (s. o.) |

**Die Angaben werden aus einer Quelle gepflegt.** Die Erklärung zieht
Herstellername und Anschrift aus dem Mandantendatensatz; die Vorschlagsfunktion
nennt die Quelle je Feld. Dieselbe Angabe an drei Stellen von Hand zu tippen ist
genau die Fehlerklasse, die dieses Projekt als Spiegel-Liste führt — beim
vierten Produkt steht sonst eine andere da.

!!! warning "Was noch nicht aus einer Quelle kommt"
    Die Angaben in `cra.html` und in der `security.txt` der Website sind von
    Hand gepflegt und nicht an den Mandantendatensatz gebunden. Sie werden
    deshalb in die jährliche Durchsicht aufgenommen (unten) — und bis dahin
    ist der Gleichstand oben die Prüfung, nicht der Mechanismus.

## Die zentrale Anlaufstelle (Art. 13 Abs. 17)

Abs. 17 steht hier, weil er mit Abs. 16 zusammen gelesen werden muss und einen
Punkt enthält, der leicht übersehen wird:

> Die zentrale Anlaufstelle ermöglicht es den Nutzern, ihr bevorzugtes
> Kommunikationsmittel zu wählen, wobei diese Mittel **nicht auf automatisierte
> Instrumente beschränkt** werden dürfen.

Die Anlaufstelle ist `security@cyberwoks.de`. Sie ist leicht zu ermitteln
(Produktseite, Sicherheitsseite, `security.txt` nach RFC 9116, `SECURITY.md`)
und sie wird **von einer Person gelesen**, nicht von einem Werkzeug
beantwortet — damit ist sie kein automatisiertes Instrument.

!!! warning "Offener Punkt: ein zweites Mittel"
    „Ihr bevorzugtes Kommunikationsmittel wählen" legt mehr als einen Kanal
    nahe. Angeboten ist heute **nur** E-Mail; eine Rufnummer ist nicht
    veröffentlicht, und ein Kontaktformular hat die Website bewusst nicht.

    Dass die Anlaufstelle von Menschen gelesen wird, erfüllt den Halbsatz
    „nicht auf automatisierte Instrumente beschränkt". Die Wahlmöglichkeit
    erfüllt es nicht. Postalisch ist der Hersteller über die Anschrift oben
    erreichbar — das ist ein zweiter, nicht automatisierter Weg, aber kein
    schneller.

    Die Angabe einer Rufnummer würde beides schließen: diesen Punkt und die
    Anforderung des § 5 DDG an eine schnelle Kontaktaufnahme, die im Impressum
    der Website offen ist. Geführt in [Abweichungen](abweichungen.md).

## Durchsicht

| Prüfung | Turnus | Nachweis |
|---|---|---|
| Gleichstandstabelle oben Zeile für Zeile gegen die drei Stellen gehalten | jährlich und bei jeder Änderung der Herstellerangaben | Fassungsangabe unten |
| Fußzeile und *Version & Updates* zeigen den Stand der laufenden Installation | nach jedem Deploy | Vermerk im Release-Vorgang |
| Digest des ausgelieferten Abbilds in der Erklärung der Fassung eingetragen | je Release | Erklärung Nr. 4 |
| Die vier Bau-Metadaten im laufenden Abbild nachgemessen | je Release | Tabelle oben |

Die letzte Zeile ist aus diesem Vorgang entstanden: Die Tabelle oben behauptete
vier gesetzte Angaben, und eine davon war leer. **Eine Nachweistabelle, die
niemand gegen die Wirklichkeit hält, ist eine Behauptung** — gemessen wird mit

```
docker exec <container> printenv APP_VERSION APP_IMAGE_SOURCE \
    APP_IMAGE_TAG APP_IMAGE_DIGEST
```

**Fassung 1.0, 2. November 2026.** Fundstellen: Art. 13 Abs. 15 (Kennzeichen),
Abs. 16 (Herstellerangaben), Abs. 17 (zentrale Anlaufstelle), Abs. 18
(Informationen und Anleitungen), Anhang II Nr. 1 bis 3, Anhang V Nr. 4 der
Verordnung (EU) 2024/2847. Gegen die amtliche deutsche Fassung geprüft
(ABl. L vom 20.11.2024).
