# Marktbeobachtung und Vorfälle (AIA-HR-08 · AIA-HR-09 · Art. 72 · Art. 73)

## Post-Market-Monitoring (AIA-HR-08)

| Quelle | Was wird beobachtet | Auswertung |
|---|---|---|
| GitHub-Issues (auch aus der Suite erzeugt, In-App-Issue-Assistent) | Fehlerberichte, fehlerhafte KI-Bewertungen, Verbesserungen | laufend; Label `ai` für KI-bezogene Meldungen |
| Audit-Trail `ai.*` | Fehler- und Abbruchquoten je Provider/Modell (`outcome = fail/aborted`) | je Release / bei Auffälligkeiten |
| Support-Bundle (#1509) | Logs der Installation (redigiert) | im Supportfall |
| Schwachstellen-Feeds | Dependabot, OSV, CRA-Vulnerability-Sync (#937) | täglich (CI) |
| Eigenbewertung | AI-Act-Bewertung der Suite im eigenen Modul | jährlich |

**Plan:** Erkenntnisse werden als Issues erfasst, im [Risikoregister](risikomanagement.md)
bewertet und über den regulären [Change-Prozess](qms-change-management.md) behandelt. Wiederholte
fachlich falsche KI-Bewertungen eines Moduls lösen eine Überprüfung der Prompt-Vorlage aus.

## Incident-Management (AIA-HR-09)

**Was ist ein Vorfall?** Ein Fehlverhalten der KI-Funktionen, das zu einer falschen
Compliance-Aussage mit Außenwirkung führt (z. B. fehlerhafter Bericht an eine Behörde), ein
unbeabsichtigter Datenabfluss an einen KI-Anbieter oder eine Sicherheitslücke in der KI-Kette.

| Schritt | Vorgehen |
|---|---|
| Meldung | Sicherheitsrelevant: privat nach [SECURITY.md](https://github.com/martinzeifang/AI_Compliance_Suite/blob/main/SECURITY.md) (GitHub Security Advisory). Sonst: GitHub-Issue mit Label `bug` + `ai`. |
| Triage | Eingangsbestätigung innerhalb von 5 Werktagen (SECURITY.md); Einstufung nach Auswirkung |
| Eindämmung | Betreiber können KI-Funktionen sofort deaktivieren (Provider entfernen / Cloud-Freigabe zurücknehmen); Fix-Release |
| Analyse | Audit-Trail (`ai.*`, Provenienz der Bewertung), Reproduktion |
| Kommunikation | Release-Notes, ggf. Security Advisory; Betreiber informieren |
| Behördenmeldung | Art. 73 gilt für **Hochrisiko**-Systeme — die Suite ist keines (siehe [Einordnung](index.md#einordnung)). Datenschutzvorfälle meldet der Betreiber nach Art. 33 DSGVO; Sicherheitsvorfälle ggf. nach CRA Art. 14 / NIS2. |

Für die **Betreiber** stellt die Suite die passenden Werkzeuge selbst bereit: Art.-73-Vorfallsregister
im AI-Act-Modul, Datenpannen-Register (DSGVO) und CRA-Meldewesen.
