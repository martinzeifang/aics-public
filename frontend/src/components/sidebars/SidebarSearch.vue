<template>
  <div class="sidebar-search">
    <div class="search-row">
      <span class="search-icon" aria-hidden="true">🔍</span>
      <input
        ref="feld"
        :value="modelValue"
        type="search"
        class="search-input"
        :placeholder="placeholder || 'Suchen …'"
        :aria-label="placeholder || 'Suchen'"
        @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        @keydown.esc.prevent="$emit('update:modelValue', '')"
      />
      <button
        v-if="modelValue"
        type="button"
        class="search-clear"
        title="Suche zurücksetzen (Esc)"
        aria-label="Suche zurücksetzen"
        @click="$emit('update:modelValue', '')"
      >×</button>
    </div>
    <div v-if="modelValue" class="search-meta">
      <span :class="{ leer: treffer === 0 }">
        {{ treffer }} von {{ gesamt }} {{ einheit || 'Einträgen' }}
      </span>
      <button v-if="zeigeAufklappen" type="button" class="link" @click="$emit('expand-all')">
        alle aufklappen
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Suchfeld für die Modul-Sidebars (#1710).
 *
 * Bewusst „dumm": filtert nichts selbst, sondern meldet nur den Suchtext und
 * zeigt den Treffer-Zähler an, den die Sidebar berechnet. Dadurch bleibt die
 * Filterlogik dort, wo die Datenstruktur bekannt ist.
 */
import { ref } from 'vue'

defineProps<{
  modelValue: string
  placeholder?: string
  /** Anzahl sichtbarer Treffer (nur zur Anzeige). */
  treffer: number
  /** Gesamtzahl vor dem Filtern. */
  gesamt: number
  /** Einheit für den Zähler, z. B. „Projekten". */
  einheit?: string
  /** „alle aufklappen"-Link anzeigen (nur bei gruppierten Sidebars sinnvoll). */
  zeigeAufklappen?: boolean
}>()

defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'expand-all'): void
}>()

const feld = ref<HTMLInputElement | null>(null)
defineExpose({ focus: () => feld.value?.focus() })
</script>

<style scoped>
.sidebar-search {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 6px;
}

.search-row {
  display: flex;
  align-items: center;
  gap: 6px;
  background: white;
  border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 4px;
  padding: 4px 6px;
}

.search-row:focus-within {
  border-color: var(--color-primary, #1565c0);
}

.search-icon {
  font-size: 11px;
  opacity: 0.6;
  flex: none;
}

.search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 12px;
  color: #333;
}

/* Browser-eigenes Such-Kreuz unterdrücken — wir haben einen eigenen Button. */
.search-input::-webkit-search-cancel-button { display: none; }

.search-clear {
  flex: none;
  border: none;
  background: transparent;
  color: #888;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  padding: 0 2px;
}

.search-clear:hover { color: #333; }

.search-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  color: #888;
  padding: 0 2px;
}

.search-meta .leer { color: #c62828; font-weight: 600; }

.link {
  border: none;
  background: none;
  padding: 0;
  font-size: 10px;
  color: var(--color-primary, #1565c0);
  cursor: pointer;
  text-decoration: underline;
}
</style>
