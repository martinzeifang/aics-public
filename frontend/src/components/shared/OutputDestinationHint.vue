<template>
  <div class="odh">
    <span class="odh-icon" aria-hidden="true">📥</span>
    <div class="odh-body">
      <span class="odh-title">So wird die Antwort verwendet:</span>
      <span class="odh-dest">{{ destinationText }}</span>
      <span v-if="impactText" class="odh-impact">{{ impactText }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * OutputDestinationHint — kompakter Hinweis, wohin die KI-Antwort gespeichert
 * wird und welche Wirkung sie hat (#869).
 *
 * Props:
 *   - destination / targetFieldLabel:  Zielfeld (z. B. „wird im Bewertungs-
 *     Kommentar gespeichert").
 *   - impact / effectDescription:      Optionale Wirkungsbeschreibung
 *     (z. B. „setzt den Status auf 'in Prüfung'").
 *
 * Es werden bewusst beide Namenskonventionen unterstützt (Task vs. Sprint-Plan),
 * damit migrierende Module flexibel anbinden können.
 *
 * Teil von #865.
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    destination?: string
    impact?: string
    targetFieldLabel?: string
    effectDescription?: string
  }>(),
  { destination: '', impact: '', targetFieldLabel: '', effectDescription: '' },
)

const destinationText = computed(() => props.destination || props.targetFieldLabel || '—')
const impactText = computed(() => props.impact || props.effectDescription || '')
</script>

<style scoped>
.odh {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.55rem 0.8rem;
  background: #e8f0fe;
  border: 1px solid #bbdefb;
  border-radius: 6px;
  font-size: 0.82rem;
  color: #0d47a1;
}

.odh-icon {
  font-size: 1rem;
  line-height: 1.3;
}

.odh-body {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.odh-title {
  font-weight: 600;
}

.odh-dest {
  color: #1a237e;
}

.odh-impact {
  color: #455a64;
  font-style: italic;
}
</style>
