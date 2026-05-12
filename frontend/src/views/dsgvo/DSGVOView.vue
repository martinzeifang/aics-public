<template>
  <div class="dsgvo-view">
    <div class="header">
      <h2>DSGVO – Datenschutz-Grundverordnung</h2>
      <p>Verordnung (EU) 2016/679 · 36 Anforderungen in 6 Kapiteln · 0-5-Bewertung mit Gewichtung</p>
      <button class="help-btn" @click="helpOpen = true" title="Erläuterung der Kategorien">
        ❓ Hilfe
      </button>
    </div>

    <div v-if="store.error" class="alert alert-error">{{ store.error }}</div>

    <div v-if="!store.selectedProjektObj && !creating" class="empty-state">
      <h3>{{ store.projekte.length === 0 ? 'Noch kein DSGVO-Projekt' : 'Projekt wählen' }}</h3>
      <p v-if="store.projekte.length > 0">Wähle ein Projekt aus der Liste oder lege ein neues an.</p>
      <p v-else>Lege ein neues DSGVO-Projekt an, um zu beginnen.</p>
      <div v-if="store.projekte.length > 0" class="proj-list">
        <button v-for="p in store.projekte" :key="p.name"
                class="proj-tile" @click="store.selectedProjekt = p.name">
          <strong>{{ p.name }}</strong>
          <span>{{ p.unternehmen }}</span>
        </button>
      </div>
      <button class="btn-primary" @click="startNew">+ Neues DSGVO-Projekt</button>
    </div>

    <div v-else-if="creating" class="form-card">
      <h3>Neues DSGVO-Projekt</h3>
      <div class="form-row">
        <label>Projektname *</label>
        <input v-model="newForm.name" placeholder="z.B. Mein Unternehmen DSGVO-Audit" />
      </div>
      <div class="form-row">
        <label>Unternehmen</label>
        <input v-model="newForm.unternehmen" />
      </div>
      <div class="form-row">
        <label>Organisationstyp</label>
        <select v-model="newForm.organisationstyp">
          <option value="verantwortlicher">Verantwortlicher</option>
          <option value="auftragsverarbeiter">Auftragsverarbeiter</option>
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
      <!-- Projekt-Auswahl -->
      <div class="proj-selector">
        <select v-model="store.selectedProjekt">
          <option v-for="p in store.projekte" :key="p.name" :value="p.name">
            {{ p.name }} — {{ p.unternehmen }}
          </option>
        </select>
        <button class="btn-secondary" @click="startNew">+ Neues Projekt</button>
        <button class="btn-danger-mini" @click="confirmDeleteProjekt" title="Projekt löschen">🗑️ Löschen</button>
      </div>

      <!-- Tab-Navigation -->
      <div class="tabs">
        <button v-for="t in tabs" :key="t.id"
                :class="['tab-btn', { active: activeTab === t.id }]"
                @click="activeTab = t.id">{{ t.label }}</button>
      </div>

    <template v-if="activeTab === 'anforderungen'">
      <!-- Dashboard -->
      <div class="dashboard">
        <div class="gauge-card">
          <MaturityGauge
            :percent="store.reifegrad?.gesamt_pct ?? 0"
            :ampel="store.reifegrad?.ampel"
            label="Gesamt-Reifegrad"
          />
          <div class="gauge-stats">
            <div>{{ store.reifegrad?.bewertete_count ?? 0 }} / {{ store.reifegrad?.gesamt_count ?? 0 }} bewertet</div>
            <div>{{ store.anforderungen.length }} Anforderungen</div>
          </div>
        </div>

        <div class="chapters-grid">
          <div
            v-for="(pct, kap) in (store.reifegrad?.kapitel_pct || {})"
            :key="kap"
            class="chapter-card"
            :style="{ borderLeftColor: kapitelColor(String(kap)) }"
            @click="filterKapitel = String(kap)"
          >
            <div class="chap-id">{{ kap }}</div>
            <div class="chap-title">{{ kapitelTitle(String(kap)) }}</div>
            <div class="chap-pct" :style="{ color: kapitelColor(String(kap)) }">{{ Math.round(pct) }}%</div>
            <div class="chap-bar">
              <div class="chap-bar-fill" :style="{ width: pct + '%', background: kapitelColor(String(kap)) }"></div>
            </div>
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
            :endpoint="`/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/fragebogen/import`"
            label="⬆️ Import"
            @imported="onImported"
          />
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
              <td>
                <span class="kapitel-tag" :style="{ background: kapitelColor(r.kapitel), color: '#fff' }">
                  {{ r.kapitel }}
                </span>
              </td>
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

    <!-- TOM-Tab -->
    <template v-if="activeTab === 'tom'">
      <div class="generator-card">
        <h3>🔒 TOM-Entwurf (Art. 32 DSGVO)</h3>
        <p>Generiert einen vollständigen Entwurf der Technischen und Organisatorischen Maßnahmen (TOM) als Word-Dokument auf Basis der Bewertungen aus dem Anforderungs-Tab.</p>
        <div class="tom-list">
          <div v-for="t in tomAbschnitte" :key="t.id" class="tom-item">
            <strong>{{ t.id }}</strong> – {{ t.titel }}
            <span class="muted">({{ t.untertitel }})</span>
          </div>
        </div>
        <div v-if="tomDraft" class="ai-draft-info">
          <strong>🤖 KI-Draft vorhanden</strong> · {{ Object.keys(tomDraft.payload?.abschnitte || {}).length }} Abschnitte ·
          <span class="muted">Stand: {{ formatDate(tomDraft.updated_at) }}</span>
          <details class="mt-1">
            <summary>Vorschau</summary>
            <div v-for="(a, id) in (tomDraft.payload?.abschnitte || {})" :key="id" class="ai-section">
              <strong>{{ id }}</strong>
              <ul>
                <li v-for="m in (a.vorhandene_massnahmen || [])" :key="m">✓ {{ m }}</li>
                <li v-for="g in (a.luecken || [])" :key="g" class="gap">⚠ Lücke: {{ g }}</li>
              </ul>
            </div>
          </details>
        </div>
        <div class="action-row">
          <button class="btn-secondary" @click="onTomGeneratePrompt" :disabled="aiBusy">
            {{ aiBusy ? 'Lädt…' : '🤖 KI-Prompt erstellen (aus Kunden-Dokumenten)' }}
          </button>
          <DownloadButton
            :endpoint="`/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt || '')}/tom/export`"
            label="📝 TOM-Entwurf herunterladen (DOCX)"
            variant="primary"
          />
        </div>
      </div>
    </template>

    <!-- Datenschutzerklärung-Tab -->
    <template v-if="activeTab === 'privacy'">
      <div class="generator-card">
        <h3>📜 Datenschutzerklärung</h3>
        <p>Erstelle einen Entwurf einer Website/App-Datenschutzerklärung. Fülle die Felder aus, ungesetzte Felder werden im Dokument als <code>[PLATZHALTER]</code> markiert.</p>

        <div class="privacy-form" v-if="privacyFelder">
          <details v-for="grp in privacyGruppen" :key="grp" class="form-group" :open="grp === 'Verantwortlicher'">
            <summary>{{ grp }}</summary>
            <div class="form-grid">
              <div v-for="f in feldsByGruppe(grp)" :key="f.key" class="form-cell">
                <label>{{ f.label }}<span v-if="f.required" class="req">*</span></label>
                <textarea v-if="f.key === 'rechtsgrundlage_beschreibung' || f.key === 'drittland_beschreibung' || f.key === 'speicherdauer_sonstiges' || f.key === 'zwecke_sonstiges'"
                          v-model="privacyIntake[f.key]" rows="2"></textarea>
                <select v-else-if="f.type === 'bool'" v-model="privacyIntake[f.key]">
                  <option :value="undefined">— wählen —</option>
                  <option :value="true">Ja</option>
                  <option :value="false">Nein</option>
                </select>
                <div v-else-if="f.type === 'checklist'" class="checklist">
                  <label v-for="opt in f.optionen" :key="opt[0]" class="check-row">
                    <input type="checkbox" :value="opt[0]"
                           :checked="(privacyIntake[f.key] || []).includes(opt[0])"
                           @change="onZweckToggle(f.key, opt[0], $event)" />
                    {{ opt[1] }}
                  </label>
                </div>
                <input v-else v-model="privacyIntake[f.key]" :placeholder="f.tip || ''" />
                <small v-if="f.tip && f.type !== 'checklist'" class="hint">{{ f.tip }}</small>
              </div>
            </div>
          </details>
        </div>

        <div class="action-row">
          <button class="btn-secondary" @click="onPrivacyGeneratePrompt" :disabled="aiBusy">
            {{ aiBusy ? 'Lädt…' : '🤖 KI-Vorbefüllung (aus Kunden-Dokumenten)' }}
          </button>
          <button class="btn-secondary" @click="savePrivacyIntake">💾 Speichern</button>
          <DownloadButton
            :endpoint="`/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt || '')}/privacy/export`"
            label="📜 Datenschutzerklärung herunterladen (DOCX)"
            variant="primary"
          />
          <span v-if="privacyMsg" class="hint" :class="{ ok: privacyMsgOk }">{{ privacyMsg }}</span>
        </div>
      </div>
    </template>

    <!-- Schulungs-Tab -->
    <template v-if="activeTab === 'training'">
      <div class="generator-card">
        <h3>🎓 Jahresschulung</h3>
        <p>Generiert ein Schulungs-Skript inkl. Quiz für ausgewählte Zielgruppen.</p>

        <div class="training-zielgruppen">
          <h4>Zielgruppen</h4>
          <label v-for="(meta, key) in (trainingOutline?.zielgruppen || {})" :key="key" class="check-row">
            <input type="checkbox" :value="key"
                   :checked="trainingZielgruppen.includes(String(key))"
                   @change="onZielgruppeToggle(String(key), $event)" />
            <strong :style="{ color: meta.farbe }">{{ meta.label }}</strong>
            <span class="muted">— {{ meta.beschreibung }}</span>
          </label>
        </div>

        <div class="action-row">
          <button class="btn-primary" @click="downloadTraining" :disabled="trainingBusy">
            {{ trainingBusy ? 'Lädt…' : '🎓 Schulung herunterladen (DOCX)' }}
          </button>
          <span v-if="trainingMsg" class="hint" :class="{ err: trainingErr }">{{ trainingMsg }}</span>
        </div>
      </div>
    </template>
    </template>

    <!-- Editor (Details + KI-Bewertung) -->
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
          api-base="/dsgvo"
          @saved="onActionSaved"
          @error="(msg) => store.error = msg"
        />
      </template>
    </RequirementEditor>

    <!-- KI-Prompt-Modal -->
    <div v-if="aiPromptModal.open" class="modal-overlay" @click.self="aiPromptModal.open = false">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>🤖 ChatGPT-Prompt — {{ aiPromptModal.kind === 'tom' ? 'TOM-Entwurf' : 'Datenschutzerklärung' }}</h3>
          <button class="btn-close" @click="aiPromptModal.open = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">
            <strong>Kunde:</strong> {{ aiPromptModal.kunde || '—' }} ·
            <strong>Evidence-Auszüge:</strong> {{ aiPromptModal.evidence_count }}
          </p>
          <div v-if="aiPromptModal.evidence_count === 0" class="alert alert-warn">
            ⚠️ Keine Kunden-Dokumente vorhanden. Lade zuerst unter <em>Kunden → Evidence</em>
            für "{{ aiPromptModal.kunde }}" PDFs/DOCXs hoch, damit ChatGPT konkretere Inhalte
            generieren kann.
          </div>
          <button class="btn-mini" @click="copyToClipboard(aiPromptModal.prompt)">📋 Prompt kopieren</button>
          <textarea readonly :value="aiPromptModal.prompt" rows="14" class="prompt-textarea"></textarea>

          <hr style="margin: 16px 0;" />
          <p class="hint">Kopiere den Prompt in ChatGPT, dann füge die JSON-Antwort hier ein:</p>
          <textarea v-model="aiResponseRaw" rows="10" class="prompt-textarea"
                    placeholder="ChatGPT-Antwort hier einfügen…"></textarea>
          <span v-if="aiImportMsg" class="hint" :class="{ ok: aiImportOk, err: !aiImportOk }">{{ aiImportMsg }}</span>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="aiPromptModal.open = false">Schließen</button>
          <button class="btn-primary" @click="onAiImport" :disabled="!aiResponseRaw || aiBusy">
            {{ aiBusy ? 'Importiere…' : '✓ Antwort übernehmen' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Hilfe-Dialog -->
    <HelpDialog
      :open="helpOpen"
      title="DSGVO – Erläuterung der Kapitel"
      subtitle="Verordnung (EU) 2016/679 — Datenschutz-Grundverordnung"
      header-bg="#1565c0"
      :kapitel="store.constants?.kapitel"
      :bewertung-skala="store.constants?.bewertung_skala"
      @close="helpOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useDsgvoStore } from '../../stores/dsgvo'
import MaturityGauge from '../../components/shared/MaturityGauge.vue'
import RequirementEditor from '../../components/shared/RequirementEditor.vue'
import RequirementActions from '../../components/shared/RequirementActions.vue'
import ImportButton from '../../components/shared/ImportButton.vue'
import DownloadButton from '../../components/shared/DownloadButton.vue'
import HelpDialog from '../../components/shared/HelpDialog.vue'
import apiClient from '../../api/client'

const store = useDsgvoStore()
const stripApi = (u: string): string => u.replace(/^\/api/, '')

const helpOpen = ref(false)
const creating = ref(false)

const tabs = [
  { id: 'anforderungen', label: '📋 Anforderungen' },
  { id: 'tom', label: '🔒 TOM' },
  { id: 'privacy', label: '📜 Datenschutzerklärung' },
  { id: 'training', label: '🎓 Schulung' },
]
const activeTab = ref<'anforderungen' | 'tom' | 'privacy' | 'training'>('anforderungen')

// TOM
const tomAbschnitte = ref<any[]>([])
const loadTom = async () => {
  if (tomAbschnitte.value.length) return
  try {
    const res = await apiClient.get('/dsgvo/tom/abschnitte')
    tomAbschnitte.value = res.data
  } catch { /* ignore */ }
}

// Privacy intake
const privacyFelder = ref<any[] | null>(null)
const privacyGruppen = ref<string[]>([])
const privacyIntake = ref<Record<string, any>>({})
const privacyMsg = ref('')
const privacyMsgOk = ref(false)
const feldsByGruppe = (grp: string) =>
  (privacyFelder.value || []).filter(f => f.group === grp)
const loadPrivacySchema = async () => {
  if (privacyFelder.value) return
  try {
    const res = await apiClient.get('/dsgvo/privacy/intake-schema')
    privacyFelder.value = res.data.felder
    privacyGruppen.value = res.data.gruppen
  } catch { /* ignore */ }
}
const loadPrivacyIntake = async () => {
  if (!store.selectedProjekt) return
  try {
    const res = await apiClient.get(`/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/privacy/intake`)
    privacyIntake.value = res.data.intake || {}
  } catch { /* ignore */ }
}
const savePrivacyIntake = async () => {
  if (!store.selectedProjekt) return
  try {
    await apiClient.put(`/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/privacy/intake`,
      privacyIntake.value)
    privacyMsgOk.value = true
    privacyMsg.value = '✓ Gespeichert.'
    setTimeout(() => privacyMsg.value = '', 3000)
  } catch (e: any) {
    privacyMsgOk.value = false
    privacyMsg.value = `Fehler: ${e?.response?.data?.error || e.message}`
  }
}
const onZweckToggle = (key: string, value: string, e: Event) => {
  const checked = (e.target as HTMLInputElement).checked
  const arr = (privacyIntake.value[key] || []) as string[]
  if (checked && !arr.includes(value)) arr.push(value)
  else if (!checked && arr.includes(value)) arr.splice(arr.indexOf(value), 1)
  privacyIntake.value[key] = [...arr]
}

// KI-Generator (TOM + Privacy)
const aiBusy = ref(false)
const aiResponseRaw = ref('')
const aiImportMsg = ref('')
const aiImportOk = ref(false)
const aiPromptModal = ref<{
  open: boolean
  kind: 'tom' | 'privacy'
  prompt: string
  kunde: string
  evidence_count: number
}>({ open: false, kind: 'tom', prompt: '', kunde: '', evidence_count: 0 })

const tomDraft = ref<any | null>(null)

const formatDate = (s?: string | null): string => {
  if (!s) return '—'
  try { return new Date(s).toLocaleString('de-DE') } catch { return s }
}

const loadTomDraft = async () => {
  if (!store.selectedProjekt) return
  try {
    const res = await apiClient.get(
      `/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/tom/ai-draft`,
    )
    tomDraft.value = res.data?.draft || null
  } catch { tomDraft.value = null }
}

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    aiImportMsg.value = '✓ In Zwischenablage kopiert.'
    aiImportOk.value = true
    setTimeout(() => aiImportMsg.value = '', 3000)
  } catch {
    aiImportMsg.value = 'Konnte nicht kopieren — Text manuell markieren.'
    aiImportOk.value = false
  }
}

const onTomGeneratePrompt = async () => {
  if (!store.selectedProjekt) return
  aiBusy.value = true
  aiResponseRaw.value = ''
  aiImportMsg.value = ''
  try {
    const res = await apiClient.post(
      `/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/tom/ai-prompt`,
      {},
    )
    aiPromptModal.value = {
      open: true,
      kind: 'tom',
      prompt: res.data.prompt,
      kunde: res.data.kunde || '',
      evidence_count: res.data.evidence_count || 0,
    }
  } catch (e: any) {
    aiImportMsg.value = `Fehler: ${e?.response?.data?.error || e.message}`
    aiImportOk.value = false
  } finally {
    aiBusy.value = false
  }
}

const onPrivacyGeneratePrompt = async () => {
  if (!store.selectedProjekt) return
  aiBusy.value = true
  aiResponseRaw.value = ''
  aiImportMsg.value = ''
  try {
    const res = await apiClient.post(
      `/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/privacy/ai-prompt`,
      {},
    )
    aiPromptModal.value = {
      open: true,
      kind: 'privacy',
      prompt: res.data.prompt,
      kunde: res.data.kunde || '',
      evidence_count: res.data.evidence_count || 0,
    }
  } catch (e: any) {
    aiImportMsg.value = `Fehler: ${e?.response?.data?.error || e.message}`
    aiImportOk.value = false
  } finally {
    aiBusy.value = false
  }
}

const onAiImport = async () => {
  if (!store.selectedProjekt || !aiResponseRaw.value) return
  aiBusy.value = true
  aiImportMsg.value = ''
  try {
    const path = aiPromptModal.value.kind === 'tom'
      ? `/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/tom/ai-import`
      : `/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/privacy/ai-import`
    const res = await apiClient.post(path, { raw: aiResponseRaw.value, merge: true })
    aiImportOk.value = true
    if (aiPromptModal.value.kind === 'tom') {
      aiImportMsg.value = `✓ ${res.data.abschnitte_count} Abschnitte importiert. TOM-DOCX nutzt jetzt KI-Inhalte.`
      await loadTomDraft()
    } else {
      aiImportMsg.value = `✓ ${res.data.fields_set} Felder befüllt (${res.data.missing.length} Pflichtfelder noch leer).`
      await loadPrivacyIntake()
    }
    setTimeout(() => { aiPromptModal.value.open = false; aiResponseRaw.value = '' }, 1800)
  } catch (e: any) {
    aiImportOk.value = false
    aiImportMsg.value = `Fehler: ${e?.response?.data?.error || e.message}`
  } finally {
    aiBusy.value = false
  }
}

// Training
const trainingOutline = ref<any | null>(null)
const trainingZielgruppen = ref<string[]>(['alle'])
const trainingBusy = ref(false)
const trainingMsg = ref('')
const trainingErr = ref(false)
const loadTrainingOutline = async () => {
  if (trainingOutline.value) return
  try {
    const res = await apiClient.get('/dsgvo/training/outline')
    trainingOutline.value = res.data
  } catch { /* ignore */ }
}
const onZielgruppeToggle = (key: string, e: Event) => {
  const checked = (e.target as HTMLInputElement).checked
  if (checked && !trainingZielgruppen.value.includes(key)) {
    trainingZielgruppen.value.push(key)
  } else if (!checked) {
    trainingZielgruppen.value = trainingZielgruppen.value.filter(z => z !== key)
  }
}
const downloadTraining = async () => {
  if (!store.selectedProjekt) return
  trainingBusy.value = true
  trainingMsg.value = ''
  trainingErr.value = false
  try {
    const res = await apiClient.post(
      `/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/training/export`,
      { zielgruppen: trainingZielgruppen.value },
      { responseType: 'blob', timeout: 120000 },
    )
    const blob = res.data as Blob
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `Schulung_${store.selectedProjekt}.docx`
    a.click()
    URL.revokeObjectURL(url)
    trainingMsg.value = '✓ Heruntergeladen.'
    setTimeout(() => trainingMsg.value = '', 3000)
  } catch (e: any) {
    trainingErr.value = true
    trainingMsg.value = `Fehler: ${e?.response?.data?.error || e.message}`
  } finally {
    trainingBusy.value = false
  }
}

// Lazy-load tab data
watch(activeTab, async (t) => {
  if (t === 'tom') { await loadTom(); await loadTomDraft() }
  if (t === 'privacy') { await loadPrivacySchema(); await loadPrivacyIntake() }
  if (t === 'training') await loadTrainingOutline()
})
const newForm = ref({ name: '', unternehmen: '', organisationstyp: 'verantwortlicher', beschreibung: '' })
const editingReq = ref<any | null>(null)
const searchQuery = ref('')
const filterKapitel = ref('')
const filterStatus = ref<'all' | 'pending' | 'partial' | 'complete'>('all')

const onImported = async () => {
  if (!store.selectedProjekt) return
  await store.fetchAnforderungen(store.selectedProjekt)
  await store.fetchReifegrad(store.selectedProjekt)
}

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

const kapitelColor = (id: string): string => {
  return store.constants?.kapitel?.[id]?.farbe || '#1565c0'
}
const kapitelTitle = (id: string): string => {
  return store.constants?.kapitel?.[id]?.titel || id
}

const SCORE_COLORS = ['#9e9e9e', '#c62828', '#e65100', '#f57f17', '#558b2f', '#2e7d32']
const scoreColor = (s: number) => SCORE_COLORS[s] || '#9e9e9e'
const statusLabel = (s: string): string => {
  if (s === 'complete') return 'Vollständig'
  if (s === 'partial') return 'Teilweise'
  return 'Ausstehend'
}

const exportUrl = (fmt: string): string => {
  if (!store.selectedProjekt) return '#'
  return `/api/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/report?format=${fmt}`
}

const confirmDeleteProjekt = async () => {
  if (!store.selectedProjekt) return
  if (!confirm(`DSGVO-Projekt "${store.selectedProjekt}" wirklich löschen?\n\nAlle Bewertungen, Intake-Daten und KI-Drafts gehen verloren.`)) return
  await store.deleteProjekt(store.selectedProjekt)
}

const startNew = () => {
  newForm.value = { name: '', unternehmen: '', organisationstyp: 'verantwortlicher', beschreibung: '' }
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

const editAnforderung = (req: any) => {
  editingReq.value = req
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
  await store.fetchConstants()
  await store.fetchProjekte()
  if (!store.selectedProjekt && store.projekte.length > 0) {
    store.selectedProjekt = store.projekte[0].name
  }
  if (store.selectedProjekt) await reloadProjekt()
})
</script>

<style scoped>
.dsgvo-view { max-width: 1400px; }

.header {
  display: flex; align-items: flex-end; gap: 16px;
  margin-bottom: 16px; padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}
.header h2 { margin: 0; font-size: 22px; flex: 1; }
.header p { margin: 2px 0 0 0; color: var(--color-text-secondary); font-size: 13px; flex: 2; }
.help-btn {
  background: var(--color-background); color: var(--color-primary);
  border: 1px solid var(--color-border); padding: 6px 14px; border-radius: 4px;
  cursor: pointer; font-size: 14px;
}
.help-btn:hover { background: var(--color-border); }

.alert-error {
  background: #ffebee; color: #c62828; padding: 10px; border-radius: 4px;
  margin-bottom: 12px; border: 1px solid #ef5350;
}

.empty-state, .form-card {
  background: var(--color-surface); padding: 32px; border-radius: 8px;
  border: 1px solid var(--color-border);
}
.empty-state { text-align: center; }
.empty-state h3 { margin: 0 0 12px; }
.empty-state p { color: var(--color-text-secondary); margin-bottom: 20px; }

.proj-list {
  display: flex; flex-wrap: wrap; gap: 12px;
  justify-content: center; margin-bottom: 24px;
}
.proj-tile {
  background: var(--color-background); border: 1px solid var(--color-border);
  padding: 12px 20px; border-radius: 6px; cursor: pointer;
  display: flex; flex-direction: column; gap: 4px; min-width: 200px;
}
.proj-tile:hover { background: var(--color-border); border-color: var(--color-primary); }
.proj-tile strong { font-size: 15px; }
.proj-tile span { font-size: 12px; color: var(--color-text-secondary); }

.btn-danger-mini {
  background: #ffebee; color: #c62828; border: 1px solid #ef5350;
  padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;
}
.btn-danger-mini:hover { background: #ffcdd2; }

.proj-selector {
  display: flex; gap: 8px; align-items: center; margin-bottom: 16px;
}
.proj-selector select {
  flex: 1; padding: 8px; border: 1px solid var(--color-border); border-radius: 4px;
}

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
  background: var(--color-surface); border: 1px solid var(--color-border);
  padding: 16px; border-radius: 8px;
  display: flex; flex-direction: column; align-items: center;
}
.gauge-stats { margin-top: 12px; font-size: 13px; color: var(--color-text-secondary); text-align: center; }
.chapters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.chapter-card {
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-left: 4px solid;
  padding: 12px 14px; border-radius: 6px; cursor: pointer;
  transition: transform 150ms, box-shadow 150ms;
}
.chapter-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.chap-id {
  font-family: monospace; font-size: 12px;
  font-weight: 700; color: var(--color-text-secondary);
}
.chap-title { font-size: 14px; font-weight: 600; margin: 4px 0; }
.chap-pct { font-size: 22px; font-weight: 700; }
.chap-bar {
  background: var(--color-background); height: 6px; border-radius: 3px;
  overflow: hidden; margin-top: 6px;
}
.chap-bar-fill { height: 100%; transition: width 300ms; }

.anf-toolbar {
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
  background: var(--color-surface); padding: 10px; border-radius: 6px;
  border: 1px solid var(--color-border); margin-bottom: 8px;
}
.search { flex: 1; min-width: 200px; padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; }
.filter { padding: 6px 8px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; }
.info { font-size: 12px; color: var(--color-text-secondary); }
.export-group { display: flex; gap: 6px; align-items: center; margin-left: auto; }
.export-group span { font-size: 12px; color: var(--color-text-secondary); }
.export-btn { font-size: 12px; }

.anf-list { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden; }
.anf-list table { width: 100%; border-collapse: collapse; }
.anf-list th {
  background: var(--color-background); text-align: left;
  padding: 8px 10px; font-size: 12px; font-weight: 600; border-bottom: 1px solid var(--color-border);
}
.anf-list td {
  padding: 8px 10px; border-bottom: 1px solid var(--color-border); font-size: 13px;
}
.anf-list tbody tr { cursor: pointer; }
.anf-list tbody tr:hover { background: var(--color-background); }
.title-cell { max-width: 500px; }
code { background: var(--color-background); padding: 2px 6px; border-radius: 3px; font-size: 12px; }
.kapitel-tag {
  font-family: monospace; font-size: 11px;
  padding: 2px 8px; border-radius: 3px; font-weight: 600;
}
.score-pill {
  display: inline-block; min-width: 26px; padding: 2px 8px;
  border-radius: 12px; color: #fff; text-align: center; font-weight: 700;
}
.status-pill { font-size: 12px; padding: 2px 10px; border-radius: 12px; font-weight: 600; }
.status-pill.pending { background: #ffebee; color: #c62828; }
.status-pill.partial { background: #fff3e0; color: #e65100; }
.status-pill.complete { background: #e8f5e9; color: #2e7d32; }
.empty { padding: 32px; text-align: center; color: var(--color-text-secondary); }

.btn-primary {
  background: var(--color-primary); color: #fff; border: none;
  padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: 500;
}
.btn-primary:hover { background: var(--color-primary-dark); }
.btn-secondary {
  background: var(--color-background); color: var(--color-primary);
  border: 1px solid var(--color-border);
  padding: 8px 16px; border-radius: 4px; cursor: pointer;
}
.btn-secondary:hover { background: var(--color-border); }

.tabs {
  display: flex; gap: 0; border-bottom: 2px solid var(--color-border);
  margin-bottom: 16px;
}
.tab-btn {
  background: none; border: none; padding: 10px 20px;
  cursor: pointer; font-size: 14px; color: var(--color-text-secondary);
  border-bottom: 3px solid transparent; margin-bottom: -2px;
}
.tab-btn:hover { color: var(--color-primary); }
.tab-btn.active {
  color: var(--color-primary); border-bottom-color: var(--color-primary); font-weight: 600;
}

.generator-card {
  background: var(--color-surface); border: 1px solid var(--color-border);
  padding: 24px; border-radius: 8px;
}
.generator-card h3 { margin: 0 0 8px; }
.generator-card > p { color: var(--color-text-secondary); margin: 0 0 16px; }

.tom-list { margin: 12px 0; }
.tom-item { padding: 6px 12px; background: var(--color-background); margin-bottom: 4px; border-radius: 4px; }
.muted { color: var(--color-text-secondary); font-size: 13px; }

.privacy-form { margin: 16px 0; }
.form-group { background: var(--color-background); border-radius: 6px; padding: 8px 14px; margin-bottom: 8px; }
.form-group summary { font-weight: 600; cursor: pointer; padding: 4px 0; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding-top: 12px; }
.form-cell { display: flex; flex-direction: column; gap: 4px; }
.form-cell label { font-size: 13px; font-weight: 600; }
.form-cell label .req { color: #c62828; }
.form-cell input, .form-cell select, .form-cell textarea {
  padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px;
  background: var(--color-surface); color: var(--color-text-primary);
}
.form-cell .hint { font-size: 11px; color: var(--color-text-secondary); }
.checklist { display: flex; flex-direction: column; gap: 4px; }
.check-row { display: flex; align-items: center; gap: 8px; font-size: 14px; cursor: pointer; padding: 4px 0; }
.check-row input[type="checkbox"] { margin: 0; }

.training-zielgruppen { margin-bottom: 16px; }
.training-zielgruppen h4 { margin: 0 0 8px; }

.action-row {
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
  padding-top: 16px; border-top: 1px solid var(--color-border); margin-top: 16px;
}
.hint.ok { color: var(--color-success); }
.hint.err { color: var(--color-error); }
</style>
