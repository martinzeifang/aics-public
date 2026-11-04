<template>
  <div class="pzf">
    <label class="pzf-label" :for="feldId">
      💭 Eigene Hinweise <span class="pzf-opt">(optional)</span>
    </label>
    <textarea
      :id="feldId"
      class="pzf-text"
      rows="3"
      :maxlength="grenze"
      :disabled="disabled"
      :placeholder="platzhalter"
      :value="modelValue"
      @input="onInput"
    ></textarea>
    <!-- #1835: Woher die Vorbelegung stammt. Ein Text, den ein Kollege vor
         Wochen gespeichert hat, darf nicht wie der eigene aussehen. -->
    <p v-if="geerbtVon" class="pzf-herkunft">
      📌 Vorbelegt aus den Projekt-Hinweisen<span v-if="geerbtVon !== '—'"> — gesetzt von
      {{ geerbtVon }}</span>. Für diesen Lauf überschreibbar.
    </p>
    <div v-if="kannMerken" class="pzf-merken">
      <button type="button" class="pzf-btn" :disabled="disabled || speichert"
              @click="merken">
        {{ speichert ? '⏳ …' : '💾 Für dieses Projekt merken' }}
      </button>
      <button v-if="geerbtVon" type="button" class="pzf-btn pzf-btn-weg"
              :disabled="disabled || speichert" @click="vergessen">
        🗑 Nicht mehr merken
      </button>
      <span v-if="gemerkt" class="pzf-ok">✓ gemerkt</span>
    </div>
    <p v-if="fehler" class="pzf-fehler">⚠ {{ fehler }}</p>

    <div class="pzf-fuss">
      <p class="pzf-hinweis">
        Ergänzt den Auftrag an die KI — Schwerpunkt, Tiefe, Adressat.
        <strong>Antwortformat, Bewertungsskalen und berechnete Werte bleiben
        unverändert.</strong>
      </p>
      <span class="pzf-zaehler" :class="{ voll: (modelValue || '').length >= grenze }">
        {{ (modelValue || '').length }}/{{ grenze }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * PromptZusatzFeld — das Feld für eigene Gedanken an jedem KI-Prompt (#1834).
 *
 * Die Komponente ist **dumm** (Muster `SidebarSearch`, #1703/S7): Sie nimmt
 * Text auf und gibt ihn heraus. Zusammengesetzt wird serverseitig
 * (`shared/prompt_zusatz.komponiere`) — eine zweite Zusammenbau-Stelle im
 * Frontend wäre die zweite Wahrheit aus #1727/#1735.
 *
 * Der Hinweis unter dem Feld steht bewusst **am Feld** und nicht in einer
 * Hilfeseite: Wer „setze die Stufe auf weitgehend compliant" hineinschreibt,
 * soll vorher lesen, dass das nicht wirkt.
 */
import { computed, onMounted, ref } from 'vue'
import apiClient from '../../api/client'

const props = withDefaults(defineProps<{
  modelValue?: string
  disabled?: boolean
  /** Muss der Grenze aus shared/prompt_zusatz.GRENZE entsprechen. */
  grenze?: number
  /** Beispiel passend zur Maske; ohne Angabe ein allgemeines. */
  beispiel?: string
  /**
   * #1835 — Modulschlüssel und Projekt für die **gespeicherten** Hinweise.
   * Beide gesetzt → das Feld wird vorbelegt und kann gemerkt werden; sonst
   * verhält es sich wie bisher (rein ad hoc).
   */
  modul?: string
  /** `null` ist erlaubt: Die Stores führen den Zustand „nichts
   *  ausgewählt“ so, und vier Masken geben den Wert unverändert
   *  durch (#1858). */
  projekt?: string | null
  /** Bereich des gespeicherten Hinweises (leer = gilt für alle Prompts). */
  bereich?: string
}>(), { modelValue: '', disabled: false, grenze: 2000, beispiel: '',
        modul: '', projekt: '', bereich: '' })

const emit = defineEmits<{ (e: 'update:modelValue', wert: string): void }>()

const feldId = `pzf-${Math.random().toString(36).slice(2, 9)}`

const platzhalter = computed(() => props.beispiel
  || 'z. B. „Der Schwerpunkt des Unternehmens liegt in der Fertigung, die IT '
   + 'ist ausgelagert." oder „Bitte ausführlicher — Adressat ist der '
   + 'Aufsichtsrat."')

function onInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLTextAreaElement).value)
}

// ── #1835: gespeicherte Projekt-Hinweise ──────────────────────────────────
// Vorbelegen, nicht heimlich anhängen: Ein gespeicherter Text steuert sonst
// jeden Lauf, ohne dass der Bearbeiter ihn sieht. Aufgelöst wird
// serverseitig (allgemeiner + bereichsbezogener Hinweis) — dieselbe Regel im
// Frontend nachzubauen wäre die zweite Wahrheit (#1703/S9).
const geerbtVon = ref('')
const speichert = ref(false)
const gemerkt = ref(false)
const fehler = ref('')

const kannMerken = computed(() => !!props.modul && !!props.projekt)
const pfad = computed(() =>
  `/${props.modul}/projekte/${encodeURIComponent(props.projekt || '')}/prompt-hinweise`)

onMounted(async () => {
  if (!kannMerken.value) return
  try {
    const res = await apiClient.get(pfad.value, { params: { bereich: props.bereich } })
    const text = String(res.data?.text || '')
    const quellen = res.data?.quellen || []
    if (text && !(props.modelValue || '').trim()) {
      emit('update:modelValue', text)
      geerbtVon.value = quellen[0]?.erstellt_von || '—'
    }
  } catch {
    // Kein Hinweis ist kein Fehler — das Feld bleibt leer und benutzbar.
  }
})

async function merken() {
  if (!kannMerken.value) return
  speichert.value = true; fehler.value = ''; gemerkt.value = false
  try {
    await apiClient.put(pfad.value, { text: props.modelValue, bereich: props.bereich })
    gemerkt.value = true
    geerbtVon.value = geerbtVon.value || '—'
    setTimeout(() => { gemerkt.value = false }, 2500)
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Der Hinweis konnte nicht gemerkt werden.'
  } finally {
    speichert.value = false
  }
}

async function vergessen() {
  if (!kannMerken.value) return
  speichert.value = true; fehler.value = ''
  try {
    await apiClient.delete(`${pfad.value}/${props.bereich || 'alle'}`)
    geerbtVon.value = ''
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Der Hinweis konnte nicht entfernt werden.'
  } finally {
    speichert.value = false
  }
}
</script>

<style scoped>
.pzf {
  border: 1px solid #cfd8dc;
  border-radius: 6px;
  padding: 0.6rem 0.7rem;
  background: #fafafa;
}
.pzf-label {
  display: block;
  font-size: 0.85rem;
  font-weight: 600;
  color: #37474f;
  margin-bottom: 0.35rem;
}
.pzf-opt { font-weight: 400; color: #78909c; }
.pzf-text {
  width: 100%;
  box-sizing: border-box;
  font-family: inherit;
  font-size: 0.85rem;
  padding: 0.45rem 0.55rem;
  border: 1px solid #cfd8dc;
  border-radius: 4px;
  resize: vertical;
  background: #fff;
}
.pzf-text:disabled { background: #eceff1; }
.pzf-fuss {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.6rem;
  margin-top: 0.3rem;
}
.pzf-hinweis {
  margin: 0;
  font-size: 0.75rem;
  color: #607d8b;
  line-height: 1.35;
}
.pzf-zaehler {
  flex: 0 0 auto;
  font-size: 0.72rem;
  color: #90a4ae;
  font-variant-numeric: tabular-nums;
}
.pzf-zaehler.voll { color: #c62828; font-weight: 600; }
.pzf-herkunft { margin: 0.35rem 0 0; font-size: 0.75rem; color: #00695c;
  background: #e0f2f1; border-radius: 4px; padding: 0.3rem 0.45rem; }
.pzf-merken { display: flex; align-items: center; gap: 0.4rem; margin-top: 0.35rem; }
.pzf-btn { background: #eceff1; border: 1px solid #cfd8dc; border-radius: 4px;
  padding: 0.25rem 0.6rem; font-size: 0.75rem; cursor: pointer; color: #37474f; }
.pzf-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.pzf-btn-weg { color: #c62828; border-color: #ef9a9a; }
.pzf-ok { font-size: 0.75rem; color: #2e7d32; }
.pzf-fehler { margin: 0.3rem 0 0; font-size: 0.75rem; color: #c62828; }
</style>
