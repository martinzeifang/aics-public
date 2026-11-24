# Bedienung: Projektliste, Werkzeugleiste, Bausteine

Die sechs Compliance-Module (CRA, NIS2, AI Act, DSGVO, WiBA, Risikobewertung)
sind fachlich verschieden und werden **gleich bedient**. Diese Seite beschreibt,
was in allen Modulen an derselben Stelle steht und dasselbe tut.

## Die Projektliste links

Ab zwei Einträgen bietet die Liste drei Werkzeuge:

| Werkzeug | Wirkung |
|---|---|
| 🔍 **Suche** | über Firma, Produkt und Projektname. Mehrere Begriffe werden UND-verknüpft, `Esc` leert das Feld. Unter dem Feld steht, wie viele Einträge noch sichtbar sind. |
| ↕ **Sortierung** | *Name A–Z* oder *Zuletzt geändert*. Bei „zuletzt geändert" wandern auch die Firmengruppen mit nach oben. |
| **Filter** | je Modul: Produktklasse (CRA), Framework (Risikobewertung), Einrichtungsklasse (NIS2), Rolle (DSGVO), Organisation/KI-System (AI Act), Berater. |

Ein Filter erscheint nur, wenn es im Bestand **mindestens zwei verschiedene
Werte** gibt — ein Auswahlfeld mit einer Option könnte nichts eingrenzen.
Firmengruppen lassen sich ein- und ausklappen; der Zustand bleibt erhalten, und
bei aktiver Suche sind alle Gruppen offen, damit kein Treffer verborgen bleibt.

## Die Projekt-Werkzeugleiste

Über dem Inhalt steht in jedem Modul dieselbe Leiste. Die sieben Handlungen
gelten dem **ganzen Projekt** und sind deshalb aus jedem Tab erreichbar.

| Handlung | Wirkung |
|---|---|
| 🤖 Automatische Massenbewertung | Mehrere Objekte auswählen, je Objekt ein KI-Lauf mit Fortschritt und Abbruch. |
| 🧮 Massenbewertung (Sammel-Prompt) | Ein gemeinsamer Prompt für mehrere Objekte; die Antwort wird vor der Übernahme angezeigt. |
| 🐙 Issues anlegen | Für die offenen Punkte des Projekts GitHub-/GitLab-Issues im Stapel anlegen; bereits verknüpfte Objekte werden übersprungen. |
| 🔄 Issue-Status abgleichen | Status und neue Kommentare der verknüpften Issues abrufen. |
| 📥 Issue-Feedback übernehmen | Inhalt und Kommentare in den Freitext des Objekts übernehmen. |
| 🧪 Neubewertung aus Issues | Lesende Übersicht: was die verknüpften Issues je Objekt sagen. |
| 📜 Audit-Log | Revisionspfad dieses Projekts — wer wann welche Handlung ausgelöst hat. |

Daneben stehen die Knöpfe, die es nur im jeweiligen Modul gibt (etwa
„➕ KI-System anlegen" im AI Act oder „🔍 Repo-Scan" im CRA).

!!! note "Der Abgleich bewertet nicht"
    Ein geschlossenes Issue belegt nicht, dass eine Anforderung erfüllt ist.
    Der Abgleich ändert deshalb **keine** Bewertung, sondern markiert das
    Objekt sichtbar als „⚠️ Neubewertung erforderlich" — mit Anlass
    („Issue geschlossen", „3 neue Kommentare") und Ticketnummer. Die Bewertung
    bleibt eine Entscheidung des Menschen.

### Was das Audit-Log zeigt

Alle Module schreiben in dieselbe revisionssichere, fortschreibungsgeschützte
Spur. Das Audit-Log am Projekt zeigt daraus die Einträge **dieses** Projekts:
Zeitpunkt, Handlung, handelnde Person und betroffenes Objekt. Wo ein Modul
zusätzlich ein Änderungsprotokoll auf Feldebene führt (Risikobewertung: vorher
und nachher je Risiko), steht es in derselben Liste — jede Zeile nennt ihre
Quelle.

Die Ansicht durchsucht die jüngsten Einträge des Moduls. Ist der Bestand
größer, sagt sie das ausdrücklich; der vollständige Revisionspfad steht der
Administration offen.

## Am einzelnen Objekt

Öffnet man eine Anforderung, eine Prüffrage, ein Risiko oder eine Kontrolle,
stehen unter den Bewertungsfeldern zwei Abschnitte.

### 🤖 KI-Bewertung

* **KI-Bewertung (Prompt → Antwort)** — Prompt erzeugen, in ein externes Modell
  einfügen, Antwort zurückgeben.
* **Automatische Bewertung** — ruft den konfigurierten Provider direkt auf; der
  Lauf ist live sichtbar und abbrechbar.
* **Neubewertung mit Issue-Feedback** — bezieht den Inhalt verknüpfter Issues
  ein.

Vor jedem Senden zeigt eine **Datenvorschau**, was übermittelt wird; bei einem
Cloud-Provider ist die Zustimmung Voraussetzung und wird im Revisionspfad
vermerkt. Im Prompt-Fenster lassen sich **eigene Hinweise** ergänzen; sie wirken
zusätzlich, ohne die geforderte Antwortform zu gefährden, und lassen sich je
Projekt merken.

Trägt ein Text einen **Herkunftshinweis**, stammt der Entwurf von der KI und
ist noch nicht fachlich geprüft. Ein Klick bestätigt die Prüfung mit Namen und
Zeitpunkt.

### 🔗 Verknüpfte Issues

* **Issue anlegen** — Provider, Repository, Titel und Beschreibung sind
  vorbelegt. Bleiben Provider und Repository leer, gilt die Repo-Konfiguration
  des Projekts.
* **Bestehendes verknüpfen** — ein vorhandenes Issue über seine URL anhängen.
* **Status abgleichen** — wie in der Projektleiste, nur für dieses Objekt.
* **Issue-Inhalt importieren** — Text einfügen oder aus den verknüpften Issues
  laden; der Text landet im Freitext, die Bewertung bleibt unverändert.
* **✕** löst eine Verknüpfung.

Die Markierung „⚠️ Neubewertung erforderlich" erscheint nicht nur im geöffneten
Editor, sondern auch in den **Listen** — dort wird sie gesucht.

## Die Hilfe fragen

Jedes Modul hat oben rechts den Knopf **❓ Hilfe**. Darin steht oben
**🤖 Frage zur Bedienung stellen**: Eine Frage in eigenen Worten eintippen —
„Warum ist mein Release rot?", „Wo trage ich den Verzicht auf einen Pentest
ein?" — und **Fragen** drücken.

Die Antwort stützt sich auf das Handbuch, auf den Hilfe-Abschnitt des
Bereichs, in dem Sie gerade sind, und auf den Stand (Modul, Bereich, Projekt).
Unter der Antwort stehen die **Fundstellen**: die Abschnitte, auf die sie sich
stützt. Was in der Dokumentation nicht steht, sagt die Antwort ausdrücklich —
sie denkt sich keine Menüpunkte aus.

Zwei Grenzen:

- **Keine Rechtsberatung.** Zur Auslegung einer Vorschrift beschreibt die
  Antwort, was die Anwendung dazu vorsieht, und verweist für die Bewertung auf
  fachliche Prüfung.
- **Die Frage geht an den eingestellten KI-Anbieter.** Vor dem Lauf fragt die
  Anwendung nach Ihrer Zustimmung und nennt den Anbieter. Bei einem
  Cloud-Anbieter verlässt der Fragetext mit dem Hilfe-Material das Haus; die
  Zustimmung wird im Revisionspfad festgehalten.
