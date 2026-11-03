# Wie funktionieren die KI-Funktionen in AICS?

Diese Seite erklärt, **wo und wie** Künstliche Intelligenz (KI) in der
AI Compliance Suite (AICS) eingesetzt wird, welche Daten dabei verarbeitet
werden und wie der Datenschutz gewahrt bleibt.

> 🤖 **Grundsatz:** Alle KI-Ausgaben sind **KI-generiert und fachlich zu
> prüfen.** Die KI unterstützt – die fachliche Verantwortung bleibt beim
> Menschen (Human-in-the-Loop).

## Was ist KI in AICS?

AICS nutzt KI, um bei Compliance-Aufgaben zu unterstützen, z. B. beim
Klassifizieren von Produkten, Entwerfen von Bewertungen, Vorschlagen von
Pflichtdokumentation oder beim Beantworten von Fragebögen. Über alle Module
hinweg (CRA, NIS2, AI-Act, DSGVO, Risikobewertung, Gutachten u. a.) gibt es
rund 45 KI-gestützte Funktionen.

Damit immer transparent ist, dass KI im Spiel ist, zeigt AICS:

- ein **🤖-Label** an KI-Aktionen,
- ein **Provider-Badge** in der Kopfzeile (🏠 lokal / ☁️ Cloud),
- vor dem KI-Aufruf, **welche Daten** übermittelt werden,
- **wohin** die Antwort gespeichert wird und welche **Wirkung** sie hat,
- den Disclaimer **„🤖 KI-generiert — fachlich zu prüfen."**

## Der Copy-Paste-Workflow

Die meisten KI-Funktionen folgen einem bewussten, transparenten
**Copy-Paste-Workflow** (kein automatischer API-Aufruf an externe Anbieter):

1. **Prompt erstellen** – AICS baut aus deinen Projekt-/Domänendaten einen
   Prompt inklusive JSON-Schema.
2. **In die KI kopieren** – Du kopierst den Prompt z. B. nach ChatGPT.
3. **Antwort zurück einfügen** – Die KI-Antwort (JSON) fügst du in AICS ein.
4. **Übernehmen** – AICS parst die Antwort und übernimmt sie in die Zielfelder.

Dieser Ansatz respektiert, dass ChatGPT Pro keine offizielle API bietet, und
vermeidet rechtliche/ToS-Probleme. Du behältst die volle Kontrolle darüber,
welche Daten du an welche KI gibst.

## Lokal (Ollama) vs. Cloud

AICS unterstützt zwei Betriebsarten für direkte KI-Aufrufe:

| | 🏠 Lokal (Ollama) | ☁️ Cloud |
|---|---|---|
| Verarbeitung | auf deinem Rechner/Netzwerk | bei einem externen Anbieter |
| Daten-Egress | **keiner** – Daten bleiben lokal | Daten **verlassen dein Netzwerk** |
| Voraussetzung | laufender Ollama-Dienst + Modell | API-Key + ausdrückliche Zustimmung |
| Standard | **ja** (`provider = on_prem`) | nur nach expliziter Freigabe |

Der **aktive Provider** wird über das Badge in der Kopfzeile angezeigt und ist
in den **Administrations-Einstellungen** sichtbar.

### Sonderfall: Risikobewertung-Bulk

Die Massen-/Bulk-Bewertung der Risikobewertung nutzt einen **direkten lokalen
Ollama-Aufruf** (statt Copy-Paste). Auch hier werden die Daten lokal
verarbeitet.

## Datenschutz & Egress (`allow_data_egress`)

Der Cloud-Modus ist standardmäßig **deaktiviert**. Bevor Daten ein externes
Netzwerk erreichen können, muss `allow_data_egress` ausdrücklich aktiviert
werden (Schalter `ai.cloud.allow_data_egress`).

- **Lokal:** `allow_data_egress` ist stets `false` – es verlassen keine Daten
  dein Netzwerk.
- **Cloud:** Ist Egress erlaubt, weist AICS vor dem Absenden deutlich darauf
  hin, **welche Daten** (inkl. Markierung sensibler Felder wie Projekt-/Repo-/
  PII-Daten) übermittelt werden. Eine Bestätigung ist erforderlich.
- AICS führt im Cloud-Modus eine Best-Effort-Redaktion offensichtlicher
  Secrets/PII durch, bevor Daten gesendet werden. Diese ersetzt jedoch nicht
  die eigene Prüfung.

Der Egress-Status ist read-only sichtbar in:

- dem **Provider-Badge** (Status „Egress blockiert" / „konfiguriert"),
- den **Administrations-Einstellungen** (Bereich „KI / Provider").

## „KI-generiert — fachlich zu prüfen"

Jedes KI-Ergebnis ist ein **Vorschlag**. Prüfe es fachlich, bevor du es
übernimmst oder freigibst. AICS kennzeichnet KI-Ergebnisse durchgängig
entsprechend.
