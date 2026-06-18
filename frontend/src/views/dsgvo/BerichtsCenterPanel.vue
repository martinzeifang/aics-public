<template>
  <div class="berichts-center">
    <div class="intro-banner">
      <strong>📄 Berichts-Center</strong>
      <p class="hint">Einzelberichte je DSMS-Bereich als Word oder PDF. Der Jahresbericht
        (inkl. Freigabe/Signatur) liegt im eigenen Tab „📅 Jahresbericht".</p>
    </div>

    <div v-if="!projektName" class="hint">Bitte zuerst ein Projekt auswählen.</div>

    <div v-else class="report-grid">
      <div v-for="r in reports" :key="r.key" class="report-card">
        <div class="report-head">
          <span class="report-titel">{{ r.titel }}</span>
          <span class="report-norm">{{ r.norm }}</span>
        </div>
        <div class="report-actions">
          <button class="btn-secondary" :disabled="busy === r.key + ':docx'" @click="download(r, 'docx')">
            {{ busy === r.key + ':docx' ? '⏳' : '📝 Word' }}
          </button>
          <button class="btn-secondary" :disabled="busy === r.key + ':pdf'" @click="download(r, 'pdf')">
            {{ busy === r.key + ':pdf' ? '⏳' : '📄 PDF' }}
          </button>
        </div>
      </div>
    </div>
    <p v-if="msg" :class="['msg', msgKind]">{{ msg }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import apiClient from '../../api/client'

const props = defineProps<{ projektName: string | null }>()

const reports = ref<Array<{ key: string; titel: string; norm: string }>>([])
const busy = ref('')
const msg = ref('')
const msgKind = ref<'ok' | 'err'>('ok')

const loadReports = async () => {
  try {
    reports.value = (await apiClient.get('/dsgvo-berichte/berichte')).data || []
  } catch {
    reports.value = []
  }
}

const flash = (text: string, kind: 'ok' | 'err' = 'ok') => {
  msg.value = text; msgKind.value = kind
  setTimeout(() => { if (msg.value === text) msg.value = '' }, 5000)
}

const download = async (r: { key: string; titel: string }, fmt: 'docx' | 'pdf') => {
  if (!props.projektName) return
  busy.value = `${r.key}:${fmt}`
  try {
    const resp = await apiClient.get(
      `/dsgvo-berichte/projekte/${encodeURIComponent(props.projektName)}/berichte/${r.key}/export`,
      { params: { format: fmt }, responseType: 'blob' },
    )
    const url = URL.createObjectURL(resp.data as Blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${r.titel}.${fmt}`
    a.click()
    URL.revokeObjectURL(url)
    flash(`✓ ${r.titel} (${fmt.toUpperCase()}) heruntergeladen`)
  } catch (e: any) {
    let detail = 'Export fehlgeschlagen'
    if (e?.response?.status === 503) detail = 'PDF-Konverter nicht verfügbar — Word nutzen.'
    flash(detail, 'err')
  } finally {
    busy.value = ''
  }
}

onMounted(loadReports)
</script>

<style scoped>
.berichts-center { display: flex; flex-direction: column; gap: 14px; padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 8px; }
.intro-banner .hint { color: #1565c0; font-size: 13px; margin: 4px 0 0; }
.hint { color: #666; font-size: 13px; }
.report-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.report-card { background: white; border: 1px solid var(--color-border); border-radius: 8px; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.report-head { display: flex; flex-direction: column; gap: 2px; }
.report-titel { font-size: 14px; font-weight: 600; color: #222; }
.report-norm { font-size: 12px; color: #888; }
.report-actions { display: flex; gap: 8px; }
.btn-secondary { background: #e0e0e0; color: #333; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-secondary:hover:not(:disabled) { background: #d5d5d5; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.msg { font-size: 13px; }
.msg.ok { color: #2e7d32; }
.msg.err { color: #c62828; }
</style>
