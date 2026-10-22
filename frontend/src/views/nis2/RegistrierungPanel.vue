<template>
  <div class="reg-panel">
    <div class="intro-banner">
      <strong>📝 BSI-Registrierung (Art. 27 NIS2)</strong>
      <p class="hint">Sechs Pflichtangaben für die Registrierung beim BSI binnen 3 Monaten,
        Übermittlungsstatus und jährliche Bestätigung (Wiedervorlage mit 3-Monats-Hinweis).</p>
    </div>

    <div v-if="!projektName" class="hint">Bitte zuerst ein Projekt auswählen.</div>

    <template v-else>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>

      <div class="toolbar">
        <button class="btn-secondary" @click="doPrefill">✨ Aus Stammdaten vorbefüllen</button>
        <span
          v-if="form.bestaetigung?.hinweis"
          class="badge"
          :class="'ampel-' + (form.bestaetigung.ampel)"
        >{{ form.bestaetigung.hinweis }}</span>
      </div>

      <div
        v-if="form.fehlende_pflichtfelder && form.fehlende_pflichtfelder.length"
        class="warn"
      >⚠️ Unvollständig — fehlende Pflichtangaben: {{ form.fehlende_pflichtfelder.join(', ') }}</div>

      <div class="form-grid">
        <label>1. Name der Einrichtung * <input v-model="form.name" /></label>
        <label>2a. Sektor * <input v-model="form.sektor" /></label>
        <label>2b. Subsektor <input v-model="form.subsektor" /></label>
        <label>2c. Einrichtungsart (Anhang I/II) <input v-model="form.einrichtungsart" /></label>
        <label>3a. Anschrift Hauptniederlassung * <input v-model="form.anschrift" /></label>
        <label>3b. Sonstige EU-Niederlassungen/Vertreter <input v-model="form.eu_niederlassungen" /></label>
        <label>4a. Kontakt E-Mail * <input v-model="form.kontakt_email" type="email" /></label>
        <label>4b. Kontakt Telefon <input v-model="form.kontakt_telefon" /></label>
        <label>5. Mitgliedstaaten der Diensteerbringung * <input v-model="form.mitgliedstaaten" /></label>
        <label>6. IP-Adressbereiche * <input v-model="form.ip_bereiche" /></label>
      </div>

      <fieldset class="status-box">
        <legend>Übermittlung &amp; Bestätigung</legend>
        <label>Status
          <select v-model="form.status">
            <option v-for="s in store.constants?.status || []" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>Registrierungsdatum <input v-model="form.registrierungs_datum" type="date" /></label>
        <label>Bestätigungsreferenz <input v-model="form.bestaetigungs_referenz" /></label>
        <label>Nächste Jahres-Bestätigung <input v-model="form.naechste_jahres_bestaetigung" type="date" /></label>
        <label>Notizen <textarea v-model="form.notizen" rows="2" /></label>
      </fieldset>

      <div class="actions">
        <button class="btn-primary" @click="submit">Speichern</button>
        <button class="btn-secondary" :disabled="!form.id" @click="store.exportRegistrierung(projektName, 'md')">📄 Export (MD)</button>
        <button class="btn-secondary" :disabled="!form.id" @click="store.exportRegistrierung(projektName, 'json')">📄 Export (JSON)</button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted, watch } from 'vue'
import { useNis2RegistrierungStore } from '../../stores/nis2Registrierung'

const props = defineProps<{ projektName: string | null }>()
const store = useNis2RegistrierungStore()

const emptyForm = () => ({
  id: 0, name: '', sektor: '', subsektor: '', einrichtungsart: '', anschrift: '',
  eu_niederlassungen: '', kontakt_email: '', kontakt_telefon: '',
  mitgliedstaaten: '', ip_bereiche: '', status: 'offen',
  registrierungs_datum: '', bestaetigungs_referenz: '',
  naechste_jahres_bestaetigung: '', notizen: '',
  fehlende_pflichtfelder: [] as string[], bestaetigung: null as any,
})
const form = reactive<any>(emptyForm())

const reload = async () => {
  Object.assign(form, emptyForm())
  if (!props.projektName) return
  await store.fetchRegistrierung(props.projektName)
  if (store.registrierung) Object.assign(form, store.registrierung)
}

onMounted(async () => {
  await store.fetchConstants()
  await reload()
})
watch(() => props.projektName, reload)

const doPrefill = async () => {
  if (!props.projektName) return
  const sug = await store.fetchPrefill(props.projektName)
  for (const [k, v] of Object.entries(sug)) {
    if (v && !form[k]) form[k] = v
  }
}

const submit = async () => {
  if (!props.projektName) return
  const ok = await store.saveRegistrierung(props.projektName, { ...form })
  if (ok && store.registrierung) Object.assign(form, store.registrierung)
}
</script>

<style scoped>
.reg-panel { padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; }
.intro-banner strong { color: #1565c0; }
.hint { color: #607d8b; font-size: 0.9em; }
.msg.err { color: #c62828; }
.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
.badge { font-size: 0.85em; padding: 4px 10px; border-radius: 12px; color: #fff; }
.ampel-green { background: #43a047; }
.ampel-amber { background: #fb8c00; }
.ampel-red { background: #e53935; }
.ampel-grey { background: #bdbdbd; }
.warn { background: #fff3e0; border-left: 4px solid #fb8c00; padding: 8px 12px; border-radius: 6px; margin-bottom: 12px; font-size: 0.9em; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 16px; }
label { display: block; margin: 6px 0; font-size: 0.9em; }
input, select, textarea { width: 100%; padding: 6px 8px; border: 1px solid #cfd8dc; border-radius: 4px; margin-top: 4px; box-sizing: border-box; }
.status-box { border: 1px solid #cfd8dc; border-radius: 8px; padding: 12px 16px; margin: 16px 0; }
.status-box legend { color: #1565c0; font-weight: 600; padding: 0 6px; }
.actions { display: flex; gap: 12px; }
.btn-primary { background: #1565c0; color: #fff; border: none; padding: 7px 14px; border-radius: 6px; cursor: pointer; }
.btn-secondary { background: #eceff1; border: 1px solid #cfd8dc; padding: 6px 12px; border-radius: 6px; cursor: pointer; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
