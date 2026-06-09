<template>
  <div class="konf-panel">
    <div class="panel-header">
      <h3>✅ Art. 32 / Annex VIII — Konformitätsbewertung & DoC/CE</h3>
      <p class="sub">Bewertungsweg (Modul A | B+C | H | EUCC) · NB-Kennnummer ·
        EU-Konformitätserklärung · CE-Kennzeichnung</p>
    </div>

    <div v-if="store.error" class="alert alert-error">{{ store.error }}</div>

    <div class="form-card">
      <div class="form-row">
        <label>Bewertungsweg</label>
        <select v-model="form.bewertungsweg">
          <option v-for="w in store.wege" :key="w" :value="w">{{ wegLabel(w) }}</option>
        </select>
      </div>
      <div class="form-row">
        <label>Nachweis-Checkliste (Modul {{ form.bewertungsweg }})</label>
        <div class="checkliste">
          <label v-for="n in sollNachweise" :key="n" class="check-item">
            <input type="checkbox" v-model="form.checkliste[n]" /> {{ nachweisLabel(n) }}
          </label>
        </div>
      </div>
      <div class="form-row">
        <label>Notified-Body-Kennnummer</label>
        <input v-model="form.nb_kennnummer" placeholder="z.B. 0123" />
      </div>
      <div class="form-row" v-if="form.bewertungsweg === 'EUCC'">
        <label>EUCC-Level</label>
        <input v-model="form.eucc_level" placeholder="z.B. EAL4+" />
      </div>
      <div class="form-row">
        <label>CE-Status</label>
        <select v-model="form.ce_status">
          <option v-for="s in store.ceStatus" :key="s" :value="s">{{ ceLabel(s) }}</option>
        </select>
      </div>
      <div class="form-row">
        <label class="check-item">
          <input type="checkbox" v-model="form.bewertung_abgeschlossen" />
          Bewertungsweg abgeschlossen
        </label>
      </div>
      <button class="btn-primary" @click="save">Speichern</button>
    </div>

    <div class="form-card doc">
      <h4>EU-Konformitätserklärung (Annex V)</h4>
      <p v-if="!form.bewertung_abgeschlossen" class="hint warn">
        DoC erst ausstellbar, wenn der Bewertungsweg abgeschlossen ist.
      </p>
      <div class="form-row">
        <label>Modell / Produktidentifikation</label>
        <input v-model="docForm.modell" />
      </div>
      <div class="form-row">
        <label>Hersteller</label>
        <input v-model="docForm.hersteller" />
      </div>
      <button class="btn-primary" :disabled="!form.bewertung_abgeschlossen" @click="issueDoc">
        DoC ausstellen
      </button>
      <p v-if="store.record.doc_ausgestellt" class="hint ok">
        ✓ DoC v{{ store.record.doc_version }} ausgestellt am
        {{ (store.record.doc_ausgestellt_am || '').slice(0, 10) }}
      </p>
    </div>

    <!-- #1208: Wesentliche Änderung + Release-Versionierung (Art. 13(4)) -->
    <div class="form-card release">
      <h4>Art. 13(4) — Wesentliche Änderung / Release</h4>
      <p class="hint">Aktuelle Version: <strong>{{ releaseStore.release.aktuelle_version || 'v1.0' }}</strong></p>
      <ul v-if="hasReassess" class="reassess">
        <li v-for="(v, k) in releaseStore.release.reassess" :key="k">
          {{ k }}: <span :class="v === 'offen' ? 'offen' : 'ok'">{{ v }}</span>
        </li>
      </ul>
      <div class="form-row">
        <label>Neue Version</label>
        <input v-model="modForm.neue_version" placeholder="z.B. v2.0" />
      </div>
      <div class="form-row">
        <label>Grund der wesentlichen Änderung</label>
        <textarea v-model="modForm.grund"></textarea>
      </div>
      <button class="btn-primary" @click="doSubstantialMod">Wesentliche Änderung erfassen</button>
      <p v-if="releaseStore.error" class="hint warn">{{ releaseStore.error }}</p>
      <div v-if="releaseStore.snapshots.length" class="snapshots">
        <h5>Eingefrorene Vorgänger-Versionen</h5>
        <ul>
          <li v-for="s in releaseStore.snapshots" :key="s.id">
            {{ s.version }} — {{ s.grund }} ({{ (s.eingefroren_am || '').slice(0, 10) }})
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useCraKonformitaetStore } from '../../stores/craKonformitaet'
import { useCraReleaseStore } from '../../stores/craRelease'

const props = defineProps<{ projekt: string }>()
const store = useCraKonformitaetStore()
const releaseStore = useCraReleaseStore()
const modForm = ref<any>({ neue_version: '', grund: '' })
const hasReassess = computed(() =>
  Object.keys(releaseStore.release.reassess || {}).length > 0)

async function doSubstantialMod() {
  if (await releaseStore.substantialModification(
    props.projekt, modForm.value.neue_version, modForm.value.grund)) {
    modForm.value = { neue_version: '', grund: '' }
  }
}

const form = ref<any>({ bewertungsweg: 'A', checkliste: {}, nb_kennnummer: '',
  eucc_level: '', ce_status: 'offen', bewertung_abgeschlossen: false })
const docForm = ref<any>({ modell: '', hersteller: '' })

const sollNachweise = computed(() => store.checkliste[form.value.bewertungsweg] || [])

function wegLabel(w: string) {
  return ({ A: 'Modul A (Selbstbewertung)', 'B+C': 'Modul B+C (Baumusterprüfung)',
    H: 'Modul H (Umfassendes QM)', EUCC: 'EUCC-Zertifizierung' } as Record<string, string>)[w] || w
}
function ceLabel(s: string) {
  return ({ offen: 'Offen', in_bewertung: 'In Bewertung',
    bewertung_abgeschlossen: 'Bewertung abgeschlossen', doc_ausgestellt: 'DoC ausgestellt',
    ce_angebracht: 'CE angebracht' } as Record<string, string>)[s] || s
}
function nachweisLabel(n: string) {
  return n.replace(/_/g, ' ')
}

function loadFromRecord() {
  const r = store.record as any
  if (r && r.bewertungsweg) {
    form.value = {
      bewertungsweg: r.bewertungsweg, checkliste: { ...(r.checkliste || {}) },
      nb_kennnummer: r.nb_kennnummer || '', eucc_level: r.eucc_level || '',
      ce_status: r.ce_status || 'offen',
      bewertung_abgeschlossen: !!r.bewertung_abgeschlossen,
    }
  }
}

async function save() {
  await store.save(props.projekt, { ...form.value })
  loadFromRecord()
}
async function issueDoc() {
  if (await store.issueDoc(props.projekt, { ...docForm.value })) loadFromRecord()
}

async function load() {
  await store.fetch(props.projekt)
  loadFromRecord()
  await releaseStore.fetch(props.projekt)
}

onMounted(async () => { await store.fetchConstants(); await load() })
watch(() => props.projekt, load)
</script>

<style scoped>
.panel-header h3 { color: #1565c0; margin-bottom: 4px; }
.panel-header .sub { color: #607d8b; font-size: 13px; }
.form-card { background: #f5f8fc; border: 1px solid #cfd8e3; border-radius: 8px; padding: 16px; margin: 12px 0; }
.form-row { display: flex; flex-direction: column; margin-bottom: 8px; }
.form-row label { font-size: 12px; color: #455a64; margin-bottom: 2px; }
.checkliste { display: flex; flex-direction: column; gap: 4px; }
.check-item { flex-direction: row; align-items: center; gap: 6px; }
.hint.warn { color: #c62828; }
.hint.ok { color: #2e7d32; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.reassess { margin: 6px 0 0 18px; font-size: 12px; }
.reassess .offen { color: #c62828; font-weight: 600; }
.reassess .ok { color: #2e7d32; }
.snapshots { margin-top: 10px; font-size: 12px; }
.snapshots h5 { margin: 4px 0; color: #455a64; }
</style>
