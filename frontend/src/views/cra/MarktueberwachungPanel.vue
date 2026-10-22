<template>
  <div class="marktaufsicht-panel">
    <div class="panel-header">
      <h3>🏛️ Art. 52–56 — Vorgänge der Marktüberwachung</h3>
      <p class="sub">Behördenanfragen · Anordnungen · Fristen · bereitgestellte
        Unterlagen. Hier liegt der Fall, in dem <em>die Behörde</em> aktiv wird —
        die Korrekturmaßnahmen oben sind der umgekehrte.</p>
    </div>

    <div v-if="store.error" class="alert alert-error">{{ store.error }}</div>

    <!-- Fristenlage zuerst: ohne sie ist das Register nur eine Ablage -->
    <div class="kpi-zeile">
      <span class="kpi">Vorgänge: <strong>{{ store.uebersicht.gesamt || 0 }}</strong></span>
      <span class="kpi">laufend: <strong>{{ store.uebersicht.laufend || 0 }}</strong></span>
      <span :class="['kpi', (store.uebersicht.versaeumt || 0) > 0 ? 'kpi-rot' : '']">
        Frist versäumt: <strong>{{ store.uebersicht.versaeumt || 0 }}</strong>
      </span>
      <span v-if="store.uebersicht.naechste_frist" class="kpi">
        nächste Frist: <strong>{{ store.uebersicht.naechste_frist.frist_am }}</strong>
        ({{ store.uebersicht.naechste_frist.tage_verbleibend }} Tage)
      </span>
    </div>
    <p v-if="(store.uebersicht.versaeumt || 0) > 0" class="hinweis-rot">
      Eine versäumte Behördenfrist macht den Release-Check rot — wie eine
      versäumte Meldefrist nach Art. 14. Vorgang beantworten und die
      bereitgestellten Unterlagen hier festhalten.
    </p>

    <!-- Anlage -->
    <div class="form-card">
      <h4>Vorgang erfassen</h4>
      <div class="form-grid">
        <div class="form-row">
          <label>Vorgangsart</label>
          <select v-model="form.vorgangsart">
            <option v-for="a in store.vorgangsarten" :key="a" :value="a">{{ artLabel(a) }}</option>
          </select>
        </div>
        <div class="form-row">
          <label>Behörde</label>
          <input v-model="form.behoerde_name" placeholder="z. B. Bundesnetzagentur" />
        </div>
        <div class="form-row">
          <label>Mitgliedstaat</label>
          <input v-model="form.behoerde_land" placeholder="z. B. DE" />
        </div>
        <div class="form-row">
          <label>Aktenzeichen der Behörde</label>
          <input v-model="form.aktenzeichen" placeholder="z. B. MÜ-2026/4711" />
        </div>
        <div class="form-row">
          <label>Eingang</label>
          <input v-model="form.eingang_am" type="date" />
        </div>
        <div class="form-row">
          <label>Frist der Behörde</label>
          <input v-model="form.frist_am" type="date" />
        </div>
        <div class="form-row span2">
          <label>Gegenstand</label>
          <input v-model="form.gegenstand" placeholder="worum es geht" />
        </div>
        <div class="form-row span2">
          <label>Verlangen der Behörde</label>
          <textarea v-model="form.verlangen" rows="2"
                    placeholder="welche Unterlagen/Maßnahmen verlangt werden"></textarea>
        </div>
        <div class="form-row">
          <label>Betroffene Versionen</label>
          <input v-model="form.betroffene_versionen" placeholder="z. B. 7.4.0 – 8.0.0" />
        </div>
      </div>
      <button class="btn-primary" @click="create">Vorgang anlegen</button>
    </div>

    <!-- Register -->
    <div class="form-card">
      <h4>Erfasste Vorgänge ({{ store.vorgaenge.length }})</h4>
      <p v-if="!store.vorgaenge.length" class="hint">
        Noch kein Vorgang erfasst. Das ist der Normalfall — wichtig ist, dass der
        erste Vorgang nicht im Postfach bleibt.
      </p>
      <div v-for="v in store.vorgaenge" :key="v.id" class="vorgang">
        <div class="vorgang-head">
          <span class="badge">{{ artLabel(v.vorgangsart) }}</span>
          <strong>{{ v.aktenzeichen || `Vorgang #${v.id}` }}</strong>
          <span class="behoerde">{{ v.behoerde_name }}{{ v.behoerde_land ? ` (${v.behoerde_land})` : '' }}</span>
          <span :class="['ampel', `ampel-${v.frist.ampel}`]" :title="fristTitel(v)">
            {{ fristText(v) }}
          </span>
          <span :class="['status', v.status]">{{ statusLabel(v.status) }}</span>
          <button class="btn-link danger" @click="remove(v.id)">Löschen</button>
        </div>
        <div class="vorgang-body">
          <p v-if="v.gegenstand"><em>Gegenstand:</em> {{ v.gegenstand }}</p>
          <p v-if="v.verlangen"><em>Verlangen:</em> {{ v.verlangen }}</p>
          <p>
            <em>Eingang:</em> {{ v.eingang_am || '—' }} ·
            <em>Frist:</em> {{ v.frist_am || '—' }}
            <span v-if="v.beantwortet_am"> · <em>beantwortet:</em> {{ v.beantwortet_am }}</span>
          </p>

          <p class="unterlagen-titel"><em>Bereitgestellte Unterlagen
            ({{ v.unterlagen.length }}):</em></p>
          <ul v-if="v.unterlagen.length" class="unterlagen">
            <li v-for="(u, i) in v.unterlagen" :key="i">
              {{ u.titel }}<span v-if="u.ref"> — {{ u.ref }}</span>
              <span v-if="u.uebergeben_am"> (übergeben {{ u.uebergeben_am }})</span>
            </li>
          </ul>
          <p v-else class="hint">
            Noch nichts erfasst. Was die Behörde bekommen hat, ist später die
            einzige Antwort auf „was haben Sie vorgelegt?“.
          </p>

          <div class="actions">
            <input v-model="unterlageTitel[v.id]" class="u-in"
                   placeholder="Unterlage (Bezeichnung)" />
            <input v-model="unterlageRef[v.id]" class="u-in"
                   placeholder="Fundstelle/Referenz (optional)" />
            <button class="btn-secondary" @click="unterlage(v.id)">Unterlage erfassen</button>
            <select :value="v.status" @change="changeStatus(v, $event)">
              <option v-for="s in store.status" :key="s" :value="s">{{ statusLabel(s) }}</option>
            </select>
          </div>

          <details v-if="v.audit_trail && v.audit_trail.length" class="audit">
            <summary>Verlauf ({{ v.audit_trail.length }})</summary>
            <ul>
              <li v-for="(ev, i) in v.audit_trail" :key="i">
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
import {
  useCraMarktueberwachungStore, type Marktaufsichtsvorgang,
} from '../../stores/craMarktueberwachung'

const props = defineProps<{ projekt: string }>()
const store = useCraMarktueberwachungStore()

const empty = () => ({
  vorgangsart: 'auskunftsverlangen', behoerde_name: '', behoerde_land: '',
  aktenzeichen: '', eingang_am: '', frist_am: '', gegenstand: '', verlangen: '',
  betroffene_versionen: '',
})
const form = ref<any>(empty())
const unterlageTitel = ref<Record<number, string>>({})
const unterlageRef = ref<Record<number, string>>({})

function artLabel(a: string) {
  return ({
    auskunftsverlangen: 'Auskunftsverlangen',
    pruefung: 'Prüfung',
    anordnung: 'Anordnung',
    korrekturverlangen: 'Korrekturverlangen',
    marktbeschraenkung: 'Marktbeschränkung',
    sonstiges: 'Sonstiges',
  } as Record<string, string>)[a] || a
}
function statusLabel(s: string) {
  return ({
    offen: 'Offen', in_bearbeitung: 'In Bearbeitung', beantwortet: 'Beantwortet',
    abgeschlossen: 'Abgeschlossen', eingestellt: 'Eingestellt',
  } as Record<string, string>)[s] || s
}

/** Kurztext der Ampel. „verstrichen“ wird nur bei laufendem Vorgang als
 *  Versäumnis benannt — bei einem beantworteten Vorgang ist das Datum Historie. */
function fristText(v: Marktaufsichtsvorgang) {
  if (!v.frist.datum) return 'keine Frist'
  if (v.frist_versaeumt) return `versäumt (${-(v.frist.tage_verbleibend || 0)} Tage)`
  if (v.frist.verstrichen) return 'Frist abgelaufen'
  return `${v.frist.tage_verbleibend} Tage`
}
function fristTitel(v: Marktaufsichtsvorgang) {
  return v.frist.datum ? `Frist ${v.frist.datum}` : 'Keine Frist erfasst'
}

async function create() {
  const ok = await store.createVorgang(props.projekt, { ...form.value })
  if (ok) form.value = empty()
}
async function changeStatus(v: Marktaufsichtsvorgang, ev: Event) {
  const neu = (ev.target as HTMLSelectElement).value
  await store.setStatus(props.projekt, v.id, neu)
}
async function unterlage(id: number) {
  const ok = await store.addUnterlage(props.projekt, id, unterlageTitel.value[id] || '',
                                      unterlageRef.value[id] || '')
  if (ok) { unterlageTitel.value[id] = ''; unterlageRef.value[id] = '' }
}
async function remove(id: number) {
  await store.deleteVorgang(props.projekt, id)
}

async function load() { await store.fetchVorgaenge(props.projekt) }
onMounted(async () => { await store.fetchConstants(); await load() })
watch(() => props.projekt, load)
</script>

<style scoped>
.marktaufsicht-panel { margin-top: 24px; border-top: 1px solid #cfd8e3; padding-top: 16px; }
.panel-header h3 { color: #1565c0; margin-bottom: 4px; }
.panel-header .sub { color: #607d8b; font-size: 13px; }
.kpi-zeile { display: flex; flex-wrap: wrap; gap: 12px; margin: 10px 0; font-size: 13px; }
.kpi { background: #eceff1; color: #37474f; padding: 3px 10px; border-radius: 10px; }
.kpi-rot { background: #ffebee; color: #c62828; }
.hinweis-rot { color: #c62828; font-size: 13px; margin: 4px 0 8px; }
.form-card { background: #f5f8fc; border: 1px solid #cfd8e3; border-radius: 8px; padding: 16px; margin: 12px 0; }
.form-card h4 { color: #1565c0; margin: 0 0 10px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.form-row { display: flex; flex-direction: column; margin-bottom: 8px; }
.form-row.span2 { grid-column: 1 / 3; }
.form-row label { font-size: 12px; color: #455a64; margin-bottom: 2px; }
.vorgang { border: 1px solid #e0e6ee; border-radius: 6px; padding: 10px; margin-bottom: 10px; background: #fff; }
.vorgang-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.badge { background: #90caf9; color: #0d47a1; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
.behoerde { color: #607d8b; font-size: 12px; }
.ampel { padding: 2px 8px; border-radius: 10px; font-size: 11px; background: #eceff1; color: #455a64; }
.ampel-gruen { background: #e8f5e9; color: #2e7d32; }
.ampel-gelb { background: #fff8e1; color: #ef6c00; }
.ampel-rot { background: #ffebee; color: #c62828; }
.ampel-verstrichen { background: #ffebee; color: #b71c1c; font-weight: 600; }
.status { margin-left: auto; padding: 2px 8px; border-radius: 10px; font-size: 11px; background: #eceff1; color: #455a64; }
.status.abgeschlossen, .status.beantwortet { background: #e8f5e9; color: #2e7d32; }
.vorgang-body { font-size: 13px; margin-top: 6px; }
.vorgang-body p { margin: 3px 0; }
.unterlagen-titel { margin-top: 6px; }
.unterlagen { margin: 2px 0 0 16px; }
.actions { display: flex; gap: 8px; align-items: center; margin: 8px 0; flex-wrap: wrap; }
.u-in { flex: 1; min-width: 140px; }
.audit { font-size: 12px; margin-top: 6px; }
.audit ul { margin: 4px 0 0 16px; }
.hint { color: #607d8b; font-size: 13px; }
.btn-link { background: none; border: none; cursor: pointer; color: #1565c0; }
.btn-link.danger { color: #c62828; }
</style>
