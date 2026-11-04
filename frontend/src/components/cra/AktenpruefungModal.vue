<!--
  „Akte prüfen lassen" (#1864/B) — auf Knopfdruck.

  Das Gate rechnet, ob die Akte **vollständig** ist. Was es nicht kann, ist die
  Frage, die eine Marktüberwachungsbehörde zuerst stellt: Hält diese Aussage
  der ersten Rückfrage stand? Dieser Lauf liest die Akte als Ganzes und nennt,
  was auffällt — vor der Freigabe statt in der Rückfrage danach.

  KEIN ZWEITES URTEIL
  Keine Ampel, keine Zahl, kein Konformitätsstand. Zwei Urteile über dieselbe
  Akte wären zwei Wahrheiten (#1726/#1727/#1776); der Server verwirft solche
  Felder, auch wenn das Modell sie liefert. Hier steht nur, was ein Prüfer
  fragen würde.
-->
<template>
  <ModalRahmen titel="🔎 Akte prüfen lassen" breite="breit"
               :hintergrund-schliesst="false" @close="$emit('close')">
    <template #inhalt>
      <FehlerHinweis :text="fehler" @close="fehler = ''" />

      <p class="hint">
        Die KI liest die Akte — gerechnete offene Punkte, Anhang-VII-Belege,
        Sicherheitstests, Bewertungsweg — und nennt, was der ersten Rückfrage
        nicht standhält. <strong>Es entsteht kein Urteil über die
        Konformität</strong>; das rechnet die Anwendung.
      </p>

      <DataPreviewWarning v-if="!laeuft && !fertig" :fields="vorschauFelder"
                          :provider="provider" @confirm="lauf" />

      <p v-if="laeuft" class="laeuft">⏳ Die Akte wird gelesen …</p>

      <template v-if="fertig">
        <p v-if="!befunde.length" class="ok">
          Keine Befunde. Das ist <em>keine</em> Konformitätsaussage — nur, dass
          in der vorgelegten Akte keine Widersprüche und keine offensichtlich
          dünnen Belege aufgefallen sind.
        </p>
        <table v-else class="ap-table">
          <thead>
            <tr><th>Schwere</th><th>Stelle</th><th>Befund</th><th>Rückfrage eines Prüfers</th></tr>
          </thead>
          <tbody>
            <tr v-for="(b, i) in befunde" :key="i">
              <td :class="['schwere', b.schwere]">{{ SCHWERE[b.schwere] || b.schwere }}</td>
              <td class="stelle">{{ b.stelle || '—' }}</td>
              <td>
                {{ b.befund }}
                <em class="art">{{ ART[b.art] || b.art }}</em>
              </td>
              <td class="frage">{{ b.rueckfrage || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p class="muted" v-if="letzterProvider">
          {{ letzterProvider === 'cloud' ? '☁️ Cloud' : letzterProvider === 'copy-paste' ? '📋 Eingefügt' : '🖥️ Lokal' }}
          · 🤖 KI-Entwurf, fachlich zu prüfen
        </p>
      </template>

      <details class="cp">
        <summary>Prompt kopieren und Antwort einfügen</summary>
        <div class="cp-body">
          <PromptAustausch v-model="antwort" :prompt="prompt" :busy="laeuft"
                           :prompt-zeilen="7" :antwort-zeilen="5"
                           prompt-platzhalter="Noch nicht erzeugt — „Prompt erzeugen“ klicken."
                           platzhalter='{"befunde": [ … ]}'
                           >
            <!-- Das Klemmbrett gehört dem Kopieren. Dieser Knopf **holt** den
                 Prompt vom Server; er hieß „📋 Prompt erzeugen" und versprach
                 damit genau das, was die Maske nicht konnte (#1867). -->
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

const props = defineProps<{ projekt: string; version?: string }>()
defineEmits<{ close: [] }>()

interface Befund {
  art: string
  stelle: string
  befund: string
  rueckfrage: string
  schwere: string
}

const SCHWERE: Record<string, string> = { hoch: '🔴 hoch', mittel: '🟠 mittel', niedrig: '🟡 niedrig' }
const ART: Record<string, string> = {
  widerspruch: 'Widerspruch in der Akte',
  belegtiefe: 'Beleg trägt die Aussage nicht',
  luecke: 'Lücke mit Folge für eine Pflicht',
}

const basis = computed(() =>
  `/cra-konformitaet/projekte/${encodeURIComponent(props.projekt)}/aktenpruefung`)

const laeuft = ref(false)
const fertig = ref(false)
const fehler = ref('')
const befunde = ref<Befund[]>([])
const provider = ref<'on_prem' | 'cloud'>('on_prem')
const letzterProvider = ref('')
const prompt = ref('')
const antwort = ref('')

const vorschauFelder = computed(() => [
  { label: 'Produkt', value: props.projekt },
  { label: 'Release', value: props.version || '(Produktstand)' },
  { label: 'Inhalt', value: 'Offene Punkte, Anhang-VII-Belege, Sicherheitstests, '
      + 'Bewertungsweg und Freigabestand dieser Akte' },
])

onMounted(async () => {
  try {
    const res = await apiClient.get('/ai/provider-status')
    provider.value = res.data?.provider === 'cloud' ? 'cloud' : 'on_prem'
  } catch { /* Default on_prem */ }
})

async function lauf() {
  laeuft.value = true; fehler.value = ''; fertig.value = false
  try {
    const res = await apiClient.post(basis.value,
                                     { version: props.version || '', confirmed: true })
    befunde.value = res.data?.befunde || []
    letzterProvider.value = res.data?.provider || ''
    fertig.value = true
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Die Aktenprüfung ist fehlgeschlagen.'
  } finally { laeuft.value = false }
}

async function promptHolen() {
  fehler.value = ''
  try {
    const res = await apiClient.get(`${basis.value}/prompt`,
                                    { params: { version: props.version || '' } })
    prompt.value = res.data?.prompt || ''
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Prompt konnte nicht erzeugt werden.'
  }
}

async function antwortUebernehmen() {
  laeuft.value = true; fehler.value = ''
  try {
    const res = await apiClient.post(`${basis.value}/import`, { response: antwort.value })
    befunde.value = res.data?.befunde || []
    letzterProvider.value = 'copy-paste'
    fertig.value = true
    antwort.value = ''
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Die Antwort war nicht verwertbar.'
  } finally { laeuft.value = false }
}
</script>

<style scoped>
.hint { color: #546e7a; font-size: 13px; margin: 0; }
.muted { color: #90a4ae; font-size: 12px; margin: 0; }
.laeuft { background: #e3f2fd; border-radius: 6px; padding: 8px 10px;
  font-size: 13px; color: #1565c0; margin: 0; }
.ok { background: #e8f5e9; border: 1px solid #a5d6a7; border-radius: 6px;
  padding: 8px 10px; font-size: 13px; color: #2e7d32; margin: 0; }
.ap-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.ap-table th { text-align: left; font-size: 12px; color: #546e7a;
  border-bottom: 1px solid #e0e0e0; padding: 4px 6px; }
.ap-table td { padding: 6px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
.schwere { white-space: nowrap; font-weight: 600; }
.schwere.hoch { color: #c62828; } .schwere.mittel { color: #ef6c00; } .schwere.niedrig { color: #f9a825; }
.stelle { color: #455a64; }
.art { display: block; font-style: normal; font-size: 11px; color: #90a4ae; margin-top: 2px; }
.frage { color: #37474f; font-style: italic; }
.cp { font-size: 13px; }
.cp summary { cursor: pointer; color: #1565c0; }
.cp-body { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
.btn-mini { padding: 3px 9px; font-size: 12px; border: 1px solid #b0bec5;
  border-radius: 6px; background: #fff; cursor: pointer; }
.btn-secondary { padding: 6px 14px; border: 1px solid #b0bec5; border-radius: 6px;
  background: #fff; cursor: pointer; font-size: 13px; }
</style>
