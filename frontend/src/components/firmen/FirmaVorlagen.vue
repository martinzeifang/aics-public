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
      <h3>{{ $t('firmen.firmaVorlagen.wordVorlagenFurV0', { v0: firma }) }}</h3>
      <select v-model="modul" class="select" @change="laden">
        <option v-for="m in MODULE" :key="m.id" :value="m.id">{{ m.label }}</option>
      </select>
      <button class="btn-secondary" :disabled="store.loading" @click="laden">{{ $t('common.aktualisieren') }}</button>
    </div>

    <p class="fv-hint">
      {{ $t('firmen.firmaVorlagen.kundendokumenteKonformitatserklarung') }}
    </p>

    <FehlerHinweis :text="fehler" @close="fehler = ''" />
    <div v-if="warnung" class="alert alert-warn" @click="warnung = ''">{{ warnung }}</div>
    <p v-if="!firmenId" class="alert alert-warn">
      {{ $t('firmen.firmaVorlagen.dieseFirmaIstNochKeinerFirmenIDZugeo') }}
    </p>

    <table v-if="eigene.length" class="fv-table">
      <thead>
        <tr><th>{{ $t('common.name') }}</th><th>{{ $t('firmen.firmaVorlagen.bericht') }}</th><th>{{ $t('common.version') }}</th><th>{{ $t('common.standard') }}</th><th>{{ $t('firmen.firmaVorlagen.variablen') }}</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="t in eigene" :key="t.id">
          <td><strong>{{ t.name }}</strong></td>
          <td>{{ berichtLabel(t.bericht_typ) }}</td>
          <td>{{ t.version }}</td>
          <td>
            <span v-if="t.ist_default" class="badge-default">{{ $t('common.standard') }}</span>
            <button v-else class="btn-link" @click="standardSetzen(t)">{{ $t('common.alsStandard') }}</button>
          </td>
          <td>
            {{ (t.variablen || []).length }}
            <span v-if="t.pruefung && !t.pruefung.ok" class="badge-warn"
                  :title="t.pruefung.meldung">{{ $t('firmen.firmaVorlagen.passtNicht') }}</span>
          </td>
          <td><button class="btn-icon" :title="$t('common.delete')" @click="loeschen(t)">🗑️</button></td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="!store.loading" class="fv-empty">
      {{ $t('firmen.firmaVorlagen.keineEigenenVorlagenDieDokumenteEnts') }}
    </p>

    <div v-if="haus.length" class="fv-haus">
      <h4>{{ $t('firmen.firmaVorlagen.hausVorlagenGeltenSolangeDerMandantK') }}</h4>
      <ul>
        <li v-for="t in haus" :key="t.id">
          {{ t.name }} · {{ berichtLabel(t.bericht_typ) }}
          <span v-if="t.ist_default" class="badge-default">{{ $t('common.standard') }}</span>
        </li>
      </ul>
    </div>

    <fieldset v-if="firmenId" class="fv-upload">
      <legend>{{ $t('firmen.firmaVorlagen.vorlageFurDiesenMandantenHochladen') }}</legend>
      <div class="fv-grid">
        <label>{{ $t('firmen.firmaVorlagen.dateiDOCXDOTX') }}
          <input ref="dateiFeld" type="file" accept=".docx,.dotx" @change="onDatei" />
        </label>
        <label>{{ $t('common.name') }}
          <input v-model="name" :placeholder="$t('firmen.firmaVorlagen.zBKonformitatserklarungKundenformat')" />
        </label>
        <label>{{ $t('firmen.firmaVorlagen.furWelchenBericht') }}
          <select v-model="berichtTyp" class="select">
            <option value="">{{ $t('firmen.firmaVorlagen.alleBerichteDesModuls') }}</option>
            <option v-for="b in berichte" :key="b.key" :value="b.key">
              {{ b.titel }}{{ b.vorgeschrieben ? $t('firmen.firmaVorlagen.aufbauVorgegeben') : '' }}
            </option>
          </select>
        </label>
      </div>
      <p class="fv-tokens">
        {{ $t('firmen.firmaVorlagen.dieVerfugbarenPlatzhalterStehenImAdm') }}
      </p>
      <button class="btn-primary" :disabled="!kannHochladen || laeuft" @click="hochladen">
        {{ laeuft ? $t('firmen.firmaVorlagen.ladeHoch') : $t('firmen.firmaVorlagen.hochladen') }}
      </button>
    </fieldset>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useTemplatesStore, type BerichtTyp, type WordTemplate } from '../../stores/templates'
import FehlerHinweis from '../shared/FehlerHinweis.vue'
// `t` ist in dieser Maske schon belegt (lokale Variable/Parameter) —
// deshalb unter anderem Namen. Ein Import überdeckt eine lokale
// Bindung nicht, er kollidiert mit ihr: Der Aufruf trifft die
// Variable, und die ist keine Funktion. Gefunden hat das der
// Typprüfer (#1858), nicht der Build.
import { t as uebersetze } from '../../i18n'

const props = defineProps<{ firma: string; firmenId: number | null }>()

// Module mit Vorlagen-Adapter. Gutachten ist bewusst nicht angebunden (#988).
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
  if (!key) return uebersetze('firmen.firmaVorlagen.alleBerichte')
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
      fehler.value = store.error || uebersetze('firmen.firmaVorlagen.hochladenFehlgeschlagen')
      return
    }
    // #1741: Das Prüfergebnis gehört vor die Augen des Anwenders, nicht in den
    // nächsten kaputten Export.
    if (res.pruefung && !res.pruefung.ok) {
      warnung.value = `${res.pruefung.meldung} Die Vorlage ist hochgeladen, lässt `
        + uebersetze('firmen.firmaVorlagen.sichAberNichtAlsStandardSetzenSolang')
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
  if (!ok) fehler.value = store.error || uebersetze('firmen.firmaVorlagen.standardKonnteNichtGesetztWerden')
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
