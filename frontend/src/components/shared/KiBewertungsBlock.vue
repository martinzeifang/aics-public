<!--
  KiBewertungsBlock (#1848) — der Abschnitt „🤖 KI-Bewertung" für alle Masken.

  DER BEFUND
  Der Baustein war für vier Module geteilt (`RequirementActions` → CRA, NIS2,
  AI Act, DSGVO) und dreimal nachgebaut. Was dabei verloren ging, war nicht
  Einheitlichkeit, sondern Funktion:

  - **OWASP-LLM und WiBA hatten kein `DataPreviewWarning`.** Damit lief der
    eingebaute Knopf „⚡ Direkt mit KI ausführen" dort **ohne**
    Egress-Bestätigung — genau die Lücke, die #1840 für den Server geschlossen
    hat, auf der Seite der Maske wieder offen.
  - **Beide setzten `hinweis-modul`/`hinweis-projekt` am `WizardPromptModal`
    nicht.** Das eingebaute Hinweis-Feld (#1834) lief mit leerem Modul, also
    wurden die **gespeicherten** Projekt-Hinweise (#1835) nie geladen. Das Feld
    war da und tat nichts — die Fehlerklasse aus #1830.
  - Der RisikoEditor zeigte die Markierung „⚠️ Neubewertung erforderlich"
    nicht an und verlinkte Issue-URLs **ohne** `safeUrl`.

  Deshalb entsteht die Komponente aus `RequirementActions` (der reifsten
  Fassung) und nicht aus dem kleinsten gemeinsamen Teiler: So erben alle
  Masken auf einen Schlag, was in dieser Woche an den geteilten Bausteinen
  entstanden ist (Hinweis-Feld, Projekt-Hinweise, Egress-Bestätigung, Abbruch).

  WAS DER ADAPTER TRÄGT
  Wertetyp, Freitextname, Endpunkte und — ausdrücklich — welche Einstiege es
  gibt (`utils/kiBewertung.ts`). Ein abgeschalteter Einstieg ist eine Aussage;
  eine fehlende Route ist ein Zufall.
-->
<template>
  <!-- #1765: Herkunft + fachliche Prüfung am Text, nicht im gedruckten Dokument.
       Die Stelle gehört der Maske: Der Hinweis soll unter den Bewertungsfeldern
       stehen, und wo die stehen, weiß nur sie (`mitHerkunftBadge`). -->
  <KiHerkunftBadge
    v-if="mitHerkunftBadge && adapter.herkunftArt && objektId && adapter.modul"
    :modul="adapter.modul"
    :projekt="projektName"
    :art="adapter.herkunftArt"
    :objekt-id="objektId"
  />

  <fieldset class="kb-block">
    <legend>
      {{ ABSCHNITTE.kiBewertung }}
      <NeubewertungBadge :text="freitextWert" />
    </legend>
    <div class="kb-knoepfe">
      <button v-if="adapter.einstiege.prompt" class="kb-knopf" type="button"
              :disabled="!!busy" :title="A.kiPrompt.titel" @click="oeffnePrompt">
        {{ knopf(A.kiPrompt, busy === 'prompt') }}
      </button>
      <button v-if="adapter.einstiege.auto" class="kb-knopf" type="button"
              :disabled="!!busy" :title="A.kiAuto.titel" @click="oeffneAuto">
        {{ knopf(A.kiAuto, busy === 'auto') }}
      </button>
      <button v-if="adapter.einstiege.neubewertung" class="kb-knopf" type="button"
              :disabled="!!busy" :title="A.kiNeubewertung.titel" @click="oeffneNeubewertung">
        {{ knopf(A.kiNeubewertung, busy === 'neu') }}
      </button>
      <slot name="knoepfe" />
    </div>
    <FehlerHinweis :text="fehler" @close="fehler = ''" />
    <p class="kb-vorbehalt">{{ KI_VORBEHALT }}</p>
  </fieldset>

  <!-- ── Prompt → Antwort ────────────────────────────────────────────── -->
  <WizardPromptModal
    v-if="wizard.open"
    :title="`${ABSCHNITTE.kiBewertung} — ${objektTitel || objektId}`"
    :prompt="wizard.prompt"
    :schema-hint="adapter.schemaHinweis"
    :busy="busy === 'parse'"
    :zusatz-beispiel="adapter.zusatzBeispiel"
    :egress-vorbestaetigt="wizard.bestaetigt"
    :hinweis-modul="adapter.modul"
    :hinweis-projekt="projektName"
    hinweis-bereich="bewertung"
    @apply="uebernimmAntwort"
    @close="wizard.open = false"
  >
    <template #before>
      <DataPreviewWarning
        :fields="vorschauFelder"
        :sensitive="adapter.sensibel"
        :provider="provider"
        @confirm="wizard.bestaetigt = true"
      />
      <FehlerHinweis :text="wizard.fehler" @close="wizard.fehler = ''" />
    </template>
    <template #after>
      <OutputDestinationHint :destination="adapter.ziel" :impact="adapter.wirkung" />
    </template>
  </WizardPromptModal>

  <!-- ── Automatische Bewertung (#1573) ──────────────────────────────── -->
  <AutoBewertungDialog
    v-if="auto.open"
    :title="objektTitel || String(objektId)"
    :stream-url="adapter.streamUrl(objektId)"
    :body="auto.body"
    :preview-fields="vorschauFelder"
    :sensitive="adapter.sensibel"
    :wert-label="adapter.wertLabel"
    :egress-modul="adapter.modul"
    :hinweis-modul="adapter.modul"
    :hinweis-projekt="projektName"
    :destination="adapter.ziel"
    :impact="adapter.wirkung"
    @close="auto.open = false"
    @done="aufErgebnis"
  />

  <!-- ── Neubewertung mit Issue-Feedback (#1521/#1527) ───────────────── -->
  <ModalRahmen v-if="neu.open" :titel="`${A.kiNeubewertung.text} — ${objektTitel || objektId}`"
               @close="neu.open = false">
    <template #inhalt>
      <p class="kb-vorbehalt">
        Das eingefügte Issue-/Review-Feedback fließt in die KI-Neubewertung ein.
        Leer lassen, um die <strong>verknüpften Issues</strong> automatisch einzubeziehen.
      </p>
      <textarea v-model="neu.text" rows="8"
                placeholder="Optional: Issue-Beschreibung / Review-Feedback einfügen…"></textarea>
      <!-- #1527: Transparenz — was fließt ein? -->
      <div class="kb-quelle">
        <template v-if="neu.text.trim()">
          ✍️ Es wird der <strong>eingefügte Text</strong> verwendet
          (verknüpfte Issues bleiben außen vor).
        </template>
        <template v-else-if="issues.length">
          🔗 Es
          {{ issues.length === 1
            ? 'wird der Inhalt von 1 verknüpften Issue'
            : `werden die Inhalte von ${issues.length} verknüpften Issues` }}
          einbezogen:
          <ul class="kb-issue-liste">
            <li v-for="i in issues" :key="i.id">
              <span class="kb-status" :class="i.state || 'open'">{{ i.state || 'open' }}</span>
              {{ i.provider }}{{ nummer(i) }} – {{ i.title || '(ohne Titel)' }}
            </li>
          </ul>
        </template>
        <template v-else>
          ⚠️ <strong>Keine verknüpften Issues</strong> — die KI bewertet ohne zusätzliches
          Feedback. Füge oben Text ein oder verknüpfe zuerst ein Issue.
        </template>
      </div>
    </template>
    <template #fuss>
      <button class="kb-sekundaer" type="button" @click="neu.open = false">Abbrechen</button>
      <button class="kb-primaer" type="button" :disabled="!!busy" @click="starteNeubewertung">
        Neubewertung starten
      </button>
    </template>
  </ModalRahmen>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import apiClient from '../../api/client'
import { ABSCHNITTE, KI_VORBEHALT, OBJEKT_AKTIONEN as A, knopf } from '../../utils/aktionen'
import type { KiBewertungsAdapter } from '../../utils/kiBewertung'
import { useKiHerkunftStore } from '../../stores/kiHerkunft'
import AutoBewertungDialog from './AutoBewertungDialog.vue'
import DataPreviewWarning from './DataPreviewWarning.vue'
import FehlerHinweis from './FehlerHinweis.vue'
import KiHerkunftBadge from './KiHerkunftBadge.vue'
import ModalRahmen from './ModalRahmen.vue'
import NeubewertungBadge from './NeubewertungBadge.vue'
import OutputDestinationHint from './OutputDestinationHint.vue'
import WizardPromptModal from './WizardPromptModal.vue'

const props = withDefaults(defineProps<{
  adapter: KiBewertungsAdapter
  projektName: string
  /** Das Objekt selbst — für Vorschau und Markierung. */
  objekt: any
  objektId: string | number
  objektTitel?: string
  /** Verknüpfte Issues — für die Transparenz der Neubewertung (#1527). */
  issues?: any[]
  /** Freitext des Objekts; trägt die Markierung „⚠️ Neubewertung erforderlich". */
  freitext?: string
  /** Zusätzlicher Body für den Prompt-Abruf (WiBA: Nachweise einbeziehen). */
  promptBody?: Record<string, any>
  /** Den Herkunfts-Hinweis hier zeigen. Aus, wo die Maske ihn selbst setzt. */
  mitHerkunftBadge?: boolean
}>(), {
  objektTitel: '',
  issues: () => [],
  freitext: '',
  promptBody: () => ({}),
  mitHerkunftBadge: true,
})

const emit = defineEmits<{
  /** Bewertung übernommen — die Maske lädt nach. */
  gespeichert: [ergebnis: any]
  fehler: [meldung: string]
}>()

type Busy = '' | 'prompt' | 'parse' | 'auto' | 'neu'
const busy = ref<Busy>('')
const fehler = ref('')
const provider = ref<'on_prem' | 'cloud'>('on_prem')
const kiHerkunft = useKiHerkunftStore()

const wizard = ref({ open: false, prompt: '', fehler: '', bestaetigt: false })
const auto = ref<{ open: boolean; body: any }>({ open: false, body: {} })
const neu = ref({ open: false, text: '' })

const vorschauFelder = computed(() => props.adapter.vorschau(props.objekt))
const freitextWert = computed(() => props.freitext || '')

const nummer = (i: any) => {
  const n = i?.issue_number ?? i?.number ?? i?.issue_iid ?? i?.iid
  return n ? `#${n}` : ''
}

const meldung = (e: any, ersatz: string) => e?.response?.data?.error || ersatz

onMounted(async () => {
  // Nur für den Egress-Hinweis in der Daten-Vorschau — read-only, keine Secrets.
  try {
    const res = await apiClient.get('/ai/provider-status')
    provider.value = res.data?.provider === 'cloud' ? 'cloud' : 'on_prem'
  } catch { /* Vorgabe on_prem */ }
})

/**
 * Nach dem Speichern die Herkunfts-Karte nachziehen, sonst erscheint der
 * Hinweis „KI-Entwurf, ungeprüft" erst beim Neuladen der Seite (#1765).
 */
const aufErgebnis = (ergebnis: any) => {
  emit('gespeichert', ergebnis)
  if (props.adapter.herkunftArt) {
    kiHerkunft.reload(props.adapter.modul, props.projektName, props.adapter.herkunftArt)
  }
}

// ── Prompt → Antwort ──────────────────────────────────────────────────────
const oeffnePrompt = async () => {
  if (!props.objektId) return
  busy.value = 'prompt'
  wizard.value = { open: false, prompt: '', fehler: '', bestaetigt: false }
  try {
    const url = props.adapter.promptUrl(props.objektId)
    const res = props.adapter.promptMethode === 'post'
      ? await apiClient.post(url, props.promptBody || {})
      : await apiClient.get(url)
    const text = res.data?.prompt || ''
    if (!text.trim()) {
      // #1839: Ein leeres Prompt-Fenster ist keine Antwort — häufigste Ursache
      // ist ein fehlender Katalog (#1817).
      fehler.value = 'Der Prompt ist leer — es liegen keine Daten für diese Bewertung vor.'
      return
    }
    wizard.value = { open: true, prompt: text, fehler: '', bestaetigt: false }
  } catch (e: any) {
    fehler.value = meldung(e, 'Der Prompt konnte nicht erzeugt werden.')
    emit('fehler', fehler.value)
  } finally {
    busy.value = ''
  }
}

const uebernimmAntwort = async (rohtext: string) => {
  if (!props.objektId || !rohtext) return
  busy.value = 'parse'
  wizard.value.fehler = ''
  try {
    const res = await apiClient.post(props.adapter.parseUrl(props.objektId),
                                     { raw: rohtext, response: rohtext, apply: true })
    // Antwortformen sind eine Obermenge (#1846/#1830) — je Modul ein anderer
    // Schlüssel, und ein fehlender wird im Frontend still `undefined`.
    const uebernommen = res.data?.bewertung !== undefined
      || res.data?.score !== undefined
      || res.data?.status !== undefined
      || res.data?.ok === true
      || res.data?.applied === true
    if (uebernommen) {
      wizard.value.open = false
      aufErgebnis(res.data)
    } else {
      wizard.value.fehler = 'Die Antwort konnte nicht ausgewertet werden.'
    }
  } catch (e: any) {
    wizard.value.fehler = meldung(e, 'Die Antwort konnte nicht übernommen werden.')
  } finally {
    busy.value = ''
  }
}

// ── Automatische Bewertung ────────────────────────────────────────────────
const oeffneAuto = () => {
  if (!props.objektId) return
  fehler.value = ''
  auto.value = { open: true, body: {} }
}

// ── Neubewertung mit Issue-Feedback ───────────────────────────────────────
const oeffneNeubewertung = () => {
  if (!props.objektId) return
  neu.value = { open: true, text: '' }
}

const starteNeubewertung = () => {
  const text = neu.value.text.trim()
  neu.value.open = false
  fehler.value = ''
  // Eingefügter Text gewinnt; sonst sammelt der Server die verknüpften Issues.
  auto.value = { open: true, body: text ? { issue_context: text } : { use_issue_feedback: true } }
}
</script>

<style scoped>
.kb-block {
  border: 1px solid var(--color-border); border-radius: 6px;
  padding: 10px 14px; margin-top: 12px; background: #f9f9f9;
}

.kb-block legend {
  padding: 0 6px; font-weight: 600; font-size: 12px;
  color: var(--color-primary); text-transform: uppercase;
}

.kb-knoepfe { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }

.kb-knopf {
  background: white; border: 1px solid #b3d4f5; color: #1565c0;
  padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;
}

.kb-knopf:hover:not(:disabled) { background: #1565c0; color: white; }
.kb-knopf:disabled { opacity: 0.5; cursor: not-allowed; }

.kb-vorbehalt { margin: 4px 0 0; font-size: 11px; color: #e65100; }

.kb-quelle {
  margin-top: 10px; padding: 8px 12px; border-radius: 6px;
  background: #f5faff; border: 1px solid #cfe3f7; font-size: 13px; color: #37474f;
}

.kb-issue-liste { margin: 6px 0 0; padding-left: 4px; list-style: none; }
.kb-issue-liste li { padding: 2px 0; font-size: 12px; }

.kb-status {
  padding: 2px 8px; border-radius: 3px;
  font-size: 10px; font-weight: 600; text-transform: uppercase;
}

.kb-status.open { background: #e3f2fd; color: #1565c0; }
.kb-status.closed { background: #e8f5e9; color: #2e7d32; }

:deep(.mr-inhalt) textarea {
  width: 100%; padding: 8px;
  border: 1px solid var(--color-border); border-radius: 4px;
  font-family: monospace; font-size: 12px; resize: vertical;
}

.kb-primaer, .kb-sekundaer {
  padding: 8px 16px; border: none; border-radius: 4px;
  cursor: pointer; font-size: 13px;
}

.kb-primaer { background: var(--color-primary); color: white; }
.kb-primaer:disabled { opacity: 0.6; cursor: not-allowed; }
.kb-sekundaer { background: #e0e0e0; color: #333; }
</style>
