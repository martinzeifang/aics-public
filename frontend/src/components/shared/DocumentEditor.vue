<template>
  <div class="doc-editor-overlay" @mousedown.self="onClose">
    <div class="doc-editor">
      <header class="editor-header">
        <div class="header-main">
          <span class="doc-type-label">{{ doc.doc_type }}</span>
          <input
            v-model="titelDraft"
            class="titel-input"
            placeholder="Titel des Dokuments"
          />
        </div>
        <button class="btn-close" title="Schließen" @click="onClose">✕</button>
      </header>

      <div class="meta-bar">
        <div class="meta-item" v-if="doc.rechtsgrundlage">
          <span class="meta-key">Rechtsgrundlage</span>
          <span class="meta-val">{{ doc.rechtsgrundlage }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-key">Version</span>
          <span class="meta-val">v{{ doc.version }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-key">Status</span>
          <span class="status-pill" :class="doc.status">{{ statusLabel(doc.status) }}</span>
        </div>
      </div>

      <div v-if="error" class="alert-error">{{ error }}</div>

      <!-- Status-Workflow -->
      <div class="workflow-bar">
        <span class="workflow-label">Status-Workflow:</span>
        <button
          class="wf-step"
          :class="{ active: doc.status === 'entwurf' }"
          :disabled="busy"
          @click="changeStatus('entwurf')"
        >Entwurf</button>
        <span class="wf-arrow">→</span>
        <button
          class="wf-step"
          :class="{ active: doc.status === 'final' }"
          :disabled="busy"
          @click="changeStatus('final')"
        >Final</button>
        <span class="wf-arrow">→</span>
        <button
          class="wf-step wf-approve"
          :class="{ active: doc.status === 'freigegeben' }"
          :disabled="busy"
          @click="changeStatus('freigegeben')"
        >Freigegeben</button>
      </div>

      <div v-if="doc.status === 'freigegeben'" class="lock-hint">
        🔒 Dieses Dokument ist freigegeben. Eine erneute Bearbeitung und Speicherung
        erhöht die Version.
      </div>

      <div class="editor-body">
        <RichEditor v-model="contentDraft" />
      </div>

      <footer class="editor-footer">
        <button class="btn-danger" :disabled="busy" @click="onDelete">🗑️ Löschen</button>
        <div class="spacer"></div>
        <button class="btn-secondary" :disabled="busy || exporting" @click="onExport('docx')">⬇️ Word</button>
        <button class="btn-secondary" :disabled="busy || exporting" @click="onExport('pdf')">⬇️ PDF</button>
        <button class="btn-primary" :disabled="busy || !dirty" @click="onSave">
          {{ busy ? '⏳ Speichern…' : '💾 Speichern' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import RichEditor from '../RichEditor.vue'
import { useDocumentsStore, type Document, type DocStatus } from '../../stores/documents'

const props = defineProps<{
  modul: string
  projekt: string
  /** Das zu bearbeitende Dokument (Quelle der Wahrheit). */
  document: Document
}>()

const emit = defineEmits<{
  (e: 'saved'): void
  (e: 'close'): void
}>()

const store = useDocumentsStore()

// Lokale Kopie, die wir bei Aktionen aus dem Store-Result aktualisieren.
const doc = ref<Document>({ ...props.document })

const titelDraft = ref(doc.value.titel || '')
const contentDraft = ref(doc.value.content_html || '')

const busy = ref(false)
const exporting = ref(false)
const error = ref('')

watch(
  () => props.document,
  (d) => {
    doc.value = { ...d }
    titelDraft.value = d.titel || ''
    contentDraft.value = d.content_html || ''
  },
)

const dirty = computed(
  () =>
    titelDraft.value !== (doc.value.titel || '') ||
    contentDraft.value !== (doc.value.content_html || ''),
)

function statusLabel(s: DocStatus): string {
  if (s === 'final') return 'Final'
  if (s === 'freigegeben') return 'Freigegeben'
  return 'Entwurf'
}

function applyResult(updated: Document | null) {
  if (updated) doc.value = { ...updated }
}

async function onSave() {
  busy.value = true
  error.value = ''
  const updated = await store.updateDocument(props.modul, props.projekt, doc.value.id, {
    titel: titelDraft.value,
    content_html: contentDraft.value,
  })
  busy.value = false
  if (updated) {
    applyResult(updated)
    titelDraft.value = doc.value.titel || ''
    contentDraft.value = doc.value.content_html || ''
    emit('saved')
  } else {
    error.value = store.keyState(props.modul, props.projekt).error || 'Speichern fehlgeschlagen.'
  }
}

async function changeStatus(status: DocStatus) {
  if (status === doc.value.status) return
  if (status === 'freigegeben') {
    if (!confirm('Dokument wirklich freigeben? Freigegebene Dokumente werden als verbindlich markiert.')) {
      return
    }
  }
  busy.value = true
  error.value = ''
  const updated = await store.setStatus(props.modul, props.projekt, doc.value.id, status)
  busy.value = false
  if (updated) {
    applyResult(updated)
    emit('saved')
  } else {
    error.value = store.keyState(props.modul, props.projekt).error || 'Statuswechsel fehlgeschlagen.'
  }
}

async function onExport(format: 'docx' | 'pdf') {
  exporting.value = true
  error.value = ''
  try {
    await store.exportDocument(props.modul, props.projekt, doc.value.id, format)
  } catch (e: any) {
    const status = e?.response?.status
    if (format === 'pdf' && status === 503) {
      error.value = 'PDF-Konverter ist derzeit nicht verfügbar — bitte als Word (DOCX) exportieren.'
    } else {
      error.value = e?.response?.data?.error || e?.message || 'Export fehlgeschlagen.'
    }
  } finally {
    exporting.value = false
  }
}

async function onDelete() {
  if (!confirm(`Dokument „${doc.value.titel || doc.value.doc_type}" wirklich löschen?`)) return
  busy.value = true
  error.value = ''
  const ok = await store.deleteDocument(props.modul, props.projekt, doc.value.id)
  busy.value = false
  if (ok) {
    emit('saved')
    emit('close')
  } else {
    error.value = store.keyState(props.modul, props.projekt).error || 'Löschen fehlgeschlagen.'
  }
}

function onClose() {
  emit('close')
}
</script>

<style scoped>
.doc-editor-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: flex-end;
  z-index: 1200;
}
.doc-editor {
  background: #fff;
  width: 720px;
  max-width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.2);
}

.editor-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: #1565c0;
  color: #fff;
}
.header-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.doc-type-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #90caf9;
}
.titel-input {
  border: none;
  border-bottom: 1px solid rgba(255, 255, 255, 0.4);
  background: transparent;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  padding: 4px 2px;
  outline: none;
}
.titel-input::placeholder { color: rgba(255, 255, 255, 0.6); }
.btn-close {
  background: none;
  border: none;
  color: #fff;
  font-size: 22px;
  cursor: pointer;
  line-height: 1;
}

.meta-bar {
  display: flex;
  gap: 24px;
  padding: 10px 20px;
  background: #f5f7fa;
  border-bottom: 1px solid #e0e0e0;
  flex-wrap: wrap;
}
.meta-item { display: flex; flex-direction: column; gap: 2px; }
.meta-key { font-size: 10px; color: #888; text-transform: uppercase; letter-spacing: 0.04em; }
.meta-val { font-size: 13px; color: #333; font-weight: 600; }

.status-pill {
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  width: fit-content;
}
.status-pill.entwurf { background: #fff8e1; color: #e65100; }
.status-pill.final { background: #e3f2fd; color: #1565c0; }
.status-pill.freigegeben { background: #e8f5e9; color: #2e7d32; }

.workflow-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-bottom: 1px solid #eee;
  flex-wrap: wrap;
}
.workflow-label { font-size: 12px; color: #666; margin-right: 4px; }
.wf-step {
  padding: 5px 14px;
  border: 1px solid #cfd8dc;
  background: #fff;
  border-radius: 16px;
  cursor: pointer;
  font-size: 12px;
  color: #555;
}
.wf-step:hover:not(:disabled) { border-color: #1565c0; color: #1565c0; }
.wf-step.active { background: #1565c0; color: #fff; border-color: #1565c0; }
.wf-step.wf-approve.active { background: #2e7d32; border-color: #2e7d32; }
.wf-step:disabled { opacity: 0.5; cursor: not-allowed; }
.wf-arrow { color: #bbb; font-size: 12px; }

.lock-hint {
  margin: 0 20px;
  background: #fff8e1;
  border: 1px solid #ffe082;
  color: #e65100;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 12px;
}

.alert-error {
  margin: 10px 20px 0;
  background: #ffebee;
  color: #c62828;
  border: 1px solid #ef5350;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 13px;
}

.editor-body {
  flex: 1;
  overflow: auto;
  padding: 16px 20px;
}

.editor-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid #e0e0e0;
  background: #fafafa;
}
.editor-footer .spacer { flex: 1; }

.btn-primary, .btn-secondary, .btn-danger {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.btn-primary { background: #1565c0; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #0d47a1; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-secondary:hover:not(:disabled) { background: #d5d5d5; }
.btn-danger { background: #ffebee; color: #c62828; border: 1px solid #ef5350; }
.btn-danger:hover:not(:disabled) { background: #ffcdd2; }
.btn-primary:disabled, .btn-secondary:disabled, .btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

@media (max-width: 768px) {
  .doc-editor { width: 100%; }
}
</style>
