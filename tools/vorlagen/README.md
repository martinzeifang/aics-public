# Vorlagen im Hausdesign erzeugen

Seit #1777 wählt das Berichts-Center die Word-Vorlage **je Berichtstyp**. Eine
Vorlage ohne Berichtstyp gilt für das ganze Modul — bei CRA sind das sieben
fachlich verschiedene Dokumente, und mit gesetztem Standard liefern alle
dasselbe Papier, bis hin zur EU-Konformitätserklärung.

Dieses Werkzeug erzeugt für **jeden** Berichtstyp eine eigene Vorlage im Design
einer vorhandenen Datei.

## Warum das Design geerbt und nicht nachgebaut wird

Jede erzeugte Datei entsteht aus einem Rohling: Formatvorlagen, Theme,
Nummerierung sowie Kopf- und Fußzeile bleiben erhalten, ersetzt wird nur der
Textkörper. Ein Nachbau aus Einzelangaben trifft das Briefpapier nie
vollständig — und was fehlt, sieht man erst im fertigen Dokument.

Der Rohling liegt **nicht** im Repository. Er ist das Briefpapier eines Hauses,
kein Quelltext:

```bash
docker exec -u aics aics_web cat \
  /app/data/templates/cra/3__Vorlage_CRA_Readiness_Cyberwoks.docx > rohling.docx
```

## Erzeugen

```bash
python3 tools/vorlagen/erzeuge_cyberwoks.py --rohling rohling.docx --ziel out/vorlagen
python3 tools/vorlagen/erzeuge_cyberwoks.py --rohling rohling.docx --ziel out/vorlagen --nur cra
```

Dabei entsteht neben den DOCX eine `zuordnung.json`. Sie hält fest, welche Datei
zu welchem Modul und Berichtstyp gehört, und ist beim Einspielen maßgeblich —
Dateinamen sind es nicht: `ohne_empfehlungen` zerfällt am Unterstrich zu `ohne`,
einem Berichtstyp, den es nicht gibt.

## Hoch- und Querformat

Das Dokument ist hochformatig; **breite Auflistungen stehen im Querformat**.
Word hängt die Ausrichtung nicht am Dokument, sondern am Abschnitt — eine
Vorlage kann also beides führen. Im Bauplan umschließt `with b.querformat(doc)`
Überschrift **und** Tabelle; nur die Tabelle zu umschließen lässt die
Überschrift allein am Fuß der vorigen Seite zurück.

Die Regel ist mechanisch, damit sie nachvollziehbar bleibt: **ab fünf Spalten
quer**, bei vier Spalten dann, wenn eine davon Freitext trägt (Titel einer
Schwachstelle, Maßnahme, Begründung, Prüffrage). Bis drei Spalten bleibt es
hoch; dort kostet Querformat nur Papier. `tests/test_vorlagen_querformat_1790.py`
rechnet das für alle Baupläne nach. Eine Ausnahme von Hand: Die
EU-Konformitätserklärung bleibt durchgehend hoch — ihr Aufbau folgt Anhang V.

Zwei Dinge wechseln mit und sind leicht zu übersehen: „Abweichende erste Seite"
gilt **je Abschnitt** (sonst bekommt jeder neue Abschnitt die Kopf- und Fußzeile
der Titelseite), und der rechte Tabulator in Kopf- und Fußzeile steht als
**absolute** Position. Querformat-Abschnitte bekommen deshalb eigene Kopf- und
Fußzeilen mit nachgezogenem Tabulator; ihr Inhalt wird kopiert, nicht neu
gebaut — im Fuß steckt das Feld „Seite x von y".

## Prüfen

Vor dem Einspielen gehört jede Vorlage einmal gerendert. „Kein Fehler" allein
genügt nicht — Jinja ersetzt einen falsch geschriebenen Namen stillschweigend
durch nichts, und das Dokument sieht fertig aus:

```python
from shared.templates import schema, engine, validate
ctx = schema.get_context_builder("cra")(schema.MODULE_DB["cra"], "<Projekt>")
engine.render_docx_from_path(pfad, dict(ctx, bericht_typ="gesamt"), modul="cra")
validate.pruefe_variablen("cra", str(pfad))    # Pflichtangaben + unbekannte Namen
```

Die Pflichtprüfung ist dabei die schärfste: Für Konformitätsnachweis und
EU-Konformitätserklärung sind Angaben vorgeschrieben, und eine Vorlage ohne sie
lässt sich nicht als Standard setzen.

## Einspielen

In der Installation, mit denselben Pfaden, die die Anwendung benutzt:

```bash
python3 tools/vorlagen/einspielen.py --ordner /tmp/vorlagen          # Haus-Vorlagen
python3 tools/vorlagen/einspielen.py --ordner /tmp/vorlagen --firma 7  # je Mandant
python3 tools/vorlagen/einspielen.py --ordner /tmp/vorlagen --ersetzen # Austausch
```

Das Einspielen geht denselben Weg wie der Upload über die Oberfläche und
schreibt einen Eintrag in den Revisionspfad.

`--ersetzen` ist für den **Austausch** eines Satzes: Ein erneuter Upload legt
eine neue Version an, die alte bleibt sonst aktiv und wählbar. Wer sie greift,
bekommt den Fehler zurück, den der Austausch beseitigen sollte. Abgeschaltet
wird per Soft-Delete — Zeile und Datei bleiben, nur unsichtbar.

## Ein anderes Haus

`cyberwoks_plaene.py` enthält die Gliederungen; sie sind nicht
firmenspezifisch. Für ein anderes Haus genügen ein anderer Rohling und die
Anschrift in `cyberwoks_bausteine.titelblock`.
