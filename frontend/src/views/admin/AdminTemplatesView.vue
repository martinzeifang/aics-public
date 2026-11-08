<template>
  <div class="templates-view">
    <div class="header">
      <h2>{{ $t('admin.adminTemplatesView.wordVorlagen') }}</h2>
      <p>{{ $t('admin.adminTemplatesView.zentraleVorlagenVerwaltungFurCRANIS2') }}</p>
      <span :class="['soffice', store.sofficeAvailable ? 'on' : 'off']">
        {{ $t('admin.adminTemplatesView.pDFExportV0', { v0: store.sofficeAvailable ? $t('admin.adminTemplatesView.verfugbar') : $t('admin.adminTemplatesView.nichtVerfugbar') }) }}
      </span>
    </div>

    <FehlerHinweis :text="store.error" @close="store.error = ''" />
    <!-- #1741: Ergebnis der Variablen-Prüfung direkt nach dem Upload. Hochladen
         bleibt erlaubt (eine Vorlage darf in Arbeit sein) — „Als Standard" nicht. -->
    <div v-if="pruefWarnung" class="alert alert-warn" @click="pruefWarnung = ''">
      {{ pruefWarnung }}
    </div>

    <div class="toolbar">
      <label class="tb-label">{{ $t('common.modul') }}</label>
      <select v-model="selectedModul" class="select" @change="onModulChange">
        <option v-for="m in MODULE" :key="m.id" :value="m.id">{{ m.label }}</option>
      </select>
      <button class="btn-secondary" @click="reload">{{ $t('admin.adminTemplatesView.neuLaden') }}</button>

      <!-- B1 (#1092): Variablen-Hilfe pro Modul (vor dem Vorlagen-Upload) -->
      <span class="vars-help-group">
        <select v-model="varsModul" class="select" :title="$t('admin.adminTemplatesView.modulFurDieVariablenliste')">
          <option v-for="m in MODULE" :key="m.id" :value="m.id">{{ m.label }}</option>
        </select>
        <button class="btn-secondary" @click="openVarsHelp">{{ $t('admin.adminTemplatesView.variablenliste') }}</button>
      </span>
    </div>

    <table v-if="store.templates.length > 0" class="data-table">
      <thead>
        <tr>
          <th>{{ $t('common.name') }}</th>
          <th>{{ $t('common.version') }}</th>
          <th>{{ $t('admin.adminTemplatesView.bericht') }}</th>
          <th>{{ $t('common.firma') }}</th>
          <th>{{ $t('common.standard') }}</th>
          <th>{{ $t('admin.adminTemplatesView.variablen') }}</th>
          <th>{{ $t('admin.adminTemplatesView.hochgeladen') }}</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in store.templates" :key="t.id">
          <td><strong>{{ t.name }}</strong></td>
          <td>{{ t.version }}</td>
          <!-- #1777: Eine Vorlage gilt für EINEN Bericht; „alle Berichte" ist
               weiterhin möglich, aber jetzt eine sichtbare Aussage. -->
          <td class="small">{{ berichtLabel(t.bericht_typ) }}</td>
          <!-- #1778: Haus-Vorlage oder Mandantenvorlage. -->
          <td class="small">{{ t.firma || (t.firmen_id ? `#${t.firmen_id}` : $t('admin.adminTemplatesView.haus')) }}</td>
          <td>
            <span v-if="t.ist_default" class="badge-default">{{ $t('common.standard') }}</span>
            <button v-else class="btn-link" @click="onSetDefault(t)">{{ $t('common.alsStandard') }}</button>
          </td>
          <td>
            {{ (t.variablen || []).length }}
            <!-- #1741: fremde Vorlage sofort sichtbar, nicht erst im kaputten Export -->
            <span v-if="t.pruefung && !t.pruefung.ok" class="badge-warn"
                  :title="t.pruefung.meldung">{{ $t('admin.adminTemplatesView.fremdesModul') }}</span>
          </td>
          <td class="small">{{ formatDate(t.hochgeladen_am) }} · {{ t.hochgeladen_von || '—' }}</td>
          <td class="actions">
            <button class="btn-icon" @click="openMapping(t)" :title="$t('admin.adminTemplatesView.variablenMapping')">🔗</button>
            <button class="btn-icon" @click="openExport(t)" :title="$t('admin.adminTemplatesView.testExport')">⬇️</button>
            <button class="btn-icon" @click="onDelete(t)" :title="$t('common.delete')">🗑️</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else-if="!store.loading" class="empty">{{ $t('admin.adminTemplatesView.keineVorlagenFurDiesesModul') }}</div>
    <div v-if="store.loading" class="loading">{{ $t('admin.adminTemplatesView.ladeVorlagen') }}</div>

    <!-- Upload -->
    <fieldset class="fset upload">
      <legend>{{ $t('admin.adminTemplatesView.neueVorlageHochladen') }}</legend>
      <div class="form-grid">
        <div class="form-row">
          <label>{{ $t('admin.adminTemplatesView.dateiDOCXDOTX') }}</label>
          <input type="file" accept=".docx,.dotx" @change="onFileChange" ref="fileInput" />
        </div>
        <div class="form-row">
          <label>{{ $t('common.name') }}</label>
          <input v-model="uploadName" placeholder="z.B. CRA-Standardbericht" />
        </div>
        <div class="form-row">
          <label>{{ $t('admin.adminTemplatesView.furWelchenBericht') }}</label>
          <select v-model="uploadBerichtTyp" class="select">
            <option value="">{{ $t('admin.adminTemplatesView.alleBerichteDesModuls') }}</option>
            <!-- #1997: Zwei getrennte Schlüsselräume. Ein Bericht bekommt den
                 Modul-Kontext, ein Dokument einen anderen — in einer Liste
                 vermischt wäre die Auswahl eine Einladung zur Verwechslung,
                 und die endet in einem Dokument mit leeren Feldern (#1777). -->
            <optgroup :label="$t('admin.adminTemplatesView.gruppeBerichte')">
              <option v-for="b in berichte" :key="b.key" :value="b.key">
                {{ b.titel }}{{ b.vorgeschrieben ? $t('admin.adminTemplatesView.aufbauVorgegeben') : '' }}
              </option>
            </optgroup>
            <optgroup v-if="dokumente.length" :label="$t('admin.adminTemplatesView.gruppeDokumente')">
              <option v-for="d in dokumente" :key="d.key" :value="d.key">
                {{ d.titel }}
              </option>
            </optgroup>
          </select>
          <small class="hint">
            {{ $t('admin.adminTemplatesView.einStandardWirktNurAufDenGewahltenBe') }}
          </small>
          <small v-if="istDokumentBereich" class="hint hint-dokument">
            {{ $t('admin.adminTemplatesView.dokumentVorlageHinweis') }}
            <code>{{ INHALT_VARIABLE }}</code>
            {{ $t('admin.adminTemplatesView.dokumentVorlageVariablen') }}
            <span class="dok-vars">
              <code v-for="v in dokumentVariablen" :key="v.key">{{ v.key }}</code>
            </span>
          </small>
        </div>
        <div class="form-row">
          <label>{{ $t('admin.adminTemplatesView.furWelchenMandanten') }}</label>
          <select v-model="uploadFirmenId" class="select">
            <option :value="0">{{ $t('admin.adminTemplatesView.hausVorlageAlleMandanten') }}</option>
            <option v-for="f in firmen" :key="f.id" :value="f.id">{{ f.name }}</option>
          </select>
          <small class="hint">
            {{ $t('admin.adminTemplatesView.konformitatserklarungNachweisUndKund') }}
          </small>
        </div>
        <div class="form-row form-row-wide">
          <label>{{ $t('common.notizen') }}</label>
          <input v-model="uploadNotizen" placeholder="optional" />
        </div>
      </div>
      <button class="btn-primary" :disabled="!canUpload || uploading" @click="onUpload">
        {{ uploading ? $t('admin.adminTemplatesView.ladeHoch') : $t('admin.adminTemplatesView.hochladen') }}
      </button>
    </fieldset>

    <!-- Mapping Modal -->
    <div v-if="mappingTpl" class="modal-overlay" @mousedown.self="closeMapping">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>{{ $t('admin.adminTemplatesView.variablenMappingV0', { v0: mappingTpl.name }) }}</h3>
          <button class="btn-close" @click="closeMapping">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">
            {{ $t('admin.adminTemplatesView.ordneJedeInDerVorlageErkannteVariabl') }}
          </p>
          <div v-if="(mappingTpl.variablen || []).length === 0" class="empty">
            {{ $t('admin.adminTemplatesView.keinePlatzhalterInDieserVorlageErkan') }}
          </div>
          <table v-else class="map-table">
            <thead>
              <tr>
                <th>{{ $t('admin.adminTemplatesView.erkannteVariable') }}</th>
                <th>{{ $t('admin.adminTemplatesView.datenfeldSchema') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="v in mappingTpl.variablen" :key="v">
                <td><code>{{ v }}</code></td>
                <td>
                  <select v-model="mappingDraft[v]" class="select">
                    <option value="">{{ $t('admin.adminTemplatesView.nichtZugeordnet') }}</option>
                    <option v-for="s in mappingTpl.schema || []" :key="s.key" :value="s.key">
                      {{ s.key }}<template v-if="s.pflicht"> *</template> — {{ s.beschreibung }}
                    </option>
                  </select>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="closeMapping">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" @click="onSaveMapping">{{ $t('common.save') }}</button>
        </div>
      </div>
    </div>

    <!-- Export Modal -->
    <div v-if="exportTpl" class="modal-overlay" @mousedown.self="exportTpl = null">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ $t('admin.adminTemplatesView.testExportV0', { v0: exportTpl.name }) }}</h3>
          <button class="btn-close" @click="exportTpl = null">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>{{ $t('common.projektname') }}</label>
            <input v-model="exportProjekt" placeholder="z.B. AICS" />
          </div>
          <div class="form-row">
            <label>{{ $t('common.format') }}</label>
            <div class="radio-row">
              <label class="check-row">
                <input type="radio" value="docx" v-model="exportFormat" /> {{ $t('admin.adminTemplatesView.dOCX') }}
              </label>
              <label class="check-row" :class="{ disabled: !store.sofficeAvailable }">
                <input type="radio" value="pdf" v-model="exportFormat" :disabled="!store.sofficeAvailable" /> {{ $t('admin.adminTemplatesView.pDF') }}
              </label>
            </div>
            <small v-if="!store.sofficeAvailable" class="hint">
              {{ $t('admin.adminTemplatesView.pDFExportNichtVerfugbarLibreOfficeSo') }}
            </small>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="exportTpl = null">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="!exportProjekt || exporting" @click="onExport">
            {{ exporting ? $t('admin.adminTemplatesView.exportiere') : $t('admin.adminTemplatesView.exportieren') }}
          </button>
        </div>
      </div>
    </div>

    <!-- B1 (#1092): Variablen-Hilfe-Modal (kopierbare Tokens je Modul) -->
    <div v-if="varsOpen" class="modal-overlay" @mousedown.self="varsOpen = false">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>{{ $t('admin.adminTemplatesView.verfugbareVariablenV0', { v0: varsModulLabel }) }}</h3>
          <button class="btn-close" @click="varsOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">
            {{ $t('admin.adminTemplatesView.fugeDiePlatzhalterKlickKopierenInDei') }}
          </p>
          <div v-if="varsLoading" class="loading">{{ $t('admin.adminTemplatesView.ladeVariablen') }}</div>
          <div v-else-if="varsSchema.length === 0" class="empty">
            {{ $t('admin.adminTemplatesView.keineVariablenFurDiesesModul') }}
          </div>
          <table v-else class="map-table">
            <thead>
              <tr>
                <th>{{ $t('admin.adminTemplatesView.token') }}</th>
                <th>{{ $t('common.typ') }}</th>
                <th>{{ $t('common.description') }}</th>
                <th>{{ $t('common.pflicht') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in varsSchema" :key="s.key">
                <td>
                  <code class="copy-token" :title="`„${tokenFor(s)}“ kopieren`" @click="copyToken(s)">{{ tokenFor(s) }}</code>
                </td>
                <td>{{ s.typ }}</td>
                <td>{{ s.beschreibung }}</td>
                <td>{{ s.pflicht ? '✓' : '' }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="varsCopyMsg" class="hint copy-msg">{{ varsCopyMsg }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="varsOpen = false">{{ $t('common.close') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { useTemplatesStore, type WordTemplate, type TemplateSchemaEntry,
         type BerichtTyp, type VorlagenVariable } from '../../stores/templates'
import apiClient from '../../api/client'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'
// `t` ist in dieser Maske schon belegt (lokale Variable/Parameter) —
// deshalb unter anderem Namen. Ein Import überdeckt eine lokale
// Bindung nicht, er kollidiert mit ihr: Der Aufruf trifft die
// Variable, und die ist keine Funktion. Gefunden hat das der
// Typprüfer (#1858), nicht der Build.
import { t as uebersetze } from '../../i18n'

// Muss jedes Modul aus shared/templates/schema.py `_ADAPTERS` enthalten (#1731):
// WiBA hatte einen Adapter, fehlte aber hier und in der REST-Schicht —
// ihre Vorlagen liessen sich dadurch weder hochladen noch rendern.
const MODULE = [
  { id: 'cra', label: uebersetze('nav.cra.label') },
  { id: 'nis2', label: 'NIS2' },
  { id: 'aiact', label: 'AI Act' },
  { id: 'dsgvo', label: uebersetze('nav.dsgvo.label') },
  { id: 'risikobewertung', label: uebersetze('nav.risikobewertung.label') },
  { id: 'wiba', label: uebersetze('nav.wiba.label') },
  { id: 'compliance_audit', label: uebersetze('nav.compliance-audit.label') },
]

const store = useTemplatesStore()

const selectedModul = ref<string>('cra')

// Upload
const fileInput = ref<HTMLInputElement | null>(null)
const uploadFile = ref<File | null>(null)
const uploadName = ref('')
const uploadNotizen = ref('')
// #1777/#1778: Für welchen Bericht und welchen Mandanten gilt die Vorlage?
const uploadBerichtTyp = ref('')
const uploadFirmenId = ref(0)
const berichte = ref<BerichtTyp[]>([])
// #1997: Dokument-Geltungsbereiche und die Variablen ihres Kontexts.
//
// Die Pflichtvariable steht als Konstante und nicht als Literal im Template:
// Der Vue-Compiler liest `{{ '...' }}` mit geschweiften Klammern darin als Ende
// der Interpolation und bricht mit „Unterminated string constant" ab. `vue-tsc`
// beanstandet das nicht — gefunden hat es erst `npm run build`.
const INHALT_VARIABLE = '{' + '{ inhalt }' + '}'
const dokumente = ref<BerichtTyp[]>([])
const dokumentVariablen = ref<VorlagenVariable[]>([])
const istDokumentBereich = computed(() =>
  uploadBerichtTyp.value === 'dokument' || uploadBerichtTyp.value.startsWith('dokument:'))
const firmen = ref<Array<{ id: number; name: string }>>([])
const uploading = ref(false)
const canUpload = computed(() => !!uploadFile.value && uploadName.value.trim().length > 0)
// #1741: Klartext statt stillem Ausfall im Modul-Export.
const pruefWarnung = ref('')

// Mapping
const mappingTpl = ref<WordTemplate | null>(null)
const mappingDraft = reactive<Record<string, string>>({})

// Export
const exportTpl = ref<WordTemplate | null>(null)
const exportProjekt = ref('')
const exportFormat = ref<'docx' | 'pdf'>('docx')
const exporting = ref(false)

// B1 (#1092): Variablen-Hilfe
const varsModul = ref<string>('cra')
const varsOpen = ref(false)
const varsLoading = ref(false)
const varsSchema = ref<TemplateSchemaEntry[]>([])
const varsCopyMsg = ref('')
const varsModulLabel = computed(() =>
  MODULE.find(m => m.id === varsModul.value)?.label || varsModul.value,
)
const tokenFor = (s: TemplateSchemaEntry): string => `{{ ${s.key} }}`

const openVarsHelp = async () => {
  varsCopyMsg.value = ''
  varsOpen.value = true
  varsLoading.value = true
  try {
    varsSchema.value = await store.fetchSchemaForModul(varsModul.value)
  } finally {
    varsLoading.value = false
  }
}

const copyToken = async (s: TemplateSchemaEntry) => {
  const token = tokenFor(s)
  try {
    await navigator.clipboard.writeText(token)
    varsCopyMsg.value = `✓ „${token}" in die Zwischenablage kopiert`
  } catch {
    varsCopyMsg.value = '⚠ Kopieren nicht möglich — bitte manuell markieren'
  }
}

const formatDate = (s?: string | null): string => {
  if (!s) return '—'
  try { return new Date(s).toLocaleString('de-DE') } catch { return s }
}

const berichtLabel = (key?: string): string => {
  if (!key) return 'alle'
  // Dokument-Bereiche stehen in ihrer eigenen Liste (#1997); ohne sie zeigte
  // die Tabelle den rohen Schlüssel „dokument:sbom_begleitdoc".
  return (berichte.value.find(b => b.key === key)?.titel
    || dokumente.value.find(d => d.key === key)?.titel
    || key)
}

const reload = async () => {
  await store.fetchTemplates(selectedModul.value)
  const bereiche = await store.fetchGeltungsbereiche(selectedModul.value)
  berichte.value = bereiche.berichte
  dokumente.value = bereiche.dokumente
  dokumentVariablen.value = bereiche.dokumentVariablen
}

const onModulChange = () => {
  // Ein Geltungsbereich gehört zu seinem Modul — nach dem Wechsel ist die alte
  // Auswahl keine gültige Angabe mehr. Das gilt für Berichtstypen und für
  // Dokumenttypen gleichermaßen (#1997).
  uploadBerichtTyp.value = ''
  reload()
}

const ladeFirmen = async () => {
  try {
    const res = await apiClient.get('/firmen')
    const roh = Array.isArray(res.data) ? res.data : (res.data?.items || [])
    // Die Firmenliste adressiert über den **Namen**; die numerische Kennung
    // heißt ``firmen_id`` (wie in der Benutzerverwaltung, #1185). ``f.id`` wäre
    // leer — das Auswahlfeld bliebe ohne Fehlermeldung leer.
    firmen.value = roh.map((f: any) => ({ id: f.firmen_id, name: f.name }))
                      .filter((f: any) => f.id != null)
  } catch {
    firmen.value = []   // ohne Firmenliste bleibt nur die Haus-Vorlage
  }
}

const onFileChange = (e: Event) => {
  const files = (e.target as HTMLInputElement).files
  uploadFile.value = files && files.length > 0 ? files[0] : null
  if (uploadFile.value && !uploadName.value) {
    uploadName.value = uploadFile.value.name.replace(/\.[^.]+$/, '')
  }
}

const onUpload = async () => {
  if (!uploadFile.value) return
  uploading.value = true
  try {
    const res = await store.uploadTemplate(
      selectedModul.value,
      uploadName.value.trim(),
      uploadFile.value,
      uploadNotizen.value.trim() || undefined,
      uploadBerichtTyp.value || undefined,
      uploadFirmenId.value || null,
    )
    if (res) {
      pruefWarnung.value = res.pruefung && !res.pruefung.ok
        ? `${res.pruefung.meldung} Die Vorlage ist hochgeladen, lässt sich aber `
          + uebersetze('admin.adminTemplatesView.nichtAlsStandardSetzenSolangeDieseVa')
        : ''
      uploadFile.value = null
      uploadName.value = ''
      uploadNotizen.value = ''
      if (fileInput.value) fileInput.value.value = ''
      await reload()
    }
  } finally {
    uploading.value = false
  }
}

const onSetDefault = async (t: WordTemplate) => {
  const ok = await store.setDefault(t.id)
  if (ok) await reload()
}

const onDelete = async (t: WordTemplate) => {
  const reason = window.prompt(`Vorlage "${t.name}" löschen — bitte Begründung angeben:`)
  if (reason === null) return
  if (reason.trim().length === 0) {
    store.error = uebersetze('admin.adminTemplatesView.eineBegrundungIstErforderlich')
    return
  }
  await store.deleteTemplate(t.id, reason.trim())
}

const openMapping = async (t: WordTemplate) => {
  const full = await store.fetchTemplate(t.id)
  const tpl = full || t
  mappingTpl.value = tpl
  for (const k of Object.keys(mappingDraft)) delete mappingDraft[k]
  for (const v of tpl.variablen || []) {
    mappingDraft[v] = (tpl.mapping && tpl.mapping[v]) ? String(tpl.mapping[v]) : ''
  }
}

const closeMapping = () => {
  mappingTpl.value = null
}

const onSaveMapping = async () => {
  if (!mappingTpl.value) return
  const mapping: Record<string, string> = {}
  for (const [k, val] of Object.entries(mappingDraft)) {
    if (val) mapping[k] = val
  }
  const res = await store.saveMapping(mappingTpl.value.id, mapping)
  if (res !== null) {
    closeMapping()
    await reload()
  }
}

const openExport = (t: WordTemplate) => {
  exportTpl.value = t
  exportProjekt.value = ''
  exportFormat.value = 'docx'
}

const onExport = async () => {
  if (!exportTpl.value) return
  exporting.value = true
  try {
    const ok = await store.render(exportTpl.value.id, exportProjekt.value.trim(), exportFormat.value)
    if (ok) exportTpl.value = null
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  // Parallel: Die Firmenliste braucht nur das Upload-Formular, die
  // Vorlagenliste die Tabelle. Hintereinander geladen erscheint die Tabelle
  // sichtbar später, obwohl keine Abfrage auf die andere wartet.
  await Promise.all([store.fetchHealth(), ladeFirmen(), reload()])
})
</script>

<style scoped>
/* #1997 — Variablen des Dokument-Kontexts unter dem Auswahlfeld. */
.hint-dokument { display: block; margin-top: 4px; line-height: 1.6; }
.hint-dokument code {
  background: #f0f0f0;
  border-radius: 3px;
  padding: 1px 4px;
  margin-right: 4px;
  font-size: 0.82em;
}
.dok-vars { display: inline-flex; flex-wrap: wrap; gap: 2px; }

.templates-view { max-width: 1400px; padding: 16px; }

.header { display: flex; align-items: flex-end; gap: 16px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border); }
.header h2 { margin: 0; flex: 0 0 auto; }
.header p { flex: 1; margin: 0; color: var(--color-text-secondary); font-size: 13px; }

.soffice { padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; white-space: nowrap; }
.soffice.on { background: #e8f5e9; color: #2e7d32; }
.soffice.off { background: #fff3e0; color: #e65100; }

.alert-error {
  background: #ffebee; color: #c62828; padding: 10px; border-radius: 4px;
  margin-bottom: 12px; border: 1px solid #ef5350; cursor: pointer;
}
.alert-warn {
  background: #fff3e0; color: #e65100; padding: 10px; border-radius: 4px;
  margin-bottom: 12px; border: 1px solid #ffb74d; cursor: pointer; font-size: 13px;
}
.badge-warn {
  display: inline-block; margin-left: 8px; background: #fff3e0; color: #e65100;
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 12px;
  cursor: help;
}

.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.tb-label { font-weight: 600; font-size: 13px; }
.select {
  padding: 7px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px;
  background: var(--color-surface); color: var(--color-text-primary);
}

.empty, .loading { padding: 32px; text-align: center; color: var(--color-text-secondary); }

.data-table { width: 100%; border-collapse: collapse; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden; }
.data-table th { background: var(--color-background); text-align: left; padding: 10px 12px; font-size: 12px; font-weight: 600; border-bottom: 1px solid var(--color-border); }
.data-table td { padding: 10px 12px; border-bottom: 1px solid var(--color-border); font-size: 13px; vertical-align: middle; }
.data-table tr:hover { background: var(--color-background); }
.data-table .actions { white-space: nowrap; text-align: right; }
.small { font-size: 12px; color: var(--color-text-secondary); }

.badge-default { display: inline-block; background: #e3f2fd; color: #1565c0; font-size: 11px; font-weight: 600; padding: 2px 10px; border-radius: 12px; }
.btn-link { background: none; border: none; color: var(--color-primary); cursor: pointer; font-size: 12px; padding: 0; text-decoration: underline; }

.btn-icon { background: none; border: none; cursor: pointer; padding: 4px 6px; font-size: 14px; }
.btn-icon:hover { background: var(--color-background); border-radius: 4px; }

.fset { border: 1px solid var(--color-border); border-radius: 6px; padding: 12px 16px; margin: 20px 0; }
.fset legend { font-weight: 600; padding: 0 6px; }
.upload .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
.form-row-wide { grid-column: 1 / -1; }
.form-row { margin-bottom: 8px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input[type=text], .form-row input:not([type]), .form-row input[type=file] {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px;
  background: var(--color-surface); color: var(--color-text-primary);
}
.hint { font-size: 11px; color: var(--color-text-secondary); }

.radio-row { display: flex; gap: 20px; }
.check-row { display: flex; align-items: center; gap: 6px; font-size: 13px; cursor: pointer; }
.check-row.disabled { opacity: 0.5; cursor: not-allowed; }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: var(--color-surface); border-radius: 8px; max-width: 520px; width: 90%; max-height: 92vh; display: flex; flex-direction: column; }
.modal-wide { max-width: 760px; }
.modal-header { background: var(--color-primary); color: #fff; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; }
.modal-header h3 { margin: 0; font-size: 16px; }
.btn-close { background: none; border: none; color: #fff; font-size: 22px; cursor: pointer; }
.modal-body { padding: 20px; overflow-y: auto; flex: 1; }
.modal-footer { padding: 12px 20px; border-top: 1px solid var(--color-border); display: flex; gap: 8px; justify-content: flex-end; }

.map-table { width: 100%; border-collapse: collapse; }
.map-table th { text-align: left; padding: 8px; font-size: 12px; border-bottom: 1px solid var(--color-border); }
.map-table td { padding: 8px; border-bottom: 1px solid var(--color-background); vertical-align: middle; }
.map-table td:first-child { width: 40%; }
.map-table .select { width: 100%; }
.map-table code { background: var(--color-background); padding: 2px 6px; border-radius: 3px; font-size: 12px; }

.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-primary:hover:not(:disabled) { background: var(--color-primary-dark); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: var(--color-background); color: var(--color-primary); border: 1px solid var(--color-border); padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-secondary:hover { background: var(--color-border); }

.vars-help-group { display: inline-flex; align-items: center; gap: 8px; margin-left: auto; }
.copy-token { cursor: pointer; }
.copy-token:hover { background: var(--color-primary); color: #fff; }
.copy-msg { margin-top: 12px; color: #2e7d32; }
</style>
