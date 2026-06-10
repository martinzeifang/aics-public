<template>
  <!-- #1234: Konformitäts-Checkliste (Soll-Ist) — nur sichtbar, wenn Items existieren -->
  <div v-if="checklist && checklist.items.length" class="checklist-panel">
    <div class="cl-head">
      <h4 class="cl-title">✅ Konformitäts-Checkliste</h4>
      <div class="cl-progress">
        <div class="cl-bar">
          <div class="cl-bar-fill" :style="{ width: progressPct + '%' }"></div>
        </div>
        <span class="cl-progress-text">
          {{ checklist.fortschritt.erfuellt }}/{{ checklist.fortschritt.gesamt }} erfüllt
          <template v-if="checklist.fortschritt.pflicht_gesamt">
            · Pflicht {{ checklist.fortschritt.pflicht_erfuellt }}/{{ checklist.fortschritt.pflicht_gesamt }}
          </template>
        </span>
      </div>
    </div>

    <div v-if="error" class="cl-error">{{ error }}</div>

    <ul class="cl-list">
      <li v-for="it in checklist.items" :key="it.id" class="cl-item">
        <label class="cl-check">
          <input
            type="checkbox"
            :checked="it.erfuellt"
            :disabled="busy"
            @change="toggle(it, ($event.target as HTMLInputElement).checked)"
          />
          <span class="cl-label">
            {{ it.label }}
            <span v-if="it.pflicht" class="cl-pflicht">Pflicht</span>
            <span v-else class="cl-optional">optional</span>
          </span>
        </label>
        <span v-if="it.rechtsbezug" class="cl-legal">{{ it.rechtsbezug }}</span>
        <span
          v-if="suggestions[it.id] !== undefined && suggestions[it.id] !== it.erfuellt"
          class="cl-suggest"
          :title="'KI-Vorschlag — bitte selbst bestätigen'"
        >🤖 Vorschlag: {{ suggestions[it.id] ? 'erfüllt' : 'offen' }}</span>
      </li>
    </ul>

    <!-- #1236: Querverweis-Bausteine (vorhandene Modul-Daten als Bestandteil) -->
    <div v-if="checklist.bausteine && checklist.bausteine.length" class="cl-bausteine">
      <span class="cl-bausteine-title">🔗 Vorhandene Bausteine (keine Datendopplung):</span>
      <ul>
        <li v-for="b in checklist.bausteine" :key="b.ziel">
          <strong>{{ b.label }}</strong> — {{ b.hinweis }}
        </li>
      </ul>
    </div>

    <div class="cl-actions">
      <button class="btn-secondary" :disabled="busy" @click="onAiCheck">
        🤖 KI-Prüfung (Prompt)
      </button>
    </div>

    <!-- KI-Prüf-Dialog (Copy/Paste) -->
    <div v-if="aiOpen" class="cl-ai-overlay" @mousedown.self="aiOpen = false">
      <div class="cl-ai-modal">
        <h3>🤖 KI-Prüfung der Pflichtinhalte</h3>
        <p class="cl-ai-hint">
          1. Prompt kopieren und in den KI-Assistenten einfügen.
          2. Die JSON-Antwort hier einfügen — die Häkchen werden <strong>vorgeschlagen</strong>,
          aber nicht automatisch gesetzt. Du entscheidest final.
        </p>
        <label class="cl-ai-label">Prompt</label>
        <textarea class="cl-ai-prompt" :value="aiPrompt" rows="6" readonly></textarea>
        <button class="btn-mini" @click="copyPrompt">📋 Prompt kopieren</button>
        <label class="cl-ai-label">KI-Antwort (JSON) einfügen</label>
        <textarea
          v-model="aiResponse"
          class="cl-ai-prompt"
          rows="6"
          placeholder='{"items": [{"id": "...", "erfuellt": true}]}'
        ></textarea>
        <div v-if="aiError" class="cl-error">{{ aiError }}</div>
        <div class="cl-ai-actions">
          <button class="btn-secondary" @click="aiOpen = false">Schließen</button>
          <button class="btn-primary" :disabled="!aiResponse.trim()" @click="applySuggestions">
            Vorschläge übernehmen
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useDocumentsStore, type Checklist, type ChecklistItem } from '../../stores/documents'

const props = defineProps<{
  modul: string
  projekt: string
  docId: number
}>()
// #1251: dem Editor melden, ob eine Checkliste existiert (→ Zwei-Spalten-Layout).
const emit = defineEmits<{ (e: 'has-items', value: boolean): void }>()

const store = useDocumentsStore()

const checklist = ref<Checklist | null>(null)
const busy = ref(false)
const error = ref('')

const aiOpen = ref(false)
const aiPrompt = ref('')
const aiResponse = ref('')
const aiError = ref('')
/** KI-Vorschläge (nicht verbindlich) je item_id. */
const suggestions = ref<Record<string, boolean>>({})

const progressPct = computed(() => {
  const f = checklist.value?.fortschritt
  if (!f || !f.gesamt) return 0
  return Math.round((f.erfuellt / f.gesamt) * 100)
})

async function load() {
  checklist.value = await store.fetchChecklist(props.modul, props.projekt, props.docId)
  emit('has-items', !!(checklist.value && checklist.value.items.length))
}

async function toggle(it: ChecklistItem, checked: boolean) {
  busy.value = true
  error.value = ''
  const ok = await store.saveChecklist(props.modul, props.projekt, props.docId, {
    [it.id]: { erfuellt: checked, kommentar: it.kommentar || '' },
  })
  busy.value = false
  if (ok) {
    await load()
  } else {
    error.value = store.keyState(props.modul, props.projekt).error || 'Speichern fehlgeschlagen.'
  }
}

async function onAiCheck() {
  aiError.value = ''
  aiResponse.value = ''
  const p = await store.fetchChecklistPrompt(props.modul, props.projekt, props.docId)
  if (p) {
    aiPrompt.value = p
    aiOpen.value = true
  } else {
    error.value = store.keyState(props.modul, props.projekt).error || 'Prompt konnte nicht erzeugt werden.'
  }
}

async function copyPrompt() {
  try {
    await navigator.clipboard.writeText(aiPrompt.value)
  } catch {
    /* ignore — Nutzer kann manuell markieren */
  }
}

function applySuggestions() {
  aiError.value = ''
  try {
    const parsed = JSON.parse(aiResponse.value)
    const items = Array.isArray(parsed?.items) ? parsed.items : []
    const next: Record<string, boolean> = {}
    for (const it of items) {
      if (it && typeof it.id === 'string') next[it.id] = !!it.erfuellt
    }
    if (!Object.keys(next).length) {
      aiError.value = 'Keine gültigen Items in der Antwort gefunden.'
      return
    }
    // NICHT automatisch setzen — nur als Vorschlag anzeigen.
    suggestions.value = next
    aiOpen.value = false
  } catch {
    aiError.value = 'Antwort ist kein gültiges JSON.'
  }
}

onMounted(load)
watch(() => props.docId, load)
</script>

<style scoped>
.checklist-panel {
  border-top: 1px solid #eee;
  padding: 14px 20px;
  background: #fafcff;
}
.cl-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.cl-title { margin: 0; font-size: 14px; color: #1565c0; }
.cl-progress { display: flex; align-items: center; gap: 8px; }
.cl-bar { width: 140px; height: 8px; background: #e0e0e0; border-radius: 4px; overflow: hidden; }
.cl-bar-fill { height: 100%; background: #2e7d32; transition: width 200ms; }
.cl-progress-text { font-size: 12px; color: #555; }

.cl-list { list-style: none; margin: 12px 0 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.cl-item { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.cl-check { display: flex; align-items: baseline; gap: 8px; cursor: pointer; flex: 1; }
.cl-label { font-size: 13px; color: #333; }
.cl-pflicht { background: #fce4ec; color: #ad1457; font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 8px; margin-left: 6px; }
.cl-optional { background: #eceff1; color: #607d8b; font-size: 10px; padding: 1px 6px; border-radius: 8px; margin-left: 6px; }
.cl-legal { font-size: 11px; color: #1565c0; font-weight: 600; }
.cl-suggest { font-size: 11px; color: #7b1fa2; background: #f3e5f5; padding: 1px 8px; border-radius: 8px; }

.cl-bausteine { margin-top: 14px; background: #eef5ff; border-left: 3px solid #1565c0; padding: 8px 12px; border-radius: 4px; }
.cl-bausteine-title { font-size: 12px; font-weight: 600; color: #1565c0; }
.cl-bausteine ul { margin: 6px 0 0; padding-left: 18px; }
.cl-bausteine li { font-size: 12px; color: #444; line-height: 1.5; }

.cl-actions { margin-top: 12px; }
.cl-error { background: #ffebee; color: #c62828; border: 1px solid #ef5350; padding: 6px 10px; border-radius: 4px; font-size: 12px; margin: 8px 0; }

.btn-secondary { background: #e0e0e0; color: #333; border: none; padding: 7px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #1565c0; color: #fff; border: none; padding: 7px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-mini { background: #fff; border: 1px solid #ddd; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; margin: 6px 0; }

.cl-ai-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1400; }
.cl-ai-modal { background: #fff; border-radius: 8px; padding: 24px; width: 680px; max-width: 95%; max-height: 90vh; overflow: auto; }
.cl-ai-modal h3 { margin: 0 0 8px; color: #1565c0; }
.cl-ai-hint { font-size: 12px; color: #666; line-height: 1.5; margin: 0 0 12px; }
.cl-ai-label { display: block; font-weight: 600; font-size: 12px; margin: 10px 0 4px; color: #333; }
.cl-ai-prompt { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font: 12px/1.4 monospace; resize: vertical; }
.cl-ai-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
</style>
