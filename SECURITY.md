# Sicherheitshinweise und Meldung von Schwachstellen

Diese Datei ist die **verbindliche Richtlinie des Herstellers** für die Behandlung
von Schwachstellen der AI Compliance Suite. Sie ist keine Vorlage und kein Muster.

| | |
|---|---|
| **Hersteller** | Martin Zeifang, Finkenweg 42, 89150 Laichingen, Deutschland |
| **Produkt** | AI Compliance Suite — serverseitige Webanwendung, ausgeliefert als Container-Abbild |
| **Zentrale Anlaufstelle** | `security@cyberwoks.de` |
| **Maschinenlesbar** | <https://cyberwoks.de/.well-known/security.txt> (RFC 9116) |
| **Offenlegungskonzept** | <https://cyberwoks.de/sicherheit.html> |
| **Hinweisliste** | <https://cyberwoks.de/hinweise.html> |
| **Rechtsgrundlage** | Verordnung (EU) 2024/2847 (Cyber Resilience Act), Art. 13 und 14, Anhang I Teil II |

Dies ist keine Rechtsberatung.

## Unterstützte Fassungen

| Fassung | Unterstützt |
|---|---|
| jeweils zuletzt in Verkehr gebrachte Haupt-/Nebenfassung | ja |
| ältere Fassungen innerhalb des Unterstützungszeitraums | ja, durch kostenlosen Zugang zur zuletzt veröffentlichten Fassung (Art. 13 Abs. 10) |
| Fassungen nach Ende des Unterstützungszeitraums | nein |

Der **Unterstützungszeitraum** läuft von Oktober 2026 bis **Oktober 2031**.
Herleitung und Einzelheiten:
<https://martinzeifang.github.io/AI_Compliance_Suite/cra/unterstuetzungszeitraum/>

Ältere Abbilder bleiben im öffentlichen Paketverzeichnis abrufbar. **Der Betrieb
einer Fassung, die nicht mehr unterstützt wird, erfolgt ohne
Sicherheitsaktualisierungen und auf eigenes Risiko** (Hinweis nach Art. 13
Abs. 11).

## Eine Schwachstelle melden

Bitte **zuerst vertraulich** melden, damit eine korrigierte Fassung bereitsteht,
bevor Einzelheiten öffentlich werden.

1. **E-Mail an `security@cyberwoks.de`** — Betreff `[SECURITY] AI Compliance Suite`
2. **Security Advisory im öffentlichen Quellverzeichnis** —
   „Report a vulnerability" unter <https://github.com/martinzeifang/aics-public>

Beide Wege werden von einer Person gelesen, nicht von einem automatisierten
Werkzeug. Wer einen anderen Weg braucht, kann das in einer kurzen Nachricht an
die Anlaufstelle sagen; die Anlaufstelle ist nach Art. 13 Abs. 17 nicht auf
automatisierte Mittel beschränkt.

### Was eine Meldung tragen sollte

* betroffene Fassung oder Commit, betroffenes Modul
* Beschreibung und Auswirkung — was ist möglich?
* ein Weg zum Nachstellen, soweit vorhanden
* Protokolle oder Bildschirmfotos **ohne** personenbezogene oder Mandantendaten
* wie Du genannt werden möchtest, falls Du genannt werden möchtest

## Fristen, die wir uns selbst setzen

Die Verordnung beziffert diese Fristen nicht. Sie stehen hier, weil eine Zusage
ohne Maß keine ist — und sie gelten.

| Schritt | Frist |
|---|---|
| Eingangsbestätigung | 5 Werktage |
| erste Einschätzung (Schwere, Betroffenheit) | 10 Werktage |
| Behebung kritisch | 7 Tage |
| Behebung hoch | 30 Tage |
| Behebung mittel | 90 Tage |
| Veröffentlichung des Hinweises | mit der Bereitstellung der korrigierten Fassung |

Läuft eine Frist, wird der Melder **vor** ihrem Ablauf über den Stand
unterrichtet. Eine stillschweigend verstrichene Frist ist schlechter als eine
verlängerte.

## Was wir veröffentlichen — und wann

**Zu jeder behobenen Schwachstelle wird ein Hinweis veröffentlicht.** Das ist
keine Ermessensentscheidung, sondern Anhang I Teil II Nr. 4 der Verordnung.

| | |
|---|---|
| **Wo** | [Hinweisliste](https://cyberwoks.de/hinweise.html) als maßgebliche Fassung; zusätzlich als Security Advisory des öffentlichen Quellverzeichnisses und in den Freigabehinweisen |
| **Wann** | mit der Bereitstellung der korrigierten Fassung — nicht später, und nicht vorher |
| **Form** | strukturiert nach [`ADVISORY_VORLAGE.md`](.github/ADVISORY_VORLAGE.md); über die Advisory-Schnittstelle des Quellverzeichnisses zusätzlich maschinenlesbar abrufbar |

### Pflichtangaben je Hinweis

Ein Hinweis, dem eine dieser Angaben fehlt, wird nicht veröffentlicht, sondern
vervollständigt:

1. **Beschreibung** der Schwachstelle in verständlicher Sprache
2. **betroffene Fassungen** — von/bis, nicht „ältere Fassungen"
3. **behoben in** — die Fassung, die die Korrektur trägt
4. **Auswirkung und Schwere** — CVSS v3.1 oder v4.0 mit Vektor; die Zahl allein
   sagt nichts
5. **Angriffsweg** und Voraussetzungen (Authentisierung? Netzzugang? Rolle?)
6. **Behebungshinweis** — Fassungswechsel, und falls es eine Zwischenmaßnahme
   gibt, diese
7. **Kennung** — CVE oder GHSA, soweit vergeben
8. **Datum** der Veröffentlichung

**Eine Kennung wird beantragt**, sobald eine Schwachstelle Nutzer außerhalb des
eigenen Hauses betrifft — über das CNA-Programm des Quellverzeichnisses, sonst
über MITRE. Eine Schwachstelle ohne Kennung ist für einen Betreiber, der
mehrere Produkte überwacht, praktisch unsichtbar.

### Wann die Veröffentlichung aufgeschoben wird

Nur aus einem Grund: wenn die Veröffentlichung Nutzer **mehr** gefährdet als
sie schützt — etwa solange keine Korrektur bereitsteht und der Hinweis die
Ausnutzung erleichtern würde. Der Aufschub wird mit Grund und Datum
festgehalten und spätestens mit der korrigierten Fassung beendet. Ein Aufschub
„bis es gelegen kommt" gibt es nicht.

## Fremdkomponenten — ausdrücklich **im** Anwendungsbereich

Schwachstellen in mitgelieferten Fremdkomponenten gehören zu diesem Produkt.
Das ist Art. 13 Abs. 5 und 6 und nicht verhandelbar: Wer eine Komponente
integriert, verantwortet ihren Beitrag zur Sicherheit des Produkts.

Daraus folgen **zwei Pflichten in zwei Richtungen**:

**Nach oben (Art. 13 Abs. 6).** Stellen wir eine Schwachstelle in einer
integrierten Komponente fest — auch in quelloffener —, melden wir sie der
Person oder Einrichtung, die die Komponente herstellt oder wartet. Haben wir
eine Änderung entwickelt, die sie behebt, teilen wir den Code oder die
Unterlagen mit, soweit angemessen in maschinenlesbarer Form.

Das gilt für **eigene Funde**. Eine Schwachstelle, die der Hersteller der
Komponente selbst veröffentlicht hat und die wir über einen Abgleich übernehmen,
ist ihm bekannt; sie ihm zu melden wäre eine Meldung ohne Empfänger.

**Nach unten.** Betrifft eine Schwachstelle einer Fremdkomponente die
Sicherheitseigenschaften dieses Produkts, erscheint sie in der Hinweisliste wie
eine eigene — mit der Angabe, welche Komponente betroffen ist. Betreiber
sollen nicht die Stückliste gegen Schwachstellenkataloge halten müssen, um zu
erfahren, ob sie handeln müssen.

**Nicht betroffen heißt nicht verschwiegen.** Zu Schwachstellen in
Fremdkomponenten, die dieses Produkt nachweislich *nicht* berühren, geben wir
auf Anfrage eine Aussage mit Begründung ab — sie ist für einen Betreiber, der
einen Scanner-Treffer erklären muss, genauso wertvoll wie ein Hinweis.

## Anwendungsbereich

**Umfasst:**

* die Webanwendung AI Compliance Suite in allen unterstützten Fassungen
* die ausgelieferten Abbilder `ghcr.io/martinzeifang/ai_compliance_suite` und
  `ghcr.io/martinzeifang/aics-nginx`
* alle Module dieses Quellbaums
* die Veröffentlichungskette: Bauläufe, Signaturen, Stückliste, Herkunftsnachweis
* mitgelieferte Fremdkomponenten, soweit sie dieses Produkt betreffen (siehe oben)

**Nicht umfasst:**

* Fassungen nach Ende des Unterstützungszeitraums
* Veränderungen Dritter, Abspaltungen und Betrieb außerhalb der dokumentierten
  Betriebsvoraussetzungen
* die Infrastruktur einer Installation (Betriebssystem, Datenbank, Netz) — das
  ist Sache des Betreibers; wir unterrichten ihn, wenn ein Befund dorthin zeigt
* Angriffe, die zwingend körperlichen Zugriff voraussetzen
* Social Engineering und das Durchprobieren erbeuteter Kennwörter ohne
  technische Schwachstelle

## Keine rechtlichen Schritte bei redlicher Prüfung

Wer in gutem Glauben prüft und dabei

* keine Daten ausleitet, verändert oder dauerhaft speichert,
* fremde Installationen nicht beeinträchtigt,
* nicht weiter geht, als zum Nachweis nötig ist, und
* uns Zeit für eine Korrektur lässt,

handelt verantwortungsvoll. Wir leiten dagegen keine rechtlichen Schritte ein.
Prämien zahlen wir nicht; eine Nennung in der Hinweisliste und in den
Freigabehinweisen gibt es auf Wunsch.

## Wie diese Richtlinie geprüft wird

| Prüfung | Turnus |
|---|---|
| Vollständigkeit der Hinweise zu allen behobenen Schwachstellen der Fassung | je Release, im Release-Vorgang |
| Fristen eingehalten? Offene Meldungen ohne Rückmeldung? | vierteljährlich |
| Kontaktangaben und `security.txt` gültig, Ablaufdatum in der Zukunft | jährlich |
| Diese Richtlinie gegen den Verordnungstext gegengelesen | jährlich und bei Anlass |

**Fassung 2.0, 2. November 2026.** Fundstellen: Art. 13 Abs. 5, 6, 10, 11 und 17,
Art. 14, Anhang I Teil II Nr. 4, 5 und 6 der Verordnung (EU) 2024/2847. Gegen die
amtliche deutsche Fassung geprüft (ABl. L vom 20.11.2024).
