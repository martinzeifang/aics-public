<template>
  <ModuleShell
    class="wiba-view"
    title="WiBA – Weg in die Basis-Absicherung"
    subtitle="BSI IT-Grundschutz · Prüffragen zur Basis-Absicherung"
    module-name="wiba"
    :tabs="store.selectedProjektObj ? tabs : []"
    v-model="activeTab"
  >
    <div v-if="store.error" class="alert-error" @click="store.error = null">{{ store.error }}</div>

    <!-- Leerzustand / Projektwahl -->
    <div v-if="!store.selectedProjektObj && !creating" class="empty-state">
      <h3>{{ store.projekte.length === 0 ? 'Noch kein WiBA-Projekt' : 'Projekt wählen' }}</h3>
      <p>Lege ein neues Projekt an oder wähle ein bestehendes.</p>
      <div class="proj-select" v-if="store.projekte.length">
        <select v-model="pickProjekt">
          <option value="">— Projekt wählen —</option>
          <option v-for="p in store.projekte" :key="p.name" :value="p.name">
            {{ p.name }}<span v-if="p.unternehmen"> ({{ p.unternehmen }})</span>
          </option>
        </select>
        <button class="btn-secondary" :disabled="!pickProjekt" @click="selectProjekt">Öffnen</button>
      </div>
      <button class="btn-primary" @click="startNew">+ Neues WiBA-Projekt</button>
    </div>

    <!-- Neues Projekt -->
    <div v-else-if="creating" class="form-card">
      <h3>Neues WiBA-Projekt</h3>
      <div class="form-row">
        <label>Projektname *</label>
        <input v-model="newForm.name" placeholder="z.B. Basis-Absicherung 2026" />
      </div>
      <div class="form-row">
        <label>Firma</label>
        <select v-model="newForm.unternehmen">
          <option value="">— ohne Firma —</option>
          <option v-for="k in firmenStore.firmen" :key="k.name" :value="k.name">
            {{ k.name }}<span v-if="k.company"> ({{ k.company }})</span>
          </option>
        </select>
        <small class="hint">Verknüpft das Projekt mit einer Firma aus der Firmenverwaltung.</small>
      </div>
      <div class="form-row">
        <label>Berater</label>
        <input v-model="newForm.berater" placeholder="Verantwortliche Person" />
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

    <!-- Projekt-Leiste -->
    <template v-if="store.selectedProjektObj" #project-bar>
      <h3 class="project-name">{{ store.selectedProjektObj?.name }}
        <span v-if="store.selectedProjektObj?.unternehmen" class="project-company">— {{ store.selectedProjektObj.unternehmen }}</span>
      </h3>
      <select class="proj-switch" :value="store.selectedProjekt || ''" @change="onSwitch($event)">
        <option v-for="p in store.projekte" :key="p.name" :value="p.name">{{ p.name }}</option>
      </select>
      <button class="btn-secondary" @click="startNew">+ Neu</button>
      <button class="btn-danger-mini" @click="confirmDelete" title="Projekt löschen">🗑️ Projekt löschen</button>
    </template>

    <!-- Repo-Config pro Projekt -->
    <template v-if="store.selectedProjektObj && store.selectedProjekt" #repo-config>
      <RepoConfigPanel :api-base="'/wiba'" :projekt-name="store.selectedProjekt" />
    </template>

    <!-- Tab-Inhalte -->
    <template v-if="store.selectedProjektObj">
      <div v-show="activeTab === 'dashboard'" class="tab-content">
        <DashboardPanel />
      </div>

      <div v-if="activeTab === 'risikocockpit'" class="tab-content">
        <RiskCockpitPanel v-if="store.selectedProjekt" :projekt="store.selectedProjekt" />
      </div>

      <div v-if="activeTab === 'dokumentation'" class="tab-content">
        <DokumentationPanel />
      </div>

      <div v-if="activeTab === 'prueffragen'" class="tab-content">
        <PrueffragenPanel @changed="reloadControls" />
      </div>

      <div v-if="activeTab === 'assistenten'" class="tab-content">
        <AssistentenPanel v-if="store.selectedProjekt" @applied="reloadControls" />
      </div>

      <div v-if="activeTab === 'bericht'" class="tab-content">
        <BerichtPanel :projekt-name="store.selectedProjekt || ''" />
      </div>
    </template>
  </ModuleShell>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useWibaStore } from '../../stores/wiba'
import { useFirmenStore } from '../../stores/firmen'
import ModuleShell from '../../components/shared/ModuleShell.vue'
import RepoConfigPanel from '../../components/RepoConfigPanel.vue'
import DashboardPanel from './DashboardPanel.vue'
import RiskCockpitPanel from './RiskCockpitPanel.vue'
import DokumentationPanel from './DokumentationPanel.vue'
import PrueffragenPanel from './PrueffragenPanel.vue'
import AssistentenPanel from './AssistentenPanel.vue'
import BerichtPanel from './BerichtPanel.vue'

const store = useWibaStore()
const firmenStore = useFirmenStore()
const route = useRoute()

const tabs = [
  { id: 'dashboard', label: '📊 Dashboard' },
  { id: 'risikocockpit', label: '📊 Risiko-Cockpit' },
  { id: 'dokumentation', label: '📋 Dokumentation' },
  { id: 'prueffragen', label: '✅ Prüffragen' },
  { id: 'assistenten', label: '🤖 Assistenten' },
  { id: 'bericht', label: '📄 Bericht' },
]
const activeTab = ref('dashboard')

const creating = ref(false)
const pickProjekt = ref('')
const newForm = ref({ name: '', unternehmen: '', berater: '', beschreibung: '' })

const startNew = () => {
  newForm.value = { name: '', unternehmen: '', berater: '', beschreibung: '' }
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
    await reloadControls()
  }
}

const selectProjekt = async () => {
  if (!pickProjekt.value) return
  store.selectedProjekt = pickProjekt.value
  await reloadControls()
}

const onSwitch = async (e: Event) => {
  const val = (e.target as HTMLSelectElement).value
  store.selectedProjekt = val || null
  if (val) await reloadControls()
}

const confirmDelete = async () => {
  if (!store.selectedProjekt) return
  if (!confirm(`WiBA-Projekt "${store.selectedProjekt}" wirklich löschen?\n\nAlle Antworten gehen verloren.`)) return
  await store.deleteProjekt(store.selectedProjekt)
}

const reloadControls = async () => {
  if (!store.selectedProjekt) return
  await store.fetchControls(store.selectedProjekt)
}

watch(() => store.selectedProjekt, async (n) => {
  if (n) await reloadControls()
})

onMounted(async () => {
  await Promise.all([
    store.fetchProjekte(),
    store.fetchConstants(),
    store.fetchCatalogStatus(),
  ])
  const proj = (route.query.projekt || '') as string
  if (proj) store.selectedProjekt = proj
  if (store.selectedProjekt) await reloadControls()
})
</script>

<style scoped>
.wiba-view { max-width: 1400px; }

.alert-error {
  background: #ffebee; color: #c62828; padding: 10px; border-radius: 4px;
  margin-bottom: 12px; border: 1px solid #ef5350; cursor: pointer;
}

.empty-state, .form-card {
  background: white; padding: 32px; border-radius: 8px; border: 1px solid var(--color-border);
}
.empty-state { text-align: center; }
.empty-state h3 { margin: 0 0 12px; }
.empty-state p { color: #888; margin-bottom: 20px; }
.proj-select { display: flex; gap: 8px; justify-content: center; margin-bottom: 16px; }
.proj-select select { padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; min-width: 240px; }

.form-card { max-width: 600px; }
.form-card h3 { margin: 0 0 16px; }
.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input, .form-row select, .form-row textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px;
}
.form-row small.hint { display: block; font-size: 11px; color: #888; margin-top: 2px; }
.form-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }

.project-name { margin: 0; font-size: 16px; flex: 1; color: var(--color-text-primary); }
.project-company { font-weight: 400; color: var(--color-text-secondary); font-size: 13px; }
.proj-switch { padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; }

.btn-primary { background: var(--color-primary, #1565c0); color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-primary:hover:not(:disabled) { background: #0d47a1; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: #e0e0e0; color: #333; border: none; padding: 8px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-secondary:hover:not(:disabled) { background: #d5d5d5; }
.btn-secondary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-danger-mini { background: #ffebee; color: #c62828; border: 1px solid #ef5350; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.btn-danger-mini:hover { background: #ffcdd2; }

.tab-content { padding: 8px 0; }
</style>
