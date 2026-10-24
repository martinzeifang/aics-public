<template>
  <!-- v7.0.0: Firmen-Gesamtüberblick — Umsetzungsgrad aller Module, Risiko-Lage,
       DSGVO-TOM/WiBA, offene Aufgaben, Berichte. Daten: GET /firmen/<firma>/uebersicht -->
  <div class="fdash">
    <div v-if="loading && !daten" class="muted pad">⏳ Lade Gesamtüberblick …</div>
    <FehlerHinweis v-else-if="error" :text="error" />

    <template v-else-if="daten">
      <!-- Zeile 1: Gesamt · Risiken · Kennzahlen -->
      <div class="row top">
        <div class="card gauge-card">
          <MaturityGauge :percent="Math.round(daten.gesamt_pct ?? 0)" :ampel="daten.gesamt_ampel"
                         label="Gesamt-Umsetzungsgrad" />
          <p class="muted center">Ø über {{ bewerteteModule }} Modul(e) mit Projekten</p>
        </div>

        <div class="card clickable" @click="$emit('open-tab', 'cockpit')">
          <div class="card-title">⚠️ Offene Risiken</div>
          <div v-if="daten.risiken.unassigned" class="muted">Firma nicht im Risiko-Cockpit zugeordnet.</div>
          <template v-else>
            <div class="big" :class="daten.risiken.total ? 'rot' : 'gruen'">{{ daten.risiken.total }}</div>
            <div class="sev-row">
              <span v-for="s in SEV" :key="s.key" v-show="(daten.risiken.by_severity?.[s.key] || 0) > 0"
                    :class="['sev', s.key]">{{ daten.risiken.by_severity[s.key] }} {{ s.label }}</span>
            </div>
            <ul class="top-list">
              <li v-for="(t, i) in daten.risiken.top.slice(0, 4)" :key="i">
                <span :class="['dot', t.severity]"></span>
                <span class="tl-text" :title="t.titel">{{ t.titel }}</span>
                <span class="tl-src" :title="t.projekt">{{ (t.source || '').toUpperCase() }} · {{ kurz(t.projekt) }}</span>
              </li>
            </ul>
            <div class="link">Zum Risiko-Cockpit →</div>
          </template>
        </div>

        <div class="card">
          <div class="card-title">📌 Kennzahlen</div>
          <div class="kpis">
            <div class="kpi"><span class="kv">{{ projekteGesamt }}</span><span class="kl">Projekte</span></div>
            <div class="kpi"><span class="kv">{{ daten.produkte.length }}</span><span class="kl">Produkte</span></div>
            <div class="kpi"><span class="kv">{{ daten.nachweise }}</span><span class="kl">Nachweise</span></div>
            <div class="kpi"><span :class="['kv', { rot: daten.aufgaben_gesamt }]">{{ daten.aufgaben_gesamt }}</span>
              <span class="kl">offene Aufgaben</span></div>
            <!-- #1582: offene Pentest-Findings (Firmen → 🛡️ Pentests) -->
            <div class="kpi kpi-link" :title="pentestTitel" @click="$emit('open-tab', 'pentest')">
              <span :class="['kv', { rot: daten.pentest?.offen }]">{{ daten.pentest?.offen ?? 0 }}</span>
              <span class="kl">offene Pentest-Findings</span></div>
          </div>
        </div>
      </div>

      <!-- #1749: CRA-Release-Vorgänge. Die Release-Prüfung hängt am Produkt;
           hier steht die Gegenrichtung — welches Release dieses Mandanten ist in
           Prüfung, welches ist rot, wo wartet eine Freigabe. Read-only; alle
           Zahlen kommen aus dem Modul (uebersicht.cra_releases_fuer_projekte).
           Ohne CRA-Projekt liefert der Server den Block nicht → kein Abschnitt. -->
      <template v-if="daten.cra_releases">
        <h3 class="section">
          🚦 Releases
          <span class="sec-meta">
            <span v-if="daten.cra_releases.offen" class="pill offen">{{ daten.cra_releases.offen }} offen</span>
            <span v-if="daten.cra_releases.in_pruefung" class="pill pruefung">
              {{ daten.cra_releases.in_pruefung }} wartet auf Freigabe</span>
            <span v-if="daten.cra_releases.rot" class="pill rot-pill">{{ daten.cra_releases.rot }} rot</span>
            <span v-if="!daten.cra_releases.gesamt" class="muted small">noch kein Release-Vorgang</span>
          </span>
        </h3>
        <div class="module-grid">
          <div v-for="p in daten.cra_releases.produkte" :key="p.projekt" class="card">
            <div class="m-head">
              <router-link :to="`/cra?projekt=${encodeURIComponent(p.projekt)}&tab=releases`"
                           class="p-name m-label" :title="p.projekt">
                {{ p.produkt || kurz(p.projekt) }}</router-link>
              <span :class="['bereit', p.bereit_status]" :title="bereitTitel(p)">{{ BEREIT[p.bereit_status] || p.bereit_status }}</span>
            </div>
            <p v-if="!p.vorgaenge.length" class="muted small">Noch kein Release-Vorgang.</p>
            <ul v-else class="rel-list">
              <li v-for="v in p.vorgaenge" :key="v.version">
                <router-link class="rel-link"
                             :to="`/cra?projekt=${encodeURIComponent(v.projekt)}&tab=releases&version=${encodeURIComponent(v.version)}`">
                  <span class="rel-ver" :title="v.version">{{ v.version }}</span>
                  <span :class="['pill', 'st-' + v.status]">{{ STATUS[v.status] || v.status }}</span>
                  <span :class="['ampel', v.ampel || 'unbekannt']" :title="ampelTitel(v)">{{ AMPEL[v.ampel] || '?' }}</span>
                </router-link>
                <span class="rel-wer">{{ wer(v) }}</span>
              </li>
            </ul>
            <p v-if="p.vorgaenge_gesamt > p.vorgaenge.length" class="muted small">
              … {{ p.vorgaenge_gesamt - p.vorgaenge.length }} älteres Release im Modul
            </p>
          </div>
        </div>
      </template>

      <!-- Zeile 2: Module -->
      <h3 class="section">Umsetzungsgrad je Modul</h3>
      <div class="module-grid">
        <div v-for="m in daten.module" :key="m.key" :class="['card', 'modul', { leer: !m.projekte.length }]">
          <div class="m-head">
            <span class="m-label">{{ m.label }}</span>
            <span v-if="m.key !== 'risikobewertung'" :class="['m-pct', m.ampel]">{{ m.pct == null ? '—' : Math.round(m.pct) + ' %' }}</span>
            <span v-else class="m-pct neutral">{{ rbSumme(m) }} Risiken</span>
          </div>
          <div v-if="m.key !== 'risikobewertung'" class="bar"><span :style="{ width: (m.pct ?? 0) + '%' }" :class="m.ampel"></span></div>
          <p v-if="!m.projekte.length" class="muted small">{{ m.aktiv ? 'Noch kein Projekt.' : 'Modul für diese Firma inaktiv.' }}</p>
          <ul v-else class="p-list">
            <li v-for="p in m.projekte" :key="p.name">
              <router-link :to="`${m.route}?projekt=${encodeURIComponent(p.name)}`" class="p-name" :title="p.name">
                {{ m.key === 'risikobewertung' ? kurz(p.name) : (p.produkt || kurz(p.name)) }}</router-link>
              <span v-if="m.key === 'risikobewertung'" class="p-meta">
                {{ p.risiken }} · <span :class="{ rot: p.offen }">{{ p.offen }} offen</span><span v-if="p.unbewertet"> · {{ p.unbewertet }} unbewertet</span>
              </span>
              <span v-else :class="['p-meta', ampel(p.pct)]">{{ p.pct == null ? '—' : Math.round(p.pct) + ' %' }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- Zeile 3: TOM/WiBA · Aufgaben · Berichte -->
      <div class="row bottom">
        <div class="card">
          <div class="card-title">🔐 DSGVO-TOM &amp; BSI-WiBA</div>
          <p v-if="!daten.tom.length" class="muted small">Noch kein TOM-Katalog (DSGVO → TOM-Katalog).</p>
          <div v-for="t in daten.tom" :key="t.projekt" class="tom-row">
            <div class="tom-head"><span :title="t.projekt">{{ kurz(t.projekt) }}</span>
              <strong :class="ampel(t.pct)">{{ Math.round(t.pct) }} %</strong></div>
            <div class="bar"><span :style="{ width: t.pct + '%' }" :class="ampel(t.pct)"></span></div>
            <div class="muted small">{{ t.anzahl }} TOM · {{ t.aus_wiba }} aus WiBA abgeleitet · {{ t.mit_umsetzung }} mit Umsetzungsbeschreibung</div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">⏰ Offene Aufgaben &amp; Fristen</div>
          <p v-if="!daten.aufgaben.length" class="muted small">Keine offenen Aufgaben.</p>
          <ul v-else class="task-list">
            <li v-for="(a, i) in daten.aufgaben" :key="i" :class="{ overdue: a.overdue }">
              <span class="t-area">{{ a.area_label || a.area }}</span>
              <span class="t-text" :title="a.text">{{ a.text }}</span>
              <span class="t-due">{{ a.due || '' }}</span>
            </li>
          </ul>
        </div>

        <div class="card clickable" @click="$emit('open-tab', 'berichte')">
          <div class="card-title">📄 Berichte</div>
          <p v-if="!daten.berichte.length" class="muted small">Noch keine Berichte erzeugt.</p>
          <ul v-else class="task-list">
            <li v-for="b in daten.berichte" :key="`${b.modul}-${b.id}`">
              <span class="t-area">{{ MODUL_LABEL[b.modul] || b.modul }}</span>
              <span class="t-text" :title="b.projekt">{{ b.typ }} · {{ kurz(b.projekt) }}</span>
              <span class="t-due">{{ (b.erstellt || '').slice(0, 10) }}</span>
            </li>
          </ul>
          <div class="link">Firmen-Gesamtbericht erzeugen →</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'
import { computed } from 'vue'
import MaturityGauge from '../../components/shared/MaturityGauge.vue'

const props = defineProps<{ daten: any; loading?: boolean; error?: string }>()
defineEmits<{ 'open-tab': [tab: string] }>()

const SEV = [
  { key: 'critical', label: 'kritisch' }, { key: 'high', label: 'hoch' },
  { key: 'medium', label: 'mittel' }, { key: 'low', label: 'gering' }, { key: 'unknown', label: 'unbewertet' },
]
const MODUL_LABEL: Record<string, string> = {
  cra: 'CRA', nis2: 'NIS2', ai_act: 'AI Act', dsgvo: 'DSGVO', wiba: 'WiBA', risikobewertung: 'RB',
}
const ampel = (p: number | null | undefined) => p == null ? 'neutral' : p >= 70 ? 'gruen' : p >= 40 ? 'orange' : 'rot'

// #1749: Release-Vorgang — Beschriftungen. Die Werte selbst kommen vom Server
// (freigabe_status, Ampel), hier wird nur übersetzt.
const STATUS: Record<string, string> = {
  entwurf: 'Entwurf', in_pruefung: 'In Prüfung', freigegeben: 'Freigegeben',
  zurueckgewiesen: 'Zurückgewiesen', veroeffentlicht: 'Veröffentlicht',
}
const AMPEL: Record<string, string> = { gruen: '🟢', bedingt: '🟡', rot: '🔴' }
const BEREIT: Record<string, string> = {
  offen: 'CRA-Ready offen', bereit: 'CRA-Ready', entzogen: 'CRA-Ready entzogen',
}
const bereitTitel = (p: any) => p.bereit_status === 'bereit'
  ? `Phase 1 festgestellt${p.bereit_am ? ' am ' + String(p.bereit_am).slice(0, 10) : ''}${p.bereit_von ? ' von ' + p.bereit_von : ''}`
  : 'Phase 1 (CRA-Ready) noch nicht festgestellt'
// „eingefroren" ist bei einem eingereichten Vorgang der richtige Wert, nicht nur
// der billigere: geprüft und freigegeben wurde gegen diesen Stand.
const ampelTitel = (v: any) => !v.ampel
  ? 'Ampel nicht geprüft — im Release-Tab des Moduls öffnen'
  : `${v.ampel}${v.ampel_quelle === 'eingefroren' ? ' (Stand bei Einreichung)' : ' (aktueller Stand)'}`
const wer = (v: any) => {
  const teile: string[] = []
  if (v.erstellt_von) teile.push(`eingereicht von ${v.erstellt_von}`)
  if (v.freigegeben_von) teile.push(`freigegeben von ${v.freigegeben_von}`)
  else if (v.geprueft_von) teile.push(`geprüft von ${v.geprueft_von}`)
  return teile.join(' · ')
}
// Projektnamen „<Firma> – <Produkt>" auf den Produktteil kürzen
const kurz = (n: string) => {
  const f = props.daten?.firma || ''
  return n && f && n.startsWith(f) && n.length > f.length ? n.slice(f.length).replace(/^\s*[–-]\s*/, '') || n : n
}
const rbSumme = (m: any) => m.projekte.reduce((s: number, p: any) => s + (p.risiken || 0), 0)
const projekteGesamt = computed(() => (props.daten?.module || []).reduce((s: number, m: any) => s + m.projekte.length, 0))
const bewerteteModule = computed(() =>
  (props.daten?.module || []).filter((m: any) => m.key !== 'risikobewertung' && m.pct != null).length)

const pentestTitel = computed(() => {
  const p = props.daten?.pentest
  if (!p || !p.berichte) return 'Noch kein Pentest-Bericht — Firmen → 🛡️ Pentests'
  const l = p.letzter
  return `${p.berichte} Bericht(e)${l ? ` · zuletzt „${l.titel}“ ${l.datum_bis || ''}` : ''}`
})
</script>

<style scoped>
.fdash { display: flex; flex-direction: column; gap: 14px; }
.pad { padding: 16px; }
.row { display: grid; gap: 14px; }
.row.top { grid-template-columns: minmax(220px, 1fr) minmax(260px, 1.3fr) minmax(240px, 1fr); }
.row.bottom { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
.card { background: #fff; border: 1px solid var(--color-border, #e0e0e0); border-radius: 10px; padding: 14px 16px; min-width: 0; }
.card.clickable { cursor: pointer; transition: box-shadow .15s, border-color .15s; }
.card.clickable:hover { border-color: #1565c0; box-shadow: 0 2px 10px rgba(21,101,192,.12); }
.card-title { font-weight: 700; color: #37474f; margin-bottom: 8px; font-size: 14px; }
.gauge-card { display: flex; flex-direction: column; align-items: center; justify-content: center; }
.center { text-align: center; }
.muted { color: #78909c; font-size: 13px; }
.small { font-size: 12px; }
.big { font-size: 34px; font-weight: 800; line-height: 1.1; }
.rot { color: #c62828; } .orange { color: #e65100; } .gruen { color: #2e7d32; } .neutral { color: #546e7a; }
.sev-row { display: flex; flex-wrap: wrap; gap: 4px; margin: 6px 0; }
.sev { font-size: 11px; font-weight: 600; padding: 1px 8px; border-radius: 10px; }
.sev.critical { background: #ffebee; color: #b71c1c; } .sev.high { background: #fff3e0; color: #e65100; }
.sev.medium { background: #fffde7; color: #f57f17; } .sev.low { background: #e8f5e9; color: #2e7d32; }
.sev.unknown { background: #eceff1; color: #455a64; }
.top-list, .p-list, .task-list { list-style: none; margin: 6px 0 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.top-list li, .task-list li { display: flex; gap: 6px; align-items: center; font-size: 12px; min-width: 0; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; background: #b0bec5; }
.dot.critical { background: #b71c1c; } .dot.high { background: #e65100; } .dot.medium { background: #f9a825; } .dot.low { background: #2e7d32; }
.tl-text, .t-text { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #37474f; }
.tl-src { font-size: 10px; color: #90a4ae; max-width: 45%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.link { margin-top: 8px; font-size: 12px; color: #1565c0; }
.kpis { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.kpi { display: flex; flex-direction: column; background: #f5f8fb; border-radius: 8px; padding: 8px 10px; }
.kv { font-size: 22px; font-weight: 800; color: #1565c0; }
.kv.rot { color: #c62828; }
.kl { font-size: 11px; color: #607d8b; }
.section { margin: 4px 0 0; font-size: 15px; color: #1565c0; }
.module-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.modul.leer { opacity: .7; }
.m-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.m-label { font-weight: 700; color: #263238; }
.m-pct { font-size: 20px; font-weight: 800; white-space: nowrap; }
.m-pct.neutral { font-size: 14px; }
.bar { height: 6px; background: #eceff1; border-radius: 3px; overflow: hidden; margin: 6px 0 8px; }
.bar span { display: block; height: 100%; background: #b0bec5; }
.bar span.gruen { background: #2e7d32; } .bar span.orange { background: #ef6c00; } .bar span.rot { background: #c62828; }
.p-list li { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; min-width: 0; }
.p-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #1565c0; text-decoration: none; }
.p-name:hover { text-decoration: underline; }
.p-meta { white-space: nowrap; font-weight: 600; color: #546e7a; }
.tom-row { margin-bottom: 8px; }
.tom-head { display: flex; justify-content: space-between; font-size: 13px; gap: 8px; }
.tom-head span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.t-area { font-size: 10px; font-weight: 700; color: #1565c0; background: #e3f2fd; border-radius: 6px; padding: 0 6px; white-space: nowrap; }
.t-due { font-size: 11px; color: #78909c; white-space: nowrap; }
.task-list li.overdue .t-due { color: #c62828; font-weight: 700; }
@media (max-width: 900px) { .row.top { grid-template-columns: 1fr; } }
.kpi-link { cursor: pointer; }
.kpi-link:hover .kl { color: #1565c0; text-decoration: underline; }

/* #1749 Releases */
.sec-meta { display: inline-flex; flex-wrap: wrap; gap: 6px; margin-left: 8px; vertical-align: middle; }
.pill { font-size: 11px; font-weight: 700; padding: 1px 8px; border-radius: 10px; background: #eceff1; color: #455a64; white-space: nowrap; }
.pill.offen { background: #e3f2fd; color: #1565c0; }
.pill.pruefung, .pill.st-in_pruefung { background: #fff3e0; color: #e65100; }
.pill.rot-pill, .pill.st-zurueckgewiesen { background: #ffebee; color: #b71c1c; }
.pill.st-freigegeben { background: #e8f5e9; color: #2e7d32; }
.pill.st-veroeffentlicht { background: #e0f2f1; color: #00695c; }
.rel-list { list-style: none; margin: 8px 0 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.rel-list li { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.rel-link { display: flex; align-items: center; gap: 6px; min-width: 0; text-decoration: none; }
.rel-link:hover .rel-ver { text-decoration: underline; }
.rel-ver { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; font-size: 13px; color: #1565c0; }
.ampel { font-size: 11px; }
.ampel.unbekannt { color: #90a4ae; }
.rel-wer { font-size: 10px; color: #90a4ae; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bereit { font-size: 10px; font-weight: 700; padding: 1px 7px; border-radius: 9px; background: #eceff1; color: #546e7a; white-space: nowrap; }
.bereit.bereit { background: #e8f5e9; color: #2e7d32; }
.bereit.entzogen { background: #ffebee; color: #b71c1c; }
</style>
