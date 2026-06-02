<!--
  CRA-Tab „Risikoanalyse" (#882/#883) — verknüpft das CRA-Projekt transparent mit
  einem Projekt aus dem Modul Risikobewertung. Zeigt Verknüpfung, Risiko-Summary,
  Abdeckungs-Kennzahl und einen Deep-Link ins Risikobewertungs-Modul.

  Fachlich (AI1-01, Annex I): die Risikoabschätzung wird im Risikobewertungs-Modul
  geführt und hier nur referenziert/nachgewiesen — es werden KEINE Anforderungen
  aus- oder eingeblendet.
-->
<template>
  <div class="risikoanalyse-panel" v-if="projektName">
    <div class="info-box">
      <strong>ℹ️ CRA-Risikoabschätzung (AI1-01, Annex I)</strong>
      <p>
        Der Cyber Resilience Act verlangt eine Cybersicherheits-Risikoabschätzung des
        Produkts (Anforderung <code>AI1-01</code>). Sie wird im Modul
        <strong>Risikobewertung</strong> geführt (STRIDE/TARA/OCTAVE) und hier mit dem
        CRA-Projekt verknüpft — als Nachweis. Die Verknüpfung filtert keine
        Anforderungen; die Anforderungsliste bleibt vollständig.
      </p>
    </div>

    <section class="link-section">
      <h3>🔍 Verknüpftes Risikobewertungs-Projekt</h3>

      <div v-if="linked" class="linked-card">
        <div class="linked-head">
          <span class="linked-name">🔗 {{ linked }}</span>
          <a class="deep-link" :href="`#/risikobewertung?projekt=${encodeURIComponent(linked)}`">
            Im Risikobewertung-Modul öffnen →
          </a>
        </div>
        <div v-if="summary" class="summary-grid">
          <div class="stat"><span class="num">{{ summary.total }}</span> Risiken</div>
          <div class="stat offen"><span class="num">{{ summary.offen }}</span> offen</div>
          <div class="stat ok"><span class="num">{{ summary.geloest }}</span> gelöst</div>
          <div class="stat"><span class="num">{{ coverage.abgedeckt }}/{{ coverage.gesamt }}</span> Anforderungen mit Risiko</div>
        </div>
        <button class="btn-secondary" @click="unlink" :disabled="busy">Verknüpfung lösen</button>
      </div>

      <div v-else class="link-form">
        <p v-if="candidates.length === 0" class="hint">
          Keine Risikobewertungs-Projekte für den Kunden <code>{{ kunde || '—' }}</code> gefunden.
          Lege im Modul Risikobewertung ein Projekt für diesen Kunden an.
        </p>
        <template v-else>
          <label>Risikobewertungs-Projekt wählen
            <select v-model="selected">
              <option value="">— wählen —</option>
              <option v-for="c in candidates" :key="c.name" :value="c.name">
                {{ c.name }}<span v-if="c.framework"> ({{ c.framework }})</span>
              </option>
            </select>
          </label>
          <button class="btn-primary" @click="link" :disabled="busy || !selected">Verknüpfen</button>
        </template>
      </div>

      <p v-if="msg" :class="['msg', msgKind]">{{ msg }}</p>
    </section>

    <!-- #920: Nachweis für die risiko-relevanten CRA-Anforderungen -->
    <section v-if="linked && reqStatus.length" class="nachweis-section">
      <h3>📋 Nachweis für risiko-relevante Anforderungen</h3>
      <p class="hint">
        Vorschlag aus der Vollständigkeit der verknüpften Risikobewertung — Übernahme
        nur auf Bestätigung. Der vorgeschlagene Status überschreibt nichts automatisch.
      </p>
      <table class="nachweis-table">
        <thead>
          <tr><th>Anforderung</th><th>Aktuell</th><th>Vorschlag</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="r in reqStatus" :key="r.id">
            <td><code>{{ r.id }}</code> <span class="req-titel">{{ r.titel }}</span></td>
            <td><span :class="['status-pill', r.current_status]">{{ r.current_status }}</span></td>
            <td><span :class="['status-pill', r.suggested_status]">{{ r.suggested_status }}</span></td>
            <td>
              <button v-if="r.differs" class="btn-mini" :disabled="applying" @click="applyOne(r)">übernehmen</button>
              <span v-else class="muted">✓</span>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="nachweis-foot">
        <button class="btn-primary" :disabled="applying || !anyDiffers" @click="applyAll">
          {{ applying ? 'Übernehme…' : 'Alle Vorschläge übernehmen' }}
        </button>
        <span v-if="nachweisMsg" :class="['msg', nachweisKind]">{{ nachweisMsg }}</span>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'

const props = defineProps<{ projektName: string }>()

const kunde = ref('')
const candidates = ref<{ name: string; framework?: string }[]>([])
const linked = ref<string | null>(null)
const summary = ref<{ total: number; offen: number; geloest: number } | null>(null)
const coverage = reactive({ abgedeckt: 0, gesamt: 0 })
const selected = ref('')
const busy = ref(false)
const msg = ref('')
const msgKind = ref<'ok' | 'err'>('ok')

// #920: Nachweis-Vorschläge für die 5 risiko-relevanten Anforderungen
interface ReqRow {
  id: string; titel: string
  current_status: string; current_score: number
  suggested_status: string; suggested_score: number
  differs: boolean
}
const reqStatus = ref<ReqRow[]>([])
const applying = ref(false)
const nachweisMsg = ref('')
const nachweisKind = ref<'ok' | 'err'>('ok')
const anyDiffers = computed(() => reqStatus.value.some(r => r.differs))

function setMsg(t: string, k: 'ok' | 'err' = 'ok') { msg.value = t; msgKind.value = k }

async function loadReqStatus() {
  reqStatus.value = []
  nachweisMsg.value = ''
  if (!linked.value || !props.projektName) return
  try {
    const { default: api } = await import('../../api/client')
    const r = await api.get(`/cra/projekte/${encodeURIComponent(props.projektName)}/risk-assessment-status`)
    reqStatus.value = r.data?.requirements || []
  } catch { reqStatus.value = [] }
}

async function applyOne(r: ReqRow) {
  applying.value = true; nachweisMsg.value = ''
  try {
    const { default: api } = await import('../../api/client')
    await api.post(`/cra/projekte/${encodeURIComponent(props.projektName)}/bewertungen`,
      { anforderung_id: r.id, bewertung: r.suggested_score })
    // Reload ZUERST (loadReqStatus leert nachweisMsg), Erfolg DANACH anzeigen.
    await loadReqStatus()
    nachweisKind.value = 'ok'; nachweisMsg.value = `${r.id} auf „${r.suggested_status}“ gesetzt.`
  } catch (e: any) {
    nachweisKind.value = 'err'; nachweisMsg.value = e?.response?.data?.error || 'Übernehmen fehlgeschlagen.'
  } finally { applying.value = false }
}

async function applyAll() {
  applying.value = true; nachweisMsg.value = ''
  try {
    const { default: api } = await import('../../api/client')
    const todo = reqStatus.value.filter(r => r.differs)
    for (const r of todo) {
      await api.post(`/cra/projekte/${encodeURIComponent(props.projektName)}/bewertungen`,
        { anforderung_id: r.id, bewertung: r.suggested_score })
    }
    const n = todo.length
    // Reload ZUERST (loadReqStatus leert nachweisMsg), Erfolg DANACH anzeigen.
    await loadReqStatus()
    nachweisKind.value = 'ok'
    nachweisMsg.value = n ? `${n} Anforderung(en) aktualisiert.` : 'Keine offenen Vorschläge.'
  } catch (e: any) {
    nachweisKind.value = 'err'; nachweisMsg.value = e?.response?.data?.error || 'Übernehmen fehlgeschlagen.'
  } finally { applying.value = false }
}

async function load() {
  if (!props.projektName) return
  msg.value = ''
  const { default: api } = await import('../../api/client')
  const base = `/cra/projekte/${encodeURIComponent(props.projektName)}`
  try {
    const r = await api.get(`${base}/risk-link`)
    linked.value = r.data?.linked_risk_projekt || null
    summary.value = r.data?.summary || null
  } catch { linked.value = null; summary.value = null }
  if (linked.value) {
    try {
      const cov = await api.get(`${base}/risk-coverage`)
      coverage.abgedeckt = cov.data?.abgedeckt || 0
      coverage.gesamt = cov.data?.gesamt || 0
    } catch { /* ignore */ }
    await loadReqStatus()
  } else {
    try {
      const c = await api.get(`${base}/risk-link/candidates`)
      kunde.value = c.data?.kunde || ''
      candidates.value = c.data?.candidates || []
    } catch { candidates.value = [] }
  }
}

async function link() {
  if (!selected.value) return
  busy.value = true; msg.value = ''
  try {
    const { default: api } = await import('../../api/client')
    await api.put(`/cra/projekte/${encodeURIComponent(props.projektName)}/risk-link`,
      { risk_projekt: selected.value })
    setMsg('Verknüpfung gespeichert.')
    await load()
  } catch (e: any) {
    setMsg(e?.response?.data?.error || 'Verknüpfen fehlgeschlagen.', 'err')
  } finally { busy.value = false }
}

async function unlink() {
  busy.value = true; msg.value = ''
  try {
    const { default: api } = await import('../../api/client')
    await api.delete(`/cra/projekte/${encodeURIComponent(props.projektName)}/risk-link`)
    selected.value = ''
    setMsg('Verknüpfung gelöst.')
    await load()
  } catch (e: any) {
    setMsg(e?.response?.data?.error || 'Lösen fehlgeschlagen.', 'err')
  } finally { busy.value = false }
}

watch(() => props.projektName, load)
onMounted(load)
</script>

<style scoped>
.risikoanalyse-panel { padding: 4px 0; }
.info-box { background: #e3f2fd; border-left: 4px solid #1565c0; border-radius: 6px; padding: 10px 14px; margin-bottom: 16px; }
.info-box p { margin: 6px 0 0; font-size: 0.88rem; color: #37474f; }
.link-section h3 { color: #1565c0; margin-bottom: 10px; }
.linked-card { border: 1px solid #c8e6c9; background: #f1f8e9; border-radius: 8px; padding: 14px 16px; }
.linked-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.linked-name { font-weight: 600; }
.deep-link { color: #1565c0; text-decoration: none; font-size: 0.9rem; }
.deep-link:hover { text-decoration: underline; }
.summary-grid { display: flex; gap: 18px; margin: 12px 0; flex-wrap: wrap; }
.stat { font-size: 0.85rem; color: #555; }
.stat .num { font-size: 1.25rem; font-weight: 700; color: #1565c0; display: block; }
.stat.offen .num { color: #e65100; }
.stat.ok .num { color: #2e7d32; }
.link-form { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; }
.link-form label { display: flex; flex-direction: column; font-size: 0.85rem; gap: 4px; }
.link-form select { padding: 6px 8px; border: 1px solid #d0d7de; border-radius: 6px; min-width: 260px; }
.hint { color: #57606a; font-size: 0.88rem; }
.msg { margin-top: 10px; font-size: 0.85rem; }
.msg.ok { color: #2e7d32; }
.msg.err { color: #c62828; }

/* #920: Nachweis-Abschnitt */
.nachweis-section { margin-top: 22px; border-top: 1px solid #e0e0e0; padding-top: 14px; }
.nachweis-section h3 { color: #1565c0; margin-bottom: 6px; }
.nachweis-table { width: 100%; border-collapse: collapse; font-size: 0.86rem; margin-top: 8px; }
.nachweis-table th, .nachweis-table td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #eee; }
.nachweis-table th { color: #607d8b; font-size: 0.78rem; text-transform: uppercase; }
.req-titel { color: #455a64; }
.status-pill {
  display: inline-block; padding: 1px 9px; border-radius: 10px;
  font-size: 0.78rem; font-weight: 600;
}
.status-pill.erfüllt { background: #e8f5e9; color: #2e7d32; }
.status-pill.teilerfüllt { background: #fff8e1; color: #e65100; }
.status-pill.offen { background: #ffebee; color: #c62828; }
.btn-mini {
  background: #1565c0; color: #fff; border: none; border-radius: 5px;
  padding: 3px 10px; font-size: 0.78rem; cursor: pointer;
}
.btn-mini:disabled { opacity: 0.5; cursor: not-allowed; }
.muted { color: #9e9e9e; }
.nachweis-foot { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
</style>
