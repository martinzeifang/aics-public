<template>
  <div :class="['chapter-card', ampelClass]" @click="$emit('click')">
    <div class="chapter-header">
      <div class="chapter-id">{{ id }}</div>
      <div class="chapter-percent">{{ percent }}%</div>
    </div>
    <div v-if="title" class="chapter-title">{{ title }}</div>
    <div class="progress-bar">
      <div class="progress-fill" :style="{ width: percent + '%', background: color }"></div>
    </div>
    <div class="chapter-stats">
      <span>{{ bewertet }} / {{ gesamt }}</span>
      <span class="ampel-dot" :style="{ background: color }"></span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  id: string
  title?: string
  percent: number
  bewertet: number
  gesamt: number
  ampel?: string
}>()

defineEmits<{ click: [] }>()

const color = computed(() => {
  if (props.ampel === 'gruen') return '#2e7d32'
  if (props.ampel === 'orange') return '#e65100'
  if (props.ampel === 'rot') return '#c62828'
  const p = props.percent
  if (p >= 75) return '#2e7d32'
  if (p >= 50) return '#f57f17'
  if (p >= 25) return '#e65100'
  return '#c62828'
})

const ampelClass = computed(() => {
  if (props.ampel === 'gruen' || props.percent >= 75) return 'ampel-gruen'
  if (props.ampel === 'orange' || props.percent >= 25) return 'ampel-orange'
  return 'ampel-rot'
})
</script>

<style scoped>
.chapter-card {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.15s;
  border-left: 4px solid #ccc;
}

.chapter-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.chapter-card.ampel-gruen { border-left-color: #2e7d32; }
.chapter-card.ampel-orange { border-left-color: #e65100; }
.chapter-card.ampel-rot { border-left-color: #c62828; }

.chapter-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 6px;
}

.chapter-id {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-primary);
}

.chapter-percent {
  font-size: 22px;
  font-weight: 700;
  color: #333;
}

.chapter-title {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

.progress-bar {
  height: 6px;
  background: #f0f0f0;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 6px;
}

.progress-fill {
  height: 100%;
  transition: width 0.3s ease-out;
}

.chapter-stats {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: #888;
}

.ampel-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
</style>
