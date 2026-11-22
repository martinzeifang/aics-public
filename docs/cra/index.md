# CRA-Dossier der AI Compliance Suite

Dieses Dossier ist die Nachweisführung für die **AI Compliance Suite als Produkt**
nach der Verordnung (EU) 2024/2847 (Cyber Resilience Act). Es ist das Gegenstück zum
[AI-Act-Dossier](../ai/aiact-dossier/index.md): dort die KI-Verordnung, hier der CRA.

!!! info "Was dieses Dossier ist — und was nicht"
    Es ist die **öffentliche Seite** der Nachweisführung: Entscheidungen, Prozesse und
    Zusagen, die ein Kunde oder eine Marktüberwachungsbehörde ohne Zugang zu unseren
    Systemen nachlesen können soll.

    Die **technische Dokumentation nach Anhang VII** ist etwas anderes. Sie wird im
    CRA-Modul der Suite selbst geführt — mit Schwachstellenregister, Software-Stückliste
    je Artefakt, Bedrohungsmodell, Risikobewertung und Testnachweisen — und der Behörde
    auf begründetes Verlangen vorgelegt. Sie steht nicht hier.

## Einordnung

| | |
|---|---|
| **Rolle** | Hersteller im Sinne des Art. 3 Nr. 13 |
| **Produkt** | AI Compliance Suite — serverseitige Webanwendung, ausgeliefert als Container-Abbild |
| **Produktklasse** | Standardprodukt (siehe [Produktklassifizierung](produktklassifizierung.md)) |
| **Bewertungsweg** | Modul A — interne Fertigungskontrolle, Anhang VIII |
| **Notifizierte Stelle** | nicht vorgesehen und nicht beteiligt |
| **Unterstützungszeitraum** | Oktober 2026 bis Oktober 2031 (siehe [Unterstützungszeitraum](unterstuetzungszeitraum.md)) |

## Zeitlicher Anwendungsbereich

| Gegenstand | Gilt ab |
|---|---|
| Meldepflichten nach Art. 14 | **11. September 2026** — gilt bereits |
| Kapitel IV (Notifizierung von Konformitätsbewertungsstellen) | 11. Juni 2026 |
| Übrige Pflichten, CE-Kennzeichnung, EU-Konformitätserklärung | **11. Dezember 2027** |

Art. 71 Abs. 2. Die Meldepflichten sind damit keine Vorbereitung mehr, sondern laufende
Pflicht — [Meldewege nach Art. 14](meldewege-art14.md) ist deshalb das Dokument mit
Vorrang.

## Die Dokumente

| Dokument | Beantwortet | Fundstelle |
|---|---|---|
| [Produktklassifizierung und Bewertungsweg](produktklassifizierung.md) | Welche Klasse, welcher Weg, und warum nicht Anhang III/IV | Art. 7, Art. 32, Anhang III/IV |
| [Governance und Verantwortlichkeiten](governance.md) | Wer verantwortet die Cybersicherheit des Produkts | Art. 13 Abs. 1, Erwägungsgrund 34 |
| [Meldewege nach Art. 14](meldewege-art14.md) | Wer meldet was, an wen, in welcher Frist | Art. 14, Art. 16 |
| [Unterstützungszeitraum](unterstuetzungszeitraum.md) | Wie lange, wie hergeleitet, wie kommuniziert | Art. 13 Abs. 8 und 19, Anhang II Nr. 7 |
| [Offenlegung und Austausch zu Schwachstellen](schwachstellen-offenlegung.md) | Was wir veröffentlichen, was wir Upstream melden | Anhang I Teil II Nr. 4, Art. 13 Abs. 6 |
| [Lieferkette und Fremdkomponenten](lieferkette.md) | Sorgfalt bei Komponenten Dritter | Art. 13 Abs. 5 |
| [Aktualisierungen, Signaturprüfung und Rückfall](update-und-rueckfall.md) | Wie eine Aktualisierung sicher ankommt, und wie der Rückweg aussieht | Anhang I Teil II Nr. 7, Teil I Nr. 2 Buchst. c |
| [Kennzeichnung und Herstellerangaben](kennzeichnung-und-herstellerangaben.md) | Woran das Produkt zu erkennen ist, und wer es herstellt | Art. 13 Abs. 15 bis 17 |
| [Korrekturmaßnahmen bei Nicht-Konformität](korrekturmassnahmen.md) | Was geschieht, wenn die Konformität selbst in Frage steht | Art. 13 Abs. 21 |
| [Marktüberwachung](marktueberwachung.md) | Unterlagen auf Verlangen, Zusammenarbeit, Ablage | Art. 13 Abs. 22 |
| [Einstellung der Betriebstätigkeit](einstellung-betriebstaetigkeit.md) | Wer wird wann unterrichtet, und was bleibt danach | Art. 13 Abs. 23 |
| [Schulung und Awareness](../security/awareness.md) | Wer muss was wissen, in welchem Takt, und woran es sich belegen lässt | Art. 13 Abs. 1, Erwägungsgrund 34 |
| [Aufbewahrung der Nachweise](aufbewahrung.md) | Was wird zehn Jahre aufbewahrt, und wo | Art. 13 Abs. 9, 13 und 18 |
| [Abweichungen und offene Umsetzung](abweichungen.md) | **Was nicht erfüllt ist — und in welcher Kategorie** | Art. 13 Abs. 2 bis 4 |

!!! tip "Welches Dokument man zuerst liest"
    [Abweichungen und offene Umsetzung](abweichungen.md). Es ist die Gegenprobe
    zum Rest und trennt drei Dinge, die rechtlich verschieden sind: was auf
    dieses Produkt nicht zutrifft (mit Begründung nach Art. 13 Abs. 4), was
    abgewogen und als Restrisiko angenommen ist, und was schlicht offen ist.

    Ein Dossier ohne dieses Dokument liest sich wie eine Erfüllungsmeldung. Mit
    ihm ist es eine Akte.

## Öffentliche Angaben

Was den **Nutzern** zur Verfügung stehen muss (Anhang II), steht nicht hier, sondern auf
der Produktseite des Herstellers:

* [CRA-Informationen für den Nutzer](https://cyberwoks.de/cra.html) — Anhang II Nr. 1 bis 9
* [EU-Konformitätserklärung](https://cyberwoks.de/konformitaet.html) — dauerhafte Adresse
* [Sicherheit und Meldung von Schwachstellen](https://cyberwoks.de/sicherheit.html) — zentrale Kontaktstelle und Offenlegungskonzept
* [Sicherheitshinweise](https://cyberwoks.de/hinweise.html) — Hinweise zu behobenen Schwachstellen

## Wie dieses Dossier gepflegt wird

Jedes Dokument trägt eine Fassung und ein Datum. Geändert wird es aus einem Anlass, nicht
nach Kalender: eine neue Produktfassung mit wesentlicher Änderung, ein Vorfall, eine
geänderte Zusage oder eine Erkenntnis aus der Marktbeobachtung. Die Überprüfung ist Teil
des Release-Vorgangs im CRA-Modul; der dort gerechnete Prüfpunkt verlangt für jede
Behauptung einen Nachweis in der Akte.

!!! warning "Fundstellen"
    Artikel- und Anhangsnummern in diesem Dossier sind gegen die amtliche deutsche
    Fassung geprüft. Maßgeblich ist stets der im Amtsblatt der Europäischen Union
    veröffentlichte Text. Eine erfundene Fundstelle ist in einer Nachweisakte schlechter
    als keine — sie liest sich wie eine Feststellung.

**Fassung 1.1, 4. November 2026.**

??? note "Was sich gegenüber Fassung 1.0 geändert hat"
    * **Die Sicherungen sind verschlüsselt** (Fassung 8.3.4 des Produkts,
      eingeschaltet am 4. November 2026). Abweichung **B2** verkleinert sich
      damit auf die Nachweisdateien und den Datenbestand; die Messung dort ist
      nachgezogen. Der zweite Aufbewahrungsort war ausdrücklich an diese
      Verschlüsselung gebunden und ist jetzt möglich.
    * **Ein Widerspruch in B2 ist beseitigt:** Unter den ausgleichenden
      Maßnahmen stand „Nachweisdateien liegen verschlüsselt (`.enc`)", während
      die Messung im selben Abschnitt `encrypt_evidence: false` und null
      `.enc`-Dateien auswies. Eine ausgleichende Maßnahme, die es nicht gibt,
      ist in einem Abweichungsverzeichnis der schwerste Eintrag.
    * **[Schulung und Awareness](../security/awareness.md) ist aufgenommen.**
      Das Dokument bestand, war aber aus dem Dossier nicht erreichbar und in
      keiner Navigation; sein Kopf verwies auf eine Datei, die im
      veröffentlichten Baum nicht existiert.
