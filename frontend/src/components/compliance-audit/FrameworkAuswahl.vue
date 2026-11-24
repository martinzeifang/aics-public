<!--
  Kompakte Framework-Auswahl als Tabelle (#2134).

  Ersetzt die zuvor zweifach kopierte Checkbox-Liste (.fw-checks) im Anlegen- und
  Bearbeiten-Formular. Eine Komponente, zwei Einbauorte — die Darstellung kann
  nicht mehr auseinanderlaufen (Linie aus #1731/#1735). Die Auswahl steht in der
  ersten Spalte, direkt vor dem Framework; die ganze Zeile ist klickbar.
-->
<template>
  <div class="fw-auswahl">
    <table class="fw-tabelle">
      <thead>
        <tr>
          <th class="c-check" :aria-label="$t('complianceAudit.complianceAuditView.auswahl')"></th>
          <th class="c-code">{{ $t('complianceAudit.complianceAuditView.spalteFramework') }}</th>
          <th class="c-label">{{ $t('complianceAudit.complianceAuditView.spalteBezeichnung') }}</th>
          <th class="c-status">{{ $t('complianceAudit.complianceAuditView.spalteNormtext') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="fw in frameworks" :key="fw.id"
            :class="{ sel: gewaehlt(fw.id) }" @click="toggle(fw.id)">
          <td class="c-check">
            <input type="checkbox" :checked="gewaehlt(fw.id)" @click.stop="toggle(fw.id)" />
          </td>
          <td class="c-code">{{ fw.id }}</td>
          <td class="c-label">{{ kurzLabel(fw.label) }}</td>
          <td class="c-status">
            <span class="pill" :class="fw.sections_count ? 'da' : 'leer'">
              {{ fw.sections_count
                ? fw.sections_count + $t('complianceAudit.complianceAuditView.abschnitte')
                : $t('complianceAudit.complianceAuditView.nichtEingelesen') }}
            </span>
          </td>
        </tr>
        <tr v-if="!frameworks.length">
          <td colspan="4" class="leer-zeile">
            {{ $t('complianceAudit.complianceAuditView.keineFrameworksImKatalog') }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
interface Framework { id: string; label: string; sections_count?: number }

const props = defineProps<{
  modelValue: string[]
  frameworks: Framework[]
}>()
const emit = defineEmits<{ (e: 'update:modelValue', v: string[]): void }>()

const gewaehlt = (id: string) => (props.modelValue || []).includes(id)

const toggle = (id: string) => {
  const aktuell = Array.isArray(props.modelValue) ? props.modelValue : []
  emit('update:modelValue', gewaehlt(id)
    ? aktuell.filter(f => f !== id)
    : [...aktuell, id])
}

// Code-Präfix aus dem Label entfernen (z. B. "CRA – Cyber…" → "Cyber…").
const kurzLabel = (label: string) => (label || '').replace(/^[A-Z0-9_]+\s*[–-]\s*/, '')
</script>

<style scoped>
.fw-auswahl { border: 1px solid var(--color-border, #d7dde2); border-radius: 8px; overflow: hidden; }
.fw-tabelle { width: 100%; border-collapse: collapse; font-size: 13px; }
.fw-tabelle thead th {
  text-align: left; font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .03em; color: var(--color-text-secondary, #607079);
  background: var(--color-bg-subtle, #f5f7f8); padding: 6px 10px;
  border-bottom: 1px solid var(--color-border, #d7dde2);
}
.fw-tabelle tbody tr { cursor: pointer; border-bottom: 1px solid var(--color-border-subtle, #eceff1); }
.fw-tabelle tbody tr:last-child { border-bottom: 0; }
.fw-tabelle tbody tr:hover { background: var(--color-bg-subtle, #f5f7f8); }
.fw-tabelle tbody tr.sel { background: #e8f1fd; }
.fw-tabelle tbody tr.sel:hover { background: #ddeafb; }
.fw-tabelle td { padding: 5px 10px; vertical-align: middle; }
.c-check { width: 1%; white-space: nowrap; text-align: center; }
.c-check input { cursor: pointer; margin: 0; }
.c-code { font-family: Consolas, monospace; font-weight: 600; white-space: nowrap; }
.c-label { color: var(--color-text-secondary, #607079); width: 100%; }
.c-status { white-space: nowrap; text-align: right; }
.pill { font-size: 11px; border-radius: 10px; padding: 1px 8px; white-space: nowrap; }
.pill.da { background: #e8f5e9; color: #2e7d32; }
.pill.leer { background: #fff3e0; color: #ef6c00; }
.leer-zeile { text-align: center; color: var(--color-text-secondary, #607079); padding: 14px; font-style: italic; }
</style>
