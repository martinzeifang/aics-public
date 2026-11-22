<!--
  ModuleShell (Bugfix-Sprint #22, B3) — gemeinsames Chrome für die fünf
  Compliance-Modul-Views (CRA, NIS2, AI Act, DSGVO, Risikobewertung). Bündelt
  Header (Titel/Subtitel + ModuleHelpButton), Projekt-Leiste, RepoConfigPanel,
  TabBar und Tab-Inhalt. Styling spiegelt das bisherige CRAView-Aussehen.

  Slot-API (alle optional außer dem Tab-Inhalt):
    #project-bar  — Projektselektor + Aktionsbuttons des Moduls
                    (wird in einen .project-bar-Container gewrappt)
    #repo-config  — das RepoConfigPanel des Moduls
    default / #tab-content — Body des aktiven Tabs
    #modals       — modulspezifische Dialoge/Editoren (außerhalb des Flows)

  Props:
    title       — Überschrift (h2)
    subtitle    — Unterzeile (p)
    moduleName  — Modul-Key für <ModuleHelpButton :module="…" />
    tabs        — [{ id, label }] für die TabBar
    modelValue  — aktive Tab-ID (v-model)

  Verwendung:
    <ModuleShell title="…" subtitle="…" module-name="cra"
                 :tabs="tabs" v-model="activeTab">
      <template #project-bar> … </template>
      <template #repo-config> <RepoConfigPanel … /> </template>
      <YourActiveTabBody />
      <template #modals> … </template>
    </ModuleShell>
-->
<template>
  <div class="module-shell">
    <div class="header">
      <h2>{{ title }}</h2>
      <p>{{ subtitle }}</p>
      <ModuleHelpButton :module="moduleName" :active-area="modelValue" />
    </div>

    <div v-if="$slots['project-bar']" class="project-bar">
      <slot name="project-bar" />
    </div>

    <slot name="repo-config" />

    <!-- Gruppierte Navigation (Sprint #34, #1369) bevorzugt, sonst flache TabBar -->
    <GroupedModuleNav
      v-if="groups && groups.length"
      :groups="groups"
      :persist-key="persistKey"
      :model-value="modelValue"
      @update:model-value="(id: string) => emit('update:modelValue', id)"
    />
    <TabBar
      v-else-if="tabs && tabs.length"
      :tabs="tabs"
      :model-value="modelValue"
      @update:model-value="(id: string) => emit('update:modelValue', id)"
    />

    <div class="tab-content">
      <slot name="tab-content">
        <slot />
      </slot>
    </div>

    <slot name="modals" />
  </div>
</template>

<script setup lang="ts">
import ModuleHelpButton from '../shared/ModuleHelpButton.vue'
import TabBar from './TabBar.vue'
import GroupedModuleNav from './GroupedModuleNav.vue'

defineProps<{
  title: string
  subtitle: string
  moduleName: string
  tabs: { id: string; label: string }[]
  modelValue: string
  // Optional: gruppierte Navigation (Sprint #34). Wenn gesetzt, ersetzt sie die
  // flache TabBar. [{ id, label, tabs: [{ id, label }] }]
  groups?: { id: string; label: string; tabs: { id: string; label: string }[] }[]
  persistKey?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', id: string): void
}>()
</script>

<style scoped>
.module-shell { max-width: 1400px; }

.header {
  margin-bottom: 16px; padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
  display: flex; align-items: flex-end; gap: 16px;
}
.header h2 { margin: 0; font-size: 22px; flex: 1; }
.header p { margin: 2px 0 0; color: #888; font-size: 13px; flex: 2; }

.project-bar {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; background: var(--color-background);
  border: 1px solid var(--color-border); border-radius: 6px;
  margin-bottom: 12px; flex-wrap: wrap;
}

.tab-content { padding: 8px 0; }
</style>
