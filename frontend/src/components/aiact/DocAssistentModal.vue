<!--
  A8 — KI-Assistent für die EU-Konformitätserklärung der KI-VO (#1889).

  WARUM ES DIESE DATEI BRAUCHT
  Den Assistenten gab es (`wizards/eu-doc`), aber sein Ergebnis **erreichte das
  Formular nicht**: `parse_eu_doc_response` lieferte Prosa, der Endpunkt hängte
  sie an die Notizen der System-Doku, und die Anhang-V-Felder blieben leer. Ein
  Assistent, dessen Ergebnis nicht dort ankommt, wo die Angabe gebraucht wird,
  ist eine Sackgasse — dieselbe Form wie #1783.

  DIE GRENZE ZIEHT DER SERVER
  Übernommen werden nur die Felder, die `ai_act/doc_vorschlag.KI_FELDER`
  freigibt (Typ des KI-Systems, Zusatzangaben). Anbieter, Anschrift, eindeutige
  Kennung, Unterzeichner, Datum und die Angaben zur notifizierten Stelle sind
  gerechnet oder übernommen; ein Modell, das sie plausibel ausfüllt, erzeugt
  eine Falschaussage in einem Dokument, das zehn Jahre bereitzuhalten ist
  (Art. 47 Abs. 2). Was verworfen wurde, **sagt die Maske**.

  Der Prompt entsteht serverseitig (#1834) und trägt die erfassten Werte sowie
  den gerechneten Stand als Vorgabe. Transport über `WizardPromptModal`, damit
  Kopieren, Einfügen (#1867), eigene Hinweise (#1834) und der Direktlauf samt
  Egress-Bestätigung (#1519/#1840) hier genauso gelten wie überall.
-->
<template>
  <WizardPromptModal
    title="EU-Konformitätserklärung — Assistent (Art. 47 · Anhang V)"
    :prompt="prompt"
    schema-hint="Antwort als JSON; übernommen werden nur system_typ und zusatzangaben."
    zusatz-beispiel="z. B. „Adressat ist eine Marktüberwachungsbehörde — sachlich und knapp.“"
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
import { onMounted, ref } from 'vue'
import apiClient from '../../api/client'
import WizardPromptModal from '../shared/WizardPromptModal.vue'

const props = defineProps<{ projekt: string }>()
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

onMounted(async () => {
  try {
    const { data } = await apiClient.get(
      `/aiact/projekte/${encodeURIComponent(props.projekt)}/wizards/eu-doc/prompt`)
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
      `/aiact/projekte/${encodeURIComponent(props.projekt)}/wizards/eu-doc/parse`,
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
