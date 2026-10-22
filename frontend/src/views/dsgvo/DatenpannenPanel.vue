<template>
  <div class="datenpannen-panel">
    <div class="intro-banner">
      <strong>🚨 Datenpannen (Art. 33/34)</strong>
      <p class="hint">Meldung an die Aufsichtsbehörde unverzüglich, möglichst binnen
        <strong>72 Stunden</strong> nach Bekanntwerden (Art. 33(1)). Countdown +
        Überfälligkeits-Alarm je Vorfall; strukturiertes Art.-33(3)-Meldeformular als Export.</p>
    </div>

    <div v-if="!projektName" class="hint">Bitte zuerst ein Projekt auswählen.</div>
    <template v-else>
      <button class="btn-primary" @click="openNew">➕ Neue Datenpanne</button>

      <p v-if="store.error" class="msg err">{{ store.error }}</p>
      <p v-if="store.loading" class="hint">⏳ Lädt…</p>

      <div v-if="overdueCount > 0" class="alarm">
        ⚠ {{ overdueCount }} Datenpanne(n) mit überschrittener 72-h-Frist (Art. 33(1)).
      </div>

      <table v-if="store.pannen.length" class="grid">
        <thead>
          <tr>
            <th>ID</th><th>Titel</th><th>Festgestellt</th>
            <th>72-h-Frist</th><th>Status</th><th>Aktionen</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in store.pannen" :key="p.id">
            <td>{{ p.panne_id }}</td>
            <td>{{ p.titel }}</td>
            <td>{{ p.festgestellt_am }}</td>
            <td>
              <span class="pill" :class="'pill-' + p.frist.ampel">
                {{ countdownLabel(p) }}
              </span>
            </td>
            <td>{{ p.status }}</td>
            <td class="actions">
              <button class="btn-secondary" @click="openEdit(p)">✏️</button>
              <button class="btn-secondary" :disabled="busy === p.id + ':docx'"
                @click="exportForm(p, 'docx')">📝 Meldeformular</button>
              <button class="btn-secondary" :disabled="busy === p.id + ':pdf'"
                @click="exportForm(p, 'pdf')">📄 PDF</button>
              <button class="btn-danger-mini" @click="del(p)">🗑️</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else-if="!store.loading" class="hint">— Keine Datenpannen erfasst —</p>
    </template>

    <!-- Editor -->
    <div v-if="editing" class="modal-backdrop" @click.self="editing = null">
      <div class="modal">
        <h3>{{ editing.id ? 'Datenpanne bearbeiten' : 'Neue Datenpanne' }}</h3>
        <label>Vorfall-ID <input v-model="editing.panne_id" placeholder="DSGVO-P-2026-001" /></label>
        <label>Titel <input v-model="editing.titel" /></label>
        <label>Art
          <select v-model="editing.art">
            <option value="vertraulichkeit">Vertraulichkeit</option>
            <option value="integritaet">Integrität</option>
            <option value="verfuegbarkeit">Verfügbarkeit</option>
          </select>
        </label>
        <label>Festgestellt am <input v-model="editing.festgestellt_am" type="date" /></label>
        <label>Beschreibung <textarea v-model="editing.beschreibung" rows="2"></textarea></label>
        <label>Datenkategorien <input v-model="editing.datenkategorien" /></label>
        <label>Betroffene (Anzahl) <input v-model.number="editing.betroffene_anzahl" type="number" min="0" /></label>
        <label>Risikoeinschätzung
          <select v-model="editing.risikoeinschaetzung">
            <option value="gering">gering</option>
            <option value="mittel">mittel</option>
            <option value="hoch">hoch</option>
          </select>
        </label>
        <label>Sofortmaßnahmen <textarea v-model="editing.sofortmassnahmen" rows="2"></textarea></label>
        <label>Status
          <select v-model="editing.status">
            <option value="offen">offen</option>
            <option value="gemeldet">gemeldet</option>
            <option value="abgeschlossen">abgeschlossen</option>
          </select>
        </label>
        <label class="cb"><input type="checkbox" v-model="aufsichtPflicht" /> Meldung an Aufsicht erforderlich (Art. 33)</label>
        <label class="cb"><input type="checkbox" v-model="betroffenePflicht" /> Meldung an Betroffene erforderlich (Art. 34)</label>
        <div class="modal-actions">
          <button class="btn-primary" @click="save">💾 Speichern</button>
          <button class="btn-secondary" @click="editing = null">Abbrechen</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useDsgvoDatenpannenStore, type Datenpanne } from '../../stores/dsgvoDatenpannen'

const props = defineProps<{ projektName: string | null }>()
const store = useDsgvoDatenpannenStore()

const editing = ref<Partial<Datenpanne> | null>(null)
const aufsichtPflicht = ref(false)
const betroffenePflicht = ref(false)
const busy = ref('')

const overdueCount = computed(() => store.pannen.filter((p) => p.frist?.overdue).length)

const countdownLabel = (p: Datenpanne): string => {
  const f = p.frist
  if (!f || f.ampel === 'grau') return f?.due_at ? '— erledigt —' : 'keine Frist'
  if (f.overdue) return `überfällig (${Math.abs(Math.round(f.hours_left || 0))} h)`
  return `${Math.round(f.hours_left || 0)} h verbleibend`
}

const load = () => { if (props.projektName) store.fetchPannen(props.projektName) }

const openNew = () => {
  aufsichtPflicht.value = false
  betroffenePflicht.value = false
  editing.value = {
    panne_id: '', titel: '', art: 'vertraulichkeit', festgestellt_am: '',
    beschreibung: '', datenkategorien: '', betroffene_anzahl: 0,
    risikoeinschaetzung: 'gering', sofortmassnahmen: '', status: 'offen',
  }
}

const openEdit = (p: Datenpanne) => {
  aufsichtPflicht.value = !!p.meldung_aufsicht_pflicht
  betroffenePflicht.value = !!p.meldung_betroffene_pflicht
  editing.value = { ...p }
}

const save = async () => {
  if (!props.projektName || !editing.value) return
  const payload = {
    ...editing.value,
    meldung_aufsicht_pflicht: aufsichtPflicht.value ? 1 : 0,
    meldung_betroffene_pflicht: betroffenePflicht.value ? 1 : 0,
  }
  if (await store.savePanne(props.projektName, payload)) editing.value = null
}

const del = async (p: Datenpanne) => {
  if (!props.projektName) return
  if (confirm(`Datenpanne ${p.panne_id} löschen?`)) await store.deletePanne(props.projektName, p.id)
}

const exportForm = async (p: Datenpanne, fmt: 'docx' | 'pdf') => {
  if (!props.projektName) return
  busy.value = `${p.id}:${fmt}`
  await store.exportMeldeformular(props.projektName, p.id, fmt)
  busy.value = ''
}

onMounted(load)
watch(() => props.projektName, load)
</script>

<style scoped>
.datenpannen-panel { display: flex; flex-direction: column; gap: 14px; padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 8px; }
.intro-banner .hint { color: #1565c0; font-size: 13px; margin: 4px 0 0; }
.hint { color: #666; font-size: 13px; }
.alarm { background: #ffebee; border-left: 4px solid #c62828; color: #c62828; padding: 10px 14px; border-radius: 6px; font-weight: 600; }
.grid { width: 100%; border-collapse: collapse; font-size: 13px; }
.grid th, .grid td { border: 1px solid var(--color-border, #ddd); padding: 6px 8px; text-align: left; }
.grid th { background: #1565c0; color: white; }
.actions { display: flex; gap: 4px; flex-wrap: wrap; }
.pill { padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; white-space: nowrap; }
.pill-gruen { background: #e8f5e9; color: #2e7d32; }
.pill-gelb { background: #fff8e1; color: #f57f17; }
.pill-rot { background: #ffebee; color: #c62828; }
.pill-grau { background: #eceff1; color: #607d8b; }
.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 14px; border-radius: 4px; cursor: pointer; align-self: flex-start; }
.btn-secondary { background: #e0e0e0; color: #333; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-danger-mini { background: #ffcdd2; color: #b71c1c; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.msg { font-size: 13px; }
.msg.err { color: #c62828; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: white; border-radius: 8px; padding: 20px 24px; width: min(560px, 92vw); max-height: 88vh; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.modal h3 { color: #1565c0; margin: 0 0 8px; }
.modal label { display: flex; flex-direction: column; font-size: 13px; gap: 2px; }
.modal label.cb { flex-direction: row; align-items: center; gap: 6px; }
.modal input, .modal select, .modal textarea { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
.modal-actions { display: flex; gap: 8px; margin-top: 12px; }
</style>
