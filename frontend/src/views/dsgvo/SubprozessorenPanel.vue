<template>
  <div class="sub-panel">
    <div class="intro-banner">
      <strong>🔗 Subprozessoren (Art. 28(2)/(4))</strong>
      <p class="hint">Weitere Auftragsverarbeiter nur mit vorheriger Genehmigung des
        Verantwortlichen; identische Datenschutzpflichten back-to-back weitergeben.</p>
    </div>

    <div v-if="!projektName" class="hint">Bitte zuerst ein Projekt auswählen.</div>
    <template v-else>
      <div class="toolbar">
        <button class="btn-secondary" @click="store.exportBericht(projektName!, 'docx')">📝 AVV-Bericht (Word)</button>
        <button class="btn-secondary" @click="store.exportBericht(projektName!, 'pdf')">📄 PDF</button>
      </div>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>
      <p v-if="!store.avv.length && !store.loading" class="hint">
        Keine Auftragsverarbeiter erfasst — bitte zunächst im AVV-Tracker (Dokumentation) anlegen.</p>

      <div v-for="a in store.avv" :key="a.id" class="avv-card">
        <div class="avv-head">
          <strong>{{ a.auftragsverarbeiter }}</strong>
          <span class="muted">{{ a.leistung }}</span>
          <span v-if="a.review_faellig" class="pill pill-rot">⚠ {{ a.sub_ausstehend }} ungenehmigt</span>
          <span v-else-if="a.sub_gesamt" class="pill pill-gruen">✓ alle genehmigt</span>
          <button class="btn-secondary" @click="toggle(a.id)">
            {{ open === a.id ? '▲' : '▼' }} Subprozessoren ({{ a.sub_gesamt }})
          </button>
        </div>

        <div v-if="open === a.id" class="sub-body">
          <table v-if="(store.subs[a.id] || []).length" class="grid">
            <thead>
              <tr><th>Name</th><th>Leistung</th><th>Drittland/Garantie</th>
                <th>Genehmigung</th><th>back-to-back</th><th>Aktionen</th></tr>
            </thead>
            <tbody>
              <tr v-for="s in store.subs[a.id]" :key="s.id">
                <td>{{ s.name }}</td>
                <td>{{ s.leistung }}</td>
                <td>{{ s.drittland ? 'Drittland — ' : '' }}{{ s.drittland_garantie || '—' }}</td>
                <td>
                  <span class="pill" :class="'pill-' + s.genehmigung_status">{{ s.genehmigung_status }}</span>
                  <span v-if="s.genehmigung_datum" class="muted"> {{ s.genehmigung_datum }}</span>
                </td>
                <td>{{ s.pflichten_backtoback ? '✓' : '✗' }}</td>
                <td class="actions">
                  <button class="btn-mini" @click="approve(a.id, s.id, 'genehmigt')">✓</button>
                  <button class="btn-mini" @click="approve(a.id, s.id, 'abgelehnt')">✗</button>
                  <button class="btn-secondary" @click="openEdit(a.id, s)">✏️</button>
                  <button class="btn-danger-mini" @click="del(a.id, s.id)">🗑️</button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="hint">— Keine Subprozessoren —</p>
          <button class="btn-primary" @click="openNew(a.id)">➕ Subprozessor</button>
        </div>
      </div>
    </template>

    <!-- Editor -->
    <div v-if="editing" class="modal-backdrop" @click.self="editing = null">
      <div class="modal">
        <h3>{{ editing.id ? 'Subprozessor bearbeiten' : 'Neuer Subprozessor' }}</h3>
        <label>Name <input v-model="editing.name" /></label>
        <label>Leistung <input v-model="editing.leistung" /></label>
        <label class="cb"><input type="checkbox" v-model="drittland" /> Drittland</label>
        <label>Drittland-Garantie
          <select v-model="editing.drittland_garantie">
            <option value="">—</option>
            <option value="SCC">SCC</option>
            <option value="Adäquanzbeschluss">Adäquanzbeschluss</option>
            <option value="BCR">BCR</option>
          </select>
        </label>
        <label>Genehmigungs-Status
          <select v-model="editing.genehmigung_status">
            <option value="ausstehend">ausstehend</option>
            <option value="genehmigt">genehmigt</option>
            <option value="abgelehnt">abgelehnt</option>
          </select>
        </label>
        <label>Genehmigungsdatum <input v-model="editing.genehmigung_datum" type="date" /></label>
        <label class="cb"><input type="checkbox" v-model="subAvv" /> Sub-AVV vorhanden</label>
        <label>Sub-AVV URL <input v-model="editing.sub_avv_url" /></label>
        <label class="cb"><input type="checkbox" v-model="backToBack" /> Identische Pflichten back-to-back weitergegeben (Art. 28(4))</label>
        <div class="modal-actions">
          <button class="btn-primary" @click="save">💾 Speichern</button>
          <button class="btn-secondary" @click="editing = null">Abbrechen</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useDsgvoSubprozessorenStore, type Subprozessor } from '../../stores/dsgvoSubprozessoren'

const props = defineProps<{ projektName: string | null }>()
const store = useDsgvoSubprozessorenStore()

const open = ref<number | null>(null)
const editing = ref<(Partial<Subprozessor> & { _avvPk?: number }) | null>(null)
const drittland = ref(false)
const subAvv = ref(false)
const backToBack = ref(false)

const load = () => { if (props.projektName) store.fetchAvv(props.projektName) }

const toggle = (avvPk: number) => {
  if (open.value === avvPk) { open.value = null; return }
  open.value = avvPk
  if (props.projektName) store.fetchSubs(props.projektName, avvPk)
}

const openNew = (avvPk: number) => {
  drittland.value = false; subAvv.value = false; backToBack.value = false
  editing.value = {
    _avvPk: avvPk, name: '', leistung: '', drittland_garantie: '',
    genehmigung_status: 'ausstehend', genehmigung_datum: '', sub_avv_url: '',
  }
}

const openEdit = (avvPk: number, s: Subprozessor) => {
  drittland.value = !!s.drittland; subAvv.value = !!s.sub_avv_vorhanden
  backToBack.value = !!s.pflichten_backtoback
  editing.value = { ...s, _avvPk: avvPk }
}

const save = async () => {
  if (!props.projektName || !editing.value) return
  const avvPk = editing.value._avvPk!
  const payload = {
    name: editing.value.name, leistung: editing.value.leistung,
    drittland: drittland.value ? 1 : 0, drittland_garantie: editing.value.drittland_garantie,
    genehmigung_status: editing.value.genehmigung_status,
    genehmigung_datum: editing.value.genehmigung_datum,
    sub_avv_vorhanden: subAvv.value ? 1 : 0, sub_avv_url: editing.value.sub_avv_url,
    pflichten_backtoback: backToBack.value ? 1 : 0,
  }
  const ok = editing.value.id
    ? await store.updateSub(props.projektName, avvPk, editing.value.id, payload)
    : await store.createSub(props.projektName, avvPk, payload)
  if (ok) editing.value = null
}

const approve = async (avvPk: number, pk: number, status: string) => {
  if (!props.projektName) return
  await store.setGenehmigung(props.projektName, avvPk, pk, status, new Date().toISOString().slice(0, 10))
}

const del = async (avvPk: number, pk: number) => {
  if (!props.projektName) return
  if (confirm('Subprozessor löschen?')) await store.deleteSub(props.projektName, avvPk, pk)
}

onMounted(load)
watch(() => props.projektName, load)
</script>

<style scoped>
.sub-panel { display: flex; flex-direction: column; gap: 14px; padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 8px; }
.intro-banner .hint { color: #1565c0; font-size: 13px; margin: 4px 0 0; }
.hint { color: #666; font-size: 13px; }
.muted { color: #888; font-size: 12px; }
.toolbar { display: flex; gap: 8px; }
.avv-card { border: 1px solid var(--color-border, #ddd); border-radius: 8px; padding: 10px 14px; background: white; }
.avv-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.sub-body { margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }
.grid { width: 100%; border-collapse: collapse; font-size: 13px; }
.grid th, .grid td { border: 1px solid var(--color-border, #ddd); padding: 6px 8px; text-align: left; }
.grid th { background: #1565c0; color: white; }
.actions { display: flex; gap: 4px; flex-wrap: wrap; }
.pill { padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.pill-gruen, .pill-genehmigt { background: #e8f5e9; color: #2e7d32; }
.pill-rot, .pill-abgelehnt { background: #ffebee; color: #c62828; }
.pill-ausstehend { background: #fff8e1; color: #f57f17; }
.btn-primary { background: #1565c0; color: white; border: none; padding: 7px 12px; border-radius: 4px; cursor: pointer; align-self: flex-start; }
.btn-secondary { background: #e0e0e0; color: #333; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.btn-mini { background: #c8e6c9; color: #2e7d32; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.btn-danger-mini { background: #ffcdd2; color: #b71c1c; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.msg { font-size: 13px; }
.msg.err { color: #c62828; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: white; border-radius: 8px; padding: 20px 24px; width: min(540px, 92vw); max-height: 88vh; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.modal h3 { color: #1565c0; margin: 0 0 8px; }
.modal label { display: flex; flex-direction: column; font-size: 13px; gap: 2px; }
.modal label.cb { flex-direction: row; align-items: center; gap: 6px; }
.modal input, .modal select { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
.modal-actions { display: flex; gap: 8px; margin-top: 12px; }
</style>
