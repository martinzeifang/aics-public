<template>
  <div class="nis2-view">
    <div class="header">
      <h2>NIS2 – Cybersicherheit</h2>
      <p>NIS2-Richtlinie · 30+ Anforderungen in 5 Kapiteln · 0-5-Bewertung mit Gewichtung</p>
      <ModuleHelpButton module="nis2" />
    </div>

    <HelpDialog
      :open="helpOpen"
      title="NIS2 – Erläuterung der Kapitel"
      subtitle="NIS2-Richtlinie (EU 2022/2555)"
      header-bg="#1565c0"
      :kapitel="constants?.kapitel"
      :bewertung-skala="constants?.bewertung_skala"
      @close="helpOpen = false"
    />

    <div v-if="store.error" class="alert alert-error">{{ store.error }}</div>

    <div v-if="!store.selectedProjektObj" class="empty-state">
      <h3>{{ store.projekte.length === 0 ? 'Noch keine NIS2-Bewertungen' : 'Firma wählen' }}</h3>
      <p v-if="store.projekte.length === 0">
        NIS2 ist <strong>firmenbezogen</strong> — pro Firma eine Bewertung.
        Lege einen Firmen mit aktiviertem NIS2-Modul in der Firmenverwaltung an;
        die NIS2-Bewertung wird dann automatisch erzeugt.
      </p>
      <p v-else>Wähle links einen Firmen aus der Sidebar.</p>
      <router-link to="/firmen" class="btn-primary">→ Zur Firmenverwaltung</router-link>
    </div>

    <template v-else>
      <div class="project-bar">
        <h3 class="project-name">{{ store.selectedProjektObj.name }}</h3>
        <FirmaSelector
          :model-value="(store.selectedProjektObj as any)?.unternehmen || ''"
          :saving="reassignSaving"
          :success-text="reassignMsg.ok"
          :error-text="reassignMsg.err"
          @save="onReassignFirma"
        />
        <button class="btn-secondary" @click="bulkCreateIssues" :disabled="issuesBusy" title="Für alle Lücken (Score < 5) GitHub-Issues anlegen">{{ issuesBusy ? '⏳ Anlegen…' : '🐙 Issues anlegen' }}</button>
        <button class="btn-secondary" @click="syncIssues" :disabled="syncingIssues" title="Status aller verlinkten Issues dieses Projekts von GitHub/GitLab aktualisieren">{{ syncingIssues ? '⏳ Sync…' : '🔄 Issues synchronisieren' }}</button>
        <button class="btn-secondary" @click="importIssues" :disabled="importingIssues" title="Inhalt (Titel/Status/Kommentare) aller verlinkten Issues in die jeweiligen Anforderungs-Bewertungen übernehmen">{{ importingIssues ? '⏳ Übernehme…' : '📥 Issue-Feedback übernehmen' }}</button>
        <button class="btn-danger-mini" @click="confirmDeleteProjekt" title="Projekt löschen">🗑️ Projekt löschen</button>
      </div>
      <!-- #862: Repository pro Projekt -->
      <RepoConfigPanel v-if="store.selectedProjekt" :api-base="'/nis2'" :projekt-name="store.selectedProjekt" />

      <!-- Tab-Navigation (Sprint β #579) -->
      <div class="tabs">
        <button v-for="t in tabs" :key="t.id"
                :class="['tab-btn', { active: activeTab === t.id }]"
                @click="activeTab = t.id">{{ t.label }}</button>
      </div>

      <!-- Tab: Pflicht-Doku -->
      <div v-if="activeTab === 'pflichtdoku'">
        <NIS2PflichtDokuPanel />
      </div>

      <!-- Tab: Bericht -->
      <div v-if="activeTab === 'bericht'" class="tab-content">
        <div class="report-card">
          <h3>📄 NIS2-Compliance-Bericht</h3>
          <p>Vollständiger Bericht mit Reifegrad-Dashboard, Anforderungs-Detail-Bewertungen,
            Pflicht-Doku-Nachweisen (N1 Assets, N2 Risiken, N3 IR, N4 Supply-Chain, N5 BCP)
            sowie N6 Klassifikator-Ergebnis. Format-Auswahl:</p>
          <div class="report-buttons">
            <DownloadButton :endpoint="stripApi(exportUrl('xlsx'))" class="report-btn">📊 Excel</DownloadButton>
            <DownloadButton :endpoint="stripApi(exportUrl('docx'))" class="report-btn">📝 Word (DOCX)</DownloadButton>
            <DownloadButton :endpoint="stripApi(exportUrl('pdf'))" class="report-btn">📄 PDF</DownloadButton>
          </div>
          <div class="import-hint" v-if="store.selectedProjekt">
            <strong>Import:</strong> ein zuvor exportierter Excel-Fragebogen kann hier wieder
            hochgeladen werden:
            <ImportButton
              variant="secondary"
              :endpoint="`/nis2/projekte/${encodeURIComponent(store.selectedProjekt)}/fragebogen/import`"
              label="⬆️ Excel-Fragebogen importieren"
              @imported="onImported"
            />
          </div>
        </div>
      </div>

      <!-- Tab: Dashboard + Anforderungen (Bestehender Inhalt) -->
      <template v-if="activeTab === 'anforderungen'">

      <!-- Dashboard -->
      <div class="dashboard">
        <div class="gauge-card">
          <MaturityGauge
            :percent="store.reifegrad?.gesamt?.prozent ?? 0"
            :ampel="store.reifegrad?.gesamt?.ampel"
            label="Gesamt-Reifegrad"
          />
          <div class="gauge-stats">
            <div>{{ store.reifegrad?.gesamt?.punkte_aktuell ?? 0 }} / {{ store.reifegrad?.gesamt?.punkte_max ?? 0 }} Punkte</div>
            <div>{{ store.anforderungen.length }} Anforderungen</div>
          </div>
        </div>

        <div class="chapters-grid">
          <ChapterCard
            v-for="(data, kapitel) in store.reifegrad?.kapitel || {}"
            :key="kapitel"
            :id="String(kapitel)"
            :percent="data.prozent"
            :bewertet="data.bewertet"
            :gesamt="data.gesamt"
            :ampel="data.ampel"
            @click="filterKapitel = String(kapitel)"
          />
        </div>
      </div>

      <!-- Lücken -->
      <div v-if="(store.reifegrad?.luecken || []).length > 0" class="luecken-section">
        <h3>🚨 Top-Lücken (höchste Gewichtung × niedrige Bewertung)</h3>
        <div class="luecken-list">
          <div v-for="l in (store.reifegrad?.luecken || []).slice(0, 5)"
               :key="l.id" class="luecken-item" @click="editAnforderungById(l.id)">
            <code>{{ l.id }}</code>
            <strong>{{ l.titel }}</strong>
            <span class="luecken-meta">{{ l.kapitel }} · Gew. {{ l.gewichtung }} · Score {{ l.bewertung }}</span>
          </div>
        </div>
      </div>

      <!-- Anforderungs-Toolbar -->
      <div class="anf-toolbar">
        <input v-model="searchQuery" placeholder="Anforderungen durchsuchen…" class="search" />
        <select v-model="filterKapitel" class="filter">
          <option value="">Alle Kapitel</option>
          <option v-for="k in chapters" :key="k" :value="k">{{ k }}</option>
        </select>
        <select v-model="filterStatus" class="filter">
          <option value="all">Alle</option>
          <option value="pending">Ausstehend</option>
          <option value="partial">Teilweise</option>
          <option value="complete">Vollständig</option>
        </select>
        <span class="info">{{ visible.length }} / {{ store.anforderungen.length }}</span>

        <div class="export-group">
          <span>Export:</span>
          <DownloadButton :endpoint="stripApi(exportUrl('xlsx'))" class="export-btn">📊 Excel</DownloadButton>
          <DownloadButton :endpoint="stripApi(exportUrl('docx'))" class="export-btn">📝 Word</DownloadButton>
          <DownloadButton :endpoint="stripApi(exportUrl('pdf'))" class="export-btn">📄 PDF</DownloadButton>
          <ImportButton
            v-if="store.selectedProjekt"
            variant="secondary"
            :endpoint="`/nis2/projekte/${encodeURIComponent(store.selectedProjekt)}/fragebogen/import`"
            label="⬆️ Import"
            @imported="onImported"
          />
          <button class="btn-small" @click="customDialogOpen = true">+ Custom</button>
        </div>
      </div>

      <!-- Anforderungs-Liste -->
      <div class="anf-list">
        <table v-if="visible.length > 0">
          <thead>
            <tr>
              <th>ID</th>
              <th>Kapitel</th>
              <th>Titel</th>
              <th>Bewertung</th>
              <th>Status</th>
              <th>Gewichtung</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in visible" :key="r.id" @click="editAnforderung(r)">
              <td><code>{{ r.id }}</code></td>
              <td>{{ r.kapitel }}</td>
              <td class="title-cell">{{ r.titel }}</td>
              <td>
                <span class="score-pill" :style="{ background: scoreColor(r.bewertung) }">
                  {{ r.bewertung }}
                </span>
              </td>
              <td>
                <span :class="['status-pill', r.status]">{{ statusLabel(r.status) }}</span>
              </td>
              <td>{{ r.gewichtung }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">Keine Anforderungen zum Filter.</div>
      </div>

      </template>
    </template>

    <!-- Editor -->
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
          api-base="/nis2"
          @saved="onActionSaved"
          @error="(msg) => store.error = msg"
        />
      </template>
    </RequirementEditor>

    <!-- Custom-Anforderungs-Dialog -->
    <div v-if="customDialogOpen" class="modal-overlay" @mousedown.self="customDialogOpen = false">
      <div class="modal-content custom-modal">
        <h3>Neue Custom-Anforderung</h3>
        <div class="form-row">
          <label>ID *</label>
          <input v-model="customForm.id" placeholder="z.B. NIS-CUSTOM-01" />
        </div>
        <div class="form-row">
          <label>Kapitel</label>
          <select v-model="customForm.kapitel">
            <option v-for="k in chapters" :key="k" :value="k">{{ k }}</option>
          </select>
        </div>
        <div class="form-row">
          <label>Titel *</label>
          <input v-model="customForm.titel" />
        </div>
        <div class="form-row">
          <label>Beschreibung</label>
          <textarea v-model="customForm.beschreibung" rows="3"></textarea>
        </div>
        <div class="form-row">
          <label>Hinweise</label>
          <textarea v-model="customForm.hinweise" rows="2"></textarea>
        </div>
        <div class="form-row">
          <label>Gewichtung (1-3)</label>
          <input v-model.number="customForm.gewichtung" type="number" min="1" max="3" />
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="customDialogOpen = false">Abbrechen</button>
          <button class="btn-primary" @click="onSaveCustom">Anlegen</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import DownloadButton from '../../components/shared/DownloadButton.vue'

const stripApi = (u: string): string => u.replace(/^\/api/, '')
import { ref, computed, onMounted, watch } from 'vue'
import { useNis2Store } from '../../stores/nis2'
import { useFirmenStore } from '../../stores/firmen'
import { useRoute } from 'vue-router'
import FirmaSelector from '../../components/shared/FirmaSelector.vue'
import MaturityGauge from '../../components/shared/MaturityGauge.vue'
import ChapterCard from '../../components/shared/ChapterCard.vue'
import RequirementEditor from '../../components/shared/RequirementEditor.vue'
import RequirementActions from '../../components/shared/RequirementActions.vue'
import ImportButton from '../../components/shared/ImportButton.vue'
import HelpDialog from '../../components/shared/HelpDialog.vue'
import ModuleHelpButton from '../../components/shared/ModuleHelpButton.vue'
import apiClient from '../../api/client'
import NIS2PflichtDokuPanel from './NIS2PflichtDokuPanel.vue'
import RepoConfigPanel from '../../components/RepoConfigPanel.vue'

const store = useNis2Store()

const tabs = [
  { id: 'pflichtdoku', label: '📋 Pflicht-Doku (Start hier)' },
  { id: 'anforderungen', label: '✅ Anforderungen' },
  { id: 'bericht', label: '📄 Bericht' },
]
const activeTab = ref<'pflichtdoku' | 'anforderungen' | 'bericht'>('pflichtdoku')
const firmenStore = useFirmenStore()
const route = useRoute()
const helpOpen = ref(false)
const constants = ref<any | null>(null)
const loadConstants = async () => {
  if (constants.value) return
  try {
    const res = await apiClient.get('/nis2/constants')
    constants.value = res.data
  } catch { /* ignore */ }
}

const syncingIssues = ref(false)
async function syncIssues() {
  if (!store.selectedProjekt) return
  syncingIssues.value = true
  try {
    const { default: api } = await import('../../api/client')
    const r = await api.post(`/nis2/projekte/${encodeURIComponent(store.selectedProjekt)}/issues/sync`, {}, { timeout: 120000 })
    const d = r.data || {}
    alert(`Issues synchronisiert: ${d.synced || 0} aktualisiert, ${d.errors || 0} Fehler (gesamt ${d.total || 0}), davon ${d.auto_completed || 0} automatisch als vollständig bearbeitet markiert.`)
  } catch (e: any) {
    alert(e?.response?.data?.error || 'Issue-Sync fehlgeschlagen.')
  } finally { syncingIssues.value = false }
}

const importingIssues = ref(false)
async function importIssues() {
  if (!store.selectedProjekt) return
  if (!confirm('Inhalt aller verlinkten Issues in die jeweiligen Anforderungs-Bewertungen (Kommentar) übernehmen?')) return
  importingIssues.value = true
  try {
    const { default: api } = await import('../../api/client')
    const r = await api.post(`/nis2/projekte/${encodeURIComponent(store.selectedProjekt)}/issues/import`, {}, { timeout: 120000 })
    const d = r.data || {}
    alert(`Issue-Feedback übernommen: ${d.imported || 0} Anforderungen aktualisiert, ${d.failed || 0} ohne Inhalt (gesamt ${d.total || 0}).`)
    await store.fetchAnforderungen(store.selectedProjekt)
  } catch (e: any) {
    alert(e?.response?.data?.error || 'Issue-Feedback-Import fehlgeschlagen.')
  } finally { importingIssues.value = false }
}

const issuesBusy = ref(false)
async function bulkCreateIssues() {
  // #862: Repo aus der pro-Projekt-Konfiguration (RepoConfigPanel), kein prompt().
  if (!store.selectedProjekt) return
  if (!confirm('Für alle offenen Gaps (Score < 5) dieses Projekts GitHub/GitLab-Issues anlegen?')) return
  issuesBusy.value = true
  try {
    const { default: api } = await import('../../api/client')
    const r = await api.post(
      `/nis2/projekte/${encodeURIComponent(store.selectedProjekt)}/issues/bulk`,
      { only_gaps: true, skip_linked: true },
      { timeout: 120000 },
    )
    const s = r.data?.summary || {}
    alert(`Issues angelegt: ${s.created || 0} erstellt, ${s.skipped || 0} übersprungen, ${s.failed || 0} fehlgeschlagen.`)
  } catch (e: any) {
    const msg = e?.response?.status === 400
      ? 'Bitte zuerst das Repository im Panel speichern.'
      : (e?.response?.data?.error || 'Issue-Anlage fehlgeschlagen.')
    alert(msg)
  } finally { issuesBusy.value = false }
}

const confirmDeleteProjekt = async () => {
  if (!store.selectedProjekt) return
  if (!confirm(`NIS2-Projekt "${store.selectedProjekt}" wirklich löschen?\n\nAlle Bewertungen gehen verloren.`)) return
  await store.deleteProjekt(store.selectedProjekt)
}

const onImported = async () => {
  if (!store.selectedProjekt) return
  await store.fetchAnforderungen(store.selectedProjekt)
  await store.fetchReifegrad(store.selectedProjekt)
}

const creating = ref(false)
const newForm = ref({ name: '', unternehmen: '', einrichtungsklasse: '', beschreibung: '' })

const editingReq = ref<any | null>(null)
const customDialogOpen = ref(false)
const customForm = ref({ id: '', kapitel: 'NIS1', titel: '', beschreibung: '', hinweise: '', gewichtung: 1 })

const searchQuery = ref('')
const filterKapitel = ref('')
const filterStatus = ref<'all' | 'pending' | 'partial' | 'complete'>('all')

const chapters = computed(() => {
  const set = new Set<string>()
  for (const a of store.anforderungen) set.add(a.kapitel)
  return Array.from(set).sort()
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
  return `/api/nis2/projekte/${encodeURIComponent(store.selectedProjekt)}/report?format=${fmt}`
}

// Issue #436: Firma des Projekts nachtraeglich aendern
const reassignSaving = ref(false)
const reassignMsg = ref<{ ok: string; err: string }>({ ok: '', err: '' })
const onReassignFirma = async (newFirma: string) => {
  if (!store.selectedProjekt) return
  reassignSaving.value = true
  reassignMsg.value = { ok: '', err: '' }
  try {
    await store.updateProjekt(store.selectedProjekt, { unternehmen: newFirma } as any)
    await store.fetchProjekte()
    reassignMsg.value.ok = newFirma ? `✓ Firma geändert auf „${newFirma}"` : '✓ Firmenzuordnung entfernt'
    setTimeout(() => { reassignMsg.value = { ok: '', err: '' } }, 4000)
  } catch (e: any) {
    reassignMsg.value.err = e?.response?.data?.error || 'Fehler beim Speichern'
  } finally {
    reassignSaving.value = false
  }
}

const startNew = () => {
  newForm.value = { name: '', unternehmen: '', einrichtungsklasse: '', beschreibung: '' }
  creating.value = true
  if (firmenStore.firmen.length === 0) firmenStore.fetchFirmen()
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

const editAnforderung = (req: any) => {
  editingReq.value = req
}

const editAnforderungById = (id: string) => {
  const r = store.anforderungen.find(a => a.id === id)
  if (r) editingReq.value = r
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

const onSaveCustom = async () => {
  if (!customForm.value.id || !customForm.value.titel) {
    store.error = 'ID und Titel sind Pflicht.'
    return
  }
  const ok = await store.saveCustomAnforderung(customForm.value)
  if (ok) {
    customDialogOpen.value = false
    customForm.value = { id: '', kapitel: 'NIS1', titel: '', beschreibung: '', hinweise: '', gewichtung: 1 }
    if (store.selectedProjekt) await store.fetchAnforderungen(store.selectedProjekt)
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
}, { immediate: false })

onMounted(async () => {
  await loadConstants()
  await store.fetchProjekte()
  // Issue #434: Deep-Link via ?projekt=<firma> aus FirmenView
  const proj = (route.query.projekt || '') as string
  if (proj) {
    store.selectedProjekt = proj
  }
  if (store.selectedProjekt) await reloadProjekt()
})
</script>

<style scoped>
.nis2-view {
  max-width: 1400px;
}

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
  border: 1px solid #ef5350;
}

.empty-state, .form-card {
  background: white; padding: 32px; border-radius: 8px; border: 1px solid var(--color-border);
}

.empty-state {
  text-align: center;
}

.empty-state h3 { margin: 0 0 12px; }
.empty-state p { color: #888; margin-bottom: 20px; }

.form-card { max-width: 600px; }
.form-card h3 { margin: 0 0 16px; }

.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input,
.form-row select,
.form-row textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border);
  border-radius: 4px; font-size: 13px;
}

.form-actions {
  display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px;
}

.dashboard {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.gauge-card {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.gauge-stats {
  margin-top: 12px;
  text-align: center;
  font-size: 12px;
  color: #666;
}

.gauge-stats div { margin-bottom: 4px; }

.chapters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

.luecken-section {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 16px;
}

.luecken-section h3 {
  margin: 0 0 8px;
  font-size: 14px;
}

.luecken-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.luecken-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: #fff8e1;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.1s;
}

.luecken-item:hover {
  background: #fff3c4;
}

.luecken-item code {
  background: white;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
}

.luecken-item strong {
  flex: 1;
  font-weight: 500;
}

.luecken-meta {
  font-size: 11px;
  color: #666;
}

.anf-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.search { flex: 1; min-width: 200px; padding: 6px 10px; border: 1px solid var(--color-border);
  border-radius: 4px; font-size: 13px; }

.filter { padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; }

.info { color: #888; font-size: 12px; }

.export-group {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  font-size: 12px;
  color: #666;
}

.export-btn {
  padding: 5px 10px;
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 12px;
  text-decoration: none;
  color: #333;
}

.export-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.anf-list {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  overflow: hidden;
}

.anf-list table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.anf-list th {
  background: #f5f5f5;
  text-align: left;
  padding: 10px;
  font-weight: 600;
  border-bottom: 1px solid var(--color-border);
}

.anf-list tbody tr {
  cursor: pointer;
}

.anf-list tbody tr:hover {
  background: #f5f5f5;
}

.anf-list td {
  padding: 8px 10px;
  border-bottom: 1px solid #f0f0f0;
}

.title-cell {
  max-width: 400px;
}

.score-pill {
  padding: 2px 10px;
  border-radius: 3px;
  color: white;
  font-size: 11px;
  font-weight: 600;
}

.status-pill {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}

.status-pill.pending { background: #f3e5f5; color: #6a1b9a; }
.status-pill.partial { background: #fff3e0; color: #e65100; }
.status-pill.complete { background: #e8f5e9; color: #2e7d32; }

.empty { padding: 40px; text-align: center; color: #888; }

.btn-primary, .btn-secondary, .btn-small {
  padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;
}

.btn-primary { background: var(--color-primary); color: white; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-small {
  padding: 5px 10px;
  background: white;
  border: 1px solid var(--color-border);
  font-size: 12px;
}

.btn-small:hover { border-color: var(--color-primary); }

/* Custom-Modal */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}

.modal-content {
  background: white; border-radius: 8px; padding: 24px;
  max-width: 500px; width: 90%;
  max-height: 90vh; overflow-y: auto;
}

.custom-modal h3 { margin: 0 0 16px; color: var(--color-primary); }

.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }

@media (max-width: 768px) {
  .dashboard { grid-template-columns: 1fr; }
}

.tabs { display: flex; gap: 4px; border-bottom: 2px solid #1565c0; margin-bottom: 16px; }
.tab-btn {
  padding: 10px 18px; background: #f5f5f5; border: 1px solid #ddd; border-bottom: none;
  border-radius: 6px 6px 0 0; cursor: pointer; font-size: 14px; transition: all 0.2s;
}
.tab-btn:hover { background: #e3f2fd; }
.tab-btn.active { background: #1565c0; color: white; font-weight: 600; border-color: #1565c0; }

.tab-content { padding: 16px 0; }
.report-card {
  background: white; border: 1px solid #ddd; border-radius: 8px;
  padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.report-card h3 { margin: 0 0 12px; color: #1565c0; }
.report-card > p { color: #555; line-height: 1.6; }
.report-buttons {
  display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap;
}
.report-btn {
  padding: 10px 20px; background: #1565c0; color: white;
  border: none; border-radius: 4px; font-size: 14px;
}
.import-hint {
  margin-top: 24px; padding-top: 16px; border-top: 1px dashed #ddd;
  color: #555; font-size: 13px;
}
</style>
