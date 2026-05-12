<template>
  <div class="dora-view">
    <div class="header">
      <h2>DORA – Digital Operational Resilience Act</h2>
      <p>EU 2022/2554 · seit 17.01.2025 · Finanzdienstleister · 32 Anforderungen in 5 Pfeilern</p>
      <button class="help-btn" @click="helpOpen = true" title="Erläuterung der Pfeiler">❓ Hilfe</button>
    </div>

    <HelpDialog
      :open="helpOpen"
      title="DORA – Erläuterung der Pfeiler"
      subtitle="Verordnung (EU) 2022/2554 — Digital Operational Resilience Act"
      header-bg="#1565c0"
      :kapitel="store.constants?.kapitel"
      @close="helpOpen = false"
    />

    <div v-if="store.error" class="alert alert-error">{{ store.error }}</div>

    <div v-if="!store.selectedProjektObj && !creating" class="empty-state">
      <h3>{{ store.projekte.length === 0 ? 'Noch kein DORA-Projekt' : 'Projekt wählen' }}</h3>
      <p>Wähle links ein Projekt oder lege ein neues an.</p>
      <button class="btn-primary" @click="startNew">+ Neues DORA-Projekt</button>
    </div>

    <div v-else-if="creating" class="form-card">
      <h3>Neues DORA-Projekt</h3>
      <div class="form-row">
        <label>Projektname *</label>
        <input v-model="newForm.name" placeholder="z.B. Mein Finanzinstitut DORA-Readiness" />
      </div>
      <div class="form-row">
        <label>Unternehmen</label>
        <input v-model="newForm.unternehmen" />
      </div>
      <div class="form-row">
        <label>Finanzeinrichtungs-Klasse</label>
        <select v-model="newForm.finanzeinrichtung_klasse">
          <option value="">— bitte wählen —</option>
          <option value="bank">Bank / Kreditinstitut</option>
          <option value="insurer">Versicherung</option>
          <option value="investment">Wertpapierfirma / Investmentgesellschaft</option>
          <option value="other">Sonstige Finanzeinrichtung</option>
        </select>
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
          <span v-if="store.selectedProjektObj.unternehmen" class="project-company">— {{ store.selectedProjektObj.unternehmen }}</span>
        </h3>
        <button class="btn-danger-mini" @click="confirmDeleteProjekt" title="Projekt löschen">🗑️ Projekt löschen</button>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button v-for="t in tabs" :key="t.id"
                :class="['tab-btn', { active: activeTab === t.id }]"
                @click="activeTab = t.id">
          {{ t.label }}
        </button>
      </div>

      <!-- Dashboard -->
      <div v-if="activeTab === 'dashboard'" class="tab-content">
        <div class="dashboard">
          <div class="gauge-card">
            <MaturityGauge
              :percent="Math.round(store.reifegrad?.gesamt?.prozent ?? 0)"
              :ampel="store.reifegrad?.gesamt?.ampel"
              label="Gesamt-Reifegrad"
            />
            <div class="gauge-stats">
              <div>{{ store.reifegrad?.gesamt?.punkte_aktuell ?? 0 }} / {{ store.reifegrad?.gesamt?.punkte_max ?? 0 }} Punkte</div>
              <div>{{ store.anforderungen.length }} Anforderungen · {{ store.tpps.length }} TPP</div>
            </div>
          </div>

          <div class="pfeiler-grid">
            <ChapterCard
              v-for="(data, pfeiler) in store.reifegrad?.kapitel || {}"
              :key="pfeiler"
              :id="String(pfeiler)"
              :title="pfeilerLabel(String(pfeiler))"
              :percent="Math.round(data.prozent ?? 0)"
              :bewertet="data.bewertet ?? 0"
              :gesamt="data.gesamt ?? 0"
              :ampel="data.ampel"
              @click="activeTab = 'requirements'; filterPfeiler = String(pfeiler)"
            />
          </div>
        </div>

        <div v-if="(store.reifegrad?.luecken || []).length > 0" class="luecken-section">
          <h3>🚨 Top-Lücken</h3>
          <div class="luecken-list">
            <div v-for="l in (store.reifegrad?.luecken || []).slice(0, 8)"
                 :key="l.id" class="luecken-item"
                 @click="editAnforderungById(l.id)">
              <code>{{ l.id }}</code>
              <strong>{{ l.titel }}</strong>
              <span class="luecken-meta">{{ l.kapitel }} · Gew. {{ l.gewichtung }} · Score {{ l.bewertung }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Anforderungen -->
      <div v-if="activeTab === 'requirements'" class="tab-content">
        <div class="anf-toolbar">
          <input v-model="searchQuery" placeholder="Suche…" class="search" />
          <select v-model="filterPfeiler" class="filter">
            <option value="">Alle Pfeiler</option>
            <option v-for="(label, id) in store.constants?.pfeiler || {}" :key="id" :value="id">
              {{ id }} – {{ label }}
            </option>
          </select>
          <select v-model="filterStatus" class="filter">
            <option value="all">Alle</option>
            <option value="pending">Ausstehend</option>
            <option value="partial">Teilweise</option>
            <option value="complete">Vollständig</option>
          </select>
          <button class="btn-secondary" @click="customDialogOpen = true">+ Custom</button>
          <span class="info">{{ visibleAnforderungen.length }} / {{ store.anforderungen.length }}</span>
          <DownloadButton :endpoint="stripApi(exportUrl('docx'))" class="export-btn">📝 Word</DownloadButton>
          <DownloadButton :endpoint="stripApi(exportUrl('pdf'))" class="export-btn">📄 PDF</DownloadButton>
          <ImportButton
            v-if="store.selectedProjekt"
            variant="secondary"
            :endpoint="`/dora/projekte/${encodeURIComponent(store.selectedProjekt)}/fragebogen/import`"
            label="⬆️ Import"
            @imported="onImported"
          />
        </div>

        <div class="anf-list">
          <table v-if="visibleAnforderungen.length > 0">
            <thead>
              <tr>
                <th>ID</th>
                <th>Pfeiler</th>
                <th>Ref</th>
                <th>Titel</th>
                <th>Bewertung</th>
                <th>Status</th>
                <th>Gewicht</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in visibleAnforderungen" :key="r.id" @click="editingReq = r">
                <td><code>{{ r.id }}</code></td>
                <td>{{ r.pfeiler }}</td>
                <td>{{ r.ref }}</td>
                <td class="title-cell">{{ r.titel }}</td>
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
      </div>

      <!-- TPP-Register -->
      <div v-if="activeTab === 'tpp'" class="tab-content">
        <div class="anf-toolbar">
          <h3 class="section-h3">Drittanbieter-Register</h3>
          <span class="info">{{ store.tpps.length }} Einträge · {{ kritischeTppCount }} kritisch</span>
          <button class="btn-primary" @click="openTPPDialog(null)">+ Neuer TPP</button>
        </div>

        <div class="anf-list">
          <table v-if="store.tpps.length > 0">
            <thead>
              <tr>
                <th>Name</th>
                <th>Kategorie</th>
                <th>Kritisch</th>
                <th>Risiko</th>
                <th>Status</th>
                <th>Vertrag</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in store.tpps" :key="t.id" @click="openTPPDialog(t)">
                <td><strong>{{ t.name }}</strong></td>
                <td>{{ t.kategorie }}</td>
                <td>
                  <span v-if="t.kritisch" class="critical-badge">⚠ KRITISCH</span>
                  <span v-else class="muted">—</span>
                </td>
                <td>{{ t.risiko_score }}/5</td>
                <td>{{ t.status }}</td>
                <td>
                  <a v-if="t.vertrag_url" :href="t.vertrag_url" target="_blank" @click.stop>📄</a>
                  <span v-else class="muted">—</span>
                </td>
                <td>
                  <button class="btn-tiny" @click.stop="onDeleteTPP(t)">✕</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty">Keine Drittanbieter erfasst.</div>
        </div>
      </div>

      <!-- Testing-Plan -->
      <div v-if="activeTab === 'testing'" class="tab-content">
        <div class="anf-toolbar">
          <h3 class="section-h3">Testing-Plan (TLPT + Vulnerability-Tests)</h3>
          <span class="info">{{ store.tests.length }} Tests</span>
          <button class="btn-primary" @click="openTestDialog(null)">+ Neuer Test</button>
        </div>

        <div class="anf-list">
          <table v-if="store.tests.length > 0">
            <thead>
              <tr>
                <th>Typ</th>
                <th>Scope</th>
                <th>Frequenz</th>
                <th>Nächster Termin</th>
                <th>Status</th>
                <th>Verantwortlich</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in store.tests" :key="t.id" @click="openTestDialog(t)">
                <td>
                  <strong>{{ t.test_typ }}</strong>
                  <span v-if="t.test_typ === 'TLPT'" class="tlpt-badge">TLPT</span>
                </td>
                <td class="title-cell">{{ t.scope }}</td>
                <td>{{ t.frequenz }}</td>
                <td>{{ t.naechster_termin || '—' }}</td>
                <td><span :class="['test-status', t.status]">{{ t.status }}</span></td>
                <td>{{ t.verantwortlich }}</td>
                <td>
                  <button class="btn-tiny" @click.stop="onDeleteTest(t)">✕</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty">Keine Tests geplant.</div>
        </div>
      </div>
    </template>

    <!-- Anforderungs-Editor (shared) -->
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
          api-base="/dora"
          @saved="onActionSaved"
          @error="(msg: string) => store.error = msg"
        />
      </template>
    </RequirementEditor>

    <!-- TPP-Dialog -->
    <div v-if="tppDialog.open" class="modal-overlay" @click.self="tppDialog.open = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ tppDialog.editing?.id ? 'TPP bearbeiten' : 'Neuer Drittanbieter' }}</h3>
          <button class="btn-close" @click="tppDialog.open = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Name *</label>
            <input v-model="tppForm.name" placeholder="z.B. AWS, Microsoft 365" />
          </div>
          <div class="form-row">
            <label>Kategorie</label>
            <select v-model="tppForm.kategorie">
              <option value="cloud">Cloud-Service</option>
              <option value="saas">SaaS</option>
              <option value="payment">Payment-Provider</option>
              <option value="data_center">Rechenzentrum</option>
              <option value="security">Security-Anbieter</option>
              <option value="other">Sonstige</option>
            </select>
          </div>
          <div class="form-row">
            <label class="checkbox-label">
              <input type="checkbox" v-model="tppForm.kritisch" />
              Kritischer Drittanbieter (Art. 31 DORA)
            </label>
          </div>
          <div class="form-row">
            <label>Beschreibung</label>
            <textarea v-model="tppForm.beschreibung" rows="2"></textarea>
          </div>
          <div class="form-row">
            <label>Vertrags-URL / Dokument</label>
            <input v-model="tppForm.vertrag_url" placeholder="https://..." />
          </div>
          <div class="form-row">
            <label>Ansprechpartner</label>
            <input v-model="tppForm.ansprechpartner" />
          </div>
          <div class="form-row">
            <label>Risiko-Score (0-5)</label>
            <input v-model.number="tppForm.risiko_score" type="number" min="0" max="5" />
          </div>
          <div class="form-row">
            <label>Status</label>
            <select v-model="tppForm.status">
              <option value="active">Aktiv</option>
              <option value="onboarding">Onboarding</option>
              <option value="exit_planned">Exit geplant</option>
              <option value="terminated">Beendet</option>
            </select>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="tppDialog.open = false">Abbrechen</button>
          <button class="btn-primary" @click="onSaveTPP">Speichern</button>
        </div>
      </div>
    </div>

    <!-- Test-Dialog -->
    <div v-if="testDialog.open" class="modal-overlay" @click.self="testDialog.open = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ testDialog.editing?.id ? 'Test bearbeiten' : 'Neuer Test' }}</h3>
          <button class="btn-close" @click="testDialog.open = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Test-Typ *</label>
            <select v-model="testForm.test_typ">
              <option value="TLPT">TLPT (Threat-Led Penetration Testing)</option>
              <option value="vulnerability_scan">Vulnerability Scan</option>
              <option value="pen_test">Penetration Test</option>
              <option value="bcm_drill">BCM-Drill / DR-Test</option>
              <option value="red_team">Red-Team-Übung</option>
              <option value="other">Sonstige</option>
            </select>
          </div>
          <div class="form-row">
            <label>Scope</label>
            <textarea v-model="testForm.scope" rows="2" placeholder="z.B. Online-Banking-Plattform inkl. Auth"></textarea>
          </div>
          <div class="form-row">
            <label>Frequenz</label>
            <input v-model="testForm.frequenz" placeholder="z.B. jährlich, alle 3 Jahre" />
          </div>
          <div class="form-row">
            <label>Nächster Termin</label>
            <input v-model="testForm.naechster_termin" type="date" />
          </div>
          <div class="form-row">
            <label>Status</label>
            <select v-model="testForm.status">
              <option value="planned">Geplant</option>
              <option value="in_progress">In Durchführung</option>
              <option value="completed">Abgeschlossen</option>
              <option value="cancelled">Abgesagt</option>
            </select>
          </div>
          <div class="form-row">
            <label>Verantwortlich</label>
            <input v-model="testForm.verantwortlich" />
          </div>
          <div class="form-row">
            <label>Ergebnis / Bemerkungen</label>
            <textarea v-model="testForm.ergebnis" rows="3"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="testDialog.open = false">Abbrechen</button>
          <button class="btn-primary" @click="onSaveTest">Speichern</button>
        </div>
      </div>
    </div>

    <!-- Custom-Anforderungs-Dialog -->
    <div v-if="customDialogOpen" class="modal-overlay" @click.self="customDialogOpen = false">
      <div class="modal-content">
        <h3>Neue Custom-Anforderung</h3>
        <div class="form-row">
          <label>ID *</label>
          <input v-model="customForm.id" placeholder="z.B. ICT-RM-CUSTOM-01" />
        </div>
        <div class="form-row">
          <label>Pfeiler</label>
          <select v-model="customForm.pfeiler">
            <option v-for="(label, id) in store.constants?.pfeiler || {}" :key="id" :value="id">
              {{ id }} – {{ label }}
            </option>
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
import { useDoraStore, type DoraTPP, type DoraTest } from '../../stores/dora'
import MaturityGauge from '../../components/shared/MaturityGauge.vue'
import ChapterCard from '../../components/shared/ChapterCard.vue'
import RequirementEditor from '../../components/shared/RequirementEditor.vue'
import RequirementActions from '../../components/shared/RequirementActions.vue'
import ImportButton from '../../components/shared/ImportButton.vue'
import HelpDialog from '../../components/shared/HelpDialog.vue'

const store = useDoraStore()
const helpOpen = ref(false)

const confirmDeleteProjekt = async () => {
  if (!store.selectedProjekt) return
  if (!confirm(`DORA-Projekt "${store.selectedProjekt}" wirklich löschen?\n\nAlle Bewertungen, TPP-Verträge und Resilience-Tests gehen verloren.`)) return
  await store.deleteProjekt(store.selectedProjekt)
}

const onImported = async () => {
  if (!store.selectedProjekt) return
  await store.fetchAnforderungen(store.selectedProjekt)
  await store.fetchReifegrad(store.selectedProjekt)
}

const tabs = [
  { id: 'dashboard', label: '📊 Dashboard' },
  { id: 'requirements', label: '📋 Anforderungen' },
  { id: 'tpp', label: '🤝 TPP-Register' },
  { id: 'testing', label: '🧪 Testing-Plan' },
]
const activeTab = ref<'dashboard' | 'requirements' | 'tpp' | 'testing'>('dashboard')

const creating = ref(false)
const newForm = ref({ name: '', unternehmen: '', finanzeinrichtung_klasse: '', beschreibung: '' })

const editingReq = ref<any | null>(null)

const customDialogOpen = ref(false)
const customForm = ref({ id: '', pfeiler: 'ICT-RM', titel: '', beschreibung: '', hinweise: '', gewichtung: 1 })

const searchQuery = ref('')
const filterPfeiler = ref('')
const filterStatus = ref<'all' | 'pending' | 'partial' | 'complete'>('all')

// TPP
const tppDialog = ref<{ open: boolean; editing: DoraTPP | null }>({ open: false, editing: null })
const tppForm = ref<Partial<DoraTPP>>({})

// Tests
const testDialog = ref<{ open: boolean; editing: DoraTest | null }>({ open: false, editing: null })
const testForm = ref<Partial<DoraTest>>({})

const PFEILER_LABEL: Record<string, string> = {
  'ICT-RM': 'ICT Risk Management',
  'ICT-IM': 'ICT Incident Management',
  'ICT-RT': 'Resilience Testing',
  'ICT-TP': 'Third-Party Risk',
  'ICT-IS': 'Information Sharing',
}
const pfeilerLabel = (k: string): string => PFEILER_LABEL[k] || k

const visibleAnforderungen = computed(() => {
  let list = store.anforderungen
  if (filterPfeiler.value) list = list.filter(a => a.pfeiler === filterPfeiler.value)
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

const kritischeTppCount = computed(() => store.tpps.filter(t => t.kritisch).length)

const SCORE_COLORS = ['#9e9e9e', '#c62828', '#e65100', '#f57f17', '#558b2f', '#2e7d32']
const scoreColor = (s: number) => SCORE_COLORS[s] || '#9e9e9e'

const statusLabel = (s: string): string => {
  if (s === 'complete') return 'Vollständig'
  if (s === 'partial') return 'Teilweise'
  return 'Ausstehend'
}

const exportUrl = (fmt: string): string => {
  if (!store.selectedProjekt) return '#'
  return `/api/dora/projekte/${encodeURIComponent(store.selectedProjekt)}/report?format=${fmt}`
}

const startNew = () => {
  newForm.value = { name: '', unternehmen: '', finanzeinrichtung_klasse: '', beschreibung: '' }
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

const editAnforderungById = (id: string) => {
  const r = store.anforderungen.find(a => a.id === id)
  if (r) editingReq.value = r
}

const onSaveBewertung = async (data: any) => {
  if (!editingReq.value || !store.selectedProjekt) return
  const ok = await store.saveBewertung(store.selectedProjekt, editingReq.value.id, data)
  if (ok) {
    editingReq.value = null
    await reloadProjekt()
  }
}

const onActionSaved = async () => {
  editingReq.value = null
  await reloadProjekt()
}

const onSaveCustom = async () => {
  if (!customForm.value.id || !customForm.value.titel) return
  const ok = await store.saveCustomAnforderung(customForm.value)
  if (ok) {
    customDialogOpen.value = false
    customForm.value = { id: '', pfeiler: 'ICT-RM', titel: '', beschreibung: '', hinweise: '', gewichtung: 1 }
    await reloadProjekt()
  }
}

// TPP
const openTPPDialog = (tpp: DoraTPP | null) => {
  tppDialog.value = { open: true, editing: tpp }
  tppForm.value = tpp
    ? { ...tpp, kritisch: !!tpp.kritisch }
    : {
        name: '', kategorie: 'cloud', kritisch: false, beschreibung: '',
        vertrag_url: '', ansprechpartner: '', risiko_score: 0, status: 'active',
      }
}

const onSaveTPP = async () => {
  if (!store.selectedProjekt || !tppForm.value.name) return
  const data: any = { ...tppForm.value, kritisch: !!tppForm.value.kritisch }
  const ok = await store.saveTPP(store.selectedProjekt, data)
  if (ok) tppDialog.value.open = false
}

const onDeleteTPP = async (tpp: DoraTPP) => {
  if (!store.selectedProjekt) return
  if (!confirm(`TPP "${tpp.name}" wirklich löschen?`)) return
  await store.deleteTPP(store.selectedProjekt, tpp.id)
}

// Tests
const openTestDialog = (test: DoraTest | null) => {
  testDialog.value = { open: true, editing: test }
  testForm.value = test
    ? { ...test }
    : {
        test_typ: 'vulnerability_scan', scope: '', frequenz: 'jährlich',
        naechster_termin: '', status: 'planned', verantwortlich: '', ergebnis: '',
      }
}

const onSaveTest = async () => {
  if (!store.selectedProjekt) return
  const ok = await store.saveTest(store.selectedProjekt, testForm.value)
  if (ok) testDialog.value.open = false
}

const onDeleteTest = async (test: DoraTest) => {
  if (!store.selectedProjekt) return
  if (!confirm(`Test "${test.test_typ}" wirklich löschen?`)) return
  await store.deleteTest(store.selectedProjekt, test.id)
}

const reloadProjekt = async () => {
  if (!store.selectedProjekt) return
  await Promise.all([
    store.fetchAnforderungen(store.selectedProjekt),
    store.fetchReifegrad(store.selectedProjekt),
    store.fetchTPPs(store.selectedProjekt),
    store.fetchTests(store.selectedProjekt),
  ])
}

watch(() => store.selectedProjekt, async (n) => {
  if (n) await reloadProjekt()
})

onMounted(async () => {
  await Promise.all([
    store.fetchProjekte(),
    store.fetchConstants(),
  ])
  if (store.selectedProjekt) await reloadProjekt()
})
</script>

<style scoped>
.dora-view { max-width: 1400px; }

.header { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border); }
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
  background: #ffebee; color: #c62828; padding: 10px;
  border-radius: 4px; margin-bottom: 12px; border: 1px solid #ef5350;
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
.form-row input, .form-row select, .form-row textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border);
  border-radius: 4px; font-size: 13px; font-family: inherit;
}
.form-row textarea { resize: vertical; min-height: 60px; }
.checkbox-label { display: flex; align-items: center; gap: 8px; cursor: pointer; }

.form-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }

.tabs {
  display: flex; gap: 2px; margin-bottom: 16px;
  border-bottom: 2px solid var(--color-border);
}

.tab-btn {
  background: none; border: none; padding: 10px 18px;
  font-size: 14px; font-weight: 500; cursor: pointer;
  border-bottom: 3px solid transparent; color: #666;
}

.tab-btn.active {
  color: var(--color-primary); border-bottom-color: var(--color-primary);
  background: #f5f5f5;
}

.tab-content { padding: 8px 0; }

.dashboard {
  display: grid; grid-template-columns: 280px 1fr; gap: 16px; margin-bottom: 16px;
}
.gauge-card {
  background: white; border: 1px solid var(--color-border); border-radius: 8px; padding: 16px;
  display: flex; flex-direction: column; align-items: center;
}
.gauge-stats { margin-top: 12px; text-align: center; font-size: 12px; color: #666; }
.gauge-stats div { margin-bottom: 4px; }

.pfeiler-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px;
}

.luecken-section {
  background: white; border: 1px solid var(--color-border);
  border-radius: 6px; padding: 12px 16px;
}
.luecken-section h3 { margin: 0 0 8px; font-size: 14px; }
.luecken-list { display: flex; flex-direction: column; gap: 4px; }
.luecken-item {
  display: flex; align-items: center; gap: 8px; padding: 6px 10px;
  background: #fff8e1; border-radius: 4px; cursor: pointer; font-size: 12px;
}
.luecken-item:hover { background: #fff3c4; }
.luecken-item code { background: white; padding: 1px 6px; border-radius: 3px; font-size: 11px; }
.luecken-item strong { flex: 1; font-weight: 500; }
.luecken-meta { font-size: 11px; color: #666; }

.anf-toolbar {
  display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;
}
.section-h3 { margin: 0; font-size: 16px; }

.search { flex: 1; min-width: 200px; padding: 6px 10px; border: 1px solid var(--color-border);
  border-radius: 4px; font-size: 13px; }
.filter { padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; }
.info { color: #888; font-size: 12px; margin-left: auto; }
.export-btn {
  padding: 5px 10px; background: white; border: 1px solid var(--color-border);
  border-radius: 4px; font-size: 12px; text-decoration: none; color: #333;
}
.export-btn:hover { border-color: var(--color-primary); color: var(--color-primary); }

.anf-list {
  background: white; border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden;
}
.anf-list table { width: 100%; border-collapse: collapse; font-size: 13px; }
.anf-list th {
  background: #f5f5f5; text-align: left; padding: 10px; font-weight: 600;
  border-bottom: 1px solid var(--color-border);
}
.anf-list tbody tr { cursor: pointer; }
.anf-list tbody tr:hover { background: #f5f5f5; }
.anf-list td { padding: 8px 10px; border-bottom: 1px solid #f0f0f0; }
.title-cell { max-width: 400px; }

.score-pill {
  padding: 2px 10px; border-radius: 3px; color: white; font-size: 11px; font-weight: 600;
}

.status-pill {
  padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;
}
.status-pill.pending { background: #f3e5f5; color: #6a1b9a; }
.status-pill.partial { background: #fff3e0; color: #e65100; }
.status-pill.complete { background: #e8f5e9; color: #2e7d32; }

.critical-badge {
  background: #ffebee; color: #c62828; padding: 2px 8px;
  border-radius: 3px; font-size: 11px; font-weight: 600;
}

.tlpt-badge {
  background: #1565c0; color: white;
  padding: 2px 6px; margin-left: 6px;
  border-radius: 3px; font-size: 10px; font-weight: 600;
}

.test-status {
  padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;
}
.test-status.planned { background: #e3f2fd; color: #1565c0; }
.test-status.in_progress { background: #fff3e0; color: #e65100; }
.test-status.completed { background: #e8f5e9; color: #2e7d32; }
.test-status.cancelled { background: #f5f5f5; color: #999; }

.muted { color: #888; font-size: 12px; }

.btn-tiny {
  background: none; border: 1px solid #ddd;
  width: 22px; height: 22px;
  border-radius: 3px; cursor: pointer; color: #888;
}
.btn-tiny:hover { background: #ffebee; color: #c62828; border-color: #c62828; }

.empty { padding: 40px; text-align: center; color: #888; }

.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal-content {
  background: white; border-radius: 8px;
  max-width: 600px; width: 90%; max-height: 90vh;
  display: flex; flex-direction: column;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid var(--color-border);
}
.modal-header h3 { margin: 0; color: var(--color-primary); font-size: 16px; }
.btn-close { background: none; border: none; font-size: 22px; color: #999; cursor: pointer; }
.modal-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.modal-footer {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 12px 20px; border-top: 1px solid var(--color-border);
}
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }

.btn-primary, .btn-secondary {
  padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;
}
.btn-primary { background: var(--color-primary); color: white; }
.btn-secondary { background: #e0e0e0; color: #333; }

@media (max-width: 768px) {
  .dashboard { grid-template-columns: 1fr; }
}
</style>
