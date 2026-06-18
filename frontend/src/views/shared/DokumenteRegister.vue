<template>
  <div class="dokumente-register">
    <div v-if="!projekt" class="empty-state">
      <p>Bitte zuerst ein Projekt auswählen, um die Dokumentation zu verwalten.</p>
    </div>

    <template v-else>
      <div v-if="error" class="alert-error">{{ error }}</div>
      <div v-if="loading" class="hint">Lädt Dokumenten-Katalog…</div>

      <template v-else-if="catalog">
        <!-- Pflichtdokumente -->
        <section class="section">
          <h3 class="section-title">📋 Pflichtdokumente</h3>
          <div v-if="catalog.katalog.length === 0" class="hint">
            Für dieses Modul sind keine Pflichtdokumente definiert.
          </div>
          <div v-else class="card-grid">
            <div v-for="spec in catalog.katalog" :key="spec.doc_type" class="doc-card">
              <div class="card-head">
                <span class="status-pill" :class="spec.status">{{ statusLabel(spec.status) }}</span>
                <span v-if="spec.pflicht" class="pflicht-badge" title="Pflichtdokument">Pflicht</span>
                <span v-if="spec.doc_mode === 'extern'" class="link-badge" title="Externe Web-Doku">🔗 Web-Link</span>
              </div>
              <h4 class="card-title">{{ spec.titel }}</h4>
              <p v-if="spec.rechtsgrundlage" class="card-legal">{{ spec.rechtsgrundlage }}</p>
              <p v-if="spec.beschreibung" class="card-desc">{{ spec.beschreibung }}</p>
              <details v-if="spec.erklaerung" class="card-why">
                <summary>ℹ️ Wofür ist das?</summary>
                <p>{{ spec.erklaerung }}</p>
              </details>
              <a
                v-if="spec.doc_mode === 'extern' && spec.external_url"
                class="card-link"
                :href="spec.external_url"
                target="_blank"
                rel="noopener noreferrer"
              >↗️ {{ spec.external_url }}</a>

              <div class="card-actions">
                <button
                  v-if="spec.vorhanden && spec.doc_id != null"
                  class="btn-mini btn-primary-mini"
                  @click="openExisting(spec.doc_id)"
                >✏️ Bearbeiten</button>
                <button
                  v-else
                  class="btn-mini btn-primary-mini"
                  :disabled="busyType === spec.doc_type"
                  @click="createAndEdit(spec)"
                >✏️ Erstellen</button>

                <button
                  v-if="spec.suggested_assistant"
                  class="btn-mini btn-assist"
                  @click="emit('open-assistent', spec.suggested_assistant)"
                  title="Mit dem vorgeschlagenen Assistenten erstellen"
                >🤖 Mit Assistent erstellen</button>

                <template v-if="spec.vorhanden && spec.doc_id != null">
                  <button class="btn-mini" :disabled="exportingId === spec.doc_id" @click="exportDoc(spec.doc_id, 'docx')">⬇️ Word</button>
                  <button class="btn-mini" :disabled="exportingId === spec.doc_id" @click="exportDoc(spec.doc_id, 'pdf')">⬇️ PDF</button>
                </template>
              </div>
            </div>
          </div>
        </section>

        <!-- Weitere Dokumente -->
        <section class="section">
          <div class="section-header">
            <h3 class="section-title">📄 Weitere Dokumente</h3>
            <button class="btn-mini btn-primary-mini" @click="freeDialogOpen = true">➕ Neues Dokument</button>
          </div>
          <div v-if="catalog.weitere.length === 0" class="hint">
            Noch keine weiteren (freien) Dokumente angelegt.
          </div>
          <div v-else class="card-grid">
            <div v-for="d in catalog.weitere" :key="d.id" class="doc-card">
              <div class="card-head">
                <span class="status-pill" :class="d.status">{{ statusLabel(d.status) }}</span>
                <span class="type-badge">{{ d.doc_type }}</span>
                <span v-if="d.doc_mode === 'extern'" class="link-badge" title="Externe Web-Doku">🔗 Web-Link</span>
              </div>
              <h4 class="card-title">{{ d.titel || d.doc_type }}</h4>
              <p v-if="d.rechtsgrundlage" class="card-legal">{{ d.rechtsgrundlage }}</p>
              <a
                v-if="d.doc_mode === 'extern' && d.external_url"
                class="card-link"
                :href="d.external_url"
                target="_blank"
                rel="noopener noreferrer"
              >↗️ {{ d.external_url }}</a>
              <div class="card-actions">
                <button class="btn-mini btn-primary-mini" @click="openExisting(d.id)">✏️ Bearbeiten</button>
                <button class="btn-mini" :disabled="exportingId === d.id" @click="exportDoc(d.id, 'docx')">⬇️ Word</button>
                <button class="btn-mini" :disabled="exportingId === d.id" @click="exportDoc(d.id, 'pdf')">⬇️ PDF</button>
              </div>
            </div>
          </div>
        </section>
      </template>
    </template>

    <!-- Freies-Dokument-Dialog -->
    <div v-if="freeDialogOpen" class="modal-overlay" @mousedown.self="freeDialogOpen = false">
      <div class="modal">
        <h3>Neues Dokument</h3>
        <div class="form-row">
          <label>Dokumenttyp / Schlüssel *</label>
          <input v-model="freeForm.doc_type" placeholder="z.B. interne_richtlinie" />
        </div>
        <div class="form-row">
          <label>Titel</label>
          <input v-model="freeForm.titel" placeholder="Titel des Dokuments" />
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="freeDialogOpen = false">Abbrechen</button>
          <button class="btn-primary" :disabled="!freeForm.doc_type.trim()" @click="createFree">Anlegen</button>
        </div>
      </div>
    </div>

    <!-- Editor -->
    <DocumentEditor
      v-if="editing"
      :modul="modul"
      :projekt="projekt as string"
      :document="editing"
      @saved="onEditorSaved"
      @close="editing = null"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import DocumentEditor from '../../components/shared/DocumentEditor.vue'
import {
  useDocumentsStore,
  type Document,
  type DocSpec,
  type CatalogStatus,
} from '../../stores/documents'

const props = defineProps<{
  modul: string
  projekt: string | null
  /** #1235: Dokument-ID, die nach dem Mounten direkt geöffnet werden soll. */
  autoOpenId?: number | null
}>()

const emit = defineEmits<{
  (e: 'open-assistent', assistantKey: string): void
}>()

const store = useDocumentsStore()

const slice = computed(() => store.keyState(props.modul, props.projekt))
const catalog = computed(() => slice.value.catalog)
const loading = computed(() => slice.value.loading)
const error = computed(() => slice.value.error)

const editing = ref<Document | null>(null)
const busyType = ref<string | null>(null)
const exportingId = ref<number | null>(null)

const freeDialogOpen = ref(false)
const freeForm = ref({ doc_type: '', titel: '' })

function statusLabel(s: CatalogStatus): string {
  if (s === 'final') return 'Final'
  if (s === 'freigegeben') return 'Freigegeben'
  if (s === 'entwurf') return 'Entwurf'
  return 'Fehlt'
}

async function reload() {
  if (!props.projekt) return
  await store.fetchCatalog(props.modul, props.projekt)
}

async function openExisting(id: number) {
  if (!props.projekt) return
  const doc = await store.fetchDocument(props.modul, props.projekt, id)
  if (doc) editing.value = doc
}

async function createAndEdit(spec: DocSpec) {
  if (!props.projekt) return
  busyType.value = spec.doc_type
  const id = await store.createDocument(props.modul, props.projekt, {
    doc_type: spec.doc_type,
    titel: spec.titel,
  })
  busyType.value = null
  if (id != null) await openExisting(id)
}

async function createFree() {
  if (!props.projekt) return
  const docType = freeForm.value.doc_type.trim()
  if (!docType) return
  const id = await store.createDocument(props.modul, props.projekt, {
    doc_type: docType,
    titel: freeForm.value.titel.trim() || undefined,
  })
  freeDialogOpen.value = false
  freeForm.value = { doc_type: '', titel: '' }
  if (id != null) await openExisting(id)
}

async function exportDoc(id: number, format: 'docx' | 'pdf') {
  if (!props.projekt) return
  exportingId.value = id
  try {
    await store.exportDocument(props.modul, props.projekt, id, format)
  } catch (e: any) {
    const status = e?.response?.status
    if (format === 'pdf' && status === 503) {
      alert('PDF-Konverter ist derzeit nicht verfügbar — bitte als Word (DOCX) exportieren.')
    } else {
      alert(e?.response?.data?.error || e?.message || 'Export fehlgeschlagen.')
    }
  } finally {
    exportingId.value = null
  }
}

async function onEditorSaved() {
  await reload()
}

async function maybeAutoOpen() {
  if (props.autoOpenId != null && props.projekt) {
    await reload()
    await openExisting(props.autoOpenId)
  }
}

onMounted(async () => {
  await reload()
  await maybeAutoOpen()
})
watch(() => props.projekt, reload)
watch(() => props.modul, reload)
// #1235: Wenn der Host eine Dokument-ID setzt (Sprung aus dem Assistenten),
// das Dokument direkt im Editor öffnen.
watch(() => props.autoOpenId, maybeAutoOpen)
</script>

<style scoped>
.dokumente-register { padding: 8px 0; }

.empty-state {
  background: #fff;
  border: 1px dashed var(--color-border, #ddd);
  border-radius: 8px;
  padding: 32px;
  text-align: center;
  color: #888;
}

.alert-error {
  background: #ffebee;
  color: #c62828;
  border: 1px solid #ef5350;
  padding: 10px 14px;
  border-radius: 4px;
  margin-bottom: 12px;
}
.hint { color: #888; font-size: 13px; padding: 12px 0; }

.section { margin-bottom: 28px; }
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.section-title { margin: 0 0 12px; font-size: 16px; color: #1565c0; }
.section-header .section-title { margin: 0; }

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.doc-card {
  background: #fff;
  border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.card-title { margin: 0; font-size: 15px; color: #222; }
.card-legal { margin: 0; font-size: 12px; color: #1565c0; font-weight: 600; }
.card-desc { margin: 0; font-size: 12px; color: #666; line-height: 1.4; }

.card-why {
  font-size: 12px;
  border: 1px solid #e3f2fd;
  background: #f8fbff;
  border-radius: 4px;
  padding: 0;
}
.card-why summary {
  cursor: pointer;
  padding: 6px 10px;
  color: #1565c0;
  font-weight: 600;
  list-style: none;
  user-select: none;
}
.card-why summary::-webkit-details-marker { display: none; }
.card-why[open] summary { border-bottom: 1px solid #e3f2fd; }
.card-why p {
  margin: 0;
  padding: 8px 10px;
  color: #555;
  line-height: 1.5;
}

.status-pill {
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}
.status-pill.fehlt { background: #eceff1; color: #607d8b; }
.status-pill.entwurf { background: #fff8e1; color: #e65100; }
.status-pill.final { background: #e3f2fd; color: #1565c0; }
.status-pill.freigegeben { background: #e8f5e9; color: #2e7d32; }

.pflicht-badge {
  background: #fce4ec;
  color: #ad1457;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}
.type-badge {
  background: #f5f5f5;
  color: #666;
  font-size: 10px;
  font-family: monospace;
  padding: 2px 8px;
  border-radius: 4px;
}
.link-badge {
  background: #e1f5fe;
  color: #0277bd;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}
.card-link {
  font-size: 12px;
  color: #0277bd;
  word-break: break-all;
  text-decoration: none;
}
.card-link:hover { text-decoration: underline; }

.card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: auto;
  padding-top: 6px;
}

.btn-mini {
  padding: 5px 10px;
  border: 1px solid var(--color-border, #ddd);
  background: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: #333;
}
.btn-mini:hover:not(:disabled) { background: #f5f5f5; }
.btn-mini:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary-mini { background: #1565c0; color: #fff; border-color: #1565c0; }
.btn-primary-mini:hover:not(:disabled) { background: #0d47a1; }
.btn-assist { background: #f3e5f5; color: #7b1fa2; border-color: #ce93d8; }
.btn-assist:hover:not(:disabled) { background: #e1bee7; }

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}
.modal {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  width: 440px;
  max-width: 95%;
}
.modal h3 { margin: 0 0 16px; color: #1565c0; }
.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 4px;
  font-size: 13px;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.btn-primary, .btn-secondary {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.btn-primary { background: #1565c0; color: #fff; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: #e0e0e0; color: #333; }
</style>
