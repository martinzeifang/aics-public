<!--
  Fortschritt eines langen projektweiten Laufs (#1944).

  DER BEFUND
  Beim Klick setzte die Werkzeugleiste `busy`, danach galt
  `:disabled="!!busy"` für alle sieben Knöpfe, und der geklickte tauschte seine
  Beschriftung auf eine statische Fassung („⏳ Übernehme…"). Mehr gab es nicht:
  keine Zahl, keine Dauer, kein Abbruch, kein Ergebnis. Bei einem Lauf von
  312 s (gemessen in #1940 über 77 Objekte) ist das von einem Hänger nicht zu
  unterscheiden — und in #1943 ist belegt, dass der Anwender daraufhin erneut
  klickt, zweimal, während beide Läufe serverseitig erfolgreich waren.

  DREI DINGE, DIE DIESE ANZEIGE LEISTET
  1. „läuft" von „hängt" unterscheidbar machen — Zahl und verstrichene Zeit.
  2. Einen **Abbruch als Entscheidung**. Vorher war der einzige Ausweg
     Neuladen, und das hinterließ einen Stand, von dem niemand wusste, wie
     weit er reicht. Ein Abbruch hier hinterlässt einen **bekannten** Stand.
  3. Das Ergebnis je Objekt. Die Sammel-Endpunkte antworten mit
     `imported`/`failed`/`items`; davon kam in der Oberfläche nichts an, auch
     bei vollständigem Durchlauf nicht.

  DIESE KOMPONENTE IST DUMM. Sie zeigt, was ihr gegeben wird, und meldet den
  Abbruchwunsch. Die Schleife liegt beim Aufrufer — er kennt die Routen, und
  nur er kann entscheiden, was ein Abbruch für seinen Vorgang bedeutet.
-->
<template>
  <ModalRahmen v-if="offen" :titel="titel" @close="emit('close')">
    <template #inhalt>
      <p v-if="warnung" class="lf-warnung">⚠️ {{ warnung }}</p>

      <div class="lf-balken" role="progressbar" :aria-valuenow="fertig"
           :aria-valuemin="0" :aria-valuemax="gesamt">
        <span :style="{ width: anteil + '%' }" />
      </div>
      <p class="lf-stand">
        <strong>{{ zustandstext }}</strong>
        <span v-if="gesamt" class="lf-zahl">{{ fertig }} von {{ gesamt }}</span>
        <span v-if="dauerText" class="lf-zahl">{{ dauerText }}</span>
      </p>

      <ul v-if="sichtbareZeilen.length" class="lf-zeilen">
        <li v-for="z in sichtbareZeilen" :key="z.art + z.id" :class="'z-' + z.zustand">
          <span class="lf-sym">{{ SYMBOL[z.zustand] }}</span>
          <span class="lf-titel">{{ z.titel || z.id }}</span>
          <span v-if="z.meldung" class="lf-meldung">{{ z.meldung }}</span>
        </li>
      </ul>
      <p v-if="verborgen > 0" class="lf-rest">
        … und {{ verborgen }} weitere ohne Befund
      </p>
    </template>
    <template #fuss>
      <button v-if="laeuft" class="btn-secondary" type="button"
              @click="emit('abbrechen')">⏹ Abbrechen</button>
      <button v-else class="btn-primary" type="button" @click="emit('close')">
        Schließen
      </button>
    </template>
  </ModalRahmen>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ModalRahmen from './ModalRahmen.vue'

export type LaufZustand = 'offen' | 'laeuft' | 'ok' | 'fehler' | 'uebersprungen'

export interface LaufZeile {
  art: string
  id: string
  titel?: string
  zustand: LaufZustand
  meldung?: string
}

const props = withDefaults(defineProps<{
  offen: boolean
  titel: string
  zeilen: LaufZeile[]
  laeuft: boolean
  abgebrochen?: boolean
  /** Sekunden seit Beginn — der Aufrufer zählt, damit hier kein Timer läuft. */
  dauer?: number
  /** Vor dem Start zu lesen, etwa bei Nebenwirkungen in fremden Systemen. */
  warnung?: string
}>(), { abgebrochen: false, dauer: 0, warnung: '' })

const emit = defineEmits<{ (e: 'abbrechen'): void; (e: 'close'): void }>()

const SYMBOL: Record<LaufZustand, string> = {
  offen: '·', laeuft: '⏳', ok: '✓', fehler: '✕', uebersprungen: '—',
}

const gesamt = computed(() => props.zeilen.length)
const fertig = computed(() =>
  props.zeilen.filter(z => z.zustand !== 'offen' && z.zustand !== 'laeuft').length)
const anteil = computed(() =>
  gesamt.value ? Math.round((fertig.value / gesamt.value) * 100) : 0)

const zustandstext = computed(() => {
  if (props.laeuft) return '⏳ Läuft'
  if (props.abgebrochen) return '⏹ Abgebrochen'
  const fehler = props.zeilen.filter(z => z.zustand === 'fehler').length
  // Die Zahl der Fehlschläge steht **im Zustandstext**, nicht nur in der
  // Liste: Sie ist die Angabe, die in einer Nachweisakte zählt, und eine
  // Liste von 77 Zeilen liest niemand durch, um sie zu finden.
  return fehler ? `✓ Fertig — ${fehler} fehlgeschlagen` : '✓ Fertig'
})

const dauerText = computed(() => {
  const s = Math.round(props.dauer || 0)
  if (!s) return ''
  return s < 90 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`
})

/**
 * Nur Zeilen mit Befund und die gerade laufende. Bei 77 Objekten ist eine
 * vollständige Liste nicht lesbar, und das Wesentliche — was schiefging —
 * geht darin unter.
 */
const sichtbareZeilen = computed(() =>
  props.zeilen.filter(z => z.zustand === 'laeuft' || z.zustand === 'fehler'
                           || z.zustand === 'uebersprungen'))
const verborgen = computed(() => gesamt.value - sichtbareZeilen.value.length
                                 - (props.laeuft ? 0 : 0))
</script>

<style scoped>
.lf-warnung {
  margin: 0 0 12px; padding: 8px 10px; border-radius: 4px;
  background: #fff8e1; color: #6d4c00; font-size: 13px; line-height: 1.45;
}
.lf-balken {
  height: 8px; border-radius: 4px; background: #eceff1; overflow: hidden;
}
.lf-balken > span {
  display: block; height: 100%; background: #1565c0; transition: width .2s;
}
.lf-stand { margin: 8px 0 12px; font-size: 13px; display: flex; gap: 12px; }
.lf-zahl { color: #607d8b; }
.lf-zeilen { list-style: none; margin: 0; padding: 0; font-size: 12px; }
.lf-zeilen li {
  display: flex; gap: 8px; align-items: baseline;
  padding: 3px 0; border-bottom: 1px solid #f0f0f0;
}
.lf-sym { width: 1.2em; flex: none; }
.lf-titel { font-weight: 600; }
.lf-meldung { color: #b71c1c; }
.z-uebersprungen .lf-meldung { color: #607d8b; }
.lf-rest { margin: 8px 0 0; font-size: 12px; color: #607d8b; }
</style>
