<template>
  <div class="firmen-view">
    <div v-if="!firmen.selectedFirma && !creating" class="empty-state">
      <h2>Firmenverwaltung</h2>
      <p>Wählen Sie links einen Firmen aus oder legen Sie einen neuen an.</p>
      <div class="empty-actions">
        <button class="btn-primary" @click="startNew">+ Neuen Firmen anlegen</button>
        <button class="btn-secondary" @click="onImpressum">🌐 Aus Website-Impressum…</button>
        <button class="btn-secondary" @click="onShowDeleted">♻️ Gelöschte Firmen…</button>
        <ModuleHelpButton module="firmen" />
      </div>
    </div>

    <div v-else class="cockpit">
      <!-- Cockpit Header -->
      <div class="cockpit-header">
        <div class="cockpit-title">
          <h2>{{ creating ? 'Neuer Firma' : (form.name || 'Firma') }}</h2>
          <span v-if="!creating && form.company" class="cockpit-sub">{{ form.company }}</span>
        </div>
        <div class="cockpit-actions">
          <ModuleHelpButton module="firmen" />
          <button class="btn-secondary" @click="onImpressum">🌐 Aus Website…</button>
          <button class="btn-secondary" @click="onShowDeleted">♻️ Gelöschte Firmen</button>
          <button v-if="!creating" class="btn-danger-outline" @click="onDelete">Löschen</button>
        </div>
      </div>

      <div v-if="firmen.error" class="alert alert-error">{{ firmen.error }}</div>
      <div v-if="successMsg" class="alert alert-success">{{ successMsg }}</div>

      <!-- Stammdaten-Karte (kompakt, inline editierbar) -->
      <section class="card">
        <div class="card-head">
          <h3>Stammdaten</h3>
        </div>
        <div class="stamm-grid">
          <div class="form-row">
            <label>Firmen-Name *</label>
            <input
              v-model="form.name"
              :readonly="!creating"
              :class="{ readonly: !creating }"
              placeholder="z.B. Meine Firma GmbH"
            />
            <small v-if="creating" class="hint">
              Beim Anlegen werden in allen aktivierten Modulen Projekte mit diesem Namen erstellt.
            </small>
          </div>
          <div class="form-row">
            <label>Unternehmen</label>
            <input v-model="form.company" placeholder="z.B. Beispiel AG" />
          </div>
          <div class="form-row">
            <label>Berater / Verantwortlicher</label>
            <input v-model="form.advisor" />
          </div>
          <div class="form-row full">
            <label>Beschreibung</label>
            <textarea v-model="form.description" rows="2"></textarea>
          </div>
        </div>
      </section>

      <!-- Modul-Kacheln -->
      <section class="card">
        <div class="card-head">
          <h3>Module</h3>
          <button v-if="!creating && form.name" class="btn-small" type="button"
                  @click="onSyncProjekte" :disabled="syncing">
            {{ syncing ? '⏳ …' : '🔄 Projekte anlegen' }}
          </button>
        </div>
        <p v-if="syncResult" class="hint" :style="{ color: syncResult.error ? '#c62828' : '#2e7d32' }">
          {{ syncResult.message }}
        </p>
        <div class="tile-grid">
          <div v-for="m in moduleTiles" :key="m.key"
               class="tile" :class="{ active: m.enabled }">
            <label class="tile-toggle">
              <input type="checkbox" v-model="form.modules[m.key]" />
              <strong>{{ m.label }}</strong>
            </label>
            <small class="tile-desc">{{ m.desc }}</small>
            <div class="tile-foot">
              <span v-if="m.enabled" class="tile-status on">{{ m.statusLabel }}</span>
              <span v-else class="tile-status off">inaktiv</span>
              <router-link v-if="m.enabled && !creating && m.route" :to="m.route" class="tile-link">
                Öffnen →
              </router-link>
            </div>
          </div>
        </div>
      </section>

      <!-- Detail-Bereiche als Unter-Tabs -->
      <section class="card" v-if="!creating && form.name">
        <div class="subtabs">
          <button v-for="st in subTabs" :key="st.id"
                  :class="['subtab', { active: subTab === st.id }]"
                  @click="subTab = st.id">
            {{ st.label }}<span v-if="st.count !== undefined" class="subtab-count">{{ st.count }}</span>
          </button>
        </div>

        <!-- Sub: Risikobewertung-Projekte -->
        <div v-if="subTab === 'risiko'" class="subpanel">
          <p class="hint">Pro Firma mehrere Risikobewertungs-Projekte möglich (z. B. je Produkt/Service).</p>
          <table v-if="rbProjekte.length > 0" class="sub-table">
            <thead><tr><th>Projekt</th><th>Framework</th><th>Produkt</th><th>Risiken</th><th></th></tr></thead>
            <tbody>
              <tr v-for="p in rbProjekte" :key="p.name">
                <td><strong>{{ p.name }}</strong></td>
                <td>{{ p.framework }}</td>
                <td>{{ p.produkt || '—' }}</td>
                <td>{{ p.risiken_count }}</td>
                <td><router-link :to="`/risikobewertung?projekt=${encodeURIComponent(p.name)}`" class="btn-small">Öffnen →</router-link></td>
              </tr>
            </tbody>
          </table>
          <div v-else class="sub-empty">Noch keine Risikobewertungs-Projekte.</div>
          <div class="form-row">
            <label>Standard-Framework</label>
            <select v-model="form.rb_framework">
              <option v-for="fw in constants?.rb_frameworks || []" :key="fw" :value="fw">{{ fw }}{{ fwDescription(fw) }}</option>
            </select>
          </div>
          <router-link :to="`/risikobewertung?neu=${encodeURIComponent(form.name)}`" class="btn-secondary" style="display:inline-block;margin-top:8px;">
            + Risikobewertungs-Projekt anlegen
          </router-link>
        </div>

        <!-- Sub: Produkte + CRA -->
        <div v-if="subTab === 'produkte'" class="subpanel">
          <p class="hint">Mehrere Produkte pro Firma. Jedes Produkt erzeugt automatisch ein CRA-Projekt.</p>
          <table v-if="firmen.produkte.length > 0" class="sub-table">
            <thead><tr><th>Name</th><th>Klasse</th><th>Standard</th><th>CRA-Projekt</th><th></th></tr></thead>
            <tbody>
              <tr v-for="p in firmen.produkte" :key="p.id">
                <td>{{ p.name }}</td>
                <td>{{ produktklasseLabel(p.produktklasse) }}</td>
                <td>{{ p.is_default ? '★' : '' }}</td>
                <td>
                  <router-link v-if="craProjektFuerProdukt(p)" :to="`/cra?projekt=${encodeURIComponent(craProjektFuerProdukt(p))}`" class="btn-small">CRA öffnen →</router-link>
                  <span v-else class="muted">—</span>
                </td>
                <td class="action-cell">
                  <button class="btn-small" @click="onEditProdukt(p)">Bearbeiten</button>
                  <button class="btn-small" @click="onSetDefault(p)" :disabled="!!p.is_default">Als Standard</button>
                  <button class="btn-danger-small" @click="onDeleteProdukt(p)">Löschen</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="sub-empty">Keine Produkte. „+ Produkt" anlegen.</div>
          <button class="btn-secondary" @click="onAddProdukt" style="margin-top:8px;">+ Produkt</button>
        </div>

        <!-- Sub: Evidence -->
        <div v-if="subTab === 'evidence'" class="subpanel">
          <p class="hint">Dateien und Webseiten als Nachweis-Material für Bewertungen.</p>
          <table v-if="firmen.evidence.length > 0" class="sub-table">
            <thead><tr><th>Datei / URL</th><th>Typ</th><th>Schlagwörter</th><th></th></tr></thead>
            <tbody>
              <tr v-for="ev in firmen.evidence" :key="ev.id">
                <td>
                  <a v-if="ev.doc_kind === 'web' && ev.url" :href="safeUrl(ev.url)" target="_blank" rel="noopener noreferrer">{{ ev.filename }}</a>
                  <span v-else>{{ ev.filename }}</span>
                </td>
                <td>{{ ev.doc_type || ev.doc_kind || '—' }}</td>
                <td>{{ (ev.tags || []).join(', ') || '—' }}</td>
                <td class="action-cell">
                  <button class="btn-small" @click="onExtractEvidence(ev.id)">Extrahieren</button>
                  <button class="btn-danger-small" @click="onDeleteEvidence(ev.id)">Entfernen</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="sub-empty">Keine Nachweise.</div>
          <div class="evidence-actions">
            <label class="hint" style="display:flex;align-items:center;gap:6px;">Kategorie
              <select v-model="uploadDocType" class="evidence-cat">
                <option value="">— (allgemein)</option>
                <option value="technische_dokumentation">Technische Dokumentation</option>
                <option value="benutzerdokumentation">Benutzerdokumentation</option>
                <option value="sonstiges">Sonstiges</option>
              </select>
            </label>
            <input ref="fileInput" type="file" style="display:none" accept=".pdf,.docx,.txt,.md,.csv,.xlsx" @change="onFileChosen" />
            <button class="btn-secondary" @click="fileInput?.click()">+ Datei (PDF/DOCX …)</button>
            <button class="btn-secondary" @click="evidenceUrlOpen = true">+ URL</button>
          </div>
        </div>

        <!-- Sub: Gutachten -->
        <div v-if="subTab === 'gutachten'" class="subpanel">
          <p class="hint">Welche Frameworks werden in einem Gutachten geprüft?</p>
          <div class="checkbox-grid">
            <label v-for="fw in constants?.gutachten_frameworks || []" :key="fw" class="checkbox-row">
              <input type="checkbox" :value="fw" v-model="form.frameworks" />{{ fw }}
            </label>
          </div>
          <div class="form-row full" style="margin-top:10px;">
            <label>Prüfungsfokus</label>
            <textarea v-model="form.pruefungsfokus" rows="5" placeholder="Schwerpunkte für das Gutachten…"></textarea>
          </div>
          <div class="button-row">
            <button class="btn-secondary" @click="generateFokus">💡 Vorschlag generieren</button>
            <button class="btn-secondary" @click="form.pruefungsfokus = ''">Leeren</button>
          </div>
        </div>
      </section>

      <!-- Form-Aktionen -->
      <div class="form-actions">
        <button class="btn-primary" @click="onSave" :disabled="firmen.loading">
          {{ firmen.loading ? 'Speichert…' : '💾 Speichern' }}
        </button>
        <button class="btn-secondary" @click="onCancel">Abbrechen</button>
      </div>
    </div>

    <!-- Impressum-Dialog -->
    <ImpressumDialog
      v-if="impressumOpen"
      @apply="onImpressumApply"
      @cancel="impressumOpen = false"
    />

    <!-- Produkt-Dialog -->
    <ProduktDialog
      v-if="produktDialogOpen"
      :produkt="editingProdukt"
      :produktklassen="constants?.produktklassen || []"
      @save="onSaveProdukt"
      @cancel="produktDialogOpen = false"
    />

    <!-- Evidence-URL-Dialog -->
    <EvidenceURLDialog
      v-if="evidenceUrlOpen"
      @submit="onAddEvidenceUrl"
      @cancel="evidenceUrlOpen = false"
    />

    <!-- Gelöschte Firmen -->
    <DeletedFirmenDialog
      v-if="deletedDialogOpen"
      @cancel="deletedDialogOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import apiClient from '../../api/client'
import { safeUrl } from '../../utils/safeUrl'
import { useFirmenStore, type Firma, type Produkt } from '../../stores/firmen'
import ProduktDialog from './dialogs/ProduktDialog.vue'
import EvidenceURLDialog from './dialogs/EvidenceURLDialog.vue'
import ModuleHelpButton from '../../components/shared/ModuleHelpButton.vue'
import ImpressumDialog from './dialogs/ImpressumDialog.vue'
import DeletedFirmenDialog from './dialogs/DeletedFirmenDialog.vue'

const firmen = useFirmenStore()

// Cockpit-Unter-Tabs (Detailbereiche)
type SubTabId = 'risiko' | 'produkte' | 'evidence' | 'gutachten'
const subTab = ref<SubTabId>('produkte')
const subTabs = computed(() => [
  { id: 'risiko' as const, label: 'Risiko-Projekte', count: rbProjekte.value.length },
  { id: 'produkte' as const, label: 'Produkte (CRA)', count: firmen.produkte.length },
  { id: 'evidence' as const, label: 'Nachweise', count: firmen.evidence.length },
  { id: 'gutachten' as const, label: 'Gutachten', count: undefined as number | undefined },
])

const creating = ref(false)
const successMsg = ref('')

// Modul-Kacheln fürs Cockpit — Status, Kurzbeschreibung, Direktlink, Statuslabel
const moduleTiles = computed(() => {
  const n = encodeURIComponent(form.value.name || '')
  const mods = form.value.modules || ({} as any)
  return [
    { key: 'risikobewertung' as const, label: 'Risikobewertung', desc: 'Multi-Framework-Risiko-Editor',
      enabled: !!mods.risikobewertung, route: `/risikobewertung?firma=${n}`,
      statusLabel: rbProjekte.value.length ? `${rbProjekte.value.length} Projekt(e)` : 'aktiv' },
    { key: 'cra' as const, label: 'CRA-Readiness', desc: 'Cyber Resilience Act',
      enabled: !!mods.cra, route: `/cra?projekt=${n}`,
      statusLabel: firmen.produkte.length ? `${firmen.produkte.length} Produkt(e)` : 'aktiv' },
    { key: 'nis2' as const, label: 'NIS2', desc: 'NIS2-Richtlinie',
      enabled: !!mods.nis2, route: `/nis2?projekt=${n}`, statusLabel: 'aktiv' },
    { key: 'dsgvo' as const, label: 'DSGVO', desc: 'GDPR-Compliance',
      enabled: !!mods.dsgvo, route: `/dsgvo?projekt=${n}`, statusLabel: 'aktiv' },
    { key: 'ai_act' as const, label: 'AI Act', desc: 'EU AI Act',
      enabled: !!mods.ai_act, route: `/aiact?projekt=${n}`, statusLabel: 'aktiv' },
    { key: 'wiba' as const, label: 'WiBA', desc: 'BSI Weg in die Basis-Absicherung',
      enabled: !!mods.wiba, route: `/wiba?projekt=${n}`, statusLabel: 'aktiv' },
    { key: 'gutachten' as const, label: 'Gutachten', desc: 'Expert Opinions',
      enabled: !!mods.gutachten, route: `/gutachten?firma=${n}`,
      statusLabel: (form.value.frameworks?.length ? `${form.value.frameworks.length} Framework(s)` : 'aktiv') },
  ]
})

// Issue #430: Sync-Modul-Projekte fuer Bestandsfirmen
const syncing = ref(false)
const syncResult = ref<{ message: string; error?: boolean } | null>(null)

// Issue #433: RB-Projekte pro Firma (1:n) anzeigen
const rbProjekte = ref<Array<{
  name: string; framework: string; produkt: string; risiken_count: number;
}>>([])

const loadRbProjekte = async (firmaName: string) => {
  if (!firmaName) { rbProjekte.value = []; return }
  try {
    const res = await apiClient.get(`/firmen/${encodeURIComponent(firmaName)}/rb-projekte`)
    rbProjekte.value = res.data || []
  } catch {
    rbProjekte.value = []
  }
}

// Issue #435: CRA-Projekte pro Firma (1 pro Produkt) — fuer die
// Produkt-Tabelle, um pro Zeile den Link zum richtigen CRA-Projekt
// zu setzen.
const craProjekte = ref<Array<{
  name: string; unternehmen: string; produkt: string; produktklasse: string;
}>>([])

const loadCraProjekte = async (firmaName: string) => {
  if (!firmaName) { craProjekte.value = []; return }
  try {
    const res = await apiClient.get(`/firmen/${encodeURIComponent(firmaName)}/cra-projekte`)
    craProjekte.value = res.data || []
  } catch {
    craProjekte.value = []
  }
}

const craProjektFuerProdukt = (produkt: any): string => {
  // Default-Produkt → CRA-Projekt heisst wie der Firma
  // Sonst → "<Firma> – <Produkt>"
  const firma = form.value.name
  if (!firma) return ''
  if (produkt.is_default) {
    const hit = craProjekte.value.find(p => p.name === firma)
    return hit ? hit.name : ''
  }
  const composite = `${firma} – ${produkt.name}`
  const hit = craProjekte.value.find(p => p.name === composite || p.produkt === produkt.name)
  return hit ? hit.name : ''
}
const onSyncProjekte = async () => {
  if (!form.value.name) return
  syncing.value = true
  syncResult.value = null
  try {
    const res = await apiClient.post(`/firmen/${encodeURIComponent(form.value.name)}/sync-projekte`)
    const created: string[] = res.data?.created || []
    if (created.length === 0) {
      syncResult.value = { message: '✓ Alle aktivierten Modul-Projekte existieren bereits.' }
    } else {
      syncResult.value = { message: `✓ Modul-Projekte angelegt: ${created.join(', ')}` }
    }
  } catch (err: any) {
    syncResult.value = {
      message: err?.response?.data?.error || 'Fehler beim Synchronisieren.',
      error: true,
    }
  } finally {
    syncing.value = false
  }
}

const blankForm = (): Firma => ({
  id: '',
  name: '',
  company: '',
  advisor: '',
  description: '',
  frameworks: [],
  pruefungsfokus: '',
  rb_framework: 'STRIDE',
  produkt: '',
  produktklasse: 'default',
  modules: {
    risikobewertung: true,
    gutachten: true,
    cra: true,
    dsgvo: true,
    nis2: true,
    ai_act: true,
    wiba: true,
  },
})

const form = ref<Firma>(blankForm())

const constants = computed(() => firmen.constants)

const fwDescription = (fw: string): string => {
  const desc: Record<string, string> = {
    STRIDE: ' (Microsoft, Default)',
    Finanzinstitute: ' (Banken/Versicherungen)',
    HEAVENS: ' (Volvo, Automotive)',
    OCTAVE: ' (CERT/CMU)',
    TARA: ' (ISO/SAE 21434)',
  }
  return desc[fw] || ''
}

const startNew = () => {
  creating.value = true
  firmen.selectedFirma = null
  form.value = blankForm()

  successMsg.value = ''
}

const loadFirmaIntoForm = (k: Firma) => {
  form.value = JSON.parse(JSON.stringify(k))
  if (!form.value.modules) form.value.modules = blankForm().modules
  if (!form.value.frameworks) form.value.frameworks = []
  creating.value = false
}

watch(() => firmen.selectedFirma, async (k) => {
  if (k) {
    loadFirmaIntoForm(k)
    // Produkte und Evidence parallel laden
    await Promise.all([
      firmen.fetchProdukte(k.name),
      firmen.fetchEvidence(k.name),
      loadRbProjekte(k.name),  // #433: RB-Projekte fuer diesen Firmen
      loadCraProjekte(k.name),  // #435: CRA-Projekte pro Produkt
    ])
  }
})

const produktklasseLabel = (key: string): string => {
  const pk = constants.value?.produktklassen?.find(p => p.key === key)
  return pk?.label || key
}

// ---- Produkt-Dialog ----
const produktDialogOpen = ref(false)
const editingProdukt = ref<Produkt | null>(null)

const onAddProdukt = () => {
  editingProdukt.value = null
  produktDialogOpen.value = true
}

const onEditProdukt = (p: Produkt) => {
  editingProdukt.value = p
  produktDialogOpen.value = true
}

const onSaveProdukt = async (data: Partial<Produkt>) => {
  if (!form.value.name) return
  if (editingProdukt.value?.id) {
    await firmen.updateProdukt(form.value.name, editingProdukt.value.id, data)
  } else {
    await firmen.createProdukt(form.value.name, data)
  }
  produktDialogOpen.value = false
  // Issue #435: CRA-Projekt-Liste neu laden (Backend hat ggf. ein neues angelegt)
  await loadCraProjekte(form.value.name)
}

const onSetDefault = async (p: Produkt) => {
  if (!form.value.name || !p.id) return
  await firmen.setDefaultProdukt(form.value.name, p.id)
  await loadCraProjekte(form.value.name)
}

const onDeleteProdukt = async (p: Produkt) => {
  if (!form.value.name || !p.id) return
  if (!confirm(`Produkt "${p.name}" wirklich löschen?\n\nDas verknüpfte CRA-Projekt bleibt erhalten (Bewertungen).`)) return
  await firmen.deleteProdukt(form.value.name, p.id)
  await loadCraProjekte(form.value.name)
}

// ---- Evidence ----
const evidenceUrlOpen = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
// #1450: Kategorie für hochgeladene Doku-PDFs (techn./Benutzer-Doku) → als Firmen-Nachweis sichtbar
const uploadDocType = ref('')

const onFileChosen = async (event: Event) => {
  const target = event.target as HTMLInputElement
  if (!target.files?.[0] || !form.value.name) return
  const file = target.files[0]
  const ok = await firmen.uploadEvidenceFile(form.value.name, file, uploadDocType.value)
  if (ok) successMsg.value = `Datei "${file.name}" hochgeladen.`
  target.value = ''
}

const onAddEvidenceUrl = async (data: any) => {
  if (!form.value.name) return
  const ok = await firmen.addEvidenceUrl(form.value.name, data.url, data.max_pages, data.doc_type, data.tags)
  if (ok) {
    evidenceUrlOpen.value = false
    successMsg.value = 'Webseite importiert.'
  }
}

const onExtractEvidence = async (docId: string) => {
  if (!form.value.name) return
  const result = await firmen.extractEvidence(form.value.name, docId)
  if (result) successMsg.value = `Text extrahiert (${result.chars} Zeichen).`
}

const onDeleteEvidence = async (docId: string) => {
  if (!form.value.name) return
  if (!confirm('Nachweis wirklich entfernen?')) return
  await firmen.deleteEvidence(form.value.name, docId)
}

const onSave = async () => {
  successMsg.value = ''
  if (!form.value.name?.trim()) {
    firmen.error = 'Projektname ist Pflicht'
    return
  }
  const result = creating.value
    ? await firmen.createFirma(form.value)
    : await firmen.updateFirma(form.value.name, form.value)
  if (result) {
    successMsg.value = 'Gespeichert.'
    creating.value = false
    firmen.selectedFirma = result
    setTimeout(() => (successMsg.value = ''), 2500)
  }
}

const onCancel = () => {
  if (creating.value) {
    creating.value = false
    firmen.selectedFirma = null
    form.value = blankForm()
  } else if (firmen.selectedFirma) {
    loadFirmaIntoForm(firmen.selectedFirma)
  }
}

const onDelete = async () => {
  if (!form.value.name) return
  if (!confirm(`Firma "${form.value.name}" wirklich löschen? (Soft-Delete, kann wiederhergestellt werden)`)) return
  const ok = await firmen.deleteFirma(form.value.name)
  if (ok) {
    form.value = blankForm()
    successMsg.value = 'Gelöscht.'
  }
}

// ---- Impressum-Dialog ----
const impressumOpen = ref(false)

const onImpressum = () => {
  impressumOpen.value = true
}

const onImpressumApply = (data: any) => {
  // Wenn kein Firma aktiv ist, neuen anlegen — sonst Felder ergänzen
  if (!firmen.selectedFirma && !creating.value) {
    startNew()
  }
  if (data.unternehmen) {
    form.value.company = data.unternehmen
    if (!form.value.name && creating.value) {
      form.value.name = data.unternehmen  // Default für Projektname
    }
  }
  if (data.beschreibung) form.value.description = data.beschreibung
  if (data.vertreter?.length) form.value.advisor = data.vertreter[0]
  impressumOpen.value = false
  successMsg.value = 'Daten aus Impressum übernommen.'

}

// ---- Gelöschte Firmen Dialog ----
const deletedDialogOpen = ref(false)

const onShowDeleted = async () => {
  deletedDialogOpen.value = true
}

// ---- Gutachten-Fokus generieren ----
const generateFokus = () => {
  if (!form.value.frameworks?.length) {
    alert('Bitte zuerst Frameworks auswählen.')
    return
  }
  const fokusMap: Record<string, string> = {
    DORA: 'Digital Operational Resilience Act (EU 2022/2554). Prüfung von ICT-Risikomanagement, Incident Response, Resilience Testing und Drittanbieter-Management.',
    NIS2: 'Cybersicherheitsanforderungen gemäß NIS2-Richtlinie (EU 2022/2555 / BSIG 2025). Prüfung der Risikomaßnahmen, Meldepflichten und Lieferkettensteuerung.',
    CRA: 'Cyber Resilience Act (EU 2024/2847). Konformitätsbewertung von Produkten mit digitalen Elementen.',
    ISO27001: 'Informationssicherheits-Managementsystem gemäß ISO/IEC 27001:2022. Gap-Analyse der Annex-A-Controls und ISMS-Reife.',
    DSGVO: 'Datenschutz-Grundverordnung (EU 2016/679). Prüfung der Rechtmäßigkeit, TOMs, DSFA und Auftragsverarbeitungsverträge.',
    AI_ACT: 'EU AI Act (EU 2024/1689). Konformitätsbewertung von KI-Systemen, Risikoklassifizierung und Hochrisiko-Anforderungen.',
    BSI: 'BSI IT-Grundschutz. Prüfung der Bausteine und Maßnahmen nach BSI-Standard 200-2.',
  }
  form.value.pruefungsfokus = form.value.frameworks
    .map(fw => fokusMap[fw] || `${fw}: Prüfungsfokus`)
    .join('\n\n')
}

onMounted(async () => {
  await firmen.fetchFirmen()
  await firmen.fetchConstants()
})
</script>

<style scoped>
.firmen-view {
  max-width: 1100px;
}

/* ===== Cockpit (Sprint: Firmenverwaltung-UX) ===== */
.cockpit { display: flex; flex-direction: column; gap: 16px; }
.cockpit-header {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;
}
.cockpit-title h2 { margin: 0; font-size: 22px; }
.cockpit-sub { color: var(--color-text-secondary, #666); font-size: 14px; }
.cockpit-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.card {
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 10px;
  padding: 16px 18px;
}
.card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.card-head h3 { margin: 0; font-size: 16px; }

.stamm-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
}
.stamm-grid .form-row.full { grid-column: 1 / -1; }

/* Modul-Kacheln */
.tile-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px;
}
.tile {
  border: 1px solid var(--color-border, #e0e0e0); border-radius: 8px;
  padding: 12px; background: var(--color-background, #fafafa);
  display: flex; flex-direction: column; gap: 6px; opacity: 0.7;
  transition: opacity .15s, border-color .15s, box-shadow .15s;
}
.tile.active {
  opacity: 1; border-color: #1565c0;
  box-shadow: 0 1px 4px rgba(21,101,192,.12);
}
.tile-toggle { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.tile-toggle strong { font-size: 14px; }
.tile-desc { color: var(--color-text-secondary, #777); font-size: 12px; }
.tile-foot { display: flex; justify-content: space-between; align-items: center; margin-top: auto; }
.tile-status { font-size: 11px; padding: 2px 8px; border-radius: 999px; }
.tile-status.on { background: #e8f5e9; color: #2e7d32; }
.tile-status.off { background: #f0f0f0; color: #999; }
.tile-link { font-size: 12px; color: #1565c0; text-decoration: none; }
.tile-link:hover { text-decoration: underline; }

/* Unter-Tabs */
.subtabs { display: flex; gap: 4px; border-bottom: 1px solid var(--color-border, #e0e0e0); margin-bottom: 12px; flex-wrap: wrap; }
.subtab {
  background: none; border: none; padding: 8px 14px; cursor: pointer;
  font-size: 13px; color: var(--color-text-secondary, #666);
  border-bottom: 2px solid transparent; font-family: inherit;
}
.subtab.active { color: #1565c0; border-bottom-color: #1565c0; font-weight: 600; }
.subtab-count {
  margin-left: 6px; background: #eef2f7; color: #555; border-radius: 999px;
  padding: 0 7px; font-size: 11px;
}
.subpanel { min-height: 60px; }

.empty-state {
  background: white;
  padding: 48px;
  text-align: center;
  border-radius: 8px;
  border: 1px solid var(--color-border);
}

.empty-state h2 {
  margin: 0 0 16px;
  color: var(--color-text-primary);
}

.empty-state p {
  margin: 0 0 24px;
  color: #888;
}

.empty-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

.firma-form {
  background: white;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  padding: 20px 24px;
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}

.form-header h2 {
  margin: 0;
  font-size: 20px;
  color: var(--color-text-primary);
}

.form-header-actions {
  display: flex;
  gap: 8px;
}

.alert {
  padding: 10px 14px;
  border-radius: 4px;
  margin-bottom: 12px;
  font-size: 13px;
}

.alert-error {
  background: #ffebee;
  color: #c62828;
  border: 1px solid #ef5350;
}

.alert-success {
  background: #e8f5e9;
  color: #2e7d32;
  border: 1px solid #81c784;
}

.form-tabs {
  display: flex;
  gap: 2px;
  margin: 16px 0;
  border-bottom: 2px solid var(--color-border);
}

.tab-btn {
  background: none;
  border: none;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 3px solid transparent;
  color: #666;
}

.tab-btn.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.tab-content {
  padding: 8px 0;
}

fieldset {
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 16px 20px;
  margin-bottom: 16px;
}

fieldset legend {
  padding: 0 8px;
  font-weight: 600;
  font-size: 13px;
  color: var(--color-primary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.placeholder-section {
  background: #f9f9f9;
}

.form-row {
  margin-bottom: 12px;
}

.form-row label {
  display: block;
  margin-bottom: 4px;
  font-weight: 600;
  font-size: 13px;
}

.form-row input,
.form-row select,
.form-row textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
}

.form-row input.readonly {
  background: #f5f5f5;
  color: #666;
}

.form-row small {
  color: #888;
  font-size: 12px;
  margin-top: 2px;
  display: block;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.module-check {
  display: flex;
  flex-direction: column;
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.module-check:hover {
  background: #f5f5f5;
}

.module-check input {
  margin: 0 0 6px;
}

.module-check strong {
  font-size: 13px;
  margin-bottom: 2px;
}

.module-check small {
  font-size: 11px;
  color: #888;
}

.checkbox-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border: 1px solid #eee;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.checkbox-row:hover {
  background: #f5f5f5;
}

.button-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.hint {
  margin: 0 0 12px;
  color: #888;
  font-size: 12px;
}

.form-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}

.btn-primary,
.btn-secondary,
.btn-danger-outline {
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  border: none;
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

.btn-secondary:hover {
  background: #d0d0d0;
}

.btn-danger-outline {
  background: white;
  color: #d32f2f;
  border: 1px solid #d32f2f;
}

.btn-danger-outline:hover {
  background: #ffebee;
}

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
  padding: 24px;
  max-width: 600px;
  width: 90%;
  max-height: 85vh;
  overflow-y: auto;
}

.modal-content h3 {
  margin: 0 0 16px;
  color: var(--color-primary);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.info {
  padding: 12px;
  text-align: center;
  color: #888;
}

.impressum-preview {
  background: #f9f9f9;
  padding: 12px;
  border-radius: 4px;
  margin-top: 12px;
  font-size: 13px;
}

.impressum-preview h4 {
  margin: 0 0 8px;
}

.impressum-preview > div {
  margin-bottom: 4px;
}

.deleted-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.deleted-table th,
.deleted-table td {
  padding: 8px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.btn-small,
.btn-danger-small {
  padding: 4px 10px;
  border-radius: 3px;
  border: 1px solid var(--color-border);
  background: white;
  cursor: pointer;
  font-size: 12px;
  margin-right: 4px;
}

.btn-danger-small {
  color: #d32f2f;
  border-color: #d32f2f;
}

.empty {
  padding: 20px;
  text-align: center;
  color: #888;
}

/* Sub-Tables (Produkte / Evidence) */
.sub-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin-bottom: 12px;
}

.sub-table th {
  background: #f5f5f5;
  text-align: left;
  padding: 6px 10px;
  font-weight: 600;
  border-bottom: 1px solid var(--color-border);
}

.sub-table td {
  padding: 6px 10px;
  border-bottom: 1px solid #f0f0f0;
}

.sub-table .action-cell {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.sub-empty {
  padding: 16px;
  text-align: center;
  color: #888;
  font-size: 12px;
  font-style: italic;
}

.evidence-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
</style>
