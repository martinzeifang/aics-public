<template>
  <div class="module-dashboard">
    <!-- Gesamt-Reifegrad + Bereichs-/Kapitelkarten -->
    <div class="dashboard">
      <div class="gauge-card">
        <!--
          #2041: Kein ``label``-Literal mehr. ``MaturityGauge`` hat
          ``$t('geteilt.maturityGauge.reifegrad')`` als Vorgabe, und ein
          übergebenes Literal überstimmt sie — auf der **ersten Seite jedes
          Moduls** stand damit „Gesamt-Reifegrad" auch auf Englisch.
        -->
        <MaturityGauge
          :percent="Math.round(gesamt.percent ?? 0)"
          :ampel="gesamt.ampel"
          :label="$t('geteilt.moduleDashboard.gesamtReifegrad')"
        />
        <div class="gauge-stats">
          <div v-for="(z, i) in gesamtStats" :key="i">{{ $t(z.key, saubereWerte(z.werte)) }}</div>
        </div>
      </div>

      <div class="chapters-grid">
        <ChapterCard
          v-for="b in bereiche"
          :key="b.id"
          :id="b.id"
          :title="b.title"
          :percent="Math.round(b.percent ?? 0)"
          :bewertet="b.bewertet ?? 0"
          :gesamt="b.gesamt ?? 0"
          :ampel="b.ampel"
          @click="$emit('open-bereich', b.id)"
        />
        <div v-if="bereiche.length === 0" class="empty-card">
          {{ $t('geteilt.moduleDashboard.nochKeineBereichsDatenBitteZuerstBew') }}
        </div>
      </div>
    </div>

    <!-- Kacheln: offene Punkte / offene Fristen / Dokumente / Risiken -->
    <div class="kpi-grid">
      <!-- Offene Punkte (Score < Schwelle) -->
      <div class="kpi-card" :class="{ clickable: !!offenePunkte.length }"
           @click="offenePunkte.length && $emit('open-luecken')">
        <div class="kpi-head">
          <span class="kpi-icon">🚩</span>
          <span class="kpi-title">{{ $t('geteilt.moduleDashboard.offenePunkte') }}</span>
        </div>
        <div class="kpi-value" :class="offenePunkte.length ? 'warn' : 'ok'">
          {{ offenePunkte.length }}
        </div>
        <div class="kpi-sub">{{ $t('geteilt.moduleDashboard.anforderungenMitScoreLtV0', { v0: schwelle }) }}</div>
        <ul v-if="offenePunkte.length" class="kpi-list">
          <li v-for="l in offenePunkte.slice(0, 5)" :key="l.id"
              class="kpi-item" @click.stop="$emit('open-punkt', l.id)">
            <code>{{ l.id }}</code>
            <span class="kpi-item-text">{{ l.titel }}</span>
            <span class="kpi-item-meta">{{ $t('geteilt.moduleDashboard.scoreV0', { v0: l.bewertung }) }}</span>
          </li>
        </ul>
      </div>

      <!-- Offene Fristen -->
      <div class="kpi-card" :class="{ clickable: fristenTab }"
           @click="fristenTab && $emit('open-fristen')">
        <div class="kpi-head">
          <span class="kpi-icon">📅</span>
          <span class="kpi-title">{{ $t('geteilt.moduleDashboard.offeneFristen') }}</span>
        </div>
        <div class="kpi-value" :class="fristenOffen ? 'warn' : 'ok'">
          {{ fristen.length ? fristenOffen : '–' }}
        </div>
        <div class="kpi-sub">
          <template v-if="fristen.length">{{ $t('geteilt.moduleDashboard.v0Uberfallig', { v0: fristenUeberfaellig }) }}</template>
          <template v-else>{{ $t('geteilt.moduleDashboard.keineFristenInDiesemModul') }}</template>
        </div>
        <ul v-if="fristen.length" class="kpi-list">
          <li v-for="(f, i) in fristen.slice(0, 5)" :key="i"
              class="kpi-item" :class="{ overdue: f.overdue }"
              @click.stop="f.tab && $emit('open-fristen', f.tab)">
            <span class="kpi-item-text">{{ f.text }}</span>
            <span v-if="f.due" class="kpi-item-meta" :class="{ overdue: f.overdue }">
              {{ f.overdue ? $t('geteilt.moduleDashboard.uberfallig') : $t('geteilt.moduleDashboard.fallig') }} {{ f.due }}
            </span>
          </li>
        </ul>
      </div>

      <!-- Dokumente-Status (Soll-Ist) -->
      <div v-if="mitDokumente" class="kpi-card clickable" @click="$emit('open-dokumente')">
        <div class="kpi-head">
          <span class="kpi-icon">📄</span>
          <span class="kpi-title">{{ $t('geteilt.moduleDashboard.dokumente') }}</span>
        </div>
        <div class="kpi-value" :class="dokFehlt ? 'warn' : 'ok'">
          {{ dokFertig }}<span class="kpi-of">/ {{ dokGesamt }}</span>
        </div>
        <div class="kpi-sub">{{ $t('geteilt.moduleDashboard.dokSub', { v0: dokFehlt }) }}</div>
        <div v-if="dokGesamt" class="dok-bar">
          <div class="dok-bar-fill" :style="{ width: dokPct + '%' }"></div>
        </div>
        <div v-else class="kpi-sub muted">{{ $t('geteilt.moduleDashboard.keinDokumentenKatalogGeladen') }}</div>
      </div>

      <!-- Risiko-Kurzübersicht (read-only Verweis aufs Risiko-Cockpit) -->
      <div v-if="mitRisiken" class="kpi-card clickable" @click="$emit('open-risiken')">
        <div class="kpi-head">
          <span class="kpi-icon">⚠️</span>
          <span class="kpi-title">{{ $t('geteilt.moduleDashboard.offeneRisiken') }}</span>
        </div>
        <!--
          #2037: Drei Zustände, nicht zwei. Im Fehlerfall **keine** Ampelfarbe
          und keine Zahl — eine grüne Null bei einem Mandanten mit offenen
          kritischen Risiken ist die Fehlerklasse, die diese Akte nicht haben
          darf. Das Muster steht in derselben Datei bei den Dokumenten
          („Kein Dokumenten-Katalog geladen").
        -->
        <div class="kpi-value" :class="risiko.fehler ? 'unbekannt' : (risiko.gesamt ? 'warn' : 'ok')">
          {{ risikoLoading ? '…' : (risiko.fehler ? '–' : risiko.gesamt) }}
        </div>
        <div v-if="!risiko.fehler" class="kpi-sub">{{ $t('geteilt.moduleDashboard.nachSchwereZumRisikoCockpit') }}</div>
        <div v-else class="kpi-sub warnung">{{ $t('geteilt.moduleDashboard.risikoStandNichtAbrufbar') }}</div>
        <div v-if="risiko.fehler && !risikoLoading" class="kpi-sub muted">
          {{ $t('geteilt.moduleDashboard.risikoStandNichtAbrufbarHinweis') }}
        </div>
        <div v-else-if="risiko.gesamt" class="sev-row">
          <span v-if="risiko.kritisch" class="sev sev-kritisch">{{ $t('geteilt.moduleDashboard.sev_kritisch', { v0: risiko.kritisch }) }}</span>
          <span v-if="risiko.hoch" class="sev sev-hoch">{{ $t('geteilt.moduleDashboard.sev_hoch', { v0: risiko.hoch }) }}</span>
          <span v-if="risiko.mittel" class="sev sev-mittel">{{ $t('geteilt.moduleDashboard.sev_mittel', { v0: risiko.mittel }) }}</span>
          <span v-if="risiko.niedrig" class="sev sev-niedrig">{{ $t('geteilt.moduleDashboard.sev_niedrig', { v0: risiko.niedrig }) }}</span>
        </div>
        <div v-else-if="!risikoLoading" class="kpi-sub muted">
          {{ risiko.unassigned ? $t('geteilt.moduleDashboard.keinerFirmaZugeordnet') : $t('geteilt.moduleDashboard.keineOffenenRisiken') }}
        </div>
      </div>

      <!--
        Weitere Kacheln je Modul (#1747). Generisch und optional: Die Komponente
        verzweigt nicht nach Modul, sie rendert nur, was die View ihr gibt — wer
        nichts übergibt, bekommt keine zusätzliche Kachel (statt einer leeren).
      -->
      <div v-for="k in extraKpis" :key="k.id" class="kpi-card clickable"
           @click="$emit('open-kpi', k.id)">
        <div class="kpi-head">
          <span class="kpi-icon">{{ k.icon }}</span>
          <span class="kpi-title">{{ k.title }}</span>
        </div>
        <div class="kpi-value" :class="k.tone === 'warn' ? 'warn' : (k.tone === 'ok' ? 'ok' : '')">
          {{ k.value }}
        </div>
        <div class="kpi-sub">{{ k.sub }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MaturityGauge from './MaturityGauge.vue'
import ChapterCard from './ChapterCard.vue'

/**
 * Einheitliches Dashboard für CRA/NIS2/AI-Act/DSGVO (#1250).
 * Komplett "dumm": jede View normalisiert ihre Modul-Daten auf diese Props,
 * damit Optik + Aufbau in allen vier Modulen identisch sind.
 */
export interface DashboardBereich {
  id: string
  title?: string
  percent: number
  bewertet?: number
  gesamt?: number
  ampel?: string
}
export interface DashboardLuecke {
  id: string
  titel: string
  bewertung: number
}
export interface DashboardFrist {
  text: string
  due?: string | null
  overdue?: boolean
  tab?: string
}
/** Zusätzliche, modul-eigene KPI-Kachel — read-only, Klick meldet nur die id. */
export interface DashboardKpi {
  id: string
  icon?: string
  title: string
  value: number | string
  sub?: string
  tone?: string
}
/** Eine Zeile unter der Reifegrad-Anzeige: Schlüssel + Werte (#2041). */
export interface DashboardStat {
  key: string
  /**
   * Die Platzhalter der Nachricht (``{v0}``, ``{v1}`` …).
   *
   * ``undefined`` ist zugelassen, weil TypeScript einem Array-Literal mit
   * verschieden geformten Objekten genau das zuweist: Das kürzere Element
   * bekommt ``v1?: undefined`` — „dieser Schlüssel ist **abwesend**", nicht
   * „hat den Wert undefined". Ein Cast (``as DashboardStat[]``) hätte den
   * Prüfer nur stumm gestellt.
   *
   * Damit die Lockerung nichts aufreißt, wirft ``saubereWerte`` leere Werte
   * vor dem Rendern weg — sonst stünde bei einem echten ``undefined``
   * „undefined" in der Oberfläche, und das sieht aus wie ein Defekt.
   */
  werte?: Record<string, string | number | undefined>
}
export interface DashboardRisiko {
  gesamt: number
  kritisch?: number
  hoch?: number
  mittel?: number
  niedrig?: number
  unassigned?: boolean
  /**
   * #2037: Der Abruf ist gescheitert. Ohne diesen dritten Zustand war ein
   * Ausfall des Risiko-Cockpits von echter Risikofreiheit nicht zu
   * unterscheiden: `gesamt = 0` → Kachel grün → darunter „Keine offenen
   * Risiken". Das ist nicht ein fehlender Hinweis, sondern die **gegenteilige
   * Aussage** — auf dem ersten Tab von sechs Modulen, verlinkt, und auf der
   * Seite, die ein Mandant oder Prüfer zuerst sieht.
   */
  fehler?: boolean
}

const props = withDefaults(defineProps<{
  gesamt: { percent: number; ampel?: string }
  /**
   * #2041: **Schlüssel mit Werten**, keine fertigen Sätze.
   *
   * Vorher ``string[]`` — und damit konnte die Komponente ihre eigene
   * Übersetzung nicht durchsetzen: Alle sechs Aufrufer hatten deutsche
   * Literale hineingeschrieben (``"142 / 180 Punkte"``), und die standen
   * auf der ersten Seite jedes Moduls auch mit ``en`` als Anzeigesprache.
   *
   * Eine Komponente, die Sätze entgegennimmt, ist nicht umschaltbar. Dort
   * gehören Schlüssel und Zahlen hin.
   */
  gesamtStats?: DashboardStat[]
  bereiche?: DashboardBereich[]
  offenePunkte?: DashboardLuecke[]
  schwelle?: number
  /** true, wenn das Modul einen Fristen-Bereich hat (sonst Kachel inaktiv). */
  fristenTab?: boolean
  fristen?: DashboardFrist[]
  /** Dokumente-Soll-Ist: erstellt/freigegeben vs. gesamt. */
  dokFertig?: number
  dokGesamt?: number
  risiko?: DashboardRisiko
  risikoLoading?: boolean
  /**
   * Hat das Modul einen Dokumente- bzw. Risiko-Bereich? (#1805)
   *
   * Beide Kacheln waren fest eingebaut und **immer** als klickbar dargestellt.
   * Das Compliance-Audit hat keinen dieser Bereiche: Dort standen zwei Kacheln
   * mit Zeigefinger-Cursor, die „0/0 · Kein Dokumenten-Katalog geladen" zeigten
   * und auf einen Klick nichts taten — es gibt keinen Tab, zu dem sie springen
   * könnten. Dieselbe Haltung wie bei `extraKpis` gilt jetzt auch hier: Wer den
   * Bereich nicht hat, bekommt die Kachel nicht statt einer leeren.
   */
  mitDokumente?: boolean
  mitRisiken?: boolean
  /** Modul-eigene Zusatzkacheln (optional, Default leer). */
  extraKpis?: DashboardKpi[]
}>(), {
  gesamtStats: () => [],
  bereiche: () => [],
  offenePunkte: () => [],
  // #2066: Die Vorgabe war 5, gerechnet wurde serverseitig `<= 2` — die Kachel
  // beschriftete eine andere Zahl, als sie zeigte. Die Schwelle kommt jetzt aus
  // der Antwort (`luecken_schwelle`); 4 ist der Rückfall für einen Server, der
  // älter ist als dieser Code, und entspricht der Gate-Schwelle.
  schwelle: 4,
  fristenTab: false,
  fristen: () => [],
  dokFertig: 0,
  dokGesamt: 0,
  risiko: () => ({ gesamt: 0 }),
  risikoLoading: false,
  // Default an: Die vier Module, für die die Komponente gebaut wurde, führen
  // beide Bereiche. Nur wer sie nicht hat, schaltet sie ausdrücklich ab.
  mitDokumente: true,
  mitRisiken: true,
  extraKpis: () => [],
})

/** Leere Platzhalter weg — siehe ``DashboardStat.werte`` (#2041). */
const saubereWerte = (w?: Record<string, string | number | undefined>) => {
  const aus: Record<string, string | number> = {}
  for (const [k, v] of Object.entries(w || {})) if (v !== undefined && v !== null) aus[k] = v
  return aus
}

defineEmits<{
  'open-bereich': [id: string]
  'open-luecken': []
  'open-punkt': [id: string]
  'open-fristen': [tab?: string]
  'open-dokumente': []
  'open-risiken': []
  'open-kpi': [id: string]
}>()

const dokFehlt = computed(() => Math.max(0, (props.dokGesamt || 0) - (props.dokFertig || 0)))
const dokPct = computed(() =>
  props.dokGesamt ? Math.round(((props.dokFertig || 0) / props.dokGesamt) * 100) : 0)
const fristenOffen = computed(() => props.fristen.length)
const fristenUeberfaellig = computed(() => props.fristen.filter(f => f.overdue).length)
</script>

<style scoped>
.module-dashboard { display: flex; flex-direction: column; gap: 16px; }

.dashboard {
  display: grid; grid-template-columns: 280px 1fr; gap: 16px;
}
.gauge-card {
  background: white; border: 1px solid var(--color-border); border-radius: 8px; padding: 16px;
  display: flex; flex-direction: column; align-items: center;
}
.gauge-stats { margin-top: 12px; text-align: center; font-size: 12px; color: #666; }
.gauge-stats div { margin-bottom: 4px; }

.chapters-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px;
  align-content: start;
}
.empty-card {
  grid-column: 1 / -1; background: white; border: 1px dashed var(--color-border);
  border-radius: 8px; padding: 24px; text-align: center; color: #888; font-size: 13px;
}

/* KPI-Kacheln */
.kpi-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px;
}
.kpi-card {
  background: white; border: 1px solid var(--color-border); border-radius: 8px;
  padding: 14px 16px; display: flex; flex-direction: column; gap: 6px;
}
.kpi-card.clickable { cursor: pointer; transition: box-shadow .15s, border-color .15s; }
.kpi-card.clickable:hover { box-shadow: 0 2px 8px rgba(0,0,0,.08); border-color: #1565c0; }

.kpi-head { display: flex; align-items: center; gap: 8px; }
.kpi-icon { font-size: 16px; }
.kpi-title { font-size: 13px; font-weight: 600; color: #263238; }
.kpi-value { font-size: 30px; font-weight: 700; line-height: 1; color: #263238; }
.kpi-value.warn { color: #c62828; }
.kpi-value.ok { color: #2e7d32; }
/* #2037: Der Fehlerfall trägt KEINE Ampelfarbe — er ist keine Aussage über den
   Risikostand. Grau statt grün ist hier die ganze Reparatur. */
.kpi-value.unbekannt { color: #90a4ae; }
.kpi-sub.warnung { color: #ef6c00; font-weight: 600; }
.kpi-of { font-size: 16px; font-weight: 500; color: #90a4ae; margin-left: 4px; }
.kpi-sub { font-size: 11px; color: #607d8b; }
.kpi-sub.muted { color: #b0bec5; font-style: italic; }

.kpi-list { list-style: none; margin: 6px 0 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
.kpi-item {
  display: flex; align-items: center; gap: 6px; padding: 4px 6px;
  background: #fff8e1; border-radius: 4px; cursor: pointer; font-size: 11px;
}
.kpi-item:hover { background: #fff3c4; }
.kpi-item.overdue { background: #ffebee; }
.kpi-item code { background: white; padding: 1px 5px; border-radius: 3px; font-size: 10px;
  max-width: 40%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex-shrink: 0; }
.kpi-item-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kpi-item-meta { font-size: 10px; color: #666; white-space: nowrap; }
.kpi-item-meta.overdue { color: #c62828; font-weight: 600; }

.dok-bar { height: 6px; background: #eceff1; border-radius: 3px; overflow: hidden; margin-top: 4px; }
.dok-bar-fill { height: 100%; background: #1565c0; transition: width .3s ease-out; }

.sev-row { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.sev { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 10px; }
.sev-kritisch { background: #b71c1c; color: #fff; }
.sev-hoch { background: #ffebee; color: #c62828; }
.sev-mittel { background: #fff3e0; color: #e65100; }
.sev-niedrig { background: #e8f5e9; color: #2e7d32; }

@media (max-width: 768px) {
  .dashboard { grid-template-columns: 1fr; }
}
</style>
