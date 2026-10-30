<template>
  <span v-if="sichtbar" class="nb-wrap">
    <span class="nb-badge" :title="titel">⚠️ Neubewertung</span>
    <!-- #1868: „angesehen, passt weiterhin". Der Knopf erscheint nur, wenn
         der Aufrufer die Koordinaten mitgibt — ohne sie kann das Abzeichen
         nicht bestätigen und zeigt dann nur die Markierung. -->
    <button v-if="kannBestaetigen" type="button" class="nb-ok" :disabled="laeuft"
            :title="laeuft ? 'Wird bestätigt …'
                           : 'Angesehen, Bewertung gilt weiterhin — Markierung quittieren'"
            @click.stop="bestaetigen">
      {{ laeuft ? '…' : '✓ passt' }}
    </button>
    <span v-if="fehler" class="nb-fehler" :title="fehler">⚠</span>
  </span>
  <span v-else-if="bestaetigtSichtbar" class="nb-bestaetigt" :title="bestaetigtTitel">
    ✅ bestätigt
  </span>
</template>

<script setup lang="ts">
/**
 * „Neubewertung erforderlich" in Listen und Kacheln (#1850) — und seit #1868
 * der Weg wieder heraus.
 *
 * Die Markierung stand bisher nur im geöffneten Editor. Wer sie dort sieht,
 * hat das Objekt schon aufgeschlagen — gesucht wird sie aber in der Liste:
 * „Was hat sich getan, seit ich zuletzt hingesehen habe?" Deshalb dieselbe
 * Markierung an der Zeile, mit dem Anlass im Tooltip.
 *
 * WARUM DIESE KOMPONENTE JETZT SELBST RUFT
 * Sie war bewusst „dumm": nur Text lesen. Mit #1868 kommt eine Handlung
 * hinzu, und die Alternative wäre, den POST in allen **neun** Einbauorten zu
 * wiederholen. Das ist die Spiegel-Liste aus #1731/#1735 — beim zehnten fehlt
 * er, und es fällt niemandem auf, weil nichts fehlschlägt. Eine Stelle, ein
 * Verhalten; `tests/test_neubewertung_bestaetigen_1868.py` hält beides fest.
 *
 * Was sie weiter **nicht** weiß: ob der Marker vom Issue-Abgleich oder von
 * einem Pentest-Befund stammt (#1584). Das steht im Text und nicht in einer
 * Prop — und der Server entscheidet, ob bestätigt werden darf (409, wenn
 * keine Markierung vorliegt).
 */
import { computed, ref } from 'vue'
import apiClient from '../../api/client'
import {
  bestaetigungTitel, hatNeubewertung, istBestaetigt, neubewertungTitel,
} from '../../utils/neubewertung'

const props = defineProps<{
  /** Der Freitext des Objekts (Kommentar, Notiz, Bemerkung, Triage). */
  text?: unknown
  /** Weiterer Text, der die Markierung tragen kann. */
  text2?: unknown
  // ── Koordinaten für das Bestätigen (#1868) ──────────────────────────────
  // Alle vier oder keines. Fehlt eines, erscheint kein Knopf — ein Knopf,
  // der ins Leere ruft, wäre schlimmer als keiner (#1805/#1830).
  /** Modul-Prefix der API, z. B. `cra` · `aiact` · `risikobewertung`. */
  modul?: string
  /**
   * Projektname (unkodiert). `null` ist der echte Zustand der Stores, solange
   * kein Projekt gewählt ist — dann erscheint kein Knopf (`kannBestaetigen`).
   */
  projekt?: string | null
  /** URL-Segment der Objektart, z. B. `anforderungen` · `owasp-llm`. */
  objektPfad?: string
  /** ID des Objekts. */
  objektId?: string | number
  /** Die Bestätigung auch dann zeigen, wenn keine Markierung (mehr) steht. */
  zeigeBestaetigung?: boolean
}>()

const emit = defineEmits<{
  /** Bestätigt — der Aufrufer lädt seinen Bestand nach. */
  bestaetigt: [nutzlast: { text: string; von: string; am: string }]
}>()

const laeuft = ref(false)
const fehler = ref('')
const erledigt = ref(false)

const sichtbar = computed(
  () => !erledigt.value && hatNeubewertung(props.text, props.text2))
const titel = computed(() => neubewertungTitel(props.text, props.text2))

const bestaetigtSichtbar = computed(
  () => (props.zeigeBestaetigung ?? false)
    && (erledigt.value || istBestaetigt(props.text, props.text2)))
const bestaetigtTitel = computed(
  () => bestaetigungTitel(props.text, props.text2) || 'Angesehen und bestätigt')

const kannBestaetigen = computed(() =>
  !!props.modul && !!props.projekt && !!props.objektPfad
  && props.objektId !== undefined && props.objektId !== null
  && String(props.objektId) !== '')

async function bestaetigen() {
  if (!kannBestaetigen.value) return
  laeuft.value = true
  fehler.value = ''
  try {
    const url = `/${props.modul}/projekte/${encodeURIComponent(String(props.projekt))}`
      + `/${props.objektPfad}/${encodeURIComponent(String(props.objektId))}`
      + '/neubewertung/bestaetigen'
    const res = await apiClient.post(url, {})
    // Der Server liefert eine Obermenge der Freitext-Schlüssel (#1830).
    const text = String(res.data?.kommentar ?? res.data?.notiz
                        ?? res.data?.bewertung_text ?? '')
    erledigt.value = true
    emit('bestaetigt', { text, von: String(res.data?.von ?? ''),
                         am: String(res.data?.am ?? '') })
  } catch (e: any) {
    fehler.value = e?.response?.data?.error
      || 'Die Bestätigung ist fehlgeschlagen.'
  } finally {
    laeuft.value = false
  }
}
</script>

<style scoped>
.nb-wrap { display: inline-flex; align-items: center; gap: 4px; margin-left: 6px; }
.nb-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 10px;
  /* Gleiche Farben wie der Badge im Editor (RequirementActions) — es ist
     dieselbe Aussage und soll nicht nach zwei verschiedenen aussehen. */
  background: #fff3e0;
  color: #b26a00;
  font-size: 0.72rem;
  font-weight: 600;
  white-space: nowrap;
  cursor: help;
}
.nb-ok {
  padding: 1px 7px;
  border: 1px solid #a5d6a7;
  border-radius: 10px;
  background: #fff;
  color: #2e7d32;
  font-size: 0.72rem;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
}
.nb-ok:hover:not(:disabled) { background: #e8f5e9; }
.nb-ok:disabled { opacity: .6; cursor: default; }
.nb-fehler { color: #c62828; font-size: 0.78rem; cursor: help; }
.nb-bestaetigt {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 10px;
  background: #e8f5e9;
  color: #2e7d32;
  font-size: 0.72rem;
  font-weight: 600;
  white-space: nowrap;
  cursor: help;
}
</style>
