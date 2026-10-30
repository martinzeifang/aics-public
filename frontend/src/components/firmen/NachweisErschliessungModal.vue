<!--
  Ein Kundendokument auf Anforderungen abbilden (#1861).

  DER AUFWAND, DEN DAS SPART
  Der größte Posten im Betrieb ist nicht das Bewerten, sondern das **Lesen der
  Kundenunterlagen**. Dieses Dialog macht daraus einen Knopfdruck: Ein Lauf je
  Dokument liefert Vorschläge der Form „Abschnitt 4.2 belegt CRA-C1-03", und
  der Mensch gibt frei. Ab dann wirkt der Beleg in **jeder** künftigen
  KI-Bewertung (#1483) — mit Fundstelle.

  HUMAN-IN-CONTROL
  Der Lauf speichert **keine** Bewertung und **keinen** Beleg. Er legt
  Vorschläge ab; erst die Freigabe schreibt nach `evidence_mappings_approved`.
  Deshalb gibt es hier kein „alles übernehmen" ohne Blick auf die Fundstelle:
  Was die Akte belegt, entscheidet kein Lauf.

  BEIDE WEGE
  „⚡ Direkt mit KI" und der Prompt zum Kopieren. Die Antwort aus einem
  Fremdsystem geht durch **dieselbe** Prüfung wie der Direktlauf — ein
  zweiter, laxerer Pfad wäre die Lücke, durch die ungeprüfte Belege in die
  Akte kommen.
-->
<template>
  <ModalRahmen :titel="`🔍 Nachweis erschließen — ${doc.filename}`" breite="breit"
               :hintergrund-schliesst="false" @close="$emit('close')">
    <template #inhalt>
      <FehlerHinweis :text="fehler" @close="fehler = ''" />

      <!-- Schritt 1: Katalog wählen -->
      <div class="zeile">
        <label>
          Katalog
          <select v-model="modul" :disabled="laeuft">
            <option v-for="m in MODULE" :key="m.wert" :value="m.wert">{{ m.label }}</option>
          </select>
        </label>
        <span class="hint">
          Ein Lauf vergleicht das Dokument mit genau einem Katalog — ein
          Sicherheitskonzept kann mehrere belegen, dann läuft es mehrmals.
        </span>
      </div>

      <!-- Die Abschnitte entstehen beim Lauf von selbst (kein KI-Lauf, kostet
           nichts). Deshalb steht hier keine Vorbedingung mehr, nur noch der
           Weg, sie **neu** zu erzeugen — etwa wenn die Datei ersetzt wurde. -->
      <p class="muted">
        <span v-if="abschnitte > 0">{{ abschnitte }} Abschnitte erschlossen.</span>
        <span v-else>Text und Abschnitte entstehen beim Lauf automatisch.</span>
        <button class="btn-mini" :disabled="laeuft" @click="textErschliessen">
          📄 Neu erschließen
        </button>
      </p>

      <!-- Daten-Vorschau + Egress: hier gehen Kundenunterlagen an den Provider -->
      <DataPreviewWarning v-if="!laeuft && !fertig"
                          :fields="vorschauFelder" :provider="provider"
                          @confirm="direktLauf" />

      <div v-if="laeuft" class="laeuft">⏳ {{ laufText }}</div>

      <!-- Ergebnis des Laufs -->
      <div v-if="fertig" class="ergebnis">
        <p>
          <strong>{{ vorschlaege.length }} Vorschläge</strong>
          <span v-if="letzterProvider"> · {{ letzterProvider === 'cloud' ? '☁️ Cloud' : '🖥️ Lokal' }}</span>
        </p>
        <!-- Verworfenes wird genannt, nicht verschwiegen: Wenn von 20
             Vorschlägen 18 wegfallen, muss das sichtbar sein — sonst sieht ein
             halb verstandenes Dokument wie ein mageres aus. -->
        <details v-if="verworfen.length" class="verworfen">
          <summary>{{ verworfen.length }} Vorschläge verworfen (nicht belegbar)</summary>
          <ul><li v-for="(v, i) in verworfen" :key="i">{{ v }}</li></ul>
        </details>
      </div>

      <!-- Vorschlagsliste -->
      <table v-if="vorschlaege.length" class="vor-table">
        <thead>
          <tr><th>Anforderung</th><th>Belegte Aussage</th><th>Fundstelle</th><th>Sicher</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="v in vorschlaege" :key="v.id">
            <td class="code">{{ v.requirement_id }}</td>
            <td>
              {{ v.claim }}
              <em v-if="v.rationale" class="begr">{{ v.rationale }}</em>
            </td>
            <td class="fund">
              <span v-for="c in v.citations" :key="c.chunk" class="chunk">
                Abschnitt {{ c.chunk }}
              </span>
            </td>
            <td :class="['konf', konfKlasse(v.confidence)]">
              {{ Math.round(v.confidence * 100) }} %
            </td>
            <td class="akt">
              <button class="btn-mini ok" :disabled="busy === v.id"
                      @click="freigeben(v)">✓ Freigeben</button>
              <button class="btn-mini" :disabled="busy === v.id"
                      @click="verwerfen(v)">✕</button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Copy/Paste-Weg -->
      <details class="cp">
        <summary>Prompt kopieren und Antwort einfügen</summary>
        <div class="cp-body">
          <PromptAustausch v-model="antwort" :prompt="prompt" :busy="laeuft"
                           :prompt-zeilen="6" :antwort-zeilen="5"
                           prompt-platzhalter="Noch nicht erzeugt — „Prompt erzeugen“ klicken."
                           platzhalter='{"vorschlaege": [ … ]}'
                           >
            <template #prompt-aktionen>
              <button type="button" class="btn-mini" :disabled="laeuft"
                      @click="promptHolen">⚙ Prompt erzeugen</button>
            </template>
            <template #fuss>
              <button type="button" class="btn-mini" :disabled="!antwort.trim() || laeuft"
                      @click="antwortUebernehmen">Antwort übernehmen</button>
            </template>
          </PromptAustausch>
        </div>
      </details>
    </template>

    <template #fuss>
      <button class="btn-secondary" @click="$emit('close')">Schließen</button>
    </template>
  </ModalRahmen>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import apiClient from '../../api/client'
import ModalRahmen from '../shared/ModalRahmen.vue'
import DataPreviewWarning from '../shared/DataPreviewWarning.vue'
import FehlerHinweis from '../shared/FehlerHinweis.vue'
import PromptAustausch from '../shared/PromptAustausch.vue'
import { useFirmenStore, type EvidenceVorschlag } from '../../stores/firmen'

const props = defineProps<{
  firmaName: string
  doc: { id: string; filename: string }
}>()
defineEmits<{ close: [] }>()

/** Die Kataloge, gegen die erschlossen werden kann (Server: erschliessung.MODULE). */
const MODULE = [
  { wert: 'cra', label: 'CRA — Anforderungen' },
  { wert: 'nis2', label: 'NIS2 — Anforderungen' },
  { wert: 'aiact', label: 'AI Act — Anforderungen' },
  { wert: 'dsgvo', label: 'DSGVO — Anforderungen' },
  { wert: 'wiba', label: 'WiBA — Prüffragen' },
]

const firmen = useFirmenStore()
const modul = ref('cra')
const abschnitte = ref(0)
const laeuft = ref(false)
const laufText = ref('')
const fertig = ref(false)
const fehler = ref('')
const vorschlaege = ref<EvidenceVorschlag[]>([])
const verworfen = ref<string[]>([])
const letzterProvider = ref('')
const provider = ref<'on_prem' | 'cloud'>('on_prem')
const busy = ref('')
const prompt = ref('')
const antwort = ref('')

const vorschauFelder = computed(() => [
  { label: 'Dokument', value: props.doc.filename },
  { label: 'Umfang', value: abschnitte.value > 0
      ? `${abschnitte.value} Abschnitte im Volltext`
      : 'der Volltext des Dokuments (wird beim Lauf erschlossen)' },
  { label: 'Katalog', value: MODULE.find(m => m.wert === modul.value)?.label || modul.value },
  { label: 'Inhalt', value: 'Der Text des Kundendokuments und die Anforderungs-Liste' },
])

function konfKlasse(c: number): string {
  return c >= 0.75 ? 'hoch' : c >= 0.5 ? 'mittel' : 'niedrig'
}

async function ladeStand() {
  try {
    const items = await firmen.fetchVorschlaege(props.firmaName, props.doc.id)
    vorschlaege.value = items.filter(v => v.modul === modul.value)
  } catch { /* leer ist ein zulässiger Zustand */ }
}

onMounted(async () => {
  try {
    const res = await apiClient.get('/ai/provider-status')
    provider.value = res.data?.provider === 'cloud' ? 'cloud' : 'on_prem'
  } catch { /* Default on_prem */ }
  await ladeStand()
})

async function textErschliessen() {
  laeuft.value = true; laufText.value = 'Text und Abschnitte werden erschlossen …'
  try {
    const res = await firmen.evidenceAbschnitte(props.firmaName, props.doc.id)
    abschnitte.value = Number(res?.abschnitte || 0)
    if (!abschnitte.value) {
      fehler.value = 'Aus diesem Dokument ließ sich kein Text lesen (Scan ohne '
        + 'Texterkennung oder leere Datei).'
    }
  } finally { laeuft.value = false }
}

async function direktLauf() {
  laeuft.value = true; fertig.value = false; fehler.value = ''
  laufText.value = `Dokument wird gegen den Katalog gelesen …`
  try {
    const res = await firmen.erschliessen(props.firmaName, props.doc.id, modul.value)
    verworfen.value = res.verworfen || []
    letzterProvider.value = res.provider || ''
    fertig.value = true
    await ladeStand()
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Der Erschließungslauf ist fehlgeschlagen.'
  } finally { laeuft.value = false }
}

async function promptHolen() {
  fehler.value = ''
  try {
    const res = await firmen.erschliessungPrompt(props.firmaName, props.doc.id, modul.value)
    prompt.value = res.prompt
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Prompt konnte nicht erzeugt werden.'
  }
}

async function antwortUebernehmen() {
  laeuft.value = true; fehler.value = ''
  laufText.value = 'Antwort wird geprüft …'
  try {
    const res = await firmen.erschliessungImport(props.firmaName, props.doc.id,
                                                 modul.value, antwort.value)
    verworfen.value = res.verworfen || []
    letzterProvider.value = 'copy-paste'
    fertig.value = true
    antwort.value = ''
    await ladeStand()
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Die Antwort war nicht verwertbar.'
  } finally { laeuft.value = false }
}

async function freigeben(v: EvidenceVorschlag) {
  busy.value = v.id
  try {
    await firmen.vorschlagFreigeben(props.firmaName, v.id)
    vorschlaege.value = vorschlaege.value.filter(x => x.id !== v.id)
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Freigabe fehlgeschlagen.'
  } finally { busy.value = '' }
}

async function verwerfen(v: EvidenceVorschlag) {
  busy.value = v.id
  try {
    await firmen.vorschlagVerwerfen(props.firmaName, v.id)
    vorschlaege.value = vorschlaege.value.filter(x => x.id !== v.id)
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Verwerfen fehlgeschlagen.'
  } finally { busy.value = '' }
}
</script>

<style scoped>
.zeile { display: flex; align-items: flex-start; gap: 14px; flex-wrap: wrap; }
.zeile label { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: #37474f; }
.zeile select { padding: 4px 8px; border: 1px solid #b0bec5; border-radius: 6px; font-size: 13px; }
.hint { flex: 1; min-width: 240px; font-size: 12px; color: #78909c; }
.warn { background: #fff8e1; border: 1px solid #ffe082; border-radius: 6px;
  padding: 8px 10px; font-size: 13px; color: #8d6e00; display: flex;
  align-items: center; gap: 10px; flex-wrap: wrap; }
.warn em { font-style: normal; color: #a1887f; font-size: 12px; }
.muted { color: #90a4ae; font-size: 12px; margin: 0; }
.laeuft { background: #e3f2fd; border-radius: 6px; padding: 8px 10px; font-size: 13px; color: #1565c0; }
.ergebnis p { margin: 0; font-size: 13px; color: #37474f; }
.verworfen { font-size: 12px; color: #78909c; margin-top: 4px; }
.verworfen ul { margin: 4px 0 0; padding-left: 18px; }
.vor-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.vor-table th { text-align: left; font-size: 12px; color: #546e7a;
  border-bottom: 1px solid #e0e0e0; padding: 4px 6px; }
.vor-table td { padding: 6px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
.code { font-family: monospace; font-weight: 600; color: #1565c0; white-space: nowrap; }
.begr { display: block; font-style: normal; font-size: 12px; color: #78909c; margin-top: 2px; }
.fund { white-space: nowrap; }
.chunk { display: inline-block; background: #eceff1; border-radius: 8px;
  padding: 1px 7px; font-size: 11px; margin-right: 4px; color: #455a64; }
.konf { font-weight: 600; white-space: nowrap; }
.konf.hoch { color: #2e7d32; } .konf.mittel { color: #ef6c00; } .konf.niedrig { color: #c62828; }
.akt { white-space: nowrap; }
.btn-mini { padding: 3px 9px; font-size: 12px; border: 1px solid #b0bec5;
  border-radius: 6px; background: #fff; cursor: pointer; }
.btn-mini:hover { background: #eceff1; }
.btn-mini.ok { border-color: #a5d6a7; color: #2e7d32; }
.cp { font-size: 13px; }
.cp summary { cursor: pointer; color: #1565c0; }
.cp-body { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
.btn-secondary { padding: 6px 14px; border: 1px solid #b0bec5; border-radius: 6px;
  background: #fff; cursor: pointer; font-size: 13px; }
</style>
