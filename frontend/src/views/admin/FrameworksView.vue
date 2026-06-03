<template>
  <div class="frameworks-view">
    <div class="header">
      <h2>📚 Framework-Bibliothek</h2>
      <p>Regulierungs-PDFs herunterladen, in die Datenbank ingestieren — Grundlage für die Fragen-Generierung im Gutachten-Modul</p>
    </div>

    <div v-if="error" class="alert alert-error" @click="error = ''">{{ error }}</div>

    <div class="info-card">
      <h3>So funktioniert es</h3>
      <ol>
        <li><strong>Download</strong>: Lädt die PDF(s) eines Frameworks von der EU-Publications-Office (EUR-Lex) via CELEX. Dauert 5–60 Sekunden.</li>
        <li><strong>Ingest</strong>: Liest die PDFs ein, extrahiert Abschnitte und speichert sie in der Sections-DB.</li>
        <li><strong>Manuell</strong> (ISO27001/BSI): Da kein EU-Dokument — PDF/XLSX manuell hochladen.</li>
      </ol>
    </div>

    <div v-if="loading" class="loading">Lade Frameworks…</div>

    <div v-else class="fw-grid">
      <div v-for="fw in frameworks" :key="fw.id" class="fw-card">
        <div class="fw-head">
          <div>
            <h3>{{ fw.id }}</h3>
            <p class="fw-label">{{ fw.label }}</p>
          </div>
          <div class="fw-stats">
            <div class="stat-pill" :class="{ ok: fw.sections_count > 0 }">
              <span class="num">{{ fw.sections_count }}</span>
              <span class="lbl">Sections</span>
            </div>
            <div class="stat-pill" :class="{ ok: fw.pdf_count > 0 }">
              <span class="num">{{ fw.pdf_count }}</span>
              <span class="lbl">Dateien</span>
            </div>
          </div>
        </div>

        <p class="fw-desc">{{ fw.description }}</p>

        <div class="fw-meta">
          <span v-if="fw.celex_codes.length > 0">
            <strong>CELEX:</strong> {{ fw.celex_codes.join(', ') }}
            <span v-if="fw.sparql_derived" class="badge">+ abgeleitete via SPARQL</span>
          </span>
          <span v-else-if="fw.extra_resources && fw.extra_resources.length > 0" class="muted">
            <strong>{{ fw.extra_resources.length }}</strong> Direkt-Download(s) (z.B. {{ fw.extra_resources[0].name }})
          </span>
          <span v-else class="muted">Kein automatischer Download — manueller Upload nötig</span>
        </div>

        <div class="fw-dir muted">📁 {{ fw.data_dir }}</div>

        <div class="fw-actions">
          <button v-if="fw.has_download"
                  class="btn-primary" :disabled="busy[fw.id]"
                  @click="onDownload(fw)">
            {{ busy[fw.id] === 'download' ? '⏳ Lade…' : '⬇️ Download' }}
          </button>

          <input :ref="el => fileInputs[fw.id] = el as any" type="file" accept=".pdf,.xlsx"
                 style="display:none" @change="onUpload(fw, $event)" />
          <button class="btn-secondary" :disabled="busy[fw.id]"
                  @click="(fileInputs[fw.id] as any)?.click()">
            ⬆️ Manuell hochladen
          </button>

          <button class="btn-success" :disabled="busy[fw.id] || fw.pdf_count === 0"
                  @click="onIngest(fw)" :title="fw.pdf_count === 0 ? 'Erst Datei(en) hochladen oder downloaden' : ''">
            {{ busy[fw.id] === 'ingest' ? '⏳ Ingestiere…' : '🗂️ Ingest in DB' }}
          </button>

          <label class="check-row" v-if="fw.has_download">
            <input type="checkbox" v-model="forceFlags[fw.id]" />
            <span>Force re-download</span>
          </label>
        </div>

        <details v-if="logs[fw.id] && logs[fw.id].length" class="fw-log">
          <summary>Protokoll ({{ logs[fw.id].length }} Zeilen)</summary>
          <pre>{{ logs[fw.id].join('\n') }}</pre>
        </details>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import apiClient from '../../api/client'

interface Framework {
  id: string
  label: string
  description: string
  celex_codes: string[]
  sparql_derived: boolean
  data_dir: string
  pdf_count: number
  sections_count: number
}

const frameworks = ref<Framework[]>([])
const loading = ref(false)
const error = ref('')
const busy = reactive<Record<string, string | false>>({})
const forceFlags = reactive<Record<string, boolean>>({})
const fileInputs: Record<string, HTMLInputElement | null> = {}
const logs = reactive<Record<string, string[]>>({})

const reload = async () => {
  loading.value = true
  try {
    const res = await apiClient.get('/gutachten/frameworks')
    frameworks.value = res.data
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Fehler beim Laden'
  } finally {
    loading.value = false
  }
}

const onDownload = async (fw: Framework) => {
  busy[fw.id] = 'download'
  logs[fw.id] = ['Starte Download…']
  try {
    const res = await apiClient.post(
      `/gutachten/frameworks/${fw.id}/download`,
      { force: !!forceFlags[fw.id] },
      { timeout: 600000 },  // 10 min
    )
    logs[fw.id] = res.data.log || []
    await reload()
  } catch (e: any) {
    const data = e?.response?.data
    logs[fw.id] = data?.log || [`FEHLER: ${data?.error || e.message}`]
    error.value = data?.error || e.message
  } finally {
    busy[fw.id] = false
  }
}

const onIngest = async (fw: Framework) => {
  busy[fw.id] = 'ingest'
  try {
    const res = await apiClient.post(
      `/gutachten/frameworks/${fw.id}/ingest`,
      {},
      { timeout: 300000 },
    )
    const data = res.data
    const lines = [`✓ ${data.sections_inserted} Sections in DB`]
    if (data.errors?.length) lines.push(...data.errors.map((e: string) => `⚠️ ${e}`))
    logs[fw.id] = lines
    await reload()
  } catch (e: any) {
    error.value = e?.response?.data?.error || e.message
    logs[fw.id] = [`FEHLER: ${error.value}`]
  } finally {
    busy[fw.id] = false
  }
}

const onUpload = async (fw: Framework, e: Event) => {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  busy[fw.id] = 'upload'
  try {
    const fd = new FormData()
    fd.append('file', file)
    await apiClient.post(`/gutachten/frameworks/${fw.id}/upload`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })
    logs[fw.id] = [`✓ ${file.name} hochgeladen — jetzt "Ingest in DB" klicken`]
    await reload()
  } catch (err: any) {
    error.value = err?.response?.data?.error || err.message
    logs[fw.id] = [`FEHLER: ${error.value}`]
  } finally {
    busy[fw.id] = false
    input.value = ''
  }
}

onMounted(reload)
</script>

<style scoped>
.frameworks-view { max-width: 1400px; padding: 16px; }

.header { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border); }
.header h2 { margin: 0; font-size: 22px; }
.header p { margin: 2px 0 0; color: var(--color-text-secondary); font-size: 13px; }

.alert-error {
  background: #ffebee; color: #c62828; padding: 10px; border-radius: 4px;
  margin-bottom: 12px; border: 1px solid #ef5350; cursor: pointer;
}

.info-card {
  background: var(--color-background); padding: 14px 18px;
  border-radius: 6px; margin-bottom: 16px;
}
.info-card h3 { margin: 0 0 8px; font-size: 14px; }
.info-card ol { margin: 0; padding-left: 20px; line-height: 1.6; font-size: 13px; }

.loading { text-align: center; padding: 32px; color: var(--color-text-secondary); }

.fw-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
  gap: 14px;
}

.fw-card {
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-radius: 8px; padding: 16px;
}
.fw-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 8px; }
.fw-head h3 { margin: 0; font-size: 18px; color: var(--color-primary); }
.fw-label { margin: 2px 0 0; font-size: 12px; color: var(--color-text-secondary); }
.fw-stats { display: flex; gap: 6px; }
.stat-pill {
  background: var(--color-background); padding: 4px 12px; border-radius: 4px;
  text-align: center; min-width: 56px; border: 1px solid var(--color-border);
}
.stat-pill.ok { background: #e8f5e9; border-color: #66bb6a; }
.stat-pill .num { display: block; font-size: 18px; font-weight: 700; color: var(--color-text-primary); }
.stat-pill.ok .num { color: #2e7d32; }
.stat-pill .lbl { font-size: 10px; color: var(--color-text-secondary); }

.fw-desc { margin: 0 0 8px; color: var(--color-text-secondary); font-size: 13px; }
.fw-meta { font-size: 12px; color: var(--color-text-secondary); margin-bottom: 4px; }
.fw-meta strong { color: var(--color-text-primary); font-family: monospace; }
.badge { font-size: 10px; background: var(--color-primary); color: #fff; padding: 1px 6px; border-radius: 8px; margin-left: 6px; }
.fw-dir { font-family: monospace; font-size: 11px; margin-bottom: 12px; }
.muted { color: var(--color-text-secondary); }

.fw-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.check-row { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 12px; color: var(--color-text-secondary); }

.fw-log { margin-top: 12px; padding: 8px; background: var(--color-background); border-radius: 4px; }
.fw-log summary { cursor: pointer; font-size: 12px; font-weight: 600; }
.fw-log pre {
  margin: 8px 0 0; max-height: 200px; overflow-y: auto;
  background: var(--color-surface); padding: 8px; border-radius: 4px;
  font-family: monospace; font-size: 11px; white-space: pre-wrap;
}

.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-primary:hover:not(:disabled) { background: var(--color-primary-dark); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: var(--color-background); color: var(--color-primary); border: 1px solid var(--color-border); padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-secondary:hover:not(:disabled) { background: var(--color-border); }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-success { background: #2e7d32; color: #fff; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-success:hover:not(:disabled) { background: #1b5e20; }
.btn-success:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
