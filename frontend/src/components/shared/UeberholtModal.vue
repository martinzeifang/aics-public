<!--
  „Was ist überholt?" (#1864/A) — gerechnet, kein KI-Lauf.

  Eine Bewertung ist eine Aussage über einen Zeitpunkt. Danach kommen ein neuer
  Nachweis, eine neue SBOM, ein Pentest-Bericht — und die Aussage gilt weiter,
  ohne dass irgendwo steht, dass sie alt ist. Diese Liste sagt es.

  WAS SIE NICHT TUT
  Sie bewertet nichts neu. Der Weg zur Massenbewertung steht daneben, als
  **Angebot**: Ein automatisches Nachziehen wäre eine Bewertung, die niemand
  bestellt hat.
-->
<template>
  <ModalRahmen :titel="A.ueberholt.text" breite="breit" @close="$emit('close')">
    <template #inhalt>
      <FehlerHinweis :text="fehler" @close="fehler = ''" />

      <p class="hint">
        Verglichen wird der Stand jeder Bewertung mit den Ereignissen danach.
        <strong>Es wird nichts neu bewertet</strong> — die Liste ist ein
        Vorschlag.
      </p>

      <p v-if="laedt" class="muted">⏳ Wird gerechnet …</p>

      <template v-else>
        <div v-if="anlass" class="anlass">
          Jüngstes Ereignis: <strong>{{ anlass }}</strong>
          <em v-if="anlassAm">({{ datum(anlassAm) }})</em>
        </div>

        <!-- #1870: Drei Fälle, drei Sätze. Vorher stand hier einer, und er
             behauptete das Ergebnis eines Vergleichs, der nicht stattgefunden
             hatte — „keine Ereignisse" ist nicht „nichts überholt". -->
        <p v-if="!items.length && !bewertungen" class="muted">
          In diesem Projekt ist noch nichts bewertet — dann gibt es auch nichts
          zu vergleichen.
        </p>
        <p v-else-if="!items.length && !anlaesse" class="muted">
          In der Akte dieses Projekts steht bisher kein Ereignis, das eine
          Bewertung überholen könnte (neuer Nachweis, Pentest-Bericht, neue
          SBOM, Schwachstellen-Abgleich …). Verglichen wurde gegen
          <strong>{{ bewertungen }}</strong>
          {{ bewertungen === 1 ? 'Bewertung' : 'Bewertungen' }}.
        </p>
        <p v-else-if="!items.length" class="muted">
          Keine der <strong>{{ bewertungen }}</strong>
          {{ bewertungen === 1 ? 'Bewertung' : 'Bewertungen' }} ist älter als
          ein Ereignis in dieser Akte.
        </p>

        <table v-else class="ub-table">
          <thead>
            <tr><th>Objekt</th><th>Bewertet am</th><th>Anlass</th></tr>
          </thead>
          <tbody>
            <tr v-for="u in items" :key="u.objekt_art + u.objekt_id">
              <td class="code">
                {{ u.objekt_id }}
                <!-- #1864/A: Die Liste sieht alle Bewertungen, nicht nur die
                     KI-generierten. Woher sie stammt, ändert den Umgang. -->
                <em v-if="u.geprueft" class="gep" title="Von einem Menschen geprüft — die Prüfung galt für den alten Stand">✓ geprüft</em>
                <em v-else-if="!u.ki" class="hand" title="Von Hand bewertet, ohne KI">✍️ von Hand</em>
              </td>
              <td class="dat">{{ datum(u.bewertet_am) }}</td>
              <td>{{ u.anlass }} <em class="dat">({{ datum(u.anlass_am) }})</em></td>
            </tr>
          </tbody>
        </table>

        <p v-if="!vollstaendig" class="warn">
          Ein Teil der Daten war nicht lesbar — die Liste kann unvollständig
          sein.
        </p>
      </template>
    </template>

    <template #fuss>
      <button v-if="items.length" class="btn-primary" @click="$emit('massenlauf')">
        {{ A.massenAuto.text }} →
      </button>
      <button class="btn-secondary" @click="$emit('close')">Schließen</button>
    </template>
  </ModalRahmen>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import apiClient from '../../api/client'
import ModalRahmen from './ModalRahmen.vue'
import FehlerHinweis from './FehlerHinweis.vue'
import { PROJEKT_AKTIONEN as A } from '../../utils/aktionen'

const props = defineProps<{ apiBase: string; projektName: string }>()
// Kein `oeffne`-Event: Es hatte keinen Zuhörer, und der Wächter aus #1805 hat
// das zu Recht gemeldet. Ein Sprung zum Objekt müsste durch sechs Modul-Views
// verdrahtet werden und würde dabei das Modal schließen — also die Liste
// verlieren, die der Anwender gerade abarbeitet.
defineEmits<{ close: []; massenlauf: [] }>()

interface Ueberholt {
  objekt_art: string
  objekt_id: string
  bewertet_am: string
  anlass: string
  anlass_am: string
  geprueft: boolean
  /** Stammt die Bewertung (auch) aus einer KI? */
  ki: boolean
}

const laedt = ref(true)
const fehler = ref('')
const items = ref<Ueberholt[]>([])
const anlass = ref('')
const anlassAm = ref('')
const bewertungen = ref(0)
const anlaesse = ref(0)
const vollstaendig = ref(true)

function datum(s: string): string {
  if (!s) return '—'
  try { return new Date(s).toLocaleString('de-DE') } catch { return s }
}

onMounted(async () => {
  try {
    const res = await apiClient.get(
      `${props.apiBase}/projekte/${encodeURIComponent(props.projektName)}/ueberholt`)
    items.value = res.data?.items || []
    anlass.value = res.data?.anlass || ''
    anlassAm.value = res.data?.anlass_am || ''
    bewertungen.value = Number(res.data?.bewertungen || 0)
    anlaesse.value = Number(res.data?.anlaesse || 0)
    vollstaendig.value = res.data?.vollstaendig !== false
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Die Liste konnte nicht geladen werden.'
  } finally {
    laedt.value = false
  }
})
</script>

<style scoped>
.hint { color: #546e7a; font-size: 13px; margin: 0; }
.muted { color: #90a4ae; font-size: 13px; margin: 0; }
.anlass { background: #f5faff; border: 1px solid #cfe3f7; border-radius: 6px;
  padding: 7px 10px; font-size: 13px; color: #37474f; }
.anlass em { font-style: normal; color: #78909c; font-size: 12px; margin-left: 6px; }
.warn { background: #fff8e1; border: 1px solid #ffe082; border-radius: 6px;
  padding: 7px 10px; font-size: 12px; color: #8d6e00; margin: 0; }
.ub-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.ub-table th { text-align: left; font-size: 12px; color: #546e7a;
  border-bottom: 1px solid #e0e0e0; padding: 4px 6px; }
.ub-table td { padding: 6px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
.code { font-family: monospace; font-weight: 600; color: #1565c0; white-space: nowrap; }
.hand { display: block; font-family: system-ui, sans-serif; font-style: normal;
  font-weight: 400; font-size: 11px; color: #78909c; }
.gep { display: block; font-family: system-ui, sans-serif; font-style: normal;
  font-weight: 400; font-size: 11px; color: #2e7d32; }
.dat { color: #78909c; font-size: 12px; white-space: nowrap; font-style: normal; }
.btn-primary { padding: 6px 14px; border: 1px solid #1565c0; border-radius: 6px;
  background: #1565c0; color: #fff; cursor: pointer; font-size: 13px; }
.btn-secondary { padding: 6px 14px; border: 1px solid #b0bec5; border-radius: 6px;
  background: #fff; cursor: pointer; font-size: 13px; }
</style>
