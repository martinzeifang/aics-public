# Schulung & Awareness — Cybersicherheitskultur

> **Bezug:** CRA (VO (EU) 2024/2847), Erwägungsgründe + Art. 13 · Prüfpunkt
> **IMPL-06** im [CRA-Umsetzungsplan](../cra/CRA-UMSETZUNGSPLAN.md) · Issue #861
>
> **Gegenstand:** Die AI Compliance Suite als Produkt mit digitalen Elementen.
> Dieses Dokument beschreibt, **wie** die an Entwicklung und Betrieb
> beteiligten Personen über die CRA-Anforderungen und die einschlägigen
> Cybersicherheitspraktiken geschult werden — und **woran** sich das belegen
> lässt.

## Was dieses Dokument ist und was nicht

Es ist das **Konzept** und der **Nachweisrahmen**. Es ist kein Nachweis
darüber, dass eine Schulung stattgefunden hat: Der Nachweis entsteht erst
durch die Durchführung und die Einträge in der Tabelle unten. Ein Dokument,
das die eigene Erfüllung behauptet, ohne dass der Vorgang stattgefunden hat,
wäre in einer CRA-Akte schlechter als eine offene Lücke — es sieht aus wie
eine Feststellung.

Deshalb trägt der Umsetzungsplan IMPL-06 weiterhin **🟡 teilweise**, bis der
erste Zyklus durchlaufen und quittiert ist.

## Wer

| Rolle | Betroffen | Begründung |
|---|---|---|
| Entwicklung | ja | Schreibt den Code, der die Sicherheitseigenschaften des Produkts trägt (Anhang I Teil I) |
| Betrieb / Deployment | ja | Verantwortet Konfiguration, Updates und Bereitstellung (Anhang I Teil II) |
| Produkt / Compliance | ja | Führt die technische Dokumentation und die Konformitätsbewertung |
| Vertrieb / Verwaltung | Grundlagen | Keine Produktverantwortung, aber Meldewege und Phishing-Erkennung |

In einem Haus dieser Größe fallen mehrere Rollen auf dieselbe Person. Das
entwertet die Zuordnung nicht: Sie sagt, **welche Inhalte** jemand braucht,
nicht wie viele Personen es gibt.

## Was

Vier Bausteine. Die Reihenfolge ist bewusst — ohne den ersten sind die
übrigen Einzelmaßnahmen ohne Rahmen.

### 1. CRA-Grundlagen (alle, jährlich, ca. 60 min)

- Was der CRA verlangt: Anhang I Teil I (Produkteigenschaften), Teil II
  (Pflichten des Herstellers über den Lebenszyklus).
- Was eine **wesentliche Änderung** ist (Art. 3 Nr. 30) und warum ein
  Sicherheitsupdate keine ist (Erwägungsgrund 39).
- Melde­pflichten nach Art. 14: 24 h Frühwarnung, 72 h Meldung,
  Abschlussbericht — und dass die Frist **ab Kenntnis** läuft.
- Die eigene Akte: wo Anhang VII geführt wird, wer die EU-Konformitäts­-
  erklärung ausstellt und wer sie freigibt (Vier-Augen, #1743).

### 2. Secure Coding (Entwicklung, jährlich, ca. 120 min)

- OWASP Proactive Controls als Ordnungsrahmen — dieselben Kontrollen, die das
  CRA-Modul der Suite führt.
- Die Fehlerklassen, die in diesem Projekt **tatsächlich** aufgetreten sind:
  SSRF bei anwendergesteuerten Adressen (#741, #1761), Teil-Updates, die
  Felder leeren (#1771, #1805, #1820), Spiegel-Listen, die auseinanderlaufen
  (#1731, #1735), Grenzen, die hinter einer kleineren Grenze liegen (#1807),
  und Prüfungen, die auf Kommentare statt auf Code anspringen (#1833).
  **Eigene Fundstellen schulen besser als fremde Beispiele.**
- Eingaben sind Daten, keine Anweisungen: `security_utils.add_untrusted_block`
  und warum Modelltext durch `ProsaText` gerendert wird (#1783).

### 3. Threat Modeling (Entwicklung + Produkt, jährlich, ca. 90 min)

- STRIDE am eigenen Produkt; die Suite führt das Threat Model in C5.
- Vertrauensgrenzen dieser Anwendung: Browser ↔ Server, Server ↔
  KI-Provider (lokal **und** Cloud), Server ↔ Registry, Mandant ↔ Mandant.
- Datenausgang an die KI: Wann verlässt Inhalt das Haus, wer bestätigt das,
  wo steht es im Revisionspfad (#1519, #1836/E2).

### 4. Incident Response (Betrieb + Produkt, halbjährlich, ca. 60 min)

- Die eigene Meldekette: Erkennung → Bewertung → Art.-14-Fristen → CSIRT und
  ENISA **gleichzeitig** (#1760) → Nutzerunterrichtung.
- Wiederanlauf: Sicherung einspielen gegen Daten **übernehmen** — der
  Unterschied, der in #1808 elf von zwölf Mandanten gekostet hat.
- Eine Übung je Halbjahr mit einem erfundenen Vorfall, protokolliert wie ein
  echter.

### Begleitend: Phishing-Erkennung

Zwei Simulationen im Jahr. Ergebnis wird **aggregiert** festgehalten (Quote),
nicht personenbezogen — eine namentliche Auswertung macht aus einer
Lernmaßnahme eine Leistungskontrolle und beschädigt die Mitwirkung.

## Wann

| Baustein | Takt | Anlass zusätzlich |
|---|---|---|
| CRA-Grundlagen | jährlich | bei Eintritt, bei wesentlicher Änderung der Verordnungslage |
| Secure Coding | jährlich | bei Eintritt in die Entwicklung |
| Threat Modeling | jährlich | vor einem Release mit neuer Vertrauensgrenze |
| Incident Response | halbjährlich | nach jedem echten Vorfall (Nachbesprechung) |
| Phishing-Simulation | halbjährlich | — |

## Wie der Nachweis entsteht

Drei Dinge, und alle drei sind nötig:

1. **Inhalt** — die verwendeten Unterlagen (Foliensatz, Aufzeichnung, Link),
   abgelegt mit Datum und Version.
2. **Teilnahme** — Datum, Person, Baustein, Dauer; quittiert durch die Person
   selbst oder den Durchführenden.
3. **Wirksamkeit** — eine kurze Verständnisprüfung (fünf bis zehn Fragen) oder
   die Phishing-Quote. Ohne sie ist „geschult" eine Anwesenheitsaussage.

Die Suite kann dabei helfen: Der **DSGVO-Schulungsgenerator** erzeugt
Schulungsinhalte, und über die verwalteten Dokumente
(`<modul>_managed_docs`, #1149) lässt sich der Foliensatz als versioniertes
Artefakt führen. Die Teilnahmeliste gehört dagegen in die Personalakte und
**nicht** in die Produktdokumentation — sie enthält personenbezogene Daten,
und Anhang VII verlangt sie nicht.

## Qualifikation als Nachweis

Eine geprüfte, von einer dritten Stelle vergebene Qualifikation kann den
Zustand „geschult sein" für **ihren Gegenstand** belegen — und nur für ihren
Gegenstand. Dieser Abschnitt legt fest, wann das gilt, damit die Entscheidung
nachvollziehbar ist und nicht im Einzelfall neu begründet werden muss.

### Warum das zulässig ist

Der Prüfpunkt IMPL-06 verlangt, dass die beteiligten Personen „über die
CRA-Anforderungen und relevante Cybersicherheitspraktiken **geschult sein**"
müssen. Das ist ein **Zustand**, kein Vorgang. Die Fundstelle lautet
`Art. 13 Abs. 1; Erwägungsgründe` — **die Verordnung verlangt keine
Schulung.** Art. 13 Abs. 1 verlangt, dass das Produkt in Übereinstimmung mit
den grundlegenden Anforderungen entworfen, entwickelt und hergestellt wird;
Kompetenz ist dafür Voraussetzung, die Form ihres Erwerbs nicht geregelt.

Die „jährliche Pflichtschulung" oben steht in **unseren** Umsetzungshinweisen,
nicht im Rechtstext. Das ist dieselbe Unterscheidung wie bei der
24/7-Erreichbarkeit in [B5](../cra/abweichungen.md): ein Hinweis guter Praxis,
keine Pflicht. Ein Kompetenznachweis einer prüfenden Stelle ist für seinen
Gegenstand belastbarer als eine Teilnahmebestätigung, die sich der
Durchführende selbst ausstellt — in einem Haus mit einer Person ist das keine
Spitzfindigkeit, sondern der Unterschied zwischen Nachweis und Behauptung.

### Wo die Grenze liegt

Eine Qualifikation deckt die Bausteine ab, die ihr Gegenstand umfasst — und
keinen weiteren. Die Zuordnung ist ausdrücklich zu treffen:

| Baustein | Durch eine Qualifikation abdeckbar? |
|---|---|
| 1 · CRA-Grundlagen | **ja**, bei einer Qualifikation mit Gegenstand Regulatorik / CRA |
| 2 · Secure Coding | nein — es sei denn, der Gegenstand umfasst sichere Entwicklung ausdrücklich |
| 3 · Threat Modeling | nein |
| 4 · Incident Response | nein |
| Phishing-Erkennung | nein — sie prüft Verhalten, nicht Wissen |

Drei Einschränkungen gelten **immer**, auch bei einem passenden Gegenstand:

1. **Zuschnitt.** Regulatorik ist nicht Cybersicherheitspraxis. Die Bausteine
   2 bis 4 stehen hinter den Fehlerklassen, an denen dieses Projekt
   nachweislich wiederholt hängengeblieben ist — `data.get(feld, "")`,
   Spiegel-Listen, Wächter die Kommentare treffen statt Code. Dagegen hilft
   kein regulatorisches Wissen.
2. **Aktualität.** Eine Qualifikation ist zu einem Zeitpunkt vergeben. Die
   Praktiken ändern sich jährlich. **Der Selbstcheck entfällt deshalb nicht**;
   er wird nur kürzer, weil Baustein 1 bereits belegt ist.
3. **Rolle.** Eine Qualifikation belegt die Kompetenz der Rolle, für die sie
   vergeben wurde. Fallen hier mehrere Rollen auf eine Person, belegt sie
   trotzdem nur eine davon — das ist der Kern des Rollenabschnitts oben.

!!! danger "Eine Qualifikation ist kein Konformitätsnachweis"
    Sie belegt **Kompetenz** und gehört damit zu IMPL-06. Sie belegt **nicht**
    die Konformität des Produkts, und sie darf nicht in die Nähe der
    Konformitätsaussage geraten.

    Die Selbstbewertung nach Anhang VIII Modul A ist rechtlich einwandfrei.
    Steht in der Akte aber eine Gutachter- oder Sachverständigenbestellung des
    Herstellers neben der Konformitätsaussage zum eigenen Produkt, liest sich
    das wie eine Bestätigung durch eine dritte Stelle — die es nicht ist. Das
    ist die Frage, die im Ernstfall gestellt wird, und sie ist unangenehm,
    obwohl die Sache in Ordnung ist.

    Deshalb: Qualifikationen stehen **hier** und in der
    [EU-Konformitätserklärung](../cra/index.md) nicht. Nr. 7 der Erklärung
    nennt eine notifizierte Stelle nur dann, wenn eine beteiligt war.

### Register der anerkannten Qualifikationen

Eine Zeile je Qualifikation. **Vollständig ist eine Zeile erst mit Stelle,
Gegenstand, Datum und hinterlegtem Nachweis** — ohne diese vier belegt sie
nichts, genau wie eine leere Zeile im Nachweis-Tracker.

| Stelle | Gegenstand | Deckt Baustein | Rolle | Datum | Nachweis hinterlegt |
|---|---|---|---|---|---|
| BISG | Gutachter Regulatorik | 1 (CRA-Grundlagen) | Produkt / Compliance | _einzutragen_ | _einzutragen_ |

Solange Datum und Nachweis fehlen, ist die Zeile eine Absichtserklärung. Das
ist kein Formalismus: Ein Prüfer, der die Bestellung sehen will, bekommt sonst
eine Tabelle ohne Beleg vorgelegt — und das ist schlechter als keine Tabelle.

### Was damit für IMPL-06 übrig bleibt

| Hälfte der Anforderung | Nachweis |
|---|---|
| CRA-Anforderungen | Register oben, sobald die Zeile vollständig ist |
| relevante Cybersicherheitspraktiken | Bausteine 2 bis 4 plus Phishing — Selbstcheck durchführen, Ergebnis in den Nachweis-Tracker |

Erst beides zusammen trägt den Prüfpunkt. Eine Qualifikation als Begründung
dafür einzutragen, dass Schulung **nicht anwendbar** sei, wäre die falsche
Kategorie: Die Anforderung ist anwendbar und zur Hälfte erfüllt.

## Nachweis-Tracker

Eine Zeile je durchgeführtem Baustein. Personen werden **mit Rolle** geführt;
Namen bleiben in der Personalakte.

| Datum | Baustein | Teilnehmer (Rollen) | Unterlage (Version) | Wirksamkeitsprüfung | Durchgeführt von |
|---|---|---|---|---|---|
| _(noch kein Zyklus durchgeführt)_ | | | | | |

> **Offener Punkt zu IMPL-06:** Der erste Zyklus ist durchzuführen und hier
> einzutragen. Erst damit ist der Prüfpunkt erfüllt; das Konzept allein
> erfüllt ihn nicht. Geführt als **C1** im
> [Abweichungsverzeichnis](../cra/abweichungen.md), fällig 31. Dezember 2026.
>
> Ist Baustein 1 über das **Register der anerkannten Qualifikationen** belegt,
> verkleinert sich C1 auf die Bausteine 2 bis 4 und die Phishing-Erkennung —
> es entfällt nicht. Eine Qualifikation belegt Wissen zu einem Zeitpunkt, der
> Selbstcheck belegt die Aktualität der Praxis.

## Verständnisprüfung

Oben steht, dass es ohne Wirksamkeitsprüfung eine Anwesenheitsaussage bleibt.
Hier ist sie — damit der erste Zyklus nicht daran scheitert, dass sie erst
geschrieben werden muss.

**Bestanden ab 80 % je Baustein.** Die Antworten stehen in den verlinkten
Dokumenten; eine Frage, die ohne Nachschlagen zu beantworten ist, prüft nichts.

### Baustein 1 — CRA-Grundlagen

1. Welche beiden Teile hat Anhang I, und welcher betrifft das **Produkt**,
   welcher die **Pflichten über den Lebenszyklus**?
2. Ein Release behebt drei Schwachstellen und ändert nichts an Funktion oder
   Zweckbestimmung. Ist das eine wesentliche Änderung? Nenne die Fundstelle.
3. Ein Release fügt eine Funktion hinzu **und** behebt dabei eine Schwachstelle.
   Was verlangt Anhang I Teil II Nr. 2, und warum hilft es nicht, beides in
   einem Paket auszuliefern?
4. Ab wann läuft die 24-Stunden-Frist der Frühwarnung — ab Kenntnis, ab
   Bestätigung oder ab abgeschlossener Analyse?
5. An **wie viele** Empfänger geht eine Meldung nach Art. 14 Abs. 1, und
   zeitlich wie?
6. Seit wann gelten die Meldepflichten, und seit wann der übrige CRA?
7. Wer darf die EU-Konformitätserklärung dieses Produkts freigeben, und wer
   darf sie **nicht** freigeben?
8. Was ist der Unterschied zwischen einer Nicht-Konformität und einer
   Schwachstelle — und welcher Weg greift bei welcher?

### Baustein 2 — Secure Coding

1. Eine Adresse kommt aus einer Eingabe des Anwenders und der Server soll sie
   abrufen. Was ist die Regel, und wie sieht die Positivliste dafür aus?
2. Eine Speicherfunktion schreibt `data.get(feld, "")`. Welcher Fehler entsteht
   daraus, und warum fällt er nicht auf?
3. Was ist eine Spiegel-Liste, und woran erkennt man eine, bevor sie
   auseinanderläuft?
4. Ein Wächtertest prüft `"komponiere" in getsource(...)`. Warum ist er wertlos?
5. Eine Grenze wird in der Anwendung angehoben und greift nicht. Woran liegt es
   erfahrungsgemäß, und was ist zu prüfen?
6. Modelltext soll angezeigt werden. Welcher Weg, und warum nicht `{{ text }}`?
7. Fremdtext geht in einen Prompt. Was unterscheidet ihn vom Hinweis des
   Bearbeiters, und was folgt daraus für die Rahmung?
8. Ein Ereignis wird ausgelöst, und nichts geschieht. Welche zwei Richtungen
   dieses Fehlers gibt es, und welcher Prüfer fängt sie?

### Baustein 3 — Threat Modeling

1. Nenne die vier Vertrauensgrenzen dieser Anwendung.
2. Wann verlässt Inhalt das Haus in Richtung eines KI-Anbieters, wer bestätigt
   das, und wo steht es danach?
3. Welche Buchstaben von Anhang I Teil I Nr. 2 betreffen Vertraulichkeit und
   Integrität gespeicherter Daten?
4. Ein Mandant soll die Projektliste eines anderen nicht sehen. Wo greift die
   Regel, und ist sie fail-open oder fail-closed?
5. Was ist der Unterschied zwischen der Prüfung der **Herkunft** und der der
   **Signatur** eines Abbilds — und was belegt welche nicht?
6. Welches Risiko dieses Produkts steht heute als angenommenes Restrisiko im
   Abweichungsverzeichnis, mit der höchsten Einstufung?

### Baustein 4 — Incident Response

1. Zähle die drei Stufen und ihre Fristen nach Art. 14 auf — und sage je Stufe,
   **ab wann** die Frist läuft.
2. Eine Schwachstelle einer mitgelieferten Bibliothek wird in einem *anderen*
   Produkt ausgenutzt. Meldepflicht nach Art. 14? Begründe.
3. Nenne die beiden Fälle, in denen ein Vorfall „schwerwiegend" ist. Welcher
   wird häufiger übersehen?
4. Die Meldeplattform ist nicht erreichbar. Was ist der Rückfallweg, und was ist
   danach zu tun?
5. Was ist der Unterschied zwischen **Wiederherstellen** und **Übernehmen** einer
   Sicherung — und was ist beim Wiederherstellen eines fremden Archivs
   passiert?
6. Elf von elf Angaben der Übergabeliste an das CSIRT: welche davon können
   **wir** nicht liefern, und von wem sind sie zu erlangen?
7. Wer unterrichtet den Betreiber, und wer unterrichtet die Aufsichtsbehörde
   nach Art. 33 DSGVO, wenn in einer Installation Daten abfließen?

### Phishing-Simulation

Zwei Läufe im Jahr. Festgehalten wird **aggregiert**: Zahl der Nachrichten,
Quote der Klicks, Quote der Meldungen an die Anlaufstelle, mittlere Zeit bis zur
ersten Meldung. Keine namentliche Auswertung — eine Lernmaßnahme, die zur
Leistungskontrolle wird, beschädigt die Mitwirkung.

| Datum | Nachrichten | Klickquote | Meldequote | Zeit bis zur ersten Meldung |
|---|---|---|---|---|
| _(noch nicht durchgeführt)_ | | | | |

## Was dieses Dokument nicht regelt

- **Governance und Verantwortlichkeiten** — das ist IMPL-01, und es steht in
  [Governance und Verantwortlichkeiten](../cra/governance.md). Wer die Schulung
  anordnet und verantwortet, steht dort. (Hier stand bis zum 2. November 2026
  `docs/security/governance.md` — die Datei gibt es nicht; ein Verweis auf eine
  Datei, die nicht existiert, ist schlechter als keiner.)
- **Pflichtschulungen nach anderen Normen** (DSGVO Art. 39 Abs. 1 lit. b,
  NIS2 Art. 20 Abs. 2). Sie überschneiden sich inhaltlich; ein gemeinsamer
  Termin ist sinnvoll, die Nachweise bleiben aber getrennt, weil die Adressaten
  der Nachweise verschieden sind.
