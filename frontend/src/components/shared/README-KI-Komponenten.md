# Gemeinsame KI-Komponenten (Sprint #16 — KI-Transparenz)

Diese Komponenten schaffen eine einheitliche, transparente KI-UX über alle
Module hinweg. Sie liegen in `frontend/src/components/shared/` und werden in
einer späteren Phase (#871–#876) in die Modul-Views eingebunden. Dieses
Dokument ist die Konvention für die spätere Migration.

Bezug: Epic #865 (#866/#867/#868/#869/#870/#877/#878).

## Übersicht

| Komponente | Issue | Zweck |
|---|---|---|
| `AIProviderBadge.vue` | #867 | Aktiver KI-Provider (lokal/Cloud) + Status in der Topbar |
| `WizardPromptModal.vue` | #866 | Wiederverwendbares Copy-Paste-KI-Modal (Prompt → KI → JSON zurück) |
| `DataPreviewWarning.vue` | #868 | „Welche Daten gehen an die KI?" inkl. Bestätigung |
| `OutputDestinationHint.vue` | #869 | „Wohin geht die KI-Antwort?" (Zielfeld + Wirkung) |

Disclaimer-Konvention (#870): Jedes KI-Ergebnis trägt sichtbar den Hinweis
**„🤖 KI-generiert — fachlich zu prüfen."** (im `WizardPromptModal` bereits
enthalten). KI-Aktionen werden einheitlich mit dem 🤖-Label gekennzeichnet.

## AIProviderBadge.vue (#867)

Zeigt den aktiven Provider an. Lädt den Status selbstständig von
`GET /api/ai/provider-status` (über `src/api/client`). Keine Props nötig. Bereits
in `AppLayout.vue` (Topbar) eingebunden; Klick führt zu `/admin/settings`.

```vue
<AIProviderBadge />
```

Backend-Antwort (read-only, keine Secrets):

```json
{ "provider": "on_prem", "label": "Lokal (Ollama)", "configured": true, "allow_data_egress": false }
```

- `provider`: `on_prem` (🏠) | `cloud` (☁️) | `none`
- `configured`: on_prem → Modell gesetzt; cloud → Modell gesetzt UND Egress erlaubt
- `allow_data_egress`: spiegelt `ai.cloud.allow_data_egress` (#877)

## WizardPromptModal.vue (#866)

Ersetzt perspektivisch die modul-eigenen Inline-Modals (u. a.
`RequirementActions.vue`).

Props:

| Prop | Typ | Beschreibung |
|---|---|---|
| `title` | string (required) | Überschrift des Wizards |
| `prompt` | string | Anzuzeigender/kopierbarer Prompt-Text |
| `schemaHint` | string | Hinweis auf das erwartete JSON-Schema |
| `busy` | boolean | Verarbeitungszustand (deaktiviert Eingaben) |

Slots:

| Slot | Zweck |
|---|---|
| `before` | Transparenz vor Absenden — z. B. `DataPreviewWarning` (#868) |
| `after` | Ziel-/Wirkungshinweis — z. B. `OutputDestinationHint` (#869) |

Emits: `apply(rawText)`, `close`.

```vue
<WizardPromptModal
  title="CRA-Control bewerten"
  :prompt="prompt"
  schema-hint="Antwort als JSON gemäß Schema { bewertung, status }"
  :busy="busy"
  @apply="onApply"
  @close="show = false"
>
  <template #before>
    <DataPreviewWarning
      :fields="fields"
      :sensitive="['Repository', 'Projektname']"
      :provider="provider"
      @confirm="confirmed = true"
    />
  </template>
  <template #after>
    <OutputDestinationHint
      destination="Antwort befüllt das Feld 'Bewertung'"
      impact="setzt den Status auf 'in Prüfung'"
    />
  </template>
</WizardPromptModal>
```

## DataPreviewWarning.vue (#868)

Props:

| Prop | Typ | Beschreibung |
|---|---|---|
| `fields` | `{ label, value }[]` | In den Prompt einfließende Daten |
| `sensitive` | `string[]` | Labels, die als sensibel markiert werden |
| `provider` | `'on_prem' \| 'cloud'` | Steuert den Egress-Warnhinweis |

Emits: `confirm` (erst nach expliziter Bestätigung durch den Nutzer).

Backend-Konvention: Jedes Modul liefert pro Wizard die genutzten Daten über
`get_*_data_used()` neben `build_*_prompt` (umzusetzen bei der Modul-Migration).

## OutputDestinationHint.vue (#869)

Props (beide Namenskonventionen werden unterstützt):

| Prop | Alias | Beschreibung |
|---|---|---|
| `destination` | `targetFieldLabel` | Zielfeld der Antwort |
| `impact` | `effectDescription` | Wirkung der Übernahme |

## Provider/Egress (#877) & Hilfe (#878)

- Der aktive Provider + `allow_data_egress` werden read-only über den
  `AIProviderBadge` (Topbar) und in den Admin-Einstellungen
  (`frontend/src/views/admin/AdminSettingsView.vue`) sichtbar gemacht.
- Zentrale Hilfe-Seite: `docs/ki-funktionen.md` (erklärt Copy-Paste-Workflow,
  lokal vs. Cloud, Datenschutz/Egress). Verlinkt in `mkdocs.yml`.
