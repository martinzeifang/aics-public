<template>
  <div class="wiba-catalog-view">
    <div class="header">
      <h2>🛡️ WiBA-Katalog</h2>
      <p>BSI „Weg in die Basis-Absicherung" — Prüffragen-Katalog herunterladen und in die Datenbank importieren.</p>
    </div>

    <div v-if="error" class="alert-error" @click="error = ''">{{ error }}</div>

    <div class="info-card">
      <h3>So funktioniert es</h3>
      <ol>
        <li><strong>Von BSI herunterladen</strong>: Lädt den aktuellen WiBA-Katalog vom BSI. Dauert wenige Sekunden.</li>
        <li><strong>Importieren</strong>: Liest den heruntergeladenen Katalog ein und speichert Themen + Prüffragen in der Datenbank.</li>
        <li><strong>Aktualisieren</strong>: Download + Import in einem Schritt.</li>
      </ol>
    </div>

    <!-- Status -->
    <div class="status-card">
      <h3>📊 Aktueller Status</h3>
      <div v-if="loading" class="loading">Lade Status…</div>
      <div v-else class="status-grid">
        <div class="stat-pill" :class="{ ok: !!status?.version }">
          <span class="num">{{ status?.version || '—' }}</span>
          <span class="lbl">Version</span>
        </div>
        <div class="stat-pill" :class="{ ok: (status?.anzahl_themen ?? 0) > 0 }">
          <span class="num">{{ status?.anzahl_themen ?? '—' }}</span>
          <span class="lbl">Themen</span>
        </div>
        <div class="stat-pill" :class="{ ok: (status?.anzahl_prueffragen ?? 0) > 0 }">
          <span class="num">{{ status?.anzahl_prueffragen ?? '—' }}</span>
          <span class="lbl">Prüffragen</span>
        </div>
        <div class="stat-pill wide">
          <span class="num small">{{ formatDate(status?.imported_at) }}</span>
          <span class="lbl">Importiert am</span>
        </div>
      </div>

      <div class="actions">
        <button class="btn-primary" :disabled="!!busy" @click="onDownload">
          {{ busy === 'download' ? '⏳ Lade…' : '⬇️ Von BSI herunterladen' }}
        </button>
        <button class="btn-success" :disabled="!!busy" @click="onIngest">
          {{ busy === 'ingest' ? '⏳ Importiere…' : '🗂️ Importieren' }}
        </button>
        <button class="btn-secondary" :disabled="!!busy" @click="onRefresh">
          {{ busy === 'refresh' ? '⏳ Aktualisiere…' : '🔄 Aktualisieren (Download + Import)' }}
        </button>
      </div>
    </div>

    <!-- Log -->
    <div v-if="logLines.length" class="log-card">
      <h3>Protokoll</h3>
      <pre>{{ logLines.join('\n') }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useWibaStore } from '../../stores/wiba'

const store = useWibaStore()

const error = ref('')
const loading = ref(false)
const busy = ref<'' | 'download' | 'ingest' | 'refresh'>('')
const logLines = ref<string[]>([])

const status = computed(() => store.catalogStatus)

const formatDate = (s?: string): string => {
  if (!s) return '—'
  try { return new Date(s).toLocaleString('de-DE') } catch { return s }
}

const reload = async () => {
  loading.value = true
  await store.fetchCatalogStatus()
  loading.value = false
}

const run = async (action: 'download' | 'ingest' | 'refresh') => {
  busy.value = action
  error.value = ''
  logLines.value = []
  store.error = null
  let res: any = null
  if (action === 'download') res = await store.downloadCatalog()
  else if (action === 'ingest') res = await store.ingestCatalog()
  else res = await store.refreshCatalog()

  if (res?.log) {
    logLines.value = Array.isArray(res.log) ? res.log : [String(res.log)]
  }
  if (!res || res.ok === false) {
    error.value = store.error || 'Aktion fehlgeschlagen.'
    if (!logLines.value.length && error.value) logLines.value = [`FEHLER: ${error.value}`]
  } else if (!logLines.value.length) {
    logLines.value = ['✓ Erfolgreich abgeschlossen.']
  }
  await reload()
  busy.value = ''
}

const onDownload = () => run('download')
const onIngest = () => run('ingest')
const onRefresh = () => run('refresh')

onMounted(reload)
</script>

<style scoped>
.wiba-catalog-view { max-width: 1100px; padding: 16px; }

.header { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border); }
.header h2 { margin: 0; font-size: 22px; }
.header p { margin: 2px 0 0; color: var(--color-text-secondary); font-size: 13px; }

.alert-error {
  background: #ffebee; color: #c62828; padding: 10px; border-radius: 4px;
  margin-bottom: 12px; border: 1px solid #ef5350; cursor: pointer;
}

.info-card {
  background: var(--color-background); padding: 14px 18px; border-radius: 6px; margin-bottom: 16px;
}
.info-card h3 { margin: 0 0 8px; font-size: 14px; }
.info-card ol { margin: 0; padding-left: 20px; line-height: 1.6; font-size: 13px; }

.status-card {
  background: var(--color-surface, white); border: 1px solid var(--color-border);
  border-radius: 8px; padding: 16px 20px; margin-bottom: 16px;
}
.status-card h3 { margin: 0 0 12px; font-size: 16px; }
.loading { padding: 16px; color: var(--color-text-secondary); }

.status-grid { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.stat-pill {
  background: var(--color-background); padding: 10px 16px; border-radius: 6px;
  text-align: center; min-width: 90px; border: 1px solid var(--color-border);
  display: flex; flex-direction: column; gap: 2px;
}
.stat-pill.wide { min-width: 180px; }
.stat-pill.ok { background: #e8f5e9; border-color: #66bb6a; }
.stat-pill .num { font-size: 22px; font-weight: 700; color: var(--color-text-primary, #222); }
.stat-pill .num.small { font-size: 14px; }
.stat-pill.ok .num { color: #2e7d32; }
.stat-pill .lbl { font-size: 11px; color: var(--color-text-secondary); }

.actions { display: flex; gap: 10px; flex-wrap: wrap; }

.log-card {
  background: var(--color-surface, white); border: 1px solid var(--color-border);
  border-radius: 8px; padding: 14px 18px;
}
.log-card h3 { margin: 0 0 8px; font-size: 14px; }
.log-card pre {
  margin: 0; max-height: 320px; overflow-y: auto;
  background: var(--color-background, #f5f5f5); padding: 10px; border-radius: 4px;
  font-family: monospace; font-size: 12px; white-space: pre-wrap;
}

.btn-primary { background: var(--color-primary, #1565c0); color: #fff; border: none; padding: 8px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-primary:hover:not(:disabled) { background: #0d47a1; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-success { background: #2e7d32; color: #fff; border: none; padding: 8px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-success:hover:not(:disabled) { background: #1b5e20; }
.btn-success:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: var(--color-background, #e0e0e0); color: #333; border: 1px solid var(--color-border); padding: 8px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-secondary:hover:not(:disabled) { background: #d5d5d5; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
