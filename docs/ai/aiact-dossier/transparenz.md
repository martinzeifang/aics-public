# Transparenz und Nutzerinformationen (AIA-HR-05 · Art. 13 · Art. 50)

## Kennzeichnung in der Oberfläche

- **🤖-Label** an jeder KI-Aktion und der Hinweis **„🤖 KI-generiert — fachlich zu prüfen."**
- **Provider-Badge** in der Kopfzeile (🏠 lokal / ☁️ Cloud); im Ergebnis wird der genutzte
  Provider angezeigt (☁️/🖥️, #1418).
- **Vor dem Aufruf:** welche Daten übermittelt werden (Datenvorschau), wohin das Ergebnis
  gespeichert wird und welche Wirkung es hat; bei direkten KI-Aufrufen eine ausdrückliche
  Bestätigung (#1519).
- **Nach dem Aufruf:** genutzte Nachweise („🔎 Genutzte Nachweise", #1485).

## Kennzeichnung gespeicherter Ergebnisse

Automatisch gespeicherte KI-Bewertungen (Auto-Bewertung aller Module) erhalten am Kommentarende
eine dauerhafte Kennzeichnung:

```
— 🤖 KI-generiert (on_prem, 2026-10-15) — fachlich zu prüfen.
```

Damit bleibt auch in Berichten und Exporten erkennbar, dass ein Ergebnis maschinell erzeugt
wurde (#1551). Eine erneute KI-Bewertung ersetzt die Kennzeichnung, statt sie zu doppeln; wird
der Kommentar fachlich überarbeitet, kann die Kennzeichnung bewusst entfernt werden.

## Gebrauchsinformationen für Betreiber (Art. 13 Abs. 3)

| Information | Fundstelle |
|---|---|
| Zweckbestimmung, Grenzen | [Dossier-Übersicht](index.md), [KI-Funktionen](../../ki-funktionen.md) |
| Genauigkeit / bekannte Grenzen | Bewertungen sind **Entwürfe**; Qualität hängt vom gewählten Modell ab; keine Garantie fachlicher Richtigkeit ([Risikoregister](risikomanagement.md) R1, R4, R5) |
| Menschliche Aufsicht | [Menschliche Aufsicht](menschliche-aufsicht.md) |
| Datenverarbeitung | [Datenanhandhabung](../data-handling.md), [Daten-Governance](daten-governance.md) |
| Protokollierung | [Logging](logging.md) |
| Betriebsarten, Konfiguration | [On-Prem](../on-prem.md), [Cloud](../cloud.md) |
