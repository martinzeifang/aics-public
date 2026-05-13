<template>
  <div class="aiact-view">
    <div class="header">
      <h2>EU AI Act – Compliance</h2>
      <p>Verordnung (EU) 2024/1689 · 13 Anforderungen in 4 Kapiteln · OWASP-LLM-Top-10-Mapping</p>
      <button class="help-btn" @click="helpOpen = true" title="Erläuterung der Kapitel">❓ Hilfe</button>
    </div>

    <HelpDialog
      :open="helpOpen"
      title="EU AI Act – Erläuterung der Kapitel"
      subtitle="Verordnung (EU) 2024/1689 — EU AI Act"
      header-bg="#1565c0"
      :kapitel="constants?.kapitel"
      :bewertung-skala="constants?.bewertung_skala"
      @close="helpOpen = false"
    />

    <div v-if="store.error" class="alert alert-error">{{ store.error }}</div>

    <div v-if="!store.selectedProjektObj && !creating" class="empty-state">
      <h3>{{ store.projekte.length === 0 ? 'Noch kein Projekt' : 'Projekt wählen' }}</h3>
      <p>Wähle links ein Projekt oder lege ein neues an.</p>
      <button class="btn-primary" @click="startNew">+ Neues AI-Act-Projekt</button>
    </div>

    <div v-else-if="creating" class="form-card">
      <h3>Neues AI-Act-Projekt</h3>
      <div class="form-row">
        <label>Projektname *</label>
        <input v-model="newForm.name" placeholder="z.B. Mein KI-System" />
      </div>
      <div class="form-row">
        <label>Organisation</label>
        <input v-model="newForm.organisation" />
      </div>
      <div class="form-row">
        <label>Produkt</label>
        <input v-model="newForm.produkt" placeholder="z.B. KI-Anwendung 1.0" />
      </div>
      <div class="form-row">
        <label>Beschreibung</label>
        <textarea v-model="newForm.beschreibung" rows="3"></textarea>
      </div>
      <div class="form-actions">
        <button class="btn-secondary" @click="creating = false">Abbrechen</button>
        <button class="btn-primary" @click="onCreate">Anlegen</button>
      </div>
    </div>

    <template v-else-if="store.selectedProjektObj">
      <div class="project-bar">
        <h3 class="project-name">{{ store.selectedProjektObj.name }}
          <span v-if="store.selectedProjektObj.organisation || store.selectedProjektObj.company" class="project-company">
            — {{ store.selectedProjektObj.organisation || store.selectedProjektObj.company }}
          </span>
        </h3>
        <button class="btn-danger-mini" @click="confirmDeleteProjekt" title="Projekt löschen">🗑️ Projekt löschen</button>
      </div>

      <!-- Dashboard -->
      <div class="dashboard">
        <div class="gauge-card">
          <MaturityGauge
            :percent="Math.round(store.reifegrad?.gesamt?.prozent ?? 0)"
            :ampel="store.reifegrad?.gesamt?.ampel"
            label="Gesamt-Reifegrad"
          />
        </div>

        <div class="chapters-grid">
          <ChapterCard
            v-for="(percent, kapitel) in store.reifegrad?.kapitel || {}"
            :key="kapitel"
            :id="String(kapitel)"
            :title="chapterTitle(String(kapitel))"
            :percent="Math.round(Number(percent))"
            :bewertet="kapitelStats[String(kapitel)]?.bewertet ?? 0"
            :gesamt="kapitelStats[String(kapitel)]?.gesamt ?? 0"
            @click="filterKapitel = String(kapitel)"
          />
        </div>
      </div>

      <!-- Toolbar -->
      <div class="anf-toolbar">
        <input v-model="searchQuery" placeholder="Anforderungen durchsuchen…" class="search" />
        <select v-model="filterKapitel" class="filter">
          <option value="">Alle Kapitel</option>
          <option v-for="k in chapters" :key="k" :value="k">{{ k }} – {{ chapterTitle(k) }}</option>
        </select>
        <select v-model="filterStatus" class="filter">
          <option value="all">Alle</option>
          <option value="pending">Ausstehend</option>
          <option value="partial">Teilweise</option>
          <option value="complete">Vollständig</option>
        </select>
        <button class="btn-secondary" @click="repoScanOpen = true">🔍 Repo-Scan</button>
        <DownloadButton :endpoint="stripApi(exportUrl('md'))" class="export-btn">📃 Markdown</DownloadButton>
        <ImportButton
          v-if="store.selectedProjekt"
          variant="secondary"
          :endpoint="`/aiact/projekte/${encodeURIComponent(store.selectedProjekt)}/fragebogen/import`"
          label="⬆️ Import"
          @imported="onImported"
        />
      </div>

      <!-- Anforderungs-Liste -->
      <div class="anf-list">
        <table v-if="visible.length > 0">
          <thead>
            <tr>
              <th>ID</th>
              <th>Kapitel</th>
              <th>Titel</th>
              <th>OWASP-LLM</th>
              <th>Bewertung</th>
              <th>Status</th>
              <th>Gewichtung</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in visible" :key="r.id" @click="editingReq = r">
              <td><code>{{ r.id }}</code></td>
              <td>{{ r.kapitel }}</td>
              <td class="title-cell">{{ r.titel }}</td>
              <td>
                <div class="llm-badges">
                  <span v-for="risk in r.owasp_llm" :key="risk.id"
                        :title="risk.title" class="llm-badge">
                    {{ risk.id }}
                  </span>
                </div>
              </td>
              <td>
                <span class="score-pill" :style="{ background: scoreColor(r.bewertung) }">
                  {{ r.bewertung }}
                </span>
              </td>
              <td><span :class="['status-pill', r.status]">{{ statusLabel(r.status) }}</span></td>
              <td>{{ r.gewichtung }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">Keine Anforderungen zum Filter.</div>
      </div>
    </template>

    <!-- Editor (shared) -->
    <RequirementEditor
      v-if="editingReq"
      :requirement="editingReq"
      @save="onSaveBewertung"
      @cancel="editingReq = null"
    >
      <template #actions>
        <RequirementActions
          :requirement="editingReq"
          :projekt-name="store.selectedProjekt || ''"
          api-base="/aiact"
          :default-repo="defaultRepoFromMeta"
          @saved="onActionSaved"
          @error="(msg) => store.error = msg"
        />
      </template>
    </RequirementEditor>

    <!-- Repo-Scan-Dialog -->
    <div v-if="repoScanOpen" class="modal-overlay" @click.self="repoScanOpen = false">
      <div class="modal-content">
        <h3>🔍 Repository-Scan</h3>
        <p class="hint">Scannt ein GitHub-Repository auf Sicherheits-Signale für AI-Act-Compliance.</p>
        <div class="form-row">
          <label>Repository (owner/name) *</label>
          <input v-model="repoInput.repo" placeholder="z.B. anthropics/claude-code" />
        </div>
        <div class="form-row">
          <label>Branch (optional)</label>
          <input v-model="repoInput.branch" placeholder="main" />
        </div>
        <div v-if="scanLoading" class="info">⏳ Scan läuft… (kann dauern)</div>

        <div v-if="store.repoSuggestions.length > 0" class="suggestions">
          <h4>{{ store.repoSuggestions.length }} Vorschläge</h4>
          <div v-for="s in store.repoSuggestions" :key="s.field_id" class="suggestion-card">
            <div class="sugg-header">
              <code>{{ s.field_id }}</code>
              <span class="sugg-score" :style="{ background: scoreColor(s.score) }">
                Vorschlag: {{ s.score }}
              </span>
              <span class="sugg-conf">Konfidenz: {{ Math.round(s.confidence * 100) }}%</span>
            </div>
            <p>{{ s.kommentar }}</p>
            <details v-if="s.rationale">
              <summary>Rationale</summary>
              <pre>{{ s.rationale }}</pre>
            </details>
            <button class="btn-small" @click="acceptSuggestion(s)">Übernehmen</button>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" @click="repoScanOpen = false">Schließen</button>
          <button class="btn-primary" @click="onRunScan" :disabled="scanLoading">
            {{ scanLoading ? 'Lädt…' : 'Scan starten' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import DownloadButton from '../../components/shared/DownloadButton.vue'

const stripApi = (u: string): string => u.replace(/^\/api/, '')
import { ref, computed, onMounted, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import MaturityGauge from '../../components/shared/MaturityGauge.vue'
import ChapterCard from '../../components/shared/ChapterCard.vue'
import RequirementEditor from '../../components/shared/RequirementEditor.vue'
import RequirementActions from '../../components/shared/RequirementActions.vue'
import ImportButton from '../../components/shared/ImportButton.vue'
import HelpDialog from '../../components/shared/HelpDialog.vue'
import apiClient from '../../api/client'

const store = useAiActStore()
const helpOpen = ref(false)
const constants = ref<any | null>(null)
const loadConstants = async () => {
  if (constants.value) return
  try {
    const res = await apiClient.get('/aiact/constants')
    constants.value = res.data
  } catch { /* ignore */ }
}

const confirmDeleteProjekt = async () => {
  if (!store.selectedProjekt) return
  if (!confirm(`AI-Act-Projekt "${store.selectedProjekt}" wirklich löschen?\n\nAlle Bewertungen gehen verloren.`)) return
  await store.deleteProjekt(store.selectedProjekt)
}

const onImported = async () => {
  if (!store.selectedProjekt) return
  await store.fetchAnforderungen(store.selectedProjekt)
  await store.fetchReifegrad(store.selectedProjekt)
}

const creating = ref(false)
const newForm = ref({ name: '', organisation: '', produkt: '', beschreibung: '' })
const editingReq = ref<any | null>(null)

const defaultRepoFromMeta = computed(() => {
  try {
    const meta = JSON.parse(store.selectedProjektObj?.meta || '{}')
    return meta?.linked_app?.repo?.replace('https://github.com/', '') || ''
  } catch {
    return ''
  }
})

const repoScanOpen = ref(false)
const scanLoading = ref(false)
const repoInput = ref({ repo: '', branch: '' })

const searchQuery = ref('')
const filterKapitel = ref('')
const filterStatus = ref<'all' | 'pending' | 'partial' | 'complete'>('all')

const KAPITEL_TITEL: Record<string, string> = {
  HR: 'High-Risk Requirements',
  GOV: 'Governance',
  DATA: 'Daten-Governance',
  OPS: 'Operations / Post-Market',
}

const chapterTitle = (k: string): string => KAPITEL_TITEL[k] || k

const chapters = computed(() => {
  const set = new Set<string>()
  for (const a of store.anforderungen) set.add(a.kapitel)
  return Array.from(set).sort()
})

const kapitelStats = computed(() => {
  const stats: Record<string, { bewertet: number; gesamt: number }> = {}
  for (const a of store.anforderungen) {
    if (!stats[a.kapitel]) stats[a.kapitel] = { bewertet: 0, gesamt: 0 }
    stats[a.kapitel].gesamt++
    if (a.bewertung > 0) stats[a.kapitel].bewertet++
  }
  return stats
})

const visible = computed(() => {
  let list = store.anforderungen
  if (filterKapitel.value) list = list.filter(a => a.kapitel === filterKapitel.value)
  if (filterStatus.value !== 'all') list = list.filter(a => a.status === filterStatus.value)
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(a =>
      a.id.toLowerCase().includes(q) ||
      (a.titel || '').toLowerCase().includes(q) ||
      (a.beschreibung || '').toLowerCase().includes(q),
    )
  }
  return list
})

const SCORE_COLORS = ['#9e9e9e', '#c62828', '#e65100', '#f57f17', '#558b2f', '#2e7d32']
const scoreColor = (s: number) => SCORE_COLORS[s] || '#9e9e9e'

const statusLabel = (s: string): string => {
  if (s === 'complete') return 'Vollständig'
  if (s === 'partial') return 'Teilweise'
  return 'Ausstehend'
}

const exportUrl = (fmt: string): string => {
  if (!store.selectedProjekt) return '#'
  return `/api/aiact/projekte/${encodeURIComponent(store.selectedProjekt)}/report?format=${fmt}`
}

const startNew = () => {
  newForm.value = { name: '', organisation: '', produkt: '', beschreibung: '' }
  creating.value = true
}

const onCreate = async () => {
  if (!newForm.value.name.trim()) {
    store.error = 'Projektname ist Pflicht.'
    return
  }
  const result = await store.createProjekt(newForm.value)
  if (result) {
    store.selectedProjekt = result.name
    creating.value = false
    await reloadProjekt()
  }
}

const onActionSaved = async () => {
  editingReq.value = null
  await reloadProjekt()
}

const onSaveBewertung = async (data: any) => {
  if (!editingReq.value || !store.selectedProjekt) return
  const ok = await store.saveBewertung(store.selectedProjekt, editingReq.value.id, data)
  if (ok) {
    editingReq.value = null
    await store.fetchReifegrad(store.selectedProjekt)
    await store.fetchAnforderungen(store.selectedProjekt)
  }
}

const onRunScan = async () => {
  if (!repoInput.value.repo || !store.selectedProjekt) return
  scanLoading.value = true
  await store.repoScan(store.selectedProjekt, repoInput.value.repo, repoInput.value.branch)
  scanLoading.value = false
}

const acceptSuggestion = async (s: any) => {
  if (!store.selectedProjekt) return
  const ok = await store.saveBewertung(store.selectedProjekt, s.field_id, {
    bewertung: s.score,
    kommentar: s.kommentar,
  })
  if (ok) {
    store.repoSuggestions = store.repoSuggestions.filter(x => x.field_id !== s.field_id)
    await store.fetchAnforderungen(store.selectedProjekt)
    await store.fetchReifegrad(store.selectedProjekt)
  }
}

const reloadProjekt = async () => {
  if (!store.selectedProjekt) return
  await Promise.all([
    store.fetchAnforderungen(store.selectedProjekt),
    store.fetchReifegrad(store.selectedProjekt),
  ])
}

watch(() => store.selectedProjekt, async (n) => {
  if (n) await reloadProjekt()
})

onMounted(async () => {
  await loadConstants()
  await store.fetchProjekte()
  if (store.selectedProjekt) await reloadProjekt()
})
</script>

<style scoped>
.aiact-view { max-width: 1400px; }

.header {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}

.header { display: flex; align-items: flex-end; gap: 16px; }
.header h2 { margin: 0; font-size: 22px; flex: 1; }
.header p { margin: 2px 0 0; color: #888; font-size: 13px; flex: 2; }
.help-btn {
  background: var(--color-background); color: var(--color-primary);
  border: 1px solid var(--color-border); padding: 6px 14px; border-radius: 4px;
  cursor: pointer; font-size: 14px;
}
.help-btn:hover { background: var(--color-border); }

.project-bar {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; background: var(--color-background);
  border: 1px solid var(--color-border); border-radius: 6px;
  margin-bottom: 12px;
}
.project-name { margin: 0; font-size: 16px; flex: 1; color: var(--color-text-primary); }
.project-company { font-weight: 400; color: var(--color-text-secondary); font-size: 13px; }
.btn-danger-mini {
  background: #ffebee; color: #c62828; border: 1px solid #ef5350;
  padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;
}
.btn-danger-mini:hover { background: #ffcdd2; }

.alert-error {
  background: #ffebee; color: #c62828; padding: 10px; border-radius: 4px; margin-bottom: 12px;
}

.empty-state, .form-card {
  background: white; padding: 32px; border-radius: 8px; border: 1px solid var(--color-border);
}
.empty-state { text-align: center; }
.empty-state h3 { margin: 0 0 12px; }
.empty-state p { color: #888; margin-bottom: 20px; }
.form-card { max-width: 600px; }
.form-card h3 { margin: 0 0 16px; }

.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input, .form-row textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border);
  border-radius: 4px; font-size: 13px;
}

.form-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }

.dashboard {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.gauge-card {
  background: white; border: 1px solid var(--color-border); border-radius: 8px; padding: 16px;
  display: flex; align-items: center; justify-content: center;
}

.chapters-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px;
}

.anf-toolbar {
  display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;
}

.search { flex: 1; min-width: 200px; padding: 6px 10px; border: 1px solid var(--color-border);
  border-radius: 4px; font-size: 13px; }

.filter, .export-btn {
  padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px;
  background: white; text-decoration: none; color: #333;
}

.export-btn:hover { border-color: var(--color-primary); color: var(--color-primary); }

.anf-list {
  background: white; border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden;
}

.anf-list table {
  width: 100%; border-collapse: collapse; font-size: 13px;
}

.anf-list th {
  background: #f5f5f5; text-align: left; padding: 10px; font-weight: 600;
  border-bottom: 1px solid var(--color-border);
}

.anf-list tbody tr { cursor: pointer; }
.anf-list tbody tr:hover { background: #f5f5f5; }
.anf-list td { padding: 8px 10px; border-bottom: 1px solid #f0f0f0; }

.title-cell { max-width: 400px; }

.llm-badges { display: flex; gap: 3px; flex-wrap: wrap; }

.llm-badge {
  background: #fff3e0; color: #e65100;
  padding: 2px 6px;
  font-size: 10px;
  border-radius: 3px;
  font-weight: 600;
}

.score-pill {
  padding: 2px 10px; border-radius: 3px; color: white; font-size: 11px; font-weight: 600;
}

.status-pill {
  padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;
}

.status-pill.pending { background: #f3e5f5; color: #6a1b9a; }
.status-pill.partial { background: #fff3e0; color: #e65100; }
.status-pill.complete { background: #e8f5e9; color: #2e7d32; }

.empty { padding: 40px; text-align: center; color: #888; }

/* Repo-Scan-Modal */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}

.modal-content {
  background: white; border-radius: 8px; padding: 24px;
  max-width: 700px; width: 90%; max-height: 90vh; overflow-y: auto;
}

.modal-content h3 { margin: 0 0 8px; color: var(--color-primary); }

.hint { color: #888; font-size: 13px; margin-bottom: 16px; }

.info {
  background: #fff8e1; color: #e65100; padding: 8px 12px; border-radius: 4px;
  margin: 12px 0; font-size: 13px;
}

.suggestions { margin-top: 16px; }
.suggestions h4 { margin: 0 0 8px; }

.suggestion-card {
  background: #f9f9f9;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 10px 12px;
  margin-bottom: 8px;
}

.sugg-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.sugg-score {
  padding: 2px 10px; border-radius: 3px; color: white; font-size: 12px; font-weight: 600;
}
.sugg-conf { font-size: 11px; color: #666; }

.suggestion-card p { margin: 0 0 6px; font-size: 13px; color: #333; }

.suggestion-card pre {
  background: white; padding: 6px; border-radius: 4px;
  font-size: 11px; max-height: 100px; overflow-y: auto;
}

.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }

.btn-primary, .btn-secondary, .btn-small {
  padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;
}

.btn-primary { background: var(--color-primary); color: white; }
.btn-primary:disabled { opacity: 0.6; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-small { padding: 5px 10px; background: white; border: 1px solid var(--color-border); font-size: 12px; }

@media (max-width: 768px) {
  .dashboard { grid-template-columns: 1fr; }
}
</style>
