<template>
  <div class="suggest-bar">
    <div class="suggest-actions">
      <button class="btn-suggest" :disabled="busy" @click="$emit('from-repo')">⚡ Aus Repo vorschlagen</button>
      <button class="btn-suggest" :disabled="busy" @click="urlMode = !urlMode">🌐 Aus URL vorschlagen</button>
      <span v-if="busy" class="hint">Analysiere…</span>
    </div>

    <div v-if="urlMode" class="url-row">
      <input v-model="url" type="url" placeholder="https://… (z.B. Modell-/Doku-URL)" @keyup.enter="submitUrl" />
      <button class="btn-suggest" :disabled="busy || !url.trim()" @click="submitUrl">Analysieren</button>
    </div>

    <div v-if="suggestionList.length" class="suggest-list">
      <div class="suggest-head">
        <strong>{{ suggestionList.length }} Vorschläge</strong>
        <button class="btn-link-text" @click="$emit('apply-all')">Alle übernehmen</button>
      </div>
      <div v-for="s in suggestionList" :key="s.field" class="suggest-pill" :class="{ existing: hasValue(s.field) }">
        <div class="pill-main">
          <span class="pill-field">{{ label(s.field) }}</span>
          <span v-if="hasValue(s.field)" class="pill-warn" title="Bestehender Wert wird überschrieben">⚠️ belegt</span>
          <span class="pill-value">{{ truncate(s.value) }}</span>
        </div>
        <div class="pill-meta">
          <span v-if="s.source_path" class="pill-src" :title="s.source_path">📄 {{ s.source_path }}</span>
          <span v-if="s.confidence != null" class="pill-conf">{{ Math.round(s.confidence * 100) }}%</span>
          <button class="btn-link-text" @click="$emit('apply-one', s.field)">Übernehmen</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  busy: boolean
  suggestions: Record<string, any> | null
  existing: Record<string, any>
  fieldLabels: Record<string, string>
}>()

const emit = defineEmits<{
  (e: 'from-repo'): void
  (e: 'from-url', url: string): void
  (e: 'apply-one', field: string): void
  (e: 'apply-all'): void
}>()

const urlMode = ref(false)
const url = ref('')

const suggestionList = computed<any[]>(() => {
  const s = props.suggestions
  if (!s) return []
  return Object.values(s)
})

const label = (field: string) => props.fieldLabels[field] || field
const hasValue = (field: string) => {
  const v = props.existing?.[field]
  return v != null && String(v).trim() !== ''
}
const truncate = (v: any) => {
  const str = v == null ? '' : String(v)
  return str.length > 90 ? str.slice(0, 90) + '…' : str
}

const submitUrl = () => {
  if (!url.value.trim()) return
  emit('from-url', url.value.trim())
}
</script>

<style scoped>
.suggest-bar {
  background: #f1f8e9; border-left: 4px solid #7cb342; padding: 10px 14px;
  border-radius: 4px; margin-bottom: 12px;
}
.suggest-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.btn-suggest {
  background: #558b2f; color: white; border: none; padding: 6px 12px;
  border-radius: 4px; cursor: pointer; font-size: 13px;
}
.btn-suggest:hover { background: #33691e; }
.btn-suggest:disabled { opacity: 0.5; cursor: not-allowed; }
.url-row { display: flex; gap: 8px; margin-top: 8px; }
.url-row input { flex: 1; padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; font: inherit; }
.suggest-list { margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }
.suggest-head { display: flex; justify-content: space-between; align-items: center; }
.suggest-pill {
  background: white; border: 1px solid #c5e1a5; border-radius: 6px;
  padding: 6px 10px; display: flex; flex-direction: column; gap: 4px;
}
.suggest-pill.existing { border-color: #ffb74d; background: #fff8e1; }
.pill-main { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
.pill-field { font-weight: 600; font-size: 13px; color: #33691e; }
.pill-warn { font-size: 11px; color: #e65100; }
.pill-value { font-size: 12px; color: #555; }
.pill-meta { display: flex; gap: 10px; align-items: center; font-size: 12px; color: #777; }
.pill-src { font-family: monospace; max-width: 50%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pill-conf { font-weight: 600; color: #558b2f; }
.btn-link-text { background: none; border: none; color: #1565c0; cursor: pointer; font-size: 13px; padding: 0; }
.btn-link-text:hover { text-decoration: underline; }
.hint { color: #666; font-size: 13px; }
</style>
