<template>
  <div class="frameworks-view">
    <div class="header">
      <h2>{{ $t('admin.frameworksView.frameworkBibliothek') }}</h2>
      <p>{{ $t('admin.frameworksView.regulierungsPDFsHerunterladenInDieDa') }}</p>
    </div>

    <FehlerHinweis :text="error" @close="error = ''" />

    <div class="info-card">
      <h3>{{ $t('admin.frameworksView.soFunktioniertEs') }}</h3>
      <ol>
        <li><strong>{{ $t('admin.frameworksView.download') }}</strong>{{ $t('admin.frameworksView.ladtDiePDFSEinesFrameworksVonDerEUPu') }}</li>
        <li><strong>{{ $t('admin.frameworksView.ingest') }}</strong>{{ $t('admin.frameworksView.liestDiePDFsEinExtrahiertAbschnitteU') }}</li>
        <li><strong>{{ $t('admin.frameworksView.manuell') }}</strong> {{ $t('admin.frameworksView.iSO27001BSIDaKeinEUDokumentPDFXLSXMa') }}</li>
      </ol>
    </div>

    <div v-if="loading" class="loading">{{ $t('admin.frameworksView.ladeFrameworks') }}</div>

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
              <span class="lbl">{{ $t('admin.frameworksView.sections') }}</span>
            </div>
            <div class="stat-pill" :class="{ ok: fw.pdf_count > 0 }">
              <span class="num">{{ fw.pdf_count }}</span>
              <span class="lbl">{{ $t('admin.frameworksView.dateien') }}</span>
            </div>
          </div>
        </div>

        <p class="fw-desc">{{ fw.description }}</p>

        <div class="fw-meta">
          <span v-if="fw.celex_codes.length > 0">
            <strong>{{ $t('admin.frameworksView.cELEX') }}</strong> {{ fw.celex_codes.join(', ') }}
            <span v-if="fw.sparql_derived" class="badge">{{ $t('admin.frameworksView.abgeleiteteViaSPARQL') }}</span>
          </span>
          <span v-else-if="fw.extra_resources && fw.extra_resources.length > 0" class="muted">
            <strong>{{ fw.extra_resources.length }}</strong> Direkt-Download(s) (z.B. {{ fw.extra_resources[0].name }})
          </span>
          <span v-else class="muted">{{ $t('admin.frameworksView.keinAutomatischerDownloadManuellerUp') }}</span>
        </div>

        <div class="fw-dir muted">📁 {{ fw.data_dir }}</div>

        <div class="fw-actions">
          <button v-if="fw.has_download"
                  class="btn-primary" :disabled="!!busy[fw.id]"
                  @click="onDownload(fw)">
            {{ busy[fw.id] === 'download' ? $t('admin.frameworksView.lade') : $t('admin.frameworksView.download2') }}
          </button>

          <input :ref="el => fileInputs[fw.id] = el as any" type="file" accept=".pdf,.xlsx"
                 style="display:none" @change="onUpload(fw, $event)" />
          <button class="btn-secondary" :disabled="!!busy[fw.id]"
                  @click="(fileInputs[fw.id] as any)?.click()">
            {{ $t('admin.frameworksView.manuellHochladen') }}
          </button>

          <button class="btn-success" :disabled="!!busy[fw.id] || fw.pdf_count === 0"
                  @click="onIngest(fw)" :title="fw.pdf_count === 0 ? $t('admin.frameworksView.erstDateiEnHochladenOderDownloaden') : ''">
            {{ busy[fw.id] === 'ingest' ? $t('admin.frameworksView.ingestiere') : $t('admin.frameworksView.ingestInDB') }}
          </button>

          <label class="check-row" v-if="fw.has_download">
            <input type="checkbox" v-model="forceFlags[fw.id]" />
            <span>{{ $t('admin.frameworksView.forceReDownload') }}</span>
          </label>
        </div>

        <p v-if="ingestStand[fw.id]?.laeuft" class="fw-ingest-stand">
          ⏳ {{ $t('admin.frameworksView.ingestStand') }}:
          {{ ingestStand[fw.id].laeuft.fortschritt || '…' }}
        </p>
        <details v-if="logs[fw.id] && logs[fw.id].length" class="fw-log">
          <summary>{{ $t('admin.frameworksView.protokollV0Zeilen', { v0: logs[fw.id].length }) }}</summary>
          <pre>{{ logs[fw.id].join('\n') }}</pre>
        </details>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import apiClient from '../../api/client'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'
import { t } from '../../i18n'

interface Framework {
  id: string
  label: string
  description: string
  celex_codes: string[]
  sparql_derived: boolean
  data_dir: string
  pdf_count: number
  sections_count: number
  // Liefert `GET /api/compliance-audit/frameworks` mit (`server/api/
  // compliance_audit.py`): Direkt-Downloads neben den CELEX-Quellen und die
  // Frage, ob es überhaupt einen automatischen Download gibt. Beide wurden
  // hier gelesen und standen nicht im Typ (#1858).
  extra_resources?: { name: string; filename: string }[]
  has_download?: boolean
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
    const res = await apiClient.get('/compliance-audit/frameworks')
    frameworks.value = res.data
  } catch (e: any) {
    error.value = e?.response?.data?.error || t('common.fehlerBeimLaden')
  } finally {
    loading.value = false
  }
}

const onDownload = async (fw: Framework) => {
  busy[fw.id] = 'download'
  logs[fw.id] = ['Starte Download…']
  try {
    const res = await apiClient.post(
      `/compliance-audit/frameworks/${fw.id}/download`,
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

/**
 * #2022: Das Einlesen läuft seit v8.6.4 **im Hintergrund** (202 statt 200).
 *
 * Vorher stand hier `{ timeout: 300000 }` und der Browser wartete auf das
 * Ergebnis. Gemessen braucht das BSI-Verzeichnis 3 668 s — der Abbruch kam
 * also zuverlässig, der Server arbeitete weiter, und der Anwender sah einen
 * Fehler für einen Lauf, der gelang. Ein größeres Zeitlimit hätte die Grenze
 * nur verschoben.
 *
 * Abgefragt wird der Stand, nicht gewartet. Das Abfrageintervall ist bewusst
 * grob (5 s): Der Lauf dauert Minuten bis Stunden, und ein 2-Sekunden-Takt
 * wäre genau die Last, die #2087 beanstandet.
 */
const ingestStand = reactive<Record<string, any>>({})
const ingestTimer = reactive<Record<string, number>>({})

const ladeIngestStand = async (fwId: string) => {
  try {
    const res = await apiClient.get(
      `/compliance-audit/frameworks/${fwId}/ingest/status`)
    ingestStand[fwId] = res.data
    if (res.data?.laeuft) return true
    // Fertig oder gescheitert: Abfrage beenden und die Liste neu laden.
    const letzter = res.data?.letzter
    if (letzter?.zustand === 'fertig') {
      logs[fwId] = [t('admin.frameworksView.ingestFertigV0', { v0: letzter.abschnitte }),
                    ...(letzter.log || []).map((e: string) => `⚠️ ${e}`)]
      await reload()
    } else if (letzter?.zustand === 'fehler') {
      logs[fwId] = [t('admin.frameworksView.ingestGescheitert'),
                    ...(letzter.log || [])]
    }
    return false
  } catch {
    // Ein Ausfall der Abfrage ist kein Ausfall des Laufs — nicht als Fehler
    // melden, sondern weiter abfragen (der Lauf steht in der Datenbank).
    return true
  }
}

const beobachteIngest = (fwId: string) => {
  if (ingestTimer[fwId]) window.clearInterval(ingestTimer[fwId])
  ingestTimer[fwId] = window.setInterval(async () => {
    const weiter = await ladeIngestStand(fwId)
    if (!weiter) {
      window.clearInterval(ingestTimer[fwId])
      delete ingestTimer[fwId]
      busy[fwId] = false
    }
  }, 5000)
}

const onIngest = async (fw: Framework) => {
  busy[fw.id] = 'ingest'
  try {
    const res = await apiClient.post(
      `/compliance-audit/frameworks/${fw.id}/ingest`, {})
    logs[fw.id] = [t('admin.frameworksView.ingestLaeuftImHintergrund',
                     { v0: res.data?.dateien ?? 0 })]
    await ladeIngestStand(fw.id)
    beobachteIngest(fw.id)
  } catch (e: any) {
    if (e?.response?.status === 409) {
      logs[fw.id] = [t('admin.frameworksView.ingestLaeuftBereits')]
      await ladeIngestStand(fw.id)
      beobachteIngest(fw.id)
      return
    }
    error.value = e?.response?.data?.error || e.message
    logs[fw.id] = [`FEHLER: ${error.value}`]
    busy[fw.id] = false
  }
}

onUnmounted(() => {
  // Ohne das läuft die Abfrage weiter, nachdem die Maske zu ist (#2087).
  Object.values(ingestTimer).forEach(id => window.clearInterval(id))
})

const onUpload = async (fw: Framework, e: Event) => {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  busy[fw.id] = 'upload'
  try {
    const fd = new FormData()
    fd.append('file', file)
    await apiClient.post(`/compliance-audit/frameworks/${fw.id}/upload`, fd, {
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
.fw-ingest-stand { font-size: 12px; color: #ef6c00; margin: 4px 0 0; }
</style>
