<template>
  <!-- #1564: Risiko für Nichterfüllung ausweisen — Bewertung in der verknüpften Risikobewertung -->
  <section class="req-risks">
    <div class="head" @click="open = !open">
      <h4>{{ $t('geteilt.requirementRiskLinks.risikenZurNichterfullung') }}
        <span v-if="data.risks.length" class="count">{{ data.risks.length }}</span>
      </h4>
      <span class="toggle">{{ open ? '▾' : '▸' }}</span>
    </div>

    <div v-if="open" class="body">
      <p v-if="loading" class="muted">{{ $t('common.loading') }}</p>

      <!-- Keine Risikobewertung verknüpft -->
      <template v-else-if="!data.linked_risk_projekt">
        <p class="muted">
          {{ $t('geteilt.requirementRiskLinks.furDiesesProjektIstNochKeineRisikobe') }}
        </p>
        <div class="row">
          <select v-model="rbSel" :disabled="!candidates.length">
            <option value="">{{ candidates.length ? $t('geteilt.requirementRiskLinks.vorhandeneRisikobewertungWahlen') : $t('geteilt.requirementRiskLinks.keinePassendeRisikobewertungVorhande') }}</option>
            <option v-for="c in candidates" :key="c.name" :value="c.name">
              {{ c.name }} · {{ c.framework }}{{ c.firma_match ? '' : ` (${c.unternehmen || 'ohne Firma'})` }}
            </option>
          </select>
          <button class="btn-secondary" :disabled="busy || !rbSel" @click="linkRb">{{ $t('common.verknupfen') }}</button>
        </div>
        <div class="row">
          <button class="btn-primary" :disabled="busy" @click="createRb">
            {{ $t('geteilt.requirementRiskLinks.neueRisikobewertungAnlegenVerknupfen') }}<span v-if="frameworkHint"> ({{ frameworkHint }})</span>
          </button>
        </div>
      </template>

      <!-- Verknüpft -->
      <template v-else>
        <p class="muted small">
          {{ $t('geteilt.requirementRiskLinks.risikobewertung') }} <strong>{{ data.linked_risk_projekt }}</strong>
          <router-link :to="{ path: '/risikobewertung', query: { projekt: data.linked_risk_projekt } }">{{ $t('geteilt.requirementRiskLinks.offnen') }}</router-link>
        </p>
        <p v-if="erfuellt" class="hint-ok">{{ $t('geteilt.requirementRiskLinks.vollErfulltScoreEinNichterfullungsRi') }}</p>

        <ul v-if="data.risks.length" class="risks">
          <li v-for="r in data.risks" :key="r.id">
            <span class="nr">#{{ r.nr }}</span> {{ r.risk_name }}
            <span v-if="r.bewertet" class="lvl" :class="levelClass(r.risiko_label)">{{ r.risiko_label || r.risikowert }}</span>
            <span v-else class="lvl open">unbewertet</span>
            <span v-if="r.behandlung === 'akzeptiert'" class="lvl ok" :title="r.akzeptanz_grund">akzeptiert ({{ r.akzeptanz_kategorie }})</span>
            <span v-else-if="r.is_resolved" class="lvl ok">behandelt</span>
            <button v-if="r.behandlung !== 'akzeptiert'" class="btn-link" :disabled="busy"
                    :title="$t('geteilt.requirementRiskLinks.abweichungAlsRestrisikoAkzeptierenCR')"
                    @click="akzeptierenId = akzeptierenId === r.id ? null : r.id">akzeptieren</button>
            <!-- #1941: Der Rückweg fehlte. Sobald akzeptiert war, verschwand
                 „akzeptieren", und übrig blieb „lösen" — das aber die Akzeptanz
                 NICHT wegnimmt, weil das Gate `felder._source_id` liest und
                 nicht die Verknüpfungstabelle. -->
            <button v-if="r.behandlung === 'akzeptiert'" class="btn-link" :disabled="busy"
                    :title="$t('geteilt.requirementRiskLinks.akzeptanzZurucknehmenBegrundungspfli')"
                    @click="ruecknahmeId = ruecknahmeId === r.id ? null : r.id">{{ $t('geteilt.requirementRiskLinks.zurucknehmen') }}</button>
            <button class="btn-link" :disabled="busy"
                    :title="r.behandlung === 'akzeptiert'
                      ? $t('geteilt.requirementRiskLinks.lostNurDieVerknupfungDieAkzeptanzBle')
                      : $t('geteilt.requirementRiskLinks.nurDieVerknupfungLosenDasRisikoBleib')"
                    @click="unlink(r.id, r.behandlung === 'akzeptiert')">{{ $t('geteilt.requirementRiskLinks.losen') }}</button>
            <!-- #1941: Rücknahme-Formular -->
            <div v-if="ruecknahmeId === r.id" class="akz">
              <p class="akz-hinweis">
                {{ $t('geteilt.requirementRiskLinks.dieRucknahmeSetztKategorieBegrundung') }} <strong>{{ $t('geteilt.requirementRiskLinks.undRechtsgrundlage') }}</strong> {{ $t('geteilt.requirementRiskLinks.zuruckDassEineAkzeptanzBestandBleibt') }}
              </p>
              <label>{{ $t('geteilt.requirementRiskLinks.grundDerRucknahmeMindZeichen') }}
                <textarea v-model="ruecknahme.grund" rows="2"
                          :placeholder="$t('geteilt.requirementRiskLinks.warumGiltDieBegrundungNichtMehr')"></textarea>
              </label>
              <div class="akz-aktionen">
                <button class="btn-secondary" :disabled="busy" @click="ruecknahmeId = null">{{ $t('common.cancel') }}</button>
                <button class="btn-primary" :disabled="busy || ruecknahme.grund.trim().length < 20"
                        @click="zurueckziehen(r.id)">{{ $t('geteilt.requirementRiskLinks.akzeptanzZurucknehmen') }}</button>
              </div>
            </div>
            <!-- #1608/#1613: Akzeptanz-Formular -->
            <div v-if="akzeptierenId === r.id" class="akz">
              <label>{{ $t('geteilt.requirementRiskLinks.begrundungskategorie') }}
                <select v-model="akz.kategorie">
                  <option value="nicht_anwendbar">{{ $t('geteilt.requirementRiskLinks.nichtAnwendbarRisikobasiert') }}</option>
                  <option value="restrisiko">{{ $t('geteilt.requirementRiskLinks.restrisikoNachMassnahmen') }}</option>
                  <option value="kompensierend">{{ $t('geteilt.requirementRiskLinks.kompensierendeMassnahme') }}</option>
                </select></label>
              <label>{{ $t('common.begruendung') }}<textarea v-model="akz.grund" rows="2" :placeholder="$t('geteilt.requirementRiskLinks.warumIstDieAbweichungVertretbar')" /></label>
              <label>{{ $t('geteilt.requirementRiskLinks.akzeptiertVon') }}<input v-model="akz.von" placeholder="Rolle/Person" /></label>
              <label>{{ $t('common.rechtsgrundlage') }}<input v-model="akz.rechtsgrundlage" :placeholder="$t('geteilt.requirementRiskLinks.zBAnnexIWhereApplicable')" /></label>
              <button class="btn-primary" :disabled="busy || !akz.grund.trim()" @click="akzeptieren(r.id)">{{ $t('geteilt.requirementRiskLinks.akzeptieren') }}</button>
            </div>
          </li>
        </ul>
        <p v-else class="muted small">{{ $t('geteilt.requirementRiskLinks.nochKeinRisikoVerknupft') }}</p>

        <details class="create" :open="!erfuellt && !data.risks.length">
          <summary>{{ $t('geteilt.requirementRiskLinks.risikoFurNichterfullungAusweisen') }}</summary>
          <label>{{ $t('common.titel') }}<input v-model="form.risk_name" /></label>
          <label>{{ $t('common.description') }}<textarea v-model="form.beschreibung" rows="5" /></label>
          <button class="btn-primary" :disabled="busy || !form.risk_name.trim()" @click="createRisk">
            {{ $t('geteilt.requirementRiskLinks.risikoAnlegenVerknupfen') }}
          </button>
          <p class="muted small">{{ $t('geteilt.requirementRiskLinks.dasRisikoWirdUnbewertetAngelegtEintr') }}</p>
        </details>

        <div v-if="data.verfuegbar.length" class="row">
          <select v-model="riskSel">
            <option value="">{{ $t('geteilt.requirementRiskLinks.vorhandenesRisikoVerknupfen') }}</option>
            <option v-for="r in data.verfuegbar" :key="r.id" :value="r.id">#{{ r.nr }} {{ r.risk_name }}</option>
          </select>
          <button class="btn-secondary" :disabled="busy || !riskSel" @click="linkRisk">{{ $t('common.verknupfen') }}</button>
        </div>
      </template>
      <p v-if="msg" class="msg" :class="{ err: msgErr }">{{ msg }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import apiClient from '../../api/client'
// `t` ist in dieser Maske schon belegt (lokale Variable/Parameter) —
// deshalb unter anderem Namen. Ein Import überdeckt eine lokale
// Bindung nicht, er kollidiert mit ihr: Der Aufruf trifft die
// Variable, und die ist keine Funktion. Gefunden hat das der
// Typprüfer (#1858), nicht der Build.
import { t as uebersetze } from '../../i18n'

const props = defineProps<{
  /** /cra | /nis2 | /dsgvo | /aiact */
  apiBase: string
  projektName: string
  /** requirement | owasp | owasp_llm */
  objectKind: 'requirement' | 'owasp' | 'owasp_llm'
  objectId: string
  titel?: string
  score?: number | null
  kommentar?: string
}>()
const emit = defineEmits<{ (e: 'changed'): void }>()

const open = ref(true)
const loading = ref(true)
const busy = ref(false)
const msg = ref('')
const msgErr = ref(false)
const data = ref<{ linked_risk_projekt: string | null; risks: any[]; verfuegbar: any[] }>({ linked_risk_projekt: null, risks: [], verfuegbar: [] })
const candidates = ref<any[]>([])
const frameworkHint = ref('')
const rbSel = ref('')
const riskSel = ref<string | number>('')
const form = ref({ risk_name: '', beschreibung: '' })
// #1608/#1613: Risiko-Akzeptanz
const akzeptierenId = ref<number | null>(null)
const akz = ref({ kategorie: 'restrisiko', grund: '', von: '', rechtsgrundlage: '' })

const erfuellt = computed(() => Number(props.score ?? 0) >= 5)
const base = computed(() => `${props.apiBase}/projekte/${encodeURIComponent(props.projektName)}/req-risks`)
const objUrl = computed(() => `${base.value}/${props.objectKind}/${encodeURIComponent(props.objectId)}`)

const art = computed(() => ({ requirement: uebersetze('common.anforderung'), owasp: uebersetze('geteilt.requirementRiskLinks.oWASPControl'), owasp_llm: uebersetze('geteilt.requirementRiskLinks.oWASPLLMRisiko') })[props.objectKind])
function resetForm() {
  const t = (props.titel || '').trim()
  form.value.risk_name = `Nichterfüllung ${props.objectId}${t ? ': ' + t : ''}`.slice(0, 250)
  const lines = [`${art.value} ${props.objectId}${t ? ' (' + t + ')' : ''} ist nicht vollständig erfüllt.`]
  if (props.score !== null && props.score !== undefined) lines.push(`Aktueller Erfüllungsgrad: ${props.score}/5.`)
  if ((props.kommentar || '').trim()) lines.push('', 'Bewertungskommentar:', (props.kommentar || '').trim().slice(0, 3000))
  lines.push('', 'Risiko aus der Nichterfüllung — Eintrittswahrscheinlichkeit und Auswirkung sind in der Risikobewertung zu bewerten.')
  form.value.beschreibung = lines.join('\n')
}

function say(t: string, err = false) { msg.value = t; msgErr.value = err }
const errText = (e: any, d: string) => e?.response?.data?.error || d

async function load() {
  if (!props.projektName || !props.objectId) return
  loading.value = true
  try {
    const ov = (await apiClient.get(base.value)).data || {}
    frameworkHint.value = ov.framework_hint || ''
    candidates.value = ov.candidates || []
    data.value = (await apiClient.get(objUrl.value)).data
  } catch (e: any) {
    say(errText(e, 'Laden fehlgeschlagen.'), true)
  } finally { loading.value = false }
}

async function run(fn: () => Promise<any>, ok: string, fail: string) {
  busy.value = true
  try {
    const r = await fn()
    if (r?.data?.risks) data.value = r.data
    else await load()
    say(ok)
    emit('changed')
  } catch (e: any) { say(errText(e, fail), true) } finally { busy.value = false }
}

const linkRb = () => run(() => apiClient.put(`${base.value}/link`, { rb_projekt: rbSel.value }),
  'Risikobewertung verknüpft.', 'Verknüpfen fehlgeschlagen.')
const createRb = () => run(() => apiClient.post(`${base.value}/create-rb`, {}),
  'Risikobewertung angelegt und verknüpft.', 'Anlegen fehlgeschlagen.')
const createRisk = () => run(() => apiClient.post(objUrl.value, {
  titel: props.titel || '', risk_name: form.value.risk_name, beschreibung: form.value.beschreibung,
  score: props.score, kommentar: props.kommentar || '',
}), 'Risiko angelegt — bitte in der Risikobewertung bewerten.', 'Risiko konnte nicht angelegt werden.')
const linkRisk = () => run(() => apiClient.post(objUrl.value, { risk_id: riskSel.value }),
  'Risiko verknüpft.', 'Verknüpfen fehlgeschlagen.').then(() => { riskSel.value = '' })
const unlink = (rid: number, akzeptiert = false) => {
  // #1941: Das Lösen nimmt die Akzeptanz nicht weg — vorher sagen, nicht
  // hinterher erklären.
  if (akzeptiert && !confirm(
      uebersetze('geteilt.requirementRiskLinks.diesesRisikoIstAlsAbweichungAkzeptie')
      + uebersetze('geteilt.requirementRiskLinks.dasLosenEntferntNurDieVerknupfungDie')
      + uebersetze('geteilt.requirementRiskLinks.undWirktWeiterImKonformitatsGateSieI')
      + uebersetze('geteilt.requirementRiskLinks.anforderungNurNichtMehrZuSehenNN')
      + uebersetze('geteilt.requirementRiskLinks.zumZurucknehmenStattdessenZurucknehm')
      + uebersetze('geteilt.requirementRiskLinks.trotzdemNurDieVerknupfungLosen'))) return Promise.resolve()
  return run(() => apiClient.delete(`${objUrl.value}/${rid}`),
    'Verknüpfung gelöst (Risiko bleibt in der Risikobewertung).', 'Lösen fehlgeschlagen.')
}

// #1941: Rücknahme einer Akzeptanz. Die Person stempelt der Server.
const ruecknahmeId = ref<number | null>(null)
const ruecknahme = ref({ grund: '' })
const zurueckziehen = (rid: number) => run(() => apiClient.patch(
  `/risikobewertung/projekte/${encodeURIComponent(data.value.linked_risk_projekt || '')}/risiken/${rid}/behandlung`,
  { behandlung: 'offen', ruecknahme_grund: ruecknahme.value.grund }),
  'Akzeptanz zurückgenommen — die Anforderung gilt wieder als offen.',
  'Rücknahme fehlgeschlagen.')
  .then(() => { ruecknahmeId.value = null; ruecknahme.value = { grund: '' } })

// #1608/#1613: Abweichung als Restrisiko akzeptieren (CRA-konform, begründet)
const akzeptieren = (rid: number) => run(() => apiClient.patch(
  `/risikobewertung/projekte/${encodeURIComponent(data.value.linked_risk_projekt || '')}/risiken/${rid}/behandlung`,
  { behandlung: 'akzeptiert', kategorie: akz.value.kategorie, grund: akz.value.grund,
    von: akz.value.von, rechtsgrundlage: akz.value.rechtsgrundlage }),
  'Abweichung als Risiko akzeptiert.', 'Akzeptanz fehlgeschlagen.')
  .then(() => { akzeptierenId.value = null; akz.value = { kategorie: 'restrisiko', grund: '', von: '', rechtsgrundlage: '' } })

const levelClass = (l: string) => {
  const s = (l || '').toLowerCase()
  if (s.includes('krit') || s.includes('sehr hoch')) return 'crit'
  if (s.includes('hoch')) return 'high'
  if (s.includes('mittel')) return 'mid'
  return 'low'
}

watch(() => [props.projektName, props.objectKind, props.objectId], () => { msg.value = ''; resetForm(); load() }, { immediate: true })
</script>

<style scoped>
.req-risks { border: 1px solid #ffcc80; background: #fffaf2; border-radius: 6px; margin: 10px 0; }
.head { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; cursor: pointer; }
.head h4 { margin: 0; font-size: 14px; color: #e65100; }
.count { background: #e65100; color: white; border-radius: 9px; padding: 0 7px; font-size: 11px; margin-left: 4px; }
.toggle { color: #999; }
.body { padding: 0 12px 12px; }
.row { display: flex; gap: 8px; align-items: center; margin: 6px 0; flex-wrap: wrap; }
.row select { flex: 1; min-width: 200px; padding: 6px; border: 1px solid var(--color-border); border-radius: 4px; }
.risks { list-style: none; padding: 0; margin: 6px 0; font-size: 13px; }
.risks li { display: flex; align-items: center; gap: 6px; padding: 4px 0; border-bottom: 1px dashed #f0e0c8; flex-wrap: wrap; }
/* #1669: Akzeptanz-Formular als eigene Karte (volle Zeilenbreite, Block-Layout) */
.akz { flex-basis: 100%; width: 100%; display: flex; flex-direction: column; gap: 8px;
  background: #f5f8fc; border: 1px solid #cfd8e3; border-radius: 8px; padding: 12px; margin: 6px 0 2px; }
.akz label { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: #455a64; font-weight: 600; }
.akz select, .akz input, .akz textarea { width: 100%; box-sizing: border-box; padding: 6px 8px;
  border: 1px solid #cfd8e3; border-radius: 6px; font: inherit; font-weight: 400; }
.akz textarea { resize: vertical; min-height: 44px; }
.akz .btn-primary { align-self: flex-start; }
/* #1941: Rücknahme-Formular — eigene Zeile für die beiden Knöpfe, damit
   „Abbrechen" nicht unter „Zurücknehmen" rutscht. `align-self` der
   Regel darüber greift hier nicht, weil die Knöpfe in einem eigenen
   Flex-Container stehen. */
.akz-aktionen { display: flex; gap: 8px; align-items: center; }
.akz-aktionen .btn-primary { align-self: auto; }
.akz-hinweis { margin: 0; font-size: 12px; color: #455a64; line-height: 1.45; }
.nr { color: #888; font-family: Consolas, monospace; }
.lvl { border-radius: 10px; padding: 0 8px; font-size: 11px; font-weight: 600; }
.lvl.crit { background: #ffebee; color: #b71c1c; } .lvl.high { background: #fff3e0; color: #e65100; }
.lvl.mid { background: #fffde7; color: #f57f17; } .lvl.low { background: #e8f5e9; color: #2e7d32; }
.lvl.open { background: #eceff1; color: #546e7a; } .lvl.ok { background: #e8f5e9; color: #2e7d32; }
.create { margin: 8px 0; }
.create summary { cursor: pointer; font-weight: 600; font-size: 13px; color: #e65100; }
.create label { display: flex; flex-direction: column; gap: 3px; font-size: 12px; font-weight: 600; margin: 6px 0; }
.create input, .create textarea { padding: 6px 8px; border: 1px solid var(--color-border); border-radius: 4px; font: inherit; font-weight: normal; }
.muted { color: #666; font-size: 13px; margin: 4px 0; } .small { font-size: 12px; }
.hint-ok { color: #2e7d32; font-size: 13px; margin: 4px 0; }
.msg { font-size: 13px; color: #1b5e20; margin: 6px 0 0; } .msg.err { color: #c62828; }
.btn-primary, .btn-secondary { padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-primary { background: var(--color-primary); color: white; } .btn-secondary { background: #e0e0e0; color: #333; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; font-size: 12px; margin-left: auto; }
button:disabled { opacity: .6; cursor: not-allowed; }
</style>
