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

    <!-- #1671: CE-Kennzeichnung (Modul A: Hersteller bringt selbst an) -->
    <div class="form-card ce">
      <h4>CE-Kennzeichnung</h4>
      <p class="hint">Bei Modul A (Selbstbewertung) bringst du das CE-Zeichen nach Ausstellung der
        EU-Konformitätserklärung in Eigenverantwortung an. Es wird nicht beantragt.</p>
      <div class="ce-logo-row">
        <div class="ce-preview" v-html="CE_SVG"></div>
        <div>
          <button class="btn-secondary" @click="downloadCeLogo">⬇️ CE-Logo (SVG) herunterladen</button>
          <p class="hint small">Referenzdarstellung. Beim Skalieren Proportionen beibehalten,
            Mindesthöhe 5&nbsp;mm, sichtbar/lesbar/dauerhaft (Reg. (EG) 765/2008 Art.&nbsp;30).</p>
        </div>
      </div>
      <ul class="ce-check">
        <li>EU-Konformitätserklärung ausgestellt (Voraussetzung)</li>
        <li>CE am Produkt bzw. — falls nicht möglich — auf Verpackung/Begleitunterlagen angebracht</li>
        <li>Mindesthöhe 5&nbsp;mm, Proportionen gewahrt, dauerhaft &amp; gut sichtbar</li>
        <li>Bei Software: z.&nbsp;B. im Info-/Über-Dialog und in der Dokumentation</li>
      </ul>
      <div class="form-row">
        <label>Angebracht am</label>
        <input type="date" v-model="form.ce_angebracht_am" />
      </div>
      <div class="form-row">
        <label>Ort der Anbringung</label>
        <input v-model="form.ce_ort" placeholder="z. B. Info-Dialog, Handbuch S. 1, Verpackung" />
      </div>
      <div class="form-row">
        <label>Nachweis / Bemerkung</label>
        <textarea v-model="form.ce_nachweis" rows="2" placeholder="Beleg, Screenshot-Referenz, Verantwortliche/r …"></textarea>
      </div>
      <button class="btn-primary" @click="save">CE-Kennzeichnung speichern</button>
    </div>

    <!-- #1208: Wesentliche Änderung + Release-Versionierung (Art. 13(4)) -->
    <div class="form-card release">
      <h4>Art. 13(4) — Wesentliche Änderung / Release</h4>
      <p class="hint">Aktuelle Version: <strong>{{ releaseStore.release.aktuelle_version || 'v1.0' }}</strong></p>
      <div v-if="hasReassess" class="reassess-box">
        <p class="hint">Nach einer wesentlichen Änderung sind diese Bausteine für die neue Version
          <strong>erneut zu bestätigen</strong> (Art. 13(4)) — „offen" heißt „noch nicht bestätigt",
          nicht „leer". Nach Prüfung abhaken:</p>
        <ul class="reassess">
          <li v-for="(v, k) in releaseStore.release.reassess" :key="k">
            <label>
              <input type="checkbox" :checked="v !== 'offen'"
                     @change="toggleReassess(k, ($event.target as HTMLInputElement).checked)" />
              {{ reassessLabel(k) }}:
              <span :class="v === 'offen' ? 'offen' : 'ok'">{{ v === 'offen' ? 'zu bestätigen' : 'bestätigt' }}</span>
            </label>
          </li>
        </ul>
      </div>
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

const REASSESS_LABELS: Record<string, string> = {
  risikobewertung: 'Cybersicherheits-Risikobewertung',
  konformitaetsbewertung: 'Konformitätsbewertung',
  technische_doku: 'Technische Dokumentation',
  doc: 'EU-Konformitätserklärung',
}
const reassessLabel = (k: string) => REASSESS_LABELS[k] || k
async function toggleReassess(k: string, checked: boolean) {
  await releaseStore.setReassess(props.projekt, k, checked ? 'erledigt' : 'offen')
}

async function doSubstantialMod() {
  if (await releaseStore.substantialModification(
    props.projekt, modForm.value.neue_version, modForm.value.grund)) {
    modForm.value = { neue_version: '', grund: '' }
  }
}

const form = ref<any>({ bewertungsweg: 'A', checkliste: {}, nb_kennnummer: '',
  eucc_level: '', ce_status: 'offen', bewertung_abgeschlossen: false,
  ce_ort: '', ce_angebracht_am: '', ce_nachweis: '' })
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
      ce_ort: r.ce_ort || '', ce_angebracht_am: (r.ce_angebracht_am || '').slice(0, 10),
      ce_nachweis: r.ce_nachweis || '',
    }
  }
}

// #1671: konformes CE-Logo als SVG herunterladen (Proportionen nach Reg. (EG) 765/2008).
const CE_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 228 128" width="228" height="128">
<g fill="#000">
<path d="M64 8 A56 56 0 1 0 64 120 A56 56 0 0 0 112 92 L96 83 A38 38 0 1 1 96 45 L112 36 A56 56 0 0 0 64 8 Z"/>
<path d="M172 8 A56 56 0 1 0 172 120 A56 56 0 0 0 220 92 L204 83 A38 38 0 1 1 204 45 L220 36 A56 56 0 0 0 172 8 Z M150 55 H196 V73 H150 Z"/>
</g>
</svg>`
function downloadCeLogo() {
  const blob = new Blob([CE_SVG], { type: 'image/svg+xml' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = 'CE-Kennzeichen.svg'; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 10000)
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
/* #1671: CE-Kennzeichnung */
.ce-logo-row { display: flex; gap: 16px; align-items: center; margin: 8px 0; }
.ce-preview { width: 72px; flex: 0 0 72px; }
.ce-preview :deep(svg) { width: 72px; height: auto; }
.ce-check { margin: 8px 0 12px 18px; font-size: 12px; color: #455a64; }
.ce-check li { margin: 2px 0; }
.hint.small { font-size: 11px; }
</style>
