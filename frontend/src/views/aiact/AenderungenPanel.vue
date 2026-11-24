<template>
  <div class="aend-panel">
    <p v-if="!projekt" class="hint">{{ $t('aiact.aenderungenPanel.bitteZuerstEinKISystemAuswahlen') }}</p>

    <template v-else>
      <div class="aend-toolbar">
        <div class="toolbar-info">
          <strong>{{ $t('aiact.aenderungenPanel.anderungenAmKISystemArtAbs') }}</strong>
          <span class="muted">
            {{ $t('aiact.aenderungenPanel.v0VorgangVorgangeV1InPrufung', { v0: store.aenderungen.length, v1: inPruefung }) }}
          </span>
        </div>
        <button class="btn-secondary" @click="neuOeffnen">{{ $t('aiact.aenderungenPanel.anderungErfassen') }}</button>
      </div>

      <p v-if="meldung" class="status-msg">{{ meldung }}</p>

      <p class="muted intro">
        {{ $t('aiact.aenderungenPanel.eineAnderungAmSystemNachtrainingNeue') }} <strong>{{ $t('aiact.aenderungenPanel.keine') }}</strong> {{ $t('aiact.aenderungenPanel.wesentlicheAnderungDieTechnischeDoku') }}
      </p>

      <!-- Neuanlage -->
      <section v-if="neu.offen" class="card neu">
        <h4>{{ $t('aiact.aenderungenPanel.neueAnderungErfassen') }}</h4>
        <div class="grid">
          <label class="full">{{ $t('aiact.aenderungenPanel.standBezeichnerDerAnderung') }}
            <input v-model="neu.stand" :placeholder="$t('aiact.aenderungenPanel.zBModellOderNachtrainingQ3')" />
          </label>
          <label>{{ $t('aiact.aenderungenPanel.anlass') }}
            <select v-model="neu.grund_art">
              <option v-for="g in grundArten" :key="g.code" :value="g.code">{{ g.label }}</option>
            </select>
          </label>
          <label>{{ $t('aiact.aenderungenPanel.modellVersion') }}<input v-model="neu.modell_version" placeholder="m-4.2" /></label>
          <label>{{ $t('aiact.aenderungenPanel.datenVersion') }}<input v-model="neu.daten_version" placeholder="ds-2026-09" /></label>
          <label>{{ $t('aiact.aenderungenPanel.wirksamAb') }}<input type="date" v-model="neu.wirksam_ab" /></label>
          <label class="full">{{ $t('common.description') }}
            <textarea v-model="neu.beschreibung" rows="2"></textarea>
          </label>
        </div>
        <div class="row">
          <button class="btn-primary" :disabled="!neu.stand.trim() || busy" @click="anlegen">
            {{ $t('common.anlegen') }}
          </button>
          <button class="btn-small" @click="neu.offen = false">{{ $t('common.cancel') }}</button>
        </div>
      </section>

      <!-- Liste -->
      <section v-if="!store.aenderungen.length && !neu.offen" class="card">
        <p class="muted">{{ $t('aiact.aenderungenPanel.nochKeineAnderungErfasst') }}</p>
      </section>

      <section v-for="a in store.aenderungen" :key="a.stand" class="card"
               :class="'st-' + a.status">
        <div class="row between head" @click="oeffnen(a.stand)">
          <h4>
            <span class="caret">{{ offen === a.stand ? '▾' : '▸' }}</span>
            {{ a.stand }}
            <span class="muted small">{{ labelGrund(a.grund_art) }}</span>
          </h4>
          <span class="pill" :class="'pill-' + a.status">{{ statusLabel(a.status) }}</span>
        </div>
        <p class="muted small meta">
          <template v-if="a.modell_version">{{ $t('aiact.aenderungenPanel.modellV0', { v0: a.modell_version }) }} </template>
          <template v-if="a.daten_version">{{ $t('aiact.aenderungenPanel.datenV0', { v0: a.daten_version }) }} </template>
          <span :class="kernKlasse(a.wesentlich)">{{ kernKurz(a.wesentlich) }}</span>
        </p>

        <!-- Detail -->
        <div v-if="offen === a.stand" class="detail">
          <p v-if="ladeDetail" class="muted">{{ $t('aiact.aenderungenPanel.ladeVorgang') }}</p>
          <template v-else-if="detail">
            <!-- Ampel -->
            <div class="ampel-box" :class="'ampel-' + (gate.ampel || 'grey')">
              <strong>{{ ampelText(gate.ampel) }}</strong>
              <span v-if="gate.ungeprueft?.length" class="warn">
                {{ $t('aiact.aenderungenPanel.v0PrufungEnKonntenNichtLaufenUngepru', { v0: gate.ungeprueft.length }) }}
              </span>
            </div>
            <ul v-if="gate.offene_punkte?.length" class="punkte">
              <li v-for="(p, i) in gate.offene_punkte" :key="i"
                  :class="p.ampel_wirkung === 'rot' ? 'rot' : (p.ungeprueft ? 'ungeprueft' : '')">
                <strong>{{ p.titel }}</strong>
                <span class="muted small"> — {{ p.hinweis }}</span>
                <span v-if="p.ref" class="ref">{{ p.ref }}</span>
                <button v-if="p.link" class="btn-link" @click="$emit('goto', p.link)">
                  {{ $t('aiact.aenderungenPanel.hierPflegen') }}
                </button>
              </li>
            </ul>

            <!-- Kernfrage -->
            <div class="kernfrage">
              <h5>{{ $t('aiact.aenderungenPanel.wesentlicheAnderungArtNrArtAbs') }}</h5>
              <p class="muted small">
                {{ $t('aiact.aenderungenPanel.dreiAntwortenEineWesentlicheAnderung') }}
              </p>
              <div class="grid">
                <label>{{ $t('common.antwort') }}
                  <select v-model="kern.wert" :disabled="detail.vorgang.gesperrt">
                    <option value="">{{ $t('aiact.aenderungenPanel.offen') }}</option>
                    <option v-for="w in wesentlichWerte" :key="w.code" :value="w.code">
                      {{ w.label }}
                    </option>
                  </select>
                </label>
                <label v-if="kern.wert === 'vorab_bewertet'" class="full">
                  {{ $t('aiact.aenderungenPanel.fundstelleDerVorabFestgelegtenAnderu') }}
                  <input v-model="kern.vorab_referenz" :disabled="detail.vorgang.gesperrt"
                         :placeholder="$t('aiact.aenderungenPanel.zBTechDocAbschnittAnhangIVNrF')" />
                </label>
                <label class="full">{{ $t('aiact.aenderungenPanel.begrundungAuchFurNein') }}
                  <textarea v-model="kern.grund" rows="2"
                            :disabled="detail.vorgang.gesperrt"></textarea>
                </label>
              </div>
              <button class="btn-primary" :disabled="!kern.wert || detail.vorgang.gesperrt || busy"
                      @click="kernSpeichern(a.stand)">
                {{ $t('aiact.aenderungenPanel.antwortSpeichern') }}
              </button>
              <p v-if="detail.vorgang.wesentlich_von" class="muted small">
                {{ $t('aiact.aenderungenPanel.beantwortetVonV0', { v0: detail.vorgang.wesentlich_von }) }}
                <template v-if="detail.vorgang.wesentlich_am">
                  am {{ (detail.vorgang.wesentlich_am || '').slice(0, 10) }}
                </template>
              </p>
            </div>

            <!-- Checkliste in drei Arten -->
            <div v-for="art in ARTEN" :key="art.id" class="checkgruppe">
              <h5>{{ art.label }}</h5>
              <p class="muted small">{{ art.hinweis }}</p>
              <div v-for="item in katalogNach(art.id)" :key="item.id" class="punkt"
                   :class="{ irrelevant: item.relevant === false }">
                <div class="row between">
                  <div>
                    <strong>{{ item.label }}</strong>
                    <span class="ref">{{ item.rechtsbezug }}</span>
                  </div>
                  <template v-if="item.relevant === false">
                    <span class="pill pill-irrelevant">{{ $t('aiact.aenderungenPanel.entfallt') }}</span>
                  </template>
                  <template v-else-if="item.art === 'gerechnet'">
                    <span class="pill pill-gerechnet">gerechnet</span>
                  </template>
                  <template v-else-if="item.id === KERNFRAGE">
                    <span class="pill pill-gerechnet">{{ $t('aiact.aenderungenPanel.sieheOben') }}</span>
                  </template>
                  <select v-else :value="standVon(item.id).status"
                          :disabled="detail.vorgang.gesperrt"
                          @change="statusSetzen(a.stand, item, $event)">
                    <option v-for="s in checkStatus" :key="s" :value="s">{{ s }}</option>
                  </select>
                </div>
                <p v-if="item.erklaerung" class="muted small">{{ item.erklaerung }}</p>
                <p v-if="item.relevant === false" class="muted small">
                  {{ item.nicht_relevant_grund }}
                </p>
                <p v-else-if="standVon(item.id).begruendung" class="muted small begr">
                  „{{ standVon(item.id).begruendung }}“
                  <template v-if="standVon(item.id).von">— {{ standVon(item.id).von }}</template>
                </p>
              </div>
            </div>

            <!-- Statusmaschine -->
            <div class="schritte">
              <h5>{{ $t('aiact.aenderungenPanel.prufungUndFreigabe') }}</h5>
              <p class="muted small">
                {{ $t('aiact.aenderungenPanel.entwicklungReichtEinEineZweitePerson') }}
                <code>aiact_approver</code>{{ $t('aiact.aenderungenPanel.werEinreichtKannNichtFreigeben') }}
              </p>
              <div class="row">
                <button v-if="['entwurf', 'zurueckgewiesen'].includes(detail.vorgang.status)"
                        class="btn-primary" :disabled="busy"
                        @click="schritt(a.stand, 'einreichen')">
                  {{ $t('aiact.aenderungenPanel.zurPrufungGeben') }}
                </button>
                <template v-if="detail.vorgang.status === 'in_pruefung'">
                  <button class="btn-primary" :disabled="busy"
                          @click="schritt(a.stand, 'freigeben')">{{ $t('aiact.aenderungenPanel.freigeben') }}</button>
                  <button class="btn-small danger" :disabled="busy"
                          @click="zurueckweisen(a.stand)">{{ $t('aiact.aenderungenPanel.zuruckweisen') }}</button>
                </template>
                <button v-if="detail.vorgang.status === 'freigegeben'" class="btn-primary"
                        :disabled="busy" @click="schritt(a.stand, 'umsetzen')">
                  {{ $t('aiact.aenderungenPanel.alsUmgesetztMarkieren') }}
                </button>
                <button v-if="detail.vorgang.status === 'entwurf'" class="btn-small danger"
                        :disabled="busy" @click="verwerfen(a.stand)">{{ $t('aiact.aenderungenPanel.entwurfVerwerfen') }}</button>
              </div>
              <p v-if="detail.vorgang.zurueckweisung_grund" class="zurueck">
                {{ $t('aiact.aenderungenPanel.zuruckgewiesenVonV0V1', { v0: detail.vorgang.geprueft_von, v1: detail.vorgang.zurueckweisung_grund }) }}
              </p>
              <p class="muted small">
                <template v-if="detail.vorgang.erstellt_von">
                  {{ $t('aiact.aenderungenPanel.eingereichtVonV0', { v0: detail.vorgang.erstellt_von }) }}
                </template>
                <template v-if="detail.vorgang.freigegeben_von">
                  {{ $t('aiact.aenderungenPanel.freigegebenVonV0', { v0: detail.vorgang.freigegeben_von }) }}
                </template>
                {{ $t('aiact.aenderungenPanel.standBeiEinreichungV0', { v0: detail.gate_bei_einreichung?.ampel || $t('aiact.aenderungenPanel.nochNichtEingereicht') }) }}
              </p>
            </div>
          </template>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import { t } from '../../i18n'

defineEmits<{ (e: 'goto', tab: string): void }>()

const store = useAiActStore()
const projekt = computed(() => store.selectedProjekt)

const KERNFRAGE = 'wesentliche_aenderung'
const ARTEN = [
  { id: 'gerechnet', label: t('aiact.aenderungenPanel.gerechnet'),
    hinweis: t('aiact.aenderungenPanel.ausDenRegisternDerAnwendungAbgeleite')
      + t('aiact.aenderungenPanel.eineChecklisteDieSichSelbstAbhakenLa') },
  { id: 'entscheidung', label: t('aiact.aenderungenPanel.entscheidung'),
    hinweis: t('aiact.aenderungenPanel.jedesMalNeuZuBeantwortenMitBegrundun') },
  { id: 'gleichbleibend', label: t('aiact.aenderungenPanel.gleichbleibend'),
    hinweis: t('aiact.aenderungenPanel.einmalGesetztJeAnderungNurBestatigt') },
]

const busy = ref(false)
const meldung = ref('')
const offen = ref<string>('')
const detail = ref<any | null>(null)
const ladeDetail = ref(false)
const neu = reactive({ offen: false, stand: '', grund_art: 'nachtraining',
  beschreibung: '', modell_version: '', daten_version: '', wirksam_ab: '' })
const kern = reactive({ wert: '', grund: '', vorab_referenz: '' })

const grundArten = computed(() => store.aenderungConstants?.grund_arten || [])
const wesentlichWerte = computed(() => store.aenderungConstants?.wesentlich_werte || [])
const checkStatus = computed(() => store.aenderungConstants?.checkliste_status
  || ['offen', 'erledigt', 'nicht_anwendbar'])
const gate = computed(() => detail.value?.gate || {})
const inPruefung = computed(
  () => store.aenderungen.filter((a: any) => a.status === 'in_pruefung').length)

const labelGrund = (code: string) =>
  grundArten.value.find((g: any) => g.code === code)?.label || code
const statusLabel = (s: string) => ({
  entwurf: t('common.entwurf'), in_pruefung: t('aiact.aenderungenPanel.inPrufung'), freigegeben: 'freigegeben',
  zurueckgewiesen: t('aiact.aenderungenPanel.zuruckgewiesen'), umgesetzt: 'umgesetzt',
} as Record<string, string>)[s] || s
const kernKurz = (w: string) => ({
  ja: t('aiact.aenderungenPanel.wesentlicheAnderungErneuteKonformita'),
  nein: t('aiact.aenderungenPanel.keineWesentlicheAnderung'),
  vorab_bewertet: t('aiact.aenderungenPanel.vorabFestgelegtUndMitbewertetArtAbs'),
} as Record<string, string>)[w] || t('aiact.aenderungenPanel.kernfrageOffen')
const kernKlasse = (w: string) =>
  w === 'ja' ? 'kern-ja' : (w ? 'kern-ok' : 'kern-offen')
const ampelText = (a: string) => ({
  gruen: t('aiact.aenderungenPanel.keineOffenenPunkte'), bedingt: t('aiact.aenderungenPanel.offenePunkteAkteUnvollstandig'),
  rot: t('aiact.aenderungenPanel.offenePflichtverletzung'),
} as Record<string, string>)[a] || t('aiact.aenderungenPanel.nichtBewertet')

const katalogNach = (art: string) =>
  (detail.value?.katalog || []).filter((i: any) => i.art === art)
const standVon = (id: string) => detail.value?.stand?.[id]
  || { status: 'offen', begruendung: '', von: '', am: '' }

async function laden() {
  detail.value = null
  offen.value = ''
  if (!projekt.value) return
  await store.fetchAenderungConstants()
  await store.fetchAenderungen()
}

function neuOeffnen() {
  neu.offen = true
  neu.stand = ''
  neu.beschreibung = ''
  neu.modell_version = ''
  neu.daten_version = ''
  neu.wirksam_ab = ''
}

async function anlegen() {
  busy.value = true
  meldung.value = ''
  const { offen: _ignore, ...daten } = neu
  const r = await store.createAenderung(daten)
  busy.value = false
  if (!r) { meldung.value = store.error || t('fehler.anlegen'); store.error = null; return }
  neu.offen = false
  await store.fetchAenderungen()
  await oeffnen(r.stand)
}

async function oeffnen(stand: string) {
  if (offen.value === stand) { offen.value = ''; detail.value = null; return }
  offen.value = stand
  ladeDetail.value = true
  detail.value = await store.fetchAenderung(stand)
  ladeDetail.value = false
  const v = detail.value?.vorgang || {}
  kern.wert = v.wesentlich || ''
  kern.grund = v.wesentlich_grund || ''
  kern.vorab_referenz = v.vorab_referenz || ''
}

async function neuLaden(stand: string) {
  detail.value = await store.fetchAenderung(stand)
  await store.fetchAenderungen()
}

async function kernSpeichern(stand: string) {
  busy.value = true
  meldung.value = ''
  const r = await store.setAenderungWesentlich(stand, kern.wert, kern.grund,
                                               kern.vorab_referenz)
  busy.value = false
  if (!r) { meldung.value = store.error || t('common.speichernFehlgeschlagen'); store.error = null; return }
  await neuLaden(stand)
  meldung.value = t('aiact.aenderungenPanel.antwortGespeichert')
}

async function statusSetzen(stand: string, item: any, ev: Event) {
  const status = (ev.target as HTMLSelectElement).value
  let begruendung = standVon(item.id).begruendung || ''
  if (status !== 'offen' && (detail.value?.katalog || []).length) {
    const pflicht = item.art === 'entscheidung'
    if (pflicht) {
      const eingabe = window.prompt(
        `Begründung für „${item.label}“ (${item.rechtsbezug}):`, begruendung)
      if (eingabe === null) { await neuLaden(stand); return }
      begruendung = eingabe
    }
  }
  busy.value = true
  const r = await store.setAenderungCheckliste(stand, item.id, status, begruendung)
  busy.value = false
  if (!r) { meldung.value = store.error || t('aiact.aenderungenPanel.setzenFehlgeschlagen'); store.error = null }
  await neuLaden(stand)
}

async function schritt(stand: string, name: 'einreichen' | 'freigeben' | 'umsetzen') {
  busy.value = true
  meldung.value = ''
  const r = await store.aenderungSchritt(stand, name)
  busy.value = false
  if (!r) { meldung.value = store.error || t('aiact.aenderungenPanel.schrittFehlgeschlagen'); store.error = null }
  await neuLaden(stand)
}

async function zurueckweisen(stand: string) {
  const grund = window.prompt('Begründung der Zurückweisung (mindestens 10 Zeichen):', '')
  if (!grund) return
  busy.value = true
  const r = await store.aenderungSchritt(stand, 'zurueckweisen', { grund })
  busy.value = false
  if (!r) { meldung.value = store.error || t('aiact.aenderungenPanel.zuruckweisenFehlgeschlagen'); store.error = null }
  await neuLaden(stand)
}

async function verwerfen(stand: string) {
  if (!window.confirm(`Entwurf „${stand}“ verwerfen?`)) return
  busy.value = true
  const ok = await store.deleteAenderung(stand)
  busy.value = false
  if (!ok) { meldung.value = store.error || t('aiact.aenderungenPanel.verwerfenFehlgeschlagen'); store.error = null; return }
  offen.value = ''
  detail.value = null
  await store.fetchAenderungen()
}

onMounted(laden)
watch(projekt, laden)
</script>

<style scoped>
.aend-panel { padding: 8px 0; }
.hint { color: #607d8b; padding: 16px; }
.aend-toolbar { background: #1565c0; color: #fff; padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }
.toolbar-info strong { color: #fff; }
.toolbar-info .muted { color: #90caf9; margin-left: 12px; }
.status-msg { color: #1565c0; margin: 8px 0; }
.intro { max-width: 72em; line-height: 1.5; }
.card { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin-bottom: 14px; border-left: 4px solid #cfd8dc; }
.card.st-in_pruefung { border-left-color: #f9a825; }
.card.st-freigegeben { border-left-color: #2e7d32; }
.card.st-zurueckgewiesen { border-left-color: #c62828; }
.card.st-umgesetzt { border-left-color: #1565c0; }
.card h4 { margin: 0; color: #0d47a1; }
.card h5 { margin: 14px 0 4px; color: #455a64; }
.head { cursor: pointer; }
.caret { color: #90a4ae; margin-right: 6px; }
.meta { margin: 4px 0 0; }
.row { display: flex; gap: 12px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
.row.between { justify-content: space-between; }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 8px 0; }
label { display: flex; flex-direction: column; font-size: 0.82em; color: #455a64; gap: 3px; }
label.full { grid-column: 1 / -1; }
input, select, textarea { box-sizing: border-box; width: 100%; padding: 4px 6px; }
.muted { color: #78909c; font-size: 0.9em; }
.small { font-size: 0.82em; }
.pill { padding: 2px 8px; border-radius: 10px; font-size: 0.8em; background: #eceff1; white-space: nowrap; }
.pill-in_pruefung { background: #fff3e0; }
.pill-freigegeben { background: #e8f5e9; }
.pill-zurueckgewiesen { background: #ffebee; }
.pill-umgesetzt { background: #e3f2fd; }
.pill-gerechnet, .pill-irrelevant { background: #eceff1; color: #607d8b; }
.detail { border-top: 1px solid #eee; margin-top: 12px; padding-top: 8px; }
.ampel-box { padding: 8px 12px; border-radius: 6px; background: #f5f5f5; }
.ampel-box.ampel-gruen { background: #e8f5e9; }
.ampel-box.ampel-bedingt { background: #fff8e1; }
.ampel-box.ampel-rot { background: #ffebee; }
.ampel-box .warn { color: #c62828; font-size: 0.85em; }
.punkte { margin: 8px 0; padding-left: 18px; }
.punkte li { font-size: 0.86em; padding: 2px 0; }
.punkte li.rot strong { color: #c62828; }
.punkte li.ungeprueft strong { color: #ef6c00; }
.ref { color: #90a4ae; font-size: 0.78em; margin-left: 6px; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; font-size: 0.82em; }
.kernfrage { background: #f3f7fb; border: 1px solid #d6e4f0; border-radius: 6px; padding: 10px 12px; margin: 12px 0; }
.kern-ja { color: #c62828; font-weight: 600; }
.kern-ok { color: #2e7d32; }
.kern-offen { color: #ef6c00; }
.checkgruppe { margin: 12px 0; }
.punkt { border-top: 1px dashed #eceff1; padding: 6px 0; }
.punkt.irrelevant { opacity: 0.6; }
.punkt .begr { color: #546e7a; }
.schritte { background: #fafafa; border: 1px solid #eee; border-radius: 6px; padding: 8px 12px; margin-top: 12px; }
.zurueck { color: #c62828; font-size: 0.85em; }
.btn-small.danger { color: #c62828; }
.card.neu { border-left-color: #1565c0; }
</style>
