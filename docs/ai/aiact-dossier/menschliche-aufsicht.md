# Menschliche Aufsicht (AIA-HR-06 · Art. 14)

Die KI der Suite **unterstützt**, sie **entscheidet nicht**. Jede KI-Funktion ist so gestaltet,
dass ein Mensch das Ergebnis vor oder nach der Übernahme prüft und jederzeit überstimmen kann.

## Eingriffs- und Kontrollmöglichkeiten

| Art. 14 Abs. 4 | Umsetzung in der Suite |
|---|---|
| a) Fähigkeiten/Grenzen verstehen | Transparenz-Hinweise, [KI-Funktionen](../../ki-funktionen.md), KI-Kompetenz über das Literacy-Register (Art. 4) |
| b) Automation Bias bewusst machen | Disclaimer an jeder KI-Aktion, Kennzeichnung gespeicherter KI-Ergebnisse (#1551), „⚠️ Neubewertung erforderlich" statt Auto-Erfüllung (#1526) |
| c) Ausgabe korrekt interpretieren | Begründung, Maßnahmen, Normbezug und genutzte Nachweise je Bewertung (#1419, #1485) |
| d) Ausgabe nicht verwenden / überstimmen | jede Bewertung ist editierbar; Copy/Paste-Workflow mit Prüfung vor Übernahme; Massenbewertung mit **Vorschau und Auswahl** vor dem Übernehmen (#1528) |
| e) Eingreifen / anhalten | KI-Aufruf startet erst nach Bestätigung (#1519, kein Autostart); Schließen des KI-Fensters bricht einen laufenden Stream ab (Abbruch wird protokolliert, #1550); KI kann global abgeschaltet werden (kein Provider konfiguriert → klare 409, kein stiller Fallback) |

## Rollen

- **Fachanwender:in** — prüft und verantwortet jede übernommene Bewertung.
- **Administrator:in** — konfiguriert Provider/Modell, Freigabe der Cloud-Nutzung
  (`allow_data_egress`), Berechtigungen (RBAC).
- Die für die Aufsicht benannten Personen werden im **AI-Literacy-Register** mit Schulungsnachweis
  geführt (Feld „Oversight-Person").
