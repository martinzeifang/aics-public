<!--
  KI-Assistent für die EU-Konformitätserklärung (#1887).

  WARUM ES DIESE DATEI BRAUCHT
  Den Assistenten gab es (`wizards/eu-doc`), aber sein Ergebnis **erreichte das
  Formular nicht**: `eu_doc_parse` lieferte Prosa, das Frontend speicherte sie
  als Dokument, und die Anhang-V-Felder blieben leer. Ein Assistent, dessen
  Ergebnis nicht dort ankommt, wo die Angabe gebraucht wird, ist eine
  Sackgasse — dieselbe Form wie #1783 („fachlich zu prüfen" ohne einen Weg, es
  zu tun).

  DIE GRENZE ZIEHT DER SERVER
  Übernommen werden nur die Felder, die `doc_vorschlag.KI_FELDER` freigibt
  (Produkttyp, Zusatzangaben, Gegenstand). Version, Hersteller, Anschrift,
  Unterzeichner, Datum und Digest sind gerechnet oder übernommen; ein Modell,
  das „Release 8.0.11" plausibel findet, erzeugt sonst genau den Fall aus
  #1885. Was verworfen wurde, **sagt die Maske** — ein stilles Weglassen sähe
  aus, als hätte das Modell die Angabe nicht geliefert.

  Der Prompt wird serverseitig gebaut (#1834) und trägt den gerechneten Stand
  als Vorgabe. Transport über `WizardPromptModal`, damit Kopieren, Einfügen
  (#1867), eigene Hinweise (#1834) und der Direktlauf samt
  Egress-Bestätigung (#1519/#1840) hier genauso gelten wie überall.
-->
<template>
  <WizardPromptModal
    :title="`EU-Konformitätserklärung — Assistent${release ? ' (Release ' + release + ')' : ''}`"
    :prompt="prompt"
    schema-hint="Antwort als JSON; übernommen werden nur produkt_typ, zusatzangaben und gegenstand."
    zusatz-beispiel="z. B. „Adressat ist eine Behörde — sachlich und knapp formulieren.“"
    :erledigt="fertig"
    @apply="anwenden"
    @close="emit('close')">
    <template #after>
      <div v-if="verworfen.length" class="verworfen">
        ⚠ Nicht übernommen, weil diese Angaben aus der Akte stammen:
        {{ verworfen.join(', ') }}
      </div>
      <div v-if="hinweise.length" class="hinweise">
        <ul><li v-for="(h, i) in hinweise" :key="i">{{ h }}</li></ul>
      </div>
      <div v-if="uebernommen.length" class="ok">
        ✓ In das Formular übernommen: {{ uebernommen.join(', ') }}
      </div>
    </template>
  </WizardPromptModal>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import apiClient from '../../api/client'
import WizardPromptModal from '../shared/WizardPromptModal.vue'

const props = defineProps<{ projekt: string; release?: string }>()
const emit = defineEmits<{
  (e: 'uebernehmen', felder: Record<string, string>): void
  (e: 'close'): void
}>()

const prompt = ref('')
const verworfen = ref<string[]>([])
const hinweise = ref<string[]>([])
const uebernommen = ref<string[]>([])
/** #1899: Übernahme durch, es gibt aber noch etwas zu lesen. */
const fertig = ref(false)

const release = props.release || ''

onMounted(async () => {
  try {
    const { data } = await apiClient.get(
      `/cra/projekte/${encodeURIComponent(props.projekt)}/wizards/eu-doc/prompt`,
      { params: { release } })
    prompt.value = data?.prompt || ''
  } catch {
    // Der Fehlertext lebt außerhalb des Streams (#1839); ein leerer Prompt
    // wird vom Modal selbst gemeldet, statt leer zu öffnen.
    prompt.value = ''
  }
})

async function anwenden(rawText: string) {
  verworfen.value = []; hinweise.value = []; uebernommen.value = []
  try {
    const { data } = await apiClient.post(
      `/cra/projekte/${encodeURIComponent(props.projekt)}/wizards/eu-doc/parse`,
      { response: rawText })
    const felder = (data?.felder || {}) as Record<string, string>
    verworfen.value = data?.verworfen || []
    hinweise.value = data?.plausibilitaet_hinweise || []
    uebernommen.value = Object.keys(felder)
    if (uebernommen.value.length) emit('uebernehmen', felder)
    // #1899: Gibt es nichts zu lesen, ist der Assistent fertig und das
    // Fenster geht zu — ein Dialog, der nach erledigter Arbeit stehen bleibt,
    // sieht aus wie einer, der hängt. Gibt es etwas zu lesen (verworfene
    // Angaben, Hinweise), bleibt er offen: Das sichtbar zu machen ist der
    // Zweck dieser Anzeige (#1887), und ein sofortiges Schließen nähme
    // genau die Zusage zurück, dass nichts stillschweigend verschwindet.
    if (!verworfen.value.length && !hinweise.value.length) {
      emit('close')
      return
    }
    fertig.value = true
  } catch (e: any) {
    hinweise.value = [e?.response?.data?.error || 'Antwort nicht verwertbar']
  }
}
</script>

<style scoped>
.verworfen { color: #ef6c00; font-size: 12px; margin: 6px 0; }
.hinweise { font-size: 12px; color: #455a64; }
.hinweise ul { margin: 4px 0 4px 18px; }
.ok { color: #2e7d32; font-size: 12px; margin: 6px 0; }
</style>
