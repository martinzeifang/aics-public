<template>
  <div class="lang-switch" :title="$t('app.language')">
    <button
      v-for="code in (['de','en'] as const)"
      :key="code"
      type="button"
      :class="['lang-btn', { active: current === code }]"
      @click="onSelect(code)"
    >{{ code.toUpperCase() }}</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLocale, type LocaleCode } from '../i18n'

const { locale } = useI18n()
const current = computed(() => locale.value as LocaleCode)

function onSelect(code: LocaleCode) {
  setLocale(code)
}
</script>

<style scoped>
.lang-switch { display: inline-flex; border: 1px solid var(--color-border, #d4d8e0); border-radius: 6px; overflow: hidden; }
.lang-btn {
  background: transparent;
  border: 0;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  color: var(--color-text-muted, #5a6470);
}
.lang-btn.active {
  background: var(--color-primary, #1565c0);
  color: #fff;
}
.lang-btn:not(.active):hover { background: var(--color-surface-alt, #f3f5f9); }
</style>
