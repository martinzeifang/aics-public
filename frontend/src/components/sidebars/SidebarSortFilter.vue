<template>
  <div class="sidebar-sortfilter">
    <div class="zeile">
      <label class="feld" :title="'Sortierung'">
        <span class="kuerzel" aria-hidden="true">↕</span>
        <select
          class="auswahl"
          aria-label="Sortierung"
          :value="sortierung"
          @change="$emit('update:sortierung', ($event.target as HTMLSelectElement).value)"
        >
          <option v-for="o in sortOptionen" :key="o.wert" :value="o.wert">{{ o.label }}</option>
        </select>
      </label>

      <label v-for="a in auswahlen || []" :key="a.key" class="feld" :title="a.label">
        <select
          class="auswahl"
          :class="{ gesetzt: !!a.wert }"
          :aria-label="a.label"
          :value="a.wert"
          @change="$emit('auswahl', { key: a.key, wert: ($event.target as HTMLSelectElement).value })"
        >
          <option value="">{{ a.label }}: alle</option>
          <option v-for="o in a.optionen" :key="o.wert" :value="o.wert">{{ o.label }}</option>
        </select>
      </label>
    </div>

    <div v-if="(schalter || []).length || aktiv" class="chips">
      <button
        v-for="s in schalter || []"
        :key="s.key"
        type="button"
        class="chip"
        :class="{ an: s.aktiv }"
        :aria-pressed="s.aktiv ? 'true' : 'false'"
        :title="s.titel || s.label"
        @click="$emit('schalter', s.key)"
      >
        {{ s.label }}<span v-if="s.anzahl != null" class="anz">{{ s.anzahl }}</span>
      </button>
      <button v-if="aktiv" type="button" class="link" @click="$emit('reset')">
        Filter zurücksetzen
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Sortier- und Filterleiste für die Modul-Sidebars (#1764).
 *
 * Wie `SidebarSearch` bewusst „dumm": sie sortiert und filtert nichts selbst,
 * sondern zeigt nur die Bedienelemente und meldet die Auswahl. Die Logik bleibt
 * in der Sidebar, die ihre Datenstruktur kennt.
 */
export interface SortOption {
  wert: string
  label: string
}

/** Auswahlfilter (Dropdown), z. B. Framework oder Produktklasse. */
export interface AuswahlFilter {
  key: string
  /** Beschriftung, erscheint auch in der „alle"-Zeile. */
  label: string
  /** Aktueller Wert; `''` = kein Filter. */
  wert: string
  optionen: SortOption[]
}

/** Ja/Nein-Filter als Chip, z. B. „nur mit offenen Risiken". */
export interface SchalterFilter {
  key: string
  label: string
  aktiv: boolean
  /** Treffer-Anzahl (nur Anzeige). */
  anzahl?: number | null
  titel?: string
}

defineProps<{
  sortierung: string
  sortOptionen: SortOption[]
  auswahlen?: AuswahlFilter[]
  schalter?: SchalterFilter[]
  /** True, wenn mindestens ein Filter gesetzt ist → „zurücksetzen" anzeigen. */
  aktiv?: boolean
}>()

defineEmits<{
  (e: 'update:sortierung', wert: string): void
  (e: 'auswahl', payload: { key: string; wert: string }): void
  (e: 'schalter', key: string): void
  (e: 'reset'): void
}>()
</script>

<style scoped>
.sidebar-sortfilter {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 6px;
}

.zeile {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.feld {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1 1 auto;
  min-width: 0;
  background: white;
  border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 4px;
  padding: 2px 4px;
}

.feld:focus-within {
  border-color: var(--color-primary, #1565c0);
}

.kuerzel {
  font-size: 11px;
  opacity: 0.6;
  flex: none;
}

.auswahl {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 11px;
  color: #333;
  cursor: pointer;
}

.auswahl.gesetzt {
  color: var(--color-primary, #1565c0);
  font-weight: 600;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.chip {
  border: 1px solid var(--color-border, #e0e0e0);
  background: white;
  color: #666;
  border-radius: 10px;
  padding: 2px 8px;
  font-size: 10px;
  line-height: 1.5;
  cursor: pointer;
}

.chip:hover {
  border-color: var(--color-primary, #1565c0);
  color: #333;
}

.chip.an {
  background: #e3f2fd;
  border-color: var(--color-primary, #1565c0);
  color: var(--color-primary, #1565c0);
  font-weight: 600;
}

.chip .anz {
  margin-left: 4px;
  opacity: 0.75;
}

.link {
  border: none;
  background: none;
  padding: 0 2px;
  font-size: 10px;
  color: var(--color-primary, #1565c0);
  cursor: pointer;
  text-decoration: underline;
}
</style>
