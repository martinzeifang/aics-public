<!--
  ProjektWerkzeugleiste (#1851) — die sieben projektweiten Handlungen, in
  allen sechs Modulen gleich benannt, gleich angeordnet, gleich bedient.

  DER BEFUND
  Dieselbe Handlung trug drei Namen, und zwei Handlungen fehlten in fünf von
  sechs Modulen. Dazu lagen die Knöpfe an **zwei** Orten: die Issue-Aktionen in
  der Projekt-Leiste, die Massenbewertung in der Werkzeugleiste des
  Anforderungs-Tabs — und in der Risikobewertung alles im Tab. WiBA hatte
  „Issues anlegen" gar nicht, weil die **Route** fehlte (sie kommt jetzt aus
  der Fabrik), und das Audit-Log gab es nur in der Risikobewertung.

  WARUM ALLES IN DIE PROJEKT-LEISTE
  Alle sieben Handlungen gelten dem **Projekt**, nicht der Liste, die gerade
  offen ist. In der Leiste sind sie aus jedem Tab erreichbar; vorher lag das
  Audit-Log hinter dem Risiken-Tab und WiBAs Massenbewertung hinter dem
  Prüffragen-Tab. Die Massenbewertungs-Dialoge holen ihre Objekte selbst über
  den Adapter — sie hängen nicht an der sichtbaren Liste.

  CRAs Klappmenü entfällt (Vorgabe aus #1851). Es war das einzige im Haus,
  und es ließ sich weder mit Escape noch durch einen Klick daneben schließen.

  WAS NICHT HIERHER GEHÖRT
  Fachlich modul-eigene Knöpfe („➕ KI-System anlegen", „🔍 Repo-Scan",
  „🪄 Risiken-Assistent", „+ Custom", „🗑️ Projekt löschen"). Sie stehen im
  Slot `eigene`. Eine Leiste, die alles aufnimmt, ordnet nichts.
-->
<template>
  <div class="pw-leiste">
    <!-- Bewerten -->
    <button v-if="massAdapter && !nurLesend" class="pw-knopf" type="button"
            :disabled="!projektName || !!busy" :title="A.massenAuto.titel"
            @click="autoMassOffen = true">
      {{ A.massenAuto.text }}
    </button>
    <button v-if="massAdapter && mitSammelPrompt && !nurLesend" class="pw-knopf" type="button"
            :disabled="!projektName || !!busy" :title="A.massenPrompt.titel"
            @click="massOffen = true">
      {{ A.massenPrompt.text }}
    </button>

    <span v-if="massAdapter && !nurLesend" class="pw-trenner" aria-hidden="true"></span>

    <!-- Issues -->
    <button v-if="!nurLesend" class="pw-knopf" type="button"
            :disabled="!projektName || !!busy"
            :title="A.issuesAnlegen.titel" @click="stapelAnlegen">
      {{ knopf(A.issuesAnlegen, busy === 'stapel') }}
    </button>
    <button class="pw-knopf" type="button" :disabled="!projektName || !!busy"
            :title="A.statusAbgleichen.titel" @click="abgleichen">
      {{ knopf(A.statusAbgleichen, busy === 'abgleich') }}
    </button>
    <button v-if="!nurLesend" class="pw-knopf" type="button"
            :disabled="!projektName || !!busy"
            :title="A.feedbackUebernehmen.titel" @click="uebernehmen">
      {{ knopf(A.feedbackUebernehmen, busy === 'uebernahme') }}
    </button>
    <button class="pw-knopf" type="button" :disabled="!projektName || !!busy"
            :title="A.neubewertung.titel" @click="neubewertungOffen = true">
      {{ A.neubewertung.text }}
    </button>

    <span class="pw-trenner" aria-hidden="true"></span>

    <!-- Nachweis -->
    <button class="pw-knopf" type="button" :disabled="!projektName || !!busy"
            :title="A.auditLog.titel" @click="auditOffen = true">
      {{ A.auditLog.text }}
    </button>
    <!-- #1864/A: gerechnet, kein KI-Lauf — deshalb auch bei `nurLesend`
         erlaubt: Die Liste liest nur und bewertet nichts. -->
    <button class="pw-knopf" type="button" :disabled="!projektName || !!busy"
            :title="A.ueberholt.titel" @click="ueberholtOffen = true">
      {{ A.ueberholt.text }}
    </button>

    <!-- Modul-eigene Knöpfe -->
    <slot name="eigene" />
  </div>

  <FehlerHinweis :text="fehler" @close="fehler = ''" />
  <FehlerHinweis v-if="meldung" :text="meldung" art="erfolg" @close="meldung = ''" />

  <!-- #1573: die beiden geteilten Massenbewertungs-Dialoge -->
  <MassAssessmentModal v-if="massOffen && massAdapter && projektName"
                       :projekt-name="projektName" :adapter="massAdapter"
                       @close="massOffen = false" @applied="$emit('reload')" />
  <AutoMassBewertungModal v-if="autoMassOffen && massAdapter && projektName"
                          :projekt-name="projektName" :adapter="massAdapter"
                          @close="autoMassOffen = false" @done="$emit('reload')" />

  <IssueNeubewertungModal v-if="neubewertungOffen && projektName"
                          :api-base="apiBase" :projekt-name="projektName"
                          @close="neubewertungOffen = false" />
  <UeberholtModal v-if="ueberholtOffen && projektName"
                  :api-base="apiBase" :projekt-name="projektName"
                  @close="ueberholtOffen = false"
                  @massenlauf="ueberholtOffen = false; autoMassOffen = true" />
  <AuditLogModal v-if="auditOffen && projektName"
                 :api-base="apiBase" :projekt-name="projektName"
                 @close="auditOffen = false" />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import apiClient from '../../api/client'
import { PROJEKT_AKTIONEN as A, knopf } from '../../utils/aktionen'
import type { MassAdapter } from '../../utils/massAdapters'
import AuditLogModal from './AuditLogModal.vue'
import UeberholtModal from './UeberholtModal.vue'
import AutoMassBewertungModal from './AutoMassBewertungModal.vue'
import FehlerHinweis from './FehlerHinweis.vue'
import IssueNeubewertungModal from './IssueNeubewertungModal.vue'
import MassAssessmentModal from './MassAssessmentModal.vue'

const props = withDefaults(defineProps<{
  /** Modul-Prefix: `/cra`, `/nis2`, `/aiact`, `/dsgvo`, `/wiba`, `/risikobewertung`. */
  apiBase: string
  projektName: string
  /** Adapter der Massenbewertung; ohne ihn entfallen die beiden Knöpfe. */
  massAdapter?: MassAdapter | null
  /**
   * Hat das Modul einen Sammel-Prompt-Endpunkt? Für OWASP-Kontrollen gibt es
   * keinen, und ein sichtbarer Knopf ohne Route ist ein Defekt (#1846).
   */
  mitSammelPrompt?: boolean
  /** Wie die Objekte dieses Moduls heißen („Anforderungen", „Prüffragen"). */
  objektWort?: string
  /** Was der Abgleich **nicht** verändert („Bewertungen", „Antworten"). */
  wertWort?: string
  /**
   * Nur die lesenden Handlungen zeigen.
   *
   * Für eine AI-Act-Organisation mit mindestens einem KI-System sperrt
   * `make_org_write_guard` (#1562) die Register-Schreibwege mit 409
   * `org_controls_locked` — ausdrücklich **erlaubt** sind dort der
   * Issue-Abgleich und, weil der Guard GETs durchlässt, die
   * Neubewertungs-Übersicht und das Audit-Log. Die ganze Leiste
   * auszublenden wäre der bequeme Weg und nähme dem Anwender genau die drei
   * Handlungen, die er dort haben darf; vier sichtbare Knöpfe vor einem 409
   * wären die andere Hälfte desselben Fehlers (#1846).
   */
  nurLesend?: boolean
}>(), {
  massAdapter: null,
  mitSammelPrompt: true,
  objektWort: 'Objekte',
  wertWort: 'Bewertungen',
  nurLesend: false,
})

const emit = defineEmits<{
  /** Nach jeder Handlung, die Daten verändert hat. */
  reload: []
}>()

type Busy = '' | 'stapel' | 'abgleich' | 'uebernahme'
const busy = ref<Busy>('')
const fehler = ref('')
const meldung = ref('')

const massOffen = ref(false)
const autoMassOffen = ref(false)
const neubewertungOffen = ref(false)
const auditOffen = ref(false)
const ueberholtOffen = ref(false)

/**
 * Die beiden Massenbewertungen auch von außen öffnen.
 *
 * Der Framework-Wechsel der Risikobewertung (#1577) bietet sie als
 * Folgeschritt an („Felder zurückgesetzt — jetzt neu bewerten"). Ohne diesen
 * Weg bräuchte die View eine **zweite** Instanz derselben Dialoge, nur um
 * denselben Knopf zu haben — und zwei Instanzen eines Dialogs sind zwei
 * Zustände, die auseinanderlaufen können.
 */
defineExpose({
  oeffneMassenAuto: () => { autoMassOffen.value = true },
  oeffneMassenPrompt: () => { massOffen.value = true },
})

const basis = () => `${props.apiBase}/projekte/${encodeURIComponent(props.projektName)}`
const text = (e: any, ersatz: string) => e?.response?.data?.error || ersatz

/**
 * Meldungen stehen in `FehlerHinweis`, nicht in `alert()`.
 *
 * Der Bestand nutzte `alert()` — ein Fenster, das den Browser anhält und das
 * der Anwender wegklicken muss, bevor er das Ergebnis in der Liste ansehen
 * kann. Dazu waren die Texte je Modul verschieden formuliert, obwohl sie
 * dasselbe meldeten.
 */
const stapelAnlegen = async () => {
  if (!props.projektName) return
  if (!confirm(`Für die offenen Punkte dieses Projekts GitHub-/GitLab-Issues `
             + `anlegen?\n\nBereits verknüpfte ${props.objektWort} werden `
             + `übersprungen.`)) return
  busy.value = 'stapel'
  fehler.value = ''
  meldung.value = ''
  try {
    const res = await apiClient.post(`${basis()}/issues/bulk`, {}, { timeout: 180000 })
    const s = res.data?.summary || {}
    meldung.value = `Issues angelegt: ${s.created ?? 0} erstellt, `
      + `${s.skipped ?? 0} übersprungen, ${s.failed ?? 0} fehlgeschlagen.`
    const erster = (res.data?.failed || [])[0]
    if (erster?.error) meldung.value += ` Erster Fehler: ${erster.error}`
    emit('reload')
  } catch (e: any) {
    fehler.value = text(e, 'Die Stapel-Anlage ist fehlgeschlagen.')
  } finally {
    busy.value = ''
  }
}

const abgleichen = async () => {
  if (!props.projektName) return
  busy.value = 'abgleich'
  fehler.value = ''
  meldung.value = ''
  try {
    const res = await apiClient.post(`${basis()}/issues/sync`, {}, { timeout: 120000 })
    const d = res.data || {}
    meldung.value = `Issues abgeglichen: ${d.synced ?? 0} aktualisiert, `
      + `${d.errors ?? 0} Fehler (gesamt ${d.total ?? 0}); `
      + `${d.markiert ?? 0} Objekt(e) als „⚠️ Neubewertung erforderlich" markiert. `
      + `${props.wertWort} wurden NICHT verändert — ein geschlossenes Issue ist `
      + `kein Nachweis.`
    emit('reload')
  } catch (e: any) {
    fehler.value = text(e, 'Der Issue-Abgleich ist fehlgeschlagen.')
  } finally {
    busy.value = ''
  }
}

const uebernehmen = async () => {
  if (!props.projektName) return
  if (!confirm(`Inhalt und Kommentare aller verknüpften Issues in den Freitext `
             + `der jeweiligen ${props.objektWort} übernehmen?\n\n`
             + `${props.wertWort} bleiben unverändert; ein früher übernommener `
             + `Block wird ersetzt.`)) return
  busy.value = 'uebernahme'
  fehler.value = ''
  meldung.value = ''
  try {
    const res = await apiClient.post(`${basis()}/issues/import`, {}, { timeout: 180000 })
    const d = res.data || {}
    meldung.value = `Issue-Feedback übernommen: ${d.imported ?? 0} `
      + `${props.objektWort} aktualisiert, ${d.failed ?? 0} ohne Inhalt `
      + `(gesamt ${d.total ?? 0}).`
    emit('reload')
  } catch (e: any) {
    fehler.value = text(e, 'Die Übernahme des Issue-Feedbacks ist fehlgeschlagen.')
  } finally {
    busy.value = ''
  }
}
</script>

<style scoped>
.pw-leiste { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }

.pw-trenner {
  width: 1px; align-self: stretch; min-height: 20px;
  background: var(--color-border); margin: 0 2px;
}

.pw-knopf {
  background: white; border: 1px solid #b3d4f5; color: #1565c0;
  padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;
  white-space: nowrap;
}

.pw-knopf:hover:not(:disabled) { background: #1565c0; color: white; }
.pw-knopf:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
