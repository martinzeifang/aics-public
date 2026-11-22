# Vorlage für einen Sicherheitshinweis

Diese Vorlage erfüllt die Pflichtangaben aus `SECURITY.md` und damit Anhang I
Teil II Nr. 4 der Verordnung (EU) 2024/2847. **Jedes Feld wird gefüllt oder
ausdrücklich als nicht zutreffend bezeichnet** — ein leeres Feld ist keine
Angabe, und ein Hinweis mit Lücken ist für einen Betreiber nicht bewertbar.

Verwendet wird sie an drei Stellen mit demselben Inhalt: in der
[Hinweisliste](https://cyberwoks.de/hinweise.html) (maßgeblich), als Security
Advisory des öffentlichen Quellverzeichnisses (maschinenlesbar) und in den
Freigabehinweisen der Fassung.

---

## AICS-JJJJ-NN — ⟨Titel in einem Satz, ohne Produktnamen⟩

| | |
|---|---|
| **Kennung** | ⟨CVE-…⟩ / ⟨GHSA-…⟩ / `beantragt am JJJJ-MM-TT` / `nicht vergeben — nur eigene Installation betroffen` |
| **Veröffentlicht** | JJJJ-MM-TT |
| **Betroffene Fassungen** | ⟨ab X.Y.Z bis einschließlich A.B.C⟩ |
| **Behoben in** | ⟨A.B.C+1⟩ |
| **Betroffene Komponente** | ⟨Modul der Suite⟩ / ⟨Name der Fremdkomponente samt Fassung⟩ |
| **Schwere** | ⟨kritisch / hoch / mittel / niedrig⟩ — CVSS ⟨4.0 oder 3.1⟩ ⟨Punktwert⟩ (`⟨Vektor⟩`) |
| **Melder** | ⟨Name oder „anonym"⟩ / `eigener Fund` / `Abgleich mit dem Komponentenhersteller` |

### Beschreibung

⟨Was ist der Fehler, in verständlicher Sprache. Keine Fachbegriffe ohne
Erklärung, kein Ausnutzungscode.⟩

### Auswirkung

⟨Was kann ein Angreifer erreichen — welche Daten, welche Funktion, welcher
Mandant. Wenn mehrere Mandanten betroffen sein können, steht das hier.⟩

### Voraussetzungen für den Angriffsweg

| Frage | Antwort |
|---|---|
| Netzzugang nötig? | ⟨aus dem Internet / nur im internen Netz / nur lokal⟩ |
| Anmeldung nötig? | ⟨nein / ja, jedes Konto / ja, mit Rolle ⟨…⟩⟩ |
| Mitwirkung eines Nutzers nötig? | ⟨nein / ja — ⟨was⟩⟩ |
| Betrifft die Angabe nur bestimmte Konfigurationen? | ⟨nein / ja — ⟨welche⟩⟩ |

### Was zu tun ist

1. ⟨Auf Fassung A.B.C+1 wechseln — der Regelfall.⟩
2. ⟨Zwischenmaßnahme, falls der Wechsel nicht sofort möglich ist. Wenn es keine
   gibt, steht hier ausdrücklich „Eine Zwischenmaßnahme gibt es nicht".⟩
3. ⟨Was nach dem Wechsel zu prüfen ist — etwa: Sitzungen beenden, Zugangstoken
   erneuern, Protokolle auf Anzeichen durchsehen.⟩

### Anzeichen einer Ausnutzung

⟨Woran ein Betreiber erkennt, ob es ihn getroffen hat: Protokollmuster,
Einträge im Revisionspfad, Dateinamen. Wenn es keine gibt, steht das hier —
„nicht feststellbar" ist eine wichtige Angabe und kein Mangel des Hinweises.⟩

### Zeitlicher Ablauf

| Datum | Ereignis |
|---|---|
| JJJJ-MM-TT | Meldung eingegangen / eigener Fund |
| JJJJ-MM-TT | Eingangsbestätigung |
| JJJJ-MM-TT | Einschätzung abgeschlossen |
| JJJJ-MM-TT | ⟨an den Hersteller der Komponente gemeldet — nur bei eigenem Fund in Fremdcode, Art. 13 Abs. 6⟩ |
| JJJJ-MM-TT | korrigierte Fassung bereitgestellt |
| JJJJ-MM-TT | Hinweis veröffentlicht |

---

## Wenn das Produkt **nicht** betroffen ist

Für Schwachstellen einer Fremdkomponente, die dieses Produkt nachweislich nicht
berühren, wird kein Hinweis veröffentlicht, aber auf Anfrage eine Aussage
abgegeben. Sie trägt dieselbe Form und genau eine zusätzliche Angabe:

| | |
|---|---|
| **Status** | `nicht betroffen` |
| **Begründung** | ⟨Welcher Code wird nicht erreicht, welche Funktion nicht benutzt, welche Voraussetzung liegt nicht vor. „Nicht betroffen" ohne Begründung ist eine Behauptung.⟩ |

Für einen Betreiber, der einen Treffer seines Prüfwerkzeugs erklären muss, ist
diese Aussage genauso wertvoll wie ein Hinweis — und sie ist der einzige Weg,
einen Fehlalarm belastbar auszuräumen.

---

**Zur Fristenlage:** Die Veröffentlichung eines Hinweises ist **nicht** die
Meldung nach Art. 14. Eine aktiv ausgenutzte Schwachstelle wird zusätzlich und
unabhängig an den als Koordinator benannten CSIRT und die ENISA gemeldet — mit
24 Stunden für die Frühwarnung. Der Weg dorthin steht in
[Meldewege nach Art. 14](https://martinzeifang.github.io/AI_Compliance_Suite/cra/meldewege-art14/).
