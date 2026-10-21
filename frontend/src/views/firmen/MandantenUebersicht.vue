<template>
  <div class="mandanten-uebersicht">
    <div class="head">
      <div>
        <h3>Mandanten</h3>
        <p class="sub">
          {{ gefiltert.length }} von {{ firmen.length }}
          {{ firmen.length === 1 ? 'Mandant' : 'Mandanten' }}
          <span v-if="aktiveFilter" class="filter-hinweis">· gefiltert</span>
        </p>
      </div>
      <button v-if="aktiveFilter" class="btn-link" type="button" @click="filterZuruecksetzen">
        Filter zurücksetzen
      </button>
    </div>

    <!-- Filterzeile: Suche, Modul, Berater, Sortierung (#1711) -->
    <div class="filterbar">
      <input
        v-model="suche"
        type="search"
        class="f-suche"
        placeholder="🔍 Name, Unternehmen oder Berater …"
        aria-label="Mandanten durchsuchen"
      />
      <select v-model="modulFilter" aria-label="Nach Modul filtern">
        <option value="">Alle Module</option>
        <option v-for="m in modulOptionen" :key="m.key" :value="m.key">{{ m.label }}</option>
      </select>
      <select v-model="beraterFilter" aria-label="Nach Berater filtern">
        <option value="">Alle Berater</option>
        <option v-for="b in berater" :key="b" :value="b">{{ b }}</option>
      </select>
      <select v-model="sortierung" aria-label="Sortierung">
        <option value="name">Name A–Z</option>
        <option value="name-desc">Name Z–A</option>
        <option value="module">Module (meiste zuerst)</option>
        <option value="updated">Zuletzt geändert</option>
      </select>
    </div>

    <div v-if="loading" class="hint">⏳ Lade Mandanten …</div>

    <div v-else-if="firmen.length === 0" class="hint">
      Noch keine Mandanten angelegt.
    </div>

    <div v-else-if="gefiltert.length === 0" class="hint">
      Kein Mandant passt zu den Filtern.
    </div>

    <table v-else class="tabelle">
      <thead>
        <tr>
          <th>Mandant</th>
          <th>Unternehmen</th>
          <th>Berater</th>
          <th>Module</th>
          <th class="num">Geändert</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="f in seite" :key="f.name" class="zeile" @click="$emit('open', f)">
          <td class="name">{{ f.name }}</td>
          <td class="muted">{{ f.company || f.unternehmen || '—' }}</td>
          <td class="muted">{{ f.advisor || f.berater || '—' }}</td>
          <td>
            <span v-for="m in aktiveModule(f)" :key="m.key" class="badge" :title="m.label">
              {{ m.kurz }}
            </span>
            <span v-if="aktiveModule(f).length === 0" class="muted">—</span>
          </td>
          <td class="num muted">{{ datum(f.updated_at) }}</td>
        </tr>
      </tbody>
    </table>

    <div v-if="gefiltert.length > proSeite" class="pager">
      <button class="btn-small" :disabled="seitenIndex === 0" @click="seitenIndex--">‹ zurück</button>
      <span class="pager-info">
        {{ seitenIndex * proSeite + 1 }}–{{ Math.min((seitenIndex + 1) * proSeite, gefiltert.length) }}
        von {{ gefiltert.length }}
      </span>
      <button class="btn-small" :disabled="(seitenIndex + 1) * proSeite >= gefiltert.length"
              @click="seitenIndex++">weiter ›</button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Mandanten-Übersicht (#1711).
 *
 * Bisher war die Firmenliste ausschließlich die Sidebar — bei einem
 * Wholesale-Bestand mit 50+ Mandanten eine unbedienbar lange Liste, und der
 * Startzustand von `/firmen` war ein leerer Platzhalter. Diese Tabelle nutzt
 * diesen Platz: durchsuchbar, nach Modul und Berater filterbar, sortierbar,
 * paginiert.
 *
 * Rein lesend und ohne eigene Requests — die Daten kommen aus dem Firmen-Store,
 * der beim Laden der Sidebar schon gefüllt wird.
 */
import { computed, ref, watch } from 'vue'
import type { Firma } from '../../stores/firmen'
import { matchesSuche } from '../../composables/useSidebarFilter'

const props = defineProps<{
  firmen: Firma[]
  loading?: boolean
}>()

defineEmits<{ (e: 'open', firma: Firma): void }>()

const MODULE = [
  { key: 'cra', label: 'CRA', kurz: 'CRA' },
  { key: 'nis2', label: 'NIS2', kurz: 'NIS2' },
  { key: 'ai_act', label: 'EU AI Act', kurz: 'AI' },
  { key: 'dsgvo', label: 'DSGVO', kurz: 'DS' },
  { key: 'wiba', label: 'WiBA (BSI)', kurz: 'WiBA' },
  { key: 'risikobewertung', label: 'Risikobewertung', kurz: 'RB' },
  { key: 'gutachten', label: 'Gutachten', kurz: 'GA' },
] as const

const proSeite = 25

const suche = ref('')
const modulFilter = ref('')
const beraterFilter = ref('')
const sortierung = ref<'name' | 'name-desc' | 'module' | 'updated'>('name')
const seitenIndex = ref(0)

const modulOptionen = computed(() => MODULE)

const aktiveFilter = computed(() =>
  Boolean(suche.value || modulFilter.value || beraterFilter.value),
)

const berater = computed(() => {
  const set = new Set<string>()
  for (const f of props.firmen) {
    const b = (f.advisor || f.berater || '').trim()
    if (b) set.add(b)
  }
  return [...set].sort((a, b) => a.localeCompare(b, 'de'))
})

const aktiveModule = (f: Firma) =>
  MODULE.filter((m) => (f.modules as Record<string, boolean>)?.[m.key])

const gefiltert = computed(() => {
  let liste = props.firmen.filter((f) =>
    matchesSuche(suche.value, f.name, f.company, f.unternehmen, f.advisor, f.berater))
  if (modulFilter.value) {
    liste = liste.filter((f) =>
      (f.modules as Record<string, boolean>)?.[modulFilter.value])
  }
  if (beraterFilter.value) {
    liste = liste.filter((f) =>
      (f.advisor || f.berater || '').trim() === beraterFilter.value)
  }
  const sortiert = [...liste]
  switch (sortierung.value) {
    case 'name-desc':
      sortiert.sort((a, b) => b.name.localeCompare(a.name, 'de'))
      break
    case 'module':
      sortiert.sort((a, b) =>
        aktiveModule(b).length - aktiveModule(a).length ||
        a.name.localeCompare(b.name, 'de'))
      break
    case 'updated':
      sortiert.sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
      break
    default:
      sortiert.sort((a, b) => a.name.localeCompare(b.name, 'de'))
  }
  return sortiert
})

const seite = computed(() =>
  gefiltert.value.slice(seitenIndex.value * proSeite, (seitenIndex.value + 1) * proSeite),
)

// Filterwechsel darf nicht auf einer leeren Seite landen.
watch([suche, modulFilter, beraterFilter, sortierung], () => { seitenIndex.value = 0 })

const filterZuruecksetzen = () => {
  suche.value = ''
  modulFilter.value = ''
  beraterFilter.value = ''
}

const datum = (iso?: string): string => {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('de-DE')
}
</script>

<style scoped>
.mandanten-uebersicht { display: flex; flex-direction: column; gap: 12px; }

.head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.head h3 { margin: 0; font-size: 15px; }
.sub { margin: 2px 0 0; font-size: 12px; color: #777; }
.filter-hinweis { color: var(--color-primary, #1565c0); }

.btn-link {
  border: none; background: none; padding: 0; cursor: pointer;
  color: var(--color-primary, #1565c0); font-size: 12px; text-decoration: underline;
}

.filterbar { display: flex; flex-wrap: wrap; gap: 8px; }
.filterbar input, .filterbar select {
  padding: 6px 8px; border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 4px; font-size: 13px; background: white;
}
.f-suche { flex: 1 1 240px; min-width: 180px; }

.hint { font-size: 13px; color: #777; padding: 12px 0; }

.tabelle { width: 100%; border-collapse: collapse; font-size: 13px; }
.tabelle th {
  text-align: left; padding: 8px 10px; border-bottom: 2px solid var(--color-border, #e0e0e0);
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.4px; color: #666;
}
.tabelle td { padding: 8px 10px; border-bottom: 1px solid #f0f0f0; }
.tabelle th.num, .tabelle td.num { text-align: right; white-space: nowrap; }

.zeile { cursor: pointer; }
.zeile:hover { background: #f5f9ff; }
.name { font-weight: 600; color: #333; }
.muted { color: #888; }

.badge {
  display: inline-block; margin: 0 3px 2px 0; padding: 1px 6px; border-radius: 9px;
  background: #e3f2fd; color: #1565c0; font-size: 10px; font-weight: 700;
}

.pager { display: flex; align-items: center; gap: 10px; justify-content: flex-end; }
.pager-info { font-size: 12px; color: #777; }
.btn-small {
  padding: 4px 10px; font-size: 12px; border: 1px solid var(--color-border, #e0e0e0);
  background: white; border-radius: 4px; cursor: pointer;
}
.btn-small:disabled { opacity: 0.45; cursor: default; }
</style>
