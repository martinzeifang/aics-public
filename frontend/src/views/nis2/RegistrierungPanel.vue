<template>
  <div class="reg-panel">
    <div class="intro-banner">
      <strong>{{ $t('nis2.registrierungPanel.bSIRegistrierungArtNIS2') }}</strong>
      <p class="hint">{{ $t('nis2.registrierungPanel.sechsPflichtangabenFurDieRegistrieru') }}</p>
    </div>

    <div v-if="!projektName" class="hint">{{ $t('common.projektWaehlen') }}</div>

    <template v-else>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>

      <div class="toolbar">
        <button class="btn-secondary" @click="doPrefill">{{ $t('nis2.registrierungPanel.ausStammdatenVorbefullen') }}</button>
        <span
          v-if="form.bestaetigung?.hinweis"
          class="badge"
          :class="'ampel-' + (form.bestaetigung.ampel)"
        >{{ form.bestaetigung.hinweis }}</span>
      </div>

      <div
        v-if="form.fehlende_pflichtfelder && form.fehlende_pflichtfelder.length"
        class="warn"
      >{{ $t('nis2.registrierungPanel.unvollstandigFehlendePflichtangabenV', { v0: form.fehlende_pflichtfelder.join(', ') }) }}</div>

      <div class="form-grid">
        <label>{{ $t('nis2.registrierungPanel.nameDerEinrichtung') }} <input v-model="form.name" /></label>
        <label>{{ $t('nis2.registrierungPanel.aSektor') }} <input v-model="form.sektor" /></label>
        <label>{{ $t('nis2.registrierungPanel.bSubsektor') }} <input v-model="form.subsektor" /></label>
        <label>{{ $t('nis2.registrierungPanel.cEinrichtungsartAnhangIII') }} <input v-model="form.einrichtungsart" /></label>
        <label>{{ $t('nis2.registrierungPanel.aAnschriftHauptniederlassung') }} <input v-model="form.anschrift" /></label>
        <label>{{ $t('nis2.registrierungPanel.bSonstigeEUNiederlassungenVertreter') }} <input v-model="form.eu_niederlassungen" /></label>
        <label>{{ $t('nis2.registrierungPanel.aKontaktEMail') }} <input v-model="form.kontakt_email" type="email" /></label>
        <label>{{ $t('nis2.registrierungPanel.bKontaktTelefon') }} <input v-model="form.kontakt_telefon" /></label>
        <label>{{ $t('nis2.registrierungPanel.mitgliedstaatenDerDiensteerbringung') }} <input v-model="form.mitgliedstaaten" /></label>
        <label>{{ $t('nis2.registrierungPanel.iPAdressbereiche') }} <input v-model="form.ip_bereiche" /></label>
      </div>

      <fieldset class="status-box">
        <legend>{{ $t('nis2.registrierungPanel.ubermittlungAmpBestatigung') }}</legend>
        <label>{{ $t('common.status') }}
          <select v-model="form.status">
            <option v-for="s in store.constants?.status || []" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>{{ $t('nis2.registrierungPanel.registrierungsdatum') }} <input v-model="form.registrierungs_datum" type="date" /></label>
        <label>{{ $t('nis2.registrierungPanel.bestatigungsreferenz') }} <input v-model="form.bestaetigungs_referenz" /></label>
        <label>{{ $t('nis2.registrierungPanel.nachsteJahresBestatigung') }} <input v-model="form.naechste_jahres_bestaetigung" type="date" /></label>
        <label>{{ $t('common.notizen') }} <textarea v-model="form.notizen" rows="2" /></label>
      </fieldset>

      <div class="actions">
        <button class="btn-primary" @click="submit">{{ $t('common.save') }}</button>
        <button class="btn-secondary" :disabled="!form.id" @click="store.exportRegistrierung(projektName, 'md')">{{ $t('nis2.registrierungPanel.exportMD') }}</button>
        <button class="btn-secondary" :disabled="!form.id" @click="store.exportRegistrierung(projektName, 'json')">{{ $t('nis2.registrierungPanel.exportJSON') }}</button>
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
