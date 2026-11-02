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

## Nachweis-Tracker

Eine Zeile je durchgeführtem Baustein. Personen werden **mit Rolle** geführt;
Namen bleiben in der Personalakte.

| Datum | Baustein | Teilnehmer (Rollen) | Unterlage (Version) | Wirksamkeitsprüfung | Durchgeführt von |
|---|---|---|---|---|---|
| _(noch kein Zyklus durchgeführt)_ | | | | | |

> **Offener Punkt zu IMPL-06:** Der erste Zyklus ist durchzuführen und hier
> einzutragen. Erst damit ist der Prüfpunkt erfüllt; das Konzept allein
> erfüllt ihn nicht.

## Was dieses Dokument nicht regelt

- **Governance und Verantwortlichkeiten** — das ist IMPL-01 (#858),
  `docs/security/governance.md`. Wer die Schulung anordnet und verantwortet,
  steht dort.
- **Pflichtschulungen nach anderen Normen** (DSGVO Art. 39 Abs. 1 lit. b,
  NIS2 Art. 20 Abs. 2). Sie überschneiden sich inhaltlich; ein gemeinsamer
  Termin ist sinnvoll, die Nachweise bleiben aber getrennt, weil die Adressaten
  der Nachweise verschieden sind.
