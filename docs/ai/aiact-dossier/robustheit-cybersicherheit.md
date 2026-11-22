# Genauigkeit, Robustheit und Cybersicherheit (AIA-HR-07 · Art. 15)

## Genauigkeit

- Bewertungen folgen einer **Rubrik je Anforderung** (0–5) mit Begründungs- und Normbezugspflicht
  (`EVAL_AUFTRAG_FORMAT`, #1419); deterministische Einstellungen (Temperatur 0.2).
- Inhaltsbasierte, nachvollziehbare Regeln statt pauschaler KI-Scores, wo möglich
  (z. B. AIA-HR-01 aus der Risikobewertung, #1561).
- Die Genauigkeit wird bei Modellwechseln per Stichprobe geprüft
  (siehe [Daten-Governance — Bias](daten-governance.md#bias-und-fairness-aia-data-02)).

## Robustheit

| Störung | Verhalten |
|---|---|
| Ungültige/abgeschnittene KI-Antwort | robuster Parser (JSON in Code-Fences, abgeschnittene Antworten), sonst Fehler statt Teilübernahme |
| Provider nicht verfügbar | klarer Fehler (409/502), **kein stiller Fallback** auf einen anderen Provider |
| Ollama-Kaltstart / lange Laufzeit | Streaming mit Fortschrittsanzeige, großzügige Timeouts, Abbruch protokolliert |
| Fehlerhafte Konfiguration | SSRF-Guard / Loopback-Pflicht für Ollama (#741), HTTPS-Pflicht für Cloud |

## Cybersicherheit (Security-by-Design)

| Bereich | Nachweis |
|---|---|
| Statische Analyse | `sast.yml` (Bandit u. a.), Bandit-Baseline im CI (`ci.yml`) |
| Abhängigkeiten | `deps-audit.yml`, Dependabot, OSV-Scan (`ai-act-osv-scan.yml`, `cra-osv-scan.yml`) |
| SBOM | `ai-act-sbom.yml`, `cra-sbom.yml` |
| Secrets | `secret-scan.yml` (gitleaks), API-Keys at-rest verschlüsselt (#1174, #1534) |
| Schwachstellen-Management | CRA-Vulnerability-Sync (#937), [SECURITY.md](https://github.com/martinzeifang/AI_Compliance_Suite/blob/main/SECURITY.md) |
| Anwendung | RBAC, JWT mit Token-Versionierung (#1182), Upload-Validierung (Magic-Bytes, Zip-Bomb, #1186), Container-Härtung |
| KI-spezifisch (OWASP LLM Top 10) | keine Ausführung von KI-Ausgaben, Schema-Parsing, Sandbox-Templates, Egress-Kontrolle, Redaktion — siehe [Risikoregister](risikomanagement.md) R2/R3 |

## Adversarial Testing

Prompt-Injection-Tests werden über den AI-Act-Assistenten „Prompt-Injection-Tests" vorbereitet;
Ergebnisse fließen in das OWASP-LLM-Register (LLM01) der AI-Act-Bewertung der Suite ein.
