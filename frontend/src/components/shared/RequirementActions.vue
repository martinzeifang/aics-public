<template>
  <fieldset class="llm-section">
    <legend>🤖 KI-Bewertung</legend>
    <div class="llm-buttons">
      <button class="btn-llm" @click="onShowWizard" :disabled="!!busy">
        {{ busy === 'prompt' ? '⏳ Lade Prompt…' : '🤖 KI-Bewertung (Prompt → Antwort)' }}
      </button>
      <button class="btn-llm" @click="onAutoBewertung" :disabled="!!busy" title="LLM direkt aufrufen und Bewertung übernehmen">
        {{ busy === 'auto' ? '⏳ Bewerte…' : '🤖 Automatische Bewertung' }}
      </button>
    </div>
    <p v-if="autoError" class="alert alert-error">{{ autoError }}</p>
    <p class="llm-disclaimer">🤖 KI-generiert — fachlich zu prüfen.</p>
  </fieldset>

  <fieldset class="issues-section">
    <legend>🔗 Verknüpfte Issues</legend>
    <div v-if="issues.length === 0" class="muted">Keine Issues verknüpft.</div>
    <div v-else class="issues-list">
      <div v-for="i in issues" :key="i.id" class="issue-item">
        <span class="issue-state" :class="i.state">{{ i.state || 'open' }}</span>
        <a :href="safeUrl(i.url)" target="_blank" rel="noopener noreferrer" class="issue-link">
          {{ i.provider }}#{{ i.issue_number || i.issue_iid }} – {{ i.title }}
        </a>
        <button class="btn-tiny" @click="onUnlink(i.id)" title="Verknüpfung entfernen">✕</button>
      </div>
    </div>
    <div class="llm-buttons">
      <button class="btn-llm" @click="onShowCreateIssue" :disabled="!!busy">
        ➕ Neues Issue
      </button>
      <button class="btn-llm" @click="onShowLinkIssue" :disabled="!!busy">
        🔗 Existierendes verknüpfen
      </button>
      <button class="btn-llm" @click="onSyncIssues" :disabled="!!busy || issues.length === 0">
        {{ busy === 'sync' ? '⏳ Sync…' : '🔄 Status synchronisieren' }}
      </button>
    </div>
  </fieldset>

  <!-- #866/#868/#869/#870: gemeinsames KI-Wizard-Modal mit Transparenz-Bausteinen -->
  <WizardPromptModal
    v-if="wizard.open"
    :title="`KI-Bewertung für ${requirement?.id || 'Anforderung'}`"
    :prompt="wizard.prompt"
    schema-hint='Antwort als JSON: { "score": 0-5, "kommentar": "…", "massnahme": "…" }'
    :busy="busy === 'json'"
    @apply="onApplyWizard"
    @close="wizard.open = false"
  >
    <template #before>
      <DataPreviewWarning
        :fields="previewFields"
        :sensitive="['Repository']"
        :provider="aiProvider"
        @confirm="wizard.confirmed = true"
      />
      <p v-if="wizard.error" class="alert alert-error">{{ wizard.error }}</p>
    </template>
    <template #after>
      <OutputDestinationHint
        destination="Befüllt Bewertung (Score), Kommentar und Maßnahme der Anforderung."
        impact="Überschreibt die aktuelle Bewertung nach dem Übernehmen."
      />
    </template>
  </WizardPromptModal>

  <Teleport to="body">
    <!-- #1380: Bestätigung der Datenübermittlung vor automatischer KI-Bewertung -->
    <div v-if="autoConfirm.open" class="modal-overlay nested" @mousedown.self="autoConfirm.open = false">
      <div class="modal-content prompt-modal">
        <div class="modal-header">
          <h3>🤖 Automatische KI-Bewertung</h3>
          <button class="btn-close" @click="autoConfirm.open = false">✕</button>
        </div>
        <div class="modal-body">
          <DataPreviewWarning
            :fields="previewFields"
            :sensitive="['Repository']"
            :provider="aiProvider"
            @confirm="startAutoStream"
          />
          <OutputDestinationHint
            destination="Die KI bewertet direkt; Score, Kommentar und Maßnahme werden übernommen."
            impact="Überschreibt die aktuelle Bewertung nach dem Aufruf."
          />
        </div>
      </div>
    </div>

    <!-- #1397: Ergebnis der automatischen KI-Bewertung anzeigen -->
    <div v-if="autoResult.open" class="modal-overlay nested" @mousedown.self="closeAutoResult">
      <div class="modal-content prompt-modal">
        <div class="modal-header">
          <h3>🤖 KI-Bewertung: Ergebnis</h3>
          <button class="btn-close" @click="closeAutoResult">✕</button>
        </div>
        <div class="modal-body">
          <!-- #1408: Live-Token-Stream der KI -->
          <KiStreamView v-if="autoResult.streaming" :url="`/api${baseUrl}/auto-bewertung/stream`"
                        :body="{}" :pipeline="true" @done="onAutoStreamDone"
                        @error="(m: string) => { autoResult.streaming = false; autoError = m }" />
          <div v-if="autoResult.bewertung !== null" class="auto-result-score">
            <span class="ars-label">Bewertung</span>
            <span class="ars-value">{{ autoResult.bewertung !== null ? autoResult.bewertung : '–' }}<span class="ars-max"> / 5</span></span>
          </div>
          <div v-if="autoResult.bewertung !== null" class="auto-result-block">
            <h4>Begründung der KI</h4>
            <p class="auto-result-text">{{ autoResult.kommentar || '— keine Begründung geliefert —' }}</p>
          </div>
          <div v-if="autoResult.bewertung !== null && autoResult.massnahme" class="auto-result-block">
            <h4>Empfohlene Maßnahmen</h4>
            <p class="auto-result-text">{{ autoResult.massnahme }}</p>
          </div>
          <!-- #1485/#1487 (Sprint #40): Provenienz — welche App-Nachweise den Score stützen -->
          <div v-if="autoResult.bewertung !== null && autoResult.genutzte_nachweise.length" class="auto-result-block">
            <h4>🔎 Genutzte Nachweise aus der Anwendung</h4>
            <ul class="auto-result-evidence">
              <li v-for="(n, i) in autoResult.genutzte_nachweise" :key="i">{{ n }}</li>
            </ul>
          </div>
          <p v-if="autoResult.bewertung !== null" class="llm-disclaimer">🤖 KI-generiert<span v-if="autoResult.provider"> ({{ autoResult.provider === 'cloud' ? 'Cloud' : 'Lokal' }})</span> — fachlich zu prüfen. Die Bewertung wurde übernommen.</p>
          <p v-if="autoError" class="alert alert-error">{{ autoError }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn-primary" :disabled="autoResult.streaming && autoResult.bewertung === null" @click="closeAutoResult">
            {{ autoResult.bewertung !== null ? 'Verstanden, übernehmen' : 'Schließen' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Issue erstellen -->
    <div v-if="createModal.open" class="modal-overlay nested" @mousedown.self="createModal.open = false">
      <div class="modal-content prompt-modal">
        <div class="modal-header">
          <h3>➕ Neues Issue für {{ requirement?.id }}</h3>
          <button class="btn-close" @click="createModal.open = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Provider</label>
            <select v-model="createModal.provider">
              <option value="github">GitHub</option>
              <option value="gitlab">GitLab</option>
            </select>
          </div>
          <div class="form-row">
            <label>Repository *</label>
            <input v-model="createModal.repo" placeholder="owner/repo" />
          </div>
          <div class="form-row">
            <label>Titel</label>
            <input v-model="createModal.title" :placeholder="`(auto: Gap: ${requirement?.id})`" />
          </div>
          <div class="form-row">
            <label>Body (optional, Auto-generiert wenn leer)</label>
            <textarea v-model="createModal.body" rows="4"></textarea>
          </div>
          <div v-if="createModal.error" class="alert alert-error">{{ createModal.error }}</div>
          <div v-if="createModal.created" class="preview">
            ✅ <a :href="safeUrl(createModal.created.url)" target="_blank" rel="noopener noreferrer">{{ createModal.created.url }}</a>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="createModal.open = false">Schließen</button>
          <button class="btn-primary" @click="onCreateIssue"
                  :disabled="!createModal.repo || busy === 'create'">
            {{ busy === 'create' ? 'Erstellt…' : 'Issue erstellen' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Issue verknüpfen -->
    <div v-if="linkModal.open" class="modal-overlay nested" @mousedown.self="linkModal.open = false">
      <div class="modal-content prompt-modal">
        <div class="modal-header">
          <h3>🔗 Existierendes Issue verknüpfen</h3>
          <button class="btn-close" @click="linkModal.open = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Issue-URL *</label>
            <input v-model="linkModal.url" placeholder="https://github.com/owner/repo/issues/123" />
            <small>Provider und Issue-Nummer werden automatisch erkannt.</small>
          </div>
          <div class="form-row">
            <label>Titel (optional)</label>
            <input v-model="linkModal.title" />
          </div>
          <div v-if="linkModal.error" class="alert alert-error">{{ linkModal.error }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="linkModal.open = false">Abbrechen</button>
          <button class="btn-primary" @click="onLinkIssue" :disabled="!linkModal.url">Verknüpfen</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import apiClient from '../../api/client'
import { safeUrl } from '../../utils/safeUrl'
import WizardPromptModal from './WizardPromptModal.vue'
import DataPreviewWarning from './DataPreviewWarning.vue'
import KiStreamView from './KiStreamView.vue'
import OutputDestinationHint from './OutputDestinationHint.vue'

const props = defineProps<{
  /** Aktuelle Anforderung (mit id, titel, kapitel) */
  requirement: any
  /** Projekt-Name für API-URL */
  projektName: string
  /** API-Base-URL: /cra | /nis2 | /aiact */
  apiBase: string
  /** Object-Kind für Issue-Linking: 'requirement' (default) | 'owasp' */
  objectKind?: 'requirement' | 'owasp'
  /** Default-Repo aus Projekt-Meta-JSON */
  defaultRepo?: string
}>()

const emit = defineEmits<{
  /** Wird ausgelöst wenn Bewertung erfolgreich übernommen wurde */
  saved: [result: any]
  error: [message: string]
}>()

const busy = ref<'' | 'prompt' | 'json' | 'auto' | 'create' | 'link' | 'sync'>('')
const issues = ref<any[]>([])
const autoError = ref('')

// #866: gemeinsames KI-Wizard-Modal (ersetzt die früheren Prompt-/JSON-Modals)
const wizard = ref<{ open: boolean; prompt: string; error: string; confirmed: boolean }>({
  open: false, prompt: '', error: '', confirmed: false,
})
// #867/#877: aktiver KI-Provider für die Daten-Transparenz (Egress-Hinweis)
const aiProvider = ref<'on_prem' | 'cloud'>('on_prem')

// #868: Daten, die in den Prompt einfließen — aus den bereits vorhandenen
// Anforderungs-/Projekt-Daten abgeleitet (keine zusätzliche Backend-Abfrage nötig).
const previewFields = computed(() => [
  { label: 'Projekt', value: props.projektName },
  { label: 'Anforderung', value: props.requirement?.id },
  { label: 'Titel', value: props.requirement?.titel || props.requirement?.title },
  { label: 'Kapitel', value: props.requirement?.kapitel },
  { label: 'Aktuelle Bewertung', value: props.requirement?.bewertung ?? props.requirement?.score },
])

const createModal = ref<{ open: boolean; provider: string; repo: string; title: string; body: string; error: string; created: any | null }>({
  open: false, provider: 'github', repo: '', title: '', body: '', error: '', created: null,
})
const linkModal = ref({ open: false, url: '', title: '', error: '' })
// #1380: Bestätigung der Datenübermittlung vor automatischer KI-Bewertung
const autoConfirm = ref<{ open: boolean }>({ open: false })
// #1397: Ergebnis der automatischen KI-Bewertung anzeigen (Score + Begründung)
const autoResult = ref<{ open: boolean; streaming: boolean; bewertung: number | null; kommentar: string; massnahme: string; provider: string; genutzte_nachweise: string[]; data: any }>(
  { open: false, streaming: false, bewertung: null, kommentar: '', massnahme: '', provider: '', genutzte_nachweise: [], data: null })

const baseUrl = computed(() => {
  const path = props.objectKind === 'owasp' ? 'owasp' : 'anforderungen'
  return `${props.apiBase}/projekte/${encodeURIComponent(props.projektName)}/${path}/${encodeURIComponent(props.requirement?.id || '')}`
})

const issuesUrl = computed(() => `${baseUrl.value}/issues`)

const loadIssues = async () => {
  if (!props.requirement?.id) {
    issues.value = []
    return
  }
  try {
    const res = await apiClient.get(issuesUrl.value)
    issues.value = res.data || []
  } catch {
    issues.value = []
  }
}

watch(() => props.requirement?.id, () => loadIssues(), { immediate: true })

// #867/#877: aktiven Provider laden (read-only, keine Secrets) für den
// Egress-Hinweis in der Daten-Vorschau.
onMounted(async () => {
  try {
    const res = await apiClient.get('/ai/provider-status')
    aiProvider.value = res.data?.provider === 'cloud' ? 'cloud' : 'on_prem'
  } catch { /* Default on_prem */ }
})

const onShowWizard = async () => {
  if (!props.requirement?.id) return
  busy.value = 'prompt'
  wizard.value = { open: false, prompt: '', error: '', confirmed: false }
  try {
    const res = await apiClient.get(`${baseUrl.value}/prompt`)
    wizard.value = {
      open: true,
      prompt: res.data?.prompt || '',
      error: '',
      confirmed: false,
    }
  } catch (e: any) {
    emit('error', e?.response?.data?.error || 'Prompt-Fehler')
  } finally {
    busy.value = ''
  }
}

const onApplyWizard = async (rawText: string) => {
  if (!props.requirement?.id || !rawText) return
  wizard.value.error = ''
  busy.value = 'json'
  try {
    const res = await apiClient.post(`${baseUrl.value}/parse-response`, {
      raw: rawText, apply: true,
    })
    if (res.data?.bewertung !== undefined || res.data?.score !== undefined) {
      emit('saved', res.data)
      wizard.value.open = false
    } else {
      wizard.value.error = 'Antwort konnte nicht geparst werden'
    }
  } catch (e: any) {
    wizard.value.error = e?.response?.data?.error || 'Fehler beim Parsen'
  } finally {
    busy.value = ''
  }
}

// #1366: Automatische KI-Bewertung — ruft den LLM direkt auf (on_prem/cloud).
// #1380: Vor dem direkten LLM-Aufruf muss die Datenübermittlung bestätigt werden
// (gleiche Transparenz wie beim Prompt-Flow). Klick öffnet zuerst den Dialog.
const onAutoBewertung = () => {
  if (!props.requirement?.id) return
  autoError.value = ''
  autoConfirm.value = { open: true }
}

// #1408: Live-Streaming statt Block-POST — Token-für-Token zusehen.
const startAutoStream = () => {
  if (!props.requirement?.id) return
  autoConfirm.value.open = false
  autoError.value = ''
  autoResult.value = { open: true, streaming: true, bewertung: null, kommentar: '',
                       massnahme: '', provider: '', genutzte_nachweise: [], data: null }
}

// #1397: Ergebnis (Score + Begründung) anzeigen; Übernahme/Refresh erst beim Schließen.
const onAutoStreamDone = (payload: any) => {
  autoResult.value.streaming = false
  autoResult.value.bewertung = payload?.bewertung ?? payload?.score ?? 0
  autoResult.value.kommentar = payload?.kommentar || ''
  autoResult.value.massnahme = payload?.massnahme || ''
  autoResult.value.provider = payload?.provider || ''
  autoResult.value.genutzte_nachweise = Array.isArray(payload?.genutzte_nachweise) ? payload.genutzte_nachweise : []
  autoResult.value.data = payload
}

// #1397: Dialog schließen → jetzt erst den Parent aktualisieren (Liste/Score neu laden).
const closeAutoResult = () => {
  const d = autoResult.value.data
  autoResult.value.open = false
  if (d) emit('saved', d)
}

const onShowCreateIssue = () => {
  createModal.value = {
    open: true, provider: 'github', repo: props.defaultRepo || '',
    title: '', body: '', error: '', created: null,
  }
}

const onCreateIssue = async () => {
  if (!props.requirement?.id || !createModal.value.repo) return
  busy.value = 'create'
  createModal.value.error = ''
  try {
    const res = await apiClient.post(issuesUrl.value, {
      provider: createModal.value.provider,
      repo: createModal.value.repo,
      title: createModal.value.title || undefined,
      body: createModal.value.body || undefined,
    })
    if (res.data?.created) {
      createModal.value.created = res.data
      await loadIssues()
      setTimeout(() => { createModal.value.open = false }, 2000)
    }
  } catch (e: any) {
    createModal.value.error = e?.response?.data?.error || 'Fehler beim Erstellen'
  } finally {
    busy.value = ''
  }
}

const onShowLinkIssue = () => {
  linkModal.value = { open: true, url: '', title: '', error: '' }
}

const onLinkIssue = async () => {
  if (!props.requirement?.id || !linkModal.value.url) return
  busy.value = 'link'
  linkModal.value.error = ''
  try {
    const res = await apiClient.post(`${issuesUrl.value}/link`, {
      url: linkModal.value.url,
      title: linkModal.value.title || undefined,
    })
    if (res.data?.linked) {
      linkModal.value.open = false
      await loadIssues()
    }
  } catch (e: any) {
    linkModal.value.error = e?.response?.data?.error || 'Verknüpfung fehlgeschlagen'
  } finally {
    busy.value = ''
  }
}

const onSyncIssues = async () => {
  if (!props.requirement?.id) return
  busy.value = 'sync'
  try {
    await apiClient.post(`${issuesUrl.value}/sync`)
    await loadIssues()
  } catch (e: any) {
    emit('error', e?.response?.data?.error || 'Sync fehlgeschlagen')
  } finally {
    busy.value = ''
  }
}

const onUnlink = async (linkId: string) => {
  if (!props.requirement?.id) return
  if (!confirm('Verknüpfung wirklich entfernen?')) return
  try {
    await apiClient.delete(`${issuesUrl.value}/${linkId}`)
    await loadIssues()
  } catch (e: any) {
    emit('error', e?.response?.data?.error || 'Fehler beim Entfernen')
  }
}
</script>

<style scoped>
/* #1397: Ergebnis-Dialog der automatischen KI-Bewertung */
.auto-result-score {
  display: flex; align-items: baseline; gap: 12px;
  padding: 10px 14px; margin-bottom: 12px;
  background: #e3f2fd; border-radius: 8px;
}
.ars-label { font-size: 13px; color: #1565c0; font-weight: 600; }
.ars-value { font-size: 30px; font-weight: 700; color: #0d47a1; line-height: 1; }
.ars-max { font-size: 15px; font-weight: 500; color: #5c8fc0; }
.auto-result-block { margin-bottom: 12px; }
.auto-result-block h4 { margin: 0 0 4px; font-size: 13px; color: #37474f; }
.auto-result-text { margin: 0; white-space: pre-wrap; line-height: 1.5; color: #263238; }
.auto-result-evidence { margin: 0; padding-left: 18px; font-size: 13px; color: #37474f; }
.auto-result-evidence li { margin: 2px 0; }

.llm-section, .issues-section {
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 10px 14px;
  margin-top: 12px;
  background: #f9f9f9;
}

.llm-section legend, .issues-section legend {
  padding: 0 6px;
  font-weight: 600;
  font-size: 12px;
  color: var(--color-primary);
  text-transform: uppercase;
}

.llm-buttons {
  display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px;
}

.llm-disclaimer {
  margin: 4px 0 0; font-size: 11px; color: #e65100;
}

.btn-llm {
  background: white;
  border: 1px solid #b3d4f5;
  color: #1565c0;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.btn-llm:hover:not(:disabled) {
  background: #1565c0; color: white;
}

.btn-llm:disabled {
  opacity: 0.5; cursor: not-allowed;
}

.muted {
  color: #888; font-size: 12px; font-style: italic;
}

.issues-list {
  display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px;
}

.issue-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 8px; background: white;
  border-radius: 3px; font-size: 12px;
}

.issue-state {
  padding: 2px 8px; border-radius: 3px;
  font-size: 10px; font-weight: 600; text-transform: uppercase;
}

.issue-state.open { background: #e3f2fd; color: #1565c0; }
.issue-state.closed { background: #e8f5e9; color: #2e7d32; }

.issue-link {
  flex: 1; color: #333; text-decoration: none;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.issue-link:hover { text-decoration: underline; color: var(--color-primary); }

.btn-tiny {
  background: none; border: 1px solid #ddd;
  width: 22px; height: 22px;
  border-radius: 3px; cursor: pointer;
  color: #888; font-size: 12px;
}

.btn-tiny:hover { background: #ffebee; color: #c62828; border-color: #c62828; }

/* Modal-Styles über Teleport */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1100;
}

.modal-overlay.nested { z-index: 1200; }

.modal-content {
  background: white; border-radius: 8px;
  display: flex; flex-direction: column;
}

.prompt-modal {
  max-width: 800px; width: 90%; max-height: 90vh;
}

.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid var(--color-border);
}

.modal-header h3 { margin: 0; color: var(--color-primary); font-size: 16px; }

.btn-close {
  background: none; border: none; font-size: 22px;
  color: #999; cursor: pointer;
}

.modal-body { flex: 1; overflow-y: auto; padding: 16px 20px; }

.modal-footer {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 12px 20px; border-top: 1px solid var(--color-border);
}

.hint { color: #666; font-size: 13px; margin: 0 0 12px; }

.prompt-text {
  background: #f5f5f5; padding: 12px; border-radius: 4px;
  font-size: 12px; line-height: 1.5;
  white-space: pre-wrap; max-height: 50vh; overflow-y: auto;
  font-family: monospace; border: 1px solid #ddd;
}

.modal-body textarea {
  width: 100%; padding: 8px;
  border: 1px solid var(--color-border); border-radius: 4px;
  font-family: monospace; font-size: 12px; resize: vertical;
}

.modal-body input,
.modal-body select {
  width: 100%; padding: 8px 10px;
  border: 1px solid var(--color-border); border-radius: 4px;
  font-size: 13px;
}

.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row small { display: block; font-size: 11px; color: #888; margin-top: 2px; }

.alert-error {
  background: #ffebee; color: #c62828;
  padding: 10px; border-radius: 4px; margin: 12px 0;
  border: 1px solid #ef5350; font-size: 13px;
}

.preview {
  background: #e8f5e9; padding: 10px 14px; border-radius: 4px;
  margin-top: 12px; font-size: 13px; border: 1px solid #81c784;
}

.preview a { color: #2e7d32; }
.preview pre {
  white-space: pre-wrap; font-size: 12px;
  max-height: 200px; overflow-y: auto;
  background: white; padding: 6px; border-radius: 3px;
}

.btn-primary, .btn-secondary {
  padding: 8px 16px; border: none; border-radius: 4px;
  cursor: pointer; font-size: 13px;
}

.btn-primary { background: var(--color-primary); color: white; }
.btn-primary:disabled { opacity: 0.6; }
.btn-secondary { background: #e0e0e0; color: #333; }
</style>
