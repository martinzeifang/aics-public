<!--
  GroupedModuleNav (Sprint #34, #1369) — zweistufige, gruppierte Modul-Navigation.
  Ebene 1 = Gruppen-Pills (z. B. Überblick · Tagesbetrieb · Detektion · Compliance &
  Register · Dokumentation · Berichte · Verwaltung), Ebene 2 = die Tabs der aktiven
  Gruppe. Die aktive Gruppe wird aus der aktiven Tab-ID abgeleitet (modelValue) —
  kein separater Gruppen-State nötig.

  Ersetzt die flache TabBar dort, wo Module zu viele Tabs haben (SOC 16, CRA 15,
  DSGVO 24 …). Optik/Scheme konsistent mit TabBar (#1565c0 / #90caf9).

  Props:
    groups     — [{ id, label, tabs: [{ id, label }] }]
    modelValue — aktive Tab-ID (v-model)
    persistKey — optional: localStorage-Schlüssel für Tab-Persistenz (#1376).
                 Deep-Links (?tab=…) haben Vorrang vor dem gespeicherten Stand.

  Verwendung:
    <GroupedModuleNav :groups="groups" v-model="activeTab" persist-key="cra" />

  Responsive (#1372): Gruppen-Pills + Tabs scrollen horizontal bei schmaler Breite.
-->
<template>
  <div v-if="groups && groups.length" class="grouped-nav">
    <div class="nav-groups" role="tablist" aria-label="Bereichsgruppen">
      <button
        v-for="g in groups"
        :key="g.id"
        type="button"
        role="tab"
        :aria-selected="g.id === activeGroupId"
        :class="['nav-group', { active: g.id === activeGroupId }]"
        @click="selectGroup(g)"
      >
        {{ g.label }}
        <span class="grp-count">{{ g.tabs.length }}</span>
      </button>
    </div>

    <div v-if="activeGroup && activeGroup.tabs.length" class="nav-tabs" role="tablist">
      <button
        v-for="t in activeGroup.tabs"
        :key="t.id"
        type="button"
        role="tab"
        :aria-selected="modelValue === t.id"
        :class="['nav-tab', { active: modelValue === t.id }]"
        @click="emit('update:modelValue', t.id)"
      >
        {{ t.label }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'

interface NavTab { id: string; label: string }
interface NavGroup { id: string; label: string; tabs: NavTab[] }

const props = defineProps<{
  groups: NavGroup[]
  modelValue: string
  persistKey?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', id: string): void
}>()

const activeGroup = computed(() =>
  props.groups.find((g) => g.tabs.some((t) => t.id === props.modelValue)) || props.groups[0],
)
const activeGroupId = computed(() => activeGroup.value?.id)

function selectGroup(g: NavGroup) {
  // Gruppe wählen → erste Tab der Gruppe aktivieren (außer die aktive Tab gehört
  // bereits zu dieser Gruppe, dann kein Sprung).
  if (g.tabs.some((t) => t.id === props.modelValue)) return
  if (g.tabs.length) emit('update:modelValue', g.tabs[0].id)
}

// ── Persistenz (#1376) ───────────────────────────────────────────────────────
function storageKey(): string | null {
  return props.persistKey ? `nav:${props.persistKey}:tab` : null
}
function allTabIds(): Set<string> {
  return new Set(props.groups.flatMap((g) => g.tabs.map((t) => t.id)))
}

onMounted(() => {
  const key = storageKey()
  if (!key) return
  // Deep-Link (?tab=…) hat Vorrang — dann nicht aus localStorage wiederherstellen.
  try {
    if (new URLSearchParams(window.location.search).has('tab')) return
  } catch {
    /* ignore */
  }
  try {
    const saved = window.localStorage.getItem(key)
    if (saved && saved !== props.modelValue && allTabIds().has(saved)) {
      emit('update:modelValue', saved)
    }
  } catch {
    /* localStorage nicht verfügbar — ignorieren */
  }
})

watch(
  () => props.modelValue,
  (id) => {
    const key = storageKey()
    if (!key || !id) return
    try {
      window.localStorage.setItem(key, id)
    } catch {
      /* ignore */
    }
  },
)
</script>

<style scoped>
.grouped-nav {
  margin-bottom: 16px;
}

/* Ebene 1 — Gruppen-Pills */
.nav-groups {
  display: flex;
  gap: 6px;
  padding: 4px;
  background: #e3f2fd;
  border-radius: 8px;
  overflow-x: auto;
  scrollbar-width: thin;
}
.nav-group {
  flex: 0 0 auto;
  background: transparent;
  border: none;
  padding: 7px 14px;
  font-size: 13.5px;
  font-weight: 600;
  color: #1565c0;
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  line-height: 1.3;
}
.nav-group:hover {
  background: #bbdefb;
}
.nav-group.active {
  background: #1565c0;
  color: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}
.grp-count {
  font-size: 11px;
  font-weight: 600;
  opacity: 0.7;
  background: rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  padding: 0 6px;
  min-width: 16px;
  text-align: center;
}
.nav-group.active .grp-count {
  background: rgba(255, 255, 255, 0.25);
  opacity: 1;
}

/* Ebene 2 — Tabs der aktiven Gruppe */
.nav-tabs {
  display: flex;
  gap: 2px;
  margin-top: 8px;
  border-bottom: 2px solid var(--color-border);
  overflow-x: auto;
  scrollbar-width: thin;
}
.nav-tab {
  flex: 0 0 auto;
  background: none;
  border: none;
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 3px solid transparent;
  color: #666;
  white-space: nowrap;
}
.nav-tab:hover {
  color: var(--color-primary);
}
.nav-tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  background: #f5f5f5;
}

@media (max-width: 768px) {
  .nav-group {
    padding: 7px 11px;
    font-size: 13px;
  }
}
</style>
