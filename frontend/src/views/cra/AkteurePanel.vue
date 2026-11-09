<template>
  <div class="akteure-panel">
    <div class="panel-header">
      <h3>{{ $t('cra.akteurePanel.artWirtschaftsakteureRegister') }}</h3>
      <p class="sub">{{ $t('cra.akteurePanel.importeurHandlerBevollmachtigterOpen') }}</p>
    </div>

    <FehlerHinweis :text="store.error" @close="store.error = ''" />

    <!-- Anlage-Formular -->
    <div class="form-card">
      <h4>{{ $t('cra.akteurePanel.wirtschaftsakteurErfassen') }}</h4>
      <div class="form-grid">
        <div class="form-row">
          <label>{{ $t('common.rolle') }}</label>
          <select v-model="form.rolle">
            <option v-for="r in store.rollen" :key="r" :value="r">{{ rolleLabel(r) }}</option>
          </select>
        </div>
        <div class="form-row">
          <label>{{ $t('common.name') }}</label>
          <input v-model="form.name" :placeholder="$t('cra.akteurePanel.firmaPerson')" />
        </div>
        <div class="form-row">
          <label>{{ $t('cra.akteurePanel.anschrift') }}</label>
          <input v-model="form.anschrift" />
        </div>
        <div class="form-row">
          <label>{{ $t('cra.akteurePanel.kontakt') }}</label>
          <input v-model="form.kontakt" :placeholder="$t('cra.akteurePanel.eMailTelefon')" />
        </div>
        <div class="form-row">
          <label>{{ $t('common.produkt') }}</label>
          <input v-model="form.produkt" />
        </div>
        <div class="form-row">
          <label>{{ $t('common.status') }}</label>
          <select v-model="form.status">
            <option v-for="s in store.status" :key="s" :value="s">{{ statusLabel(s) }}</option>
          </select>
        </div>
      </div>

      <div class="form-row">
        <label>{{ $t('cra.akteurePanel.pflichtChecklisteV0', { v0: rolleLabel(form.rolle) }) }}</label>
        <div class="checkliste">
          <label v-for="n in sollNachweise" :key="n" class="check-item">
            <input type="checkbox" v-model="form.checkliste[n]" /> {{ nachweisLabel(n) }}
          </label>
        </div>
      </div>

      <!-- #1762: Der Open-Source-Verwalter braucht den Aufgabenumfang genauso —
           bei ihm ist er die Abgrenzung zur Herstellerrolle und damit der Grund,
           warum die schmaleren Pflichten gelten. -->
      <div class="form-row"
           v-if="form.rolle === 'bevollmaechtigter' || form.rolle === 'open_source_verwalter'">
        <label>{{ form.rolle === 'open_source_verwalter'
          ? $t('cra.akteurePanel.aufgabenumfangVerwalteteKomponentenA')
          : $t('cra.akteurePanel.aufgabenumfangSchriftlichesMandat') }}</label>
        <textarea v-model="form.aufgabenumfang"></textarea>
      </div>
      <div class="form-row">
        <label>{{ $t('cra.akteurePanel.mandatsNachweisReferenz') }}</label>
        <input v-model="form.mandat_ref" :placeholder="$t('cra.akteurePanel.zBDokumentIDURLOderAblageort')" />
      </div>
      <button class="btn-primary" @click="create">{{ $t('cra.akteurePanel.akteurAnlegen') }}</button>
    </div>

    <!-- Register -->
    <div class="form-card">
      <h4>{{ $t('cra.akteurePanel.erfassteAkteureV0', { v0: store.akteure.length }) }}</h4>
      <p v-if="!store.akteure.length" class="hint">{{ $t('cra.akteurePanel.nochKeineWirtschaftsakteureErfasst') }}</p>
      <table v-else class="akteure-table">
        <thead>
          <tr>
            <th>{{ $t('common.rolle') }}</th><th>{{ $t('common.name') }}</th><th>{{ $t('common.produkt') }}</th>
            <th>{{ $t('cra.akteurePanel.checkliste') }}</th><th>{{ $t('common.status') }}</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in store.akteure" :key="a.id">
            <td>{{ rolleLabel(a.rolle) }}</td>
            <td>{{ a.name || '—' }}</td>
            <td>{{ a.produkt || '—' }}</td>
            <td>
              <span :class="['pill', a.checkliste_vollstaendig ? 'ok' : 'warn']">
                {{ a.checkliste_vollstaendig ? $t('cra.akteurePanel.vollstandig') : $t('cra.akteurePanel.unvollstandig') }}
              </span>
            </td>
            <td>
              <select :value="a.status" @change="changeStatus(a, $event)">
                <option v-for="s in store.status" :key="s" :value="s">{{ statusLabel(s) }}</option>
              </select>
            </td>
            <td><button class="btn-link danger" @click="remove(a.id)">{{ $t('common.delete') }}</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useCraAkteureStore, type Akteur } from '../../stores/craAkteure'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'
import { t } from '../../i18n'

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
  return ({ importeur: t('cra.akteurePanel.importeurArt'), haendler: t('cra.akteurePanel.handlerArt'),
    bevollmaechtigter: t('cra.akteurePanel.bevollmachtigterArt'),
    // #1762: Art. 24. Der Verwalter ist ausdrücklich kein Hersteller — seine
    // Checkliste trägt deshalb keine CE-/DoC-Punkte (siehe cra/akteure_db.py).
    open_source_verwalter: 'Open-Source-Verwalter (Art. 24)',
  } as Record<string, string>)[r] || r
}
function statusLabel(s: string) {
  return ({ offen: t('common.offen'), in_pruefung: t('cra.akteurePanel.inPrufung'), konform: t('cra.akteurePanel.konform'),
    nicht_konform: t('cra.akteurePanel.nichtKonform') } as Record<string, string>)[s] || s
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
