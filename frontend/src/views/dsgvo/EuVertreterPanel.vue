<template>
  <div class="euv-panel">
    <div class="intro-banner">
      <strong>🇪🇺 EU-Vertreter (Art. 27)</strong>
      <p class="hint">Anwendbarkeitsprüfung nach Art. 3(2) und — falls einschlägig —
        die schriftliche Benennung eines Vertreters in der Union sowie dessen
        Angabe in den Datenschutzhinweisen.</p>
    </div>

    <div v-if="!projektName" class="hint">Bitte zuerst ein Projekt auswählen.</div>
    <template v-else>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>

      <section class="card">
        <h4>Anwendbarkeitsprüfung (Art. 3 Abs. 2)</h4>
        <label class="cb"><input type="checkbox" v-model="form.niederlassung_ausserhalb_eu" />
          Verantwortlicher/Auftragsverarbeiter ist nicht in der EU niedergelassen</label>
        <label class="cb"><input type="checkbox" v-model="form.angebot_eu_betroffene" />
          Angebot von Waren/Dienstleistungen an EU-Betroffene</label>
        <label class="cb"><input type="checkbox" v-model="form.verhaltensbeobachtung" />
          Beobachtung des Verhaltens von EU-Betroffenen</label>
        <label class="cb"><input type="checkbox" v-model="form.ausnahme_art27_2" />
          Ausnahme nach Art. 27 Abs. 2 (gelegentlich, geringes Risiko, Behörde)</label>
        <label>Notiz zur Prüfung
          <textarea v-model="form.pruefung_notiz" rows="2"></textarea></label>

        <p class="verdict" :class="einschlaegig ? 'verdict-on' : 'verdict-off'">
          {{ einschlaegig
            ? '⚠ Art. 27 ist einschlägig — ein EU-Vertreter muss benannt werden.'
            : 'Art. 27 ist (derzeit) nicht einschlägig — kein EU-Vertreter erforderlich.' }}
        </p>
      </section>

      <section class="card" :class="{ dimmed: !einschlaegig }">
        <h4>Benennungs-Register</h4>
        <label>Name des EU-Vertreters <input v-model="form.vertreter_name" /></label>
        <label>Anschrift (EU-Mitgliedstaat) <textarea v-model="form.vertreter_anschrift" rows="2"></textarea></label>
        <label>Kontakt <input v-model="form.vertreter_kontakt" /></label>
        <label class="cb"><input type="checkbox" v-model="form.mandat_vorhanden" />
          Schriftliches Mandat / Mandatsvertrag vorhanden</label>
        <label>Datum des Mandats <input v-model="form.mandat_datum" type="date" /></label>
        <label class="cb"><input type="checkbox" v-model="form.in_datenschutzhinweis" />
          In den Datenschutzhinweisen angegeben (Art. 13 Abs. 1 lit. a)</label>
        <label>Notizen <textarea v-model="form.notizen" rows="2"></textarea></label>
      </section>

      <div class="action-row">
        <button class="btn-primary" :disabled="store.loading" @click="save">💾 Speichern</button>
        <span v-if="msg" class="hint ok">{{ msg }}</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useDsgvoEuVertreterStore, type EuVertreter } from '../../stores/dsgvoEuVertreter'

const props = defineProps<{ projektName: string | null }>()
const store = useDsgvoEuVertreterStore()
const msg = ref('')

const form = reactive({
  niederlassung_ausserhalb_eu: false,
  angebot_eu_betroffene: false,
  verhaltensbeobachtung: false,
  ausnahme_art27_2: false,
  pruefung_notiz: '',
  vertreter_name: '',
  vertreter_anschrift: '',
  vertreter_kontakt: '',
  mandat_vorhanden: false,
  mandat_datum: '',
  in_datenschutzhinweis: false,
  notizen: '',
})

// Spiegelt die Server-Ableitung is_einschlaegig (Live-Vorschau im Formular).
const einschlaegig = computed(() =>
  form.niederlassung_ausserhalb_eu
  && (form.angebot_eu_betroffene || form.verhaltensbeobachtung)
  && !form.ausnahme_art27_2)

function applyRecord(r: EuVertreter | null) {
  Object.assign(form, {
    niederlassung_ausserhalb_eu: !!r?.niederlassung_ausserhalb_eu,
    angebot_eu_betroffene: !!r?.angebot_eu_betroffene,
    verhaltensbeobachtung: !!r?.verhaltensbeobachtung,
    ausnahme_art27_2: !!r?.ausnahme_art27_2,
    pruefung_notiz: r?.pruefung_notiz || '',
    vertreter_name: r?.vertreter_name || '',
    vertreter_anschrift: r?.vertreter_anschrift || '',
    vertreter_kontakt: r?.vertreter_kontakt || '',
    mandat_vorhanden: !!r?.mandat_vorhanden,
    mandat_datum: r?.mandat_datum || '',
    in_datenschutzhinweis: !!r?.in_datenschutzhinweis,
    notizen: r?.notizen || '',
  })
}

async function load() {
  if (!props.projektName) return
  await store.fetchRecord(props.projektName)
  applyRecord(store.record)
}

async function save() {
  if (!props.projektName) return
  msg.value = ''
  const payload: Partial<EuVertreter> = {
    niederlassung_ausserhalb_eu: form.niederlassung_ausserhalb_eu ? 1 : 0,
    angebot_eu_betroffene: form.angebot_eu_betroffene ? 1 : 0,
    verhaltensbeobachtung: form.verhaltensbeobachtung ? 1 : 0,
    ausnahme_art27_2: form.ausnahme_art27_2 ? 1 : 0,
    pruefung_notiz: form.pruefung_notiz,
    vertreter_name: form.vertreter_name,
    vertreter_anschrift: form.vertreter_anschrift,
    vertreter_kontakt: form.vertreter_kontakt,
    mandat_vorhanden: form.mandat_vorhanden ? 1 : 0,
    mandat_datum: form.mandat_datum,
    in_datenschutzhinweis: form.in_datenschutzhinweis ? 1 : 0,
    notizen: form.notizen,
  }
  if (await store.save(props.projektName, payload)) {
    applyRecord(store.record)
    msg.value = 'Gespeichert.'
  }
}

onMounted(load)
watch(() => props.projektName, load)
</script>

<style scoped>
.euv-panel { display: flex; flex-direction: column; gap: 14px; padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 8px; }
.intro-banner .hint { color: #1565c0; font-size: 13px; margin: 4px 0 0; }
.hint { color: #666; font-size: 13px; }
.hint.ok { color: #2e7d32; }
.card { background: white; border: 1px solid var(--color-border, #e0e0e0); border-radius: 8px; padding: 14px 18px; display: flex; flex-direction: column; gap: 8px; }
.card.dimmed { opacity: 0.7; }
.card h4 { color: #1565c0; margin: 0 0 6px; font-size: 14px; }
.card label { display: flex; flex-direction: column; font-size: 13px; gap: 2px; }
.card label.cb { flex-direction: row; align-items: center; gap: 8px; }
.card input, .card textarea { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
.verdict { padding: 8px 12px; border-radius: 4px; font-size: 13px; font-weight: 600; margin: 6px 0 0; }
.verdict-on { background: #fff8e1; color: #f57f17; }
.verdict-off { background: #eceff1; color: #607d8b; }
.action-row { display: flex; gap: 12px; align-items: center; }
.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 14px; border-radius: 4px; cursor: pointer; align-self: flex-start; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.msg { font-size: 13px; }
.msg.err { color: #c62828; }
</style>
