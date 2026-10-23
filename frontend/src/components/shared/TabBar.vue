<!--
  TabBar (Bugfix-Sprint #22, B3) — einheitliche Button-Tab-Navigation für die
  fünf Compliance-Modul-Views (CRA, NIS2, AI Act, DSGVO, Risikobewertung).
  Spiegelt das bestehende CRA-Tab-CSS (.tabs / .tab-btn / .tab-btn.active).

  Verwendung (v-model auf der aktiven Tab-ID):
    <TabBar :tabs="tabs" v-model="activeTab" />
  mit tabs = [{ id: 'dashboard', label: '📊 Dashboard' }, …]
-->
<template>
  <div class="tabs">
    <button
      v-for="t in tabs"
      :key="t.id"
      type="button"
      :class="['tab-btn', { active: modelValue === t.id }]"
      @click="emit('update:modelValue', t.id)"
    >
      {{ t.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  tabs: { id: string; label: string }[]
  modelValue: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', id: string): void
}>()
</script>

<style scoped>
.tabs {
  display: flex; gap: 2px; margin-bottom: 16px;
  border-bottom: 2px solid var(--color-border);
  flex-wrap: wrap;
}

.tab-btn {
  background: none; border: none; padding: 10px 18px;
  font-size: 14px; font-weight: 500; cursor: pointer;
  border-bottom: 3px solid transparent; color: #666;
}

.tab-btn.active {
  color: var(--color-primary); border-bottom-color: var(--color-primary);
  background: #f5f5f5;
}
</style>
