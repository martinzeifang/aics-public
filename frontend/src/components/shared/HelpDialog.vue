<template>
  <div v-if="open" class="help-overlay" @mousedown.self="close">
    <div class="help-modal">
      <div class="help-header" :style="{ background: headerBg }">
        <div>
          <h3>{{ title || 'Hilfe' }}</h3>
          <p v-if="subtitle" class="subtitle">{{ subtitle }}</p>
        </div>
        <button class="btn-close" @click="close">✕</button>
      </div>
      <div class="help-body">
        <div v-if="kapitel && kapitelEntries.length" class="kapitel-list">
          <div
            v-for="[id, info] in kapitelEntries"
            :key="id"
            class="kapitel-card"
            :style="{ background: info.soft || '#f5f5f5', borderColor: info.farbe || '#ccc' }"
          >
            <div class="kapitel-head" :style="{ color: info.farbe || '#333' }">
              <span class="kapitel-id">{{ id }}</span>
              <span class="kapitel-titel">{{ info.titel }}</span>
            </div>
            <p v-if="info.untertitel" class="kapitel-sub">{{ info.untertitel }}</p>
            <p v-if="info.referenz" class="kapitel-ref"><em>{{ info.referenz }}</em></p>
            <p class="kapitel-desc">{{ info.beschreibung }}</p>
          </div>
        </div>
        <slot />
        <div v-if="bewertungSkala && skalaEntries.length" class="skala">
          <h4>Bewertungsskala</h4>
          <table class="skala-table">
            <tr v-for="[score, info] in skalaEntries" :key="score">
              <td class="skala-score" :style="{ background: info.farbe || '#999', color: '#fff' }">{{ score }}</td>
              <td>{{ info.label }}</td>
              <td class="skala-pct">{{ info.reife_pct }}%</td>
            </tr>
          </table>
        </div>
      </div>
      <div class="help-footer">
        <button class="btn-secondary" @click="close">Schließen</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  open: boolean
  title?: string
  subtitle?: string
  headerBg?: string
  kapitel?: Record<string, any> | null
  bewertungSkala?: Record<string, any> | null
}>()
const emit = defineEmits<{ (e: 'close'): void }>()

const close = () => emit('close')

const kapitelEntries = computed(() =>
  props.kapitel ? Object.entries(props.kapitel) : [],
)
const skalaEntries = computed(() =>
  props.bewertungSkala ? Object.entries(props.bewertungSkala) : [],
)
</script>

<style scoped>
.help-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.help-modal {
  background: var(--color-surface);
  width: min(800px, 90vw);
  max-height: 85vh;
  display: flex; flex-direction: column;
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  overflow: hidden;
}
.help-header {
  background: #1565c0; color: #fff;
  padding: 16px 24px;
  display: flex; justify-content: space-between; align-items: flex-start;
}
.help-header h3 { margin: 0; font-size: 20px; }
.subtitle { margin: 4px 0 0; font-size: 14px; opacity: 0.85; }
.btn-close {
  background: none; border: none; color: #fff; font-size: 22px;
  cursor: pointer; padding: 0; line-height: 1;
}
.help-body { padding: 20px 24px; overflow-y: auto; flex: 1; }
.kapitel-list { display: flex; flex-direction: column; gap: 14px; }
.kapitel-card {
  border-left: 4px solid;
  padding: 12px 16px;
  border-radius: 4px;
}
.kapitel-head {
  display: flex; gap: 10px; align-items: baseline;
  font-weight: 600; font-size: 16px; margin-bottom: 4px;
}
.kapitel-id {
  font-family: monospace; font-size: 13px;
  background: rgba(255,255,255,0.7); padding: 2px 8px; border-radius: 3px;
}
.kapitel-sub { font-size: 14px; color: var(--color-text-secondary); margin: 0 0 4px; }
.kapitel-ref { font-size: 12px; color: var(--color-text-secondary); margin: 0 0 8px; }
.kapitel-desc { font-size: 14px; line-height: 1.5; color: var(--color-text-primary); margin: 0; }
.skala { margin-top: 24px; }
.skala h4 { margin: 0 0 8px; font-size: 16px; }
.skala-table { width: 100%; border-collapse: collapse; }
.skala-table td {
  padding: 6px 10px; border-bottom: 1px solid var(--color-border); font-size: 14px;
}
.skala-score {
  width: 32px; text-align: center; font-weight: 700;
}
.skala-pct { text-align: right; color: var(--color-text-secondary); font-size: 13px; }
.help-footer {
  padding: 12px 24px; border-top: 1px solid var(--color-border);
  display: flex; justify-content: flex-end;
}
.btn-secondary {
  background: var(--color-background); color: var(--color-primary);
  border: 1px solid var(--color-border);
  padding: 8px 16px; border-radius: 4px; cursor: pointer;
}
.btn-secondary:hover { background: var(--color-border); }
</style>
