<template>
  <div class="korrektur-panel">
    <div class="panel-header">
      <h3>{{ $t('cra.korrekturPanel.artKorrekturmassnahmenRuckruf') }}</h3>
      <p class="sub">{{ $t('cra.korrekturPanel.korrekturRucknahmeVomMarktRuckrufBet') }}</p>
    </div>

    <FehlerHinweis :text="store.error" @close="store.error = ''" />

    <!-- Anlage -->
    <div class="form-card">
      <h4>{{ $t('cra.korrekturPanel.korrekturmassnahmeErfassen') }}</h4>
      <div class="form-grid">
        <div class="form-row">
          <label>{{ $t('cra.korrekturPanel.massnahmentyp') }}</label>
          <select v-model="form.massnahmentyp">
            <option v-for="t in store.typen" :key="t" :value="t">{{ typLabel(t) }}</option>
          </select>
        </div>
        <div class="form-row">
          <label>{{ $t('common.titel') }}</label>
          <input v-model="form.titel" />
        </div>
        <div class="form-row span2">
          <label>{{ $t('cra.korrekturPanel.ausloserNichtKonformitatsBefund') }}</label>
          <textarea v-model="form.ausloeser"></textarea>
        </div>
        <div class="form-row">
          <label>{{ $t('cra.korrekturPanel.betroffeneVersionenChargen') }}</label>
          <input v-model="form.betroffene_versionen" placeholder="z.B. v1.0 – v1.3" />
        </div>
        <div class="form-row">
          <label>{{ $t('cra.korrekturPanel.betroffeneMitgliedstaaten') }}</label>
          <input v-model="form.betroffene_ms" placeholder="z.B. DE, FR, IT" />
        </div>
      </div>
      <button class="btn-primary" @click="create">{{ $t('cra.korrekturPanel.massnahmeAnlegen') }}</button>
    </div>

    <!-- Register -->
    <div class="form-card">
      <h4>{{ $t('cra.korrekturPanel.erfassteMassnahmenV0', { v0: store.massnahmen.length }) }}</h4>
      <p v-if="!store.massnahmen.length" class="hint">{{ $t('cra.korrekturPanel.nochKeineKorrekturmassnahmenErfasst') }}</p>
      <div v-for="m in store.massnahmen" :key="m.id" class="massnahme">
        <div class="massnahme-head">
          <span class="badge">{{ typLabel(m.massnahmentyp) }}</span>
          <strong>{{ m.titel || $t('cra.korrekturPanel.ohneTitel') }}</strong>
          <span :class="['status', m.status]">{{ statusLabel(m.status) }}</span>
          <button class="btn-link danger" @click="remove(m.id)">{{ $t('common.delete') }}</button>
        </div>
        <div class="massnahme-body">
          <p v-if="m.ausloeser"><em>{{ $t('cra.korrekturPanel.ausloser') }}</em> {{ m.ausloeser }}</p>
          <p><em>{{ $t('cra.korrekturPanel.versionen') }}</em> {{ m.betroffene_versionen || '—' }} ·
            <em>{{ $t('cra.korrekturPanel.mitgliedstaaten') }}</em> {{ m.betroffene_ms || '—' }}</p>
          <p>
            <em>{{ $t('cra.korrekturPanel.behorde') }}</em>
            <span v-if="m.behoerde_informiert" class="ok">
              ✓ informiert{{ m.behoerde_name ? ` (${m.behoerde_name})` : '' }}
              am {{ (m.behoerde_info_datum || '').slice(0, 10) }}
            </span>
            <span v-else class="warn">{{ $t('cra.korrekturPanel.nichtInformiert') }}</span>
          </p>

          <div class="actions">
            <select :value="m.status" @change="changeStatus(m, $event)">
              <option v-for="s in store.status" :key="s" :value="s">{{ statusLabel(s) }}</option>
            </select>
            <template v-if="!m.behoerde_informiert">
              <input v-model="behoerdeName[m.id]" :placeholder="$t('cra.korrekturPanel.behordenName')" class="behoerde-in" />
              <button class="btn-secondary" @click="inform(m.id)">{{ $t('cra.korrekturPanel.behordeInformieren') }}</button>
            </template>
          </div>

          <details v-if="m.audit_trail && m.audit_trail.length" class="audit">
            <summary>{{ $t('cra.korrekturPanel.auditTrailV0', { v0: m.audit_trail.length }) }}</summary>
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
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'
// `t` ist in dieser Maske schon belegt (lokale Variable/Parameter) —
// deshalb unter anderem Namen. Ein Import überdeckt eine lokale
// Bindung nicht, er kollidiert mit ihr: Der Aufruf trifft die
// Variable, und die ist keine Funktion. Gefunden hat das der
// Typprüfer (#1858), nicht der Build.
import { t as uebersetze } from '../../i18n'

const props = defineProps<{ projekt: string }>()
const store = useCraKorrekturStore()

const empty = () => ({
  massnahmentyp: 'korrektur', titel: '', ausloeser: '',
  betroffene_versionen: '', betroffene_ms: '',
})
const form = ref<any>(empty())
const behoerdeName = ref<Record<number, string>>({})

function typLabel(t: string) {
  return ({ korrektur: uebersetze('cra.korrekturPanel.korrektur'), ruecknahme: uebersetze('cra.korrekturPanel.rucknahmeVomMarkt'),
    rueckruf: uebersetze('cra.korrekturPanel.ruckruf') } as Record<string, string>)[t] || t
}
function statusLabel(s: string) {
  return ({ offen: uebersetze('common.offen'), in_durchfuehrung: uebersetze('cra.korrekturPanel.inDurchfuhrung'),
    behoerde_informiert: uebersetze('cra.korrekturPanel.behordeInformiert'),
    abgeschlossen: uebersetze('common.abgeschlossen') } as Record<string, string>)[s] || s
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
