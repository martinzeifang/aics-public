<template>
  <!--
    #1765: Der Vorbehalt gehört in die Anwendung, nicht in das Dokument.
    Kein Eintrag → keine Zeile, kein leerer Platz.
  -->
  <div v-if="status" class="kih" :class="status.geprueft ? 'kih-ok' : 'kih-offen'">
    <template v-if="status.geprueft">
      <span class="kih-text">
        ✓ Fachlich geprüft<template v-if="status.geprueft_von"> von {{ status.geprueft_von }}</template>
        <template v-if="geprueftAm"> am {{ geprueftAm }}</template>
      </span>
    </template>
    <template v-else>
      <span class="kih-text">
        🤖 KI-Entwurf<template v-if="herkunft"> ({{ herkunft }})</template> — fachlich nicht geprüft
      </span>
      <button type="button" class="kih-btn" :disabled="busy" @click="bestaetigen">
        {{ busy ? '⏳ …' : '✓ Fachlich geprüft' }}
      </button>
    </template>
    <span v-if="fehler" class="kih-fehler">{{ fehler }}</span>
  </div>
</template>

<script setup lang="ts">
/**
 * Herkunfts- und Prüfhinweis für einen KI-erzeugten Inhalt (#1765).
 *
 * Gehört an das Bewertungs-/Kommentarfeld, auf das er sich bezieht — nicht in
 * die Kopfzeile. Zeigt nichts an, solange das Objekt keinen Registereintrag
 * hat (= der Inhalt kam nicht von einer KI).
 */
import { computed, ref, watch } from 'vue'
import { useKiHerkunftStore, type KiArt } from '../../stores/kiHerkunft'

const props = defineProps<{
  /** URL-Segment des Moduls: cra | nis2 | aiact | dsgvo | wiba | risikobewertung */
  modul: string
  /** Projektname (wird im Store URL-kodiert) */
  projekt: string | null
  /** Objektart im Register */
  art: KiArt
  /** Objekt-ID (Anforderung, Prüffrage, Risiko …) */
  objektId: string | number | null
}>()

const emit = defineEmits<{
  /** Nach bestätigter Prüfung — z. B. um eine Übersicht nachzuziehen. */
  geprueft: []
}>()

const store = useKiHerkunftStore()
const busy = ref(false)
const fehler = ref('')

const objektId = computed(() => (props.objektId == null ? '' : String(props.objektId)))

const status = computed(() =>
  store.statusFor(props.modul, props.projekt, props.art, objektId.value),
)

/** „ollama, 22.10.2026" — Anbieter und Zeitpunkt des Entwurfs. */
const herkunft = computed(() => {
  const s = status.value
  if (!s) return ''
  return [s.provider, fmtDatum(s.erzeugt_am)].filter(Boolean).join(', ')
})

const geprueftAm = computed(() => fmtDatum(status.value?.geprueft_am))

function fmtDatum(iso?: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? String(iso).slice(0, 10) : d.toLocaleDateString('de-DE')
}

// Die Karte wird je (Modul, Projekt, Art) **einmal** geladen — der Store
// bündelt gleichzeitige Aufrufe mehrerer Badges zu einer Abfrage und fragt
// eine noch frische Karte gar nicht erst ab. Der Objektwechsel steht bewusst
// mit im Watch: so revalidiert eine veraltete Karte beim Öffnen des nächsten
// Objekts (z. B. nach einer Massenbewertung).
watch(
  () => [props.modul, props.projekt, props.art, objektId.value] as const,
  ([modul, projekt, art]) => {
    fehler.value = ''
    if (modul && projekt && art) store.ensureKarte(modul, projekt, art)
  },
  { immediate: true },
)

async function bestaetigen() {
  if (!props.projekt || !objektId.value || busy.value) return
  busy.value = true
  fehler.value = ''
  try {
    const neu = await store.alsGeprueftMarkieren(
      props.modul,
      props.projekt,
      props.art,
      objektId.value,
    )
    if (neu) {
      emit('geprueft')
    } else {
      // Store-Fehler sichtbar machen, nicht verschlucken. Ohne Fehlermeldung
      // (HTTP 404) gab es nichts zu prüfen — der Hinweis ist dann weg.
      const st = store.keyState(props.modul, props.projekt, props.art)
      fehler.value = st.error || ''
    }
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
/* Farben wie die bestehenden Warn-/Erfolgshinweise der Module — ruhig, kein Rot-Alarm. */
.kih {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 6px 0 10px;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 0.85em;
}
.kih-offen {
  background: #fff3e0;
  color: #b26a00;
  font-weight: 600;
}
.kih-ok {
  background: #f1f8e9;
  color: #2e7d32;
  font-size: 0.78em;
  font-weight: 500;
}
.kih-text {
  flex: 1 1 auto;
}
.kih-btn {
  padding: 3px 10px;
  border: 1px solid #b26a00;
  border-radius: 6px;
  background: #fff;
  color: #b26a00;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.kih-btn:hover:not(:disabled) {
  background: #b26a00;
  color: #fff;
}
.kih-btn:disabled {
  opacity: 0.6;
  cursor: default;
}
.kih-fehler {
  flex: 1 1 100%;
  color: #c62828;
  font-size: 12px;
  font-weight: 500;
}
</style>
