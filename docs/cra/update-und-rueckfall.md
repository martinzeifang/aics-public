# Aktualisierungen, Signaturprüfung und Rückfall

Beantwortet die Anforderung **AI2-07** der Eigenbewertung. Fundstelle: Anhang I
Teil II Nr. 7 der Verordnung (EU) 2024/2847, in Verbindung mit Anhang I Teil I
Nr. 2 Buchst. c.

> **Teil II Nr. 7:** Mechanismen für die sichere Verbreitung von Aktualisierungen
> für Produkte mit digitalen Elementen bereitstellen, damit Schwachstellen
> rechtzeitig und im Falle von Sicherheitsaktualisierungen gegebenenfalls
> automatisch behoben oder eingedämmt werden

## Der Weg einer Aktualisierung

| Schritt | Was geschieht | Wo belegt |
|---|---|---|
| 1. Freigabe | Quellstand wird mit einer Fassungsnummer versehen und als Release veröffentlicht | Quellverzeichnis |
| 2. Bau | Das **öffentliche** Verzeichnis baut die Release-Abbilder — nicht das private | Baulauf in `aics-public` |
| 3. Signatur | Die Abbilder werden schlüssellos signiert; dazu entstehen Herkunftsnachweis und Stückliste als Attestierung am Digest | Signatur und Attestierung im Paketverzeichnis |
| 4. Bezug | Der Betreiber bezieht das Abbild aus dem öffentlichen Paketverzeichnis | öffentlich, ohne Zugangsdaten lesbar |
| 5. Prüfung vor dem Einsatz | Herkunft **und** Signatur werden geprüft, bevor ein Dienst angefasst wird | siehe unten |
| 6. Einsatz | Austausch des Abbilds; die Daten bleiben, das Schema wird beim Start angelegt | Betriebsanleitung |

**Warum der Bau im öffentlichen Verzeichnis liegt:** Damit die Signatur auf einen
Quellbaum zeigt, den der Betreiber selbst lesen kann. Eine Signatur, deren
Identität auf ein Verzeichnis zeigt, in das niemand sehen kann, belegt die
Herkunft gegenüber Dritten nicht.

## Zwei Prüfungen, nicht eine

Das ist der Kern dieses Dokuments und wird regelmäßig verwechselt:

| Prüfung | Was sie belegt | Was sie **nicht** belegt |
|---|---|---|
| **Herkunft** — die Kennung `org.opencontainers.image.source` des Abbilds | dass das Abbild angibt, aus `aics-public` zu stammen | nichts kryptografisch. Die Kennung wird beim Bau gesetzt; wer ein Abbild baut, kann sie hineinschreiben |
| **Signatur** — `cosign verify` gegen Identität und Ausgeber | dass ein Baulauf dieses öffentlichen Verzeichnisses dieses Abbild signiert hat | dass das Abbild fehlerfrei ist |

Sie sind **zwei Funktionen und bleiben zwei**. Wer die zweite durch die erste
ersetzt, hat eine Prüfung verloren, und es sieht aus wie zwei. Ein Prüfer hält
das fest, damit die Zusammenführung nicht als Vereinfachung durchgeht.

Geprüft wird gegen:

```
Identität : ^https://github\.com/martinzeifang/aics-public/\.github/workflows/.+$
Ausgeber  : https://token.actions.githubusercontent.com
```

### Wo die Prüfung erzwungen wird — und wo nicht

| Weg | Herkunft | Signatur | Begründung |
|---|---|---|---|
| **Betriebsskript** (`scripts/ops/portainer_redeploy.py`) — der vorgesehene Weg | erzwungen | **erzwungen, Vorgabe** | Hier steht ein Mensch, der das Prüfwerkzeug installieren oder bewusst abschalten kann. Fail-Open wäre hier die falsche Richtung |
| **Schaltfläche in der Anwendung** (*Version & Updates*) | erzwungen | aus | Das Prüfwerkzeug liegt nicht im Abbild. Eine Schaltfläche, die immer mit einem Werkzeugfehler endet, ist schlechter als eine benannte Lücke |
| Nothilfe mit einem Entwicklungsabbild | `--quelle privat` | `--signatur aus` | ausdrücklich zu wählen, beides, und je mit eigener Angabe |

!!! warning "Die benannte Lücke, und was sie wert ist"
    Die Schaltfläche in der Anwendung prüft die **Herkunft**, nicht die
    Signatur. Das ist eine bewusst gewählte und hier benannte Grenze, keine
    Nachlässigkeit — und sie ist nicht gleichgültig: Wer über die Schaltfläche
    aktualisiert, verlässt sich auf eine Kennung, die beim Bau gesetzt wird.

    **Für eine Installation, die den Nachweis führen will, ist der vorgesehene
    Weg das Betriebsskript**, und das prüft seit Fassung 8.3.1 standardmäßig
    beides. Die Zusage ist nicht „die Anwendung prüft" — sie ist „der
    dokumentierte Deploy-Weg prüft, und der andere Weg sagt, dass er es nicht
    tut".

    Geführt in [Abweichungen](abweichungen.md) mit Wiedervorlage.

### Was ein Betreiber selbst prüfen kann

Ohne Zugang zu unseren Systemen, mit `cosign`:

```
cosign verify \
  --certificate-identity-regexp \
    '^https://github\.com/martinzeifang/aics-public/\.github/workflows/.+$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/martinzeifang/ai_compliance_suite:<Fassung>

cosign verify-attestation --type spdxjson \
  --certificate-identity-regexp '…' --certificate-oidc-issuer '…' \
  ghcr.io/martinzeifang/ai_compliance_suite:<Fassung>
```

Der zweite Aufruf liefert die **Stückliste** als signierte Attestierung am
Digest. Das ist der Grund, warum sie nicht als Datei neben dem Release liegt:
Eine Stückliste beschreibt ein Abbild, nicht einen Quellstand-Zeiger, und als
Attestierung ist sie an den Digest gebunden statt eine lose Behauptung daneben
zu sein.

**Ein Entwicklungsabbild (`:main`, `:sha-…`) wird von diesem Aufruf
abgewiesen** — es ist nicht signiert. Das ist beabsichtigt und der Unterschied
zwischen einem Release und einem Zwischenstand.

## Fassungskanäle (Reife ist nicht Herkunft)

| Kanal | Zeiger | Herkunft | Für wen |
|---|---|---|---|
| `stable` (Vorgabe) | `8.3.1`, `8.3`, `latest` | aus `aics-public` erzwungen | alle |
| `beta` | Vorabfassungen wie `8.4.0-beta.1` | aus `aics-public` erzwungen | Vorabprüfung |
| `dev` | `main`, `sha-…` | privat erlaubt | **nur intern**, nicht wählbar ohne ausdrückliche Freischaltung am Container |

Die Trennung ist der Punkt: „Ich will eine Vorabfassung prüfen" und „ich gebe
die Herkunftsprüfung auf" sind zwei verschiedene Wünsche. In beiden
Kundenkanälen bleibt die Herkunft geprüft.

## Automatische Aktualisierungen — warum nicht

Buchst. c verlangt, **dass** Schwachstellen durch Sicherheitsaktualisierungen
behoben werden *können*. Automatische Installation nennt er mit dem Vorbehalt
„**gegebenenfalls**", und Nr. 2 des Teils I steht insgesamt unter „soweit
zutreffend"; Teil II Nr. 7 wiederholt das „gegebenenfalls".

**Für dieses Produkt ist die automatische Installation nicht zutreffend**, und
das ist eine Begründung nach Art. 13 Abs. 4, keine Auslassung:

| Grund | |
|---|---|
| Der Betreiber betreibt selbst | Die Anwendung läuft in seiner Umgebung, hinter seiner Firewall, auf seiner Orchestrierung. Es gibt keinen Fernzugriff und soll keinen geben — ein Hersteller, der ungefragt Abbilder in fremden Umgebungen austauscht, hat einen Weg geschaffen, den auch ein anderer benutzen kann |
| Ein Austausch ist ein Betriebsvorgang | Er bedeutet einen Neustart der Dienste. Wann der stattfindet, entscheidet derjenige, der die Verfügbarkeit zusagt — nicht wir |
| Das Schema gehört der Anwendung | Beim Start wird es idempotent angelegt. Ein ungefragter Austausch wäre eine ungefragte Schemaänderung an fremden Daten |

**Was stattdessen zutrifft, und erfüllt ist** — die zweite Hälfte des Buchst. c
verlangt, „bei dem die Nutzer über verfügbare Aktualisierungen informiert
werden":

| Anforderung | Umsetzung |
|---|---|
| Nutzer werden über verfügbare Aktualisierungen informiert | *Administration → Version & Updates* nennt installierte und neueste Fassung samt Kanal; maschinenlesbar über die Verwaltungsschnittstelle |
| Aktualisierungen lassen sich verschieben | der Betreiber bestimmt den Zeitpunkt vollständig — das ist der Normalfall, nicht die Ausnahme |
| Hinweise und einschlägige Informationen begleiten die Aktualisierung (Teil II Nr. 8) | Freigabehinweise je Fassung, [Hinweisliste](https://cyberwoks.de/hinweise.html) |
| Sicherheitsaktualisierungen kostenlos (Teil II Nr. 8) | zugesagt, siehe [Unterstützungszeitraum](unterstuetzungszeitraum.md) |
| Sicherheitsaktualisierungen getrennt von Funktionsaktualisierungen, soweit technisch machbar (Teil II Nr. 2) | getrennte Kanäle zugesagt und im Release-Vorgang gerechnet |

Die Begründung gehört nach Art. 13 Abs. 4 **in die technische
Dokumentation** — dieses Dokument ist der Ort, an dem sie steht, und es hängt
als Nachweis an AI2-07.

## Rückfall auf die vorige Fassung

Ein Aktualisierungsweg ohne Rückweg ist keiner. Der Rückfall besteht darin, den
Fassungszeiger auf die vorige Fassung zu stellen und erneut auszurollen —
dasselbe Verfahren wie die Aktualisierung, mit derselben Prüfung von Herkunft
und Signatur.

### Was der Rückfall kann und was nicht

| | |
|---|---|
| Abbild zurücktauschen | **ja**, in derselben Zeit wie eine Aktualisierung |
| Daten unverändert behalten | **ja** — die Datenbank wird nicht angefasst |
| Eine Schemaänderung zurücknehmen | **nein** |

!!! warning "Der Rückweg ist der gefährliche Teil"
    Älterer Code auf einer Datenbank, die schon das neuere Schema trägt. Die
    Anwendung legt ihr Schema beim Start idempotent an und **baut nichts
    zurück** — eine Spalte, die eine neuere Fassung angelegt hat, bleibt stehen.
    Das ist in der Regel harmlos (die ältere Fassung kennt die Spalte nicht und
    liest sie nicht), aber es ist keine Garantie: Eine Spalte mit
    Pflichtcharakter, die die ältere Fassung nicht füllt, lässt sie scheitern.

    Deshalb: Ein Rückfall über eine **Haupt- oder Nebenfassung hinweg** verlangt
    eine ausdrückliche Bestätigung samt Zahlen, nicht nur eine Warnung. Ein
    Rückweg, den die Anwendung schlicht verbietet, endet im Eingriff von Hand,
    und der ist schlimmer.

    **Vor einem Rückfall über eine Nebenfassung hinweg** wird eine Sicherung
    erzeugt — sie ist der eigentliche Rückweg für die Daten, nicht das Abbild.

### Verfahren

1. Sicherung erzeugen und ihre Prüfsumme festhalten (bei Rückfall über eine
   Nebenfassung hinweg: Pflicht).
2. Betriebsskript mit der Zielfassung aufrufen; Herkunft und Signatur werden
   geprüft wie bei jeder Aktualisierung.
3. Nachprüfen: Zustand der Container (**alle**, nicht nur die laufenden — „angelegt"
   heißt nie gestartet), Gesundheitsabfrage, Anmeldung, eine Schreiboperation.
4. Protokollieren — Datum, Fassungen, Dauer, ob ein Eingriff von Hand nötig war.

### Protokoll des Rückfalltests

Durchzuführen mit `~/werkzeuge/rueckfalltest-dev.sh` auf der
Entwicklungsinstanz. Das Skript rollt von der laufenden Fassung auf die vorige
zurück und wieder vor und gibt das Protokoll aus.

| Datum | von → nach → zurück | Dauer | Eingriff von Hand nötig? | Nach der Rückkehr bedienbar? | Durchgeführt von |
|---|---|---|---|---|---|
| _(noch nicht durchgeführt)_ | | | | | |

!!! warning "Dieser Punkt ist offen — und das Dokument behauptet nichts anderes"
    Das Verfahren oben ist festgelegt, das Skript liegt bereit. Durchgeführt ist
    es nicht. Solange die Tabelle leer ist, ist der Rückfall **beschrieben und
    nicht belegt** — und ein Rückfallverfahren, das nie gelaufen ist, ist genau
    das, was im Ernstfall nicht trägt.

    Erst mit einer Zeile in dieser Tabelle ist der entsprechende Teil von
    AI2-07 erfüllt.

## Nachweis, dass dieser Weg trägt

| Prüfung | Turnus | Nachweis |
|---|---|---|
| Signatur der ausgelieferten Abbilder geprüft, bevor eine Instanz angefasst wird | je Deploy | Ausgabe des Betriebsskripts |
| Ein Entwicklungsabbild wird vom Prüfaufruf abgewiesen (Gegenprobe) | je Release | Vermerk im Release-Vorgang |
| Rückfalltest auf der Entwicklungsinstanz | jährlich und vor jeder Hauptfassung | Tabelle oben |
| Angabe der neuesten Fassung in *Version & Updates* stimmt mit dem Paketverzeichnis überein | je Release | Vermerk im Release-Vorgang |

Die Gegenprobe in Zeile 2 ist die wichtigere Hälfte: Eine Prüfung, die alles
durchlässt, meldet ebenfalls „gültig".

**Fassung 1.0, 2. November 2026.** Fundstellen: Anhang I Teil I Nr. 2 Buchst. c
(Behebbarkeit durch Sicherheitsaktualisierungen, Unterrichtung, Opt-out),
Anhang I Teil II Nr. 2 (getrennte Bereitstellung), Nr. 7 (sichere Verbreitung),
Nr. 8 (unverzüglich und kostenlos), Art. 13 Abs. 4 (Begründung bei
Nichtanwendbarkeit), Abs. 9 (Verfügbarkeit über zehn Jahre) der Verordnung
(EU) 2024/2847. Gegen die amtliche deutsche Fassung geprüft
(ABl. L vom 20.11.2024).
