<template>
  <div class="aend-panel">
    <p v-if="!projekt" class="hint">Bitte zuerst ein KI-System auswählen.</p>

    <template v-else>
      <div class="aend-toolbar">
        <div class="toolbar-info">
          <strong>🔄 Änderungen am KI-System — Art. 43 Abs. 4</strong>
          <span class="muted">
            {{ store.aenderungen.length }} Vorgang/Vorgänge ·
            {{ inPruefung }} in Prüfung
          </span>
        </div>
        <button class="btn-secondary" @click="neuOeffnen">➕ Änderung erfassen</button>
      </div>

      <p v-if="meldung" class="status-msg">{{ meldung }}</p>

      <p class="muted intro">
        Eine Änderung am System — Nachtraining, neue Trainingsdaten, geänderte
        Zweckbestimmung, abweichende Leistung im Betrieb — kann eine erneute
        Konformitätsbewertung auslösen (Art. 43 Abs. 4). Nicht jede tut das:
        Änderungen, die vorab festgelegt und bei der Konformitätsbewertung
        bereits mitbewertet wurden, sind <strong>keine</strong> wesentliche
        Änderung. Die technische Dokumentation (Art. 11, Anhang IV), die
        Registrierung in der EU-Datenbank (Art. 49) und der Beobachtungsplan
        (Art. 72) sind dagegen in jedem Fall nachzuziehen.
      </p>

      <!-- Neuanlage -->
      <section v-if="neu.offen" class="card neu">
        <h4>Neue Änderung erfassen</h4>
        <div class="grid">
          <label class="full">Stand / Bezeichner der Änderung *
            <input v-model="neu.stand" placeholder="z. B. modell-2026-10 oder „Nachtraining Q3“" />
          </label>
          <label>Anlass
            <select v-model="neu.grund_art">
              <option v-for="g in grundArten" :key="g.code" :value="g.code">{{ g.label }}</option>
            </select>
          </label>
          <label>Modell-Version<input v-model="neu.modell_version" placeholder="m-4.2" /></label>
          <label>Daten-Version<input v-model="neu.daten_version" placeholder="ds-2026-09" /></label>
          <label>wirksam ab<input type="date" v-model="neu.wirksam_ab" /></label>
          <label class="full">Beschreibung
            <textarea v-model="neu.beschreibung" rows="2"></textarea>
          </label>
        </div>
        <div class="row">
          <button class="btn-primary" :disabled="!neu.stand.trim() || busy" @click="anlegen">
            Anlegen
          </button>
          <button class="btn-small" @click="neu.offen = false">Abbrechen</button>
        </div>
      </section>

      <!-- Liste -->
      <section v-if="!store.aenderungen.length && !neu.offen" class="card">
        <p class="muted">Noch keine Änderung erfasst.</p>
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
          <template v-if="a.modell_version">Modell {{ a.modell_version }} · </template>
          <template v-if="a.daten_version">Daten {{ a.daten_version }} · </template>
          <span :class="kernKlasse(a.wesentlich)">{{ kernKurz(a.wesentlich) }}</span>
        </p>

        <!-- Detail -->
        <div v-if="offen === a.stand" class="detail">
          <p v-if="ladeDetail" class="muted">⏳ Lade Vorgang…</p>
          <template v-else-if="detail">
            <!-- Ampel -->
            <div class="ampel-box" :class="'ampel-' + (gate.ampel || 'grey')">
              <strong>{{ ampelText(gate.ampel) }}</strong>
              <span v-if="gate.ungeprueft?.length" class="warn">
                · {{ gate.ungeprueft.length }} Prüfung(en) konnten nicht laufen —
                ungeprüft ist nicht erfüllt
              </span>
            </div>
            <ul v-if="gate.offene_punkte?.length" class="punkte">
              <li v-for="(p, i) in gate.offene_punkte" :key="i"
                  :class="p.ampel_wirkung === 'rot' ? 'rot' : (p.ungeprueft ? 'ungeprueft' : '')">
                <strong>{{ p.titel }}</strong>
                <span class="muted small"> — {{ p.hinweis }}</span>
                <span v-if="p.ref" class="ref">{{ p.ref }}</span>
                <button v-if="p.link" class="btn-link" @click="$emit('goto', p.link)">
                  → hier pflegen
                </button>
              </li>
            </ul>

            <!-- Kernfrage -->
            <div class="kernfrage">
              <h5>Wesentliche Änderung? (Art. 3 Nr. 23, Art. 43 Abs. 4)</h5>
              <p class="muted small">
                Drei Antworten: Eine wesentliche Änderung löst eine erneute
                Konformitätsbewertung aus. „Vorab festgelegt und mitbewertet“ ist
                der Ausnahmetatbestand des Art. 43 Abs. 4 — bei fortlernenden
                Systemen der Normalfall — und verlangt die Fundstelle in der
                technischen Dokumentation.
              </p>
              <div class="grid">
                <label>Antwort
                  <select v-model="kern.wert" :disabled="detail.vorgang.gesperrt">
                    <option value="">— offen —</option>
                    <option v-for="w in wesentlichWerte" :key="w.code" :value="w.code">
                      {{ w.label }}
                    </option>
                  </select>
                </label>
                <label v-if="kern.wert === 'vorab_bewertet'" class="full">
                  Fundstelle der vorab festgelegten Änderung *
                  <input v-model="kern.vorab_referenz" :disabled="detail.vorgang.gesperrt"
                         placeholder="z. B. TechDoc Abschnitt 4.3 (Anhang IV Nr. 2 f)" />
                </label>
                <label class="full">Begründung * (auch für „nein“)
                  <textarea v-model="kern.grund" rows="2"
                            :disabled="detail.vorgang.gesperrt"></textarea>
                </label>
              </div>
              <button class="btn-primary" :disabled="!kern.wert || detail.vorgang.gesperrt || busy"
                      @click="kernSpeichern(a.stand)">
                Antwort speichern
              </button>
              <p v-if="detail.vorgang.wesentlich_von" class="muted small">
                beantwortet von {{ detail.vorgang.wesentlich_von }}
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
                    <span class="pill pill-irrelevant">entfällt</span>
                  </template>
                  <template v-else-if="item.art === 'gerechnet'">
                    <span class="pill pill-gerechnet">gerechnet</span>
                  </template>
                  <template v-else-if="item.id === KERNFRAGE">
                    <span class="pill pill-gerechnet">siehe oben</span>
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
              <h5>Prüfung und Freigabe</h5>
              <p class="muted small">
                Entwicklung reicht ein, eine zweite Person gibt frei (Rolle
                <code>aiact_approver</code>). Wer einreicht, kann nicht freigeben.
              </p>
              <div class="row">
                <button v-if="['entwurf', 'zurueckgewiesen'].includes(detail.vorgang.status)"
                        class="btn-primary" :disabled="busy"
                        @click="schritt(a.stand, 'einreichen')">
                  📤 Zur Prüfung geben
                </button>
                <template v-if="detail.vorgang.status === 'in_pruefung'">
                  <button class="btn-primary" :disabled="busy"
                          @click="schritt(a.stand, 'freigeben')">✅ Freigeben</button>
                  <button class="btn-small danger" :disabled="busy"
                          @click="zurueckweisen(a.stand)">↩️ Zurückweisen</button>
                </template>
                <button v-if="detail.vorgang.status === 'freigegeben'" class="btn-primary"
                        :disabled="busy" @click="schritt(a.stand, 'umsetzen')">
                  🚀 Als umgesetzt markieren
                </button>
                <button v-if="detail.vorgang.status === 'entwurf'" class="btn-small danger"
                        :disabled="busy" @click="verwerfen(a.stand)">🗑️ Entwurf verwerfen</button>
              </div>
              <p v-if="detail.vorgang.zurueckweisung_grund" class="zurueck">
                Zurückgewiesen von {{ detail.vorgang.geprueft_von }}:
                „{{ detail.vorgang.zurueckweisung_grund }}“
              </p>
              <p class="muted small">
                <template v-if="detail.vorgang.erstellt_von">
                  eingereicht von {{ detail.vorgang.erstellt_von }} ·
                </template>
                <template v-if="detail.vorgang.freigegeben_von">
                  freigegeben von {{ detail.vorgang.freigegeben_von }} ·
                </template>
                Stand bei Einreichung:
                {{ detail.gate_bei_einreichung?.ampel || '— noch nicht eingereicht' }}
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

defineEmits<{ (e: 'goto', tab: string): void }>()

const store = useAiActStore()
const projekt = computed(() => store.selectedProjekt)

const KERNFRAGE = 'wesentliche_aenderung'
const ARTEN = [
  { id: 'gerechnet', label: '🧮 Gerechnet',
    hinweis: 'Aus den Registern der Anwendung abgeleitet — nicht von Hand setzbar. '
      + 'Eine Checkliste, die sich selbst abhaken lässt, belegt nichts.' },
  { id: 'entscheidung', label: '✍️ Entscheidung',
    hinweis: 'Jedes Mal neu zu beantworten, mit Begründung.' },
  { id: 'gleichbleibend', label: '📎 Gleichbleibend',
    hinweis: 'Einmal gesetzt, je Änderung nur bestätigt.' },
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
  entwurf: 'Entwurf', in_pruefung: 'in Prüfung', freigegeben: 'freigegeben',
  zurueckgewiesen: 'zurückgewiesen', umgesetzt: 'umgesetzt',
} as Record<string, string>)[s] || s
const kernKurz = (w: string) => ({
  ja: '⚠️ wesentliche Änderung — erneute Konformitätsbewertung',
  nein: 'keine wesentliche Änderung',
  vorab_bewertet: 'vorab festgelegt und mitbewertet (Art. 43 Abs. 4)',
} as Record<string, string>)[w] || 'Kernfrage offen'
const kernKlasse = (w: string) =>
  w === 'ja' ? 'kern-ja' : (w ? 'kern-ok' : 'kern-offen')
const ampelText = (a: string) => ({
  gruen: '🟢 Keine offenen Punkte', bedingt: '🟡 Offene Punkte — Akte unvollständig',
  rot: '🔴 Offene Pflichtverletzung',
} as Record<string, string>)[a] || '— nicht bewertet'

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
  if (!r) { meldung.value = store.error || 'Anlegen fehlgeschlagen.'; store.error = null; return }
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
  if (!r) { meldung.value = store.error || 'Speichern fehlgeschlagen.'; store.error = null; return }
  await neuLaden(stand)
  meldung.value = 'Antwort gespeichert.'
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
  if (!r) { meldung.value = store.error || 'Setzen fehlgeschlagen.'; store.error = null }
  await neuLaden(stand)
}

async function schritt(stand: string, name: 'einreichen' | 'freigeben' | 'umsetzen') {
  busy.value = true
  meldung.value = ''
  const r = await store.aenderungSchritt(stand, name)
  busy.value = false
  if (!r) { meldung.value = store.error || 'Schritt fehlgeschlagen.'; store.error = null }
  await neuLaden(stand)
}

async function zurueckweisen(stand: string) {
  const grund = window.prompt('Begründung der Zurückweisung (mindestens 10 Zeichen):', '')
  if (!grund) return
  busy.value = true
  const r = await store.aenderungSchritt(stand, 'zurueckweisen', { grund })
  busy.value = false
  if (!r) { meldung.value = store.error || 'Zurückweisen fehlgeschlagen.'; store.error = null }
  await neuLaden(stand)
}

async function verwerfen(stand: string) {
  if (!window.confirm(`Entwurf „${stand}“ verwerfen?`)) return
  busy.value = true
  const ok = await store.deleteAenderung(stand)
  busy.value = false
  if (!ok) { meldung.value = store.error || 'Verwerfen fehlgeschlagen.'; store.error = null; return }
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
