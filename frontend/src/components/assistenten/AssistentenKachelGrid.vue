<template>
  <div class="assistenten-grid">
    <div v-if="!wizards.length" class="empty">
      Für dieses Modul sind noch keine Assistenten verfügbar.
    </div>

    <template v-else-if="grouped">
      <section
        v-for="group in groups"
        :key="group.kategorie"
        class="kategorie-section"
      >
        <h3 class="kategorie-title">{{ group.label }}</h3>
        <div class="card-grid">
          <div
            v-for="w in group.wizards"
            :key="w.id"
            class="assistent-card-wrap"
          >
            <button
              type="button"
              class="assistent-card"
              :class="{ 'is-disabled': w.disabled }"
              :disabled="w.disabled"
              @click="onOpen(w)"
            >
              <div class="card-icon">{{ w.icon }}</div>
              <h4>{{ w.title }}</h4>
              <p>{{ w.description }}</p>
            </button>
            <button
              v-if="w.produces_document && canSaveDocument"
              type="button"
              class="save-doc-btn"
              title="Ergebnis dieses Assistenten als Dokument speichern"
              @click.stop="openSaveDialog(w)"
            >📄 Als Dokument speichern</button>
          </div>
        </div>
      </section>
    </template>

    <div v-else class="card-grid">
      <div
        v-for="w in wizards"
        :key="w.id"
        class="assistent-card-wrap"
      >
        <button
          type="button"
          class="assistent-card"
          :class="{ 'is-disabled': w.disabled }"
          :disabled="w.disabled"
          @click="onOpen(w)"
        >
          <div class="card-icon">{{ w.icon }}</div>
          <h4>{{ w.title }}</h4>
          <p>{{ w.description }}</p>
        </button>
        <button
          v-if="w.produces_document && canSaveDocument"
          type="button"
          class="save-doc-btn"
          title="Ergebnis dieses Assistenten als Dokument speichern"
          @click.stop="openSaveDialog(w)"
        >📄 Als Dokument speichern</button>
      </div>
    </div>

    <!-- Generischer „Als Dokument speichern"-Dialog (Sprint #24, Block C; #1235) -->
    <div v-if="saveDialog.open" class="save-doc-overlay" @mousedown.self="closeSaveDialog">
      <div class="save-doc-modal">
        <h3>📄 Als Dokument speichern</h3>

        <!-- Schritt 1: Eingabe -->
        <template v-if="!saveDialog.savedId">
          <p class="save-hint">
            Füge das Ergebnis von „{{ saveDialog.title }}" ein. Es wird als
            editierbares, versioniertes und exportierbares Dokument
            (Typ <code>{{ saveDialog.docType }}</code>) gespeichert.
          </p>
          <textarea
            v-model="saveDialog.text"
            rows="10"
            placeholder="Assistenten-Ergebnis (Markdown oder Text) hier einfügen…"
          ></textarea>
          <div v-if="saveDialog.error" class="save-error">{{ saveDialog.error }}</div>
          <div class="save-actions">
            <button class="btn-secondary" @click="closeSaveDialog">Abbrechen</button>
            <button
              class="btn-primary"
              :disabled="!saveDialog.text.trim() || saveDialog.busy"
              @click="confirmSave"
            >{{ saveDialog.busy ? 'Speichern…' : 'Speichern' }}</button>
          </div>
        </template>

        <!-- Schritt 2: Erfolg + Sprung ins Register (#1235) -->
        <template v-else>
          <div class="save-success">
            ✅ Dokument gespeichert. Es ist im Dokumente-Register editier-,
            freigabe- und exportierbar (DOCX/PDF).
          </div>
          <div class="save-actions">
            <button class="btn-secondary" @click="closeSaveDialog">Schließen</button>
            <button class="btn-primary" @click="goToRegister">
              📂 Im Register öffnen
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import {
  groupWizardsByKategorie,
  type WizardDescriptor,
} from './registry'
import { useDocumentsStore } from '../../stores/documents'
import markdownToHtml from '../../utils/markdownToHtml'

const props = withDefaults(
  defineProps<{
    /** Wizard tiles to render. */
    wizards: WizardDescriptor[]
    /** When true, tiles are grouped into category sections. */
    grouped?: boolean
    /**
     * Module + project context for the generic „Als Dokument speichern" action
     * (Sprint #24, Block C). When both are set, tiles whose descriptor carries
     * `produces_document` show a save action.
     */
    modul?: string
    projekt?: string | null
  }>(),
  {
    grouped: false,
    modul: '',
    projekt: null,
  },
)

const emit = defineEmits<{
  /** Emitted with the wizard id when an enabled tile is activated. */
  (e: 'open', id: string): void
  /** Emitted after a wizard result was stored as a document. */
  (e: 'document-saved', id: number): void
  /**
   * #1235: Request the host to navigate to the Dokumente-Register and open the
   * just-created document for editing/export. Hosts that show a register tab
   * should react; if unhandled, the success banner still informs the user.
   */
  (e: 'open-in-register', id: number): void
}>()

const documents = useDocumentsStore()

const groups = computed(() => groupWizardsByKategorie(props.wizards))

const canSaveDocument = computed(() => !!props.modul && !!props.projekt)

function onOpen(w: WizardDescriptor): void {
  if (w.disabled) return
  emit('open', w.id)
}

// ── Generischer „Als Dokument speichern"-Flow (Block C) ─────────────────────
const saveDialog = reactive({
  open: false,
  title: '',
  docType: '',
  assistantKey: '',
  text: '',
  busy: false,
  error: '',
  savedId: null as number | null,
})

function openSaveDialog(w: WizardDescriptor, prefillText = ''): void {
  if (!w.produces_document || !canSaveDocument.value) return
  saveDialog.open = true
  saveDialog.title = w.title
  saveDialog.docType = w.produces_document.doc_type
  saveDialog.assistantKey = w.id
  saveDialog.text = prefillText || ''
  saveDialog.error = ''
  saveDialog.busy = false
  saveDialog.savedId = null
}

/**
 * #1445–#1449: Open the save dialog for a specific wizard id and pre-fill it with
 * the text a per-module wizard modal produced (parsed markdown / direct-API text).
 * Returns true when the dialog was opened (wizard found + savable), false otherwise.
 */
function openSaveDialogFor(wizardId: string, text: string): boolean {
  const w = props.wizards.find((x) => x.id === wizardId)
  if (!w || !w.produces_document || !canSaveDocument.value) return false
  openSaveDialog(w, text)
  return true
}

defineExpose({ openSaveDialogFor })

function closeSaveDialog(): void {
  saveDialog.open = false
  saveDialog.savedId = null
}

async function confirmSave(): Promise<void> {
  if (!props.modul || !props.projekt || !saveDialog.text.trim()) return
  saveDialog.busy = true
  saveDialog.error = ''
  const html = markdownToHtml(saveDialog.text)
  // #1235: generische „Wizard-Ergebnis → managed_doc"-Funktion (source='assistent').
  const id = await documents.createFromAssistant(
    props.modul,
    props.projekt,
    saveDialog.docType,
    saveDialog.assistantKey,
    html,
  )
  saveDialog.busy = false
  if (id != null) {
    emit('document-saved', id)
    saveDialog.savedId = id  // Erfolgs-Schritt mit „Im Register öffnen"
  } else {
    saveDialog.error =
      documents.keyState(props.modul, props.projekt).error ||
      'Dokument konnte nicht gespeichert werden.'
  }
}

function goToRegister(): void {
  if (saveDialog.savedId != null) emit('open-in-register', saveDialog.savedId)
  closeSaveDialog()
}
</script>

<style scoped>
.assistenten-grid {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.empty {
  padding: 24px;
  color: var(--color-text-secondary);
  font-size: 14px;
  text-align: center;
  background: var(--color-surface);
  border: 1px dashed var(--color-border);
  border-radius: 8px;
}

.kategorie-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.kategorie-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.assistent-card-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.assistent-card-wrap .assistent-card {
  flex: 1;
  width: 100%;
}

.save-doc-btn {
  background: #f3e5f5;
  color: #7b1fa2;
  border: 1px solid #ce93d8;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
}
.save-doc-btn:hover { background: #e1bee7; }

.save-doc-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1300;
}
.save-doc-modal {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  width: 640px;
  max-width: 95%;
}
.save-doc-modal h3 { margin: 0 0 8px; color: #1565c0; }
.save-hint { font-size: 13px; color: #666; margin: 0 0 12px; line-height: 1.4; }
.save-hint code { background: #f5f5f5; padding: 1px 6px; border-radius: 3px; }
.save-doc-modal textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font: 13px/1.5 monospace;
  resize: vertical;
}
.save-error {
  background: #ffebee;
  color: #c62828;
  border: 1px solid #ef5350;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 13px;
  margin-top: 10px;
}
.save-success {
  background: #e8f5e9;
  color: #2e7d32;
  border: 1px solid #a5d6a7;
  padding: 12px 14px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.5;
}
.save-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.save-actions .btn-primary {
  background: #1565c0; color: #fff; border: none;
  padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px;
}
.save-actions .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.save-actions .btn-secondary {
  background: #e0e0e0; color: #333; border: none;
  padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px;
}

.assistent-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 24px;
  text-align: left;
  cursor: pointer;
  color: inherit;
  font: inherit;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: transform 150ms, box-shadow 150ms, border-color 150ms;
}
.assistent-card:hover:not(.is-disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
  border-color: var(--color-primary);
}
.assistent-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
.assistent-card.is-disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.card-icon {
  font-size: 32px;
}
.assistent-card h4 {
  margin: 0;
  font-size: 16px;
  color: var(--color-primary);
}
.assistent-card p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.4;
}
</style>
