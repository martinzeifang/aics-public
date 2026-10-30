/**
 * Die beiden CRA-Prozesse als Wiki-Seiten.
 *
 * Der Anwender fragt nicht „was macht der Tab ‚Konformität‘?", sondern „wie
 * werde ich fertig?". Eine Tab-für-Tab-Beschreibung beantwortet das nicht —
 * sie setzt voraus, dass man die Reihenfolge schon kennt. Diese Seiten
 * beschreiben den Weg: erst das Produkt CRA-ready machen (einmalig), danach
 * jedes Release nachweisen (Tagesgeschäft).
 *
 * Die Zweiteilung ist nicht erfunden, sie steckt in der Anwendung:
 * `cra/konformitaet_gate.evaluate` liefert `phase` (produkt|release) und
 * trennt `produkt_punkte` von `release_punkte` (#1742).
 */

export const CRA_PROZESS = [

// ───────────────────────────────────────────────────────────────────────────
['Der CRA-Weg in zwei Phasen', `# Der CRA-Weg in zwei Phasen

Der Cyber Resilience Act verlangt zweierlei, und die beiden Dinge haben einen
sehr verschiedenen Rhythmus:

| | Phase 1 — **CRA-ready** | Phase 2 — **Release** |
|---|---|---|
| Wann | einmalig je Produkt | bei **jeder** Veröffentlichung |
| Frage | Ist das Produkt überhaupt konform? | Ist es konform **geblieben**? |
| Aufwand | hoch, einmalig | gering, wenn Phase 1 steht |
| Ergebnis | Feststellung „CRA-ready" | freigegebener Release-Vorgang |

Die Suite trennt beides sichtbar. Im Tab **🚦 Releases** steht Phase 1 als
**eine Zeile ganz oben** — dort arbeitet niemand täglich, aber ohne sie ist
jeder Release-Nachweis bodenlos. Darunter die Vorgänge je Release.

## Warum das wichtig ist

Wer beide Phasen vermischt, macht bei jedem Patch die volle Arbeit und wird
nicht fertig. Der CRA sieht das ausdrücklich anders: Nach **Erwägungsgrund 39**
gilt eine Sicherheitsaktualisierung, die die Zweckbestimmung nicht verändert,
**nicht** als wesentliche Änderung — und zwar auch dann nicht, wenn sie
Funktionen oder Leistung ändert, solange das allein dem Senken des
Cybersicherheitsrisikos dient.

Damit entfallen für ein Sicherheitsupdate vier teure Punkte:

- die Risikoabschätzung fortschreiben,
- die Konformitätsbewertung wiederholen,
- Anhang VII nachziehen,
- die EU-Konformitätserklärung neu ausstellen.

Die Suite rechnet das mit: Im Release-Vorgang erklären Sie die **Art des
Releases**, und die vier Punkte erscheinen nur dort, wo sie fällig sind.

## Die vier Arten von Prüfpunkten

Jeder Punkt in der Release-Checkliste gehört zu einer von vier Arten. Die
Unterscheidung erspart Arbeit und verhindert Scheinarbeit:

- **🔢 gerechnet** — Die Anwendung weiß die Antwort und fragt nicht. Beispiel:
  „SBOM liegt für diese Version vor". Solche Punkte lassen sich nicht von Hand
  abhaken; sie ändern sich, wenn sich die Akte ändert.
- **✍️ Entscheidung** — Nur ein Mensch kann sie treffen, mit Begründungspflicht.
  Beispiel: „Ist dieses Release eine wesentliche Änderung?"
- **♻️ gleichbleibend** — Einmal gesetzte Angaben, je Release nur zu
  bestätigen. Beispiel: „Meldestelle unverändert erreichbar".
- **🔁 Neubewertung** — Erscheint **nur** nach einer erklärten wesentlichen
  Änderung. Das sind die vier teuren Punkte von oben.

> **Merksatz:** Ein Prüfpunkt, der sich rechnen lässt, darf den Menschen nicht
> fragen — sonst wird er nicht sorgfältiger beantwortet, sondern unaufrichtiger.
`, 'cra__releases.png'],

// ───────────────────────────────────────────────────────────────────────────
['Phase 1 — Das Produkt CRA-ready machen', `# Phase 1 — Das Produkt CRA-ready machen

Einmalige Arbeit je Produkt. Ziel ist eine **grüne Phase-1-Ampel** und die
Feststellung „CRA-ready". Erst danach ist das Tagesgeschäft in Phase 2
tragfähig.

Arbeiten Sie die Schritte der Reihe nach ab — jeder baut auf dem vorigen auf.

## Schritt 1 · Produkt anlegen und einordnen

**Wo:** Modul **CRA** → Projekt anlegen (oder über **Firmen** → Produkt).

Tragen Sie Firma, Produktname und die **Produktklasse** ein. Die Klasse
entscheidet über alles Weitere, denn sie bestimmt, welche
Konformitätsbewertungsverfahren überhaupt offenstehen:

| Klasse | Bedeutung | Zulässige Wege |
|---|---|---|
| Standard | nicht in Anhang III/IV gelistet | Modul A (Selbstbewertung) genügt |
| Wichtig, Klasse I | Anhang III Klasse I | Modul A möglich, B+C/H empfohlen |
| Wichtig, Klasse II | Anhang III Klasse II | **kein** Modul A |
| Kritisch | Anhang IV | **kein** Modul A, Zertifizierung nötig |

> Die Einordnung ist Ihre Entscheidung — Anhang III und IV sind Produktlisten,
> die gelesen werden müssen. Die Suite rechnet nur die **Folge** daraus.

## Schritt 2 · Die 32 Anforderungen bewerten

**Wo:** Tab **✅ Anforderungen** (Gruppe „Compliance & Register").

Anhang I des CRA, als 32 Anforderungen aufbereitet. Jede wird auf einer Skala
**0–5** bewertet; **erfüllt gilt ab 4**. Für jede Anforderung gehören dazu:

- eine **Begründung** (was ist umgesetzt?),
- ein **Nachweis** (Dokument, Repository-Verweis, Testbericht),
- bei Abweichungen eine **risikobasierte Begründung**.

Hilfreich: Der Knopf **🤖 Automatische Bewertung** schlägt eine Bewertung aus
dem vor, was die Suite über Ihr Produkt bereits weiß (Schwachstellen, SBOM,
verknüpfte Risiken). **Der Entwurf ersetzt die Prüfung nicht** — er wird als
KI-generiert gekennzeichnet und muss fachlich bestätigt werden.

## Schritt 3 · Pflicht-Dokumentation ausfüllen

**Wo:** Tab **📋 Dokumentation**.

Die Angaben, auf die sich später alles stützt:

- **SBOM** (Anhang I Teil II Nr. 1) — Stückliste der Fremdkomponenten. Aus dem
  Repository, aus einem Ablageort oder vom Container-Image als signierte
  Attestation.
- **PSIRT / Meldestelle** (Anhang I Teil II Nr. 6) — wohin melden Dritte
  Schwachstellen? Eine Adresse, die auch gelesen wird.
- **Support-Zeitraum** (Art. 13 Abs. 8) — mindestens fünf Jahre; darunter nur
  mit Begründung.
- **Update-Kanal und Zusagen** (Anhang I Teil II Nr. 2 und 8) — wie erreichen
  Sicherheitsupdates den Anwender, kostenlos und getrennt von Funktionsupdates?
- **Offenlegungs-Richtlinie** (Anhang I Teil II Nr. 5).

## Schritt 4 · Risiken bewerten

**Wo:** Tab **🔍 Risikoanalyse** → verknüpfte Risikobewertung.

Art. 13 Abs. 2 verlangt eine Risikobeurteilung. Legen Sie eine Risikobewertung
an (oder verknüpfen Sie eine vorhandene) und bewerten Sie die Risiken. Offene
**kritische oder hohe** Risiken verhindern später die Freigabe.

## Schritt 5 · Technische Dokumentation (Anhang VII)

**Wo:** Tab **🔗 Traceability**.

Anhang VII listet, was die technische Dokumentation enthalten muss. Die Suite
führt die Bausteine als Checkliste und erkennt viele **automatisch** aus dem,
was Sie bereits erfasst haben (SBOM, Threat-Model, Schwachstellen, Risiken).
Ergänzen Sie, was fehlt.

## Schritt 6 · Bewertungsweg abschließen

**Wo:** Tab **✅ Konformität**.

Wählen Sie das Verfahren nach Anhang VIII (Modul A, B+C, H oder EUCC), haken
Sie die Nachweis-Checkliste ab und setzen Sie **„Bewertungsweg abgeschlossen"**.

> **Wichtig:** Dieser Haken gilt für das **Produkt**, nicht je Release. Jedes
> Release übernimmt ihn von hier. Ohne ihn lässt sich **kein** Release
> einreichen oder freigeben und keine EU-Konformitätserklärung ausstellen.

Bei B+C, H und EUCC ist eine notifizierte Stelle beteiligt — ohne deren
Kennnummer lässt sich der Haken nicht setzen.

## Schritt 7 · EU-Konformitätserklärung ausstellen

**Wo:** Tab **✅ Konformität**, Abschnitt „EU-Konformitätserklärung (Anhang V)".

Die Erklärung nach Art. 28 i. V. m. Anhang V. Pflichtangaben sind unter anderem
Produktidentifikation, Hersteller mit Anschrift, Gegenstand der Erklärung sowie
Ort, Datum und Unterzeichner mit Funktion. Der Satz zur alleinigen
Verantwortung und die Konformitätsaussage sind Gesetzesformeln und werden vom
Dokument selbst gesetzt.

Download im Tab **📄 Berichte** → „EU-Konformitätserklärung".

## Schritt 8 · CE-Kennzeichnung

**Wo:** Tab **✅ Konformität**, Abschnitt CE.

Erst wenn die Erklärung vorliegt, darf das CE-Zeichen angebracht werden.
Dokumentieren Sie **wo** (z. B. Info-Dialog, Handbuch, Verpackung) und **wann**.

## Schritt 9 · CRA-ready feststellen

**Wo:** Tab **🚦 Releases**, oberste Zeile → **„CRA-ready feststellen"**.

Die Feststellung ist **nur bei grüner Phase-1-Ampel möglich**. Sind noch Punkte
offen, nennt die Anwendung sie beim Namen — mit einem Sprung dorthin, wo sich
der Punkt pflegen lässt.

Die Feststellung braucht die Berechtigung **cra:approve** und hält den
Rechenstand fest, auf den sie sich bezog. Ändert sich die Akte später so, dass
der heutige Stand die Feststellung nicht mehr trägt, erscheint ein Hinweis
**„überholt"** — gelöscht wird sie nicht, ihr wird widersprochen.

---

**Damit ist das Produkt CRA-ready.** Ab hier beginnt Phase 2, und die ist bei
jedem Release deutlich kürzer.
`, 'cra__konformitt.png'],

// ───────────────────────────────────────────────────────────────────────────
['Phase 2 — Ein Release veröffentlichen', `# Phase 2 — Ein Release veröffentlichen

Das Tagesgeschäft. Vieles ist jedes Mal gleich, anderes muss jedes Mal geprüft
werden. Wenn Phase 1 steht, sind das meist wenige Minuten.

**Wo:** Modul **CRA** → Tab **🚦 Releases**.

## Schritt 1 · Vorgang anlegen

Version oben eingeben (z. B. \`2.3.0\`) und **„Vorgang öffnen"**. Für eine
Version ohne Vorgang wird **nichts** angelegt, nur angeboten — ein Tippfehler
im Link soll keinen leeren Entwurf erzeugen. Mit **„Vorgang für … anlegen"**
geht es los.

Der Vorgang erbt vom Produkt, was gleich bleibt: Bewertungsweg, Abschluss,
Angaben zur notifizierten Stelle. Das steht sichtbar dabei
(„Aus der Produktbewertung übernommen").

## Schritt 2 · Die Art des Releases erklären

Der wichtigste Schritt, denn er bestimmt den Aufwand:

| Art | Bedeutung | Folge |
|---|---|---|
| **Sicherheitsupdate** | behebt Schwachstellen, Zweckbestimmung unverändert | keine Neubewertung (Erwägungsgrund 39) |
| **Funktionsupdate** | neue oder geänderte Funktionen | hängt vom Umfang ab |
| **Wesentliche Änderung** | Art. 3 Nr. 30 | volle Neubewertung, Ampel **rot** bis erledigt |

Die Suite schlägt eine Begründung am Verordnungstext entlang vor — **gespeichert
wird erst auf Ihren Klick**, und eine bereits gegebene Antwort wird nie
überschrieben.

Anschließend rechnet sie gegen Ihre eigene Akte und meldet Widersprüche:

- „Sicherheitsupdate" erklärt, aber die Kernfrage mit „ja" beantwortet,
- „Sicherheitsupdate" mit **neu aufgenommenen** Fremdkomponenten (angehobene
  Versionen sind der Normalfall und zählen nicht),
- „Funktionsupdate", das zugleich Schwachstellen behebt — Anhang I Teil II
  Nr. 2 verlangt, soweit technisch machbar, die **getrennte** Bereitstellung.

> Erwägungsgrund 39 schließt die naheliegende Umgehung ausdrücklich aus: Ob
> eine Funktionsaktualisierung allein oder zusammen mit einer
> Sicherheitsaktualisierung ausgeliefert wird, ändert an ihrer Beurteilung
> nichts.

## Schritt 3 · Die Checkliste durchgehen

Die Punkte sind nach den vier Arten gruppiert:

- **🔢 Gerechnet** — nur ansehen. Steht hier etwas auf „offen", pflegen Sie es
  an der verlinkten Stelle („→ hier pflegen"), nicht hier.
- **✍️ Entscheidung** — beantworten und begründen.
- **♻️ Gleichbleibend** — bestätigen, dass die Angabe noch stimmt. Die
  Bestätigung hält fest, dass jemand hingesehen hat.
- **🔁 Neubewertung** — erscheint nur bei erklärter wesentlicher Änderung.

Typische gerechnete Punkte: SBOM zur Version vorhanden, keine offenen
kritischen Schwachstellen, Release im zugesagten Support-Zeitraum, keine
überfällige Meldefrist nach Art. 14, Anhang VII vollständig,
EU-Konformitätserklärung für diese Version ausgestellt.

## Schritt 4 · Zur Prüfung geben

Knopf **📤 Zur Prüfung geben**. Was die Freigabe ausnahmslos verhindern würde,
hält schon hier auf — mit der Auskunft, wo es zu beheben ist. Eine **rote
Ampel** darf dagegen eingereicht werden: Darüber soll die Prüfung ja gerade
entscheiden.

## Schritt 5 · Freigeben — durch eine zweite Person

**Wer einreicht, gibt nicht frei.** Die Freigabe braucht

- die Berechtigung **cra:approve** und
- ein **anderes Konto** als das einreichende (Vier-Augen-Prinzip, Art. 13
  Abs. 1).

Bei roter Ampel ist eine ausdrückliche Bestätigung nötig; die offenen Punkte
bleiben im Vorgang sichtbar. Alternativ **↩️ Zurückweisen** mit Begründung —
der Vorgang geht zurück in den Entwurf.

## Schritt 6 · Nachweis erzeugen und archivieren

- **📄 Konformitätsnachweis (PDF/DOCX)** — das Dokument mit Rechtsgrundlage je
  Anforderung, begründeten Abweichungen und Anhang-VII-Stand.
- **📦 Nachweis archivieren** — legt die Fassung unveränderlich mit SHA-256 ab.
  Das ist das Stück, auf das sich eine Marktüberwachungsbehörde stützt.

Für Kunden gibt es zusätzlich die **Kundenfassung** — derselbe Nachweis ohne
interne Details.

## Schritt 7 · Als veröffentlicht markieren

Nach der tatsächlichen Auslieferung: **🚀 Als veröffentlicht markieren**. Damit
ist der Vorgang geschlossen und die Akte vollständig.

---

## Kurzfassung für den Alltag

\`\`\`
Sicherheitsupdate:   Vorgang anlegen → Art erklären → Gleichbleibendes
                     bestätigen → einreichen → freigeben (2. Person)
                     → Nachweis archivieren → veröffentlicht
                     ≈ 10 Minuten

Funktionsupdate:     wie oben, zusätzlich Nutzerinformation und ggf.
                     Neubewertungs-Umfang

Wesentliche Änderung: zusätzlich alle vier Neubewertungs-Punkte —
                     faktisch ein Rücksprung in Phase 1
\`\`\`
`, 'cra__releases.png'],
];
