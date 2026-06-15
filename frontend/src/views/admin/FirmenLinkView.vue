<template>
  <div class="firmen-link-view">
    <div class="header">
      <h2>🔗 Projekt → Firma-Zuordnung</h2>
      <p>Verknüpft Projekte aller Module mit einer Firma (firmen_id). Zugeordnete Projekte fließen ins Firmen-Risikocockpit ein.</p>
    </div>

    <div v-if="store.error" class="alert alert-error" @click="store.error = null">{{ store.error }}</div>

    <!-- Backfill -->
    <fieldset class="fset">
      <legend>Automatische Zuordnung (Name-Match)</legend>
      <p class="hint">
        Ordnet Projekte automatisch ihrer Firma zu, indem der Unternehmensname mit den vorhandenen Firmen abgeglichen wird.
      </p>
      <button class="btn-primary" :disabled="store.backfilling" @click="onBackfill">
        {{ store.backfilling ? 'Backfill läuft…' : 'Backfill ausführen' }}
      </button>

      <table v-if="store.backfillResults && backfillRows.length > 0" class="data-table compact">
        <thead>
          <tr>
            <th>Modul</th>
            <th>Zugeordnet</th>
            <th>Nicht zugeordnet</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in backfillRows" :key="row.module">
            <td><strong>{{ row.module }}</strong></td>
            <td><span class="badge ok">{{ row.matched }}</span></td>
            <td><span class="badge warn">{{ row.unmatched }}</span></td>
          </tr>
        </tbody>
      </table>
      <p v-else-if="store.backfillResults" class="hint">Keine Ergebnisse.</p>
    </fieldset>

    <!-- Unassigned -->
    <h3 class="section-title">Unzugeordnete Projekte</h3>
    <div v-if="store.loading" class="loading">Lade…</div>
    <div v-else-if="unassignedRows.length === 0" class="empty">
      Alle Projekte sind einer Firma zugeordnet. 🎉
    </div>
    <table v-else class="data-table">
      <thead>
        <tr>
          <th>Modul</th>
          <th>Projekt</th>
          <th>Unternehmen (aus Projekt)</th>
          <th>Firma zuordnen</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in unassignedRows" :key="row.module + '::' + row.projekt">
          <td><span class="badge mod">{{ row.module }}</span></td>
          <td><strong>{{ row.projekt }}</strong></td>
          <td class="small">{{ row.unternehmen || '—' }}</td>
          <td>
            <select v-model.number="selection[rowKey(row)]" class="select">
              <option :value="0">— Firma wählen —</option>
              <option v-for="f in store.firmen" :key="f.id" :value="f.id">{{ f.name }}</option>
            </select>
          </td>
          <td class="actions">
            <button
              class="btn-secondary"
              :disabled="!selection[rowKey(row)] || assigning === rowKey(row)"
              @click="onAssign(row)"
            >
              {{ assigning === rowKey(row) ? 'Speichere…' : 'Zuordnen' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { useFirmenLinkStore, type UnassignedProjekt } from '../../stores/firmenLink'

interface Row extends UnassignedProjekt {
  module: string
}

const store = useFirmenLinkStore()

// rowKey → ausgewählte firmen_id (0 = keine Auswahl)
const selection = reactive<Record<string, number>>({})
const assigning = ref<string | null>(null)

const rowKey = (row: Row) => `${row.module}::${row.projekt}`

const unassignedRows = computed<Row[]>(() => {
  const rows: Row[] = []
  for (const [module, list] of Object.entries(store.unassigned)) {
    for (const p of list) {
      rows.push({ module, projekt: p.projekt, unternehmen: p.unternehmen })
    }
  }
  rows.sort((a, b) => a.module.localeCompare(b.module) || a.projekt.localeCompare(b.projekt))
  return rows
})

const backfillRows = computed(() => {
  const res = store.backfillResults
  if (!res) return []
  return Object.entries(res).map(([module, r]) => ({
    module,
    matched: r?.matched ?? 0,
    unmatched: r?.unmatched ?? 0,
  }))
})

const onBackfill = async () => {
  await store.runBackfill()
}

const onAssign = async (row: Row) => {
  const key = rowKey(row)
  const firmenId = selection[key]
  if (!firmenId) return
  assigning.value = key
  try {
    const ok = await store.assign(row.module, row.projekt, firmenId)
    if (ok) delete selection[key]
  } finally {
    assigning.value = null
  }
}

onMounted(async () => {
  await Promise.all([store.fetchFirmen(), store.fetchUnassigned()])
})
</script>

<style scoped>
.firmen-link-view { max-width: 1200px; padding: 16px; }

.header { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border); }
.header h2 { margin: 0; font-size: 22px; }
.header p { margin: 4px 0 0; color: var(--color-text-secondary); font-size: 13px; }

.alert-error {
  background: #ffebee; color: #c62828; padding: 10px; border-radius: 4px;
  margin-bottom: 12px; border: 1px solid #ef5350; cursor: pointer;
}

.fset { border: 1px solid var(--color-border); border-radius: 6px; padding: 12px 16px; margin: 0 0 24px; }
.fset legend { font-weight: 600; padding: 0 6px; }

.section-title { margin: 0 0 12px; font-size: 16px; }

.hint { font-size: 12px; color: var(--color-text-secondary); margin: 0 0 12px; }

.empty, .loading { padding: 32px; text-align: center; color: var(--color-text-secondary); }

.data-table { width: 100%; border-collapse: collapse; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden; }
.data-table.compact { margin-top: 16px; max-width: 480px; }
.data-table th { background: var(--color-background); text-align: left; padding: 10px 12px; font-size: 12px; font-weight: 600; border-bottom: 1px solid var(--color-border); }
.data-table td { padding: 10px 12px; border-bottom: 1px solid var(--color-border); font-size: 13px; vertical-align: middle; }
.data-table tr:hover { background: var(--color-background); }
.data-table .actions { white-space: nowrap; text-align: right; }
.small { font-size: 12px; color: var(--color-text-secondary); }

.select {
  padding: 7px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px;
  background: var(--color-surface); color: var(--color-text-primary); min-width: 220px;
}

.badge { display: inline-block; font-size: 11px; font-weight: 600; padding: 2px 10px; border-radius: 12px; }
.badge.ok { background: #e8f5e9; color: #2e7d32; }
.badge.warn { background: #fff3e0; color: #e65100; }
.badge.mod { background: #e3f2fd; color: #1565c0; }

.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-primary:hover:not(:disabled) { background: var(--color-primary-dark); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: var(--color-background); color: var(--color-primary); border: 1px solid var(--color-border); padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-secondary:hover:not(:disabled) { background: var(--color-border); }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
