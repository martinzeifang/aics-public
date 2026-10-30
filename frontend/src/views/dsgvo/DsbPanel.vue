<template>
  <div class="dsb-panel">
    <p v-if="!projekt" class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>

    <template v-else>
      <!-- Toolbar -->
      <div class="dsb-toolbar">
        <div class="toolbar-info">
          <strong>🛡️ Datenschutzbeauftragter (Art. 37-39 DSGVO)</strong>
          <span class="status-pill" :style="{ background: statusColor }">{{ statusLabel }}</span>
        </div>
        <div class="toolbar-actions">
          <button v-if="store.dsb" class="btn-tiny btn-del" :disabled="busy" @click="onDelete">
            🗑️ DSB löschen
          </button>
        </div>
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>
      <p v-if="store.error" class="error-msg">{{ store.error }}</p>

      <!-- Formular -->
      <div class="dsb-form">
        <section class="form-card">
          <h4>Stammdaten</h4>
          <div class="form-row">
            <label>Typ</label>
            <select v-model="form.typ">
              <option v-for="t in store.typen" :key="t" :value="t">{{ typLabel(t) }}</option>
            </select>
          </div>
          <div class="form-row">
            <label>Name / Bezeichnung</label>
            <input v-model="form.name" placeholder="Name des DSB bzw. Dienstleisters" />
          </div>
          <div class="form-row">
            <label>Bestelldatum</label>
            <input v-model="form.bestelldatum" type="date" />
          </div>
          <div class="form-row">
            <label>Kontakt-E-Mail (Art. 37 Abs. 7)</label>
            <input v-model="form.kontakt_email" type="email" placeholder="datenschutz@beispiel.de" />
          </div>
          <div class="form-row checkbox-row">
            <label><input type="checkbox" v-model="form.kontakt_veroeffentlicht" />
              Kontaktdaten veröffentlicht (Art. 37 Abs. 7)</label>
          </div>
          <div class="form-row checkbox-row">
            <label><input type="checkbox" v-model="form.gemeldet_aufsicht" />
              Der Aufsichtsbehörde gemeldet (Art. 37 Abs. 7)</label>
          </div>
        </section>

        <section class="form-card">
          <h4>Nachweis &amp; Bericht</h4>
          <div class="form-row">
            <label>Aufgaben-Nachweis (Art. 39)</label>
            <textarea v-model="form.aufgaben_nachweis" rows="4"
                      placeholder="Nachweis der Wahrnehmung der DSB-Aufgaben (Beratung, Überwachung, Schulung …)"></textarea>
          </div>
          <div class="form-row">
            <label>Tätigkeitsbericht</label>
            <textarea v-model="form.taetigkeitsbericht" rows="5"
                      placeholder="Tätigkeitsbericht des DSB …"></textarea>
          </div>
          <div class="form-row">
            <label>Notizen</label>
            <textarea v-model="form.notizen" rows="2"></textarea>
          </div>
        </section>

        <div class="form-actions">
          <button class="btn-primary" :disabled="busy" @click="onSave">
            {{ busy ? 'Speichert…' : 'Speichern' }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, watch } from 'vue'
import { useDsgvoStore } from '../../stores/dsgvo'
import { useDsgvoDsbStore, type Dsb } from '../../stores/dsgvoDsb'

const dsgvo = useDsgvoStore()
const store = useDsgvoDsbStore()

const projekt = computed(() => dsgvo.selectedProjekt)

const busy = ref(false)
const message = ref('')

const TYP_LABELS: Record<string, string> = {
  intern: 'Intern',
  extern: 'Extern (Dienstleister)',
}
function typLabel(t: string): string { return TYP_LABELS[t] || t }

const statusLabel = computed(() => {
  if (!store.dsb) return 'Nicht erfasst'
  if (store.dsb.gemeldet_aufsicht && store.dsb.kontakt_veroeffentlicht) return 'Vollständig'
  return 'Erfasst'
})
const statusColor = computed(() => {
  if (!store.dsb) return '#9e9e9e'
  if (store.dsb.gemeldet_aufsicht && store.dsb.kontakt_veroeffentlicht) return '#2e7d32'
  return '#f57f17'
})

const form = reactive({
  typ: 'intern',
  name: '',
  bestelldatum: '',
  kontakt_email: '',
  kontakt_veroeffentlicht: false,
  gemeldet_aufsicht: false,
  aufgaben_nachweis: '',
  taetigkeitsbericht: '',
  notizen: '',
})

function fillForm(d: Dsb | null) {
  Object.assign(form, {
    typ: d?.typ || store.typen[0] || 'intern',
    name: d?.name || '',
    bestelldatum: d?.bestelldatum || '',
    kontakt_email: d?.kontakt_email || '',
    kontakt_veroeffentlicht: !!(d && d.kontakt_veroeffentlicht),
    gemeldet_aufsicht: !!(d && d.gemeldet_aufsicht),
    aufgaben_nachweis: d?.aufgaben_nachweis || '',
    taetigkeitsbericht: d?.taetigkeitsbericht || '',
    notizen: d?.notizen || '',
  })
}

async function load() {
  if (!projekt.value) return
  await store.fetchConstants()
  await store.fetchDsb(projekt.value)
  fillForm(store.dsb)
}
onMounted(load)
watch(projekt, load)

async function onSave() {
  if (!projekt.value) return
  busy.value = true
  message.value = ''
  try {
    const payload = {
      typ: form.typ,
      name: form.name,
      bestelldatum: form.bestelldatum,
      kontakt_email: form.kontakt_email,
      kontakt_veroeffentlicht: form.kontakt_veroeffentlicht ? 1 : 0,
      gemeldet_aufsicht: form.gemeldet_aufsicht ? 1 : 0,
      aufgaben_nachweis: form.aufgaben_nachweis,
      taetigkeitsbericht: form.taetigkeitsbericht,
      notizen: form.notizen,
    }
    const res = await store.saveDsb(projekt.value, payload)
    if (res) {
      fillForm(res)
      message.value = 'DSB-Daten gespeichert.'
    }
  } finally {
    busy.value = false
  }
}

async function onDelete() {
  if (!projekt.value) return
  if (!confirm('DSB-Datensatz dieses Projekts wirklich löschen?')) return
  busy.value = true
  message.value = ''
  try {
    const ok = await store.deleteDsb(projekt.value)
    if (ok) {
      fillForm(null)
      message.value = 'DSB-Datensatz gelöscht.'
    }
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.dsb-panel { padding: 4px 0; }
.hint { color: #607d8b; padding: 16px 0; }
.status-msg { background: #e8f5e9; color: #2e7d32; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }
.error-msg { background: #ffebee; color: #c62828; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }

.dsb-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 14px;
}
.toolbar-info { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.toolbar-info strong { color: #1565c0; font-size: 15px; }
.toolbar-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.status-pill {
  padding: 2px 10px; border-radius: 3px; color: white; font-size: 11px; font-weight: 600;
  display: inline-block; white-space: nowrap;
}

.dsb-form { display: flex; flex-direction: column; gap: 16px; max-width: 720px; }
.form-card {
  background: white; border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 8px; padding: 16px 18px;
}
.form-card h4 { margin: 0 0 12px; color: #1565c0; font-size: 14px; }

.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row.checkbox-row label { font-weight: 400; display: flex; align-items: center; gap: 8px; }
.form-row input[type="text"], .form-row input[type="date"], .form-row input[type="email"],
.form-row input:not([type]), .form-row select, .form-row textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 4px; font-size: 13px; box-sizing: border-box;
}

.form-actions { display: flex; justify-content: flex-end; }

.btn-primary {
  padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;
  background: var(--color-primary, #1565c0); color: white;
}
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

.btn-tiny {
  background: none; border: 1px solid #ddd; padding: 4px 10px;
  border-radius: 3px; cursor: pointer; font-size: 12px;
}
.btn-tiny:hover { background: #f0f0f0; }
.btn-tiny.btn-del:hover { background: #ffebee; border-color: #c62828; }
.btn-tiny:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
