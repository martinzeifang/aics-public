<template>
  <div class="gutachten-view">
    <div class="header">
      <h2>Gutachten – Compliance-Audit</h2>
      <p>Multi-Framework-Gutachten · Fragen aus Regulierungstexten generieren · Bewerten · Gutachten erstellen</p>
    </div>

    <div v-if="store.error" class="alert alert-error" @click="store.error = null">{{ store.error }}</div>

    <!-- Projekt-Auswahl/Anlegen -->
    <div v-if="!store.selectedProjektObj && !creating" class="empty-state">
      <h3>Gutachten-Projekt wählen</h3>
      <p v-if="store.projekte.length > 0">{{ store.projekte.length }} vorhandene Projekte:</p>
      <div v-if="store.projekte.length > 0" class="proj-list">
        <button v-for="p in store.projekte" :key="p.name" class="proj-tile"
                @click="store.selectedProjekt = p.name">
          <strong>{{ p.name }}</strong>
          <span class="proj-fw">{{ (p.frameworks || []).join(', ') }}</span>
        </button>
      </div>
      <button class="btn-primary" @click="startNew">+ Neues Gutachten anlegen</button>
    </div>

    <!-- Anlegen-Form -->
    <div v-else-if="creating" class="form-card">
      <h3>Neues Gutachten</h3>
      <div class="form-row">
        <label>Projektname *</label>
        <input v-model="newForm.name" placeholder="z.B. Acme Audit Q4 2026" />
      </div>
      <div class="form-row">
        <label>Kunde</label>
        <select v-model="newForm.unternehmen">
          <option value="">— ohne Kunde —</option>
          <option v-for="k in kundenStore.kunden" :key="k.name" :value="k.name">
            {{ k.name }}<span v-if="k.company"> ({{ k.company }})</span>
          </option>
        </select>
        <small class="hint">Verknüpft das Gutachten mit einem Kunden aus der Kundenverwaltung.</small>
      </div>
      <div class="form-row">
        <label>Frameworks (Mehrfachauswahl)</label>
        <div class="fw-checks">
          <label v-for="fw in availableFrameworks" :key="fw" class="check-row">
            <input type="checkbox" :value="fw"
                   :checked="newForm.frameworks.includes(fw)"
                   @change="toggleFw(newForm, fw, $event)" />
            <strong>{{ fw }}</strong>
            <span class="muted">{{ store.sectionsCount[fw] || 0 }} Abschnitte</span>
          </label>
        </div>
      </div>
      <div class="form-row">
        <label>Prüfungsfokus</label>
        <textarea v-model="newForm.pruefungsfokus" rows="3"
                  placeholder="Was ist Schwerpunkt des Audits? z.B. 'Schwerpunkt auf NIS2-Lieferantenrisiko und DORA-IKT-Drittparteien'"></textarea>
      </div>
      <div class="form-actions">
        <button class="btn-secondary" @click="creating = false">Abbrechen</button>
        <button class="btn-primary" @click="onCreate" :disabled="!newForm.name || newForm.frameworks.length === 0">Anlegen</button>
      </div>
    </div>

    <!-- Aktives Projekt -->
    <template v-else-if="store.selectedProjektObj">
      <div class="proj-selector">
        <select v-model="store.selectedProjekt">
          <option v-for="p in store.projekte" :key="p.name" :value="p.name">
            {{ p.name }} — {{ (p.frameworks || []).join(', ') }}
          </option>
        </select>
        <KundeSelector
          :model-value="(store.selectedProjektObj as any)?.unternehmen || ''"
          :saving="reassignSaving"
          :success-text="reassignMsg.ok"
          :error-text="reassignMsg.err"
          @save="onReassignKunde"
        />
        <button class="btn-secondary" @click="startNew">+ Neu</button>
        <button class="btn-secondary" @click="editProjektOpen = true">⚙️ Bearbeiten</button>
        <button class="btn-danger" @click="confirmDelete">🗑️ Löschen</button>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button v-for="t in tabs" :key="t.id"
                :class="['tab-btn', { active: activeTab === t.id }]"
                @click="activeTab = t.id">
          {{ t.label }}
          <span v-if="t.id === 'fragen' && store.fragen.length" class="badge">{{ store.fragen.length }}</span>
        </button>
      </div>

      <!-- TAB: Übersicht -->
      <div v-if="activeTab === 'overview'" class="tab-content">
        <div class="stat-grid">
          <div class="stat-card">
            <div class="stat-num">{{ store.fragen.length }}</div>
            <div class="stat-lbl">Fragen</div>
          </div>
          <div class="stat-card">
            <div class="stat-num">{{ answeredCount }}</div>
            <div class="stat-lbl">Beantwortet ({{ answeredPct }}%)</div>
          </div>
          <div class="stat-card">
            <div class="stat-num">{{ store.selectedProjektObj.frameworks?.length || 0 }}</div>
            <div class="stat-lbl">Frameworks</div>
          </div>
          <div class="stat-card">
            <div class="stat-num">{{ totalSectionsAvail }}</div>
            <div class="stat-lbl">Regulierungs-Abschnitte</div>
          </div>
        </div>

        <div class="info-card">
          <h4>📋 Workflow</h4>
          <ol>
            <li><strong>Fragen-Tab:</strong> ChatGPT-Prompts pro Framework generieren, in ChatGPT einfügen, Antworten zurück importieren</li>
            <li><strong>Fragen bearbeiten:</strong> Antworten und Bewertungen ergänzen</li>
            <li><strong>Gutachten-Tab:</strong> ChatGPT-Prompt für Gutachten-Entwurf generieren, Antwort importieren, ggf. editieren</li>
            <li><strong>Export:</strong> Word-Gutachten oder Excel-Fragebogen herunterladen</li>
          </ol>
        </div>

        <div class="info-card">
          <h4>📌 Prüfungsfokus</h4>
          <p v-if="store.selectedProjektObj.pruefungsfokus">{{ store.selectedProjektObj.pruefungsfokus }}</p>
          <p v-else class="muted">Kein Prüfungsfokus gesetzt — über "⚙️ Bearbeiten" hinzufügen.</p>
        </div>
      </div>

      <!-- TAB: Fragen -->
      <div v-if="activeTab === 'fragen'" class="tab-content">
        <div class="fragen-toolbar">
          <button class="btn-primary" @click="generatePromptOpen = true">🤖 ChatGPT-Prompt generieren</button>
          <button class="btn-secondary" @click="importFragenOpen = true">📥 Antwort importieren</button>
          <button class="btn-secondary" @click="newFrageOpen = true">+ Manuelle Frage</button>
          <DownloadButton
            v-if="store.fragen.length > 0"
            :endpoint="`/gutachten/${encodeURIComponent(store.selectedProjekt || '')}/fragebogen/export`"
            label="📊 Excel-Fragebogen"
          />
          <ImportButton
            v-if="store.selectedProjekt"
            :endpoint="`/gutachten/${encodeURIComponent(store.selectedProjekt)}/fragebogen/import`"
            label="⬆️ Excel-Import"
            @imported="onExcelImported"
          />
          <input v-model="fragenSearch" placeholder="🔎 Fragen durchsuchen…" class="search-input" />
          <select v-model="fragenFilterFw">
            <option value="">Alle Frameworks</option>
            <option v-for="fw in fragenFrameworks" :key="fw" :value="fw">{{ fw }}</option>
          </select>
        </div>

        <div v-if="visibleFragen.length === 0" class="empty">
          Noch keine Fragen.
          <span v-if="store.fragen.length > 0">Filter prüfen.</span>
          <span v-else>Klick auf "ChatGPT-Prompt generieren" oben.</span>
        </div>

        <table v-else class="fragen-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Framework</th>
              <th>Section</th>
              <th>Thema</th>
              <th>Frage / Antwort</th>
              <th>Bewertung</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in visibleFragen" :key="f.id">
              <td>{{ f.question_num }}</td>
              <td><span class="fw-tag">{{ f.framework }}</span></td>
              <td><code class="ref">{{ f.section_ref }}</code></td>
              <td class="thema-cell">{{ f.thema }}</td>
              <td class="frage-cell">
                <strong>{{ f.frage }}</strong>
                <p v-if="f.antwort" class="antwort-text">{{ f.antwort }}</p>
                <p v-else class="muted">— noch nicht beantwortet —</p>
              </td>
              <td>
                <span :class="['bw-pill', bewertungClass(f.bewertung)]">{{ f.bewertung || '?' }}</span>
              </td>
              <td>
                <button class="btn-icon" @click="editFrage(f)" title="Bearbeiten">✏️</button>
                <button class="btn-icon" @click="onDeleteFrage(f.id)" title="Löschen">🗑️</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- TAB: Gutachten -->
      <div v-if="activeTab === 'gutachten'" class="tab-content">
        <div class="gutachten-actions">
          <button class="btn-primary" @click="onBuildGutachtenPrompt" :disabled="store.fragen.length === 0">
            🤖 Gutachten-Prompt generieren
          </button>
          <button class="btn-secondary" @click="importGutachtenOpen = true">📥 Gutachten-Antwort importieren</button>
          <button v-if="store.draftPayload" class="btn-success"
                  @click="downloadGutachten" :disabled="exporting">
            {{ exporting ? 'Lädt…' : '📄 Gutachten herunterladen (DOCX)' }}
          </button>
        </div>

        <div v-if="!store.draftPayload" class="empty">
          Noch kein Gutachten-Entwurf.
          <span v-if="store.fragen.length === 0">Erst Fragen erstellen.</span>
          <span v-else>Klick auf "Gutachten-Prompt generieren" und führe den ChatGPT-Workflow durch.</span>
        </div>

        <div v-else class="gutachten-preview">
          <h3>{{ store.draftPayload?.gesamtbewertung || 'Gutachten-Entwurf' }}</h3>
          <details open>
            <summary>Zusammenfassung</summary>
            <p>{{ store.draftPayload?.zusammenfassung || '—' }}</p>
          </details>
          <details>
            <summary>Bewertungen pro Framework</summary>
            <ul>
              <li v-for="fw in (store.draftPayload?.framework_bewertungen || [])" :key="fw.framework">
                <strong>{{ fw.framework }}:</strong> {{ fw.erfuellungsgrad }}
              </li>
            </ul>
          </details>
          <details>
            <summary>Empfehlungen</summary>
            <ol>
              <li v-for="(emp, i) in (store.draftPayload?.empfehlungen || [])" :key="i">
                <strong>{{ emp.titel || emp.massnahme || `Empfehlung ${i+1}` }}</strong>
                <p v-if="emp.beschreibung">{{ emp.beschreibung }}</p>
              </li>
            </ol>
          </details>
          <details>
            <summary>Fazit</summary>
            <p>{{ store.draftPayload?.fazit || '—' }}</p>
          </details>
        </div>
      </div>
    </template>

    <!-- ==== DIALOGE ==== -->

    <!-- Prompt generieren -->
    <div v-if="generatePromptOpen" class="modal-overlay" @click.self="generatePromptOpen = false">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>🤖 ChatGPT-Prompt generieren</h3>
          <button class="btn-close" @click="generatePromptOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Anzahl Fragen pro Framework</label>
            <input type="number" v-model.number="promptBatchSize" min="3" max="50" />
          </div>
          <label class="check-row">
            <input type="checkbox" v-model="promptTestMode" />
            Test-Modus (nur 5 Fragen pro Framework)
          </label>
          <button class="btn-primary" @click="onBuildFragenPrompt" :disabled="promptBusy">
            {{ promptBusy ? 'Erstelle…' : 'Prompt(s) erstellen' }}
          </button>

          <div v-if="generatedPrompts.length > 0" class="prompts-result">
            <h4>{{ generatedPrompts.length }} Prompt(s) erstellt</h4>
            <details v-for="p in generatedPrompts" :key="p.framework" :open="generatedPrompts.length === 1">
              <summary>
                <strong>{{ p.framework }}</strong> — {{ p.section_count }} Sections
                <button class="btn-mini" @click.stop="copyPrompt(p.content)">📋 Copy</button>
              </summary>
              <textarea readonly :value="p.content" rows="20" class="prompt-textarea"></textarea>
            </details>
            <p class="hint">Kopiere den Prompt in ChatGPT. Die Antwort speicherst du dann unter "Antwort importieren".</p>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="generatePromptOpen = false">Schließen</button>
        </div>
      </div>
    </div>

    <!-- Fragen importieren -->
    <div v-if="importFragenOpen" class="modal-overlay" @click.self="importFragenOpen = false">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>📥 ChatGPT-Antwort importieren</h3>
          <button class="btn-close" @click="importFragenOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">Kopiere die JSON-Antwort von ChatGPT in das Feld unten.</p>
          <textarea v-model="importRaw" rows="14" class="prompt-textarea"
                    placeholder='[{"framework":"NIS2","section_ref":"Art. 21","thema":"...","frage":"..."}]'></textarea>
          <label class="check-row">
            <input type="checkbox" v-model="importReplace" />
            Bestehende Fragen ersetzen (sonst anhängen)
          </label>
          <span v-if="importResult" class="hint" :class="{ ok: importResult.ok }">{{ importResult.msg }}</span>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="importFragenOpen = false">Abbrechen</button>
          <button class="btn-primary" @click="onImportFragen" :disabled="!importRaw || importBusy">
            {{ importBusy ? 'Importiere…' : 'Importieren' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Frage editieren / Neu -->
    <div v-if="editingFrage || newFrageOpen" class="modal-overlay" @click.self="closeFrageEditor">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>{{ editingFrage ? 'Frage bearbeiten' : 'Neue Frage' }}</h3>
          <button class="btn-close" @click="closeFrageEditor">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Framework</label>
            <select v-model="frageEditor.framework">
              <option v-for="fw in store.selectedProjektObj?.frameworks || []" :key="fw" :value="fw">{{ fw }}</option>
            </select>
          </div>
          <div class="form-row">
            <label>Section-Referenz</label>
            <input v-model="frageEditor.section_ref" placeholder="z.B. Art. 21 Abs. 2" />
          </div>
          <div class="form-row">
            <label>Thema</label>
            <input v-model="frageEditor.thema" placeholder="z.B. Lieferantenrisiko" />
          </div>
          <div class="form-row">
            <label>Frage *</label>
            <textarea v-model="frageEditor.frage" rows="3"></textarea>
          </div>
          <div class="form-row">
            <label>Antwort</label>
            <textarea v-model="frageEditor.antwort" rows="4"></textarea>
          </div>
          <div class="form-row">
            <label>Bewertung</label>
            <select v-model="frageEditor.bewertung">
              <option value="">— wählen —</option>
              <option value="ja">Ja (umgesetzt)</option>
              <option value="teilweise">Teilweise</option>
              <option value="nein">Nein (nicht umgesetzt)</option>
              <option value="unklar">Unklar</option>
              <option value="nicht_anwendbar">Nicht anwendbar</option>
            </select>
          </div>
          <div class="form-row">
            <label>Kommentar</label>
            <textarea v-model="frageEditor.kommentar" rows="2"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="closeFrageEditor">Abbrechen</button>
          <button class="btn-primary" @click="onSaveFrage" :disabled="!frageEditor.frage">Speichern</button>
        </div>
      </div>
    </div>

    <!-- Gutachten importieren -->
    <div v-if="importGutachtenOpen" class="modal-overlay" @click.self="importGutachtenOpen = false">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>📥 Gutachten-JSON importieren</h3>
          <button class="btn-close" @click="importGutachtenOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">ChatGPT-Antwort (JSON-Objekt) hier einfügen.</p>
          <textarea v-model="gutachtenRaw" rows="14" class="prompt-textarea"
                    placeholder='{"gesamtbewertung":"...","zusammenfassung":"...","empfehlungen":[...],"fazit":"..."}'></textarea>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="importGutachtenOpen = false">Abbrechen</button>
          <button class="btn-primary" @click="onImportGutachten" :disabled="!gutachtenRaw">Importieren</button>
        </div>
      </div>
    </div>

    <!-- Gutachten-Prompt anzeigen -->
    <div v-if="gutachtenPromptText" class="modal-overlay" @click.self="gutachtenPromptText = ''">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>🤖 Gutachten-Prompt für ChatGPT</h3>
          <button class="btn-close" @click="gutachtenPromptText = ''">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">Kopiere diesen Prompt in ChatGPT. Die JSON-Antwort dann unter "Antwort importieren".</p>
          <button class="btn-mini" @click="copyPrompt(gutachtenPromptText)">📋 Copy</button>
          <textarea readonly :value="gutachtenPromptText" rows="20" class="prompt-textarea"></textarea>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="gutachtenPromptText = ''">Schließen</button>
        </div>
      </div>
    </div>

    <!-- Projekt bearbeiten -->
    <div v-if="editProjektOpen" class="modal-overlay" @click.self="editProjektOpen = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Projekt bearbeiten</h3>
          <button class="btn-close" @click="editProjektOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Frameworks</label>
            <div class="fw-checks">
              <label v-for="fw in availableFrameworks" :key="fw" class="check-row">
                <input type="checkbox" :value="fw"
                       :checked="(editForm.frameworks || []).includes(fw)"
                       @change="toggleFw(editForm, fw, $event)" />
                <strong>{{ fw }}</strong>
                <span class="muted">{{ store.sectionsCount[fw] || 0 }}</span>
              </label>
            </div>
          </div>
          <div class="form-row">
            <label>Prüfungsfokus</label>
            <textarea v-model="editForm.pruefungsfokus" rows="3"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="editProjektOpen = false">Abbrechen</button>
          <button class="btn-primary" @click="onUpdateProjekt">Speichern</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, reactive } from 'vue'
import { useGutachtenStore, type GutachtenFrage } from '../../stores/gutachten'
import { useKundenStore } from '../../stores/kunden'
import KundeSelector from '../../components/shared/KundeSelector.vue'
import DownloadButton from '../../components/shared/DownloadButton.vue'
import ImportButton from '../../components/shared/ImportButton.vue'
import apiClient from '../../api/client'

const store = useGutachtenStore()
const kundenStore = useKundenStore()

const tabs = [
  { id: 'overview', label: '📋 Übersicht' },
  { id: 'fragen', label: '❓ Fragen' },
  { id: 'gutachten', label: '📄 Gutachten' },
]
const activeTab = ref<'overview' | 'fragen' | 'gutachten'>('overview')

const availableFrameworks = computed(() => Object.keys(store.sectionsCount).sort())
const totalSectionsAvail = computed(() => {
  const fws = store.selectedProjektObj?.frameworks || []
  return fws.reduce((sum, fw) => sum + (store.sectionsCount[fw] || 0), 0)
})

// Projekt-Anlegen / Bearbeiten
const creating = ref(false)
const newForm = reactive({ name: '', frameworks: [] as string[], pruefungsfokus: '', unternehmen: '' })
const editProjektOpen = ref(false)
const editForm = reactive({ frameworks: [] as string[], pruefungsfokus: '' })

const startNew = () => {
  newForm.name = ''
  newForm.frameworks = []
  newForm.pruefungsfokus = ''
  newForm.unternehmen = ''
  creating.value = true
  if (kundenStore.kunden.length === 0) kundenStore.fetchKunden()
}

const onCreate = async () => {
  const created = await store.createProjekt(newForm)
  if (created) {
    store.selectedProjekt = created.name
    creating.value = false
  }
}

const onUpdateProjekt = async () => {
  if (!store.selectedProjekt) return
  await store.updateProjekt(store.selectedProjekt, {
    frameworks: editForm.frameworks,
    pruefungsfokus: editForm.pruefungsfokus,
  })
  editProjektOpen.value = false
}

// Issue #436: Kunde des Projekts nachtraeglich aendern
const reassignSaving = ref(false)
const reassignMsg = ref<{ ok: string; err: string }>({ ok: '', err: '' })
const onReassignKunde = async (newKunde: string) => {
  if (!store.selectedProjekt) return
  reassignSaving.value = true
  reassignMsg.value = { ok: '', err: '' }
  try {
    await store.updateProjekt(store.selectedProjekt, { unternehmen: newKunde } as any)
    await store.fetchProjekte()
    reassignMsg.value.ok = newKunde ? `✓ Kunde geändert auf „${newKunde}"` : '✓ Kundenzuordnung entfernt'
    setTimeout(() => { reassignMsg.value = { ok: '', err: '' } }, 4000)
  } catch (e: any) {
    reassignMsg.value.err = e?.response?.data?.error || 'Fehler beim Speichern'
  } finally {
    reassignSaving.value = false
  }
}

const confirmDelete = async () => {
  if (!store.selectedProjekt) return
  if (!confirm(`Projekt "${store.selectedProjekt}" wirklich löschen? (Inkl. aller Fragen)`)) return
  await store.deleteProjekt(store.selectedProjekt)
}

const toggleFw = (target: any, fw: string, e: Event) => {
  const checked = (e.target as HTMLInputElement).checked
  if (!Array.isArray(target.frameworks)) target.frameworks = []
  if (checked && !target.frameworks.includes(fw)) target.frameworks.push(fw)
  else if (!checked) target.frameworks = target.frameworks.filter((f: string) => f !== fw)
}

// Fragen
const fragenSearch = ref('')
const fragenFilterFw = ref('')
const fragenFrameworks = computed(() => {
  const set = new Set<string>()
  store.fragen.forEach(f => f.framework && set.add(f.framework))
  return Array.from(set).sort()
})

const visibleFragen = computed(() => {
  let list = store.fragen
  if (fragenFilterFw.value) list = list.filter(f => f.framework === fragenFilterFw.value)
  if (fragenSearch.value) {
    const q = fragenSearch.value.toLowerCase()
    list = list.filter(f =>
      f.frage.toLowerCase().includes(q) ||
      (f.thema || '').toLowerCase().includes(q) ||
      (f.section_ref || '').toLowerCase().includes(q),
    )
  }
  return list
})

const answeredCount = computed(() => store.fragen.filter(f => f.antwort?.trim()).length)
const answeredPct = computed(() => {
  if (store.fragen.length === 0) return 0
  return Math.round((answeredCount.value / store.fragen.length) * 100)
})

const bewertungClass = (b: string): string => {
  const v = (b || '').toLowerCase()
  if (v === 'ja' || v === 'voll' || v === 'erfuellt') return 'ok'
  if (v === 'teilweise') return 'partial'
  if (v === 'nein' || v === 'nicht_erfuellt') return 'bad'
  return 'unknown'
}

// Frage-Editor
const editingFrage = ref<GutachtenFrage | null>(null)
const newFrageOpen = ref(false)
const frageEditor = reactive<Partial<GutachtenFrage>>({
  framework: '', section_ref: '', thema: '', frage: '', antwort: '', bewertung: '', kommentar: '',
})

const editFrage = (f: GutachtenFrage) => {
  editingFrage.value = f
  Object.assign(frageEditor, f)
}

const closeFrageEditor = () => {
  editingFrage.value = null
  newFrageOpen.value = false
  Object.assign(frageEditor, { framework: '', section_ref: '', thema: '', frage: '', antwort: '', bewertung: '', kommentar: '' })
}

const onSaveFrage = async () => {
  if (!frageEditor.frage || !store.selectedProjekt) return
  if (editingFrage.value) {
    await store.updateFrage(editingFrage.value.id, { ...frageEditor })
  } else {
    await store.addFrage(store.selectedProjekt, { ...frageEditor })
  }
  closeFrageEditor()
}

const onDeleteFrage = async (id: number) => {
  if (!confirm('Diese Frage wirklich löschen?')) return
  await store.deleteFrage(id)
}

const onExcelImported = async () => {
  if (store.selectedProjekt) await store.fetchFragen(store.selectedProjekt)
}

// Prompt-Generierung
const generatePromptOpen = ref(false)
const promptBatchSize = ref(15)
const promptTestMode = ref(false)
const promptBusy = ref(false)
const generatedPrompts = ref<any[]>([])

const onBuildFragenPrompt = async () => {
  if (!store.selectedProjekt) return
  promptBusy.value = true
  generatedPrompts.value = []
  const res = await store.buildFragenPrompt(store.selectedProjekt, promptBatchSize.value, promptTestMode.value)
  if (res) generatedPrompts.value = res.prompts || []
  promptBusy.value = false
}

const copyPrompt = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    alert('In Zwischenablage kopiert.')
  } catch {
    alert('Konnte nicht kopieren — Text manuell markieren.')
  }
}

// Fragen importieren
const importFragenOpen = ref(false)
const importRaw = ref('')
const importReplace = ref(false)
const importBusy = ref(false)
const importResult = ref<{ ok: boolean; msg: string } | null>(null)

const onImportFragen = async () => {
  if (!importRaw.value || !store.selectedProjekt) return
  importBusy.value = true
  importResult.value = null
  const r = await store.importFragen(store.selectedProjekt, importRaw.value, importReplace.value)
  if (r) {
    importResult.value = { ok: true, msg: `${r.imported} Fragen importiert.` }
    importRaw.value = ''
    setTimeout(() => importFragenOpen.value = false, 1500)
  } else {
    importResult.value = { ok: false, msg: store.error || 'Import fehlgeschlagen' }
  }
  importBusy.value = false
}

// Gutachten
const gutachtenPromptText = ref('')
const importGutachtenOpen = ref(false)
const gutachtenRaw = ref('')
const exporting = ref(false)

const onBuildGutachtenPrompt = async () => {
  if (!store.selectedProjekt) return
  const r = await store.buildGutachtenPrompt(store.selectedProjekt)
  if (r) gutachtenPromptText.value = r.prompt
}

const onImportGutachten = async () => {
  if (!gutachtenRaw.value || !store.selectedProjekt) return
  const r = await store.importGutachten(store.selectedProjekt, gutachtenRaw.value)
  if (r) {
    importGutachtenOpen.value = false
    gutachtenRaw.value = ''
  }
}

const downloadGutachten = async () => {
  if (!store.selectedProjekt || !store.draftPayload) return
  exporting.value = true
  try {
    const res = await apiClient.post(
      `/gutachten/${encodeURIComponent(store.selectedProjekt)}/gutachten/export`,
      store.draftPayload,
      { responseType: 'blob', timeout: 120000 },
    )
    const blob = res.data as Blob
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `Gutachten_${store.selectedProjekt}.docx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    store.error = e?.response?.data?.error || e.message || 'Export fehlgeschlagen'
  } finally {
    exporting.value = false
  }
}

// Auf Projekt-Wechsel reagieren
const onProjektChange = async (n: string | null) => {
  if (!n) return
  await Promise.all([
    store.fetchFragen(n),
    store.fetchDraft(n),
  ])
  // editForm vorbefüllen
  const p = store.selectedProjektObj
  if (p) {
    editForm.frameworks = [...(p.frameworks || [])]
    editForm.pruefungsfokus = p.pruefungsfokus || ''
  }
}

watch(() => store.selectedProjekt, onProjektChange, { immediate: false })

onMounted(async () => {
  await store.fetchSectionsCount()
  await store.fetchProjekte()
  if (!store.selectedProjekt && store.projekte.length > 0) {
    store.selectedProjekt = store.projekte[0].name
  }
  if (store.selectedProjekt) await onProjektChange(store.selectedProjekt)
})
</script>

<style scoped>
.gutachten-view { max-width: 1500px; }

.header { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border); }
.header h2 { margin: 0; font-size: 22px; }
.header p { margin: 2px 0 0; color: var(--color-text-secondary); font-size: 13px; }

.alert-error {
  background: #ffebee; color: #c62828; padding: 10px; border-radius: 4px;
  margin-bottom: 12px; border: 1px solid #ef5350; cursor: pointer;
}

.empty-state { background: var(--color-surface); padding: 32px; border-radius: 8px; border: 1px solid var(--color-border); text-align: center; }
.empty-state h3 { margin: 0 0 12px; }
.empty-state p { color: var(--color-text-secondary); margin-bottom: 20px; }
.proj-list { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-bottom: 24px; }
.proj-tile {
  background: var(--color-background); border: 1px solid var(--color-border);
  padding: 12px 20px; border-radius: 6px; cursor: pointer;
  display: flex; flex-direction: column; gap: 4px; min-width: 220px;
}
.proj-tile:hover { background: var(--color-border); border-color: var(--color-primary); }
.proj-tile strong { font-size: 15px; }
.proj-fw { font-size: 11px; color: var(--color-text-secondary); }

.proj-selector { display: flex; gap: 8px; align-items: center; margin-bottom: 16px; }
.proj-selector select { flex: 1; padding: 8px; border: 1px solid var(--color-border); border-radius: 4px; }

.form-card { background: var(--color-surface); padding: 24px; border-radius: 8px; border: 1px solid var(--color-border); max-width: 700px; }
.form-card h3 { margin: 0 0 16px; }
.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input, .form-row select, .form-row textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 4px;
  font-size: 13px; background: var(--color-surface); color: var(--color-text-primary);
}
.form-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }

.fw-checks { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; }
.check-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; cursor: pointer; }
.muted { color: var(--color-text-secondary); font-size: 12px; }

.tabs { display: flex; gap: 0; border-bottom: 2px solid var(--color-border); margin-bottom: 16px; }
.tab-btn {
  background: none; border: none; padding: 10px 20px; cursor: pointer;
  font-size: 14px; color: var(--color-text-secondary);
  border-bottom: 3px solid transparent; margin-bottom: -2px;
  display: inline-flex; gap: 6px; align-items: center;
}
.tab-btn:hover { color: var(--color-primary); }
.tab-btn.active { color: var(--color-primary); border-bottom-color: var(--color-primary); font-weight: 600; }
.badge {
  background: var(--color-primary); color: #fff; padding: 1px 8px; border-radius: 10px;
  font-size: 11px; font-weight: 600;
}

.tab-content { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 8px; padding: 20px; }

.stat-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px; margin-bottom: 16px;
}
.stat-card {
  background: var(--color-background); padding: 16px; border-radius: 6px; text-align: center;
  border: 1px solid var(--color-border);
}
.stat-num { font-size: 32px; font-weight: 700; color: var(--color-primary); }
.stat-lbl { font-size: 12px; color: var(--color-text-secondary); }

.info-card {
  background: var(--color-background); padding: 14px 18px; border-radius: 6px;
  margin-bottom: 12px;
}
.info-card h4 { margin: 0 0 8px; font-size: 14px; }
.info-card ol { margin: 0; padding-left: 20px; line-height: 1.6; }
.info-card p { margin: 0; }

.fragen-toolbar {
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
  margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border);
}
.search-input { padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; flex: 1; min-width: 180px; }

.fragen-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.fragen-table th { text-align: left; padding: 8px; background: var(--color-background); font-weight: 600; border-bottom: 1px solid var(--color-border); }
.fragen-table td { padding: 8px; border-bottom: 1px solid var(--color-border); vertical-align: top; }
.fragen-table tr:hover { background: var(--color-background); }
.fw-tag { font-family: monospace; font-size: 11px; padding: 2px 6px; background: var(--color-background); border-radius: 3px; }
.ref { font-size: 11px; }
.thema-cell { max-width: 180px; }
.frage-cell { max-width: 600px; }
.antwort-text { margin: 6px 0 0; padding: 6px 10px; background: var(--color-background); border-left: 3px solid var(--color-success); border-radius: 4px; font-size: 12px; }

.bw-pill { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.bw-pill.ok { background: #e8f5e9; color: #2e7d32; }
.bw-pill.partial { background: #fff3e0; color: #e65100; }
.bw-pill.bad { background: #ffebee; color: #c62828; }
.bw-pill.unknown { background: var(--color-background); color: var(--color-text-secondary); }

.btn-icon { background: none; border: none; cursor: pointer; padding: 4px 6px; font-size: 14px; }
.btn-icon:hover { background: var(--color-background); border-radius: 4px; }

.empty { padding: 32px; text-align: center; color: var(--color-text-secondary); }

.gutachten-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.gutachten-preview { background: var(--color-background); padding: 16px; border-radius: 6px; }
.gutachten-preview h3 { margin: 0 0 12px; }
.gutachten-preview details { margin-bottom: 8px; padding: 8px 12px; background: var(--color-surface); border-radius: 4px; }
.gutachten-preview summary { cursor: pointer; font-weight: 600; }
.gutachten-preview p, .gutachten-preview ul, .gutachten-preview ol { margin: 8px 0 0; }

/* Modals */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal-content {
  background: var(--color-surface); border-radius: 8px; max-width: 600px; width: 90%;
  max-height: 90vh; overflow: hidden; display: flex; flex-direction: column;
}
.modal-content.modal-wide { max-width: 1000px; }
.modal-header {
  background: var(--color-primary); color: #fff;
  padding: 14px 20px; display: flex; justify-content: space-between; align-items: center;
}
.modal-header h3 { margin: 0; font-size: 16px; }
.btn-close { background: none; border: none; color: #fff; font-size: 22px; cursor: pointer; }
.modal-body { padding: 20px; overflow-y: auto; flex: 1; }
.modal-footer {
  padding: 12px 20px; border-top: 1px solid var(--color-border);
  display: flex; gap: 8px; justify-content: flex-end;
}
.prompt-textarea {
  width: 100%; font-family: monospace; font-size: 12px; padding: 10px;
  border: 1px solid var(--color-border); border-radius: 4px;
  background: var(--color-background); color: var(--color-text-primary);
}
.prompts-result { margin-top: 16px; }
.prompts-result details { margin-bottom: 8px; background: var(--color-background); padding: 8px 12px; border-radius: 4px; }
.btn-mini {
  background: var(--color-background); border: 1px solid var(--color-border);
  padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 11px;
  margin-left: 8px;
}
.hint { font-size: 12px; color: var(--color-text-secondary); }
.hint.ok { color: var(--color-success); }

.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: 500; }
.btn-primary:hover:not(:disabled) { background: var(--color-primary-dark); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: var(--color-background); color: var(--color-primary); border: 1px solid var(--color-border); padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-secondary:hover { background: var(--color-border); }
.btn-danger { background: #ffebee; color: #c62828; border: 1px solid #ef5350; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-danger:hover { background: #ffcdd2; }
.btn-success { background: #2e7d32; color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: 500; }
.btn-success:hover:not(:disabled) { background: #1b5e20; }
</style>
