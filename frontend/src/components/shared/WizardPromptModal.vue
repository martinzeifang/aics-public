<template>
  <div class="wpm-overlay" @mousedown.self="onClose" role="dialog" aria-modal="true" :aria-label="title">
    <div class="wpm-modal">
      <header class="wpm-header">
        <h2 class="wpm-title">🤖 {{ title }}</h2>
        <button class="wpm-close" type="button" aria-label="Schließen" @click="onClose">✕</button>
      </header>

      <!-- KI-Kennzeichnung / Disclaimer (#870) -->
      <p class="wpm-disclaimer">🤖 KI-generiert — fachlich zu prüfen.</p>

      <!-- Slot für Transparenz-Bausteine: DataPreviewWarning (#868) etc. -->
      <div v-if="$slots.before" class="wpm-slot">
        <slot name="before" />
      </div>

      <!-- (a) Prompt anzeigen + Kopieren -->
      <section class="wpm-section">
        <div class="wpm-section-head">
          <h3>1. Prompt für die KI</h3>
          <button class="wpm-btn wpm-copy" type="button" @click="copyPrompt">
            {{ copied ? '✓ Kopiert' : '📋 Kopieren' }}
          </button>
        </div>
        <p v-if="schemaHint" class="wpm-hint">{{ schemaHint }}</p>
        <pre class="wpm-prompt">{{ prompt }}</pre>
      </section>

      <!-- (b) KI-Antwort einfügen -->
      <section class="wpm-section">
        <div class="wpm-section-head">
          <h3>2. KI-Antwort einfügen</h3>
        </div>
        <textarea
          v-model="rawText"
          class="wpm-textarea"
          rows="8"
          placeholder="Antwort der KI hier einfügen (JSON)…"
          :disabled="busy"
        ></textarea>
      </section>

      <!-- Slot für Ziel-Hinweis: OutputDestinationHint (#869) etc. -->
      <div v-if="$slots.after" class="wpm-slot">
        <slot name="after" />
      </div>

      <!-- (c) Buttons -->
      <footer class="wpm-footer">
        <button class="wpm-btn wpm-cancel" type="button" :disabled="busy" @click="onClose">
          Abbrechen
        </button>
        <button
          class="wpm-btn wpm-apply"
          type="button"
          :disabled="busy || !rawText.trim()"
          @click="onApply"
        >
          {{ busy ? 'Übernehme…' : 'Übernehmen' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * WizardPromptModal — wiederverwendbares Copy-Paste-KI-Modal (#866).
 *
 * Ersetzt perspektivisch die modul-eigenen Inline-Modals (RequirementActions.vue
 * u. a.). Diese Komponente wird zunächst nur bereitgestellt und in einer
 * späteren Phase in die Modul-Views eingebunden.
 *
 * Props:
 *   - title:       Überschrift des Wizards.
 *   - prompt:      Anzuzeigender Prompt-Text (zum Kopieren).
 *   - schemaHint:  Optionaler Hinweis auf das erwartete JSON-Schema.
 *   - busy:        Lade-/Verarbeitungszustand (deaktiviert Eingaben).
 *
 * Slots:
 *   - before:  Transparenz vor dem Absenden (z. B. DataPreviewWarning, #868).
 *   - after:   Ziel-/Wirkungshinweis (z. B. OutputDestinationHint, #869).
 *
 * Emits:
 *   - apply(rawText):  Nutzer übernimmt die eingefügte KI-Antwort.
 *   - close:           Modal schließen/abbrechen.
 *
 * Teil von #865.
 */
import { ref } from 'vue'

const props = withDefaults(
  defineProps<{
    title: string
    prompt?: string
    schemaHint?: string
    busy?: boolean
  }>(),
  { prompt: '', schemaHint: '', busy: false },
)

const emit = defineEmits<{
  (e: 'apply', rawText: string): void
  (e: 'close'): void
}>()

const rawText = ref('')
const copied = ref(false)

async function copyPrompt() {
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(props.prompt)
    }
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch (e) {
    copied.value = false
  }
}

function onApply() {
  const text = rawText.value.trim()
  if (!text) return
  emit('apply', text)
}

function onClose() {
  emit('close')
}
</script>

<style scoped>
.wpm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.wpm-modal {
  background: var(--color-surface, #fff);
  color: var(--color-text-primary, #1a1a1a);
  border-radius: 10px;
  width: min(760px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.25);
  padding: 1.25rem 1.5rem 1.5rem;
}

.wpm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.wpm-title {
  font-size: 1.15rem;
  margin: 0;
  color: var(--color-primary, #0d47a1);
}

.wpm-close {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  color: #757575;
}

.wpm-disclaimer {
  margin: 0.5rem 0 1rem;
  padding: 0.4rem 0.7rem;
  background: #fff8e1;
  border: 1px solid #ffe082;
  border-radius: 6px;
  color: #e65100;
  font-size: 0.85rem;
}

.wpm-slot {
  margin-bottom: 1rem;
}

.wpm-section {
  margin-bottom: 1.1rem;
}

.wpm-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.4rem;
}

.wpm-section-head h3 {
  font-size: 0.95rem;
  margin: 0;
  color: #37474f;
}

.wpm-hint {
  font-size: 0.8rem;
  color: #607d8b;
  margin: 0 0 0.4rem;
}

.wpm-prompt {
  background: #263238;
  color: #eceff1;
  padding: 0.8rem;
  border-radius: 6px;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 0.8rem;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow-y: auto;
}

.wpm-textarea {
  width: 100%;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 0.85rem;
  padding: 0.6rem;
  border: 1px solid #cfd8dc;
  border-radius: 6px;
  resize: vertical;
  box-sizing: border-box;
}

.wpm-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 0.5rem;
}

.wpm-btn {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: 1px solid transparent;
  cursor: pointer;
  font-size: 0.85rem;
}

.wpm-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.wpm-copy {
  background: #eceff1;
  color: #37474f;
  border-color: #cfd8dc;
}

.wpm-cancel {
  background: #fff;
  color: #616161;
  border-color: #cfd8dc;
}

.wpm-apply {
  background: var(--color-primary, #1565c0);
  color: #fff;
}
</style>
