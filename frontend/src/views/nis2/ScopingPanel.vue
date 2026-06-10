<template>
  <div class="scoping-panel">
    <div class="intro-banner">
      <strong>🎯 Betroffenheitsanalyse &amp; Scoping (Art. 2/3 + Art. 26 NIS2)</strong>
      <p class="hint">Größenschwellen-Nachweis (Mitarbeiterzahl, Umsatz, Bilanzsumme) mit
        deterministischer Einstufung wesentlich/wichtig/out-of-scope plus
        Hauptniederlassung &amp; EU-Vertreter-Feststellung. Versioniertes Scoping-Dokument.</p>
    </div>

    <div v-if="!projektName" class="hint">Bitte zuerst ein Projekt auswählen.</div>

    <template v-else>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>

      <div class="form-grid">
        <fieldset>
          <legend>Größenschwellen (Art. 2/3)</legend>
          <label>Mitarbeiterzahl
            <input v-model.number="form.mitarbeiterzahl" type="number" min="0" @input="livePreview" />
          </label>
          <label>Jahresumsatz (Mio. EUR)
            <input v-model.number="form.jahresumsatz" type="number" min="0" step="0.1" @input="livePreview" />
          </label>
          <label>Bilanzsumme (Mio. EUR)
            <input v-model.number="form.bilanzsumme" type="number" min="0" step="0.1" @input="livePreview" />
          </label>
          <label>Sektor <input v-model="form.sektor" /></label>
          <label>Subsektor <input v-model="form.subsektor" /></label>
          <label>Anhang
            <select v-model="form.anhang" @change="livePreview">
              <option v-for="a in store.constants?.anhang || []" :key="a" :value="a">{{ a }}</option>
            </select>
          </label>
          <label>Konzernverbund <input v-model="form.konzernverbund" /></label>
        </fieldset>

        <fieldset>
          <legend>Jurisdiktion (Art. 26)</legend>
          <label>Hauptniederlassung <input v-model="form.hauptniederlassung" /></label>
          <label>Zuständige Behörde <input v-model="form.zustaendige_behoerde" /></label>
          <label class="cb"><input type="checkbox" v-model="euNiedergelassen" /> in der EU niedergelassen</label>
          <label v-if="!euNiedergelassen">EU-Vertreter (Pflicht)
            <input v-model="form.eu_vertreter" placeholder="Name / Adresse / Mitgliedstaat" />
          </label>
          <label>Scoping-Datum <input v-model="form.scoping_datum" type="date" /></label>
          <label>Notizen <textarea v-model="form.notizen" rows="2" /></label>
        </fieldset>
      </div>

      <div class="result-card" :class="'cls-' + (preview?.size_class || form.size_class)">
        <strong>Einstufung:</strong>
        {{ preview?.size_class || form.size_class || '—' }}
        <p class="hint">{{ preview?.size_begruendung || form.size_begruendung }}</p>
        <p v-if="form.version" class="hint">Version {{ form.version }}</p>
      </div>

      <div class="actions">
        <button class="btn-primary" @click="submit">Speichern</button>
        <button class="btn-secondary" :disabled="!form.version" @click="store.exportScoping(projektName, 'md')">📄 Export (MD)</button>
        <button class="btn-secondary" :disabled="!form.version" @click="store.exportScoping(projektName, 'json')">📄 Export (JSON)</button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useNis2ScopingStore } from '../../stores/nis2Scoping'

const props = defineProps<{ projektName: string | null }>()
const store = useNis2ScopingStore()

const emptyForm = () => ({
  mitarbeiterzahl: 0, jahresumsatz: 0, bilanzsumme: 0, sektor: '', subsektor: '',
  anhang: 'keiner', konzernverbund: '', size_class: '', size_begruendung: '',
  hauptniederlassung: '', zustaendige_behoerde: 'BSI', eu_niedergelassen: 1,
  eu_vertreter: '', version: 0, scoping_datum: '', notizen: '',
})
const form = reactive<any>(emptyForm())
const preview = ref<{ size_class: string; size_begruendung: string } | null>(null)

const euNiedergelassen = computed({
  get: () => form.eu_niedergelassen !== 0,
  set: (v: boolean) => { form.eu_niedergelassen = v ? 1 : 0 },
})

const reload = async () => {
  preview.value = null
  Object.assign(form, emptyForm())
  if (!props.projektName) return
  await store.fetchScoping(props.projektName)
  if (store.scoping) Object.assign(form, store.scoping)
}

onMounted(async () => {
  await store.fetchConstants()
  await reload()
})
watch(() => props.projektName, reload)

let previewTimer: any = null
const livePreview = () => {
  clearTimeout(previewTimer)
  previewTimer = setTimeout(async () => {
    preview.value = await store.previewSizeClass({
      mitarbeiterzahl: form.mitarbeiterzahl, jahresumsatz: form.jahresumsatz,
      bilanzsumme: form.bilanzsumme, anhang: form.anhang,
    })
  }, 250)
}

const submit = async () => {
  if (!props.projektName) return
  const ok = await store.saveScoping(props.projektName, { ...form })
  if (ok && store.scoping) { Object.assign(form, store.scoping); preview.value = null }
}
</script>

<style scoped>
.scoping-panel { padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; }
.intro-banner strong { color: #1565c0; }
.hint { color: #607d8b; font-size: 0.9em; }
.msg.err { color: #c62828; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
fieldset { border: 1px solid #cfd8dc; border-radius: 8px; padding: 12px 16px; }
legend { color: #1565c0; font-weight: 600; padding: 0 6px; }
label { display: block; margin: 8px 0; font-size: 0.9em; }
label.cb { display: flex; gap: 8px; align-items: center; }
input, select, textarea { width: 100%; padding: 6px 8px; border: 1px solid #cfd8dc; border-radius: 4px; margin-top: 4px; box-sizing: border-box; }
label.cb input { width: auto; margin-top: 0; }
.result-card { margin: 16px 0; padding: 12px 16px; border-radius: 8px; background: #eceff1; border-left: 4px solid #90caf9; }
.result-card.cls-wesentlich { border-left-color: #e53935; }
.result-card.cls-wichtig { border-left-color: #fb8c00; }
.result-card.cls-out-of-scope { border-left-color: #43a047; }
.actions { display: flex; gap: 12px; }
.btn-primary { background: #1565c0; color: #fff; border: none; padding: 7px 14px; border-radius: 6px; cursor: pointer; }
.btn-secondary { background: #eceff1; border: 1px solid #cfd8dc; padding: 6px 12px; border-radius: 6px; cursor: pointer; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
