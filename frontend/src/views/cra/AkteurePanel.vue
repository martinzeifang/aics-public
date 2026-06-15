<template>
  <div class="akteure-panel">
    <div class="panel-header">
      <h3>🏷️ Art. 19-22 — Wirtschaftsakteure-Register</h3>
      <p class="sub">Importeur · Händler · Bevollmächtigter — rollen-spezifische
        Pflicht-Checklisten, Mandats-/Nachweis-Referenz, Status</p>
    </div>

    <div v-if="store.error" class="alert alert-error">{{ store.error }}</div>

    <!-- Anlage-Formular -->
    <div class="form-card">
      <h4>Wirtschaftsakteur erfassen</h4>
      <div class="form-grid">
        <div class="form-row">
          <label>Rolle</label>
          <select v-model="form.rolle">
            <option v-for="r in store.rollen" :key="r" :value="r">{{ rolleLabel(r) }}</option>
          </select>
        </div>
        <div class="form-row">
          <label>Name</label>
          <input v-model="form.name" placeholder="Firma / Person" />
        </div>
        <div class="form-row">
          <label>Anschrift</label>
          <input v-model="form.anschrift" />
        </div>
        <div class="form-row">
          <label>Kontakt</label>
          <input v-model="form.kontakt" placeholder="E-Mail / Telefon" />
        </div>
        <div class="form-row">
          <label>Produkt</label>
          <input v-model="form.produkt" />
        </div>
        <div class="form-row">
          <label>Status</label>
          <select v-model="form.status">
            <option v-for="s in store.status" :key="s" :value="s">{{ statusLabel(s) }}</option>
          </select>
        </div>
      </div>

      <div class="form-row">
        <label>Pflicht-Checkliste ({{ rolleLabel(form.rolle) }})</label>
        <div class="checkliste">
          <label v-for="n in sollNachweise" :key="n" class="check-item">
            <input type="checkbox" v-model="form.checkliste[n]" /> {{ nachweisLabel(n) }}
          </label>
        </div>
      </div>

      <div class="form-row" v-if="form.rolle === 'bevollmaechtigter'">
        <label>Aufgabenumfang (schriftliches Mandat)</label>
        <textarea v-model="form.aufgabenumfang"></textarea>
      </div>
      <div class="form-row">
        <label>Mandats-/Nachweis-Referenz</label>
        <input v-model="form.mandat_ref" placeholder="z.B. Dokument-ID, URL oder Ablageort" />
      </div>
      <button class="btn-primary" @click="create">Akteur anlegen</button>
    </div>

    <!-- Register -->
    <div class="form-card">
      <h4>Erfasste Akteure ({{ store.akteure.length }})</h4>
      <p v-if="!store.akteure.length" class="hint">Noch keine Wirtschaftsakteure erfasst.</p>
      <table v-else class="akteure-table">
        <thead>
          <tr>
            <th>Rolle</th><th>Name</th><th>Produkt</th>
            <th>Checkliste</th><th>Status</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in store.akteure" :key="a.id">
            <td>{{ rolleLabel(a.rolle) }}</td>
            <td>{{ a.name || '—' }}</td>
            <td>{{ a.produkt || '—' }}</td>
            <td>
              <span :class="['pill', a.checkliste_vollstaendig ? 'ok' : 'warn']">
                {{ a.checkliste_vollstaendig ? 'vollständig' : 'unvollständig' }}
              </span>
            </td>
            <td>
              <select :value="a.status" @change="changeStatus(a, $event)">
                <option v-for="s in store.status" :key="s" :value="s">{{ statusLabel(s) }}</option>
              </select>
            </td>
            <td><button class="btn-link danger" @click="remove(a.id)">Löschen</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useCraAkteureStore, type Akteur } from '../../stores/craAkteure'

const props = defineProps<{ projekt: string }>()
const store = useCraAkteureStore()

const empty = () => ({
  rolle: 'importeur', name: '', anschrift: '', kontakt: '', produkt: '',
  checkliste: {} as Record<string, boolean>, mandat_ref: '', aufgabenumfang: '',
  status: 'offen',
})
const form = ref<any>(empty())

const sollNachweise = computed(() => store.checkliste[form.value.rolle] || [])

function rolleLabel(r: string) {
  return ({ importeur: 'Importeur (Art. 19)', haendler: 'Händler (Art. 20)',
    bevollmaechtigter: 'Bevollmächtigter (Art. 17/22)' } as Record<string, string>)[r] || r
}
function statusLabel(s: string) {
  return ({ offen: 'Offen', in_pruefung: 'In Prüfung', konform: 'Konform',
    nicht_konform: 'Nicht konform' } as Record<string, string>)[s] || s
}
function nachweisLabel(n: string) {
  return n.replace(/_/g, ' ')
}

async function create() {
  const ok = await store.createAkteur(props.projekt, { ...form.value })
  if (ok) form.value = empty()
}
async function changeStatus(a: Akteur, ev: Event) {
  const status = (ev.target as HTMLSelectElement).value
  await store.updateAkteur(props.projekt, a.id, { status })
}
async function remove(id: number) {
  await store.deleteAkteur(props.projekt, id)
}

async function load() {
  await store.fetchAkteure(props.projekt)
}
onMounted(async () => { await store.fetchConstants(); await load() })
watch(() => props.projekt, load)
</script>

<style scoped>
.panel-header h3 { color: #1565c0; margin-bottom: 4px; }
.panel-header .sub { color: #607d8b; font-size: 13px; }
.form-card { background: #f5f8fc; border: 1px solid #cfd8e3; border-radius: 8px; padding: 16px; margin: 12px 0; }
.form-card h4 { color: #1565c0; margin: 0 0 10px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.form-row { display: flex; flex-direction: column; margin-bottom: 8px; }
.form-row label { font-size: 12px; color: #455a64; margin-bottom: 2px; }
.checkliste { display: flex; flex-direction: column; gap: 4px; }
.check-item { flex-direction: row; align-items: center; gap: 6px; font-size: 13px; }
.akteure-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.akteure-table th, .akteure-table td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #e0e6ee; }
.akteure-table th { color: #455a64; }
.pill { padding: 2px 8px; border-radius: 10px; font-size: 11px; }
.pill.ok { background: #e8f5e9; color: #2e7d32; }
.pill.warn { background: #fff3e0; color: #ef6c00; }
.hint { color: #607d8b; font-size: 13px; }
.btn-link { background: none; border: none; cursor: pointer; color: #1565c0; }
.btn-link.danger { color: #c62828; }
</style>
