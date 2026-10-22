<template>
  <!-- #1765: Herkunfts-/Prüfhinweis direkt unter Bewertung + Kommentar — der
       Vorbehalt gehört an den Text, nicht in das gedruckte Dokument. -->
  <KiHerkunftBadge
    v-if="requirement?.id && projektName"
    :modul="kiModul"
    :projekt="projektName"
    :art="kiArt"
    :objekt-id="requirement.id"
  />
  <!-- #1564: Risiko für Nichterfüllung → verknüpfte Risikobewertung (CRA/NIS2/DSGVO/AI Act) -->
  <RequirementRiskLinks
    v-if="requirement?.id && projektName"
    :api-base="apiBase"
    :projekt-name="projektName"
    :object-kind="objectKind || 'requirement'"
    :object-id="String(requirement.id)"
    :titel="requirement.titel || requirement.title || ''"
    :score="requirement.bewertung ?? requirement.score ?? requirement.status ?? null"
    :kommentar="requirement.kommentar || requirement.notes || ''"
  />
  <fieldset class="llm-section">
    <legend>
      🤖 KI-Bewertung
      <span v-if="needsReassessment" class="reassess-badge"
            :title="reassessReason">⚠️ Neubewertung erforderlich</span>
    </legend>
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
    <!-- #1521/#1522: Issue-Inhalt übernehmen + Neubewertung mit Feedback (immer sichtbar, wie Risikobewertung) -->
    <div class="llm-buttons">
      <button class="btn-llm" @click="onShowImportModal" :disabled="!!busy"
              title="Issue-Inhalt/Review-Feedback in den Kommentar übernehmen — ändert die Bewertung NICHT">
        {{ busy === 'import' ? '⏳ Importiere…' : '📥 Issue-Inhalt importieren' }}
      </button>
      <button class="btn-llm" @click="onShowReassessModal" :disabled="!!busy"
              title="KI-Neubewertung unter Einbezug von Issue-/Review-Feedback">
        🔄 Neubewertung mit Issue-Feedback
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
    <!-- #1521/#1522: Issue-Inhalt importieren (Text einfügen oder aus verknüpften Issues laden) -->
    <div v-if="importModal.open" class="modal-overlay nested" @mousedown.self="importModal.open = false">
      <div class="modal-content prompt-modal">
        <div class="modal-header">
          <h3>📥 Issue-Inhalt importieren — {{ requirement?.id }}</h3>
          <button class="btn-close" @click="importModal.open = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="llm-disclaimer">Übernimmt Review-Feedback in den <strong>Kommentar</strong> —
            die Bewertung (Score) wird <strong>nicht</strong> geändert.</p>
          <button v-if="issues.length > 0" class="btn-llm" :disabled="!!busy"
                  @click="onImportFromLinked" style="margin-bottom:8px">
            {{ busy === 'import' ? '⏳ Lade…' : '🔗 Aus verknüpften Issues laden & übernehmen' }}
          </button>
          <textarea v-model="importModal.text" rows="9"
                    placeholder="Issue-Body, Kommentare, Code-Review-Feedback hier einfügen…"></textarea>
          <p v-if="importModal.error" class="alert alert-error">{{ importModal.error }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="importModal.open = false">Abbrechen</button>
          <button class="btn-primary" :disabled="!importModal.text.trim() || !!busy" @click="onApplyImport">
            In Kommentar einfügen
          </button>
        </div>
      </div>
    </div>

    <!-- #1521/#1522: Neubewertung mit Issue-Feedback (Kontext einfügen, dann KI-Stream) -->
    <div v-if="reassessModal.open" class="modal-overlay nested" @mousedown.self="reassessModal.open = false">
      <div class="modal-content prompt-modal">
        <div class="modal-header">
          <h3>🔄 Neubewertung mit Issue-Feedback — {{ requirement?.id }}</h3>
          <button class="btn-close" @click="reassessModal.open = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="llm-disclaimer">Das eingefügte Issue-/Review-Feedback fließt in die KI-Neubewertung ein.
            Leer lassen, um <strong>verknüpfte Issues</strong> automatisch einzubeziehen.</p>
          <textarea v-model="reassessModal.text" rows="8"
                    placeholder="Optional: Issue-Body / Audit-Feedback einfügen…"></textarea>
          <!-- #1527: Transparenz — was fließt in die Neubewertung ein? -->
          <div class="reassess-source">
            <template v-if="reassessModal.text.trim()">
              ✍️ Es wird der <strong>eingefügte Text</strong> verwendet (verknüpfte Issues werden ignoriert).
            </template>
            <template v-else-if="issues.length">
              🔗 Es {{ issues.length === 1 ? 'wird der Inhalt von 1 verknüpften Issue' : `werden die Inhalte von ${issues.length} verknüpften Issues` }} einbezogen:
              <ul class="reassess-issue-list">
                <li v-for="i in issues" :key="i.id">
                  <span class="issue-state" :class="i.state || 'open'">{{ i.state || 'open' }}</span>
                  {{ i.provider }}#{{ i.issue_number || i.issue_iid }} – {{ i.title || '(ohne Titel)' }}
                </li>
              </ul>
            </template>
            <template v-else>
              ⚠️ <strong>Keine verknüpften Issues</strong> — die KI bewertet ohne zusätzliches Feedback.
              Füge oben Text ein oder verknüpfe zuerst ein Issue.
            </template>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="reassessModal.open = false">Abbrechen</button>
          <button class="btn-primary" :disabled="!!busy" @click="onStartReassess">Neubewertung starten</button>
        </div>
      </div>
    </div>

    <!-- #1573: einheitlicher Auto-Bewertungs-Dialog (alle Module) — Bestätigung → Live-Stream → Ergebnis -->
    <AutoBewertungDialog v-if="autoDialog.open"
      :title="`${requirement?.id || ''}${(requirement?.titel || requirement?.title) ? ': ' + (requirement?.titel || requirement?.title) : ''}`"
      :stream-url="`/api${baseUrl}/auto-bewertung/stream`" :body="autoDialog.body"
      :preview-fields="previewFields" :sensitive="['Repository']"
      destination="Die KI bewertet direkt; Score, Kommentar und Maßnahme werden übernommen."
      @close="autoDialog.open = false" @done="(d: any) => onKiBewertungGespeichert(d)" />

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
import AutoBewertungDialog from './AutoBewertungDialog.vue'
import OutputDestinationHint from './OutputDestinationHint.vue'
import RequirementRiskLinks from './RequirementRiskLinks.vue'
import KiHerkunftBadge from './KiHerkunftBadge.vue'
import { useKiHerkunftStore, type KiArt } from '../../stores/kiHerkunft'

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

const busy = ref<'' | 'prompt' | 'json' | 'auto' | 'create' | 'link' | 'sync' | 'import'>('')
const issues = ref<any[]>([])
const autoError = ref('')

// #1765: Das Modul steckt bereits in `apiBase` (/cra, /nis2, /aiact, /dsgvo) —
// genau das URL-Segment, über das auch das Herkunfts-Register adressiert wird.
const kiHerkunft = useKiHerkunftStore()
const kiModul = computed(() => props.apiBase.replace(/^\/+|\/+$/g, ''))
const kiArt = computed<KiArt>(() => (props.objectKind === 'owasp' ? 'owasp' : 'requirement'))

/**
 * Nach einer frisch gespeicherten KI-Bewertung die Herkunfts-Karte nachziehen,
 * damit der Hinweis „KI-Entwurf, ungeprüft" ohne Neuladen der Seite erscheint.
 */
const onKiBewertungGespeichert = (result: any) => {
  emit('saved', result)
  kiHerkunft.reload(kiModul.value, props.projektName, kiArt.value)
}

// #1520/#1526: „Neubewertung erforderlich"-Badge, wenn ein verknüpftes Issue geändert wurde.
const needsReassessment = computed(() => {
  const txt = String(props.requirement?.kommentar ?? props.requirement?.notiz ?? '')
  return txt.includes('Neubewertung erforderlich')
})
// #1584: Grund anzeigen — verknüpftes Issue oder Pentest-Finding
const reassessReason = computed(() => {
  const txt = String(props.requirement?.kommentar ?? props.requirement?.notiz ?? '')
  return txt.includes('Pentest-Finding')
    ? 'Ein offenes Pentest-Finding betrifft diese Kontrolle — bitte neu bewerten (Details im Kommentar)'
    : 'Ein verknüpftes Issue wurde geschlossen/geöffnet — bitte neu bewerten'
})

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
// #1573: einheitlicher Auto-Bewertungs-Dialog; body={} normal, bei Neubewertung mit
// Issue-Feedback (#1521) der eingefügte Kontext bzw. use_issue_feedback.
const autoDialog = ref<{ open: boolean; body: any }>({ open: false, body: {} })

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
      onKiBewertungGespeichert(res.data)
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
  autoDialog.value = { open: true, body: {} }
}

// #1521/#1522: Import- + Neubewertungs-Modal (Text einfügen, wie Risikobewertung)
const importModal = ref<{ open: boolean; text: string; error: string }>({ open: false, text: '', error: '' })
const reassessModal = ref<{ open: boolean; text: string }>({ open: false, text: '' })

const onShowImportModal = () => {
  if (!props.requirement?.id) return
  importModal.value = { open: true, text: '', error: '' }
}

// Aus verknüpften Issues laden (Backend sammelt + übernimmt score-neutral).
const onImportFromLinked = async () => {
  if (!props.requirement?.id) return
  busy.value = 'import'
  importModal.value.error = ''
  try {
    const res = await apiClient.post(`${baseUrl.value}/import-issue`, {})
    importModal.value.open = false
    emit('saved', res.data)
  } catch (e: any) {
    importModal.value.error = e?.response?.data?.error || 'Aus verknüpften Issues konnte nichts geladen werden.'
  } finally { busy.value = '' }
}

// Eingefügten Text in den Kommentar übernehmen (score-neutral).
const onApplyImport = async () => {
  if (!props.requirement?.id || !importModal.value.text.trim()) return
  busy.value = 'import'
  importModal.value.error = ''
  try {
    const res = await apiClient.post(`${baseUrl.value}/import-issue`, { issue_context: importModal.value.text })
    importModal.value.open = false
    emit('saved', res.data)
  } catch (e: any) {
    importModal.value.error = e?.response?.data?.error || 'Import fehlgeschlagen.'
  } finally { busy.value = '' }
}

// #1521: Neubewertung mit Issue-Feedback — Kontext einfügen, dann KI-Stream.
const onShowReassessModal = () => {
  if (!props.requirement?.id) return
  reassessModal.value = { open: true, text: '' }
}
const onStartReassess = () => {
  // Eingefügter Text gewinnt; sonst Backend die verknüpften Issues sammeln lassen.
  const txt = reassessModal.value.text.trim()
  reassessModal.value.open = false
  autoError.value = ''
  autoDialog.value = { open: true, body: txt ? { issue_context: txt } : { use_issue_feedback: true } }
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
/* #1527: Transparenz-Block im Reassess-Modal */
.reassess-source {
  margin-top: 10px; padding: 8px 12px; border-radius: 6px;
  background: #f5faff; border: 1px solid #cfe3f7; font-size: 13px; color: #37474f;
}
.reassess-issue-list { margin: 6px 0 0; padding-left: 4px; list-style: none; }
.reassess-issue-list li { padding: 2px 0; font-size: 12px; }

/* #1520/#1526: „Neubewertung erforderlich"-Badge */
.reassess-badge {
  display: inline-block; margin-left: 8px; padding: 2px 8px;
  background: #fff3e0; color: #b26a00; border-radius: 10px;
  font-size: 0.78em; font-weight: 600; vertical-align: middle;
}

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
