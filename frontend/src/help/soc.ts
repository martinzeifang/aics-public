import type { ModuleHelp } from './types'
import { docsUrl } from './docsUrl'

export const socHelp: ModuleHelp = {
  module: 'soc',
  title: 'SOC – Security Operations Center',
  regulation: 'Wazuh-Alarm-Triage & Incident-Management; Meldepflichten DSGVO Art. 33/34, NIS2 Art. 23, CRA Art. 14, AI-Act Art. 73',
  purpose: 'Das SOC-Modul ist ein schlanker Triage- und Dokumentations-Layer für Wazuh-Alarme — kein SIEM-Nachbau und keine Log-Speicherung. Es holt Alarme ab einem einstellbaren Level aus einer bestehenden Wazuh-Instanz, hilft bei der Bewertung (Was ist das? False Positive? Echter Vorfall?), führt Incidents und leitet bei einem bestätigten Vorfall automatisch die einschlägigen Meldepflichten ab.',
  legalBasis: {
    title: 'Worauf das Modul aufsetzt',
    intro: 'SOC verbindet operative Sicherheitsüberwachung mit den gesetzlichen Melde- und Nachweispflichten. Ein bestätigter Incident kann — je nach betroffenem Asset — mehrere Meldepflichten gleichzeitig auslösen.',
    bullets: [
      'DSGVO Art. 33/34: Meldung einer Datenpanne an die Aufsichtsbehörde (72 h) bzw. Benachrichtigung Betroffener bei hohem Risiko.',
      'NIS2 Art. 23: Frühwarnung (24 h) / Meldung (72 h) / Abschlussbericht (1 Monat).',
      'CRA Art. 14: aktiv ausgenutzte Schwachstellen und schwere Vorfälle (24 h / 72 h / 14 Tage).',
      'AI-Act Art. 73: schwere Vorfälle bei Hochrisiko-KI-Systemen.',
      'Incident-Handling als Nachweis für NIS2 Art. 21(2)(b) und AI-Act-Post-Market-Monitoring (Art. 72).',
    ],
  },
  implementation: {
    title: 'Vorgehen im Modul',
    intro: 'Zunächst wird im Einrichtungsassistenten die Wazuh-Anbindung hergestellt (PULL vom Indexer empfohlen, optional PUSH per Integrator). Danach werden Alarme triagiert, Incidents geführt und Meldepflichten abgeleitet.',
    bullets: [
      'Einrichtung: read-only-Indexer-User in Wazuh anlegen, im Wizard URL/Benutzer/Passwort eintragen (bei self-signed „TLS prüfen" aus), synchronisieren.',
      'Alarme triagieren: Filter (Status/Schwere/Level/Art Schwachstelle vs. sonstige), Detailansicht mit Rohlog + MITRE ATT&CK, KI-Analyse (Ollama lokal oder Copy/Paste), Suppression-Regeln gegen Alarm-Fatigue.',
      'Incidents: aus Alarmen eskalieren, Status führen, Reaktion revisionssicher (SHA-256-Timeline) dokumentieren, mit Pflicht-Begründung schließen.',
      'Meldepflicht: betroffene Regelwerke wählen → „Meldepflicht prüfen" erzeugt die Meldetracks mit Fristen → Brücke ausführen (DSGVO-Datenpanne, CRA-Schwachstelle, NIS2-/AI-Act-Meldeentwurf).',
      'Bestätigte Incidents als GitHub/GitLab-Issue tracken; firmenweite Sichtbarkeit im Risiko-Cockpit; Incident-Report als PDF/DOCX exportieren.',
    ],
  },
  moduleSpecific: {
    title: 'KI & Datenschutz',
    intro: 'Die KI-Analyse ist zweigleisig: lokales Ollama (Default, Daten bleiben im Haus) oder Copy/Paste-Prompt für ein externes KI-Tool. Vor jeder Analyse ist transparent einsehbar, welche Daten an die KI übermittelt werden.',
  },
  links: [
    { label: 'SOC-Modul-Doku (Online)', href: docsUrl('/modules/soc/') },
    { label: 'Wazuh-Dokumentation', href: 'https://documentation.wazuh.com/' },
  ],
}
