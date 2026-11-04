<!--
  ModuleHelpButton (#926/#927) — einheitlicher „❓ Hilfe"-Button (rechts oben in
  der Modul-Übersicht). Lädt den Hilfe-Inhalt aus der Registry und öffnet den
  ModuleHelpDialog. Einbindung je Modul: <ModuleHelpButton module="cra" />
-->
<template>
  <span class="module-help">
    <button type="button" class="module-help-btn" :title="`Hilfe zu ${help?.title || 'diesem Modul'}`" @click="open = true">
      ❓ Hilfe
    </button>
    <ModuleHelpDialog :open="open" :help="help" :active-area="activeArea" @close="open = false" />
  </span>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import ModuleHelpDialog from './ModuleHelpDialog.vue'
import { getModuleHelp } from '../../help'

// #1223: activeArea = aktueller Tab → Hilfe öffnet kontext-sensitiv auf dem Bereich.
const props = defineProps<{ module: string; activeArea?: string }>()
const open = ref(false)
const help = computed(() => getModuleHelp(props.module))
</script>

<style scoped>
.module-help-btn {
  background: var(--color-background, #f5f5f5);
  color: var(--color-primary, #1565c0);
  border: 1px solid var(--color-border, #d0d7de);
  padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 14px; white-space: nowrap;
}
.module-help-btn:hover { background: var(--color-border, #e3f2fd); }
</style>
