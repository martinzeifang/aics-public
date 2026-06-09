<template>
  <div class="assistenten-grid">
    <div v-if="!wizards.length" class="empty">
      Für dieses Modul sind noch keine Assistenten verfügbar.
    </div>

    <template v-else-if="grouped">
      <section
        v-for="group in groups"
        :key="group.kategorie"
        class="kategorie-section"
      >
        <h3 class="kategorie-title">{{ group.label }}</h3>
        <div class="card-grid">
          <button
            v-for="w in group.wizards"
            :key="w.id"
            type="button"
            class="assistent-card"
            :class="{ 'is-disabled': w.disabled }"
            :disabled="w.disabled"
            @click="onOpen(w)"
          >
            <div class="card-icon">{{ w.icon }}</div>
            <h4>{{ w.title }}</h4>
            <p>{{ w.description }}</p>
          </button>
        </div>
      </section>
    </template>

    <div v-else class="card-grid">
      <button
        v-for="w in wizards"
        :key="w.id"
        type="button"
        class="assistent-card"
        :class="{ 'is-disabled': w.disabled }"
        :disabled="w.disabled"
        @click="onOpen(w)"
      >
        <div class="card-icon">{{ w.icon }}</div>
        <h4>{{ w.title }}</h4>
        <p>{{ w.description }}</p>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  groupWizardsByKategorie,
  type WizardDescriptor,
} from './registry'

const props = withDefaults(
  defineProps<{
    /** Wizard tiles to render. */
    wizards: WizardDescriptor[]
    /** When true, tiles are grouped into category sections. */
    grouped?: boolean
  }>(),
  {
    grouped: false,
  },
)

const emit = defineEmits<{
  /** Emitted with the wizard id when an enabled tile is activated. */
  (e: 'open', id: string): void
}>()

const groups = computed(() => groupWizardsByKategorie(props.wizards))

function onOpen(w: WizardDescriptor): void {
  if (w.disabled) return
  emit('open', w.id)
}
</script>

<style scoped>
.assistenten-grid {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.empty {
  padding: 24px;
  color: var(--color-text-secondary);
  font-size: 14px;
  text-align: center;
  background: var(--color-surface);
  border: 1px dashed var(--color-border);
  border-radius: 8px;
}

.kategorie-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.kategorie-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.assistent-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 24px;
  text-align: left;
  cursor: pointer;
  color: inherit;
  font: inherit;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: transform 150ms, box-shadow 150ms, border-color 150ms;
}
.assistent-card:hover:not(.is-disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
  border-color: var(--color-primary);
}
.assistent-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
.assistent-card.is-disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.card-icon {
  font-size: 32px;
}
.assistent-card h4 {
  margin: 0;
  font-size: 16px;
  color: var(--color-primary);
}
.assistent-card p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.4;
}
</style>
