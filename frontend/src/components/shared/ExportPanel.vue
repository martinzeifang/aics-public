<!--
  ExportPanel (Bugfix-Sprint #22, B2 / #1093) — vereinheitlichter „Bericht /
  Export"-Block für die fünf Compliance-Module (CRA, NIS2, AI Act, DSGVO,
  Risikobewertung). Baut die Report-URL pro Format und löst den Download über
  <DownloadButton> aus (Auth via apiClient-Blob — identischer Mechanismus wie in
  CRAView/RisikobewertungView).

  Props:
    module      — 'cra' | 'nis2' | 'aiact' | 'dsgvo' | 'risikobewertung'
    projektName — aktueller Projektname
    formats     — z.B. ['pdf','docx','xlsx','json','md']
    options?    — Inhalts-Checkboxen [{ key, label, default? }]

  URL: /api/<apiBase>/projekte/<encoded projekt>/report?format=<fmt>
       (+ &options=<csv aktivierter Option-Keys>, falls options gesetzt)
  apiBase: 'aiact' → 'aiact', sonst der Modul-String (= Modulname).

  <DownloadButton> erwartet den Endpoint OHNE führendes /api, daher stripApi().
-->
<template>
  <div class="export-panel action-card">
    <h3>Bericht / Export</h3>

    <div v-if="options && options.length" class="report-options">
      <label v-for="o in options" :key="o.key" class="checkbox-label">
        <input type="checkbox" v-model="checked[o.key]" />
        {{ o.label }}
      </label>
    </div>

    <div class="action-buttons">
      <DownloadButton
        v-for="fmt in formats"
        :key="fmt"
        :endpoint="stripApi(reportUrl(fmt))"
        :disabled="!projektName"
        class="btn-primary"
      >
        {{ formatIcon(fmt) }} {{ fmt.toUpperCase() }}
      </DownloadButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import DownloadButton from './DownloadButton.vue'

const props = defineProps<{
  module: string
  projektName: string
  formats: string[]
  options?: { key: string; label: string; default?: boolean }[]
}>()

// Checkbox-State pro Option (Vorbelegung aus `default`)
const checked = reactive<Record<string, boolean>>({})
for (const o of props.options || []) {
  checked[o.key] = o.default ?? false
}

const apiBase = (): string => (props.module === 'aiact' ? 'aiact' : props.module)

const FORMAT_ICONS: Record<string, string> = {
  pdf: '📄',
  docx: '📝',
  xlsx: '📊',
  md: '📃',
  json: '{ }',
}
const formatIcon = (fmt: string): string => FORMAT_ICONS[fmt] || '⬇️'

const stripApi = (u: string): string => u.replace(/^\/api/, '')

const reportUrl = (fmt: string): string => {
  if (!props.projektName) return '#'
  let url = `/api/${apiBase()}/projekte/${encodeURIComponent(props.projektName)}/report?format=${fmt}`
  if (props.options && props.options.length) {
    const opts = props.options
      .filter(o => checked[o.key])
      .map(o => o.key)
      .join(',')
    url += `&options=${opts}`
  }
  return url
}
</script>

<style scoped>
.export-panel {
  background: white; padding: 24px; border-radius: 8px;
  border: 1px solid var(--color-border); max-width: 700px;
}
.export-panel h3 { margin: 0 0 16px; }

.report-options {
  display: flex; flex-direction: column; gap: 8px;
  margin-bottom: 16px; padding: 12px;
  background: #f9f9f9; border-radius: 4px;
}
.checkbox-label {
  display: flex; align-items: center; gap: 8px;
  cursor: pointer; font-size: 13px;
}

.action-buttons { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }

.btn-primary { background: var(--color-primary); color: white; }
</style>
