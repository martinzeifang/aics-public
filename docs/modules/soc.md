# SOC (Security Operations Center)

Das SOC-Modul ist ein schlanker **Triage- und Dokumentations-Layer für
Wazuh-Alarme** — bewusst **kein** SIEM-Nachbau und **keine** Log-Speicherung.
Es holt Alarme ab einem einstellbaren Level aus einer bestehenden Wazuh-Instanz,
hilft bei der Bewertung (Was ist das? False Positive? Echter Vorfall?), führt
echte **Incidents** und leitet bei einem bestätigten Vorfall automatisch die
einschlägigen **Meldepflichten** ab.

## Zweck

- **Alarm-Triage** wie ein Ticketsystem: Status führen, bewerten, Reaktion
  revisionssicher dokumentieren.
- **Incident-Management** nach NIST SP 800-61 / ISO 27035 mit append-only,
  SHA-256-gesicherter Timeline.
- **Compliance-nativ:** ein bestätigter Incident erzeugt — je nach betroffenem
  Asset — die passenden Melde-Records: **DSGVO Art. 33/34**, **NIS2 Art. 23**,
  **CRA Art. 14**, **AI-Act Art. 73** (DORA Art. 19 als Stub).
- **KI-Unterstützung** zweigleisig: lokales **Ollama** (Default, Daten bleiben im
  Haus) oder **Copy/Paste-Prompt** für ChatGPT o. ä.

## Anbindung an Wazuh (generisch, jede Wazuh 4.x)

Der Einrichtungsassistent (Tab **⚙️ Einrichtung**) bietet zwei Wege:

### PULL (empfohlen, geringster Eingriff)
Das Modul fragt den **Wazuh-Indexer** (OpenSearch) ab — Wazuh selbst muss nichts
weiterleiten.

- Eingaben: Indexer-URL (`https://<host>:9200`), read-only Benutzer + Passwort,
  TLS-Prüfung (bei self-signed aus), Index-Muster (Default `wazuh-alerts-*`),
  Mindest-Level.
- In Wazuh nötig: lediglich ein **Read-only-User** mit `read` auf `wazuh-alerts-*`.
  Kein Neustart, kein Skript.
- Inkrementelles Polling über `search_after`-Cursor (idempotent, übersteht
  App-Neustarts).

### PUSH (Wazuh-Integrator)
Wazuh leitet Alarme aktiv an den Token-gesicherten Webhook `…/api/ingest/soc`.
Der Wizard erzeugt die fertigen Artefakte (ossec.conf-`<integration>`-Block +
Skript `custom-soc` + `chown/chmod/restart`).

> Es wird **nichts** auf eine bestimmte Wazuh-Instanz hartkodiert — alle Werte
> sind Eingaben oder werden generiert.

## Triage & Incidents

- **Alarme** (Tab 🚨): Filter nach Status/Schwere/Level, Detail mit Rohlog +
  MITRE-ATT&CK, Triage-Statusmaschine
  (`new → in_review → {false_positive | confirmed} → …`), KI-Analyse, „→ Incident
  anlegen".
- **Dedup:** gleichartige Alarme werden über
  `sha1(rule.id | agent.id | srcip | 5-Min-Bucket)` zu Gruppen zusammengefasst
  (gegen Alert-Fatigue). **Suppression-Regeln** (mit Ablauf/TTL + Dry-Run) für
  bekannte False Positives.
- **Incidents** (Tab 🛡️): Statusmaschine, append-only Timeline (SHA-256-Kette),
  GDPR-Flags, Notizen.

## Meldepflicht-Router

Der Button **„🔁 Meldepflicht prüfen"** wertet die **Compliance-Tags des
betroffenen Assets** aus und eröffnet die einschlägigen Meldetracks mit den aus
dem *Awareness*-Zeitpunkt berechneten Fristen:

| Asset-Tag | Track | Frist |
|-----------|-------|-------|
| personenbezogen | DSGVO Art. 33/34 | 72 h |
| nis2_scope | NIS2 Art. 23 | 24 h / 72 h / 1 Monat |
| cra_produkt | CRA Art. 14 | 24 h / 72 h / 14 Tage |
| ki_hochrisiko | AI-Act Art. 73 | 2–15 Tage |
| dora_scope | DORA Art. 19 (Stub) | 24 h |

Pro Track lässt sich die **Brücke** ausführen: DSGVO erzeugt eine echte
**Datenpanne** im DSGVO-Modul (Art. 33(3)-Felder), CRA einen **`cra_vuln`**-Eintrag
(aktiv ausgenutzt), NIS2/AI-Act je einen **Meldeentwurf** als Dokument im
Zielmodul. Die Asset-Tags pflegst du im Tab **🖥️ Assets** (Import aus der
Wazuh-Manager-Agentenliste möglich).

## Berechtigungen

- Permissions: `SOC_READ`, `SOC_WRITE`, `SOC_TRIAGE`, `SOC_INCIDENT`,
  `SOC_CONFIG`, `SOC_EXPORT`.
- Rolle **Operator** (`soc_operator`) bündelt die SOC-Berechtigungen.
- Das Modul ist **lizenzpflichtig** (`soc`).

## Datenhaltung

Eigene SQLite `data/db/soc.sqlite` — es wird nur ein **Arbeitsset** gehalten
(getriagte Alarme/Incidents), nicht der vollständige Log-Bestand des SIEM.
Verbindungs-Secrets liegen **verschlüsselt** at-rest.

> Hinweis: Das SOC-Modul ersetzt nicht das Wazuh-Dashboard für die Log-Analyse.
> Sein Mehrwert liegt im Triage-Workflow, der prüffähigen Dokumentation und der
> automatischen Verknüpfung zu den Compliance-Meldepflichten.
