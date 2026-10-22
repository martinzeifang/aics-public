# Compliance-Audit

Das Compliance-Audit erhebt per Fragenkatalog, **wie weit eine Organisation
gegenüber einem Framework tatsächlich ist**, und meldet ihr das Ergebnis als
*Wasserstandsmeldung* zurück: vollständig, weitgehend, teilweise oder nicht
compliant.

Es ist damit die Standortbestimmung am Anfang eines Vorhabens — nicht die
gutachterliche Äußerung am Ende. Dafür gibt es das
[Gutachten-Modul](gutachten.md), in das sich ein Audit überführen lässt.

!!! info "Im Grundpreis enthalten"
    Das Compliance-Audit gehört wie die Risikobewertung zu den Grundpreis-Modulen
    und ist bei jeder gültigen Lizenz nutzbar. In den Einstellungen lässt es sich
    ausblenden, wenn es nicht gebraucht wird.

## Abgrenzung zum Gutachten

|  | Compliance-Audit | Gutachten |
| --- | --- | --- |
| Zweck | Umsetzungsstand erheben | gutachterlich Stellung nehmen |
| Ergebnis | Wasserstandsmeldung mit Stufe | Gutachten (ggf. für ein Gericht) |
| Adressat | der Kunde selbst | Auftraggeber, Gericht, Dritte |
| Lizenz | im Grundpreis | kostenpflichtig, nur mit expliziter Nennung |

Bis Version 7.3.0 war das Audit Teil des Gutachten-Moduls. Seit **7.4.0** ist es
ein eigenes Modul mit eigener Navigation, eigener Lizenzierung und eigenen
Berechtigungen. Die Verbindung bleibt: aus einem Audit lässt sich ein Gutachten
ableiten, wobei die übernommenen Befunde bewusst leer bleiben und persönlich neu
formuliert werden müssen (§ 407a ZPO).

## Ablauf

1. **Audit anlegen** und einer Firma zuordnen. Die Zuordnung ist Grundlage für
   Mandantentrennung und Abrechnung.
2. **Framework-Bibliothek füllen**: Regulierungstext herunterladen oder als PDF
   hochladen, dann in Abschnitte einlesen. Die Fragen bleiben auf diese
   Fundstellen bezogen.
3. **Fragen erzeugen**: Prompt generieren, von der KI beantworten lassen,
   Fragen importieren. Eigene Fragen lassen sich ergänzen.
4. **Fragebogen exportieren** (XLSX), beim Kunden ausfüllen lassen und
   **wieder importieren**.
5. **Erfüllung setzen** je Frage: erfüllt · teilweise · nicht erfüllt ·
   nicht anwendbar · offen.
6. **Wasserstandsmeldung erstellen** — die Stufe wird gerechnet, die KI
   formuliert den Text für den Kunden.

## Wie die Stufe zustande kommt

Die Compliance-Stufe ist eine Zusage an den Kunden. Sie wird deshalb
**deterministisch aus den Antworten berechnet** und nicht von der KI vergeben:
bei gleichen Antworten kommt immer dieselbe Stufe heraus, und jede Stufe lässt
sich Frage für Frage belegen.

```
Quote = (1 × erfüllt + 0,5 × teilweise) ÷ (alle Fragen − nicht anwendbare)
```

| Stufe | Bedingung |
| --- | --- |
| vollständig compliant | Quote 100 % **und** keine offene Frage |
| weitgehend compliant | Quote ab 80 % |
| teilweise compliant | Quote ab 40 % |
| nicht compliant | darunter |

Zwei Festlegungen sind dabei wichtig:

- **Nicht anwendbare Fragen fallen vollständig heraus.** Das ist eine
  Scope-Entscheidung des Auditors und muss begründbar sein, denn sie hebt die
  Quote.
- **Offene Fragen zählen wie „nicht erfüllt".** Was nicht belegt ist, ist nicht
  nachgewiesen. Ein Audit mit 10 von 200 beantworteten Fragen kann deshalb nicht
  „vollständig compliant" ergeben, auch wenn alle 10 Antworten gut sind.

Damit der Unterschied zwischen *schlecht erfüllt* und *noch nicht erhoben*
sichtbar bleibt, weist das Modul zusätzlich die Quote nur der bewerteten Fragen
und die Abdeckung aus.

Die Rolle der KI ist bewusst eng: Sie erhält die Stufe als Vorgabe, darf sie
nicht ändern, und liefert Begründung, Hauptlücken und Maßnahmenvorschläge. Jede
Meldung wird mit gerechnetem Stand und KI-Text **getrennt** archiviert, damit
nachvollziehbar bleibt, was gerechnet und was formuliert wurde.

## Bestehende Audits aus älteren Versionen

Vor 7.4.0 gab es je Frage nur ein Freitext-Feld mit einer je Projekt
konfigurierbaren Notenskala. Daraus lässt sich keine belastbare Compliance-Aussage
rechnen. Für Bestandsprojekte gibt es deshalb die Funktion
**„Alte Bewertungen übernehmen"**: Sie leitet die Erfüllung einmalig aus dem
Freitext ab (`erfüllt`, `ja`, `konform` → erfüllt; `teilweise`, `ausreichend` →
teilweise; `mangelhaft`, `nein` → nicht erfüllt; `n/a`, `entfällt` → nicht
anwendbar). Bereits gesetzte Werte werden dabei **nie** überschrieben — eine
bewusste Entscheidung des Auditors gewinnt immer.

## Eigene Word-Vorlagen

Neben den programmatischen Berichten (Berichts-Center) lässt sich der Auditbericht
in eine **eigene Word-Vorlage** rendern — DOCX und PDF, über die zentrale,
Admin-verwaltete [Word-Vorlagen-Engine](../index.md). Der Weg ist derselbe wie in
CRA/NIS2/AI-Act/DSGVO: Vorlage unter **Administration → Word-Vorlagen** hochladen
(Modul „Compliance-Audit"), Platzhalter als `{{ jinja }}` schreiben, Export mit
`template_id`. Rendern erfordert die Permission `COMPLIANCE_AUDIT_EXPORT`.

Die vollständige Variablenliste zeigt die Admin-Oberfläche vor dem Hochladen; sie
kommt aus `compliance_audit/template_context.py`. Die wichtigsten Platzhalter:

| Platzhalter | Inhalt |
|---|---|
| `{{ projekt.name }}`, `{{ projekt.unternehmen }}` | Projekt und auditierte Organisation |
| `{{ projekt.frameworks_text }}` | geprüfte Frameworks als Text, z. B. „NIS2, CRA" |
| `{{ meta.stufe_label }}` | gerechnete Stufe im Klartext, z. B. „weitgehend compliant" |
| `{{ meta.stufe }}` | dieselbe Stufe als Schlüsselwort, für `{% if %}` in der Vorlage |
| `{{ meta.quote_prozent }}` | Erfüllungsquote; offene Fragen zählen wie „nicht erfüllt" |
| `{{ meta.abdeckung_prozent }}` | Erhebungsstand (Anteil beantworteter Fragen) |
| `{{ meta.fragen.offen }}` | Zählung je Erfüllungsgrad (`gesamt`, `erfuellt`, `offen`, …) |
| `{% for f in frameworks %}` | Stand je Framework (`quote_prozent`, `stufe_label`) |
| `{% for q in fragen %}` | alle Fragen mit `erfuellung_label` im Klartext |
| `{% for lk in luecken %}` | nur die Lücken, nicht erfüllt zuerst |
| `{{ bericht.zusammenfassung }}` | KI-Auditbericht-Entwurf, falls erzeugt |

Zwei Eigenschaften sind bewusst so gebaut:

- **Die Zahlen sind dieselben wie in der App.** Stufe und Quote kommen aus
  derselben Berechnung wie Wasserstandsmeldung, Dashboard und Berichts-Center.
  Eine Vorlage kann keine abweichende Zahl drucken.
- **Fehlende Daten brechen den Export nicht.** Der Kontext enthält niemals
  `None` — ohne KI-Entwurf bleiben dessen Felder leer, und ein unbekanntes
  Projekt rendert mit leeren Vorgaben statt mit einem Fehler.
