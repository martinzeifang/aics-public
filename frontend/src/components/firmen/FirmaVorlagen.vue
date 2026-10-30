<!--
  Word-Vorlagen eines Mandanten (#1778).

  Warum hier und nicht nur im Admin-UI: EU-Konformitätserklärung,
  Konformitätsnachweis und Kundenfassung stellt nicht der Dienstleister aus,
  sondern der Hersteller. Die Erklärung nach Art. 28 i.V.m. Anhang V
  unterschreibt der Mandant unter seinem Namen und trägt dafür die
  Alleinverantwortung — ein Dokument, das er in eigenem Namen in Verkehr gibt,
  darf nicht im Papier des Beraters erscheinen.

  Haus-Vorlagen bleiben im Admin-Bereich; hier erscheinen sie nur als Herkunft
  („Haus"), damit man sieht, worauf ein Mandant ohne eigene Vorlage zurückfällt.
-->
<template>
  <div class="firma-vorlagen">
    <div class="fv-head">
      <h3>📄 Word-Vorlagen für {{ firma }}</h3>
      <select v-model="modul" class="select" @change="laden">
        <option v-for="m in MODULE" :key="m.id" :value="m.id">{{ m.label }}</option>
      </select>
      <button class="btn-secondary" :disabled="store.loading" @click="laden">↻ Aktualisieren</button>
    </div>

    <p class="fv-hint">
      Kundendokumente — Konformitätserklärung, Konformitätsnachweis und
      Kundenfassung — stellt der Hersteller aus. Eine hier hinterlegte Vorlage
      gilt nur für diesen Mandanten und geht der Haus-Vorlage vor. Pflichtangaben
      bleiben erzwungen: Eine Vorlage, die sie auslässt, lässt sich nicht als
      Standard setzen.
    </p>

    <FehlerHinweis :text="fehler" @close="fehler = ''" />
    <div v-if="warnung" class="alert alert-warn" @click="warnung = ''">{{ warnung }}</div>
    <p v-if="!firmenId" class="alert alert-warn">
      Diese Firma ist noch keiner Firmen-ID zugeordnet — im Admin unter
      „Firmen-Zuordnung" verknüpfen, dann sind eigene Vorlagen möglich.
    </p>

    <table v-if="eigene.length" class="fv-table">
      <thead>
        <tr><th>Name</th><th>Bericht</th><th>Version</th><th>Standard</th><th>Variablen</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="t in eigene" :key="t.id">
          <td><strong>{{ t.name }}</strong></td>
          <td>{{ berichtLabel(t.bericht_typ) }}</td>
          <td>{{ t.version }}</td>
          <td>
            <span v-if="t.ist_default" class="badge-default">Standard</span>
            <button v-else class="btn-link" @click="standardSetzen(t)">Als Standard</button>
          </td>
          <td>
            {{ (t.variablen || []).length }}
            <span v-if="t.pruefung && !t.pruefung.ok" class="badge-warn"
                  :title="t.pruefung.meldung">⚠ passt nicht</span>
          </td>
          <td><button class="btn-icon" title="Löschen" @click="loeschen(t)">🗑️</button></td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="!store.loading" class="fv-empty">
      Keine eigenen Vorlagen — die Dokumente entstehen im Format des Hauses.
    </p>

    <div v-if="haus.length" class="fv-haus">
      <h4>Haus-Vorlagen (gelten, solange der Mandant keine eigene hat)</h4>
      <ul>
        <li v-for="t in haus" :key="t.id">
          {{ t.name }} · {{ berichtLabel(t.bericht_typ) }}
          <span v-if="t.ist_default" class="badge-default">Standard</span>
        </li>
      </ul>
    </div>

    <fieldset v-if="firmenId" class="fv-upload">
      <legend>Vorlage für diesen Mandanten hochladen</legend>
      <div class="fv-grid">
        <label>Datei (DOCX/DOTX) *
          <input ref="dateiFeld" type="file" accept=".docx,.dotx" @change="onDatei" />
        </label>
        <label>Name *
          <input v-model="name" placeholder="z.B. Konformitätserklärung Kundenformat" />
        </label>
        <label>Für welchen Bericht?
          <select v-model="berichtTyp" class="select">
            <option value="">Alle Berichte des Moduls</option>
            <option v-for="b in berichte" :key="b.key" :value="b.key">
              {{ b.titel }}{{ b.vorgeschrieben ? ' (Aufbau vorgegeben)' : '' }}
            </option>
          </select>
        </label>
      </div>
      <p class="fv-tokens">
        Die verfügbaren Platzhalter stehen im Admin-Bereich unter
        „Word-Vorlagen → ❓ Variablenliste".
      </p>
      <button class="btn-primary" :disabled="!kannHochladen || laeuft" @click="hochladen">
        {{ laeuft ? 'Lade hoch…' : 'Hochladen' }}
      </button>
    </fieldset>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useTemplatesStore, type BerichtTyp, type WordTemplate } from '../../stores/templates'
import FehlerHinweis from '../shared/FehlerHinweis.vue'

const props = defineProps<{ firma: string; firmenId: number | null }>()

// Module mit Vorlagen-Adapter. Gutachten ist bewusst nicht angebunden (#988).
const MODULE = [
  { id: 'cra', label: 'CRA' },
  { id: 'nis2', label: 'NIS2' },
  { id: 'aiact', label: 'AI Act' },
  { id: 'dsgvo', label: 'DSGVO' },
  { id: 'risikobewertung', label: 'Risikobewertung' },
  { id: 'wiba', label: 'WiBA' },
  { id: 'compliance_audit', label: 'Compliance-Audit' },
]

const store = useTemplatesStore()
const modul = ref('cra')
const berichte = ref<BerichtTyp[]>([])
const fehler = ref('')
const warnung = ref('')

const datei = ref<File | null>(null)
const dateiFeld = ref<HTMLInputElement | null>(null)
const name = ref('')
const berichtTyp = ref('')
const laeuft = ref(false)

const kannHochladen = computed(() => !!datei.value && name.value.trim().length > 0)
const eigene = computed(() =>
  store.templates.filter(t => Number(t.firmen_id || 0) === Number(props.firmenId || -1)))
const haus = computed(() => store.templates.filter(t => !t.firmen_id))

function berichtLabel(key?: string): string {
  if (!key) return 'alle Berichte'
  return berichte.value.find(b => b.key === key)?.titel || key
}

async function laden() {
  fehler.value = ''
  await store.fetchTemplates(modul.value, props.firmenId || undefined)
  if (store.error) fehler.value = store.error
  berichte.value = await store.fetchBerichte(modul.value)
  berichtTyp.value = ''
}

function onDatei(e: Event) {
  const f = (e.target as HTMLInputElement).files
  datei.value = f && f.length ? f[0] : null
  if (datei.value && !name.value) name.value = datei.value.name.replace(/\.[^.]+$/, '')
}

async function hochladen() {
  if (!datei.value || !props.firmenId) return
  laeuft.value = true
  warnung.value = ''
  try {
    const res = await store.uploadTemplate(
      modul.value, name.value.trim(), datei.value, undefined,
      berichtTyp.value || undefined, props.firmenId)
    if (!res) {
      fehler.value = store.error || 'Hochladen fehlgeschlagen'
      return
    }
    // #1741: Das Prüfergebnis gehört vor die Augen des Anwenders, nicht in den
    // nächsten kaputten Export.
    if (res.pruefung && !res.pruefung.ok) {
      warnung.value = `${res.pruefung.meldung} Die Vorlage ist hochgeladen, lässt `
        + 'sich aber nicht als Standard setzen, solange das so ist.'
    }
    datei.value = null
    name.value = ''
    if (dateiFeld.value) dateiFeld.value.value = ''
    await laden()
  } finally {
    laeuft.value = false
  }
}

async function standardSetzen(t: WordTemplate) {
  fehler.value = ''
  const ok = await store.setDefault(t.id)
  if (!ok) fehler.value = store.error || 'Standard konnte nicht gesetzt werden'
  await laden()
}

async function loeschen(t: WordTemplate) {
  const grund = window.prompt(`Vorlage „${t.name}" löschen — Grund (optional):`, '')
  if (grund === null) return
  await store.deleteTemplate(t.id, grund)
  await laden()
}

watch(() => props.firmenId, laden)
onMounted(laden)
</script>

<style scoped>
.firma-vorlagen { padding: 4px 0; }
.fv-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.fv-head h3 { margin: 0; flex: 1; }
.fv-hint { font-size: 13px; color: var(--color-text-secondary); max-width: 900px; }
.fv-table { width: 100%; border-collapse: collapse; margin: 12px 0; }
.fv-table th, .fv-table td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--color-border); font-size: 13px; }
.fv-empty { color: var(--color-text-secondary); font-size: 13px; }
.fv-haus { margin: 12px 0; font-size: 13px; color: var(--color-text-secondary); }
.fv-haus h4 { margin: 0 0 4px; font-size: 13px; }
.fv-haus ul { margin: 0; padding-left: 18px; }
.fv-upload { margin-top: 18px; border: 1px solid var(--color-border); border-radius: 8px; padding: 12px 14px; }
.fv-upload legend { font-size: 13px; font-weight: 600; padding: 0 6px; }
.fv-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }
.fv-grid label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; }
.fv-grid input, .fv-grid select { padding: 6px 8px; border: 1px solid var(--color-border); border-radius: 6px; }
.fv-tokens { font-size: 12px; color: var(--color-text-secondary); }
.badge-default { background: #e8f5e9; color: #2e7d32; border-radius: 10px; padding: 2px 8px; font-size: 11px; }
.badge-warn { background: #fff3e0; color: #e65100; border-radius: 10px; padding: 2px 8px; font-size: 11px; margin-left: 6px; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; font-size: 12px; padding: 0; }
.btn-icon { background: none; border: none; cursor: pointer; font-size: 15px; }
.alert { padding: 8px 12px; border-radius: 6px; font-size: 13px; margin: 8px 0; cursor: pointer; }
.alert-error { background: #ffebee; border: 1px solid #ef9a9a; color: #c62828; }
.alert-warn { background: #fff8e1; border: 1px solid #ffe082; color: #6d4c41; }
</style>
