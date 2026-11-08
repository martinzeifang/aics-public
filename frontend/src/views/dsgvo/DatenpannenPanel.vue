<template>
  <div class="datenpannen-panel">
    <div class="intro-banner">
      <strong>{{ $t('dsgvo.datenpannenPanel.datenpannenArt') }}</strong>
      <p class="hint">{{ $t('dsgvo.datenpannenPanel.meldungAnDieAufsichtsbehordeUnverzug') }}
        <strong>{{ $t('dsgvo.datenpannenPanel.stunden') }}</strong> {{ $t('dsgvo.datenpannenPanel.nachBekanntwerdenArtCountdownUberfal') }}</p>
    </div>

    <div v-if="!projektName" class="hint">{{ $t('common.projektWaehlen') }}</div>
    <template v-else>
      <button class="btn-primary" @click="openNew">{{ $t('dsgvo.datenpannenPanel.neueDatenpanne') }}</button>

      <p v-if="store.error" class="msg err">{{ store.error }}</p>
      <p v-if="store.loading" class="hint">{{ $t('common.ladt') }}</p>

      <div v-if="overdueCount > 0" class="alarm">
        {{ $t('dsgvo.datenpannenPanel.v0DatenpanneNMitUberschrittenerHFris', { v0: overdueCount }) }}
      </div>

      <table v-if="store.pannen.length" class="grid">
        <thead>
          <tr>
            <th>ID</th><th>{{ $t('common.titel') }}</th><th>{{ $t('dsgvo.datenpannenPanel.festgestellt') }}</th>
            <th>{{ $t('dsgvo.datenpannenPanel.hFrist') }}</th><th>{{ $t('common.status') }}</th><th>{{ $t('common.actions') }}</th>
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
                @click="exportForm(p, 'docx')">{{ $t('dsgvo.datenpannenPanel.meldeformular') }}</button>
              <button class="btn-secondary" :disabled="busy === p.id + ':pdf'"
                @click="exportForm(p, 'pdf')">{{ $t('common.pDF2') }}</button>
              <button class="btn-danger-mini" @click="del(p)">🗑️</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else-if="!store.loading" class="hint">{{ $t('dsgvo.datenpannenPanel.keineDatenpannenErfasst') }}</p>
    </template>

    <!-- Editor -->
    <div v-if="editing" class="modal-backdrop" @click.self="editing = null">
      <div class="modal">
        <h3>{{ editing.id ? $t('dsgvo.datenpannenPanel.datenpanneBearbeiten') : $t('dsgvo.datenpannenPanel.neueDatenpanne2') }}</h3>
        <label>{{ $t('dsgvo.datenpannenPanel.vorfallID') }} <input v-model="editing.panne_id" placeholder="DSGVO-P-2026-001" /></label>
        <label>{{ $t('common.titel') }} <input v-model="editing.titel" /></label>
        <label>{{ $t('dsgvo.datenpannenPanel.art') }}
          <select v-model="editing.art">
            <option value="vertraulichkeit">{{ $t('common.vertraulichkeit') }}</option>
            <option value="integritaet">{{ $t('dsgvo.datenpannenPanel.integritat') }}</option>
            <option value="verfuegbarkeit">{{ $t('dsgvo.datenpannenPanel.verfugbarkeit') }}</option>
          </select>
        </label>
        <label>{{ $t('dsgvo.datenpannenPanel.festgestelltAm') }} <input v-model="editing.festgestellt_am" type="date" /></label>
        <label>{{ $t('common.description') }} <textarea v-model="editing.beschreibung" rows="2"></textarea></label>
        <label>{{ $t('dsgvo.datenpannenPanel.datenkategorien') }} <input v-model="editing.datenkategorien" /></label>
        <label>{{ $t('dsgvo.datenpannenPanel.betroffeneAnzahl') }} <input v-model.number="editing.betroffene_anzahl" type="number" min="0" /></label>
        <label>{{ $t('dsgvo.datenpannenPanel.risikoeinschatzung') }}
          <select v-model="editing.risikoeinschaetzung">
            <option value="gering">gering</option>
            <option value="mittel">{{ $t('dsgvo.dSFADetailPanel.mittel') }}</option>
            <option value="hoch">{{ $t('aiact.aIActAssistentenTab.hoch') }}</option>
          </select>
        </label>
        <label>{{ $t('common.sofortmassnahmen') }} <textarea v-model="editing.sofortmassnahmen" rows="2"></textarea></label>
        <label>{{ $t('common.status') }}
          <select v-model="editing.status">
            <option value="offen">{{ $t('cra.pflichtDokuPanel.offen') }}</option>
            <option value="gemeldet">{{ $t('cra.pflichtDokuPanel.gemeldet') }}</option>
            <option value="abgeschlossen">abgeschlossen</option>
          </select>
        </label>
        <!-- #1891: Die Pflicht ist gerechnet, nicht angekreuzt. Art. 33
             Abs. 1 nimmt nur Fälle aus, in denen die Verletzung
             voraussichtlich nicht zu einem Risiko führt; Art. 34 Abs. 1
             verlangt die Benachrichtigung bei hohem Risiko — und die
             Einschätzung steht in derselben Maske. Der gerechnete Stand steht
             daneben; die Entscheidung bleibt beim Verantwortlichen, und eine
             Abweichung wird ausgewiesen statt überschrieben. -->
        <label class="cb">
          <input type="checkbox" v-model="aufsichtPflicht" />
          {{ $t('dsgvo.datenpannenPanel.meldungAnAufsichtErforderlichArt') }}
          <span v-if="gerechnet" class="gerechnet"
                :class="gerechnet.aufsicht.pflicht ? 'ja' : 'nein'"
                :title="gerechnet.aufsicht.grund">
            gerechnet: {{ gerechnet.aufsicht.pflicht ? 'ja' : 'nein' }}
          </span>
        </label>
        <label class="cb">
          <input type="checkbox" v-model="betroffenePflicht" />
          {{ $t('dsgvo.datenpannenPanel.meldungAnBetroffeneErforderlichArt') }}
          <span v-if="gerechnet" class="gerechnet"
                :class="gerechnet.betroffene.pflicht ? 'ja' : 'nein'"
                :title="gerechnet.betroffene.grund">
            gerechnet: {{ gerechnet.betroffene.pflicht ? 'ja' : 'nein' }}
          </span>
        </label>
        <p v-if="gerechnet && abweichung" class="meldehinweis">
          {{ $t('dsgvo.datenpannenPanel.dieEinschatzungV0SprichtFurEineMelde', { v0: gerechnet.stufe }) }}
          <button class="btn-link" @click="pflichtUebernehmen">
            {{ $t('dsgvo.datenpannenPanel.gerechnetenStandUbernehmen') }}
          </button>
        </p>
        <p v-if="gerechnet && gerechnet.angehoben.length" class="meldehinweis">
          {{ $t('dsgvo.datenpannenPanel.iV0DieEinschatzungWurdeDeshalbAufV1A', { v0: gerechnet.angehoben.join('; '), v1: gerechnet.stufe }) }}
        </p>
        <div class="modal-actions">
          <button class="btn-primary" @click="save">{{ $t('common.saveIcon') }}</button>
          <button class="btn-secondary" @click="editing = null">{{ $t('common.cancel') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useDsgvoDatenpannenStore, type Datenpanne } from '../../stores/dsgvoDatenpannen'
import { t } from '../../i18n'

const props = defineProps<{ projektName: string | null }>()
const store = useDsgvoDatenpannenStore()

const editing = ref<Partial<Datenpanne> | null>(null)
const aufsichtPflicht = ref(false)
// #1891: Der gerechnete Stand kommt **fertig vom Server** — die Regeln hier
// nachzubauen wäre die Lehre aus #1703/S9, und an ihnen hängt eine
// Rechtspflicht.
const gerechnet = computed<any>(() => (editing.value as any)?.meldepflicht || null)
const abweichung = computed(() =>
  !!gerechnet.value
  && ((gerechnet.value.aufsicht.pflicht && !aufsichtPflicht.value)
      || (gerechnet.value.betroffene.pflicht && !betroffenePflicht.value)))

function pflichtUebernehmen() {
  const v = gerechnet.value?.vorschlag
  if (!v) return
  // Nur setzen, nie zurücknehmen: Wer meldet, obwohl er nicht müsste, tut
  // nichts Falsches — und ein Häkchen wegzunehmen wäre ein Rat, nicht zu
  // melden.
  if (v.meldung_aufsicht_pflicht) aufsichtPflicht.value = true
  if (v.meldung_betroffene_pflicht) betroffenePflicht.value = true
}
const betroffenePflicht = ref(false)
const busy = ref('')

const overdueCount = computed(() => store.pannen.filter((p) => p.frist?.overdue).length)

const countdownLabel = (p: Datenpanne): string => {
  const f = p.frist
  if (!f || f.ampel === 'grau') return f?.due_at ? '— erledigt —' : t('dsgvo.datenpannenPanel.keineFrist')
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
/* #1891 */
.gerechnet { font-size: 11px; border-radius: 9px; padding: 0 6px; margin-left: 6px; }
.gerechnet.ja { background: #ffe0b2; color: #e65100; }
.gerechnet.nein { background: #e8f5e9; color: #2e7d32; }
.meldehinweis { font-size: 12px; color: #ef6c00; margin: 4px 0; }
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
