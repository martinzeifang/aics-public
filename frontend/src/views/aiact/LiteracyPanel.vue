<template>
  <div class="lit-panel">
    <p v-if="!projekt" class="hint">Bitte zuerst ein AI-Act-Projekt auswählen.</p>

    <template v-else>
      <div class="lit-toolbar">
        <div class="toolbar-info">
          <strong>🎓 Art. 4 — AI-Literacy & Schulungsnachweise</strong>
          <span class="muted" v-if="store.summary">
            {{ store.summary.gesamt }} Nachweise · {{ store.summary.personen }} Personen ·
            {{ store.summary.abgelaufen }} abgelaufen · {{ store.summary.bald_faellig }} bald fällig
          </span>
        </div>
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>

      <!-- Kompetenzkonzept -->
      <section class="card">
        <h4>Kompetenzkonzept</h4>
        <p class="muted">Abgestuftes KI-Kompetenz-Konzept (Wissen/Erfahrung/Einsatzkontext) nach Art. 4.</p>
        <textarea v-model="konzeptText" rows="4" placeholder="Kompetenzkonzept beschreiben…"></textarea>
        <div class="row">
          <span class="muted" v-if="store.konzept.stand">Stand: {{ store.konzept.stand }}</span>
          <button class="btn-primary" :disabled="busy !== ''" @click="saveKonzept">💾 Konzept speichern</button>
        </div>
      </section>

      <!-- Nachweise -->
      <section class="card">
        <div class="row between">
          <h4>Schulungsnachweise</h4>
          <button class="btn-secondary" @click="addRow">➕ Nachweis</button>
        </div>
        <table class="lit-table" v-if="rows.length">
          <thead>
            <tr>
              <th>Rolle</th><th>Person</th><th>Modul</th><th>Level</th>
              <th>Durchgeführt</th><th>Gültig bis</th><th>Nachweis-Ref</th><th>Status</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(n, i) in rows" :key="n.id ?? ('new-' + i)" :class="statusClass(n.ablauf_status)">
              <td><input v-model="n.rolle" /></td>
              <td>
                <input v-model="n.person" list="oversight-list" />
              </td>
              <td><input v-model="n.schulungsmodul" /></td>
              <td>
                <select v-model="n.kompetenzlevel">
                  <option v-for="l in levels" :key="l" :value="l">{{ l }}</option>
                </select>
              </td>
              <td><input type="date" v-model="n.durchgefuehrt_am" /></td>
              <td><input type="date" v-model="n.gueltig_bis" /></td>
              <td><input v-model="n.nachweis_ref" /></td>
              <td><span class="pill" :class="statusClass(n.ablauf_status)">{{ statusLabel(n.ablauf_status) }}</span></td>
              <td class="actions">
                <button class="btn-small" :disabled="busy !== ''" @click="save(n)">💾</button>
                <button class="btn-small danger" v-if="n.id" :disabled="busy !== ''" @click="remove(n)">🗑️</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="muted">Noch keine Schulungsnachweise erfasst.</p>
        <datalist id="oversight-list">
          <option v-for="p in store.oversightPersonen" :key="p" :value="p" />
        </datalist>
        <p class="muted" v-if="store.oversightPersonen.length">
          💡 Vorschlag aus A4-Oversight (Art. 14): {{ store.oversightPersonen.join(', ') }}
        </p>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import { useAiactLiteracyStore, type LiteracyNachweis } from '../../stores/aiactLiteracy'

const aiact = useAiActStore()
const store = useAiactLiteracyStore()

const projekt = computed(() => aiact.selectedProjekt)
const busy = ref('')
const message = ref('')
const konzeptText = ref('')
const rows = ref<LiteracyNachweis[]>([])

const levels = computed(() => store.kompetenzlevel.length ? store.kompetenzlevel
  : ['grundlagen', 'anwender', 'fortgeschritten', 'experte'])

function emptyRow(): LiteracyNachweis {
  return reactive({
    rolle: '', person: '', schulungsmodul: '', kompetenzlevel: 'grundlagen',
    durchgefuehrt_am: '', gueltig_bis: '', nachweis_ref: '', oversight_person: '',
    kommentar: '',
  })
}

function statusClass(s?: string): string {
  return ({ abgelaufen: 'st-expired', bald: 'st-soon', gueltig: 'st-ok', unbefristet: 'st-none' } as Record<string, string>)[s || ''] || ''
}
function statusLabel(s?: string): string {
  return ({ abgelaufen: 'Abgelaufen', bald: 'Bald fällig', gueltig: 'Gültig', unbefristet: 'Unbefristet' } as Record<string, string>)[s || ''] || '—'
}

async function load() {
  if (!projekt.value) return
  await store.loadConstants()
  await store.load(projekt.value)
  konzeptText.value = store.konzept.konzept
  rows.value = store.nachweise.map(n => reactive({ ...n }))
}

function addRow() { rows.value.push(emptyRow()) }

async function saveKonzept() {
  if (!projekt.value) return
  busy.value = 'konzept'
  try {
    await store.saveKonzept(projekt.value, konzeptText.value)
    message.value = 'Kompetenzkonzept gespeichert.'
  } catch (e: any) {
    message.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
  } finally { busy.value = '' }
}

async function save(n: LiteracyNachweis) {
  if (!projekt.value) return
  busy.value = 'save'
  try {
    await store.saveNachweis(projekt.value, n)
    rows.value = store.nachweise.map(x => reactive({ ...x }))
    message.value = 'Nachweis gespeichert.'
  } catch (e: any) {
    message.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
  } finally { busy.value = '' }
}

async function remove(n: LiteracyNachweis) {
  if (!projekt.value || !n.id) return
  if (!confirm('Nachweis löschen?')) return
  busy.value = 'del'
  try {
    await store.deleteNachweis(projekt.value, n.id)
    rows.value = store.nachweise.map(x => reactive({ ...x }))
  } catch (e: any) {
    message.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
  } finally { busy.value = '' }
}

watch(projekt, load, { immediate: true })
</script>

<style scoped>
.lit-panel { padding: 8px 0; }
.hint { color: #607d8b; padding: 16px; }
.lit-toolbar { background: #1565c0; color: #fff; padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; }
.toolbar-info strong { color: #fff; }
.toolbar-info .muted { color: #90caf9; margin-left: 12px; }
.status-msg { color: #1565c0; margin: 8px 0; }
.card { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.card h4 { margin: 0 0 8px; color: #0d47a1; }
.card textarea, .card input, .card select { box-sizing: border-box; }
.card textarea { width: 100%; }
.row { display: flex; gap: 12px; align-items: center; margin-top: 8px; }
.row.between { justify-content: space-between; }
.muted { color: #78909c; font-size: 0.85em; }
.lit-table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
.lit-table th, .lit-table td { padding: 6px; border-bottom: 1px solid #eee; text-align: left; }
.lit-table th { background: #e3f2fd; color: #0d47a1; }
.lit-table input, .lit-table select { width: 100%; box-sizing: border-box; }
.actions { white-space: nowrap; }
.pill { padding: 2px 8px; border-radius: 10px; font-size: 0.8em; }
.st-expired { background: #ffebee; }
.st-soon { background: #fff8e1; }
.st-ok { background: #e8f5e9; }
.danger { color: #c62828; }
</style>
