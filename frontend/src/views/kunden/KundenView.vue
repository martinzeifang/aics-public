<template>
  <div class="kunden-view">
    <div v-if="!kunden.selectedKunde && !creating" class="empty-state">
      <h2>Kundenverwaltung</h2>
      <p>Wählen Sie links einen Kunden aus oder legen Sie einen neuen an.</p>
      <div class="empty-actions">
        <button class="btn-primary" @click="startNew">+ Neuen Kunden anlegen</button>
        <button class="btn-secondary" @click="onImpressum">🌐 Aus Website-Impressum…</button>
        <button class="btn-secondary" @click="onShowDeleted">♻️ Gelöschte Kunden…</button>
      </div>
    </div>

    <div v-else class="kunde-form">
      <!-- Form Header -->
      <div class="form-header">
        <h2>{{ creating ? 'Neuer Kunde' : (form.name || 'Kunde bearbeiten') }}</h2>
        <div class="form-header-actions">
          <button class="btn-secondary" @click="onImpressum">🌐 Aus Website…</button>
          <button class="btn-secondary" @click="onShowDeleted">♻️ Gelöschte…</button>
          <button v-if="!creating" class="btn-danger-outline" @click="onDelete">Löschen</button>
        </div>
      </div>

      <div v-if="kunden.error" class="alert alert-error">{{ kunden.error }}</div>
      <div v-if="successMsg" class="alert alert-success">{{ successMsg }}</div>

      <!-- Tab Navigation -->
      <div class="form-tabs">
        <button
          v-for="t in tabs"
          :key="t.id"
          @click="activeTab = t.id"
          :class="['tab-btn', { active: activeTab === t.id }]"
        >
          {{ t.label }}
        </button>
      </div>

      <!-- Tab: Allgemein -->
      <div v-if="activeTab === 'general'" class="tab-content">
        <fieldset>
          <legend>Allgemein</legend>
          <div class="form-row">
            <label>Projektname *</label>
            <input
              v-model="form.name"
              :readonly="!creating"
              :class="{ readonly: !creating }"
              placeholder="z.B. Meine Firma GmbH"
            />
            <small v-if="!creating">Projektname kann nach dem Speichern nicht mehr geändert werden.</small>
          </div>
          <div class="form-row">
            <label>Unternehmen</label>
            <input v-model="form.company" placeholder="z.B. Beispiel AG" />
          </div>
          <div class="form-row">
            <label>Berater / Verantwortlicher</label>
            <input v-model="form.advisor" />
          </div>
          <div class="form-row">
            <label>Beschreibung</label>
            <textarea v-model="form.description" rows="4"></textarea>
          </div>
        </fieldset>
      </div>

      <!-- Tab: Module -->
      <div v-if="activeTab === 'modules'" class="tab-content">
        <fieldset>
          <legend>Module-Aktivierung</legend>
          <p class="hint">Aktivieren Sie nur die Module, die für diesen Kunden verwendet werden.</p>
          <div class="module-grid">
            <label class="module-check">
              <input type="checkbox" v-model="form.modules.risikobewertung" />
              <strong>Risikobewertung</strong>
              <small>Multi-Framework-Risiko-Editor</small>
            </label>
            <label class="module-check">
              <input type="checkbox" v-model="form.modules.gutachten" />
              <strong>Gutachten</strong>
              <small>Expert Opinions</small>
            </label>
            <label class="module-check">
              <input type="checkbox" v-model="form.modules.cra" />
              <strong>CRA-Readiness</strong>
              <small>Cyber Resilience Act</small>
            </label>
            <label class="module-check">
              <input type="checkbox" v-model="form.modules.dsgvo" />
              <strong>DSGVO</strong>
              <small>GDPR-Compliance</small>
            </label>
            <label class="module-check">
              <input type="checkbox" v-model="form.modules.nis2" />
              <strong>NIS2</strong>
              <small>NIS2-Richtlinie</small>
            </label>
            <label class="module-check">
              <input type="checkbox" v-model="form.modules.ai_act" />
              <strong>AI Act</strong>
              <small>EU AI Act</small>
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>Risikobewertung-Framework</legend>
          <p class="hint">Methode für die Risikoanalyse.</p>
          <div class="form-row">
            <label>Bewertungs-Framework</label>
            <select v-model="form.rb_framework">
              <option v-for="fw in constants?.rb_frameworks || []" :key="fw" :value="fw">
                {{ fw }}{{ fwDescription(fw) }}
              </option>
            </select>
          </div>
        </fieldset>
      </div>

      <!-- Tab: Gutachten -->
      <div v-if="activeTab === 'gutachten'" class="tab-content">
        <fieldset>
          <legend>Gutachten-Frameworks</legend>
          <p class="hint">Welche Frameworks werden in einem Gutachten geprüft?</p>
          <div class="checkbox-grid">
            <label v-for="fw in constants?.gutachten_frameworks || []" :key="fw" class="checkbox-row">
              <input type="checkbox" :value="fw" v-model="form.frameworks" />
              {{ fw }}
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>Prüfungsfokus</legend>
          <div class="form-row">
            <label>Schwerpunkte für das Gutachten</label>
            <textarea v-model="form.pruefungsfokus" rows="6"
                      placeholder="Welche Aspekte sollen im Gutachten besonders betrachtet werden?"></textarea>
          </div>
          <div class="button-row">
            <button class="btn-secondary" @click="generateFokus">💡 Vorschlag generieren</button>
            <button class="btn-secondary" @click="form.pruefungsfokus = ''">Leeren</button>
          </div>
        </fieldset>
      </div>

      <!-- Tab: CRA-Readiness -->
      <div v-if="activeTab === 'cra'" class="tab-content">
        <fieldset>
          <legend>CRA-Readiness</legend>
          <div class="form-row">
            <label>Produkt / Software</label>
            <input v-model="form.produkt" placeholder="z.B. Mein Produkt 1.0" />
          </div>
          <div class="form-row">
            <label>Produktklasse (CRA)</label>
            <select v-model="form.produktklasse">
              <option v-for="pk in constants?.produktklassen || []" :key="pk.key" :value="pk.key">
                {{ pk.label }}
              </option>
            </select>
            <small>
              Important Class I/II = Annex III (digitale Produkte mit erhöhtem Risiko).
              Critical Class I/II = Annex IV (kritische Produkte mit höchstem Risiko).
            </small>
          </div>
        </fieldset>

        <!-- Multi-Produkt-Verwaltung -->
        <fieldset>
          <legend>Produkte / Projekte</legend>
          <p class="hint">Mehrere Produkte pro Kunde. Standardprodukt für CRA-Bewertungen markieren.</p>

          <table v-if="kunden.produkte.length > 0" class="sub-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Klasse</th>
                <th>Standard</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in kunden.produkte" :key="p.id">
                <td>{{ p.name }}</td>
                <td>{{ produktklasseLabel(p.produktklasse) }}</td>
                <td>{{ p.is_default ? '★' : '' }}</td>
                <td class="action-cell">
                  <button class="btn-small" @click="onEditProdukt(p)">Bearbeiten</button>
                  <button class="btn-small" @click="onSetDefault(p)" :disabled="!!p.is_default">Als Standard</button>
                  <button class="btn-danger-small" @click="onDeleteProdukt(p)">Löschen</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="sub-empty">Keine Produkte. + Produkt klicken, um eines anzulegen.</div>

          <button class="btn-secondary" @click="onAddProdukt">+ Produkt</button>
        </fieldset>

        <!-- Evidence-Liste -->
        <fieldset>
          <legend>Nachweise (Evidence)</legend>
          <p class="hint">Dateien und Webseiten als Nachweis-Material für Bewertungen.</p>

          <table v-if="kunden.evidence.length > 0" class="sub-table">
            <thead>
              <tr>
                <th>Datei / URL</th>
                <th>Typ</th>
                <th>Schlagwörter</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ev in kunden.evidence" :key="ev.id">
                <td>
                  <a v-if="ev.doc_kind === 'web' && ev.url" :href="ev.url" target="_blank">{{ ev.filename }}</a>
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
            <input
              ref="fileInput"
              type="file"
              style="display:none"
              accept=".pdf,.docx,.txt,.md,.csv,.xlsx"
              @change="onFileChosen"
            />
            <button class="btn-secondary" @click="fileInput?.click()">+ Datei</button>
            <button class="btn-secondary" @click="evidenceUrlOpen = true">+ URL</button>
          </div>
        </fieldset>
      </div>

      <!-- Form-Aktionen -->
      <div class="form-actions">
        <button class="btn-primary" @click="onSave" :disabled="kunden.loading">
          {{ kunden.loading ? 'Speichert…' : '💾 Speichern' }}
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

    <!-- Gelöschte Kunden -->
    <DeletedKundenDialog
      v-if="deletedDialogOpen"
      @cancel="deletedDialogOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useKundenStore, type Kunde, type Produkt } from '../../stores/kunden'
import ProduktDialog from './dialogs/ProduktDialog.vue'
import EvidenceURLDialog from './dialogs/EvidenceURLDialog.vue'
import ImpressumDialog from './dialogs/ImpressumDialog.vue'
import DeletedKundenDialog from './dialogs/DeletedKundenDialog.vue'

const kunden = useKundenStore()

const tabs = [
  { id: 'general', label: 'Allgemein' },
  { id: 'modules', label: 'Module' },
  { id: 'gutachten', label: 'Gutachten' },
  { id: 'cra', label: 'CRA-Readiness' },
]

const activeTab = ref<'general' | 'modules' | 'gutachten' | 'cra'>('general')
const creating = ref(false)
const successMsg = ref('')

const blankForm = (): Kunde => ({
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
  },
})

const form = ref<Kunde>(blankForm())

const constants = computed(() => kunden.constants)

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
  kunden.selectedKunde = null
  form.value = blankForm()
  activeTab.value = 'general'
  successMsg.value = ''
}

const loadKundeIntoForm = (k: Kunde) => {
  form.value = JSON.parse(JSON.stringify(k))
  if (!form.value.modules) form.value.modules = blankForm().modules
  if (!form.value.frameworks) form.value.frameworks = []
  creating.value = false
}

watch(() => kunden.selectedKunde, async (k) => {
  if (k) {
    loadKundeIntoForm(k)
    // Produkte und Evidence parallel laden
    await Promise.all([
      kunden.fetchProdukte(k.name),
      kunden.fetchEvidence(k.name),
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
    await kunden.updateProdukt(form.value.name, editingProdukt.value.id, data)
  } else {
    await kunden.createProdukt(form.value.name, data)
  }
  produktDialogOpen.value = false
}

const onSetDefault = async (p: Produkt) => {
  if (!form.value.name || !p.id) return
  await kunden.setDefaultProdukt(form.value.name, p.id)
}

const onDeleteProdukt = async (p: Produkt) => {
  if (!form.value.name || !p.id) return
  if (!confirm(`Produkt "${p.name}" wirklich löschen?`)) return
  await kunden.deleteProdukt(form.value.name, p.id)
}

// ---- Evidence ----
const evidenceUrlOpen = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const onFileChosen = async (event: Event) => {
  const target = event.target as HTMLInputElement
  if (!target.files?.[0] || !form.value.name) return
  const file = target.files[0]
  const ok = await kunden.uploadEvidenceFile(form.value.name, file)
  if (ok) successMsg.value = `Datei "${file.name}" hochgeladen.`
  target.value = ''
}

const onAddEvidenceUrl = async (data: any) => {
  if (!form.value.name) return
  const ok = await kunden.addEvidenceUrl(form.value.name, data.url, data.max_pages, data.doc_type, data.tags)
  if (ok) {
    evidenceUrlOpen.value = false
    successMsg.value = 'Webseite importiert.'
  }
}

const onExtractEvidence = async (docId: string) => {
  if (!form.value.name) return
  const result = await kunden.extractEvidence(form.value.name, docId)
  if (result) successMsg.value = `Text extrahiert (${result.chars} Zeichen).`
}

const onDeleteEvidence = async (docId: string) => {
  if (!form.value.name) return
  if (!confirm('Nachweis wirklich entfernen?')) return
  await kunden.deleteEvidence(form.value.name, docId)
}

const onSave = async () => {
  successMsg.value = ''
  if (!form.value.name?.trim()) {
    kunden.error = 'Projektname ist Pflicht'
    return
  }
  const result = creating.value
    ? await kunden.createKunde(form.value)
    : await kunden.updateKunde(form.value.name, form.value)
  if (result) {
    successMsg.value = 'Gespeichert.'
    creating.value = false
    kunden.selectedKunde = result
    setTimeout(() => (successMsg.value = ''), 2500)
  }
}

const onCancel = () => {
  if (creating.value) {
    creating.value = false
    kunden.selectedKunde = null
    form.value = blankForm()
  } else if (kunden.selectedKunde) {
    loadKundeIntoForm(kunden.selectedKunde)
  }
}

const onDelete = async () => {
  if (!form.value.name) return
  if (!confirm(`Kunde "${form.value.name}" wirklich löschen? (Soft-Delete, kann wiederhergestellt werden)`)) return
  const ok = await kunden.deleteKunde(form.value.name)
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
  // Wenn kein Kunde aktiv ist, neuen anlegen — sonst Felder ergänzen
  if (!kunden.selectedKunde && !creating.value) {
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
  activeTab.value = 'general'
}

// ---- Gelöschte Kunden Dialog ----
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
  await kunden.fetchKunden()
  await kunden.fetchConstants()
})
</script>

<style scoped>
.kunden-view {
  max-width: 1100px;
}

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

.kunde-form {
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
