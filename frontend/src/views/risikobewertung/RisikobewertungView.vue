<template>
  <ModuleShell
    class="rb-view"
    title="Risikobewertung"
    subtitle="Multi-Framework-Risiko-Editor mit STRIDE, HEAVENS, OCTAVE, TARA, Finanzinstitute"
    module-name="risikobewertung"
    :tabs="rb.selectedProjektObj ? tabs : []"
    v-model="activeTab"
  >
    <div v-if="rb.error" class="alert alert-error">{{ rb.error }}</div>

    <!-- Empty state: kein Projekt gewählt -->
    <div v-if="!rb.selectedProjektObj && !creatingProjekt" class="empty-state">
      <h3>{{ rb.projekte.length === 0 ? 'Noch kein Projekt' : 'Projekt wählen' }}</h3>
      <p v-if="rb.projekte.length === 0">
        Lege ein neues Projekt an oder wähle links eines aus der Sidebar.
      </p>
      <p v-else>Wähle ein Projekt aus der Sidebar, um Risiken zu verwalten.</p>
      <button class="btn-primary" @click="startNewProjekt">+ Neues Projekt</button>
    </div>

    <!-- Neues-Projekt-Form -->
    <div v-else-if="creatingProjekt" class="form-card">
      <h3>Neues Risikobewertungs-Projekt</h3>
      <div class="form-row">
        <label>Projektname *</label>
        <input v-model="newProjektForm.name" placeholder="z.B. Mein Produkt – Risikoanalyse" />
      </div>
      <!-- Issue #428/#429: Firma wählen → unternehmen vorbelegen -->
      <div class="form-row">
        <label>Firma</label>
        <select v-model="newProjektForm.unternehmen" @change="onFirmaChanged">
          <option value="">— ohne Firma —</option>
          <option v-for="k in firmenStore.firmen" :key="k.name" :value="k.name">
            {{ k.name }}<span v-if="k.company"> ({{ k.company }})</span>
          </option>
        </select>
        <small class="hint">
          Pro Firma sind mehrere Risikobewertungs-Projekte möglich
          (Issue #433). Existierende: {{ existingForFirmaCount }}.
        </small>
      </div>
      <div class="form-row">
        <label>Framework wählen</label>
        <select v-model="newProjektForm.framework">
          <option v-for="fw in rb.frameworks" :key="fw.id" :value="fw.id">{{ fw.label }}</option>
        </select>
        <small class="hint">Das Framework legt die Bewertungslogik und Eingabefelder fest.</small>
      </div>
      <div class="form-row">
        <label>Beschreibung</label>
        <textarea v-model="newProjektForm.beschreibung" rows="3"></textarea>
      </div>
      <div class="form-actions">
        <button class="btn-secondary" @click="creatingProjekt = false">Abbrechen</button>
        <button class="btn-primary" @click="onCreateProjekt" :disabled="rb.loading">
          {{ rb.loading ? 'Lädt…' : 'Projekt anlegen' }}
        </button>
      </div>
    </div>

    <!-- Hauptansicht mit gewähltem Projekt -->
    <template v-if="rb.selectedProjektObj">
      <!-- Tab: Dashboard -->
      <div v-if="activeTab === 'dashboard'" class="tab-content">
        <div class="dashboard">
          <div class="dash-card framework-info">
            <div class="dash-label">Projekt</div>
            <div class="dash-value">{{ rb.selectedProjektObj.name }}</div>
            <div class="dash-sub">Framework: <strong>{{ frameworkLabel(rb.selectedProjektObj.framework) }}</strong></div>
          </div>
          <div class="dash-card">
            <div class="dash-label">Risiken gesamt</div>
            <div class="dash-value">{{ rb.stats.total }}</div>
          </div>
          <div class="dash-card critical">
            <div class="dash-label">Kritisch</div>
            <div class="dash-value">{{ rb.stats.kritisch }}</div>
          </div>
          <div class="dash-card high">
            <div class="dash-label">Hoch</div>
            <div class="dash-value">{{ rb.stats.hoch }}</div>
          </div>
          <div class="dash-card resolved">
            <div class="dash-label">Gelöst</div>
            <div class="dash-value">{{ rb.stats.resolved }}</div>
          </div>
        </div>
      </div>

      <!-- Tab: Risiko-Cockpit (#1098 B6) -->
      <div v-if="activeTab === 'cockpit'" class="tab-content">
        <RiskCockpitPanel v-if="rb.selectedProjekt" :projekt="rb.selectedProjekt" />
      </div>

      <!-- Tab: Risiken -->
      <div v-if="activeTab === 'risiken'" class="tab-content">
        <!-- Toolbar -->
        <div class="toolbar">
          <input v-model="searchQuery" placeholder="Risiken durchsuchen…" class="search" />
          <select v-model="filterStatus" class="filter">
            <option value="all">Alle</option>
            <option value="open">Offen</option>
            <option value="resolved">Gelöst</option>
          </select>
          <select v-model="filterLevel" class="filter">
            <option value="all">Alle Level</option>
            <option value="kritisch">Kritisch</option>
            <option value="hoch">Hoch</option>
            <option value="mittel">Mittel</option>
            <option value="niedrig">Niedrig</option>
          </select>
          <button class="btn-primary" @click="startNewRisiko">+ Neues Risiko</button>
          <button class="btn-secondary" @click="assistentOpen = true">🪄 Risiken-Assistent</button>
          <button class="btn-secondary" @click="massOpen = true">🤖 Massen-Bewertung</button>
          <button class="btn-secondary" @click="onIssueSyncReview" title="Neubewertung aller Risiken anhand des Feedbacks aus verknüpften Issues (Re-Assessment).">🧪 Neubewertung aus Issues</button>
          <button class="btn-secondary" @click="onBulkIssues" :disabled="issuesBusy"
                  title="Für alle offenen Risiken GitHub/GitLab-Issues anlegen">
            {{ issuesBusy ? '⏳ Issues…' : '🐙 Issues anlegen' }}
          </button>
          <button class="btn-secondary" @click="syncIssues" :disabled="issuesBusy" title="Offen/Geschlossen-Status aller verknüpften GitHub/GitLab-Issues dieses Projekts aktualisieren (verändert keine Bewertungen).">🔄 Issue-Status abgleichen</button>
          <button class="btn-secondary" @click="onShowAudit">📜 Audit-Log</button>
          <div class="export-group">
            <ImportButton
              v-if="rb.selectedProjekt"
              variant="secondary"
              :endpoint="`/risikobewertung/projekte/${encodeURIComponent(rb.selectedProjekt)}/risiken/import`"
              label="⬆️ Import"
              @imported="onImported"
            />
          </div>
        </div>

        <!-- Risiko-Liste -->
        <div class="risk-list">
          <table v-if="visibleRisiken.length > 0">
            <thead>
              <tr>
                <th>Nr</th>
                <th>Name</th>
                <th>Framework</th>
                <th>Risikowert</th>
                <th>Level</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="r in visibleRisiken"
                :key="r.id"
                :class="{ resolved: r.is_resolved }"
                @click="editRisiko(r)"
              >
                <td>{{ r.nr }}</td>
                <td class="name-cell">
                  {{ r.risk_name || r.name }}
                  <small v-if="r.beschreibung" class="desc">{{ r.beschreibung.substring(0, 80) }}{{ r.beschreibung.length > 80 ? '…' : '' }}</small>
                </td>
                <td>{{ r.framework }}</td>
                <td>{{ r.risikowert ?? '—' }}</td>
                <td>
                  <span class="level-badge" :style="{ background: r.farbe || '#888' }">
                    {{ r.risiko_label || '—' }}
                  </span>
                </td>
                <td>
                  <span :class="['status-pill', r.is_resolved ? 'resolved' : 'open']">
                    {{ r.is_resolved ? '✓ Gelöst' : 'Offen' }}
                  </span>
                </td>
                <td class="action-cell">
                  <button class="btn-small" @click.stop="onCreateIssue(r)" title="GitHub/GitLab-Issue aus diesem Risiko erstellen">🐙</button>
                  <button class="btn-small" @click.stop="editRisiko(r)">✎</button>
                  <button class="btn-danger-small" @click.stop="onDeleteRisiko(r)">🗑</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else-if="rb.risiken.length === 0" class="empty">
            Noch keine Risiken. Klicke "+ Neues Risiko".
          </div>
          <div v-else class="empty">Keine Risiken zum Filter.</div>
        </div>
      </div>

      <!-- Tab: Bericht — geteiltes Berichts-Center (Sprint #35) + Zusatzformate -->
      <div v-if="activeTab === 'bericht'" class="tab-content">
        <ReportCenterPanel
          v-if="rb.selectedProjekt"
          :api-base="`/risikobewertung/projekte/${encodeURIComponent(rb.selectedProjekt)}`"
          title="Risikobewertungs-Berichts-Center"
        />
        <!-- Zusatzformate (XLSX/JSON/MD) deckt das Berichts-Center nicht ab -->
        <ExportPanel
          module="risikobewertung"
          :projekt-name="rb.selectedProjekt || ''"
          :formats="['xlsx', 'json', 'md']"
        />
      </div>
    </template>

    <!-- Projekt-Leiste (ModuleShell #project-bar) -->
    <template v-if="rb.selectedProjektObj" #project-bar>
      <h3 class="project-name">{{ rb.selectedProjektObj.name }}
        <span class="project-company">— Framework: {{ frameworkLabel(rb.selectedProjektObj.framework) }}</span>
      </h3>
      <!-- #17 Stufe 1: Rück-Verknüpfung zum CRA-Projekt (Nachweis AI1-01) -->
      <a
        v-if="rb.selectedProjektObj.linked_cra_projekt"
        class="cra-link-badge"
        :href="`#/cra?projekt=${encodeURIComponent(rb.selectedProjektObj.linked_cra_projekt)}`"
        :title="`Diese Risikoanalyse ist als CRA-Risikoabschätzung mit dem Projekt „${rb.selectedProjektObj.linked_cra_projekt}“ verknüpft`"
      >🔗 Verknüpft mit CRA-Projekt: {{ rb.selectedProjektObj.linked_cra_projekt }}</a>
      <!-- Issue #436: Firma wechseln -->
      <FirmaSelector
        :model-value="(rb.selectedProjektObj as any).unternehmen || ''"
        :saving="reassignSaving"
        :success-text="reassignMsg.ok"
        :error-text="reassignMsg.err"
        @save="onReassignFirma"
      />
      <button class="btn-danger-mini" @click="confirmDeleteProjekt" title="Projekt löschen">🗑️ Projekt löschen</button>
    </template>

    <!-- #918: Repository pro Projekt (analog CRA), inkl. Token -->
    <template v-if="rb.selectedProjektObj && rb.selectedProjekt" #repo-config>
      <RepoConfigPanel
        api-base="/risikobewertung"
        :projekt-name="rb.selectedProjekt"
      />
    </template>

    <template #modals>
      <!-- Massen-Bewertung-Dialog -->
      <MassenBewertungDialog
        v-if="massOpen && rb.selectedProjekt"
        :projekt-name="rb.selectedProjekt"
        @cancel="massOpen = false"
        @refresh="onMassRefresh"
      />

      <!-- Risiken-Assistent (5-Step-Wizard) -->
      <RisikoAssistent
        :open="assistentOpen"
        :projekt-name="rb.selectedProjekt"
        @close="assistentOpen = false"
        @applied="onAssistentApplied"
      />

      <!-- Risiko-Editor -->
      <RisikoEditor
        v-if="editorOpen"
        :risiko="editingRisiko"
        :projekt-name="rb.selectedProjekt || ''"
        :default-framework="rb.selectedProjektObj?.framework"
        :fixed-framework="!!rb.selectedProjektObj"
        @saved="onRisikoSaved"
        @deleted="onRisikoDeleted"
        @cancel="editorOpen = false"
      />

      <!-- Audit-Log-Modal -->
      <div v-if="auditOpen" class="modal-overlay" @mousedown.self="auditOpen = false">
        <div class="modal-content audit-modal">
          <div class="modal-header">
            <h3>📜 Audit-Trail: {{ rb.selectedProjekt }}</h3>
            <button class="btn-close" @click="auditOpen = false">✕</button>
          </div>
          <div class="modal-body">
            <p class="hint">{{ rb.auditTotal }} Änderungen protokolliert</p>
            <table v-if="rb.auditEvents.length > 0" class="audit-table">
              <thead>
                <tr>
                  <th>Zeitstempel</th>
                  <th>Aktion</th>
                  <th>Objekt</th>
                  <th>ID</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(ev, i) in rb.auditEvents" :key="i">
                  <td>{{ formatDate(ev.created_at) }}</td>
                  <td><code>{{ ev.action }}</code></td>
                  <td>{{ ev.object_kind }}</td>
                  <td>{{ ev.object_id }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="empty">Noch keine Audit-Einträge.</div>
          </div>
        </div>
      </div>

      <!-- Issue-Sync Bulk-Modal -->
      <div v-if="issueSyncModal.open" class="modal-overlay" @mousedown.self="issueSyncModal.open = false">
        <div class="modal-content" style="width: min(1000px, 95vw); max-height: 90vh; display: flex; flex-direction: column;">
          <div class="modal-header">
            <h2>🔄 Issue-Sync — verknüpfte Risiken</h2>
            <button class="btn-close" @click="issueSyncModal.open = false">✕</button>
          </div>
          <div class="modal-body" style="overflow: auto;">
            <p class="muted" style="margin-bottom: 12px;">
              Verknüpfungen werden aus der Datenbank-Tabelle <code>linked_issues</code>
              geladen (befüllt durch die Desktop-Variante via Issue-Assistent).
              <span v-if="issueSyncModal.fromDbOnly && issueSyncModal.items.length > 0">
                <br /><strong>DB-Snapshot:</strong> Klick auf „Live-Status holen" für aktuelle GitHub-/GitLab-Daten.
              </span>
            </p>

            <div v-if="issueSyncModal.error" class="alert alert-error" style="margin-bottom: 12px;">
              ⚠ {{ issueSyncModal.error }}
            </div>
            <div v-if="issueSyncModal.loading" class="empty">⏳ Lade Verknüpfungen …</div>
            <div v-else-if="issueSyncModal.items.length === 0" class="empty">
              Keine verknüpften Issues im Projekt gefunden.
              <br /><small>Tipp: Issues mit Risiken werden in der Desktop-Variante via „Issue-Assistent" verknüpft.</small>
            </div>
            <table v-else style="width: 100%; border-collapse: collapse;">
              <thead>
                <tr style="background: #f5f5f5; text-align: left; position: sticky; top: 0;">
                  <th style="padding: 8px;">Risiko</th>
                  <th style="padding: 8px;">Issue</th>
                  <th style="padding: 8px;">Status</th>
                  <th style="padding: 8px;">Provider</th>
                  <th style="padding: 8px;">Live</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(it, idx) in issueSyncModal.items" :key="idx" style="border-bottom: 1px solid #eee">
                  <td style="padding: 8px;">
                    <strong>#{{ it.risk_id }}</strong>
                    <div class="muted" style="font-size: 12px;">{{ it.risk_name || '—' }}</div>
                  </td>
                  <td style="padding: 8px;">
                    <a :href="safeUrl(it.url)" target="_blank" rel="noopener noreferrer">
                      {{ it.title || it.url }}
                    </a>
                  </td>
                  <td style="padding: 8px;">
                    <span :class="['badge', it.state]"
                          :style="{
                            padding: '2px 8px',
                            borderRadius: '4px',
                            background: it.state === 'closed' ? '#e8f5e9' : '#e3f2fd',
                            color: it.state === 'closed' ? '#2e7d32' : '#1565c0',
                            fontSize: '11px',
                            textTransform: 'uppercase',
                          }">
                      {{ it.state || 'unbekannt' }}
                    </span>
                    <div v-if="it.state_reason" class="muted" style="font-size: 11px;">
                      {{ it.state_reason }}
                    </div>
                  </td>
                  <td style="padding: 8px;" class="muted">{{ it.provider }}</td>
                  <td style="padding: 8px;">
                    <span v-if="it.error" style="color: #c62828" :title="it.error">⚠</span>
                    <span v-else-if="it.comments_count !== undefined" class="muted">
                      💬 {{ it.comments_count }}
                    </span>
                    <span v-else class="muted">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="modal-footer" style="display: flex; gap: 8px; align-items: center;">
            <span class="muted">{{ issueSyncModal.items.length }} Verknüpfungen</span>
            <span style="flex: 1;"></span>
            <button class="btn-secondary" @click="loadIssueSync(true)"
                    :disabled="issueSyncModal.refreshing || issueSyncModal.items.length === 0">
              {{ issueSyncModal.refreshing ? '⏳ Hole …' : '🌐 Live-Status holen' }}
            </button>
            <button class="btn-secondary" @click="issueSyncModal.open = false">Schließen</button>
          </div>
        </div>
      </div>
    </template>
  </ModuleShell>
</template>

<script setup lang="ts">
import { safeUrl } from '../../utils/safeUrl'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useRisikobewertungStore, type Risiko } from '../../stores/risikobewertung'
import { useFirmenStore } from '../../stores/firmen'
import RisikoEditor from './RisikoEditor.vue'
import MassenBewertungDialog from './MassenBewertungDialog.vue'
import RisikoAssistent from './RisikoAssistent.vue'
import RepoConfigPanel from '../../components/RepoConfigPanel.vue'
import RiskCockpitPanel from './RiskCockpitPanel.vue'
import ModuleShell from '../../components/shared/ModuleShell.vue'
import ExportPanel from '../../components/shared/ExportPanel.vue'
import ReportCenterPanel from '../../components/shared/ReportCenterPanel.vue'
import ImportButton from '../../components/shared/ImportButton.vue'
import FirmaSelector from '../../components/shared/FirmaSelector.vue'

const rb = useRisikobewertungStore()
const firmenStore = useFirmenStore()
const route = useRoute()

const tabs = [
  { id: 'dashboard', label: '📊 Dashboard' },
  { id: 'cockpit', label: '📊 Risiko-Cockpit' },
  { id: 'risiken', label: '⚠️ Risiken' },
  { id: 'bericht', label: '📄 Bericht' },
]
const activeTab = ref<string>('dashboard')

const onImported = async () => {
  if (rb.selectedProjekt) await rb.fetchRisikenForProjekt(rb.selectedProjekt)
}

const creatingProjekt = ref(false)
const newProjektForm = ref({ name: '', framework: 'STRIDE', beschreibung: '', unternehmen: '' })

const editorOpen = ref(false)
const editingRisiko = ref<Risiko | null>(null)
const auditOpen = ref(false)
const massOpen = ref(false)
const assistentOpen = ref(false)

const onAssistentApplied = async (count: number) => {
  if (rb.selectedProjekt) await rb.fetchRisikenForProjekt(rb.selectedProjekt)
}

const onMassRefresh = () => {
  if (rb.selectedProjekt) {
    rb.fetchRisikenForProjekt(rb.selectedProjekt)
  }
}

const searchQuery = ref('')
const filterStatus = ref<'all' | 'open' | 'resolved'>('all')
const filterLevel = ref<'all' | 'kritisch' | 'hoch' | 'mittel' | 'niedrig'>('all')

const frameworkLabel = (id: string): string => {
  return rb.frameworks.find(f => f.id === id)?.label || id
}

const visibleRisiken = computed(() => {
  let list = rb.risiken
  if (filterStatus.value === 'open') list = list.filter(r => !r.is_resolved)
  if (filterStatus.value === 'resolved') list = list.filter(r => r.is_resolved)
  if (filterLevel.value !== 'all') {
    list = list.filter(r => (r.risiko_label || '').toLowerCase().includes(filterLevel.value))
  }
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(r =>
      (r.risk_name || r.name || '').toLowerCase().includes(q) ||
      (r.beschreibung || '').toLowerCase().includes(q),
    )
  }
  return list
})

// Issue #436: Firma des Projekts nachtraeglich aendern
const reassignSaving = ref(false)
const reassignMsg = ref<{ ok: string; err: string }>({ ok: '', err: '' })
const onReassignFirma = async (newFirma: string) => {
  if (!rb.selectedProjekt) return
  reassignSaving.value = true
  reassignMsg.value = { ok: '', err: '' }
  try {
    await rb.updateProjekt(rb.selectedProjekt, { unternehmen: newFirma } as any)
    await rb.fetchProjekte()
    reassignMsg.value.ok = newFirma
      ? `✓ Firma geändert auf „${newFirma}"`
      : '✓ Firmenzuordnung entfernt'
    setTimeout(() => { reassignMsg.value = { ok: '', err: '' } }, 4000)
  } catch (e: any) {
    reassignMsg.value.err = e?.response?.data?.error || 'Fehler beim Speichern'
  } finally {
    reassignSaving.value = false
  }
}

const startNewProjekt = () => {
  newProjektForm.value = { name: '', framework: 'STRIDE', beschreibung: '', unternehmen: '' }
  creatingProjekt.value = true
  if (firmenStore.firmen.length === 0) {
    firmenStore.fetchFirmen()
  }
}

// Issue #433: Wenn ein Firma gewaehlt wird, Anzahl existierender
// RB-Projekte fuer diesen Firmen zaehlen + Name-Vorschlag generieren.
const existingForFirmaCount = computed(() => {
  const k = newProjektForm.value.unternehmen
  if (!k) return 0
  return rb.projekte.filter((p: any) => (p.unternehmen || p.company) === k).length
})

const onFirmaChanged = () => {
  const k = newProjektForm.value.unternehmen
  if (!k) return
  // Falls Name leer ist, einen Default vorschlagen
  if (!newProjektForm.value.name.trim()) {
    const count = rb.projekte.filter((p: any) => (p.unternehmen || p.company) === k).length
    newProjektForm.value.name = count === 0
      ? `${k} – Risikoanalyse`
      : `${k} – Risikoanalyse ${count + 1}`
  }
}

const confirmDeleteProjekt = async () => {
  if (!rb.selectedProjekt) return
  if (!confirm(`RB-Projekt "${rb.selectedProjekt}" wirklich löschen?\n\nAlle Risiken gehen verloren.`)) return
  await rb.deleteProjekt(rb.selectedProjekt)
}

const onCreateProjekt = async () => {
  if (!newProjektForm.value.name.trim()) {
    rb.error = 'Projektname ist Pflicht.'
    return
  }
  const result = await rb.createProjekt({
    name: newProjektForm.value.name.trim(),
    framework: newProjektForm.value.framework,
    beschreibung: newProjektForm.value.beschreibung,
    unternehmen: newProjektForm.value.unternehmen || '',
  } as any)
  if (result) {
    rb.selectedProjekt = result.name
    creatingProjekt.value = false
    await rb.fetchRisikenForProjekt(result.name)
  }
}

const startNewRisiko = () => {
  editingRisiko.value = null
  editorOpen.value = true
}

const editRisiko = (r: Risiko) => {
  editingRisiko.value = r
  editorOpen.value = true
}

const onRisikoSaved = (r: Risiko) => {
  editorOpen.value = false
  if (rb.selectedProjekt) {
    rb.fetchRisikenForProjekt(rb.selectedProjekt)
  }
}

const onRisikoDeleted = (riskId: number) => {
  editorOpen.value = false
  rb.risiken = rb.risiken.filter(r => r.id !== riskId)
}

const onDeleteRisiko = async (r: Risiko) => {
  if (!r.id || !rb.selectedProjekt) return
  if (!confirm(`Risiko "${r.risk_name || r.name}" wirklich löschen?`)) return
  await rb.deleteRisiko(r.id, rb.selectedProjekt)
}

const onShowAudit = async () => {
  if (!rb.selectedProjekt) return
  await rb.fetchAudit(rb.selectedProjekt)
  auditOpen.value = true
}

// #786: Issue aus einem einzelnen Risiko erstellen
const issuesBusy = ref(false)
const onCreateIssue = async (r: Risiko) => {
  if (!r.id || !rb.selectedProjekt) return
  issuesBusy.value = true
  try {
    const { default: api } = await import('../../api/client')
    const res = await api.post(
      `/risikobewertung/projekte/${encodeURIComponent(rb.selectedProjekt)}/risiken/${r.id}/issue`,
      {}, { timeout: 30_000 },
    )
    const url = res.data?.url
    if (url && confirm(`Issue erstellt: ${url}\n\nJetzt öffnen?`)) window.open(url, '_blank', 'noopener')
  } catch (e: any) {
    alert(e?.response?.data?.error || 'Issue konnte nicht erstellt werden. Repo-Kontext + Token prüfen.')
  } finally { issuesBusy.value = false }
}

// #786: Massenaktion — Issues für alle offenen Risiken anlegen
const onBulkIssues = async () => {
  if (!rb.selectedProjekt) return
  if (!confirm('Für alle OFFENEN Risiken dieses Projekts GitHub/GitLab-Issues anlegen?\n(Bereits verknüpfte Risiken werden übersprungen.)')) return
  issuesBusy.value = true
  try {
    const { default: api } = await import('../../api/client')
    const res = await api.post(
      `/risikobewertung/projekte/${encodeURIComponent(rb.selectedProjekt)}/issues/bulk`,
      { only_open: true, skip_linked: true }, { timeout: 180_000 },
    )
    const s = res.data?.summary || { created: 0, skipped: 0, failed: 0 }
    let msg = `Fertig: ${s.created} erstellt, ${s.skipped} übersprungen, ${s.failed} fehlgeschlagen.`
    if (s.failed && res.data?.failed?.length) msg += `\n\nFehler: ${res.data.failed[0].error}`
    alert(msg)
  } catch (e: any) {
    alert(e?.response?.data?.error || 'Massen-Issue-Erstellung fehlgeschlagen. Repo-Kontext + Token prüfen.')
  } finally { issuesBusy.value = false }
}

// #788: Projektweiter Issue-Sync — Status aller verlinkten Issues aktualisieren
const syncIssues = async () => {
  if (!rb.selectedProjekt) return
  issuesBusy.value = true
  try {
    const { default: api } = await import('../../api/client')
    const r = await api.post(`/risikobewertung/projekte/${encodeURIComponent(rb.selectedProjekt)}/issues/sync`, {}, { timeout: 120000 })
    const d = r.data || {}
    alert(`Issues synchronisiert: ${d.synced || 0} aktualisiert, ${d.errors || 0} Fehler (gesamt ${d.total || 0}).`)
  } catch (e: any) {
    alert(e?.response?.data?.error || 'Issue-Sync fehlgeschlagen.')
  } finally { issuesBusy.value = false }
}

// Issue-Sync (Bulk, #404): liest linked_issues aus der DB; optional live refresh
const issueSyncModal = ref<{
  open: boolean; loading: boolean; refreshing: boolean;
  items: any[]; error: string; fromDbOnly: boolean;
}>({
  open: false, loading: false, refreshing: false,
  items: [], error: '', fromDbOnly: true,
})
const onIssueSyncReview = () => {
  if (!rb.selectedProjekt) return
  issueSyncModal.value = {
    open: true, loading: true, refreshing: false,
    items: [], error: '', fromDbOnly: true,
  }
  loadIssueSync(false)
}
const loadIssueSync = async (refresh: boolean) => {
  if (!rb.selectedProjekt) return
  if (refresh) issueSyncModal.value.refreshing = true
  else issueSyncModal.value.loading = true
  issueSyncModal.value.error = ''
  try {
    const { default: api } = await import('../../api/client')
    const r = await api.post(
      `/risikobewertung/projekte/${encodeURIComponent(rb.selectedProjekt)}/issue-sync`,
      { refresh },
      // Live-Refresh kann pro Issue ~1s brauchen → für 20+ Risiken großzügig
      { timeout: refresh ? 120_000 : 30_000 },
    )
    issueSyncModal.value.items = r.data.items || []
    issueSyncModal.value.fromDbOnly = !!r.data.from_db_only
  } catch (e: any) {
    const parts: string[] = []
    if (e?.response?.status) parts.push(`HTTP ${e.response.status}`)
    if (e?.response?.data?.error) parts.push(String(e.response.data.error))
    else if (e?.response?.data?.message) parts.push(String(e.response.data.message))
    else if (e?.message) parts.push(e.message)
    else parts.push('Unbekannter Fehler')
    issueSyncModal.value.error = parts.join(' · ')
    // eslint-disable-next-line no-console
    console.error('[issue-sync]', e?.response || e)
  } finally {
    issueSyncModal.value.loading = false
    issueSyncModal.value.refreshing = false
  }
}

const formatDate = (s: string): string => {
  if (!s) return ''
  try {
    return new Date(s.replace(' ', 'T') + 'Z').toLocaleString('de-DE')
  } catch {
    return s
  }
}

// Issue #426: Bei Wechsel auf 'Alle Projekte' (selectedProjekt=null) NICHT
// leeren — das löscht die Sidebar-Counts und macht visuell den Eindruck,
// als seien alle Projekte verschwunden. Stattdessen alle Risiken nachladen.
watch(() => rb.selectedProjekt, async (name) => {
  if (name) {
    await rb.fetchRisikenForProjekt(name)
  } else {
    await rb.fetchRisiken()
  }
}, { immediate: false })

onMounted(async () => {
  await Promise.all([
    rb.fetchFrameworks(),
    rb.fetchProjekte(),
  ])
  // #1398: Deep-Link via ?projekt=<name> (z. B. aus CRA „Verknüpfte Bewertung öffnen")
  const proj = (route.query.projekt || '') as string
  if (proj && rb.projekte.find(p => p.name === proj)) {
    rb.selectedProjekt = proj
  }
  if (rb.selectedProjekt) {
    await rb.fetchRisikenForProjekt(rb.selectedProjekt)
  }
  // Issue #433: Wenn ?neu=<firma> via Deep-Link aus FirmenView → direkt
  // Anlage-Form oeffnen mit dem Firmen vorausgewaehlt.
  const neuFirma = (route.query.neu || '') as string
  if (neuFirma) {
    if (firmenStore.firmen.length === 0) await firmenStore.fetchFirmen()
    newProjektForm.value = {
      name: '',
      framework: 'STRIDE',
      beschreibung: '',
      unternehmen: neuFirma,
    }
    creatingProjekt.value = true
    onFirmaChanged()
  }
  // Issue #433: ?projekt=<name> Deep-Link → direkt auf das Projekt selektieren
  const projektQuery = (route.query.projekt || '') as string
  if (projektQuery) {
    rb.selectedProjekt = projektQuery
  }
})
</script>

<style scoped>
.rb-view {
  max-width: 1400px;
}

.project-name { margin: 0; font-size: 16px; flex: 1; color: var(--color-text-primary); }
.project-company { font-weight: 400; color: var(--color-text-secondary); font-size: 13px; }
.cra-link-badge {
  display: inline-flex; align-items: center; gap: 4px;
  background: #e3f2fd; color: #1565c0; border: 1px solid #90caf9;
  border-radius: 12px; padding: 3px 10px; font-size: 12px;
  text-decoration: none; white-space: nowrap;
}
.cra-link-badge:hover { background: #bbdefb; }
.btn-danger-mini {
  background: #ffebee; color: #c62828; border: 1px solid #ef5350;
  padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;
}
.btn-danger-mini:hover { background: #ffcdd2; }

.alert-error {
  background: #ffebee;
  color: #c62828;
  border: 1px solid #ef5350;
  padding: 10px;
  border-radius: 4px;
  margin-bottom: 12px;
}

.empty-state,
.form-card {
  background: white;
  padding: 32px;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  text-align: center;
}

.form-card {
  text-align: left;
  max-width: 600px;
}

.empty-state h3,
.form-card h3 {
  margin: 0 0 12px;
}

.empty-state p {
  color: #888;
  margin-bottom: 20px;
}

.form-row {
  margin-bottom: 12px;
}

.form-row label {
  display: block;
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 4px;
}

.form-row input,
.form-row select,
.form-row textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 13px;
}

.hint {
  font-size: 12px;
  color: #888;
}

.form-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 16px;
}

.tab-content { padding: 8px 0; }

/* Dashboard */
.dashboard {
  display: grid;
  grid-template-columns: 2fr repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.dash-card {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 12px 16px;
}

.dash-card.framework-info {
  background: #e3f2fd;
  border-color: var(--color-primary);
}

.dash-card.critical {
  border-left: 4px solid #d32f2f;
}

.dash-card.high {
  border-left: 4px solid #ff9800;
}

.dash-card.resolved {
  border-left: 4px solid #2e7d32;
}

.dash-label {
  font-size: 11px;
  text-transform: uppercase;
  color: #888;
  letter-spacing: 0.5px;
}

.dash-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-primary);
}

.dash-sub {
  font-size: 11px;
  color: #666;
  margin-top: 4px;
}

/* Toolbar */
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.search,
.filter {
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 13px;
}

.search {
  flex: 1;
  min-width: 200px;
}

.export-group {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

/* Risk-Liste */
.risk-list {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  overflow: hidden;
}

.risk-list table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.risk-list th {
  background: #f5f5f5;
  text-align: left;
  padding: 10px;
  font-weight: 600;
  border-bottom: 1px solid var(--color-border);
}

.risk-list tbody tr {
  cursor: pointer;
  transition: background 0.1s;
}

.risk-list tbody tr:hover {
  background: #f5f5f5;
}

.risk-list tbody tr.resolved {
  opacity: 0.5;
}

.risk-list td {
  padding: 8px 10px;
  border-bottom: 1px solid #f0f0f0;
}

.name-cell {
  display: flex;
  flex-direction: column;
}

.name-cell .desc {
  color: #888;
  font-size: 11px;
  margin-top: 2px;
}

.level-badge {
  padding: 2px 10px;
  border-radius: 3px;
  color: white;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.status-pill {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}

.status-pill.open {
  background: #fff3e0;
  color: #e65100;
}

.status-pill.resolved {
  background: #e8f5e9;
  color: #2e7d32;
}

.action-cell {
  display: flex;
  gap: 4px;
}

.btn-small,
.btn-danger-small {
  padding: 3px 8px;
  border: 1px solid var(--color-border);
  background: white;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
}

.btn-danger-small {
  color: #d32f2f;
  border-color: #d32f2f;
}

.empty {
  padding: 40px;
  text-align: center;
  color: #888;
}

.btn-primary,
.btn-secondary {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:disabled {
  opacity: 0.6;
}

.btn-secondary {
  background: #e0e0e0;
  color: #333;
}

.muted {
  color: #888;
  font-size: 12px;
}

/* Audit-Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  max-width: 800px;
  width: 90%;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border);
}

.modal-body {
  padding: 16px 20px;
  overflow-y: auto;
}

.modal-footer {
  padding: 12px 20px;
  border-top: 1px solid var(--color-border);
}

.btn-close {
  background: none;
  border: none;
  font-size: 22px;
  color: #999;
  cursor: pointer;
}

.audit-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.audit-table th {
  background: #f5f5f5;
  padding: 6px 10px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
}

.audit-table td {
  padding: 5px 10px;
  border-bottom: 1px solid #f0f0f0;
}
</style>
