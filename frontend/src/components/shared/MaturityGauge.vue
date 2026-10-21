<template>
  <div class="gauge-wrap">
    <svg viewBox="0 0 200 110" class="gauge">
      <!-- Background arc -->
      <path d="M 20,100 A 80,80 0 0,1 180,100"
            fill="none" stroke="#e0e0e0" stroke-width="14" stroke-linecap="round" />
      <!-- Filled arc -->
      <path :d="filledArc"
            fill="none" :stroke="color" stroke-width="14" stroke-linecap="round" />
      <!-- Text -->
      <text x="100" y="78" text-anchor="middle" font-size="32" font-weight="700" :fill="color">
        {{ percent }}%
      </text>
      <text x="100" y="98" text-anchor="middle" font-size="11" fill="#888">
        {{ label || 'Reifegrad' }}
      </text>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  percent: number
  label?: string
  ampel?: string  // 'gruen' | 'orange' | 'rot'
}>()

const color = computed(() => {
  if (props.ampel === 'gruen') return '#2e7d32'
  if (props.ampel === 'orange') return '#e65100'
  if (props.ampel === 'rot') return '#c62828'
  // Auto by percent
  const p = props.percent
  if (p >= 75) return '#2e7d32'
  if (p >= 50) return '#f57f17'
  if (p >= 25) return '#e65100'
  return '#c62828'
})

const filledArc = computed(() => {
  const p = Math.max(0, Math.min(100, props.percent)) / 100
  // Bei p=0: nichts zeichnen (Background-Arc allein sichtbar)
  if (p <= 0) return 'M 20,100 L 20,100'
  // Halbkreis von (20,100) bis (180,100), Mittelpunkt (100,100), Radius 80
  // Winkel start = π (180°, links), Ende = 0 (rechts).
  // Position bei Fortschritt p: angle = π * (1-p), aus Mittelpunkt
  const angle = Math.PI * (1 - p)
  const x = 100 + 80 * Math.cos(angle)
  const y = 100 - 80 * Math.sin(angle)
  // SVG Arc: A rx,ry x-axis-rot large-arc-flag sweep-flag x,y
  // sweep-flag=1 (im Uhrzeigersinn von Start), large-arc-flag=0 (max 180° = Halbkreis)
  return `M 20,100 A 80,80 0 0 1 ${x.toFixed(2)},${y.toFixed(2)}`
})
</script>

<style scoped>
.gauge-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
}

.gauge {
  width: 200px;
  height: 110px;
}
</style>
