<template>
  <div class="korrektur-panel">
    <div class="panel-header">
      <h3>↩️ Art. 13(19)-(22) — Korrekturmaßnahmen / Rückruf</h3>
      <p class="sub">Korrektur · Rücknahme vom Markt · Rückruf — betroffene Versionen
        & Mitgliedstaaten, Behördeninformation, Audit-Trail</p>
    </div>

    <div v-if="store.error" class="alert alert-error">{{ store.error }}</div>

    <!-- Anlage -->
    <div class="form-card">
      <h4>Korrekturmaßnahme erfassen</h4>
      <div class="form-grid">
        <div class="form-row">
          <label>Maßnahmentyp</label>
          <select v-model="form.massnahmentyp">
            <option v-for="t in store.typen" :key="t" :value="t">{{ typLabel(t) }}</option>
          </select>
        </div>
        <div class="form-row">
          <label>Titel</label>
          <input v-model="form.titel" />
        </div>
        <div class="form-row span2">
          <label>Auslöser (Nicht-Konformitäts-Befund)</label>
          <textarea v-model="form.ausloeser"></textarea>
        </div>
        <div class="form-row">
          <label>Betroffene Versionen / Chargen</label>
          <input v-model="form.betroffene_versionen" placeholder="z.B. v1.0 – v1.3" />
        </div>
        <div class="form-row">
          <label>Betroffene Mitgliedstaaten</label>
          <input v-model="form.betroffene_ms" placeholder="z.B. DE, FR, IT" />
        </div>
      </div>
      <button class="btn-primary" @click="create">Maßnahme anlegen</button>
    </div>

    <!-- Register -->
    <div class="form-card">
      <h4>Erfasste Maßnahmen ({{ store.massnahmen.length }})</h4>
      <p v-if="!store.massnahmen.length" class="hint">Noch keine Korrekturmaßnahmen erfasst.</p>
      <div v-for="m in store.massnahmen" :key="m.id" class="massnahme">
        <div class="massnahme-head">
          <span class="badge">{{ typLabel(m.massnahmentyp) }}</span>
          <strong>{{ m.titel || '(ohne Titel)' }}</strong>
          <span :class="['status', m.status]">{{ statusLabel(m.status) }}</span>
          <button class="btn-link danger" @click="remove(m.id)">Löschen</button>
        </div>
        <div class="massnahme-body">
          <p v-if="m.ausloeser"><em>Auslöser:</em> {{ m.ausloeser }}</p>
          <p><em>Versionen:</em> {{ m.betroffene_versionen || '—' }} ·
            <em>Mitgliedstaaten:</em> {{ m.betroffene_ms || '—' }}</p>
          <p>
            <em>Behörde:</em>
            <span v-if="m.behoerde_informiert" class="ok">
              ✓ informiert{{ m.behoerde_name ? ` (${m.behoerde_name})` : '' }}
              am {{ (m.behoerde_info_datum || '').slice(0, 10) }}
            </span>
            <span v-else class="warn">nicht informiert</span>
          </p>

          <div class="actions">
            <select :value="m.status" @change="changeStatus(m, $event)">
              <option v-for="s in store.status" :key="s" :value="s">{{ statusLabel(s) }}</option>
            </select>
            <template v-if="!m.behoerde_informiert">
              <input v-model="behoerdeName[m.id]" placeholder="Behörden-Name" class="behoerde-in" />
              <button class="btn-secondary" @click="inform(m.id)">Behörde informieren</button>
            </template>
          </div>

          <details v-if="m.audit_trail && m.audit_trail.length" class="audit">
            <summary>Audit-Trail ({{ m.audit_trail.length }})</summary>
            <ul>
              <li v-for="(ev, i) in m.audit_trail" :key="i">
                {{ (ev.ts || '').slice(0, 19).replace('T', ' ') }} — {{ ev.event }}
              </li>
            </ul>
          </details>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useCraKorrekturStore, type Korrektur } from '../../stores/craKorrektur'

const props = defineProps<{ projekt: string }>()
const store = useCraKorrekturStore()

const empty = () => ({
  massnahmentyp: 'korrektur', titel: '', ausloeser: '',
  betroffene_versionen: '', betroffene_ms: '',
})
const form = ref<any>(empty())
const behoerdeName = ref<Record<number, string>>({})

function typLabel(t: string) {
  return ({ korrektur: 'Korrektur', ruecknahme: 'Rücknahme vom Markt',
    rueckruf: 'Rückruf' } as Record<string, string>)[t] || t
}
function statusLabel(s: string) {
  return ({ offen: 'Offen', in_durchfuehrung: 'In Durchführung',
    behoerde_informiert: 'Behörde informiert',
    abgeschlossen: 'Abgeschlossen' } as Record<string, string>)[s] || s
}

async function create() {
  const ok = await store.createMassnahme(props.projekt, { ...form.value })
  if (ok) form.value = empty()
}
async function changeStatus(m: Korrektur, ev: Event) {
  const status = (ev.target as HTMLSelectElement).value
  await store.setStatus(props.projekt, m.id, status)
}
async function inform(id: number) {
  await store.informBehoerde(props.projekt, id, behoerdeName.value[id] || '')
  behoerdeName.value[id] = ''
}
async function remove(id: number) {
  await store.deleteMassnahme(props.projekt, id)
}

async function load() {
  await store.fetchMassnahmen(props.projekt)
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
.form-row.span2 { grid-column: 1 / 3; }
.form-row label { font-size: 12px; color: #455a64; margin-bottom: 2px; }
.massnahme { border: 1px solid #e0e6ee; border-radius: 6px; padding: 10px; margin-bottom: 10px; background: #fff; }
.massnahme-head { display: flex; align-items: center; gap: 8px; }
.badge { background: #90caf9; color: #0d47a1; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
.status { margin-left: auto; padding: 2px 8px; border-radius: 10px; font-size: 11px; background: #eceff1; color: #455a64; }
.status.abgeschlossen { background: #e8f5e9; color: #2e7d32; }
.massnahme-body { font-size: 13px; margin-top: 6px; }
.massnahme-body p { margin: 3px 0; }
.actions { display: flex; gap: 8px; align-items: center; margin: 8px 0; }
.behoerde-in { flex: 1; }
.ok { color: #2e7d32; }
.warn { color: #ef6c00; }
.audit { font-size: 12px; margin-top: 6px; }
.audit ul { margin: 4px 0 0 16px; }
.hint { color: #607d8b; font-size: 13px; }
.btn-link { background: none; border: none; cursor: pointer; color: #1565c0; }
.btn-link.danger { color: #c62828; margin-left: 8px; }
</style>
