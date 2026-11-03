<template>
  <div class="wasserstand">
    <div class="intro">
      <h3>📊 Wasserstandsmeldung</h3>
      <p>
        Der Compliance-Stand wird <strong>aus den Antworten berechnet</strong>, nicht
        von der KI vergeben — bei gleichen Antworten kommt immer dieselbe Stufe heraus.
        Die KI formuliert nur den Text für den Kunden.
      </p>
    </div>

    <FehlerHinweis :text="fehler" @close="fehler = ''" />

    <!-- Berechneter Stand -->
    <div v-if="status" class="stand-card" :class="'stufe-' + status.stufe">
      <div class="stand-kopf">
        <div class="ampel">{{ ampel(status.stufe) }}</div>
        <div>
          <div class="stufe-label">{{ status.label }}</div>
          <div class="stufe-bedeutung">{{ status.bedeutung }}</div>
        </div>
        <div class="quote">
          <strong>{{ status.quote_prozent ?? '–' }} %</strong>
          <span>Erfüllungsquote</span>
        </div>
      </div>

      <div class="kennzahlen">
        <span>{{ status.fragen.gesamt }} Fragen</span>
        <span class="k-ok">{{ status.fragen.erfuellt }} erfüllt</span>
        <span class="k-teil">{{ status.fragen.teilweise }} teilweise</span>
        <span class="k-nein">{{ status.fragen.nicht_erfuellt }} nicht erfüllt</span>
        <span class="k-offen">{{ status.fragen.offen }} offen</span>
        <span class="k-na">{{ status.fragen.nicht_anwendbar }} n. a.</span>
      </div>

      <p v-if="status.fragen.offen > 0" class="hinweis">
        ⚠️ {{ status.fragen.offen }} Fragen sind noch offen. Sie zählen in der Quote als
        <em>nicht nachgewiesen</em> — die Abdeckung liegt bei
        {{ status.abdeckung_prozent ?? '–' }} %. Nur die bewerteten Fragen ergäben
        {{ status.quote_bewertet_prozent ?? '–' }} %.
      </p>

      <table v-if="status.frameworks?.length" class="fw-tabelle">
        <thead>
          <tr><th>Framework</th><th>Stufe</th><th>Quote</th><th>offen</th></tr>
        </thead>
        <tbody>
          <tr v-for="fw in status.frameworks" :key="fw.framework">
            <td>{{ fw.framework }}</td>
            <td><span :class="'pille stufe-' + fw.stufe">{{ fw.label }}</span></td>
            <td>{{ fw.quote_prozent ?? '–' }} %</td>
            <td>{{ fw.fragen.offen }} / {{ fw.fragen.anwendbar }}</td>
          </tr>
        </tbody>
      </table>

      <div class="aktionen">
        <button class="btn-secondary" :disabled="laedt" @click="ladeStatus">↻ Neu berechnen</button>
        <button class="btn-secondary" :disabled="laedt" @click="backfill"
                title="Erfüllung aus der alten Freitext-Bewertung ableiten (Projekte vor v7.4.0)">
          ⤵ Alte Bewertungen übernehmen
        </button>
        <button class="btn-primary" :disabled="laedt || !hatFragen" @click="holePrompt">
          🤖 Meldung erstellen
        </button>
      </div>
    </div>

    <div v-else-if="laedt" class="lade">Stand wird berechnet …</div>

    <!-- #1723: Gemeinsame Prompt-Komponente wie in allen anderen Modulen —
         Prompt anzeigen, "Direkt mit KI" oder Antwort einfuegen. Vorher ein
         Eigenbau mit KiStreamView, dem das /api-Praefix fehlte: runSse nutzt
         rohes fetch() ohne axios-baseURL, der POST landete in nginx' location /
         mit try_files und ergab "405 Not Allowed". -->
    <WizardPromptModal
      v-if="promptOffen"
      title="Wasserstandsmeldung erstellen"
      :prompt="prompt"
      :busy="laedt"
      force-json
      schema-hint="Die Compliance-Stufe ist vorgegeben und wird nicht neu bewertet — die KI formuliert nur Mitteilung, Lücken und Maßnahmen."
      @apply="uebernehmen"
      @close="promptOffen = false"
      hinweis-modul="compliance-audit"
      :hinweis-projekt="projekt"
      hinweis-bereich="wasserstand"
    />

    <!-- Ergebnis -->
    <div v-if="meldung" class="meldung-card">
      <div class="m-kopf">
        <h4>Mitteilung an den Kunden</h4>
        <div class="m-aktionen">
          <button v-if="!bearbeiten" class="btn-secondary" @click="starteBearbeiten">
            ✏️ Text überarbeiten
          </button>
          <template v-else>
            <button class="btn-secondary" :disabled="laedt" @click="bearbeiten = false">Abbrechen</button>
            <button class="btn-primary" :disabled="laedt" @click="speichereText">💾 Speichern</button>
          </template>
        </div>
      </div>
      <!-- #1783: Wer den Text überarbeitet hat, hat ihn fachlich übernommen.
           Vorher stand hier dauerhaft „fachlich zu prüfen" ohne einen Weg, es zu tun. -->
      <p class="m-herkunft">
        <template v-if="meldungMeta.bearbeitet_von">
          ✍️ Überarbeitet von {{ meldungMeta.bearbeitet_von }}<template
            v-if="meldungMeta.bearbeitet_am"> am
            {{ meldungMeta.bearbeitet_am.slice(0, 16).replace('T', ' ') }}</template>
          — damit fachlich verantwortet.
        </template>
        <template v-else>
          🤖 Von der KI formuliert, fachlich noch nicht geprüft — über „Text überarbeiten“
          anpassen und damit übernehmen.
        </template>
      </p>

      <template v-if="!bearbeiten">
        <div class="kundentext"><ProsaText :text="meldung.kundenmitteilung" /></div>

        <div v-for="fw in meldung.je_framework || []" :key="fw.framework" class="fw-block">
          <h5>{{ fw.framework }}</h5>
          <ProsaText :text="fw.einschaetzung" />
          <div v-if="fw.hauptluecken?.length">
            <strong>Hauptlücken</strong>
            <ul><li v-for="(l, i) in fw.hauptluecken" :key="i"><ProsaText :text="l" eng /></li></ul>
          </div>
          <div v-if="fw.naechste_schritte?.length">
            <strong>Nächste Schritte</strong>
            <ul><li v-for="(l, i) in fw.naechste_schritte" :key="i"><ProsaText :text="l" eng /></li></ul>
          </div>
        </div>

        <!-- #1783: Die Maßnahmen standen in einer vierspaltigen Tabelle; die
             Begründung ist Fließtext und wurde darin zur Spalte von zwei Wörtern
             Breite. Als Liste bekommt sie die Zeile, die sie braucht. -->
        <div v-if="meldung.top_massnahmen?.length" class="massnahmen">
          <h5>Empfohlene Maßnahmen</h5>
          <ol class="m-liste">
            <li v-for="(m, i) in meldung.top_massnahmen" :key="i">
              <div class="m-zeile">
                <strong class="m-titel">{{ m.massnahme }}</strong>
                <span :class="'prio prio-' + m.prioritaet">Priorität {{ m.prioritaet }}</span>
                <span class="aufwand">Aufwand {{ m.aufwand }}</span>
              </div>
              <ProsaText class="m-grund" :text="m.begruendung" eng />
            </li>
          </ol>
        </div>

        <div v-if="meldung.fazit" class="fazit">
          <strong>Fazit</strong>
          <ProsaText :text="meldung.fazit" />
        </div>
      </template>

      <template v-else>
        <label class="feld">Mitteilung an den Kunden
          <textarea v-model="entwurf.kundenmitteilung" rows="7"></textarea>
        </label>

        <div v-for="(fw, fi) in entwurf.je_framework" :key="fi" class="fw-block">
          <h5>{{ fw.framework }}</h5>
          <label class="feld">Einschätzung
            <textarea v-model="fw.einschaetzung" rows="3"></textarea>
          </label>
          <label class="feld">Hauptlücken <span class="hinweis-klein">(eine je Zeile)</span>
            <textarea :value="(fw.hauptluecken || []).join('\n')" rows="3"
                      @input="fw.hauptluecken = zeilen($event)"></textarea>
          </label>
          <label class="feld">Nächste Schritte <span class="hinweis-klein">(einer je Zeile)</span>
            <textarea :value="(fw.naechste_schritte || []).join('\n')" rows="3"
                      @input="fw.naechste_schritte = zeilen($event)"></textarea>
          </label>
        </div>

        <div class="massnahmen">
          <h5>Empfohlene Maßnahmen</h5>
          <div v-for="(m, mi) in entwurf.top_massnahmen" :key="mi" class="m-edit">
            <div class="m-edit-kopf">
              <input v-model="m.massnahme" placeholder="Maßnahme" />
              <select v-model="m.prioritaet">
                <option value="hoch">Priorität hoch</option>
                <option value="mittel">Priorität mittel</option>
                <option value="niedrig">Priorität niedrig</option>
              </select>
              <select v-model="m.aufwand">
                <option value="hoch">Aufwand hoch</option>
                <option value="mittel">Aufwand mittel</option>
                <option value="niedrig">Aufwand niedrig</option>
              </select>
              <button class="btn-mini" title="Maßnahme entfernen"
                      @click="entwurf.top_massnahmen.splice(mi, 1)">🗑️</button>
            </div>
            <textarea v-model="m.begruendung" rows="2" placeholder="Begründung"></textarea>
          </div>
          <button class="btn-secondary" @click="neueMassnahme">+ Maßnahme</button>
        </div>

        <label class="feld">Fazit
          <textarea v-model="entwurf.fazit" rows="3"></textarea>
        </label>
        <p class="hinweis-klein">
          Der gerechnete Stand oben bleibt unverändert — überarbeitet wird nur der Text.
        </p>
      </template>
    </div>

    <!-- Verlauf -->
    <div v-if="verlauf.length" class="verlauf">
      <h4>Verlauf</h4>
      <table>
        <thead><tr><th>Datum</th><th>Stufe</th><th>Quote</th><th>Quelle</th><th></th></tr></thead>
        <tbody>
          <tr v-for="w in verlauf" :key="w.id">
            <td>{{ (w.created_at || '').slice(0, 16).replace('T', ' ') }}</td>
            <td><span :class="'pille stufe-' + w.stufe">{{ w.stufe }}</span></td>
            <td>{{ w.quote_prozent ?? '–' }} %</td>
            <td>{{ w.provider || '–' }}</td>
            <td><button class="btn-mini" @click="oeffne(w.id)">anzeigen</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import apiClient from '../../api/client'
import WizardPromptModal from '../shared/WizardPromptModal.vue'
import FehlerHinweis from '../shared/FehlerHinweis.vue'
import ProsaText from '../shared/ProsaText.vue'

const props = defineProps<{ projekt: string }>()

const status = ref<any>(null)
const meldung = ref<any>(null)
const verlauf = ref<any[]>([])
const prompt = ref('')
const fehler = ref('')
const laedt = ref(false)
const promptOffen = ref(false)

// #1783: Die Meldung ist überarbeitbar. ``meldungId`` ist der Datensatz, in den
// gespeichert wird; ohne ihn wäre „Text überarbeiten" nur eine Anzeige.
const meldungId = ref<number | null>(null)
const meldungMeta = ref<{ bearbeitet_von?: string; bearbeitet_am?: string }>({})
const bearbeiten = ref(false)
const entwurf = ref<any>({ kundenmitteilung: '', je_framework: [], top_massnahmen: [], fazit: '' })

function zeilen(e: Event): string[] {
  return (e.target as HTMLTextAreaElement).value
    .split('\n').map(z => z.trim()).filter(Boolean)
}

function neueMassnahme() {
  entwurf.value.top_massnahmen.push(
    { massnahme: '', begruendung: '', prioritaet: 'mittel', aufwand: 'mittel' })
}

function starteBearbeiten() {
  // Tiefe Kopie: Ein Abbruch soll die angezeigte Meldung nicht verändert haben.
  const m = meldung.value || {}
  entwurf.value = {
    kundenmitteilung: m.kundenmitteilung || '',
    je_framework: (m.je_framework || []).map((f: any) => ({
      framework: f.framework,
      einschaetzung: f.einschaetzung || '',
      hauptluecken: [...(f.hauptluecken || [])],
      naechste_schritte: [...(f.naechste_schritte || [])],
    })),
    top_massnahmen: (m.top_massnahmen || []).map((x: any) => ({ ...x })),
    fazit: m.fazit || '',
  }
  bearbeiten.value = true
}

async function speichereText() {
  if (!meldungId.value) {
    fehler.value = 'Diese Meldung ist noch nicht gespeichert — bitte neu erzeugen.'
    return
  }
  laedt.value = true
  try {
    const r = await apiClient.put(
      `/compliance-audit/${encodeURIComponent(props.projekt)}/wasserstand/${meldungId.value}`,
      { ki: entwurf.value })
    meldung.value = r.data.ki
    meldungMeta.value = { bearbeitet_von: r.data.bearbeitet_von,
                          bearbeitet_am: r.data.bearbeitet_am }
    bearbeiten.value = false
    await ladeVerlauf()
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Text konnte nicht gespeichert werden'
  } finally { laedt.value = false }
}

const hatFragen = computed(() => (status.value?.fragen?.gesamt || 0) > 0)

const AMPELN: Record<string, string> = {
  vollstaendig: '🟢', weitgehend: '🟡', teilweise: '🟠', nicht: '🔴', unbewertet: '⚪',
}
function ampel(stufe: string) { return AMPELN[stufe] || '⚪' }

async function ladeStatus() {
  if (!props.projekt) return
  laedt.value = true
  try {
    const r = await apiClient.get(`/compliance-audit/${encodeURIComponent(props.projekt)}/status`)
    status.value = r.data
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Stand konnte nicht berechnet werden'
  } finally { laedt.value = false }
}

async function ladeVerlauf() {
  if (!props.projekt) return
  try {
    const r = await apiClient.get(`/compliance-audit/${encodeURIComponent(props.projekt)}/wasserstand`)
    verlauf.value = Array.isArray(r.data) ? r.data : []
  } catch { verlauf.value = [] }
}

async function backfill() {
  laedt.value = true
  try {
    const r = await apiClient.post(
      `/compliance-audit/${encodeURIComponent(props.projekt)}/erfuellung/backfill`, {})
    status.value = r.data.status
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Übernahme fehlgeschlagen'
  } finally { laedt.value = false }
}

async function holePrompt() {
  laedt.value = true
  try {
    const r = await apiClient.post(
      `/compliance-audit/${encodeURIComponent(props.projekt)}/wasserstand/prompt`, {})
    prompt.value = r.data.prompt
    status.value = r.data.status
    promptOffen.value = true
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Prompt konnte nicht erzeugt werden'
  } finally { laedt.value = false }
}

async function uebernehmen(rawText: string) {
  laedt.value = true
  try {
    const r = await apiClient.post(
      `/compliance-audit/${encodeURIComponent(props.projekt)}/wasserstand/import`,
      { response: rawText })
    meldung.value = r.data.ki
    meldungId.value = r.data.id ?? null
    meldungMeta.value = {}
    bearbeiten.value = false
    status.value = r.data.status
    promptOffen.value = false
    prompt.value = ''
    await ladeVerlauf()
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Antwort konnte nicht übernommen werden'
  } finally { laedt.value = false }
}

async function oeffne(id: number) {
  try {
    const r = await apiClient.get(
      `/compliance-audit/${encodeURIComponent(props.projekt)}/wasserstand/${id}`)
    meldung.value = r.data.ki
    meldungId.value = r.data.id ?? id
    meldungMeta.value = { bearbeitet_von: r.data.bearbeitet_von,
                          bearbeitet_am: r.data.bearbeitet_am }
    bearbeiten.value = false
    status.value = r.data.status
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Meldung konnte nicht geladen werden'
  }
}


onMounted(() => { ladeStatus(); ladeVerlauf() })
watch(() => props.projekt, () => {
  status.value = null; meldung.value = null; prompt.value = ''; promptOffen.value = false
  meldungId.value = null; meldungMeta.value = {}; bearbeiten.value = false
  ladeStatus(); ladeVerlauf()
})
</script>

<style scoped>
.wasserstand { display: flex; flex-direction: column; gap: 1.25rem; }
.intro h3 { margin: 0 0 .25rem; }
.intro p { margin: 0; color: #546e7a; font-size: .9rem; }

.stand-card { border: 1px solid #cfd8dc; border-left-width: 6px; border-radius: 8px; padding: 1rem; background: #fff; }
.stand-card.stufe-vollstaendig { border-left-color: #2e7d32; }
.stand-card.stufe-weitgehend  { border-left-color: #f9a825; }
.stand-card.stufe-teilweise   { border-left-color: #ef6c00; }
.stand-card.stufe-nicht       { border-left-color: #c62828; }
.stand-card.stufe-unbewertet  { border-left-color: #90a4ae; }

.stand-kopf { display: flex; align-items: center; gap: 1rem; }
.ampel { font-size: 2.25rem; line-height: 1; }
.stufe-label { font-size: 1.15rem; font-weight: 600; }
.stufe-bedeutung { color: #546e7a; font-size: .88rem; }
.quote { margin-left: auto; text-align: right; }
.quote strong { display: block; font-size: 1.6rem; }
.quote span { font-size: .75rem; color: #78909c; }

.kennzahlen { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .85rem; font-size: .82rem; }
.kennzahlen span { background: #eceff1; border-radius: 12px; padding: .15rem .6rem; }
.k-ok { background: #e8f5e9 !important; } .k-teil { background: #fff8e1 !important; }
.k-nein { background: #ffebee !important; } .k-offen { background: #e3f2fd !important; }
.k-na { background: #f5f5f5 !important; color: #78909c; }

.hinweis { margin: .75rem 0 0; font-size: .85rem; background: #fff8e1; border-radius: 6px; padding: .5rem .75rem; }

.fw-tabelle, .verlauf table, .massnahmen table { width: 100%; border-collapse: collapse; margin-top: .85rem; font-size: .86rem; }
.fw-tabelle th, .fw-tabelle td, .verlauf th, .verlauf td, .massnahmen th, .massnahmen td {
  text-align: left; padding: .4rem .5rem; border-bottom: 1px solid #eceff1;
}
.pille { border-radius: 10px; padding: .1rem .5rem; font-size: .78rem; background: #eceff1; }
.pille.stufe-vollstaendig { background: #e8f5e9; color: #2e7d32; }
.pille.stufe-weitgehend { background: #fff8e1; color: #f57f17; }
.pille.stufe-teilweise { background: #fff3e0; color: #ef6c00; }
.pille.stufe-nicht { background: #ffebee; color: #c62828; }

.aktionen { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1rem; }

.meldung-card, .verlauf { border: 1px solid #cfd8dc; border-radius: 8px; padding: 1rem; background: #fff; }

.kundentext { background: #f1f8e9; border-radius: 6px; padding: .75rem; }
.fw-block { margin-top: 1rem; border-top: 1px solid #eceff1; padding-top: .75rem; }
.fw-block h5 { margin: 0 0 .35rem; }
.prio { border-radius: 10px; padding: .1rem .5rem; font-size: .78rem; }
.prio-hoch { background: #ffebee; color: #c62828; }
.prio-mittel { background: #fff8e1; color: #f57f17; }
.prio-niedrig { background: #e8f5e9; color: #2e7d32; }
.fazit { margin-top: 1rem; }
.lade { color: #78909c; }
.btn-mini { font-size: .78rem; padding: .15rem .5rem; }
/* #1783: Überarbeiten + Darstellung des formulierten Texts */
.m-kopf { display: flex; align-items: center; gap: 1rem; }
.m-kopf h4 { margin: 0; flex: 1; }
.m-aktionen { display: flex; gap: .5rem; flex-wrap: wrap; }
.m-herkunft { font-size: .8rem; color: #607d8b; margin: .4rem 0 .6rem; }
.m-liste { margin: .5rem 0 0; padding-left: 1.2rem; }
.m-liste li { margin-bottom: .7rem; }
.m-zeile { display: flex; flex-wrap: wrap; align-items: baseline; gap: .5rem; }
.m-titel { flex: 1 1 18rem; }
.aufwand { font-size: .75rem; color: #546e7a; }
.m-grund { font-size: .86rem; color: #37474f; margin-top: .2rem; }
.feld { display: block; margin: .6rem 0; font-size: .82rem; color: #37474f; font-weight: 600; }
.feld textarea { display: block; width: 100%; box-sizing: border-box; margin-top: .25rem;
  font: inherit; font-weight: 400; font-size: .9rem; padding: .5rem;
  border: 1px solid #cfd8dc; border-radius: 6px; resize: vertical; }
.hinweis-klein { font-size: .75rem; color: #78909c; font-weight: 400; }
.m-edit { border: 1px solid #eceff1; border-radius: 6px; padding: .5rem; margin-bottom: .5rem; }
.m-edit-kopf { display: flex; gap: .4rem; flex-wrap: wrap; align-items: center; }
.m-edit-kopf input { flex: 1 1 16rem; padding: .35rem .5rem; border: 1px solid #cfd8dc;
  border-radius: 6px; font: inherit; }
.m-edit-kopf select { padding: .35rem; border: 1px solid #cfd8dc; border-radius: 6px; }
.m-edit textarea { width: 100%; box-sizing: border-box; margin-top: .4rem; font: inherit;
  font-size: .86rem; padding: .4rem; border: 1px solid #cfd8dc; border-radius: 6px;
  resize: vertical; }
.btn-mini { background: none; border: none; cursor: pointer; font-size: 1rem; }
</style>
