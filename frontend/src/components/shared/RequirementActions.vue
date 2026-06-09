<template>
  <fieldset class="llm-section">
    <legend>🤖 KI-Bewertung</legend>
    <div class="llm-buttons">
      <button class="btn-llm" @click="onShowWizard" :disabled="!!busy">
        {{ busy === 'prompt' ? '⏳ Lade Prompt…' : '🤖 KI-Bewertung (Prompt → Antwort)' }}
      </button>
    </div>
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

const busy = ref<'' | 'prompt' | 'json' | 'create' | 'link' | 'sync'>('')
const issues = ref<any[]>([])

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
